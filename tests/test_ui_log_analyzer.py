"""Unit tests for CrashLogAnalyzerDialog and its integration in MainWindow."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication

from models.instance import PrismInstance
from ui.log_analyzer_dialog import CrashLogAnalyzerDialog
from ui.main_window import MainWindow


class UiLogAnalyzerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_empty_instance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            instance_path = Path(temp_dir)
            dialog = CrashLogAnalyzerDialog(instance_path=instance_path, locale="ru")
            self.assertEqual(dialog.file_combo.count(), 1)
            self.assertFalse(dialog.open_editor_btn.isEnabled())
            self.assertFalse(dialog.copy_summary_btn.isEnabled())
            dialog.close()

    def test_dialog_diagnoses_crash_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            instance_path = Path(temp_dir)
            crash_dir = instance_path / "crash-reports"
            crash_dir.mkdir(parents=True)
            crash_file = crash_dir / "crash-2026-10-25_12.00.00-client.txt"
            crash_file.write_text(
                "---- Minecraft Crash Report ----\n"
                "Time: 2026-10-25 12:00:00\n"
                "java.lang.OutOfMemoryError: Java heap space\n",
                encoding="utf-8",
            )

            with patch("ui.log_analyzer_dialog.QMessageBox.information"):
                dialog = CrashLogAnalyzerDialog(instance_path=instance_path, locale="en")
                self.assertEqual(dialog.file_combo.count(), 1)
                self.assertTrue(dialog.open_editor_btn.isEnabled())
                self.assertTrue(dialog.copy_summary_btn.isEnabled())
                self.assertIn("Out of Memory", dialog.status_title_label.text())

                # Test copying summary
                dialog._copy_summary()
                clipboard_text = QApplication.clipboard().text()
                self.assertIn("MineOrganizer Crash Diagnosis", clipboard_text)
                self.assertIn("Out of Memory", clipboard_text)

                # Test copying full log
                dialog._copy_full_log()
                clipboard_log = QApplication.clipboard().text()
                self.assertIn("java.lang.OutOfMemoryError", clipboard_log)

                dialog.close()

    def test_main_window_analyze_logs_button_launches_dialog(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            user_data_file = temp_path / "user_data.json"
            library_dir = temp_path / "mods"
            library_dir.mkdir()
            instance_dir = temp_path / "instances" / "test_inst"
            instance_dir.mkdir(parents=True)

            mock_inst = PrismInstance(
                instance_id="test_inst",
                name="Test Instance",
                path=instance_dir,
                minecraft_version="1.20.1",
                loader="Fabric",
                loader_version="0.15.11",
                status="Ready",
            )

            with patch("services.mod_library.default_library_dir", return_value=library_dir), \
                 patch("services.user_data.default_user_data_path", return_value=user_data_file), \
                 patch("ui.main_window.default_library_dir", return_value=library_dir), \
                 patch("ui.main_window.find_default_prism_data_dir", return_value=None), \
                 patch.object(CrashLogAnalyzerDialog, "exec") as mock_exec:
                window = MainWindow()
                window.instances = [mock_inst]
                window.table.setRowCount(1)
                window.table.setCurrentCell(0, 0)

                window.analyze_selected_instance_logs(mock_inst)
                mock_exec.assert_called_once()
                window.close()


if __name__ == "__main__":
    unittest.main()
