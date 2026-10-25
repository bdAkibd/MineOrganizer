"""Tests for the Minecraft save library."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from services.save_library import import_save, install_save, scan_saves


class SaveLibraryTests(unittest.TestCase):
    def test_import_and_install_save(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source" / "My World"
            (source / "region").mkdir(parents=True)
            (source / "level.dat").write_text("world", encoding="utf-8")
            library = root / "library"

            success, _ = import_save(source, library)
            self.assertTrue(success)
            self.assertEqual([entry.name for entry in scan_saves(library)], ["My World"])

            instance = root / "instance"
            success, _ = install_save(library / "My World", instance)
            self.assertTrue(success)
            self.assertEqual((instance / "saves" / "My World" / "level.dat").read_text(encoding="utf-8"), "world")

    def test_existing_save_is_not_overwritten_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "library" / "World"
            source.mkdir(parents=True)
            (source / "level.dat").write_text("new", encoding="utf-8")
            instance = root / "instance" / "saves" / "World"
            instance.mkdir(parents=True)
            (instance / "level.dat").write_text("old", encoding="utf-8")

            success, _ = install_save(source, root / "instance")
            self.assertFalse(success)
            self.assertEqual((instance / "level.dat").read_text(encoding="utf-8"), "old")

    def test_import_save_from_zip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "AdventureWorld.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("AdventureWorld/level.dat", "world_data")
                archive.writestr("AdventureWorld/data/test.txt", "data")
            library = root / "library"

            success, msg = import_save(archive_path, library)
            self.assertTrue(success)
            self.assertEqual([entry.name for entry in scan_saves(library)], ["AdventureWorld"])
            self.assertEqual((library / "AdventureWorld" / "level.dat").read_text(encoding="utf-8"), "world_data")
