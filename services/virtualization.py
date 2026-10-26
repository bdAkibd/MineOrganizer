"""Safe preview, application, and rollback of profile mod links."""

import errno
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.mod_library import file_sha256, scan_mods


@dataclass(slots=True)
class VirtualizationAction:
    """One planned filesystem change for a profile."""

    filename: str
    action: str
    details: str
    path: Path


@dataclass(slots=True)
class VirtualizationPlan:
    """Preview result before any game files are changed."""

    profile_name: str
    instance_path: Path
    mods_dir: Path | None
    actions: list[VirtualizationAction]
    errors: list[str]

    @property
    def can_apply(self) -> bool:
        """Whether the plan has a target directory and no blocking errors."""
        return self.mods_dir is not None and not self.errors and any(
            action.action in {"Create link", "Remove link"} for action in self.actions
        )


def default_backup_dir() -> Path:
    """Returns the directory used for virtualization rollback manifests."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "MineOrganizer" / "rollback"
    return Path.home() / ".local" / "share" / "MineOrganizer" / "rollback"


def find_mods_dir(instance_path: Path, profile: dict[str, Any] | None = None) -> Path | None:
    """Finds the mods folder for the selected environment, avoiding a shared root when isolated versions exist."""
    if instance_path.name.casefold() == ".minecraft":
        versions_dir = instance_path / "versions"
        isolated = []
        if versions_dir.is_dir():
            for child in versions_dir.iterdir():
                if not child.is_dir():
                    continue
                has_modded_json = any(
                    marker in child.name.casefold()
                    for marker in ("fabric", "forge", "neoforge", "quilt", "optifine")
                ) and any(child.glob("*.json"))
                if (child / "mods").is_dir() or has_modded_json:
                    isolated.append(child / "mods")
        if isolated:
            version = str((profile or {}).get("minecraft_version", "")).casefold()
            loader = str((profile or {}).get("loader", "")).casefold()
            matching = []
            for mods_dir in isolated:
                folder_name = mods_dir.parent.name.casefold()
                version_match = not version or version in folder_name
                loader_match = not loader or loader in folder_name
                if version_match and loader_match:
                    matching.append(mods_dir)
            if len(matching) == 1:
                return matching[0]
            if len(isolated) == 1:
                return isolated[0]
            return None
    if instance_path.parent.name.casefold() == "versions" and any(instance_path.glob("*.json")):
        name = instance_path.name.casefold()
        if any(marker in name for marker in ("fabric", "forge", "neoforge", "quilt", "optifine")):
            return instance_path / "mods"
    candidates = [instance_path / ".minecraft" / "mods", instance_path / "minecraft" / "mods", instance_path / "mods"]
    for candidate in candidates:
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None


def _is_library_link(path: Path, library_dir: Path) -> bool:
    """Checks whether a symbolic link, hard link, or managed copy resolves to a file inside the library."""
    if not path.exists():
        return False
    if path.is_symlink():
        try:
            path.resolve().relative_to(library_dir.resolve())
            return path.is_file()
        except (OSError, ValueError):
            return False
    candidate = library_dir / path.name
    try:
        if candidate.is_file():
            if os.path.samefile(path, candidate):
                return True
            if path.stat().st_size == candidate.stat().st_size and file_sha256(path) == file_sha256(candidate):
                return True
    except OSError:
        pass
    return False


def preview_profile(profile: dict[str, Any], library_dir: Path) -> VirtualizationPlan:
    """Builds a read-only plan and never changes files."""
    instance_path = Path(str(profile.get("instance_path", "")))
    mods_dir = find_mods_dir(instance_path, profile)
    plan = VirtualizationPlan(str(profile.get("name", "(unnamed)")), instance_path, mods_dir, [], [])
    if not instance_path.is_dir():
        plan.errors.append(f"Instance directory not found: {instance_path}")
        return plan
    if mods_dir is None:
        plan.errors.append("Could not determine this environment's mods folder unambiguously. Select a separate instance instead of a shared .minecraft directory.")
        return plan

    library_mods = scan_mods(library_dir)
    selected_hashes = set(profile.get("enabled_mod_hashes", []))
    by_hash = {mod.sha256: mod for mod in library_mods}
    desired = [by_hash[digest] for digest in selected_hashes if digest in by_hash]
    missing = selected_hashes - set(by_hash)
    for digest in sorted(missing):
        plan.actions.append(VirtualizationAction(digest[:12], "Not in library", "Mod selected in the profile but missing from the library", mods_dir / digest[:12]))
        plan.errors.append(f"Selected mod is missing from the library: {digest[:12]}")
    desired_by_name = {mod.name.casefold(): mod for mod in desired}

    try:
        current_entries = list(mods_dir.iterdir())
    except OSError as error:
        plan.errors.append(f"Could not read the mods folder: {error}")
        return plan

    current_by_name = {entry.name.casefold(): entry for entry in current_entries}
    for entry in current_entries:
        if entry.suffix.lower() != ".jar":
            continue
        if _is_library_link(entry, library_dir):
            target = entry.resolve()
            wanted = desired_by_name.get(entry.name.casefold())
            if wanted is not None and target == wanted.path.resolve():
                plan.actions.append(VirtualizationAction(entry.name, "Keep link", "Already matches profile", entry))
            else:
                plan.actions.append(VirtualizationAction(entry.name, "Remove link", "Managed link to a library mod that is not selected in the profile", entry))
        elif entry.name.casefold() in desired_by_name:
            wanted = desired_by_name[entry.name.casefold()]
            plan.actions.append(VirtualizationAction(entry.name, "Conflict", f"A regular file with this name already exists; it will not be overwritten. Expected {wanted.name}", entry))
            plan.errors.append(f"Name conflict: {entry.name}")
        else:
            plan.actions.append(VirtualizationAction(entry.name, "Keep external file", "Not managed by MineOrganizer and will not be changed", entry))

    for mod in desired:
        if mod.name.casefold() not in current_by_name:
            plan.actions.append(VirtualizationAction(mod.name, "Create link", f"Link to {mod.path}", mods_dir / mod.name))
    if not plan.actions:
        plan.actions.append(VirtualizationAction("—", "No changes", "Folder already matches the profile", mods_dir))
    return plan


def create_library_reference(source: Path, destination: Path) -> str:
    """Creates a symlink, falling back to a hard link or managed copy on Windows."""
    try:
        os.symlink(source, destination, target_is_directory=False)
        return "symlink"
    except OSError as error:
        if os.name != "nt" and error.errno not in {errno.EPERM, errno.EACCES}:
            raise
        try:
            os.link(source, destination)
            return "hardlink"
        except OSError as link_error:
            # If cross-drive boundary (EXDEV / WinError 17) or permission denied, copy as fallback
            if link_error.errno in {errno.EXDEV, errno.EPERM, errno.EACCES} or getattr(link_error, "winerror", None) in {17, 1314}:
                shutil.copy2(source, destination)
                return "copy"
            raise OSError(
                link_error.errno,
                f"Could not create reference link: {link_error}. Original error: {error}",
                str(destination),
            ) from link_error


_create_library_reference = create_library_reference


def apply_profile(profile: dict[str, Any], library_dir: Path, backup_dir: Path | None = None) -> tuple[bool, str]:
    """Applies a profile using library symlinks and records a rollback manifest."""
    backup_dir = backup_dir or default_backup_dir()
    plan = preview_profile(profile, library_dir)
    if plan.errors:
        return False, "\n".join(plan.errors)
    if plan.mods_dir is None:
        return False, "The mods folder for the selected environment was not found."
    if not plan.can_apply:
        return True, "No changes required."

    library_mods = scan_mods(library_dir)
    selected_hashes = set(profile.get("enabled_mod_hashes", []))
    desired = [mod for mod in library_mods if mod.sha256 in selected_hashes]
    remove_paths = [action.path for action in plan.actions if action.action == "Remove link"]
    remove_names = {path.name.casefold() for path in remove_paths}
    create_mods = [
        mod for mod in desired
        if mod.name.casefold() in remove_names
        or (not (plan.mods_dir / mod.name).exists() and not (plan.mods_dir / mod.name).is_symlink())
    ]
    manifest: dict[str, Any] = {
        "id": uuid.uuid4().hex,
        "profile_name": str(profile.get("name", "")),
        "instance_path": str(plan.instance_path),
        "mods_dir": str(plan.mods_dir),
        "created_links": [],
        "removed_links": [],
        "rolled_back": False,
    }
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = backup_dir / f"{manifest['id']}.json"
    _write_manifest(manifest_path, manifest)

    try:
        plan.mods_dir.mkdir(parents=True, exist_ok=True)
        for path in remove_paths:
            if not _is_library_link(path, library_dir):
                raise RuntimeError(f"The link changed after preview: {path}")
            is_symlink = path.is_symlink()
            target_path = path.resolve() if is_symlink else (library_dir / path.name).resolve()
            target = str(target_path)
            manifest["removed_links"].append({"path": str(path), "target": target, "kind": "symlink" if is_symlink else "hardlink"})
            _write_manifest(manifest_path, manifest)
            path.unlink()
        for mod in create_mods:
            destination = plan.mods_dir / mod.name
            if destination.exists() or destination.is_symlink():
                raise RuntimeError(f"Path is already occupied; the file was not overwritten: {destination}")
            kind = _create_library_reference(mod.path, destination)
            manifest["created_links"].append({"path": str(destination), "target": str(mod.path.resolve()), "kind": kind})
            _write_manifest(manifest_path, manifest)
    except (OSError, RuntimeError) as error:
        rollback_errors = _undo_manifest(manifest, library_dir)
        manifest["rolled_back"] = not rollback_errors
        manifest["rollback_errors"] = rollback_errors
        _write_manifest(manifest_path, manifest)
        detail = f"Application did not complete: {error}"
        if rollback_errors:
            detail += "\nThe operation could not be fully rolled back:\n" + "\n".join(rollback_errors)
        else:
            detail += "\nPartial changes were rolled back automatically."
        return False, detail

    manifest["completed"] = True
    _write_manifest(manifest_path, manifest)
    return True, f"Profile applied. File links created: {len(manifest['created_links'])}; removed: {len(manifest['removed_links'])}.\nRollback: {manifest_path}"


def rollback_last(backup_dir: Path | None = None, library_dir: Path | None = None) -> tuple[bool, str]:
    """Undoes the most recent successful virtualization operation."""
    backup_dir = backup_dir or default_backup_dir()
    if not backup_dir.is_dir():
        return False, "No saved operations are available for rollback."
    manifests: list[tuple[float, Path, dict[str, Any]]] = []
    for path in backup_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("completed") and not data.get("rolled_back"):
                manifests.append((path.stat().st_mtime, path, data))
        except (OSError, json.JSONDecodeError):
            continue
    if not manifests:
        return False, "No applied operations are available for rollback."
    _, manifest_path, manifest = max(manifests, key=lambda item: item[0])
    errors = _undo_manifest(manifest, library_dir)
    manifest["rolled_back"] = not errors
    manifest["rollback_errors"] = errors
    _write_manifest(manifest_path, manifest)
    if errors:
        return False, "Rollback was not fully completed:\n" + "\n".join(errors)
    profile_name = manifest.get("profile_name", "")
    return True, f'The last operation was undone for profile "{profile_name}".'


def _undo_manifest(manifest: dict[str, Any], library_dir: Path | None) -> list[str]:
    """Reverses only references recorded by the operation and preserves other files."""
    errors: list[str] = []
    for record in reversed(manifest.get("created_links", [])):
        path = Path(record["path"])
        target = Path(record["target"])
        try:
            is_ours = False
            if path.is_symlink():
                is_ours = str(path.resolve()) == record["target"]
            elif path.exists() and target.exists():
                is_ours = os.path.samefile(path, target) or (
                    record.get("kind") == "copy"
                    and path.stat().st_size == target.stat().st_size
                    and file_sha256(path) == file_sha256(target)
                )
            if is_ours:
                path.unlink()
            elif path.exists() or path.is_symlink():
                errors.append(f"Changed file/link was not removed: {path}")
        except OSError as error:
            errors.append(f"{path}: {error}")
    for record in manifest.get("removed_links", []):
        path = Path(record["path"])
        target = Path(record["target"])
        try:
            if path.is_symlink():
                try:
                    if str(path.resolve()) == str(target.resolve()):
                        continue
                except OSError:
                    pass
                errors.append(f"Path is occupied; the link was not restored: {path}")
            elif path.exists():
                try:
                    if target.exists() and os.path.samefile(path, target):
                        continue
                except OSError:
                    pass
                errors.append(f"Path is occupied; the link was not restored: {path}")
            elif not target.is_file():
                errors.append(f"Library file was not found; the link was not restored: {target}")
            elif record.get("kind") == "hardlink":
                try:
                    os.link(target, path)
                except OSError:
                    create_library_reference(target, path)
            elif record.get("kind") == "copy":
                shutil.copy2(target, path)
            else:
                try:
                    os.symlink(target, path, target_is_directory=False)
                except OSError:
                    create_library_reference(target, path)
        except OSError as error:
            errors.append(f"{path}: {error}")
    return errors


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Writes rollback metadata as JSON."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
