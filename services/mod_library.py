"""Safely scan and import mod files."""

import hashlib
import os
import shutil
from pathlib import Path

from models.mod_file import ModFile


def default_library_dir() -> Path:
    """Return the default shared mod library directory."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "MineOrganizer" / "library" / "mods"
    return Path.home() / ".local" / "share" / "MineOrganizer" / "library" / "mods"


def file_sha256(path: Path) -> str:
    """Compute a file SHA-256 digest using streaming reads."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_sha1(path: Path) -> str:
    """Compute a file SHA-1 digest using streaming reads."""
    digest = hashlib.sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_mods(library_dir: Path) -> list[ModFile]:
    """Return JAR files from the library without modifying files."""
    if not library_dir.is_dir():
        return []

    mods: list[ModFile] = []
    try:
        files = sorted(
            (entry for entry in library_dir.iterdir() if entry.is_file() and entry.suffix.lower() == ".jar"),
            key=lambda entry: entry.name.casefold(),
        )
    except OSError:
        return mods

    for path in files:
        try:
            mods.append(ModFile(path.name, path, path.stat().st_size, file_sha256(path)))
        except OSError:
            continue
    return mods


def import_mods(source_paths: list[Path], library_dir: Path) -> tuple[int, int, list[str]]:
    """Copy a JAR into the library while skipping SHA-256 duplicates."""
    library_dir.mkdir(parents=True, exist_ok=True)
    known_hashes: set[str] = set()
    for mod in scan_mods(library_dir):
        known_hashes.add(mod.sha256)

    imported = 0
    skipped = 0
    errors: list[str] = []

    for source in source_paths:
        if not source.is_file() or source.suffix.lower() != ".jar":
            skipped += 1
            continue
        try:
            digest = file_sha256(source)
            if digest in known_hashes:
                skipped += 1
                continue

            destination = library_dir / source.name
            suffix_index = 2
            while destination.exists():
                destination = library_dir / f"{source.stem} ({suffix_index}){source.suffix}"
                suffix_index += 1

            shutil.copy2(source, destination)
            known_hashes.add(digest)
            imported += 1
        except OSError as error:
            errors.append(f"{source.name}: {error}")

    return imported, skipped, errors
