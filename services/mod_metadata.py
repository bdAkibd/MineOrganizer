"""Extract mod metadata and perform approximate compatibility checks."""

import json
import hashlib
import os
import re
import tempfile
import threading
import time
import tomllib
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_MODRINTH_CACHE_TTL = 30 * 24 * 60 * 60
_MODRINTH_MISS_TTL = 6 * 60 * 60
_modrinth_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_modrinth_cache_loaded = False
_modrinth_cache_lock = threading.Lock()


@dataclass(slots=True)
class ModMetadata:
    """Normalized metadata for a mod JAR file."""

    name: str = ""
    mod_id: str = ""
    version: str = ""
    minecraft_ranges: list[str] = field(default_factory=list)
    loader_ids: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    required_mod_ids: list[str] = field(default_factory=list)
    source: str = ""
    kind: str = "Mod"
    icon_bytes: bytes | None = None


def read_mod_metadata(path: Path) -> ModMetadata:
    """Read supported Fabric, Quilt, Forge, NeoForge, and mcmod.info formats."""
    result = ModMetadata(name=path.stem)
    try:
        if not zipfile.is_zipfile(path):
            raise zipfile.BadZipFile
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            icon_name = ""
            if "plugin.yml" in names:
                try:
                    plugin_text = archive.read("plugin.yml").decode("utf-8-sig")
                    plugin_data = _read_simple_yaml(plugin_text)
                    result.name = str(plugin_data.get("name") or result.name)
                    result.mod_id = str(plugin_data.get("name") or "").casefold().replace(" ", "")
                    result.version = _clean_version(plugin_data.get("version"))
                    api_version = str(plugin_data.get("api-version") or "")
                    result.source = "Bukkit/Spigot/Paper plugin.yml"
                    result.kind = "Plugin"
                    result.loader_ids = ["Bukkit/Spigot/Paper"]
                    if api_version:
                        result.minecraft_ranges.append(api_version)
                except (UnicodeDecodeError, ValueError):
                    pass
            elif "fabric.mod.json" in names:
                data = _read_json(archive, "fabric.mod.json")
                if isinstance(data, dict):
                    result.name = str(data.get("name") or result.name)
                    result.mod_id = str(data.get("id") or "")
                    result.version = _clean_version(data.get("version"))
                    result.source = "Fabric metadata"
                    result.loader_ids.append("fabric")
                    _collect_json_dependencies(data.get("depends"), result)
                    icon_val = data.get("icon")
                    if isinstance(icon_val, str):
                        icon_name = icon_val
                    elif isinstance(icon_val, dict) and icon_val:
                        try:
                            icon_name = str(sorted(icon_val.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0)[-1][1])
                        except Exception:
                            icon_name = str(list(icon_val.values())[-1])
            elif "quilt.mod.json" in names:
                data = _read_json(archive, "quilt.mod.json")
                if isinstance(data, dict):
                    quilt = data.get("quilt_loader", {})
                    if not isinstance(quilt, dict):
                        quilt = {}
                    metadata = quilt.get("metadata", {})
                    if not isinstance(metadata, dict):
                        metadata = {}
                    result.name = str(metadata.get("name") or result.name)
                    result.mod_id = str(quilt.get("id") or "")
                    result.version = _clean_version(quilt.get("version"))
                    result.source = "Quilt metadata"
                    result.loader_ids.append("quilt")
                    _collect_json_dependencies(quilt.get("depends"), result)
                    icon_val = metadata.get("icon") or quilt.get("icon")
                    if isinstance(icon_val, str):
                        icon_name = icon_val
                    elif isinstance(icon_val, dict) and icon_val:
                        try:
                            icon_name = str(sorted(icon_val.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0)[-1][1])
                        except Exception:
                            icon_name = str(list(icon_val.values())[-1])
            else:
                toml_name = next((name for name in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml") if name in names), "")
                if toml_name:
                    data = tomllib.loads(archive.read(toml_name).decode("utf-8-sig"))
                    result.source = "NeoForge metadata" if "neoforge" in toml_name else "Forge metadata"
                    result.loader_ids.append("neoforge" if "neoforge" in toml_name else "forge")
                    mods = data.get("mods", [])
                    if isinstance(mods, list) and mods:
                        first = mods[0] if isinstance(mods[0], dict) else {}
                        result.mod_id = str(first.get("modId") or "")
                        result.name = str(first.get("displayName") or result.name)
                        result.version = _clean_version(first.get("version"))
                        logo_file = first.get("logoFile")
                        if isinstance(logo_file, str) and logo_file:
                            icon_name = logo_file
                    for section in data.get("dependencies", {}).values() if isinstance(data.get("dependencies"), dict) else []:
                        if not isinstance(section, list):
                            continue
                        for dependency in section:
                            if not isinstance(dependency, dict):
                                continue
                            dep_id = str(dependency.get("modId") or "")
                            version_range = str(dependency.get("versionRange") or "")
                            if dep_id.lower() == "minecraft" and version_range:
                                result.minecraft_ranges.append(version_range)
                            elif dep_id:
                                result.dependencies.append(f"{dep_id} {version_range}".strip())
                                if dependency.get("mandatory", False) and dep_id.casefold() not in {"forge", "neoforge", "fabricloader", "quilt_loader"}:
                                    result.required_mod_ids.append(dep_id)
                elif "mcmod.info" in names:
                    data = _read_json(archive, "mcmod.info")
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        first = data[0]
                        result.name = str(first.get("name") or result.name)
                        result.mod_id = str(first.get("modid") or "")
                        result.version = _clean_version(first.get("version"))
                        result.source = "mcmod.info"
                        mcversion = str(first.get("mcversion") or "")
                        if mcversion:
                            result.minecraft_ranges.append(mcversion)
                        result.loader_ids.append("forge")
                        logo_file = first.get("logoFile")
                        if isinstance(logo_file, str) and logo_file:
                            icon_name = logo_file

            if icon_name:
                cleaned = icon_name.lstrip("/").replace("\\", "/")
                if cleaned in names:
                    result.icon_bytes = archive.read(cleaned)
                else:
                    for name in names:
                        if name.endswith("/" + cleaned) or name == cleaned:
                            result.icon_bytes = archive.read(name)
                            break
            if not result.icon_bytes:
                for fallback in ("icon.png", "logo.png", "pack.png"):
                    if fallback in names:
                        result.icon_bytes = archive.read(fallback)
                        break
            if result.icon_bytes and len(result.icon_bytes) > 2 * 1024 * 1024:
                result.icon_bytes = None
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, RuntimeError):
        # Keep the result and continue with the hash and filename fallbacks.
        pass
    result.minecraft_ranges = list(dict.fromkeys(result.minecraft_ranges))
    result.loader_ids = list(dict.fromkeys(result.loader_ids))
    result.dependencies = list(dict.fromkeys(result.dependencies))
    result.required_mod_ids = list(dict.fromkeys(result.required_mod_ids))
    # Query the authoritative external source before making any assumption
    # from the filename. A filename can contain the mod release number rather
    # than the Minecraft version, so it must never suppress this lookup.
    # Modrinth is a fallback for a missing/invalid mod release version only.
    # A missing local Minecraft range must not cause us to replace local data
    # with the complete game_versions list returned by the remote record.
    if _is_placeholder_version(result.version):
        online_metadata = _modrinth_metadata(path)
        if online_metadata:
            if _is_placeholder_version(result.version):
                result.version = online_metadata.get("version", result.version)
            if not result.minecraft_ranges:
                result.minecraft_ranges.extend(online_metadata.get("minecraft_ranges", []))
            if not result.loader_ids:
                result.loader_ids.extend(online_metadata.get("loader_ids", []))
            result.source = f"{result.source}; Modrinth API" if result.source else "Modrinth API"

    # Filename parsing is deliberately the final fallback.
    if not result.minecraft_ranges:
        filename_version = _minecraft_version_from_filename(path)
        if filename_version:
            result.minecraft_ranges.append(filename_version)
            if not result.source:
                result.source = "Filename detection"

    if _is_placeholder_version(result.version):
        result.version = _version_from_filename(path, result.minecraft_ranges)
        if result.version:
            result.source = f"{result.source}; Filename detection" if result.source else "Filename detection"
    result.minecraft_ranges = list(dict.fromkeys(result.minecraft_ranges))
    result.loader_ids = list(dict.fromkeys(result.loader_ids))
    return result


def compatibility_for_profile(metadata: ModMetadata, minecraft_version: str, loader: str, available_mod_ids: set[str] | None = None) -> tuple[str, str]:
    """Return a status and explanation without loading or launching the mod."""
    if metadata.kind == "Plugin":
        return "Server plugin", "plugin.yml was found. This is a Bukkit/Spigot/Paper server plugin, not a Fabric/Forge client mod."
    if not metadata.source:
        return "Unknown", "No supported metadata format was found; compatibility was not confirmed."
    normalized_loader = loader.casefold()
    supported = {item.casefold() for item in metadata.loader_ids}
    if normalized_loader in {"fabric", "quilt", "forge", "neoforge"} and supported and normalized_loader not in supported:
        # Some Forge mods also work on NeoForge and vice versa; do not assume this automatically.
        return "Incompatible", f"Metadata specifies loader: {', '.join(metadata.loader_ids)}."
    if metadata.minecraft_ranges and not any(version_matches(minecraft_version, item) for item in metadata.minecraft_ranges):
        return "Incompatible", f"Minecraft version {minecraft_version} does not match the range: {', '.join(metadata.minecraft_ranges)}."
    if not metadata.minecraft_ranges:
        return "Unknown", "No Minecraft range was found in metadata."
    if available_mod_ids is not None:
        missing = sorted(set(metadata.required_mod_ids) - available_mod_ids)
        if missing:
            return "Missing dependencies", "Required dependencies were not selected: " + ", ".join(missing) + "."
    return "Likely compatible", "Metadata found no conflict with Minecraft, the loader, or known required dependencies; this does not guarantee a successful launch."


def minecraft_version_entries(expressions: list[str]) -> list[str]:
    """Split version lists into separate choices while preserving Maven ranges."""
    result: list[str] = []
    for expression in expressions:
        value = expression.strip()
        if value and not (value.startswith(("[", "(")) and value.endswith(("]", ")"))):
            result.extend(part.strip() for part in value.split(",") if part.strip())
        elif value:
            result.append(value)
    return list(dict.fromkeys(result))


def minecraft_version_choices(expressions: list[str]) -> list[str]:
    """Return individual versions for selection, including range boundaries."""
    result: list[str] = []
    version_pattern = re.compile(r"\d+(?:\.\d+){1,3}")
    for expression in expressions:
        value = expression.split("#", 1)[0].strip()
        if not value or value in {"*", "any"}:
            continue
        versions = version_pattern.findall(value)
        if value.startswith(("[", "(")) and value.endswith(")"):
            versions = versions[:-1]
        if value.startswith("("):
            versions = versions[1:]
        if " " in value and all(part.startswith((">=", "<=", ">", "<", "="))
                                 for part in value.split()):
            versions = [
                version for version, constraint in zip(versions, value.split())
                if not constraint.startswith((">", "<")) or constraint.startswith((">=", "<="))
            ]
        for version in versions:
            if version not in result:
                result.append(version)
    return result


def minecraft_version_display(expressions: list[str]) -> str:
    """Format supported Minecraft versions compactly for table display."""
    versions = minecraft_version_choices(expressions)
    if len(versions) <= 2:
        return ", ".join(versions)
    ordered = sorted(versions, key=_version_key)
    return f"{ordered[0]}–{ordered[-1]}"


def _is_placeholder_version(value: str) -> bool:
    """Recognize version placeholders that a build system did not resolve."""
    normalized = str(value or "").strip().casefold()
    if not normalized:
        return True
    return bool(
        re.fullmatch(r"@[^@]*version[^@]*@", normalized)
        or re.fullmatch(r"\$[({][^)}]*version[^)}]*[)}]", normalized)
    )


def _clean_version(value: Any) -> str:
    """Convert metadata versions to text and discard unresolved placeholders."""
    text = str(value or "").strip()
    return "" if _is_placeholder_version(text) else text


def _file_sha1(path: Path) -> str:
    """Calculate the SHA-1 hash required by the Modrinth file lookup API."""
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _modrinth_metadata(path: Path) -> dict[str, Any]:
    """Look up a public file by SHA-1 and return normalized version metadata."""
    global _modrinth_cache_loaded
    file_hash = ""
    try:
        file_hash = _file_sha1(path)
        with _modrinth_cache_lock:
            if not _modrinth_cache_loaded:
                _load_modrinth_cache()
                _modrinth_cache_loaded = True
            cached = _modrinth_cache.get(file_hash)
            if cached:
                checked_at, cached_data = cached
                ttl = _MODRINTH_CACHE_TTL if cached_data else _MODRINTH_MISS_TTL
                if time.time() - checked_at < ttl:
                    return dict(cached_data)
        url = f"https://api.modrinth.com/v2/version_file/{file_hash}?algorithm=sha1"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "MineOrganizer/1.0"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        if file_hash:
            _store_modrinth_cache(file_hash, {})
        return {}
    if not isinstance(data, dict):
        _store_modrinth_cache(file_hash, {})
        return {}
    game_versions = data.get("game_versions", [])
    loaders = data.get("loaders", [])
    normalized = {
        "version": _clean_version(data.get("version_number")),
        "minecraft_ranges": [str(item) for item in game_versions if item],
        "loader_ids": [str(item) for item in loaders if item],
    }
    _store_modrinth_cache(file_hash, normalized)
    return normalized


def _modrinth_cache_path() -> Path:
    """Return the persistent cache location without touching game folders."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return root / "MineOrganizer" / "modrinth_cache.json"


def _load_modrinth_cache() -> None:
    """Load valid SHA-1 results from the persistent cache."""
    try:
        payload = json.loads(_modrinth_cache_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    now = time.time()
    for file_hash, entry in payload.items():
        if not isinstance(entry, dict):
            continue
        checked_at = entry.get("checked_at")
        data = entry.get("data")
        if not isinstance(checked_at, (int, float)) or not isinstance(data, dict):
            continue
        ttl = _MODRINTH_CACHE_TTL if data else _MODRINTH_MISS_TTL
        if now - checked_at < ttl:
            _modrinth_cache[str(file_hash)] = (float(checked_at), data)


def _store_modrinth_cache(file_hash: str, data: dict[str, Any]) -> None:
    """Store one lookup and update the cache atomically."""
    with _modrinth_cache_lock:
        _modrinth_cache[file_hash] = (time.time(), dict(data))
        path = _modrinth_cache_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                key: {"checked_at": checked_at, "data": value}
                for key, (checked_at, value) in _modrinth_cache.items()
            }
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as stream:
                json.dump(payload, stream, ensure_ascii=False)
                temporary_path = Path(stream.name)
            temporary_path.replace(path)
        except OSError:
            try:
                temporary_path.unlink(missing_ok=True)
            except (NameError, OSError):
                pass


def _version_from_filename(path: Path, minecraft_ranges: list[str]) -> str:
    """Try to recover the mod version from the JAR name, excluding Minecraft versions."""
    candidates = re.findall(r"\d+(?:\.\d+){1,3}", path.stem)
    if not candidates:
        return ""
    minecraft_choices = set(minecraft_version_choices(minecraft_ranges))
    mod_candidates = [
        candidate for candidate in candidates
        if candidate not in minecraft_choices
        and not any(version_matches(candidate, expression) for expression in minecraft_ranges)
    ]
    return (mod_candidates or candidates)[-1]


def _minecraft_version_from_filename(path: Path) -> str:
    """Find the Minecraft version in a JAR name when metadata does not provide it."""
    stem = path.stem
    marked = re.findall(r"(?i)(?:mc|minecraft)[-_]?(1\.\d+(?:\.\d+){0,2})", stem)
    if marked:
        return _normalize_minecraft_filename_version(marked[-1])
    candidates = re.findall(r"(?<!\d)(1\.\d+(?:\.\d+){0,2})(?!\d)", stem)
    return _normalize_minecraft_filename_version(candidates[-1]) if candidates else ""


def _normalize_minecraft_filename_version(value: str) -> str:
    """Limit a detected value to the standard three Minecraft version components."""
    parts = value.split(".")
    return ".".join(parts[:3])


def version_matches(version: str, expression: str) -> bool:
    """Match exact versions, lists, simple Maven ranges, and constraints."""
    expression = expression.split("#", 1)[0].strip()
    if "," in expression and not (expression.startswith(("[", "(")) and expression.endswith(("]", ")"))):
        return any(version_matches(version, part) for part in expression.split(","))
    if not expression or expression in {"*", "any"}:
        return True
    if expression.startswith(("[", "(")) and expression.endswith(("]", ")")):
        inner = expression[1:-1]
        if "," in inner:
            lower, upper = (part.strip() for part in inner.split(",", 1))
            if lower and (_version_key(version) < _version_key(lower) or (expression[0] == "(" and _version_key(version) == _version_key(lower))):
                return False
            if upper and (_version_key(version) > _version_key(upper) or (expression[-1] == ")" and _version_key(version) == _version_key(upper))):
                return False
            return True
        return _version_key(version) == _version_key(inner)
    if expression.startswith((">=", "<=" , ">", "<", "=")):
        constraints = expression.split()
        if len(constraints) > 1 and all(item.startswith((">=", "<=", ">", "<", "=")) for item in constraints):
            return all(version_matches(version, item) for item in constraints)
        operator = next(op for op in (">=", "<=", ">", "<", "=") if expression.startswith(op))
        target = expression[len(operator):].strip()
        left, right = _version_key(version), _version_key(target)
        return {">=": left >= right, "<=": left <= right, ">": left > right, "<": left < right, "=": left == right}[operator]
    if "||" in expression:
        return any(version_matches(version, part) for part in expression.split("||"))
    return _version_key(version) == _version_key(expression)


def _version_key(value: str) -> tuple[tuple[int, object], ...]:
    parts = re.findall(r"\d+|[a-zA-Z]+", value.casefold())
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)


def _read_json(archive: zipfile.ZipFile, name: str) -> Any:
    return json.loads(archive.read(name).decode("utf-8-sig"))


def _read_simple_yaml(text: str) -> dict[str, str]:
    """Read simple top-level fields from plugin.yml without external libraries."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("\"'")
        if key.strip() and value:
            result[key.strip()] = value
    return result


def _collect_json_dependencies(value: Any, result: ModMetadata) -> None:
    """Normalize Fabric dependencies (mapping) and Quilt dependencies (object list)."""
    entries: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        entries = [(str(key), constraint) for key, constraint in value.items()]
    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            dependency = item.get("id") or item.get("name")
            constraint = item.get("versions", item.get("version", "*"))
            if dependency:
                entries.append((str(dependency), constraint))
    for dependency, constraint in entries:
        if isinstance(constraint, dict):
            constraint = constraint.get("versions", constraint.get("version", "*"))
        if not isinstance(constraint, (str, int, float, list)):
            continue
        constraints = constraint if isinstance(constraint, list) else [constraint]
        for item in constraints:
            text = str(item)
            dependency_key = dependency.casefold()
            if dependency_key == "minecraft":
                result.minecraft_ranges.append(text)
            elif dependency_key in {"fabricloader", "quilt_loader", "forge", "neoforge"}:
                result.loader_ids.append({"fabricloader": "fabric", "quilt_loader": "quilt"}.get(dependency_key, dependency_key))
                result.dependencies.append(f"{dependency} {text}".strip())
            else:
                result.dependencies.append(f"{dependency} {text}".strip())
                if dependency_key != "java":
                    result.required_mod_ids.append(dependency)
