"""Tests for mod metadata reading and compatibility checks."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from services.mod_metadata import (
    compatibility_for_profile,
    minecraft_version_choices,
    minecraft_version_display,
    minecraft_version_entries,
    read_mod_metadata,
    version_matches,
)


class ModMetadataTests(unittest.TestCase):
    def setUp(self):
        self.modrinth_fallback = patch("services.mod_metadata._modrinth_metadata", return_value={})
        self.modrinth_fallback.start()

    def tearDown(self):
        self.modrinth_fallback.stop()

    def test_reads_bukkit_plugin_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "example-plugin.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("plugin.yml", "name: ExamplePlugin\nversion: 1.2.3\nmain: example.plugin.Main\napi-version: '1.20'\n")
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.kind, "Plugin")
            self.assertEqual(metadata.name, "ExamplePlugin")
            self.assertEqual(metadata.version, "1.2.3")
            self.assertEqual(metadata.loader_ids, ["Bukkit/Spigot/Paper"])
            self.assertEqual(compatibility_for_profile(metadata, "1.20.1", "fabric")[0], "Server plugin")

    def test_reads_fabric_metadata_and_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "example.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("fabric.mod.json", json.dumps({
                    "id": "example", "name": "Example Mod", "version": "1.2.3",
                    "depends": {"minecraft": "1.20.1", "fabricloader": ">=0.14.0"},
                }))
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.name, "Example Mod")
            self.assertEqual(metadata.mod_id, "example")
            self.assertEqual(metadata.version, "1.2.3")
            status, _ = compatibility_for_profile(metadata, "1.20.1", "fabric")
            self.assertEqual(status, "Likely compatible")
            status, _ = compatibility_for_profile(metadata, "1.19.4", "fabric")
            self.assertEqual(status, "Incompatible")

    def test_reads_fabric_icon(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "example-icon.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("fabric.mod.json", json.dumps({
                    "id": "iconmod", "name": "Icon Mod", "version": "1.0",
                    "icon": "assets/iconmod/icon.png",
                }))
                archive.writestr("assets/iconmod/icon.png", b"fake_png_data")
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.icon_bytes, b"fake_png_data")

    def test_reads_quilt_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "quilt.jar"
            data = {
                "quilt_loader": {
                    "id": "quilt_demo", "version": "1.0", "metadata": {"name": "Quilt Demo"},
                    "depends": [
                        {"id": "quilt_loader", "versions": ">=0.20"},
                        {"id": "minecraft", "versions": "1.20.1"},
                        {"id": "base_mod", "versions": "*"},
                    ],
                }
            }
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("quilt.mod.json", json.dumps(data))
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.name, "Quilt Demo")
            self.assertEqual(metadata.mod_id, "quilt_demo")
            self.assertIn("1.20.1", metadata.minecraft_ranges)
            self.assertIn("base_mod", metadata.required_mod_ids)
            self.assertEqual(compatibility_for_profile(metadata, "1.20.1", "quilt", {"quilt_demo", "base_mod"})[0], "Likely compatible")

    def test_reads_forge_toml(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "forge.jar"
            toml = '''modLoader="javafml"\nloaderVersion="[40,)"\n[[mods]]\nmodId="demo"\ndisplayName="Demo Mod"\nversion="2.0"\n[[dependencies.demo]]\nmodId="minecraft"\nmandatory=true\nversionRange="[1.18,1.19)"\nordering="NONE"\nside="BOTH"\n'''
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("META-INF/mods.toml", toml)
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.name, "Demo Mod")
            self.assertEqual(metadata.mod_id, "demo")
            self.assertIn("[1.18,1.19)", metadata.minecraft_ranges)
            self.assertEqual(compatibility_for_profile(metadata, "1.18.2", "forge")[0], "Likely compatible")
            self.assertEqual(compatibility_for_profile(metadata, "1.19.2", "forge")[0], "Incompatible")

    def test_placeholder_version_uses_jar_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "clientcrafting-1.20.1-2.1.jar"
            toml = '''[[mods]]\nmodId="clientcrafting"\ndisplayName="Client Crafting"\nversion="${file.jarVersion}"\n[[dependencies.clientcrafting]]\nmodId="minecraft"\nmandatory=true\nversionRange="[1.20,1.30)"\n'''
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("META-INF/mods.toml", toml)
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.version, "2.1")
            self.assertEqual(minecraft_version_choices(metadata.minecraft_ranges), ["1.20"])

    def test_missing_minecraft_range_uses_embeddium_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "embeddium-0.3.31+mc1.20.1.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("fabric.mod.json", json.dumps({
                    "id": "embeddium", "name": "Embeddium", "version": "0.3.31",
                }))
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.minecraft_ranges, ["1.20.1"])

    def test_missing_minecraft_range_uses_forge_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "lucky-block-forge-1.20.1-13.0.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("META-INF/mods.toml", '[[mods]]\nmodId="luckyblock"\ndisplayName="Lucky Block"\nversion="13.0"\n')
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.minecraft_ranges, ["1.20.1"])

    def test_filename_version_patterns_use_minecraft_version(self):
        from services.mod_metadata import _minecraft_version_from_filename

        self.assertEqual(_minecraft_version_from_filename(Path("dynamiclights-1.20.1.2.jar")), "1.20.1")
        self.assertEqual(_minecraft_version_from_filename(Path("immersive_armors-1.7.2+1.20.1-forge.jar")), "1.20.1")
        self.assertEqual(_minecraft_version_from_filename(Path("lucky-block-forge-1.20.1-13.0.jar")), "1.20.1")

    def test_unresolved_build_placeholders_are_replaced_from_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "example-mod-1.20.1-2.4.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(
                    "fabric.mod.json",
                    json.dumps({"id": "example", "name": "Example", "version": "@VERSION@"}),
                )
            metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.version, "2.4")

    def test_modrinth_is_used_when_local_metadata_and_filename_are_insufficient(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "example-mod.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(
                    "fabric.mod.json",
                    json.dumps({"id": "example", "name": "Example", "version": "${version}"}),
                )
            with patch(
                "services.mod_metadata._modrinth_metadata",
                return_value={"version": "3.1.0", "minecraft_ranges": ["1.21.1"], "loader_ids": ["fabric"]},
            ):
                metadata = read_mod_metadata(jar)
            self.assertEqual(metadata.version, "3.1.0")
            self.assertEqual(metadata.minecraft_ranges, ["1.21.1"])

    def test_modrinth_precedes_filename_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "smooth-particles-1.19.2.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(
                    "fabric.mod.json",
                    json.dumps({"id": "smooth_particles", "name": "Smooth Particles", "version": "${version}"}),
                )
            with patch(
                "services.mod_metadata._modrinth_metadata",
                return_value={"version": "1.0.0", "minecraft_ranges": ["1.19.4"], "loader_ids": ["fabric"]},
            ) as lookup:
                metadata = read_mod_metadata(jar)
            lookup.assert_called_once_with(jar)
            self.assertEqual(metadata.version, "1.0.0")
            self.assertEqual(metadata.minecraft_ranges, ["1.19.4"])

    def test_required_dependency_is_reported(self):
        from services.mod_metadata import ModMetadata
        metadata = ModMetadata(
            name="Addon", mod_id="addon", version="1.0", minecraft_ranges=["1.20.1"],
            loader_ids=["fabric"], required_mod_ids=["base_mod"], source="Fabric metadata",
        )
        status, reason = compatibility_for_profile(metadata, "1.20.1", "fabric", {"addon"})
        self.assertEqual(status, "Missing dependencies")
        self.assertIn("base_mod", reason)
        self.assertEqual(compatibility_for_profile(metadata, "1.20.1", "fabric", {"addon", "base_mod"})[0], "Likely compatible")

    def test_version_ranges(self):
        self.assertEqual(minecraft_version_entries(["1.20, 1.21", "[1.18,1.19)"]), ["1.20", "1.21", "[1.18,1.19)"])
        self.assertEqual(
            minecraft_version_choices(["1.13 # legacy", ">1.19.0 <=1.19.2", "[1.20, 1.21]", "1.20.1,1.20.2"]),
            ["1.13", "1.19.2", "1.20", "1.21", "1.20.1", "1.20.2"],
        )
        self.assertEqual(minecraft_version_choices(["[1.20,1.30)"]), ["1.20"])
        self.assertTrue(version_matches("1.21", "1.20, 1.21"))
        self.assertTrue(version_matches("1.20.1", "[1.20,1.21)"))
        self.assertFalse(version_matches("1.21", "[1.20,1.21)"))
        self.assertTrue(version_matches("1.20.1", ">=1.20"))
        self.assertTrue(version_matches("1.20.1", "1.19 || 1.20.1"))
        self.assertTrue(version_matches("1.19.1", ">1.19.0 <=1.19.2"))
        self.assertFalse(version_matches("1.19.2", ">1.19.0 <1.19.2"))

    def test_version_display_collapses_long_lists(self):
        self.assertEqual(
            minecraft_version_display(["1.7.2", "1.8.9", "1.12.2"]),
            "1.7.2–1.12.2",
        )
        self.assertEqual(minecraft_version_display(["1.20", "1.20.1"]), "1.20, 1.20.1")

    def test_unknown_metadata_is_not_assumed_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "empty.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("readme.txt", "not a mod")
            metadata = read_mod_metadata(jar)
            self.assertEqual(compatibility_for_profile(metadata, "1.20.1", "fabric")[0], "Unknown")


if __name__ == "__main__":
    unittest.main()
