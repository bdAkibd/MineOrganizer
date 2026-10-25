"""Tests for Mod Library live filtering and Drag & Drop handling."""

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from services.user_data import UserDataStore
from ui.main_window import MainWindow


class UiLibraryFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_filter_library_table_matches_and_hides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            user_data_file = temp_path / "user_data.json"
            library_dir = temp_path / "mods"
            library_dir.mkdir()

            # Create two dummy mod jars
            mod1 = library_dir / "sodium-1.20.1.jar"
            with zipfile.ZipFile(mod1, "w") as arc:
                arc.writestr("fabric.mod.json", '{"id": "sodium", "name": "Sodium", "version": "0.5.8", "depends": {"minecraft": "1.20.1"}}')
            mod2 = library_dir / "iris-1.20.4.jar"
            with zipfile.ZipFile(mod2, "w") as arc:
                arc.writestr("fabric.mod.json", '{"id": "iris", "name": "Iris Shaders", "version": "1.7.0", "depends": {"minecraft": "1.20.4"}}')

            with patch("services.mod_library.default_library_dir", return_value=library_dir), \
                 patch("services.user_data.default_user_data_path", return_value=user_data_file), \
                 patch("ui.main_window.default_library_dir", return_value=library_dir), \
                 patch("ui.main_window.find_default_prism_data_dir", return_value=None):
                window = MainWindow()
                window.library_dir = library_dir
                window.refresh_library()

                self.assertEqual(window.library_table.rowCount(), 2)

                # 1. Search for "sodium"
                window.mod_search_input.setText("sodium")
                # sodium row should be visible, iris row hidden
                row_sodium = 0 if "Sodium" in window.library_table.item(0, 0).text() else 1
                row_iris = 1 - row_sodium
                self.assertFalse(window.library_table.isRowHidden(row_sodium))
                self.assertTrue(window.library_table.isRowHidden(row_iris))

                # 2. Clear search, both visible
                window.mod_search_input.setText("")
                self.assertFalse(window.library_table.isRowHidden(0))
                self.assertFalse(window.library_table.isRowHidden(1))

                # 3. Filter by version "1.20.4"
                ver_idx = window.mod_version_filter.findText("1.20.4")
                if ver_idx >= 0:
                    window.mod_version_filter.setCurrentIndex(ver_idx)
                    self.assertTrue(window.library_table.isRowHidden(row_sodium))
                    self.assertFalse(window.library_table.isRowHidden(row_iris))

                window.close()

    def test_handle_dropped_jar_files_imports_to_library(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            user_data_file = temp_path / "user_data.json"
            library_dir = temp_path / "mods"
            library_dir.mkdir()

            drop_jar = temp_path / "new_mod.jar"
            with zipfile.ZipFile(drop_jar, "w") as arc:
                arc.writestr("fabric.mod.json", '{"id": "newmod", "name": "New Mod", "version": "1.0"}')

            with patch("services.mod_library.default_library_dir", return_value=library_dir), \
                 patch("services.user_data.default_user_data_path", return_value=user_data_file), \
                 patch("ui.main_window.default_library_dir", return_value=library_dir), \
                 patch("ui.main_window.find_default_prism_data_dir", return_value=None), \
                 patch("ui.main_window.QMessageBox.information"):
                window = MainWindow()
                window.library_dir = library_dir
                window.refresh_library()

                initial_count = len(window.mods)
                window._handle_dropped_urls([QUrl.fromLocalFile(str(drop_jar))])
                self.assertEqual(len(window.mods), initial_count + 1)
                self.assertTrue((library_dir / "new_mod.jar").exists())

                window.close()

    def test_modrinth_search_dialog_initialization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            from ui.modrinth_dialogs import ModrinthSearchDialog
            library_dir = Path(temp_dir)
            dialog = ModrinthSearchDialog(
                library_dir=library_dir,
                locale="ru",
                default_loader="Fabric",
                default_version="1.20.1",
            )
            self.assertEqual(dialog.loader_filter.currentText(), "Fabric")
            self.assertEqual(dialog.version_filter.currentText(), "1.20.1")
            dialog.close()

    def test_mod_updates_dialog_initialization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            from ui.modrinth_dialogs import ModUpdatesDialog
            library_dir = Path(temp_dir)
            mod1 = library_dir / "test.jar"
            with zipfile.ZipFile(mod1, "w") as arc:
                arc.writestr("fabric.mod.json", '{"id": "test", "name": "Test", "version": "1.0"}')
            from models.mod_file import ModFile
            mod_file = ModFile("test.jar", mod1, mod1.stat().st_size, "fakehash")
            with patch("services.mod_library.file_sha1", return_value="fakesha1"), \
                 patch("services.modrinth_service.check_mod_updates", return_value={}):
                dialog = ModUpdatesDialog(
                    mods=[mod_file],
                    library_dir=library_dir,
                    locale="en",
                )
                dialog.close()

    def test_rapid_filter_change_does_not_crash(self):
        """Simulate user typing a mod name, changing loader, then immediately changing version."""
        with tempfile.TemporaryDirectory() as temp_dir:
            from ui.modrinth_dialogs import ModrinthSearchDialog
            library_dir = Path(temp_dir)
            with patch("services.modrinth_service.search_modrinth", return_value=[]):
                dialog = ModrinthSearchDialog(
                    library_dir=library_dir,
                    locale="ru",
                )
                dialog.query_input.setText("sodium")
                # Rapid filter changes that previously caused QThread destruction crash
                dialog.loader_filter.setCurrentIndex(1)  # Fabric
                dialog.loader_filter.setCurrentIndex(2)  # Forge
                dialog.version_filter.setCurrentIndex(1) # 1.21.4
                dialog.version_filter.setCurrentIndex(2) # 1.21.3
                dialog.close()


if __name__ == "__main__":
    unittest.main()
