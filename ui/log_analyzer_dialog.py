"""UI Dialog for viewing and diagnosing Minecraft crash reports and game logs."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from services.app_identity import app_icon_path
from services.localization import translate
from services.log_analyzer import (
    CrashAnalysis,
    analyze_log_content,
    list_available_log_files,
    read_log_text_safely,
)


class CrashLogAnalyzerDialog(QDialog):
    """Dialog displaying automated diagnostics, suspected mods, and raw log contents."""

    def __init__(
        self,
        instance_path: Path,
        instance_name: str = "",
        locale: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.instance_path = instance_path
        self.instance_name = instance_name or instance_path.name
        self.locale = locale
        self.current_analysis: CrashAnalysis | None = None

        title = translate("Анализатор крашей и логов", self.locale)
        self.setWindowTitle(f"{title} — {self.instance_name}")
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.resize(920, 640)

        main_layout = QVBoxLayout(self)

        # File selector row
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel(translate("Файл лога:", self.locale)))

        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self._on_file_selected)
        top_row.addWidget(self.file_combo, 1)

        self.open_editor_btn = QPushButton(translate("Открыть файл", self.locale))
        self.open_editor_btn.clicked.connect(self._open_in_editor)
        top_row.addWidget(self.open_editor_btn)

        self.open_folder_btn = QPushButton(translate("Открыть папку", self.locale))
        self.open_folder_btn.clicked.connect(self._open_in_folder)
        top_row.addWidget(self.open_folder_btn)

        main_layout.addLayout(top_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Diagnostics card widget
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("QFrame { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; }")
        card_layout = QVBoxLayout(card)

        # Diagnostic header
        self.status_title_label = QLabel()
        self.status_title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #b91c1c;")
        self.status_title_label.setWordWrap(True)
        card_layout.addWidget(self.status_title_label)

        # Diagnostic summary
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-size: 13px; color: #1e293b;")
        self.summary_label.setWordWrap(True)
        card_layout.addWidget(self.summary_label)

        # Suspected mods
        self.suspected_mods_label = QLabel()
        self.suspected_mods_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #dc2626;")
        self.suspected_mods_label.setWordWrap(True)
        card_layout.addWidget(self.suspected_mods_label)

        # Recommendation box
        self.recommendation_label = QLabel()
        self.recommendation_label.setStyleSheet(
            "background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px; padding: 6px; font-size: 13px; color: #1e40af;"
        )
        self.recommendation_label.setWordWrap(True)
        card_layout.addWidget(self.recommendation_label)

        # Environment details
        self.env_details_label = QLabel()
        self.env_details_label.setStyleSheet("font-size: 12px; color: #64748b;")
        card_layout.addWidget(self.env_details_label)

        splitter.addWidget(card)

        # Raw log viewer
        log_viewer_widget = QWidget()
        log_layout = QVBoxLayout(log_viewer_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel(translate("Фильтр текста:", self.locale)))
        self.log_search_input = QLineEdit()
        self.log_search_input.setPlaceholderText(translate("Поиск по логу…", self.locale))
        self.log_search_input.setClearButtonEnabled(True)
        self.log_search_input.textChanged.connect(self._highlight_search_text)
        search_row.addWidget(self.log_search_input, 1)
        log_layout.addLayout(search_row)

        self.log_browser = QTextBrowser()
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_browser.setFont(font)
        self.log_browser.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
        log_layout.addWidget(self.log_browser, 1)

        splitter.addWidget(log_viewer_widget)
        splitter.setSizes([180, 400])

        main_layout.addWidget(splitter, 1)

        # Bottom buttons
        bottom_bar = QHBoxLayout()
        self.copy_summary_btn = QPushButton(translate("Копировать сводку", self.locale))
        self.copy_summary_btn.clicked.connect(self._copy_summary)
        bottom_bar.addWidget(self.copy_summary_btn)

        self.copy_log_btn = QPushButton(translate("Копировать весь лог", self.locale))
        self.copy_log_btn.clicked.connect(self._copy_full_log)
        bottom_bar.addWidget(self.copy_log_btn)

        bottom_bar.addStretch(1)

        self.close_btn = QPushButton(translate("Закрыть", self.locale))
        self.close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(self.close_btn)

        main_layout.addLayout(bottom_bar)

        self._populate_files()

    def _populate_files(self) -> None:
        """Scan and populate the file selection dropdown."""
        files = list_available_log_files(self.instance_path)
        self.file_combo.clear()

        if not files:
            self.file_combo.addItem(translate("Логи и краш-репорты не найдены", self.locale))
            self.status_title_label.setText(translate("Логи не найдены", self.locale))
            self.status_title_label.setStyleSheet("color: #64748b; font-size: 15px;")
            self.summary_label.setText(translate("В этом игровом окружении пока нет логов или отчётов о сбоях.", self.locale))
            self.recommendation_label.setVisible(False)
            self.suspected_mods_label.setVisible(False)
            self.env_details_label.setVisible(False)
            self.open_editor_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(False)
            self.copy_summary_btn.setEnabled(False)
            self.copy_log_btn.setEnabled(False)
            return

        for label, path in files:
            self.file_combo.addItem(label, path)

        self._on_file_selected(0)

    def _on_file_selected(self, index: int) -> None:
        """Load and diagnose the selected log file."""
        path = self.file_combo.currentData()
        if not isinstance(path, Path) or not path.is_file():
            return

        content = read_log_text_safely(path)
        if not content:
            self.log_browser.setPlainText("File is empty or could not be read.")
            return

        file_type = "crash_report" if "crash-" in path.name else "log"
        analysis = analyze_log_content(content, path, file_type)
        self.current_analysis = analysis

        # Update Card UI
        self.status_title_label.setText(f"● {analysis.title}")
        if analysis.category in {"out_of_memory", "java_version", "missing_dependency", "mixin_conflict", "duplicate_mod", "driver_opengl", "mod_exception"}:
            self.status_title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #b91c1c;")
        else:
            self.status_title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #047857;")

        self.summary_label.setText(analysis.summary or translate("Критических ошибок не обнаружено.", self.locale))

        if analysis.suspected_mods:
            mods_text = ", ".join(analysis.suspected_mods)
            self.suspected_mods_label.setText(f"{translate('Подозрительные моды:', self.locale)} {mods_text}")
            self.suspected_mods_label.setVisible(True)
        else:
            self.suspected_mods_label.setVisible(False)

        if analysis.recommendation:
            self.recommendation_label.setText(f"💡 {translate('Рекомендуемое действие:', self.locale)}\n{analysis.recommendation}")
            self.recommendation_label.setVisible(True)
        else:
            self.recommendation_label.setVisible(False)

        env_parts = []
        if analysis.minecraft_version:
            env_parts.append(f"Minecraft: {analysis.minecraft_version}")
        if analysis.java_version:
            env_parts.append(f"Java: {analysis.java_version}")
        if analysis.timestamp:
            env_parts.append(f"Time: {analysis.timestamp}")
        self.env_details_label.setText(" | ".join(env_parts))
        self.env_details_label.setVisible(bool(env_parts))

        # Show raw log
        self.log_browser.setPlainText(content)
        self._highlight_keywords()

    def _highlight_keywords(self) -> None:
        """Highlight critical error tokens in the log viewer."""
        cursor = self.log_browser.textCursor()
        format_error = QTextCharFormat()
        format_error.setBackground(QColor("#fee2e2"))
        format_error.setForeground(QColor("#991b1b"))

        format_caused = QTextCharFormat()
        format_caused.setBackground(QColor("#fef3c7"))
        format_caused.setForeground(QColor("#92400e"))

        document = self.log_browser.document()
        for token, fmt in (("ERROR", format_error), ("FATAL", format_error), ("Caused by:", format_caused)):
            cursor = document.find(token)
            count = 0
            while not cursor.isNull() and count < 40:
                cursor.mergeCharFormat(fmt)
                cursor = document.find(token, cursor)
                count += 1

    def _highlight_search_text(self, text: str) -> None:
        """Find and scroll to search text in the log viewer."""
        if not text:
            return
        cursor = self.log_browser.document().find(text)
        if not cursor.isNull():
            self.log_browser.setTextCursor(cursor)

    def _copy_summary(self) -> None:
        """Copy readable diagnosis to clipboard."""
        if not self.current_analysis:
            return
        a = self.current_analysis
        lines = [
            f"MineOrganizer Crash Diagnosis for: {self.instance_name}",
            f"File: {a.file_path.name}",
            f"Status: {a.title}",
            f"Summary: {a.summary}",
        ]
        if a.suspected_mods:
            lines.append(f"Suspected Mods: {', '.join(a.suspected_mods)}")
        if a.recommendation:
            lines.append(f"Recommendation: {a.recommendation}")
        if a.minecraft_version:
            lines.append(f"Minecraft: {a.minecraft_version}")
        if a.java_version:
            lines.append(f"Java: {a.java_version}")

        summary_text = "\n".join(lines)
        QApplication.clipboard().setText(summary_text)
        QMessageBox.information(
            self,
            translate("Скопировано", self.locale),
            translate("Сводка диагностики скопирована в буфер обмена.", self.locale),
        )

    def _copy_full_log(self) -> None:
        """Copy entire raw log content to clipboard."""
        content = self.log_browser.toPlainText()
        if content:
            QApplication.clipboard().setText(content)
            QMessageBox.information(
                self,
                translate("Скопировано", self.locale),
                translate("Полный текст лога скопирован в буфер обмена.", self.locale),
            )

    def _open_in_editor(self) -> None:
        """Open the active log file in system default text editor."""
        path = self.file_combo.currentData()
        if isinstance(path, Path) and path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_in_folder(self) -> None:
        """Open the folder containing the log file in Explorer."""
        path = self.file_combo.currentData()
        if isinstance(path, Path) and path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
