"""Minecraft save library and installation into game environments."""

import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SaveEntry:
    """A save imported into the application library."""

    name: str
    path: Path
    size: int


def default_save_library_dir() -> Path:
    """Return the shared save library directory."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    return (Path(local_app_data) / "MineOrganizer" / "library" / "saves") if local_app_data else Path.home() / ".local" / "share" / "MineOrganizer" / "library" / "saves"


def _directory_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file() and not item.is_symlink():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def scan_saves(library_dir: Path) -> list[SaveEntry]:
    """Scan world folders in the save library."""
    if not library_dir.is_dir():
        return []
    try:
        directories = sorted((item for item in library_dir.iterdir() if item.is_dir()), key=lambda item: item.name.casefold())
    except OSError:
        return []
    return [SaveEntry(item.name, item, _directory_size(item)) for item in directories]


def import_save(source: Path, library_dir: Path) -> tuple[bool, str]:
    """Copy a world folder or extract a world archive into the library without overwriting an existing world."""
    if source.is_file() and source.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(source) as archive:
                names = archive.namelist()
                level_dat_entry = next((n for n in names if n.replace("\\", "/").rstrip("/").split("/")[-1] == "level.dat"), None)
                if not level_dat_entry:
                    return False, "The archive does not contain a level.dat file (not a Minecraft world)."

                parts = Path(level_dat_entry.replace("\\", "/")).parts
                library_dir.mkdir(parents=True, exist_ok=True)
                if len(parts) > 1:
                    world_folder = parts[0]
                    destination = library_dir / world_folder
                    if destination.exists():
                        return False, f'Save "{world_folder}" already exists in the library.'
                    for member in archive.infolist():
                        norm = member.filename.replace("\\", "/")
                        if norm.startswith(world_folder + "/") or norm == world_folder:
                            archive.extract(member, library_dir)
                else:
                    world_folder = source.stem
                    destination = library_dir / world_folder
                    if destination.exists():
                        return False, f'Save "{world_folder}" already exists in the library.'
                    destination.mkdir(parents=True, exist_ok=True)
                    archive.extractall(destination)
                return True, f"Save imported: {destination}"
        except (OSError, zipfile.BadZipFile) as error:
            return False, f"Could not extract save archive: {error}"

    if not source.is_dir():
        return False, "The selected directory is not a Minecraft save."
    library_dir.mkdir(parents=True, exist_ok=True)
    destination = library_dir / source.name
    if destination.exists():
        return False, f'Save "{source.name}" already exists in the library.'
    try:
        shutil.copytree(source, destination)
    except OSError as error:
        if destination.is_dir():
            shutil.rmtree(destination, ignore_errors=True)
        else:
            destination.unlink(missing_ok=True)
        return False, f"Could not import save: {error}"
    return True, f"Save imported: {destination}"


def find_saves_dir(instance_path: Path) -> Path:
    """Find the saves folder in a game environment or return the expected path."""
    for root in (instance_path / ".minecraft", instance_path / "minecraft", instance_path):
        candidate = root / "saves"
        if candidate.is_dir():
            return candidate
    return instance_path / "saves"


def install_save(source: Path, instance_path: Path, overwrite: bool = False) -> tuple[bool, str]:
    """Copy a save into the selected environment's saves folder with explicit overwrite confirmation."""
    if not source.is_dir():
        return False, "Save was not found in the library."
    saves_dir = find_saves_dir(instance_path)
    destination = saves_dir / source.name
    if destination.exists() and not overwrite:
        return False, f'Save "{source.name}" already exists in the selected environment.'
    try:
        saves_dir.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
    except OSError as error:
        return False, f"Could not install save: {error}"
    return True, f"Save installed to {destination}"
