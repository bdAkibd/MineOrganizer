"""Unit tests for modpack export, inspect, and import service."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from services.asset_library import import_assets, scan_assets
from services.mod_library import file_sha256
from services.modpack_service import (
    export_profile_to_modpack,
    import_modpack_archive,
    inspect_modpack,
)
from services.user_data import UserDataStore


class ModpackServiceTests(unittest.TestCase):
    def test_export_and_inspect_and_import_modpack(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            library_dir = temp_path / "mods"
            library_dir.mkdir()
            asset_dir = temp_path / "assets"
            asset_dir.mkdir()
            (asset_dir / "resourcepacks").mkdir(parents=True)
            (asset_dir / "shaderpacks").mkdir(parents=True)

            instance_dir = temp_path / "instances" / "test_inst"
            instance_dir.mkdir(parents=True)
            config_dir = instance_dir / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "options.txt").write_text("fov:90", encoding="utf-8")

            # Create test save world
            saves_dir = instance_dir / "saves" / "World_1"
            saves_dir.mkdir(parents=True)
            (saves_dir / "level.dat").write_bytes(b"\x1f\x8b\x08dummy_level_data")

            # Create test mod in library
            mod1_path = library_dir / "sodium.jar"
            with zipfile.ZipFile(mod1_path, "w") as arc:
                arc.writestr("fabric.mod.json", '{"id": "sodium", "name": "Sodium", "version": "0.5.8"}')
            mod1_hash = file_sha256(mod1_path)

            # Create test resourcepack
            rp_path = asset_dir / "resourcepacks" / "faithfull.zip"
            with zipfile.ZipFile(rp_path, "w") as arc:
                arc.writestr("pack.mcmeta", '{"pack": {"pack_format": 15, "description": "Faithful"}}')
            rp_hash = file_sha256(rp_path)

            profile = {
                "id": "p1",
                "name": "My Pack",
                "instance_id": "test_inst",
                "instance_path": str(instance_dir),
                "minecraft_version": "1.20.1",
                "loader": "Fabric",
                "loader_version": "0.15.11",
                "enabled_mod_hashes": [mod1_hash],
                "enabled_resourcepack_hashes": [rp_hash],
                "enabled_shaderpack_hashes": [],
            }

            # 1. Export
            pack_path = temp_path / "export.morgpack"
            res = export_profile_to_modpack(
                profile=profile,
                library_dir=library_dir,
                output_archive=pack_path,
                include_configs=True,
                include_resourcepacks=True,
                include_shaderpacks=True,
                include_saves=True,
                asset_library_dir=asset_dir,
            )
            self.assertEqual(res["mods_count"], 1)
            self.assertEqual(res["configs_count"], 1)
            self.assertEqual(res["resourcepacks_count"], 1)
            self.assertEqual(res["saves_count"], 1)
            self.assertTrue(pack_path.exists())

            # 2. Inspect
            info = inspect_modpack(pack_path)
            self.assertEqual(info["format"], "morgpack")
            self.assertEqual(info["name"], "My Pack")
            self.assertEqual(info["minecraft_version"], "1.20.1")
            self.assertEqual(info["loader"], "Fabric")
            self.assertEqual(info["mod_count"], 1)
            self.assertTrue(info["has_configs"])
            self.assertTrue(info["has_resourcepacks"])
            self.assertTrue(info["has_saves"])
            self.assertIn("World_1", info["save_names"])

            # 3. Import into another library and user_data
            dest_library = temp_path / "dest_mods"
            dest_library.mkdir()
            dest_assets = temp_path / "dest_assets"
            dest_assets.mkdir()
            dest_saves = temp_path / "dest_save_lib"
            dest_saves.mkdir()
            user_data_file = temp_path / "dest_user_data.json"
            user_data = UserDataStore(user_data_file)

            dest_instance_dir = temp_path / "instances" / "dest_inst"
            dest_instance_dir.mkdir(parents=True)
            target_instance = {
                "instance_id": "dest_inst",
                "instance_path": str(dest_instance_dir),
                "minecraft_version": "1.20.1",
                "loader": "Fabric",
                "loader_version": "0.15.11",
            }

            import_res = import_modpack_archive(
                archive_path=pack_path,
                library_dir=dest_library,
                user_data=user_data,
                target_instance=target_instance,
                profile_name_override="Imported Pack",
                extract_configs=True,
                import_resourcepacks=True,
                import_shaderpacks=True,
                import_saves=True,
                asset_library_dir=dest_assets,
                save_library_dir=dest_saves,
            )

            self.assertEqual(import_res["mods_imported"], 1)
            self.assertEqual(import_res["configs_extracted"], 1)
            self.assertEqual(import_res["resourcepacks_imported"], 1)
            self.assertEqual(import_res["saves_imported"], 1)
            self.assertTrue((dest_library / "sodium.jar").exists())
            self.assertTrue((dest_instance_dir / "config" / "options.txt").exists())
            self.assertTrue((dest_instance_dir / "saves" / "World_1" / "level.dat").exists())
            self.assertTrue((dest_assets / "resourcepacks" / "faithfull.zip").exists())

            profiles = user_data.profiles()
            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0]["name"], "Imported Pack")
            self.assertIn(mod1_hash, profiles[0]["enabled_mod_hashes"])
            self.assertIn(rp_hash, profiles[0]["enabled_resourcepack_hashes"])


if __name__ == "__main__":
    unittest.main()
