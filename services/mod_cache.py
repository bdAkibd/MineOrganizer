"""Persistent caching and multi-threaded scanning for mod metadata and hashes."""

import base64
import concurrent.futures
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from models.mod_file import ModFile
from services.mod_library import file_sha1, file_sha256
from services.mod_metadata import ModMetadata, read_mod_metadata


def default_mod_cache_path() -> Path:
    """Return default persistent location for mod hash and metadata cache."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        root = Path(local_app_data)
    else:
        root = Path.home() / ".local" / "share"
    return root / "MineOrganizer" / "mod_cache.json"


def serialize_metadata(meta: ModMetadata) -> dict[str, Any]:
    """Serialize ModMetadata into JSON-compatible dictionary."""
    return {
        "name": meta.name,
        "mod_id": meta.mod_id,
        "version": meta.version,
        "minecraft_ranges": list(meta.minecraft_ranges),
        "loader_ids": list(meta.loader_ids),
        "dependencies": list(meta.dependencies),
        "required_mod_ids": list(meta.required_mod_ids),
        "source": meta.source,
        "kind": meta.kind,
        "icon_b64": base64.b64encode(meta.icon_bytes).decode("ascii") if meta.icon_bytes else None,
    }


def deserialize_metadata(data: dict[str, Any]) -> ModMetadata:
    """Reconstruct ModMetadata from JSON dictionary."""
    icon_b64 = data.get("icon_b64")
    icon_bytes = base64.b64decode(icon_b64.encode("ascii")) if icon_b64 else None
    return ModMetadata(
        name=str(data.get("name", "")),
        mod_id=str(data.get("mod_id", "")),
        version=str(data.get("version", "")),
        minecraft_ranges=[str(v) for v in data.get("minecraft_ranges", [])],
        loader_ids=[str(ldr) for ldr in data.get("loader_ids", [])],
        dependencies=[str(dep) for dep in data.get("dependencies", [])],
        required_mod_ids=[str(req) for req in data.get("required_mod_ids", [])],
        source=str(data.get("source", "")),
        kind=str(data.get("kind", "Mod")),
        icon_bytes=icon_bytes,
    )


class ModCache:
    """Thread-safe persistent cache for mod file SHA digests and extracted metadata."""

    def __init__(self, cache_file: Path | None = None) -> None:
        self.cache_file = cache_file or default_mod_cache_path()
        self._entries: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._dirty = False
        self._load()

    def _load(self) -> None:
        """Load entries from disk if cache file exists."""
        if not self.cache_file.is_file():
            return
        try:
            content = self.cache_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                entries = data.get("entries", {})
                if isinstance(entries, dict):
                    self._entries = entries
        except (OSError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        """Persist entries to disk atomically."""
        with self._lock:
            if not self._dirty:
                return
            self._save_locked()

    def _save_locked(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "entries": self._entries}
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.cache_file.parent, delete=False, suffix=".tmp"
            ) as tmp:
                json.dump(payload, tmp, ensure_ascii=False)
                tmp_path = Path(tmp.name)
            tmp_path.replace(self.cache_file)
            self._dirty = False
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def get(self, path: Path) -> tuple[str, str, ModMetadata] | None:
        """Return (sha256, sha1, metadata) if file matches cached mtime and size."""
        try:
            stat = path.stat()
        except OSError:
            return None

        key = str(path.resolve())
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                # Try fallback by path name or relative path
                entry = self._entries.get(str(path))
            if not entry:
                return None

            if entry.get("size") != stat.st_size or abs(entry.get("mtime", 0.0) - stat.st_mtime) > 0.001:
                return None

            try:
                sha256 = str(entry["sha256"])
                sha1 = str(entry.get("sha1", ""))
                meta = deserialize_metadata(entry["metadata"])
                return sha256, sha1, meta
            except (KeyError, TypeError, ValueError):
                return None

    def put(self, path: Path, sha256: str, sha1: str, meta: ModMetadata) -> None:
        """Store hash and metadata for a file."""
        try:
            stat = path.stat()
        except OSError:
            return

        key = str(path.resolve())
        with self._lock:
            self._entries[key] = {
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "sha256": sha256,
                "sha1": sha1,
                "metadata": serialize_metadata(meta),
            }
            self._dirty = True

    def scan_mods_parallel(
        self,
        library_dir: Path,
        max_workers: int = 4,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> list[tuple[ModFile, ModMetadata]]:
        """Multi-threaded scan of library_dir with cache acceleration."""
        if not library_dir.is_dir():
            return []

        try:
            files = sorted(
                (entry for entry in library_dir.iterdir() if entry.is_file() and entry.suffix.lower() == ".jar"),
                key=lambda e: e.name.casefold(),
            )
        except OSError:
            return []

        total = len(files)
        if total == 0:
            return []

        results: list[tuple[ModFile, ModMetadata] | None] = [None] * total
        uncached_indices: list[int] = []

        # Fast pass: check memory/disk cache
        for idx, path in enumerate(files):
            cached = self.get(path)
            if cached is not None:
                sha256, sha1, meta = cached
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                results[idx] = (ModFile(path.name, path, size, sha256), meta)
            else:
                uncached_indices.append(idx)

        if progress_cb:
            progress_cb(total - len(uncached_indices), total)

        # Process uncached files in parallel pool
        def _process_one(idx: int) -> tuple[int, ModFile, ModMetadata, str]:
            file_path = files[idx]
            size = file_path.stat().st_size
            h256 = file_sha256(file_path)
            h1 = file_sha1(file_path)
            metadata = read_mod_metadata(file_path)
            return idx, ModFile(file_path.name, file_path, size, h256), metadata, h1

        if uncached_indices:
            workers = min(max_workers, len(uncached_indices), os.cpu_count() or 4)
            completed = total - len(uncached_indices)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                futures = {executor.submit(_process_one, i): i for i in uncached_indices}
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        idx, mod_file, meta, h1 = fut.result()
                        results[idx] = (mod_file, meta)
                        self.put(files[idx], mod_file.sha256, h1, meta)
                    except Exception:
                        pass
                    completed += 1
                    if progress_cb:
                        progress_cb(completed, total)

            self.save()

        # Filter non-None results
        valid_items = [item for item in results if item is not None]
        return valid_items


# Global singleton instance
_GLOBAL_CACHE: ModCache | None = None
_GLOBAL_CACHE_LOCK = threading.Lock()


def get_mod_cache() -> ModCache:
    """Return the global shared ModCache instance."""
    global _GLOBAL_CACHE
    with _GLOBAL_CACHE_LOCK:
        if _GLOBAL_CACHE is None:
            _GLOBAL_CACHE = ModCache()
        return _GLOBAL_CACHE
