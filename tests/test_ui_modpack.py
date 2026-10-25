"""Unit tests for UI export and import modpack handling in MainWindow."""

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication

from models.instance import PrismInstance
from services.mod_library import file_sha256
from services.modpack_service import export_profile_to_modpack
from services.user_data import UserDataStore
from ui.main_window import ExportModpackDialog, MainWindow, QMessageBox


class UiModpackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ui_export_and_import_modpack(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            user_data_file = temp_path / "user_data.json"
            library_dir = temp_path / "mods"
            library_dir.mkdir()
            export_archive = temp_path / "my_exported_pack.morgpack"

            # Create test mod
            test_jar = library_dir / "mod_a.jar"
            with zipfile.ZipFile(test_jar, "w") as arc:
                arc.writestr("fabric.mod.json", '{"id": "mod_a", "name": "Mod A", "version": "1.0"}')
            mod_hash = file_sha256(test_jar)

            user_data = UserDataStore(user_data_file)
            user_data.add_profile(
                name="Test Pack",
                instance={
                    "instance_id": "inst_1",
                    "instance_path": str(temp_path),
                    "minecraft_version": "1.20.1",
                    "loader": "Fabric",
                    "loader_version": "0.15.11",
                },
                mod_hashes=[mod_hash],
            )

            with patch("services.mod_library.default_library_dir", return_value=library_dir), \
                 patch("services.user_data.default_user_data_path", return_value=user_data_file), \
                 patch("ui.main_window.default_library_dir", return_value=library_dir), \
                 patch("ui.main_window.find_default_prism_data_dir", return_value=None), \
                 patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(str(export_archive), "")), \
                 patch("ui.main_window.QFileDialog.getOpenFileName", return_value=(str(export_archive), "")), \
                 patch("ui.main_window.QInputDialog.getText", return_value=("Imported Modpack", True)), \
                 patch.object(ExportModpackDialog, "exec", return_value=ExportModpackDialog.DialogCode.Accepted), \
                 patch("ui.main_window.QMessageBox.information"), \
                 patch("ui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.No):

                window = MainWindow()
                window.user_data = user_data
                window.library_dir = library_dir
                window.refresh_library()
                window.refresh_profiles()

                # Test Export
                window.export_selected_profile()
                self.assertTrue(export_archive.exists())

                # Test Import
                initial_profile_count = len(window.user_data.profiles())
                window.import_modpack()
                self.assertEqual(len(window.user_data.profiles()), initial_profile_count + 1)

                imported_profile = window.user_data.profiles()[-1]
                self.assertEqual(imported_profile["name"], "Imported Modpack")
                self.assertIn(mod_hash, imported_profile["enabled_mod_hashes"])

                window.close()


if __name__ == "__main__":
    unittest.main()
