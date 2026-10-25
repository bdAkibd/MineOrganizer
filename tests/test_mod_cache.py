"""Unit tests for ModCache and parallel scanning."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from models.mod_file import ModFile
from services.mod_cache import ModCache, deserialize_metadata, serialize_metadata
from services.mod_metadata import ModMetadata


class ModCacheTests(unittest.TestCase):
    def test_serialize_deserialize_metadata(self):
        meta = ModMetadata(
            name="Test Mod",
            mod_id="testmod",
            version="1.2.3",
            minecraft_ranges=["1.20.1"],
            loader_ids=["Fabric"],
            dependencies=["fabric-api"],
            required_mod_ids=["fabric-api"],
            source="fabric.mod.json",
            kind="Mod",
            icon_bytes=b"\x89PNG\r\n\x1a\nfakeicon",
        )
        data = serialize_metadata(meta)
        restored = deserialize_metadata(data)

        self.assertEqual(restored.name, meta.name)
        self.assertEqual(restored.mod_id, meta.mod_id)
        self.assertEqual(restored.version, meta.version)
        self.assertEqual(restored.minecraft_ranges, meta.minecraft_ranges)
        self.assertEqual(restored.loader_ids, meta.loader_ids)
        self.assertEqual(restored.icon_bytes, meta.icon_bytes)

    def test_mod_cache_put_get_save_reload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cache_file = temp_path / "cache.json"
            mod_jar = temp_path / "sample.jar"
            mod_jar.write_bytes(b"dummy jar content")

            cache = ModCache(cache_file)
            self.assertIsNone(cache.get(mod_jar))

            meta = ModMetadata(name="Sample Mod", version="1.0")
            cache.put(mod_jar, "sha256_dummy", "sha1_dummy", meta)
            cache.save()

            cached = cache.get(mod_jar)
            self.assertIsNotNone(cached)
            self.assertEqual(cached[0], "sha256_dummy")
            self.assertEqual(cached[1], "sha1_dummy")
            self.assertEqual(cached[2].name, "Sample Mod")

            # Reload into new instance
            cache2 = ModCache(cache_file)
            cached2 = cache2.get(mod_jar)
            self.assertIsNotNone(cached2)
            self.assertEqual(cached2[0], "sha256_dummy")

            # If file mtime or size changes, cache misses
            mod_jar.write_bytes(b"modified jar content with different size")
            self.assertIsNone(cache2.get(mod_jar))

    def test_scan_mods_parallel(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cache_file = temp_path / "cache.json"
            library_dir = temp_path / "mods"
            library_dir.mkdir()

            # Create 3 dummy jar files
            for i in range(3):
                jar = library_dir / f"mod_{i}.jar"
                with zipfile.ZipFile(jar, "w") as arc:
                    arc.writestr("fabric.mod.json", f'{{"id": "mod_{i}", "name": "Mod {i}", "version": "1.0"}}')

            cache = ModCache(cache_file)
            results = cache.scan_mods_parallel(library_dir, max_workers=2)
            self.assertEqual(len(results), 3)

            # Check that files were placed in cache
            self.assertTrue(cache_file.exists())
            cached = cache.get(library_dir / "mod_0.jar")
            self.assertIsNotNone(cached)
            self.assertEqual(cached[2].mod_id, "mod_0")


if __name__ == "__main__":
    unittest.main()
