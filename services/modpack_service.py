"""Service for exporting and importing complete profiles and modpacks (including configs, resource packs, shaders, and saves)."""

import datetime
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from models.mod_file import ModFile
from services.asset_library import default_asset_library_dir, import_assets, scan_assets
from services.config_backups import find_config_dir
from services.mod_library import file_sha256, import_mods, scan_mods
from services.save_library import default_save_library_dir, find_saves_dir, import_save
from services.user_data import UserDataStore


def _find_instance_folder(instance_path: Path, name: str) -> Path:
    """Locate a folder such as resourcepacks, shaderpacks, or saves inside an instance."""
    for root in (instance_path / ".minecraft", instance_path / "minecraft", instance_path):
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return instance_path / name


def export_profile_to_modpack(
    profile: dict[str, Any],
    library_dir: Path,
    output_archive: Path,
    include_configs: bool = True,
    include_resourcepacks: bool = True,
    include_shaderpacks: bool = True,
    include_saves: bool = False,
    asset_library_dir: Path | None = None,
    save_library_dir: Path | None = None,
    selected_saves: list[str] | None = None,
) -> dict[str, Any]:
    """Export an active profile with its enabled mods, configs, resourcepacks, shaders, and saves."""
    asset_dir = asset_library_dir or default_asset_library_dir()
    output_archive.parent.mkdir(parents=True, exist_ok=True)

    # 1. Collect Mods
    enabled_mod_hashes = set(profile.get("enabled_mod_hashes", []))
    available_mods = scan_mods(library_dir)
    mods_to_export = [mod for mod in available_mods if mod.sha256 in enabled_mod_hashes]

    instance_path_str = profile.get("instance_path") or profile.get("target_path")
    instance_dir = Path(instance_path_str) if instance_path_str else None

    # 2. Collect Configs
    configs_to_add: list[tuple[Path, str]] = []
    if include_configs and instance_dir:
        config_dir = find_config_dir(instance_dir)
        if config_dir and config_dir.is_dir():
            for cfg in config_dir.rglob("*"):
                if cfg.is_file():
                    rel = cfg.relative_to(config_dir).as_posix()
                    configs_to_add.append((cfg, f"config/{rel}"))

    # 3. Collect Resourcepacks
    resourcepacks_to_add: list[tuple[Path, str]] = []
    enabled_rp_hashes = set(profile.get("enabled_resourcepack_hashes", []))
    if include_resourcepacks and enabled_rp_hashes:
        available_rp = scan_assets(asset_dir, "resourcepacks")
        for rp in available_rp:
            if rp.sha256 in enabled_rp_hashes and rp.path.is_file():
                resourcepacks_to_add.append((rp.path, f"resourcepacks/{rp.name}"))

    # 4. Collect Shaderpacks
    shaderpacks_to_add: list[tuple[Path, str]] = []
    enabled_sp_hashes = set(profile.get("enabled_shaderpack_hashes", []))
    if include_shaderpacks and enabled_sp_hashes:
        available_sp = scan_assets(asset_dir, "shaderpacks")
        for sp in available_sp:
            if sp.sha256 in enabled_sp_hashes and sp.path.is_file():
                shaderpacks_to_add.append((sp.path, f"shaderpacks/{sp.name}"))

    # 5. Collect Saves (Worlds)
    saves_to_add: list[tuple[Path, str]] = []
    saves_exported_names: list[str] = []
    if include_saves and instance_dir:
        saves_dir = find_saves_dir(instance_dir)
        if saves_dir.is_dir():
            try:
                for world_dir in sorted(saves_dir.iterdir()):
                    if world_dir.is_dir() and (world_dir / "level.dat").is_file():
                        if selected_saves is None or world_dir.name in selected_saves:
                            saves_exported_names.append(world_dir.name)
                            for wfile in world_dir.rglob("*"):
                                if wfile.is_file():
                                    rel = wfile.relative_to(saves_dir).as_posix()
                                    saves_to_add.append((wfile, f"saves/{rel}"))
            except OSError:
                pass

    manifest: dict[str, Any] = {
        "format_version": 1,
        "generator": "MineOrganizer",
        "name": profile.get("name", "Unnamed Profile"),
        "minecraft_version": profile.get("minecraft_version", ""),
        "loader": profile.get("loader", ""),
        "loader_version": profile.get("loader_version", ""),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mods": [
            {"filename": mod.name, "sha256": mod.sha256, "size": mod.size}
            for mod in mods_to_export
        ],
        "resourcepacks": [
            {"filename": rp[0].name, "sha256": file_sha256(rp[0]), "size": rp[0].stat().st_size}
            for rp in resourcepacks_to_add
        ],
        "shaderpacks": [
            {"filename": sp[0].name, "sha256": file_sha256(sp[0]), "size": sp[0].stat().st_size}
            for sp in shaderpacks_to_add
        ],
        "saves": saves_exported_names,
        "has_configs": bool(configs_to_add),
        "has_resourcepacks": bool(resourcepacks_to_add),
        "has_shaderpacks": bool(shaderpacks_to_add),
        "has_saves": bool(saves_exported_names),
    }

    # Write the zip archive
    with zipfile.ZipFile(output_archive, "w", compression=zipfile.ZIP_DEFLATED) as arc:
        # Manifest
        arc.writestr("modpack.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        # Mods
        for mod in mods_to_export:
            if mod.path.is_file():
                arc.write(mod.path, f"mods/{mod.name}")

        # Configs
        for src_path, arc_path in configs_to_add:
            try:
                arc.write(src_path, arc_path)
            except OSError:
                pass

        # Resourcepacks
        for src_path, arc_path in resourcepacks_to_add:
            try:
                arc.write(src_path, arc_path)
            except OSError:
                pass

        # Shaderpacks
        for src_path, arc_path in shaderpacks_to_add:
            try:
                arc.write(src_path, arc_path)
            except OSError:
                pass

        # Saves
        for src_path, arc_path in saves_to_add:
            try:
                arc.write(src_path, arc_path)
            except OSError:
                pass

    return {
        "mods_count": len(mods_to_export),
        "configs_count": len(configs_to_add),
        "resourcepacks_count": len(resourcepacks_to_add),
        "shaderpacks_count": len(shaderpacks_to_add),
        "saves_count": len(saves_exported_names),
        "archive_size": output_archive.stat().st_size if output_archive.exists() else 0,
    }


def inspect_modpack(archive_path: Path) -> dict[str, Any]:
    """Inspect an archive file to identify complete modpack metadata and structure."""
    if not archive_path.is_file():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    result: dict[str, Any] = {
        "name": archive_path.stem,
        "minecraft_version": "",
        "loader": "",
        "loader_version": "",
        "mod_count": 0,
        "resourcepacks_count": 0,
        "shaderpacks_count": 0,
        "saves_count": 0,
        "has_configs": False,
        "has_resourcepacks": False,
        "has_shaderpacks": False,
        "has_saves": False,
        "format": "generic_zip",
        "mod_filenames": [],
        "save_names": [],
    }

    with zipfile.ZipFile(archive_path, "r") as arc:
        names = set(arc.namelist())

        # 1. MineOrganizer modpack.json
        if "modpack.json" in names:
            try:
                data = json.loads(arc.read("modpack.json").decode("utf-8"))
                result["format"] = "morgpack"
                result["name"] = str(data.get("name") or result["name"])
                result["minecraft_version"] = str(data.get("minecraft_version") or "")
                result["loader"] = str(data.get("loader") or "")
                result["loader_version"] = str(data.get("loader_version") or "")
                result["has_configs"] = bool(data.get("has_configs", False))
                result["has_resourcepacks"] = bool(data.get("has_resourcepacks", False))
                result["has_shaderpacks"] = bool(data.get("has_shaderpacks", False))
                result["has_saves"] = bool(data.get("has_saves", False))
                result["save_names"] = list(data.get("saves", []))
                result["saves_count"] = len(result["save_names"])

                mod_records = data.get("mods", [])
                if isinstance(mod_records, list):
                    result["mod_filenames"] = [
                        m.get("filename") for m in mod_records if isinstance(m, dict) and "filename" in m
                    ]
            except Exception:
                pass

        # 2. Modrinth modrinth.index.json
        elif "modrinth.index.json" in names:
            try:
                data = json.loads(arc.read("modrinth.index.json").decode("utf-8"))
                result["format"] = "modrinth"
                result["name"] = str(data.get("name") or result["name"])
                deps = data.get("dependencies", {})
                result["minecraft_version"] = str(deps.get("minecraft", ""))
                for ldr in ("fabric-loader", "forge", "neoforge", "quilt-loader"):
                    if ldr in deps:
                        result["loader"] = ldr.replace("-loader", "").title()
                        result["loader_version"] = str(deps[ldr])
                        break
                files = data.get("files", [])
                result["mod_filenames"] = [
                    Path(f.get("path", "")).name for f in files if isinstance(f, dict) and "path" in f
                ]
            except Exception:
                pass

        # 3. CurseForge manifest.json
        elif "manifest.json" in names:
            try:
                data = json.loads(arc.read("manifest.json").decode("utf-8"))
                result["format"] = "curseforge"
                result["name"] = str(data.get("name") or result["name"])
                mc = data.get("minecraft", {})
                result["minecraft_version"] = str(mc.get("version", ""))
                mod_loaders = mc.get("modLoaders", [])
                if mod_loaders and isinstance(mod_loaders, list):
                    ldr_id = str(mod_loaders[0].get("id", ""))
                    if "fabric" in ldr_id.lower():
                        result["loader"] = "Fabric"
                    elif "forge" in ldr_id.lower():
                        result["loader"] = "Forge"
                    elif "quilt" in ldr_id.lower():
                        result["loader"] = "Quilt"
                    elif "neoforge" in ldr_id.lower():
                        result["loader"] = "NeoForge"
            except Exception:
                pass

        # Scan actual items in archive
        jar_entries = [name for name in names if name.lower().endswith(".jar") and not name.endswith("/")]
        if jar_entries:
            result["mod_count"] = len(jar_entries)
            if not result["mod_filenames"]:
                result["mod_filenames"] = [Path(j).name for j in jar_entries]
        elif result["mod_filenames"]:
            result["mod_count"] = len(result["mod_filenames"])

        # Check resourcepacks, shaderpacks, saves, configs
        rp_entries = [n for n in names if n.startswith("resourcepacks/") and n.lower().endswith(".zip")]
        sp_entries = [n for n in names if n.startswith("shaderpacks/") and n.lower().endswith(".zip")]
        save_level_dats = [n for n in names if n.startswith("saves/") and n.endswith("level.dat")]

        if rp_entries:
            result["resourcepacks_count"] = len(rp_entries)
            result["has_resourcepacks"] = True
        if sp_entries:
            result["shaderpacks_count"] = len(sp_entries)
            result["has_shaderpacks"] = True
        if save_level_dats:
            result["saves_count"] = len(save_level_dats)
            result["has_saves"] = True
            if not result["save_names"]:
                result["save_names"] = [Path(p).parent.name for p in save_level_dats]

        if any(name.startswith("config/") or name.startswith("overrides/config/") for name in names):
            result["has_configs"] = True

    return result


def is_safe_rel_path(base_dir: Path | str, rel_path: str | None = None) -> bool:
    """Verify that rel_path does not escape base_dir via directory traversal or absolute paths."""
    if rel_path is None:
        target_path = str(base_dir)
        base = Path(".").resolve()
    else:
        target_path = rel_path
        base = Path(base_dir).resolve()
    try:
        norm_path = target_path.replace("\\", "/")
        if not norm_path or norm_path.startswith("/") or Path(target_path).is_absolute():
            return False
        clean = Path(norm_path).as_posix()
        if not clean or clean == "." or clean.startswith("..") or "/../" in f"/{clean}/":
            return False
        dest_resolved = (base / clean).resolve()
        return dest_resolved == base or dest_resolved.is_relative_to(base)
    except (ValueError, OSError):
        return False


def safe_extract_zip_item(arc: zipfile.ZipFile, item: zipfile.ZipInfo, dest_file: Path) -> None:
    """Extract a single zip member to dest_file safely."""
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    with arc.open(item) as src, open(dest_file, "wb") as dst:
        shutil.copyfileobj(src, dst)


def import_modpack_archive(
    archive_path: Path,
    library_dir: Path,
    user_data: UserDataStore,
    target_instance: dict[str, Any] | None = None,
    profile_name_override: str = "",
    extract_configs: bool = True,
    import_resourcepacks: bool = True,
    import_shaderpacks: bool = True,
    import_saves: bool = True,
    asset_library_dir: Path | None = None,
    save_library_dir: Path | None = None,
) -> dict[str, Any]:
    """Import a complete modpack archive into libraries, environment, and user_data."""
    info = inspect_modpack(archive_path)
    asset_dir = asset_library_dir or default_asset_library_dir()
    save_dir = save_library_dir or default_save_library_dir()

    imported_mod_hashes: list[str] = []
    imported_rp_hashes: list[str] = []
    imported_sp_hashes: list[str] = []
    configs_extracted_count = 0
    saves_imported_count = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        temp_jars: list[Path] = []
        temp_rps: list[Path] = []
        temp_sps: list[Path] = []

        inst_dir = None
        if target_instance:
            inst_path_str = target_instance.get("instance_path") or target_instance.get("path")
            if inst_path_str:
                inst_dir = Path(inst_path_str)

        with zipfile.ZipFile(archive_path, "r") as arc:
            for item in arc.infolist():
                name = item.filename
                # 1. Extract Mods
                if name.lower().endswith(".jar") and not item.is_dir():
                    extracted_jar = temp_path / "mods" / Path(name).name
                    extracted_jar.parent.mkdir(parents=True, exist_ok=True)
                    with arc.open(item) as src, open(extracted_jar, "wb") as dst:
                        dst.write(src.read())
                    temp_jars.append(extracted_jar)

                # 2. Extract Resourcepacks
                elif import_resourcepacks and name.startswith("resourcepacks/") and name.lower().endswith(".zip") and not item.is_dir():
                    extracted_rp = temp_path / "resourcepacks" / Path(name).name
                    extracted_rp.parent.mkdir(parents=True, exist_ok=True)
                    with arc.open(item) as src, open(extracted_rp, "wb") as dst:
                        dst.write(src.read())
                    temp_rps.append(extracted_rp)

                # 3. Extract Shaderpacks
                elif import_shaderpacks and name.startswith("shaderpacks/") and name.lower().endswith(".zip") and not item.is_dir():
                    extracted_sp = temp_path / "shaderpacks" / Path(name).name
                    extracted_sp.parent.mkdir(parents=True, exist_ok=True)
                    with arc.open(item) as src, open(extracted_sp, "wb") as dst:
                        dst.write(src.read())
                    temp_sps.append(extracted_sp)

                # 4. Extract Configs into instance safely
                if extract_configs and inst_dir:
                    rel_cfg_path = None
                    if name.startswith("config/") and not item.is_dir():
                        rel_cfg_path = name[len("config/"):]
                    elif name.startswith("overrides/config/") and not item.is_dir():
                        rel_cfg_path = name[len("overrides/config/"):]

                    cfg_root = inst_dir / "config"
                    if rel_cfg_path:
                        if not is_safe_rel_path(cfg_root, rel_cfg_path):
                            raise ValueError(f"Insecure path in archive: {name}")
                        dest_cfg = cfg_root / rel_cfg_path
                        safe_extract_zip_item(arc, item, dest_cfg)
                        configs_extracted_count += 1

                # 5. Extract Saves (Worlds) into instance saves and/or save library safely
                if import_saves and name.startswith("saves/") and not item.is_dir():
                    rel_save_path = name[len("saves/"):]
                    if rel_save_path:
                        # Extract directly into instance saves
                        if inst_dir:
                            target_saves_dir = find_saves_dir(inst_dir)
                            if not is_safe_rel_path(target_saves_dir, rel_save_path):
                                raise ValueError(f"Insecure path in archive: {name}")
                            dest_save = target_saves_dir / rel_save_path
                            safe_extract_zip_item(arc, item, dest_save)

                        # Also extract into save library
                        if not is_safe_rel_path(save_dir, rel_save_path):
                            raise ValueError(f"Insecure path in archive: {name}")
                        dest_lib_save = save_dir / rel_save_path
                        safe_extract_zip_item(arc, item, dest_lib_save)

            # Count extracted saves by checking level.dat
            if import_saves:
                if inst_dir:
                    target_saves_dir = find_saves_dir(inst_dir)
                    if target_saves_dir.is_dir():
                        saves_imported_count = sum(
                            1 for item in target_saves_dir.iterdir() if item.is_dir() and (item / "level.dat").is_file()
                        )
                elif save_dir.is_dir():
                    saves_imported_count = sum(
                        1 for item in save_dir.iterdir() if item.is_dir() and (item / "level.dat").is_file()
                    )

        # Import JARs into shared mod library
        if temp_jars:
            import_mods(temp_jars, library_dir)
            for jar in temp_jars:
                target_jar = library_dir / jar.name
                if target_jar.is_file():
                    imported_mod_hashes.append(file_sha256(target_jar))

        # Import Resourcepacks
        if temp_rps:
            import_assets(temp_rps, asset_dir, "resourcepacks")
            rp_dest_dir = asset_dir / "resourcepacks"
            for rp in temp_rps:
                target_rp = rp_dest_dir / rp.name
                if target_rp.is_file():
                    imported_rp_hashes.append(file_sha256(target_rp))

            # Also copy to instance resourcepacks folder if target instance exists
            if inst_dir:
                inst_rp_dir = _find_instance_folder(inst_dir, "resourcepacks")
                inst_rp_dir.mkdir(parents=True, exist_ok=True)
                for rp in temp_rps:
                    try:
                        shutil.copy2(rp, inst_rp_dir / rp.name)
                    except OSError:
                        pass

        # Import Shaderpacks
        if temp_sps:
            import_assets(temp_sps, asset_dir, "shaderpacks")
            sp_dest_dir = asset_dir / "shaderpacks"
            for sp in temp_sps:
                target_sp = sp_dest_dir / sp.name
                if target_sp.is_file():
                    imported_sp_hashes.append(file_sha256(target_sp))

            # Also copy to instance shaderpacks folder if target instance exists
            if inst_dir:
                inst_sp_dir = _find_instance_folder(inst_dir, "shaderpacks")
                inst_sp_dir.mkdir(parents=True, exist_ok=True)
                for sp in temp_sps:
                    try:
                        shutil.copy2(sp, inst_sp_dir / sp.name)
                    except OSError:
                        pass

    # Create profile
    profile_name = profile_name_override.strip() or info["name"] or archive_path.stem
    instance_info = target_instance or {
        "instance_id": "",
        "instance_path": "",
        "minecraft_version": info["minecraft_version"],
        "loader": info["loader"],
        "loader_version": info["loader_version"],
    }

    profile = user_data.add_profile(
        name=profile_name,
        instance={
            "instance_id": str(instance_info.get("instance_id", "")),
            "instance_path": str(instance_info.get("instance_path") or instance_info.get("path", "")),
            "minecraft_version": str(instance_info.get("minecraft_version") or info["minecraft_version"]),
            "loader": str(instance_info.get("loader") or info["loader"]),
            "loader_version": str(instance_info.get("loader_version") or info["loader_version"]),
        },
        mod_hashes=imported_mod_hashes,
    )

    if imported_rp_hashes:
        user_data.update_profile_assets(profile["id"], "resourcepacks", imported_rp_hashes)
    if imported_sp_hashes:
        user_data.update_profile_assets(profile["id"], "shaderpacks", imported_sp_hashes)

    return {
        "profile": profile,
        "mods_imported": len(imported_mod_hashes),
        "resourcepacks_imported": len(imported_rp_hashes),
        "shaderpacks_imported": len(imported_sp_hashes),
        "configs_extracted": configs_extracted_count,
        "saves_imported": saves_imported_count,
        "info": info,
    }
