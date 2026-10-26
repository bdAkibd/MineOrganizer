"""Safe profile application for resource packs and shader packs."""

import errno
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.asset_library import default_asset_library_dir, scan_assets
from services.mod_library import file_sha256
from services.virtualization import create_library_reference, default_backup_dir


@dataclass(slots=True)
class AssetAction:
    """A planned asset filesystem operation."""

    filename: str
    action: str
    details: str
    path: Path


@dataclass(slots=True)
class AssetPlan:
    """Read-only preview for a profile's asset links."""

    instance_path: Path
    category: str
    target_dir: Path | None
    actions: list[AssetAction]
    errors: list[str]

    @property
    def can_apply(self) -> bool:
        """Whether safe changes can be applied."""
        return self.target_dir is not None and not self.errors and any(action.action in {"Create link", "Remove link"} for action in self.actions)


def _target_dir(instance_path: Path, category: str) -> Path:
    """Finds the game's asset directory or returns its conventional location."""
    for root in (instance_path / ".minecraft", instance_path / "minecraft", instance_path):
        candidate = root / category
        if candidate.is_dir():
            return candidate
    if (instance_path / ".minecraft").is_dir():
        return instance_path / ".minecraft" / category
    if (instance_path / "minecraft").is_dir():
        return instance_path / "minecraft" / category
    return instance_path / category


def _managed_link(path: Path, category_library: Path) -> bool:
    """Checks that a symlink, hardlink, or managed copy points to a file inside the relevant library."""
    if not path.exists():
        return False
    if path.is_symlink():
        try:
            path.resolve().relative_to(category_library.resolve())
            return path.is_file()
        except (OSError, ValueError):
            return False
    candidate = category_library / path.name
    try:
        if candidate.is_file():
            if os.path.samefile(path, candidate):
                return True
            if path.stat().st_size == candidate.stat().st_size and file_sha256(path) == file_sha256(candidate):
                return True
    except OSError:
        pass
    return False


def preview_assets(profile: dict[str, Any], library_root: Path, kind: str) -> AssetPlan:
    """Previews resourcepack or shaderpack changes without filesystem mutation."""
    category = "resourcepacks" if kind == "resourcepacks" else "shaderpacks"
    field = "enabled_resourcepack_hashes" if category == "resourcepacks" else "enabled_shaderpack_hashes"
    instance_path = Path(str(profile.get("instance_path", "")))
    target = _target_dir(instance_path, category)
    plan = AssetPlan(instance_path, category, target, [], [])
    if not instance_path.is_dir():
        plan.errors.append(f"Instance directory not found: {instance_path}")
        return plan
    category_library = library_root / category
    assets = scan_assets(library_root, category)
    by_hash = {asset.sha256: asset for asset in assets}
    selected = set(profile.get(field, []))
    missing = selected - set(by_hash)
    for digest in sorted(missing):
        plan.actions.append(AssetAction(digest[:12], "Not in library", "Archive selected in the profile but missing from the library", target / digest[:12]))
        plan.errors.append(f"Archive missing from the library: {digest[:12]}")
    desired = [by_hash[digest] for digest in selected if digest in by_hash]
    desired_by_name = {asset.name.casefold(): asset for asset in desired}
    try:
        entries = list(target.iterdir()) if target.is_dir() else []
    except OSError as error:
        plan.errors.append(f"Could not read directory {target}: {error}")
        return plan
    current_by_name = {entry.name.casefold(): entry for entry in entries}
    for entry in entries:
        if entry.suffix.lower() != ".zip":
            continue
        if _managed_link(entry, category_library):
            wanted = desired_by_name.get(entry.name.casefold())
            is_match = False
            if wanted:
                if entry.is_symlink():
                    try:
                        is_match = (entry.resolve() == wanted.path.resolve())
                    except OSError:
                        is_match = False
                else:
                    try:
                        is_match = (
                            (wanted.path.exists() and os.path.samefile(entry, wanted.path))
                            or (entry.stat().st_size == wanted.path.stat().st_size and file_sha256(entry) == wanted.sha256)
                        )
                    except OSError:
                        is_match = False
            if is_match:
                plan.actions.append(AssetAction(entry.name, "Keep link", "Already matches profile", entry))
            else:
                plan.actions.append(AssetAction(entry.name, "Remove link", "Managed link to a library archive that is not selected in the profile", entry))
        elif entry.name.casefold() in desired_by_name:
            plan.actions.append(AssetAction(entry.name, "Conflict", "A regular file with this name will not be overwritten", entry))
            plan.errors.append(f"Name conflict: {entry.name}")
        else:
            plan.actions.append(AssetAction(entry.name, "Keep external file", "Not managed by MineOrganizer", entry))
    for asset in desired:
        if asset.name.casefold() not in current_by_name:
            plan.actions.append(AssetAction(asset.name, "Create link", f"Link to {asset.path}", target / asset.name))
    if not plan.actions:
        plan.actions.append(AssetAction("—", "No changes", "Folder already matches the profile", target))
    return plan


def apply_assets(profile: dict[str, Any], library_root: Path, kind: str, backup_dir: Path | None = None) -> tuple[bool, str]:
    """Applies asset links and records a reversible manifest."""
    plan = preview_assets(profile, library_root, kind)
    if plan.errors:
        return False, "\n".join(plan.errors)
    if plan.target_dir is None:
        return False, "Target folder not found."
    if not plan.can_apply:
        return True, "No changes required."
    category_library = library_root / plan.category
    assets = scan_assets(library_root, plan.category)
    field = "enabled_resourcepack_hashes" if plan.category == "resourcepacks" else "enabled_shaderpack_hashes"
    selected = set(profile.get(field, []))
    desired = [asset for asset in assets if asset.sha256 in selected]
    remove_paths = [action.path for action in plan.actions if action.action == "Remove link"]
    remove_names = {path.name.casefold() for path in remove_paths}
    create_assets = [asset for asset in desired if asset.name.casefold() in remove_names or not (plan.target_dir / asset.name).exists()]
    manifest: dict[str, Any] = {"id": uuid.uuid4().hex, "type": "assets", "category": plan.category, "profile_name": str(profile.get("name", "")), "target_dir": str(plan.target_dir), "created_links": [], "removed_links": [], "completed": False, "rolled_back": False}
    backup_dir = backup_dir or (default_backup_dir() / "assets")
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = backup_dir / f"{manifest['id']}.json"

    def save_manifest() -> None:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    save_manifest()
    try:
        plan.target_dir.mkdir(parents=True, exist_ok=True)
        for path in remove_paths:
            if not _managed_link(path, category_library):
                raise RuntimeError(f"The link changed after preview: {path}")
            is_symlink = path.is_symlink()
            target_path = path.resolve() if is_symlink else (category_library / path.name).resolve()
            manifest["removed_links"].append({
                "path": str(path),
                "target": str(target_path),
                "kind": "symlink" if is_symlink else "hardlink",
            })
            save_manifest()
            path.unlink()
        for asset in create_assets:
            destination = plan.target_dir / asset.name
            if destination.exists() or destination.is_symlink():
                raise RuntimeError(f"Path is already occupied; the file was not overwritten: {destination}")
            kind = create_library_reference(asset.path, destination)
            manifest["created_links"].append({
                "path": str(destination),
                "target": str(asset.path.resolve()),
                "kind": kind,
            })
            save_manifest()
    except (OSError, RuntimeError) as error:
        errors = _undo(manifest, category_library)
        manifest["rolled_back"] = not errors
        manifest["rollback_errors"] = errors
        save_manifest()
        return False, f"Could not apply assets: {error}" + ("\nRollback errors: " + "; ".join(errors) if errors else "\nPartial changes were rolled back.")
    manifest["completed"] = True
    save_manifest()
    return True, f"Application completed. Links created: {len(manifest['created_links'])}; removed: {len(manifest['removed_links'])}."


def rollback_assets(backup_dir: Path | None = None, library_root: Path | None = None) -> tuple[bool, str]:
    """Rolls back the latest completed asset operation."""
    backup_dir = backup_dir or (default_backup_dir() / "assets")
    manifests: list[tuple[float, Path, dict[str, Any]]] = []
    if not backup_dir.is_dir():
        return False, "No asset operations are available for rollback."
    for path in backup_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("completed") and not data.get("rolled_back"):
                manifests.append((path.stat().st_mtime, path, data))
        except (OSError, json.JSONDecodeError):
            continue
    if not manifests:
        return False, "No applied asset operations are available for rollback."
    _, manifest_path, manifest = max(manifests, key=lambda item: item[0])
    library = (library_root or default_asset_library_dir()) / manifest.get("category", "")
    errors = _undo(manifest, library)
    manifest["rolled_back"] = not errors
    manifest["rollback_errors"] = errors
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return (not errors, "Rollback completed." if not errors else "Rollback errors: " + "; ".join(errors))


def _undo(manifest: dict[str, Any], library_dir: Path) -> list[str]:
    """Reverses only paths recorded by an asset operation."""
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
                errors.append(f"Changed path was preserved: {path}")
        except OSError as error:
            errors.append(f"{path}: {error}")
    for record in reversed(manifest.get("removed_links", [])):
        path = Path(record["path"])
        target = Path(record["target"])
        try:
            if path.exists() or path.is_symlink():
                errors.append(f"Cannot restore; path is occupied: {path}")
            elif _is_inside(target, library_dir):
                if record.get("kind") == "hardlink":
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
            else:
                errors.append(f"The target is no longer in the library: {target}")
        except OSError as error:
            errors.append(f"{path}: {error}")
    return errors


def _is_inside(path: Path, parent: Path) -> bool:
    """Checks whether path is inside parent."""
    try:
        path.resolve().relative_to(parent.resolve())
        return path.is_file()
    except (OSError, ValueError):
        return False
