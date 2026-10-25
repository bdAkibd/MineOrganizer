"""MineOrganizer main window."""

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QDesktopServices,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog as _QtFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog as _QtInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox as _QtMessageBox,
    QMenu,
    QSplitter,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


LIGHT_THEME = """
QMainWindow, QDialog, QWidget { background: #f5f7fb; color: #202938; }
QWidget { color: #202938; }
QLabel { color: #354258; }
QMenuBar, QMenu { background: #ffffff; color: #202938; }
QMenuBar::item { padding: 6px 10px; }
QMenuBar::item:selected, QMenu::item:selected { background: #e8eefb; }
QLabel#appHeading { color: #172033; font-size: 22px; font-weight: 700; }
QLabel#appSubtitle { color: #5e6b7e; font-size: 13px; }
QTabWidget::pane { border: 1px solid #d8deea; border-radius: 6px; background: #ffffff; }
QTabBar::tab { background: #e9edf5; color: #536176; padding: 9px 14px; margin-right: 2px; }
QTabBar::tab:selected { background: #ffffff; color: #1d4ed8; font-weight: 600; }
QPushButton { background: #ffffff; color: #202938; border: 1px solid #c9d2e3; border-radius: 5px; padding: 7px 12px; }
QPushButton:hover { background: #eef4ff; border-color: #86a9e8; }
QPushButton:pressed { background: #dce9ff; }
QComboBox, QLineEdit { background: #ffffff; color: #202938; border: 1px solid #c9d2e3; border-radius: 5px; padding: 6px 8px; }
QComboBox QAbstractItemView, QListWidget { background: #ffffff; color: #202938; selection-background-color: #dbeafe; selection-color: #172033; }
QTableWidget { background: #ffffff; color: #202938; alternate-background-color: #f4f7fb; gridline-color: #dfe5ef; border: 1px solid #d8deea; border-radius: 5px; }
QTableWidget::item { color: #202938; padding: 5px; }
QTableWidget::item:selected { background: #dbeafe; color: #172033; }
QHeaderView::section { background: #edf1f7; color: #39465b; border: 0; border-right: 1px solid #d8deea; border-bottom: 1px solid #cdd6e5; padding: 7px 8px; font-weight: 600; }
QHeaderView::section:vertical { background: #edf1f7; color: #39465b; }
QTableCornerButton::section { background: #edf1f7; border: 0; border-right: 1px solid #d8deea; border-bottom: 1px solid #cdd6e5; }
QSplitter::handle { background: #cbd5e1; }
QSplitter::handle:hover { background: #6d9ee8; }
QDialogButtonBox QPushButton { min-width: 80px; }
QStatusBar { color: #536176; }
"""


DARK_THEME = """
QMainWindow, QDialog, QWidget { background: #20252f; color: #edf2f7; }
QWidget { color: #edf2f7; }
QLabel { color: #cbd5e1; }
QMenuBar, QMenu { background: #252b35; color: #edf2f7; }
QMenuBar::item { padding: 6px 10px; }
QMenuBar::item:selected, QMenu::item:selected { background: #3a4658; }
QLabel#appHeading { color: #f8fafc; font-size: 22px; font-weight: 700; }
QLabel#appSubtitle { color: #aebdce; font-size: 13px; }
QTabWidget::pane { border: 1px solid #465365; border-radius: 6px; background: #252b35; }
QTabBar::tab { background: #303846; color: #c3cedc; padding: 9px 14px; margin-right: 2px; }
QTabBar::tab:selected { background: #252b35; color: #8bb8ff; font-weight: 600; }
QPushButton { background: #2a313c; color: #edf2f7; border: 1px solid #536276; border-radius: 5px; padding: 7px 12px; }
QPushButton:hover { background: #35445a; border-color: #78a9ed; }
QPushButton:pressed { background: #405a7d; }
QComboBox, QLineEdit { background: #2a313c; color: #edf2f7; border: 1px solid #536276; border-radius: 5px; padding: 6px 8px; }
QComboBox QAbstractItemView, QListWidget { background: #2a313c; color: #edf2f7; selection-background-color: #3b6ea8; selection-color: #ffffff; }
QTableWidget { background: #252b35; color: #edf2f7; alternate-background-color: #2d3542; gridline-color: #465365; border: 1px solid #465365; border-radius: 5px; }
QTableWidget::item { color: #edf2f7; padding: 5px; }
QTableWidget::item:selected { background: #315f93; color: #ffffff; }
QHeaderView::section { background: #303846; color: #edf2f7; border: 0; border-right: 1px solid #465365; border-bottom: 1px solid #536276; padding: 7px 8px; font-weight: 600; }
QHeaderView::section:vertical { background: #303846; color: #edf2f7; }
QTableCornerButton::section { background: #303846; border: 0; border-right: 1px solid #465365; border-bottom: 1px solid #536276; }
QSplitter::handle { background: #536276; }
QSplitter::handle:hover { background: #78a9ed; }
QDialogButtonBox QPushButton { min-width: 80px; }
QStatusBar { color: #aebdce; }
"""

from launchers.prism.discovery import find_default_prism_data_dir, is_prism_data_dir
from launchers.prism.instance_parser import scan_instances
from launchers.game_directory.scanner import (
    default_game_directory_candidates, is_game_directory, discover_game_environments, launcher_for_game_directory,
)
from models.instance import PrismInstance
from models.mod_file import ModFile
from services.mod_library import default_library_dir, file_sha1, import_mods, scan_mods
from services.mod_metadata import (
    read_mod_metadata,
    compatibility_for_profile,
    minecraft_version_entries,
    minecraft_version_choices,
    minecraft_version_display,
    version_matches,
)
from services.mod_conflicts import check_mod_conflicts
from services.asset_library import default_asset_library_dir, import_assets, scan_assets
from services.asset_virtualization import preview_assets, apply_assets, rollback_assets
from services.config_backups import (
    create_config_backup,
    delete_config_backup,
    delete_config_directory,
    find_config_dir,
    list_config_backups,
    restore_config_backup,
)
from services.save_library import default_save_library_dir, find_saves_dir, import_save, install_save, scan_saves
from services.environment_scan import scan_environment_mods
from services.user_data import UserDataStore
from services.app_config import AppConfig
from services.app_identity import APP_NAME, APP_SHORT_NAME, app_icon_path
from services.localization import SUPPORTED_LOCALES, locale_name, translate, translate_many
from services.manual import load_manual_html
from services.virtualization import (
    VirtualizationPlan, apply_profile, preview_profile, rollback_last,
)
from services.log_analyzer import analyze_instance_logs, list_available_log_files
from services.mod_cache import get_mod_cache
from services.modpack_service import (
    export_profile_to_modpack,
    import_modpack_archive,
    inspect_modpack,
)
from ui.modrinth_dialogs import ModrinthSearchDialog, ModUpdatesDialog
from ui.log_analyzer_dialog import CrashLogAnalyzerDialog


def _dialog_locale(parent) -> str:
    """Return the locale of the dialog owner window."""
    return getattr(parent, "locale", "en")


class QMessageBox:
    """Localized facade for standard Qt message boxes."""

    StandardButton = _QtMessageBox.StandardButton

    @staticmethod
    def information(parent, title: str, text: str, *args):
        return _QtMessageBox.information(parent, translate(title, _dialog_locale(parent)), translate(text, _dialog_locale(parent)), *args)

    @staticmethod
    def warning(parent, title: str, text: str, *args):
        return _QtMessageBox.warning(parent, translate(title, _dialog_locale(parent)), translate(text, _dialog_locale(parent)), *args)

    @staticmethod
    def critical(parent, title: str, text: str, *args):
        return _QtMessageBox.critical(parent, translate(title, _dialog_locale(parent)), translate(text, _dialog_locale(parent)), *args)

    @staticmethod
    def question(parent, title: str, text: str, *args):
        return _QtMessageBox.question(parent, translate(title, _dialog_locale(parent)), translate(text, _dialog_locale(parent)), *args)

    @staticmethod
    def about(parent, title: str, text: str):
        return _QtMessageBox.about(parent, translate(title, _dialog_locale(parent)), translate(text, _dialog_locale(parent)))


class QInputDialog:
    """Localized facade for Qt text dialogs."""

    @staticmethod
    def getText(parent, title: str, label: str, *args, **kwargs):
        locale = _dialog_locale(parent)
        return _QtInputDialog.getText(parent, translate(title, locale), translate(label, locale), *args, **kwargs)

    @staticmethod
    def getItem(parent, title: str, label: str, items, *args, **kwargs):
        locale = _dialog_locale(parent)
        return _QtInputDialog.getItem(parent, translate(title, locale), translate(label, locale), items, *args, **kwargs)


class QFileDialog:
    """Localized facade for Qt file and folder dialogs."""

    @staticmethod
    def getExistingDirectory(parent, title: str, *args, **kwargs):
        return _QtFileDialog.getExistingDirectory(parent, translate(title, _dialog_locale(parent)), *args, **kwargs)

    @staticmethod
    def getOpenFileNames(parent, title: str, *args, **kwargs):
        locale = _dialog_locale(parent)
        translated_args = list(args)
        if translated_args and isinstance(translated_args[-1], str):
            translated_args[-1] = translate(translated_args[-1], locale)
        return _QtFileDialog.getOpenFileNames(parent, translate(title, locale), *translated_args, **kwargs)

    @staticmethod
    def getOpenFileName(parent, title: str, *args, **kwargs):
        locale = _dialog_locale(parent)
        translated_args = list(args)
        if translated_args and isinstance(translated_args[-1], str):
            translated_args[-1] = translate(translated_args[-1], locale)
        return _QtFileDialog.getOpenFileName(parent, translate(title, locale), *translated_args, **kwargs)

    @staticmethod
    def getSaveFileName(parent, title: str, *args, **kwargs):
        locale = _dialog_locale(parent)
        translated_args = list(args)
        if translated_args and isinstance(translated_args[-1], str):
            translated_args[-1] = translate(translated_args[-1], locale)
        return _QtFileDialog.getSaveFileName(parent, translate(title, locale), *translated_args, **kwargs)


class NaturalSortItem(QTableWidgetItem):
    """Table item sorted by numeric parts of strings."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole)
        if left is not None and right is not None:
            return left < right
        return self.text().casefold() < other.text().casefold()


def _sort_key(value: str) -> tuple[tuple[int, object], ...]:
    """Split a string into numeric and text parts for version sorting."""
    import re

    parts = re.findall(r"\d+|\D+", value.casefold())
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)


class ModSelectionDialog(QDialog):
    """Select mods with Minecraft version and loader filters."""

    def __init__(self, mods: list[ModFile], selected_hashes: set[str] | None = None,
                 locale: str = "en", version_overrides: dict[str, list[str]] | None = None) -> None:
        """Create a checked mod list with compatibility filters."""
        super().__init__()
        self.locale = locale
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.setWindowTitle(translate("Profile mods", self.locale))
        self.resize(620, 520)
        self.list_widget = QListWidget()
        self.version_filter = QComboBox()
        self.loader_filter = QComboBox()
        self.version_filter.addItem(translate("All versions", self.locale))
        self.loader_filter.addItem(translate("All loaders", self.locale))
        selected = selected_hashes or set()
        version_overrides = version_overrides or {}
        self.mod_metadata: dict[str, tuple[list[str], list[str]]] = {}
        for mod in mods:
            metadata = read_mod_metadata(mod.path)
            override = version_overrides.get(mod.sha256, [])
            if override:
                metadata.minecraft_ranges = list(override)
            versions = minecraft_version_choices(metadata.minecraft_ranges) or [translate("Not specified", self.locale)]
            loaders = metadata.loader_ids or [translate("Not specified", self.locale)]
            self.mod_metadata[mod.sha256] = (metadata.minecraft_ranges, loaders)
            kind_prefix = f"[{translate(metadata.kind, self.locale)}] " if metadata.kind != "Mod" else ""
            item = QListWidgetItem(f"{kind_prefix}{metadata.name or mod.name}  ({mod.size:,} bytes)".replace(",", " "))
            item.setData(Qt.ItemDataRole.UserRole, mod.sha256)
            item.setData(Qt.ItemDataRole.UserRole + 1, (metadata.minecraft_ranges, loaders))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if mod.sha256 in selected else Qt.CheckState.Unchecked)
            item.setToolTip(
                f"{translate('Type', self.locale)}: {translate(metadata.kind, self.locale)}\n"
                f"Minecraft: {', '.join(versions)}\n"
                f"{translate('Loader', self.locale)}: {', '.join(loaders)}\n{mod.path}"
            )
            if metadata.icon_bytes:
                pixmap = QPixmap()
                if pixmap.loadFromData(metadata.icon_bytes):
                    item.setIcon(QIcon(pixmap))
            self.list_widget.addItem(item)
        versions = sorted({version for value in self.mod_metadata.values()
                           for version in minecraft_version_choices(value[0])}, key=_sort_key)
        loaders = sorted({loader for value in self.mod_metadata.values() for loader in value[1]})
        self.version_filter.addItems(versions)
        self.loader_filter.addItems(loaders)
        self.version_filter.currentTextChanged.connect(self._apply_filters)
        self.loader_filter.currentTextChanged.connect(self._apply_filters)
        self.list_widget.itemDoubleClicked.connect(self._toggle_item)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_item_menu)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Minecraft:"))
        filters.addWidget(self.version_filter, 1)
        filters.addWidget(QLabel(translate("Loader:", self.locale)))
        filters.addWidget(self.loader_filter, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(translate("Select the profile mods. Filters hide incompatible rows but do not clear selections.", self.locale)))
        layout.addLayout(filters)
        layout.addWidget(self.list_widget, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_filters(self) -> None:
        """Hide mods that do not match the selected filters."""
        version = self.version_filter.currentText()
        loader = self.loader_filter.currentText()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            item_expressions, item_loaders = item.data(Qt.ItemDataRole.UserRole + 1)
            matches_version = version == translate("All versions", self.locale) or any(
                version_matches(version, expression) for expression in item_expressions
            )
            item.setHidden((version != translate("All versions", self.locale) and not matches_version)
                           or (loader != translate("All loaders", self.locale) and loader not in item_loaders))

    def _toggle_item(self, item: QListWidgetItem) -> None:
        """Toggle a mod state on double-click."""
        item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)

    def _show_item_menu(self, position) -> None:
        """Show the mod selection context menu."""
        item = self.list_widget.itemAt(position)
        if item is None:
            return
        self.list_widget.setCurrentItem(item)
        menu = QMenu(self)
        toggle_action = menu.addAction(translate("Enable" if item.checkState() != Qt.CheckState.Checked else "Disable", self.locale))
        menu.addAction(translate("Show path", self.locale)).triggered.connect(
            lambda: QMessageBox.information(self, translate("Mod information", self.locale), item.toolTip())
        )
        chosen = menu.exec(self.list_widget.mapToGlobal(position))
        if chosen == toggle_action:
            self._toggle_item(item)

    def selected_hashes(self) -> list[str]:
        """Return hashes for all checked mods, including filter-hidden items."""
        hashes: list[str] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                hashes.append(item.data(Qt.ItemDataRole.UserRole))
        return hashes


class ManualDialog(QDialog):
    """Display the localized user manual in a scrollable window."""

    def __init__(self, parent=None, locale: str = "en") -> None:
        super().__init__(parent)
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.setWindowTitle(f"{APP_NAME} User Manual")
        self.resize(1100, 760)
        self.setMinimumSize(720, 480)

        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(True)
        browser.setHtml(load_manual_html(locale))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(browser, 1)
        layout.addWidget(buttons)


class ExportModpackDialog(QDialog):
    """Dialog allowing user to choose which parts of the profile to export."""

    def __init__(
        self,
        profile_name: str,
        has_configs: bool,
        has_rp: bool,
        has_sp: bool,
        has_saves: bool,
        locale: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.locale = locale
        self.setWindowTitle(translate("Параметры экспорта модпака", self.locale))
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.resize(440, 260)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{translate('Экспорт профиля:', self.locale)} {profile_name}</b>"))
        layout.addWidget(QLabel(translate("Выберите компоненты для включения в модпак:", self.locale)))

        self.cb_mods = QCheckBox(translate("Моды (JAR-файлы)", self.locale))
        self.cb_mods.setChecked(True)
        self.cb_mods.setEnabled(False)
        layout.addWidget(self.cb_mods)

        self.cb_configs = QCheckBox(translate("Конфигурации (папка config)", self.locale))
        self.cb_configs.setChecked(has_configs)
        self.cb_configs.setEnabled(has_configs)
        layout.addWidget(self.cb_configs)

        self.cb_rp = QCheckBox(translate("Ресурспаки (текстуры)", self.locale))
        self.cb_rp.setChecked(has_rp)
        self.cb_rp.setEnabled(has_rp)
        layout.addWidget(self.cb_rp)

        self.cb_sp = QCheckBox(translate("Шейдерпаки (шейдеры)", self.locale))
        self.cb_sp.setChecked(has_sp)
        self.cb_sp.setEnabled(has_sp)
        layout.addWidget(self.cb_sp)

        self.cb_saves = QCheckBox(translate("Сохранения (миры)", self.locale))
        self.cb_saves.setChecked(False)
        self.cb_saves.setEnabled(has_saves)
        layout.addWidget(self.cb_saves)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> dict[str, bool]:
        """Return user selections for export."""
        return {
            "include_configs": self.cb_configs.isChecked(),
            "include_resourcepacks": self.cb_rp.isChecked(),
            "include_shaderpacks": self.cb_sp.isChecked(),
            "include_saves": self.cb_saves.isChecked(),
        }


class MainWindow(QMainWindow):
    """Window for game environments, the mod library, tags, and profiles."""

    def __init__(self) -> None:
        """Build the interface and perform the initial scan."""
        super().__init__()
        self.setWindowTitle(APP_SHORT_NAME)
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.resize(1600, 780)
        self.setMinimumSize(720, 540)
        self.app_config = AppConfig()
        self.locale = self.app_config.locale
        self.theme_name = self.app_config.theme
        self._apply_theme(self.theme_name)
        self.prism_data_dir: Path | None = find_default_prism_data_dir()
        self.library_dir = default_library_dir()
        self.asset_library_dir = default_asset_library_dir()
        self.save_library_dir = default_save_library_dir()
        self.user_data = UserDataStore()
        self.instances: list[PrismInstance] = []
        self.user_data.data.setdefault("game_dirs", [])
        configured_dirs = self.user_data.data["game_dirs"]
        known_dirs = {str(Path(value).resolve(strict=False)).casefold() for value in configured_dirs if isinstance(value, str)}
        for candidate in default_game_directory_candidates():
            if is_game_directory(candidate):
                key = str(candidate.resolve(strict=False)).casefold()
                if key not in known_dirs:
                    configured_dirs.append(str(candidate))
                    known_dirs.add(key)
        self.user_data.save()
        self.mods: list[ModFile] = []

        central = QWidget(self)
        central.setObjectName("mainContent")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 14, 18, 10)
        layout.setSpacing(10)
        heading_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QIcon(str(app_icon_path())).pixmap(32, 32))
        heading_row.addWidget(icon_label)
        heading = QLabel(f"{APP_SHORT_NAME} — Minecraft modification manager")
        heading.setObjectName("appHeading")
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        layout.addLayout(heading_row)
        subtitle = QLabel(
            "Manage game environments, the mod library, and profiles in one window. "
            "Drag column separators with the mouse."
        )
        subtitle.setObjectName("appSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self._build_instances_tab()
        self._build_library_tab()
        self._build_saves_tab()
        self._build_profiles_tab()
        self._build_environment_tab()
        self._build_virtualization_tab()
        self._build_menu_bar()
        self._build_assets_tab()
        self._build_config_backups_tab()
        self.table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.table, pos))
        self.library_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.library_table, pos))
        self.saves_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.saves_table, pos))
        self.profiles_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.profiles_table, pos))
        self.asset_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.asset_table, pos))
        self.environment_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.environment_table, pos))
        self.virtualization_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.virtualization_table, pos))
        self.asset_plan_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.asset_plan_table, pos))
        self.config_entries_table.customContextMenuRequested.connect(lambda pos: self._show_table_context_menu(self.config_entries_table, pos))
        self.library_table.cellDoubleClicked.connect(lambda row, column: self.edit_selected_mod_tags())
        self.profiles_table.cellDoubleClicked.connect(lambda row, column: self.edit_profile_mods())
        self.profiles_table.currentCellChanged.connect(self._profile_row_changed)
        self.table.cellDoubleClicked.connect(lambda row, column: self.analyze_selected_instance_logs())
        self.virtualization_plan: VirtualizationPlan | None = None

        self.setAcceptDrops(True)
        for tbl in (
            self.library_table,
            self.table,
            self.virtualization_table,
            self.saves_table,
            self.asset_table,
            self.environment_table,
        ):
            tbl.setAcceptDrops(True)
            tbl.installEventFilter(self)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        self.refresh_instances()
        self.refresh_library()
        self.refresh_saves()
        self.refresh_profiles()
        self.refresh_environment_scan()
        self.refresh_virtualization_profiles()
        self.refresh_assets()
        self.refresh_config_backup_choices()
        self._apply_locale(self.locale)

    def _apply_theme(self, theme_name: str) -> None:
        """Apply the theme at application level, including child dialogs."""
        self.theme_name = "dark" if theme_name == "dark" else "light"
        application = QApplication.instance()
        if application is not None:
            application.setStyleSheet(DARK_THEME if self.theme_name == "dark" else LIGHT_THEME)
        for name, action in getattr(self, "theme_actions", {}).items():
            action.setChecked(name == self.theme_name)

    def _set_theme(self, theme_name: str) -> None:
        """Switch the theme from the View menu."""
        self._apply_theme(theme_name)
        self.app_config.set_theme(self.theme_name)

    def _apply_locale(self, locale: str) -> None:
        """Update static interface labels after a locale change."""
        self.locale = locale if locale in SUPPORTED_LOCALES else "en"
        self.setWindowTitle(APP_SHORT_NAME)
        for widget in self.findChildren(QAbstractButton):
            widget.setText(translate(widget.text(), self.locale))
        for widget in self.findChildren(QLabel):
            widget.setText(translate(widget.text(), self.locale))
        for combo in self.findChildren(QComboBox):
            for index in range(combo.count()):
                combo.setItemText(index, translate(combo.itemText(index), self.locale))
        for table in self.findChildren(QTableWidget):
            for column in range(table.columnCount()):
                header = table.horizontalHeaderItem(column)
                if header is not None:
                    header.setText(translate(header.text(), self.locale))
        for line_edit in self.findChildren(QLineEdit):
            if line_edit.placeholderText():
                line_edit.setPlaceholderText(translate(line_edit.placeholderText(), self.locale))
        for index in range(self.tabs.count()):
            self.tabs.setTabText(index, translate(self.tabs.tabText(index), self.locale))
        for action in self.findChildren(QAction):
            action.setText(translate(action.text(), self.locale))
        for locale_code, action in getattr(self, "locale_actions", {}).items():
            action.setChecked(locale_code == self.locale)

    def _set_locale(self, locale: str) -> None:
        """Save the selected locale and apply it to the current window."""
        if locale not in SUPPORTED_LOCALES:
            return
        self.app_config.set_locale(locale)
        self._apply_locale(locale)
        self.refresh_instances()
        self.refresh_library()
        self.refresh_saves()
        self.refresh_profiles()
        self.refresh_assets()
        self.refresh_config_backup_choices()
        self._apply_locale(locale)

    def choose_locale(self) -> None:
        """Open the locale selector from the Settings menu."""
        language_titles = [locale_name(code) for code in SUPPORTED_LOCALES]
        current_index = SUPPORTED_LOCALES.index(self.locale)
        selected, accepted = QInputDialog.getItem(
            self,
            translate("Language", self.locale),
            translate("Language", self.locale),
            language_titles,
            current_index,
            False,
        )
        if accepted:
            selected_index = language_titles.index(selected)
            self._set_locale(SUPPORTED_LOCALES[selected_index])

    def _build_instances_tab(self) -> None:
        """Build the game environments tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.path_label)
        toolbar = QHBoxLayout()
        self.choose_button = QPushButton("Choose Prism folder")
        self.refresh_button = QPushButton("Refresh")
        self.analyze_logs_button = QPushButton("Analyze crash & logs…")
        self.choose_button.clicked.connect(self.choose_prism_folder)
        self.refresh_button.clicked.connect(self.refresh_instances)
        self.analyze_logs_button.clicked.connect(self.analyze_selected_instance_logs)
        toolbar.addWidget(self.choose_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.analyze_logs_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(translate_many(
            ["Source", "Name", "Minecraft", "Loader", "Loader version", "Status"],
            self.locale,
        ))
        self._configure_table(self.table)
        layout.addWidget(self.table, 1)
        self.add_game_dir_button = QPushButton("Add game folder…")
        self.create_official_instance_button = QPushButton("Create Minecraft Launcher instance…")
        self.remove_game_dir_button = QPushButton("Remove connected folder")
        self.add_game_dir_button.clicked.connect(self.add_game_directory)
        self.create_official_instance_button.clicked.connect(self.create_official_launcher_instance)
        self.remove_game_dir_button.clicked.connect(self.remove_selected_game_directory)
        toolbar.insertWidget(0, self.add_game_dir_button)
        toolbar.insertWidget(1, self.create_official_instance_button)
        toolbar.insertWidget(2, self.remove_game_dir_button)
        self.tabs.addTab(page, "Game environments")

    def _build_library_tab(self) -> None:
        """Build the shared mod library and tags tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        self.library_path_label = QLabel()
        self.library_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.library_path_label)
        toolbar = QHBoxLayout()
        self.import_button = QPushButton("Import JAR…")
        self.library_refresh_button = QPushButton("Refresh library")
        self.tags_button = QPushButton("Edit tags…")
        self.version_button = QPushButton("Edit Minecraft version…")
        self.modrinth_search_button = QPushButton("Search Modrinth…")
        self.check_updates_button = QPushButton("Check updates…")
        self.import_button.clicked.connect(self.choose_mods_to_import)
        self.library_refresh_button.clicked.connect(self.refresh_library)
        self.tags_button.clicked.connect(self.edit_selected_mod_tags)
        self.version_button.clicked.connect(self.edit_selected_mod_version)
        self.modrinth_search_button.clicked.connect(self.open_modrinth_catalog)
        self.check_updates_button.clicked.connect(self.check_library_updates)
        toolbar.addWidget(self.import_button)
        toolbar.addWidget(self.library_refresh_button)
        toolbar.addWidget(self.tags_button)
        toolbar.addWidget(self.version_button)
        toolbar.addWidget(self.modrinth_search_button)
        toolbar.addWidget(self.check_updates_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # Search and filter bar
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.mod_search_input = QLineEdit()
        self.mod_search_input.setPlaceholderText(translate("Поиск модов…", self.locale))
        self.mod_search_input.setClearButtonEnabled(True)
        self.mod_search_input.textChanged.connect(self._filter_library_table)
        filter_row.addWidget(self.mod_search_input, 2)

        filter_row.addWidget(QLabel("Minecraft:"))
        self.mod_version_filter = QComboBox()
        self.mod_version_filter.addItem(translate("Все версии", self.locale))
        self.mod_version_filter.currentIndexChanged.connect(self._filter_library_table)
        filter_row.addWidget(self.mod_version_filter, 1)

        filter_row.addWidget(QLabel(translate("Loader:", self.locale)))
        self.mod_loader_filter = QComboBox()
        self.mod_loader_filter.addItem(translate("Все загрузчики", self.locale))
        for ldr in ("Fabric", "Forge", "NeoForge", "Quilt"):
            self.mod_loader_filter.addItem(ldr)
        self.mod_loader_filter.currentIndexChanged.connect(self._filter_library_table)
        filter_row.addWidget(self.mod_loader_filter, 1)

        self.library_filter_status = QLabel()
        self.library_filter_status.setStyleSheet("color: #64748b; font-size: 12px;")
        filter_row.addWidget(self.library_filter_status)
        layout.addLayout(filter_row)

        self.library_table = QTableWidget(0, 7)
        self.library_table.setIconSize(QSize(20, 20))
        self.library_table.setHorizontalHeaderLabels(translate_many(
            ["Name", "Version", "Loader", "Dependencies", "Compatibility", "File", "Tags"],
            self.locale,
        ))
        self._configure_table(self.library_table)
        layout.addWidget(self.library_table, 1)
        self.tabs.addTab(page, "Mod library")

    def _build_saves_tab(self) -> None:
        """Build the save library and environment installation controls."""
        page = QWidget()
        layout = QVBoxLayout(page)
        self.saves_path_label = QLabel()
        self.saves_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.saves_path_label)
        toolbar = QHBoxLayout()
        self.save_import_button = QPushButton("Import save…")
        self.save_refresh_button = QPushButton("Refresh library")
        self.save_import_button.clicked.connect(self.choose_save_to_import)
        self.save_refresh_button.clicked.connect(self.refresh_saves)
        toolbar.addWidget(self.save_import_button)
        toolbar.addWidget(self.save_refresh_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        self.saves_table = QTableWidget(0, 3)
        self.saves_table.setHorizontalHeaderLabels(translate_many(["Save", "Size", "Path"], self.locale))
        self._configure_table(self.saves_table)
        layout.addWidget(self.saves_table, 1)
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Game environment:"))
        self.save_instance_combo = QComboBox()
        target_row.addWidget(self.save_instance_combo, 1)
        self.save_install_button = QPushButton("Install selected save")
        self.save_install_button.clicked.connect(self.install_selected_save)
        target_row.addWidget(self.save_install_button)
        layout.addLayout(target_row)
        self.tabs.addTab(page, "Saves")

    def _build_profiles_tab(self) -> None:
        """Build the combined profiles and virtualization view."""
        page = QWidget()
        outer = QVBoxLayout(page)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.profile_left = QWidget()
        layout = QVBoxLayout(self.profile_left)
        layout.addWidget(QLabel("Profiles store a game environment and selected mods."))
        selector = QHBoxLayout()
        selector.addWidget(QLabel("Instance for new profile:"))
        self.profile_instance_combo = QComboBox()
        selector.addWidget(self.profile_instance_combo, 1)
        layout.addLayout(selector)
        toolbar = QHBoxLayout()
        self.create_profile_button = QPushButton("Create profile…")
        self.edit_profile_button = QPushButton("Edit mods…")
        self.rename_profile_button = QPushButton("Rename…")
        self.delete_profile_button = QPushButton("Delete profile")
        self.export_profile_button = QPushButton("Export modpack…")
        self.import_profile_button = QPushButton("Import modpack…")
        self.create_profile_button.clicked.connect(self.create_profile)
        self.edit_profile_button.clicked.connect(self.edit_profile_mods)
        self.rename_profile_button.clicked.connect(self.rename_profile)
        self.delete_profile_button.clicked.connect(self.delete_profile)
        self.export_profile_button.clicked.connect(self.export_selected_profile)
        self.import_profile_button.clicked.connect(self.import_modpack)
        for button in (self.create_profile_button, self.edit_profile_button,
                       self.rename_profile_button, self.delete_profile_button,
                       self.export_profile_button, self.import_profile_button):
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.profiles_table = QTableWidget(0, 5)
        self.profiles_table.setHorizontalHeaderLabels(translate_many(
            ["Profile", "Game environment", "Minecraft", "Loader", "Mods selected"],
            self.locale,
        ))
        self._configure_table(self.profiles_table)
        layout.addWidget(self.profiles_table, 1)
        self.profile_right = QWidget()
        splitter.addWidget(self.profile_left)
        splitter.addWidget(self.profile_right)
        splitter.setChildrenCollapsible(False)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setHandleWidth(8)
        splitter.setOpaqueResize(True)
        self.profile_left.setMinimumHeight(300)
        self.profile_right.setMinimumHeight(260)
        splitter.setSizes([420, 360])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        outer.addWidget(splitter, 1)
        self.tabs.addTab(page, "Profiles")

    def _build_environment_tab(self) -> None:
        """Creates a read-only report of mod files in Prism instances."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "The check only reads files. External mods are not imported automatically, "
            "and game directories are not modified."
        ))
        toolbar = QHBoxLayout()
        self.environment_scan_button = QPushButton("Check environments")
        self.environment_logs_button = QPushButton("Analyze crash & logs…")
        self.environment_scan_button.clicked.connect(self.refresh_environment_scan)
        self.environment_logs_button.clicked.connect(self.analyze_selected_environment_logs)
        toolbar.addWidget(self.environment_scan_button)
        toolbar.addWidget(self.environment_logs_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        self.environment_table = QTableWidget(0, 5)
        self.environment_table.setHorizontalHeaderLabels(translate_many(
            ["Instance", "File", "Check result", "Size", "Path"],
            self.locale,
        ))
        self._configure_table(self.environment_table)
        layout.addWidget(self.environment_table, 1)
        self.tabs.addTab(page, "Environment check")

    def _build_virtualization_tab(self) -> None:
        """Builds the preview-and-apply UI for profile symlinks."""
        page = self.profile_right
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "Profile virtualization. Check the target path and changes before applying. "
            "Close the game before applying."
        ))
        selector = QHBoxLayout()
        selector.addWidget(QLabel("Profile:"))
        self.virtualization_profile_combo = QComboBox()
        self.virtualization_profile_combo.currentIndexChanged.connect(self._refresh_profile_compatibility)
        selector.addWidget(self.virtualization_profile_combo, 1)
        layout.addLayout(selector)
        toolbar = QHBoxLayout()
        self.preview_virtualization_button = QPushButton("Preview")
        self.apply_virtualization_button = QPushButton("Apply profile")
        self.rollback_virtualization_button = QPushButton("Rollback last application")
        self.check_conflicts_button = QPushButton("Check conflicts")
        self.profile_check_updates_button = QPushButton("Check profile updates")
        self.profile_analyze_logs_button = QPushButton("Analyze crash & logs…")
        self.check_conflicts_button.clicked.connect(self.check_selected_profile_conflicts)
        self.preview_virtualization_button.clicked.connect(self.preview_selected_profile)
        self.apply_virtualization_button.clicked.connect(self.apply_selected_profile)
        self.rollback_virtualization_button.clicked.connect(self.rollback_virtualization)
        self.profile_check_updates_button.clicked.connect(self.check_profile_updates)
        self.profile_analyze_logs_button.clicked.connect(self.analyze_selected_profile_logs)
        toolbar.addWidget(self.preview_virtualization_button)
        toolbar.addWidget(self.apply_virtualization_button)
        toolbar.addWidget(self.rollback_virtualization_button)
        toolbar.addWidget(self.check_conflicts_button)
        toolbar.addWidget(self.profile_check_updates_button)
        toolbar.addWidget(self.profile_analyze_logs_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        self.virtualization_path_label = QLabel("Select a profile first.")
        self.virtualization_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.virtualization_path_label)
        self.virtualization_table = QTableWidget(0, 3)
        self.virtualization_table.setHorizontalHeaderLabels(
            translate_many(["File", "Action", "Details"], self.locale)
        )
        self._configure_table(self.virtualization_table)
        layout.addWidget(self.virtualization_table, 1)

    def _build_menu_bar(self) -> None:
        """Build the standard application menus."""
        file_menu = self.menuBar().addMenu("File")
        import_action = file_menu.addAction("Import mods…")
        import_action.triggered.connect(self.choose_mods_to_import)
        export_pack_action = file_menu.addAction("Export modpack…")
        export_pack_action.triggered.connect(self.export_selected_profile)
        import_pack_action = file_menu.addAction("Import modpack…")
        import_pack_action.triggered.connect(self.import_modpack)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)
        view_menu = self.menuBar().addMenu("View")
        theme_group = QActionGroup(view_menu)
        theme_group.setExclusive(True)
        self.theme_actions = {}
        for theme_name, title in (("light", "Light"), ("dark", "Dark")):
            action = view_menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(theme_name == self.theme_name)
            action.triggered.connect(lambda checked=False, name=theme_name: self._set_theme(name))
            theme_group.addAction(action)
            self.theme_actions[theme_name] = action
        settings_menu = self.menuBar().addMenu("Settings")
        settings_menu.addAction("Open library folder", self.open_library_folder)
        language_menu = settings_menu.addMenu("Language")
        language_group = QActionGroup(language_menu)
        language_group.setExclusive(True)
        self.locale_actions = {}
        for locale_code in SUPPORTED_LOCALES:
            title = locale_name(locale_code)
            action = language_menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(locale_code == self.locale)
            action.triggered.connect(lambda checked=False, code=locale_code: self._set_locale(code))
            language_group.addAction(action)
            self.locale_actions[locale_code] = action
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("About", self.show_manual)

    def show_manual(self) -> None:
        """Open the manual for the currently selected locale."""
        ManualDialog(self, self.locale).exec()

    def open_library_folder(self) -> None:
        """Open the mod library folder."""
        self.library_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library_dir)))

    def _build_assets_tab(self) -> None:
        """Creates asset library, profile selection, and safe apply controls."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "ZIP archives of resource packs and shaders are copied to a separate library. "
            "Applying a profile creates links; regular files are not overwritten."
        ))
        toolbar = QHBoxLayout()
        self.asset_kind_combo = QComboBox()
        self.asset_kind_combo.addItem("Resource packs", "resourcepacks")
        self.asset_kind_combo.addItem("Shaders", "shaderpacks")
        self.asset_kind_combo.currentIndexChanged.connect(self.refresh_assets)
        self.asset_import_button = QPushButton("Import ZIP…")
        self.asset_refresh_button = QPushButton("Refresh library")
        self.asset_assign_button = QPushButton("Choose for profile…")
        self.asset_import_button.clicked.connect(self.choose_assets_to_import)
        self.asset_refresh_button.clicked.connect(self.refresh_assets)
        self.asset_assign_button.clicked.connect(self.assign_assets_to_profile)
        for button in (self.asset_kind_combo, self.asset_import_button, self.asset_refresh_button, self.asset_assign_button):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        self.asset_table = QTableWidget(0, 3)
        self.asset_table.setHorizontalHeaderLabels(translate_many(["Archive", "Size", "Path"], self.locale))
        self._configure_table(self.asset_table)
        layout.addWidget(self.asset_table, 1)
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile to apply:"))
        self.asset_profile_combo = QComboBox()
        self.asset_profile_combo.currentIndexChanged.connect(self.preview_selected_assets)
        profile_row.addWidget(self.asset_profile_combo, 1)
        self.asset_preview_button = QPushButton("Preview")
        self.asset_apply_button = QPushButton("Apply assets")
        self.asset_rollback_button = QPushButton("Rollback assets")
        self.asset_preview_button.clicked.connect(self.preview_selected_assets)
        self.asset_apply_button.clicked.connect(self.apply_selected_assets)
        self.asset_rollback_button.clicked.connect(self.rollback_selected_assets)
        profile_row.addWidget(self.asset_preview_button)
        profile_row.addWidget(self.asset_apply_button)
        profile_row.addWidget(self.asset_rollback_button)
        layout.addLayout(profile_row)
        self.asset_preview_label = QLabel("Select a profile to preview changes.")
        self.asset_preview_label.setWordWrap(True)
        self.asset_preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.asset_preview_label)
        self.asset_plan_table = QTableWidget(0, 3)
        self.asset_plan_table.setHorizontalHeaderLabels(
            translate_many(["Archive", "Action", "Details"], self.locale)
        )
        self._configure_table(self.asset_plan_table)
        layout.addWidget(self.asset_plan_table, 1)
        self.tabs.addTab(page, "Resource packs and shaders")

    def _build_config_backups_tab(self) -> None:
        """Creates manual backup and restore controls for instance configs."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "A backup archives the selected instance's config folder. "
            "Restoration first saves the current configs and does not delete files missing from the archive."
        ))
        row = QHBoxLayout()
        row.addWidget(QLabel("Game environment:"))
        self.config_instance_combo = QComboBox()
        row.addWidget(self.config_instance_combo, 1)
        self.config_backup_button = QPushButton("Create backup")
        self.config_backup_button.clicked.connect(self.backup_selected_config)
        row.addWidget(self.config_backup_button)
        layout.addLayout(row)
        backup_row = QHBoxLayout()
        backup_row.addWidget(QLabel("Backup to restore:"))
        self.config_backup_combo = QComboBox()
        backup_row.addWidget(self.config_backup_combo, 1)
        self.config_restore_button = QPushButton("Restore archive…")
        self.config_restore_button.clicked.connect(self.restore_selected_config)
        backup_row.addWidget(self.config_restore_button)
        self.config_refresh_button = QPushButton("Refresh list")
        self.config_refresh_button.clicked.connect(self.refresh_config_backup_choices)
        backup_row.addWidget(self.config_refresh_button)
        layout.addLayout(backup_row)
        self.config_entries_table = QTableWidget(0, 4)
        self.config_entries_table.setHorizontalHeaderLabels(
            translate_many(["Type", "Name", "Size", "Path"], self.locale)
        )
        self._configure_table(self.config_entries_table)
        layout.addWidget(self.config_entries_table, 1)
        self.tabs.addTab(page, "Configs and backups")

    def refresh_virtualization_profiles(self) -> None:
        """Refreshes the profile selector while preserving its current choice."""
        if not hasattr(self, "virtualization_profile_combo"):
            return
        previous_id = self.virtualization_profile_combo.currentData()
        self.virtualization_profile_combo.blockSignals(True)
        self.virtualization_profile_combo.clear()
        for profile in self.user_data.profiles():
            label = f"{profile.get('name', '(unnamed)')} — {profile.get('instance_id', '')}"
            self.virtualization_profile_combo.addItem(label, profile.get("id"))
        for index in range(self.virtualization_profile_combo.count()):
            if self.virtualization_profile_combo.itemData(index) == previous_id:
                self.virtualization_profile_combo.setCurrentIndex(index)
                break
        self.virtualization_profile_combo.blockSignals(False)
        self.preview_selected_profile()
        if hasattr(self, "asset_profile_combo"):
            previous_asset_id = self.asset_profile_combo.currentData()
            self.asset_profile_combo.blockSignals(True)
            self.asset_profile_combo.clear()
            for profile in self.user_data.profiles():
                self.asset_profile_combo.addItem(f"{profile.get('name', '(unnamed)')} — {profile.get('instance_id', '')}", profile.get("id"))
            for index in range(self.asset_profile_combo.count()):
                if self.asset_profile_combo.itemData(index) == previous_asset_id:
                    self.asset_profile_combo.setCurrentIndex(index)
                    break
            self.asset_profile_combo.blockSignals(False)
            self.preview_selected_assets()
        if hasattr(self, "config_instance_combo"):
            self.refresh_config_instance_choices()
        if hasattr(self, "save_instance_combo"):
            self.refresh_save_instance_choices()
        if hasattr(self, "library_table"):
            self.refresh_library()

    def _refresh_profile_compatibility(self) -> None:
        """Update compatibility statuses for the selected profile."""
        if hasattr(self, "library_table"):
            self.refresh_library()
        else:
            self.preview_selected_profile()

    def _virtualization_profile(self) -> dict | None:
        """Returns the profile selected for virtualization."""
        profile_id = self.virtualization_profile_combo.currentData()
        return next((profile for profile in self.user_data.profiles() if profile.get("id") == profile_id), None)

    def preview_selected_profile(self) -> None:
        """Displays a non-mutating plan for the selected profile."""
        if not hasattr(self, "virtualization_table"):
            return
        profile = self._virtualization_profile()
        self.virtualization_plan = None
        if profile is None:
            self.virtualization_table.setRowCount(0)
            self.virtualization_path_label.setText(translate("No profiles. Create a profile on the Profiles tab.", self.locale))
            self.apply_virtualization_button.setEnabled(False)
            return
        plan = preview_profile(profile, self.library_dir)
        self.virtualization_plan = plan
        self.virtualization_table.setSortingEnabled(False)
        self.virtualization_table.setRowCount(len(plan.actions))
        for row, action in enumerate(plan.actions):
            self._set_item(self.virtualization_table, row, 0, action.filename, action.filename.casefold(), str(action.path))
            self._set_item(self.virtualization_table, row, 1, action.action, action.action.casefold(), str(action.path))
            self._set_item(self.virtualization_table, row, 2, action.details, action.details.casefold(), str(action.path))
        self.virtualization_table.setSortingEnabled(True)
        self._fit_table_columns(self.virtualization_table)
        target = str(plan.mods_dir) if plan.mods_dir else "mods folder not found"
        summary = f"Target folder: {target}"
        if plan.errors:
            summary += "\nProblems: " + "; ".join(plan.errors)
        else:
            creates = sum(action.action == "Create link" for action in plan.actions)
            removes = sum(action.action == "Remove link" for action in plan.actions)
            summary += f"\nLinks to be created: {creates}; managed links to be removed: {removes}."
        self.virtualization_path_label.setText(translate(summary, self.locale))
        self.apply_virtualization_button.setEnabled(plan.can_apply)

    def apply_selected_profile(self) -> None:
        """Confirms and applies the selected profile after previewing changes."""
        profile = self._virtualization_profile()
        if profile is None:
            return
        self.preview_selected_profile()
        plan = self.virtualization_plan
        if plan is None or not plan.can_apply:
            QMessageBox.information(self, "Virtualization", "There are no safe changes to apply. Check the preview.")
            return
        creates = sum(action.action == "Create link" for action in plan.actions)
        removes = sum(action.action == "Remove link" for action in plan.actions)
        answer = QMessageBox.warning(
            self, "Apply profile",
            f"Apply profile «{profile.get('name', '')}»?\n\n"
            f"Links to be created: {creates}; MineOrganizer links to remove: {removes}.\n"
            "Regular files will remain unchanged. Close Minecraft before continuing.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        success, message = apply_profile(profile, self.library_dir)
        if success:
            QMessageBox.information(self, "Virtualization", message)
            self.refresh_environment_scan()
            self.preview_selected_profile()
        else:
            QMessageBox.critical(self, "Virtualization error", message)
            self.preview_selected_profile()

    def rollback_virtualization(self) -> None:
        """Reverts the most recent completed virtualization operation."""
        answer = QMessageBox.question(
            self, "Virtualization rollback",
            "Undo the last profile application? Files changed manually after application will be preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        success, message = rollback_last(library_dir=self.library_dir)
        if success:
            QMessageBox.information(self, "Rollback", message)
            self.refresh_environment_scan()
            self.preview_selected_profile()
        else:
            QMessageBox.warning(self, "Rollback", message)

    def _asset_kind(self) -> str:
        """Returns the active asset category."""
        return str(self.asset_kind_combo.currentData() or "resourcepacks")

    def refresh_save_instance_choices(self) -> None:
        """Update environments where a save can be installed."""
        if not hasattr(self, "save_instance_combo"):
            return
        previous = self.save_instance_combo.currentData()
        self.save_instance_combo.blockSignals(True)
        self.save_instance_combo.clear()
        for instance in self.instances:
            self.save_instance_combo.addItem(
                f"{instance.launcher}: {instance.name} — {instance.minecraft_version}",
                str(instance.path),
            )
        index = self.save_instance_combo.findData(previous)
        if index >= 0:
            self.save_instance_combo.setCurrentIndex(index)
        self.save_instance_combo.blockSignals(False)

    def refresh_saves(self) -> None:
        """Show saves from the shared library."""
        if not hasattr(self, "saves_table"):
            return
        self.saves_path_label.setText(translate(f"Save library: {self.save_library_dir}", self.locale))
        entries = scan_saves(self.save_library_dir)
        self.saves_table.setSortingEnabled(False)
        self.saves_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [entry.name, self._format_size(entry.size), str(entry.path)]
            sorts = [entry.name.casefold(), entry.size, str(entry.path).casefold()]
            for column, value in enumerate(values):
                self._set_item(self.saves_table, row, column, value, sorts[column], str(entry.path))
        self.saves_table.setSortingEnabled(True)
        self._fit_table_columns(self.saves_table)
        self.refresh_save_instance_choices()

    def choose_save_to_import(self) -> None:
        """Import the selected world folder into the save library."""
        selected = QFileDialog.getExistingDirectory(self, "Choose a Minecraft save folder", str(Path.home()))
        if not selected:
            return
        success, message = import_save(Path(selected), self.save_library_dir)
        (QMessageBox.information if success else QMessageBox.warning)(self, "Import save", message)
        self.refresh_saves()

    def install_selected_save(self) -> None:
        """Install the selected save into the environment's saves folder."""
        row = self.saves_table.currentRow()
        instance_path = self.save_instance_combo.currentData()
        if row < 0 or not instance_path:
            QMessageBox.information(self, "Saves", "Select a save and a game environment.")
            return
        item = self.saves_table.item(row, 0)
        source_path = Path(str(item.data(Qt.ItemDataRole.UserRole + 2))) if item else None
        if source_path is None:
            return
        destination = find_saves_dir(Path(instance_path)) / source_path.name
        overwrite = False
        if destination.exists():
            answer = QMessageBox.warning(
                self,
                "The save already exists",
                f'World "{source_path.name}" already exists in the selected environment. Overwrite it?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            overwrite = answer == QMessageBox.StandardButton.Yes
            if not overwrite:
                return
        success, message = install_save(source_path, Path(instance_path), overwrite)
        (QMessageBox.information if success else QMessageBox.warning)(self, "Install save", message)

    def refresh_assets(self) -> None:
        """Scans and displays the selected asset library."""
        if not hasattr(self, "asset_table"):
            return
        kind = self._asset_kind()
        assets = scan_assets(self.asset_library_dir, kind)
        self.asset_table.setSortingEnabled(False)
        self.asset_table.setRowCount(len(assets))
        for row, asset in enumerate(assets):
            values = [asset.name, self._format_size(asset.size), str(asset.path)]
            sorts = [asset.name.casefold(), asset.size, str(asset.path).casefold()]
            for column, value in enumerate(values):
                self._set_item(self.asset_table, row, column, value, sorts[column], str(asset.path))
        self.asset_table.setSortingEnabled(True)
        self._fit_table_columns(self.asset_table)
        self.preview_selected_assets()

    def choose_assets_to_import(self) -> None:
        """Copies selected ZIP archives into the active asset category."""
        kind = self._asset_kind()
        title = "Choose resource packs" if kind == "resourcepacks" else "Choose shaders"
        selected, _ = QFileDialog.getOpenFileNames(self, title, str(Path.home()), "ZIP archives (*.zip)")
        if not selected:
            return
        imported, skipped, errors = import_assets([Path(path) for path in selected], self.asset_library_dir, kind)
        self.refresh_assets()
        message = f"Imported: {imported}\nSkipped (duplicates or unsuitable files): {skipped}"
        if errors:
            message += "\n\nErrors:\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "Import assets", message)

    def assign_assets_to_profile(self) -> None:
        """Stores selected asset hashes in the chosen profile."""
        profile_id = self.asset_profile_combo.currentData()
        profile = next((item for item in self.user_data.profiles() if item.get("id") == profile_id), None)
        if profile is None:
            QMessageBox.information(self, "Profile assets", "Create a profile first.")
            return
        kind = self._asset_kind()
        field = "enabled_resourcepack_hashes" if kind == "resourcepacks" else "enabled_shaderpack_hashes"
        dialog = ModSelectionDialog(scan_assets(self.asset_library_dir, kind), set(profile.get(field, [])))
        dialog.setWindowTitle("Choose resource packs" if kind == "resourcepacks" else "Choose shaders")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.user_data.update_profile_assets(profile_id, kind, dialog.selected_hashes())
            self.preview_selected_assets()
            QMessageBox.information(self, "Profile assets", "Selection saved. Apply the profile separately to change game files.")

    def _asset_profile(self) -> dict | None:
        """Returns the profile selected for asset application."""
        profile_id = self.asset_profile_combo.currentData()
        return next((profile for profile in self.user_data.profiles() if profile.get("id") == profile_id), None)

    def preview_selected_assets(self) -> None:
        """Shows planned asset changes without modifying files."""
        if not hasattr(self, "asset_plan_table"):
            return
        profile = self._asset_profile()
        if profile is None:
            self.asset_plan_table.setRowCount(0)
            self.asset_preview_label.setText(translate(
                "Create a profile to manage resource packs and shaders.", self.locale
            ))
            self.asset_apply_button.setEnabled(False)
            return
        plan = preview_assets(profile, self.asset_library_dir, self._asset_kind())
        self.asset_plan_table.setSortingEnabled(False)
        self.asset_plan_table.setRowCount(len(plan.actions))
        for row, action in enumerate(plan.actions):
            for column, value in enumerate((action.filename, action.action, action.details)):
                self._set_item(self.asset_plan_table, row, column, value, value.casefold(), str(action.path))
        self.asset_plan_table.setSortingEnabled(True)
        self._fit_table_columns(self.asset_plan_table)
        summary = f"Target folder: {plan.target_dir}"
        if plan.errors:
            summary += "\nProblems: " + "; ".join(plan.errors)
        else:
            creates = sum(action.action == "Create link" for action in plan.actions)
            removes = sum(action.action == "Remove link" for action in plan.actions)
            summary += f"\nLinks to be created: {creates}; managed links removed: {removes}."
        self.asset_preview_label.setText(translate(summary, self.locale))
        self.asset_apply_button.setEnabled(plan.can_apply)

    def apply_selected_assets(self) -> None:
        """Confirms and applies resource pack or shader pack links."""
        profile = self._asset_profile()
        if profile is None:
            return
        self.preview_selected_assets()
        if not self.asset_apply_button.isEnabled():
            QMessageBox.information(self, "Assets", "There are no safe changes to apply.")
            return
        answer = QMessageBox.warning(self, "Apply assets", "Apply the selected archives? Close Minecraft before continuing.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        success, message = apply_assets(profile, self.asset_library_dir, self._asset_kind())
        (QMessageBox.information if success else QMessageBox.critical)(self, "Assets", message)
        self.preview_selected_assets()

    def rollback_selected_assets(self) -> None:
        """Rolls back the latest asset application."""
        answer = QMessageBox.question(self, "Asset rollback", "Undo the last resource pack/shader application?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        success, message = rollback_assets(library_root=self.asset_library_dir)
        (QMessageBox.information if success else QMessageBox.warning)(self, "Asset rollback", message)
        self.preview_selected_assets()

    def refresh_config_instance_choices(self) -> None:
        """Refreshes the Prism instance list for config backup operations."""
        if not hasattr(self, "config_instance_combo"):
            return
        previous = self.config_instance_combo.currentData()
        self.config_instance_combo.clear()
        for instance in self.instances:
            self.config_instance_combo.addItem(f"{instance.launcher}: {instance.name} — {instance.minecraft_version}", str(instance.path))
        index = self.config_instance_combo.findData(previous)
        if index >= 0:
            self.config_instance_combo.setCurrentIndex(index)

    def refresh_config_backup_choices(self) -> None:
        """Refreshes the available config backup archives."""
        if not hasattr(self, "config_backup_combo"):
            return
        previous = self.config_backup_combo.currentData()
        self.config_backup_combo.clear()
        for path in list_config_backups():
            self.config_backup_combo.addItem(path.name, str(path))
        index = self.config_backup_combo.findData(previous)
        if index >= 0:
            self.config_backup_combo.setCurrentIndex(index)
        if hasattr(self, "config_instance_combo"):
            self.refresh_config_instance_choices()
        self.refresh_config_entries()

    def refresh_config_entries(self) -> None:
        """Show discovered config folders and backup archives."""
        if not hasattr(self, "config_entries_table"):
            return
        rows: list[tuple[str, str, int, str]] = []
        for instance in self.instances:
            config_dir = find_config_dir(instance.path)
            if config_dir is None:
                continue
            size = sum(
                item.stat().st_size
                for item in config_dir.rglob("*")
                if item.is_file() and not item.is_symlink()
            )
            rows.append(("Config", instance.name, size, str(config_dir)))
        for backup in list_config_backups():
            try:
                size = backup.stat().st_size
            except OSError:
                size = 0
            rows.append(("Backup", backup.name, size, str(backup)))
        self.config_entries_table.setSortingEnabled(False)
        self.config_entries_table.setRowCount(len(rows))
        for row, (kind, name, size, path) in enumerate(rows):
            values = [kind, name, self._format_size(size), path]
            sorts = [kind.casefold(), name.casefold(), size, path.casefold()]
            for column, value in enumerate(values):
                self._set_item(self.config_entries_table, row, column, value, sorts[column], path)
            kind_item = self.config_entries_table.item(row, 0)
            if kind_item is not None:
                kind_item.setData(Qt.ItemDataRole.UserRole + 3, kind)
        self.config_entries_table.setSortingEnabled(True)
        self._fit_table_columns(self.config_entries_table)

    def backup_selected_config(self) -> None:
        """Creates a backup of the selected instance config directory."""
        path = self.config_instance_combo.currentData()
        if not path:
            QMessageBox.information(self, "Backups", "Select a Prism instance first.")
            return
        success, message = create_config_backup(Path(path))
        (QMessageBox.information if success else QMessageBox.warning)(self, "Backup", message)
        self.refresh_config_backup_choices()

    def restore_selected_config(self) -> None:
        """Restores the selected backup after explicit confirmation."""
        instance_path = self.config_instance_combo.currentData()
        backup_path = self.config_backup_combo.currentData()
        if not instance_path or not backup_path:
            QMessageBox.information(self, "Restoration", "Select an instance and a backup.")
            return
        answer = QMessageBox.warning(self, "Restore configs", "A copy of the current configs will be created before restoration. Files missing from the archive will not be deleted. Continue?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        success, message = restore_config_backup(Path(backup_path), Path(instance_path))
        (QMessageBox.information if success else QMessageBox.critical)(self, "Config restoration", message)
        self.refresh_config_backup_choices()

    def delete_selected_config_entry(self) -> None:
        """Delete the selected config directory or backup archive."""
        row = self.config_entries_table.currentRow()
        if row < 0:
            return
        kind_item = self.config_entries_table.item(row, 0)
        path_item = self.config_entries_table.item(row, 3)
        if kind_item is None or path_item is None:
            return
        kind = str(kind_item.data(Qt.ItemDataRole.UserRole + 3) or "")
        path = Path(str(path_item.data(Qt.ItemDataRole.UserRole + 2) or path_item.toolTip()))
        if kind == "Config":
            title = "Delete configs"
            prompt = f'Delete all files in the config folder "{path}"?'
        elif kind == "Backup":
            title = "Delete backup"
            prompt = f'Delete the backup archive "{path.name}"?'
        else:
            return
        answer = QMessageBox.warning(
            self,
            title,
            prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        success, message = (
            delete_config_directory(path)
            if kind == "Config"
            else delete_config_backup(path)
        )
        (QMessageBox.information if success else QMessageBox.warning)(self, title, message)
        self.refresh_config_backup_choices()

    def refresh_environment_scan(self) -> None:
        """Scans instance mods folders without importing or changing files."""
        if not hasattr(self, "environment_table"):
            return
        findings = scan_environment_mods(self.instances, self.library_dir)
        self.environment_table.setSortingEnabled(False)
        self.environment_table.setRowCount(len(findings))
        for row, finding in enumerate(findings):
            size = self._format_size(finding.size) if finding.size is not None else "—"
            values = [finding.instance_name, finding.filename, finding.status,
                      size, str(finding.path)]
            sort_values = [value.casefold() for value in values]
            sort_values[3] = finding.size if finding.size is not None else -1
            for column, value in enumerate(values):
                self._set_item(self.environment_table, row, column, value,
                               sort_values[column], str(finding.path))
        self.environment_table.setSortingEnabled(True)
        self._fit_table_columns(self.environment_table)
        external_count = sum(
            finding.status == "External mod — not imported" for finding in findings
        )
        self.status_label.setText(translate(
            f"Environment check completed: {len(findings)} records, "
            f"external mods not imported: {external_count}", self.locale
        ))

    @staticmethod
    def _configure_table(table: QTableWidget) -> None:
        """Configure a table with independently resizable columns."""
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setDefaultSectionSize(128)
        header.setSectionsMovable(True)
        header.setHighlightSections(False)
        vertical_header = table.verticalHeader()
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vertical_header.setDefaultSectionSize(30)
        vertical_header.setMinimumSectionSize(30)
        vertical_header.setSectionsClickable(False)
        vertical_header.setHighlightSections(False)
        table.setWordWrap(False)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    @staticmethod
    def _fit_table_columns(table: QTableWidget) -> None:
        """Fit column widths to table headers and contents."""
        table.resizeColumnsToContents()

    def _set_item(self, table: QTableWidget, row: int, column: int, value: str,
                  sort_value: object | None = None, tooltip: str = "",
                  icon: QIcon | None = None) -> None:
        """Add a cell with a sort key and tooltip."""
        item = NaturalSortItem(translate(value, self.locale))
        if icon is not None and not icon.isNull():
            item.setIcon(icon)
        if sort_value is not None:
            item.setData(Qt.ItemDataRole.UserRole, sort_value)
        if tooltip:
            item.setToolTip(tooltip)
            item.setData(Qt.ItemDataRole.UserRole + 2, tooltip)
        table.setItem(row, column, item)

    def _show_table_context_menu(self, table: QTableWidget, position) -> None:
        """Show actions appropriate for the selected table."""
        index = table.indexAt(position)
        if not index.isValid():
            return
        table.setCurrentCell(index.row(), index.column())
        menu = QMenu(self)
        if table is self.library_table:
            edit_tags = menu.addAction(translate("Edit tags…", self.locale))
            edit_version = menu.addAction(translate("Edit Minecraft version…", self.locale))
            rename = menu.addAction(translate("Rename file…", self.locale))
            delete = menu.addAction(translate("Remove from library…", self.locale))
            menu.addSeparator()
            open_folder = menu.addAction(translate("Open file folder", self.locale))
            copy_path = menu.addAction(translate("Copy path", self.locale))
            chosen = menu.exec(table.viewport().mapToGlobal(position))
            if chosen == edit_tags:
                self.edit_selected_mod_tags()
            elif chosen == edit_version:
                self.edit_selected_mod_version()
            elif chosen == rename:
                self.rename_selected_mod()
            elif chosen == delete:
                self.delete_selected_mod()
            elif chosen == copy_path:
                self._copy_selected_path(table, table.currentColumn())
            elif chosen == open_folder:
                self._open_selected_path(table)
        elif table is self.profiles_table:
            edit = menu.addAction(translate("Edit mod list…", self.locale))
            rename = menu.addAction(translate("Rename profile…", self.locale))
            delete = menu.addAction(translate("Delete profile…", self.locale))
            chosen = menu.exec(table.viewport().mapToGlobal(position))
            if chosen == edit:
                self.edit_profile_mods()
            elif chosen == rename:
                self.rename_profile()
            elif chosen == delete:
                self.delete_profile()
        elif table is self.asset_table:
            rename = menu.addAction(translate("Rename file…", self.locale))
            delete = menu.addAction(translate("Remove from library…", self.locale))
            open_folder = menu.addAction(translate("Open file folder", self.locale))
            copy_path = menu.addAction(translate("Copy path", self.locale))
            chosen = menu.exec(table.viewport().mapToGlobal(position))
            if chosen == rename:
                self.rename_selected_asset()
            elif chosen == delete:
                self.delete_selected_asset()
            elif chosen == copy_path:
                self._copy_selected_path(table, 2)
            elif chosen == open_folder:
                self._open_selected_path(table)
        elif table is self.config_entries_table:
            delete = menu.addAction(translate("Delete config", self.locale))
            open_folder = menu.addAction(translate("Open folder", self.locale))
            copy_path = menu.addAction(translate("Copy path", self.locale))
            chosen = menu.exec(table.viewport().mapToGlobal(position))
            if chosen == delete:
                self.delete_selected_config_entry()
            elif chosen == copy_path:
                self._copy_selected_path(table, 3)
            elif chosen == open_folder:
                self._open_selected_path(table)
        elif table is self.table or table is self.environment_table:
            analyze = menu.addAction(translate("Анализ крашей и логов…", self.locale))
            open_folder = menu.addAction(translate("Open folder", self.locale))
            copy_path = menu.addAction(translate("Copy path", self.locale))
            chosen = menu.exec(table.viewport().mapToGlobal(position))
            if chosen == analyze:
                if table is self.table:
                    self.analyze_selected_instance_logs()
                else:
                    self.analyze_selected_environment_logs()
            elif chosen == copy_path:
                self._copy_selected_path(table, table.currentColumn())
            elif chosen == open_folder:
                self._open_selected_path(table)
        else:
            open_folder = menu.addAction(translate("Open folder", self.locale))
            copy_path = menu.addAction(translate("Copy path", self.locale))
            chosen = menu.exec(table.viewport().mapToGlobal(position))
            if chosen == copy_path:
                self._copy_selected_path(table, table.currentColumn())
            elif chosen == open_folder:
                self._open_selected_path(table)

    def _selected_path(self, table: QTableWidget) -> Path | None:
        """Get a row path from the cell's internal data."""
        row, column = table.currentRow(), table.currentColumn()
        item = table.item(row, column) if row >= 0 and column >= 0 else None
        if item is None:
            return None
        raw = item.data(Qt.ItemDataRole.UserRole + 2)
        if not raw:
            raw = item.toolTip()
        try:
            candidate = Path(str(raw))
            return candidate if candidate.exists() or candidate.is_symlink() else None
        except (OSError, TypeError, ValueError):
            return None

    def _open_selected_path(self, table: QTableWidget) -> None:
        """Open a file or its containing folder in the system file manager."""
        path = self._selected_path(table)
        if path is None:
            return
        target = path.parent if path.is_file() or path.is_symlink() else path
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _copy_selected_path(self, table: QTableWidget, column: int) -> None:
        """Copy the path of the selected file or instance."""
        row = table.currentRow()
        item = table.item(row, column) if row >= 0 else None
        if item is None:
            return
        raw = item.data(Qt.ItemDataRole.UserRole + 2) or item.toolTip() or item.text()
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(str(raw))
        self.status_label.setText(translate("Path copied to clipboard", self.locale))

    def _path_is_link_target(self, target: Path) -> bool:
        """Check whether a file is used as a symbolic-link target in Prism."""
        for instance in self.instances:
            for folder_name in ("mods", "resourcepacks", "shaderpacks"):
                folder = instance.path / folder_name
                try:
                    for entry in folder.iterdir():
                        if entry.is_symlink():
                            try:
                                if entry.resolve() == target.resolve():
                                    return True
                            except OSError:
                                continue
                except OSError:
                    continue
        return False

    def rename_selected_mod(self) -> None:
        """Rename a JAR without changing its contents."""
        row = self.library_table.currentRow()
        if row < 0:
            return
        path = Path(str(self.library_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 2)))
        if self._path_is_link_target(path):
            QMessageBox.warning(self, "Renaming is not allowed", "The mod is currently used by a symbolic link in a game environment. Remove it from the active profile first.")
            return
        name, accepted = QInputDialog.getText(self, "Rename mod", "New file name (with .jar):", text=path.name)
        if not accepted or not name.strip() or name.strip() == path.name:
            return
        new_name = Path(name.strip()).name
        if Path(new_name).suffix.lower() != ".jar" or new_name in {".", ".."}:
            QMessageBox.warning(self, "Invalid name", "Specify a JAR file name with the .jar extension.")
            return
        destination = path.with_name(new_name)
        if destination.exists():
            QMessageBox.warning(self, "File already exists", "A file with this name already exists in the library.")
            return
        try:
            path.rename(destination)
        except OSError as error:
            QMessageBox.critical(self, "Renaming", str(error))
            return
        self.refresh_library()

    def delete_selected_mod(self) -> None:
        """Delete a mod from the library after confirmation."""
        row = self.library_table.currentRow()
        if row < 0:
            return
        path = Path(str(self.library_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 2)))
        if self._path_is_link_target(path):
            QMessageBox.warning(self, "Deletion is not allowed", "The mod is currently used by a symbolic link in a game environment. Remove it from the active profile first.")
            return
        answer = QMessageBox.question(self, "Delete mod", f'Delete "{path.name}" from the shared library? Profiles containing this mod will lose their reference to it.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as error:
            QMessageBox.critical(self, "Deletion", str(error))
            return
        self.refresh_library()
        self.refresh_profiles()

    def rename_selected_asset(self) -> None:
        """Rename an asset archive when it is not used by an active link."""
        row = self.asset_table.currentRow()
        if row < 0:
            return
        path = Path(self.asset_table.item(row, 2).text())
        if self._path_is_link_target(path):
            QMessageBox.warning(self, "Renaming is not allowed", "The archive is used by a symbolic link. Remove it from the active profile first.")
            return
        name, accepted = QInputDialog.getText(self, "Rename archive", "New file name (with .zip):", text=path.name)
        if not accepted or not name.strip() or name.strip() == path.name:
            return
        new_name = Path(name.strip()).name
        if Path(new_name).suffix.lower() != ".zip":
            QMessageBox.warning(self, "Invalid name", "Specify a ZIP file name with the .zip extension.")
            return
        destination = path.with_name(new_name)
        if destination.exists():
            QMessageBox.warning(self, "File already exists", "A file with this name already exists.")
            return
        try:
            path.rename(destination)
        except OSError as error:
            QMessageBox.critical(self, "Renaming", str(error))
            return
        self.refresh_assets()

    def delete_selected_asset(self) -> None:
        """Delete an archive after checking usage and requesting confirmation."""
        row = self.asset_table.currentRow()
        if row < 0:
            return
        path = Path(self.asset_table.item(row, 2).text())
        if self._path_is_link_target(path):
            QMessageBox.warning(self, "Deletion is not allowed", "The archive is used by a symbolic link. Remove it from the active profile first.")
            return
        answer = QMessageBox.question(self, "Delete archive", f'Delete "{path.name}" from the library? Profiles containing it will no longer be able to apply this archive.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as error:
            QMessageBox.critical(self, "Deletion", str(error))
            return
        self.refresh_assets()

    def choose_prism_folder(self) -> None:
        """Let the user choose the Prism data directory manually."""
        selected = QFileDialog.getExistingDirectory(
            self, "Choose Prism Launcher data folder", str(self.prism_data_dir or Path.home())
        )
        if not selected:
            return
        selected_path = Path(selected)
        if not is_prism_data_dir(selected_path):
            QMessageBox.warning(self, "Folder not recognized",
                                "The selected folder does not contain an instances subfolder. "
                                "Select the Prism Launcher data root.")
            return
        self.prism_data_dir = selected_path
        self.refresh_instances()

    def create_official_launcher_instance(self) -> None:
        """Create an isolated game directory for the official launcher."""
        candidates = [path for path in default_game_directory_candidates()
                      if path.name.casefold() == ".minecraft"]
        base = candidates[0] if candidates else Path.home() / ".minecraft"
        instances_dir = base / "instances"
        name, accepted = QInputDialog.getText(
            self, "New instance", "Instance name (for example, Fabric-1.21.1):"
        )
        if not accepted:
            return
        name = name.strip()
        if not name or name in {".", ".."} or any(char in name for char in '<>:/\\|?*'):
            QMessageBox.warning(self, "Invalid name", "The name must not contain forbidden Windows path characters.")
            return
        target = instances_dir / name
        if target.exists():
            QMessageBox.warning(self, "Folder already exists", f"The folder already exists:\n{target}")
            return
        try:
            for folder in ("mods", "config", "resourcepacks", "shaderpacks", "saves"):
                (target / folder).mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(self, "Could not create instance", str(error))
            return
        configured_dirs = self.user_data.data.setdefault("game_dirs", [])
        base_key = str(base.resolve(strict=False)).casefold()
        if not any(isinstance(value, str) and str(Path(value).resolve(strict=False)).casefold() == base_key
                   for value in configured_dirs):
            configured_dirs.append(str(base))
        self.user_data.save()
        self.refresh_instances()
        QMessageBox.information(
            self, "Instance created",
            "The instance folder was created. Now open the official Minecraft Launcher, "
            "edit the required installation, and set this path in the Game Directory field:\n\n"
            f"{target}\n\nMods and settings for this installation will be stored separately."
        )

    def add_game_directory(self) -> None:
        """Connect a Minecraft, TLauncher, or Legacy Launcher game folder."""
        selected = QFileDialog.getExistingDirectory(
            self, "Choose a Minecraft game folder", str(Path.home())
        )
        if not selected:
            return
        path = Path(selected)
        if not is_game_directory(path):
            QMessageBox.warning(
                self, "Folder not recognized",
                "The folder does not contain typical Minecraft directories: versions, mods, assets, or libraries. "
                "In Legacy Launcher, select the actual game folder using the launcher's folder button.",
            )
            return
        paths = self.user_data.data.setdefault("game_dirs", [])
        key = str(path.resolve(strict=False)).casefold()
        if any(str(Path(value).resolve(strict=False)).casefold() == key for value in paths if isinstance(value, str)):
            QMessageBox.information(self, "Already connected", "This game folder is already connected.")
            return
        paths.append(str(path))
        self.user_data.save()
        self.refresh_instances()

    def remove_selected_game_directory(self) -> None:
        """Disconnect the selected external folder without deleting its files."""
        row = self.table.currentRow()
        if row < 0:
            return
        path_item = self.table.item(row, 0)
        if path_item is None:
            return
        selected_path = str(Path(path_item.toolTip() or path_item.text()).resolve(strict=False))
        stored = self.user_data.data.setdefault("game_dirs", [])
        selected_resolved = Path(selected_path)
        matching = None
        for value in stored:
            if not isinstance(value, str):
                continue
            registered = Path(value).resolve(strict=False)
            try:
                selected_resolved.relative_to(registered)
                matching = value
                break
            except ValueError:
                if str(registered).casefold() == selected_path.casefold():
                    matching = value
                    break
        if matching is None:
            QMessageBox.information(self, "Disconnect folder", "The selected environment is not connected to a folder that can be disconnected with this button.")
            return
        answer = QMessageBox.question(
            self, "Disconnect folder", "Remove the folder from MineOrganizer? Minecraft files will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        stored.remove(matching)
        self.user_data.save()
        self.refresh_instances()

    def refresh_instances(self) -> None:
        """Scan Prism and automatically discovered TLauncher/Legacy game folders."""
        self.table.setSortingEnabled(False)
        instances: list[PrismInstance] = []
        prism_available = self.prism_data_dir is not None and is_prism_data_dir(self.prism_data_dir)
        if prism_available and self.prism_data_dir is not None:
            instances.extend(scan_instances(self.prism_data_dir))
            prism_label = f"Prism: {self.prism_data_dir}"
        else:
            prism_label = "Prism was not found automatically; choose its data folder manually if needed."

        configured_dirs = self.user_data.data.setdefault("game_dirs", [])
        known_dirs = {
            str(Path(value).resolve(strict=False)).casefold()
            for value in configured_dirs if isinstance(value, str)
        }
        added_default = False
        for candidate in default_game_directory_candidates():
            if not is_game_directory(candidate):
                continue
            candidate_key = str(candidate.resolve(strict=False)).casefold()
            if candidate_key not in known_dirs:
                configured_dirs.append(str(candidate))
                known_dirs.add(candidate_key)
                added_default = True
        if added_default:
            self.user_data.save()

        known_paths = {str(instance.path.resolve(strict=False)).casefold() for instance in instances}
        for value in configured_dirs:
            if not isinstance(value, str):
                continue
            path = Path(value)
            if not is_game_directory(path):
                continue
            key = str(path.resolve(strict=False)).casefold()
            if key in known_paths:
                continue
            discovered = discover_game_environments(path, launcher_for_game_directory(path))
            for instance in discovered:
                instance_key = str(instance.path.resolve(strict=False)).casefold()
                if instance_key not in known_paths:
                    instances.append(instance)
                    known_paths.add(instance_key)

        self.instances = instances
        self.path_label.setText(translate(
            prism_label + "\nAutomatic search: Minecraft Launcher / TLauncher (.minecraft), Legacy Launcher, and Prism. For the official launcher, you can create a separate instance and set its path in the installation settings → Game Directory.",
            self.locale,
        ))
        self.table.setRowCount(len(self.instances))
        for row, instance in enumerate(self.instances):
            values = [instance.launcher, instance.name, instance.minecraft_version,
                      instance.loader, instance.loader_version or "—", instance.status]
            for column, value in enumerate(values):
                sort_value = _sort_key(value) if column in (2, 4) else value.casefold()
                self._set_item(self.table, row, column, value, sort_value, str(instance.path))
        self.table.setSortingEnabled(True)
        self._fit_table_columns(self.table)
        self.status_label.setText(translate(f"Game environments found: {len(self.instances)}", self.locale))
        self.refresh_profile_instance_choices()
        self.refresh_config_instance_choices()
        self.refresh_environment_scan()

    def refresh_profile_instance_choices(self) -> None:
        """Update instances available when creating a profile."""
        if not hasattr(self, "profile_instance_combo"):
            return
        previous = self.profile_instance_combo.currentData()
        previous_id = previous.get("instance_id") if isinstance(previous, dict) else None
        self.profile_instance_combo.clear()
        for instance in self.instances:
            details = {
                "instance_id": instance.instance_id,
                "instance_path": str(instance.path),
                "minecraft_version": instance.minecraft_version,
                "loader": instance.loader,
                "loader_version": instance.loader_version,
            }
            self.profile_instance_combo.addItem(f"{instance.launcher}: {instance.name} — {instance.minecraft_version} / {instance.loader}", details)
        for index in range(self.profile_instance_combo.count()):
            if self.profile_instance_combo.itemData(index).get("instance_id") == previous_id:
                self.profile_instance_combo.setCurrentIndex(index)
                break

    def choose_mods_to_import(self) -> None:
        """Copy selected JAR files into the library."""
        selected, _ = QFileDialog.getOpenFileNames(self, "Choose mods to import",
                                                   str(Path.home()), "Mod files (*.jar)")
        if not selected:
            return
        imported, skipped, errors = import_mods([Path(path) for path in selected], self.library_dir)
        self.refresh_library()
        message = f"Imported: {imported}\nSkipped (duplicates or unsuitable files): {skipped}"
        if errors:
            message += "\n\nErrors:\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "Mod import", message)

    def refresh_library(self) -> None:
        """Scan the library, extract metadata, and show compatibility."""
        self.library_path_label.setText(translate(f"Library: {self.library_dir}", self.locale))
        self.library_table.setSortingEnabled(False)
        cache = get_mod_cache()
        scanned_pairs = cache.scan_mods_parallel(self.library_dir)
        self.mods = [pair[0] for pair in scanned_pairs]
        profile = self._virtualization_profile() if hasattr(self, "virtualization_profile_combo") else None
        metadata_by_hash = {pair[0].sha256: pair[1] for pair in scanned_pairs}
        for mod in self.mods:
            override = self.user_data.minecraft_versions_for(mod.sha256)
            if override:
                metadata_by_hash[mod.sha256].minecraft_ranges = override
                metadata_by_hash[mod.sha256].source = (
                    f"{metadata_by_hash[mod.sha256].source}; User override"
                    if metadata_by_hash[mod.sha256].source else "User override"
                )
        selected_hashes = set(profile.get("enabled_mod_hashes", [])) if profile else set()
        available_mod_ids = {
            metadata_by_hash[digest].mod_id for digest in selected_hashes
            if digest in metadata_by_hash and metadata_by_hash[digest].mod_id
        } if profile else None
        self.library_table.setRowCount(len(self.mods))
        for row, mod in enumerate(self.mods):
            metadata = metadata_by_hash[mod.sha256]
            if profile:
                compatibility, reason = compatibility_for_profile(
                    metadata, str(profile.get("minecraft_version", "")), str(profile.get("loader", "")), available_mod_ids
                )
                target_text = str(profile.get("minecraft_version", "")) + " / " + str(profile.get("loader", ""))
            else:
                compatibility, reason = ("Not checked", "Select a profile on the Virtualization panel to check compatibility.")
                target_text = ""
            tags = ", ".join(self.user_data.tags_for(mod.sha256))
            mc_text = minecraft_version_display(metadata.minecraft_ranges) or "—"
            loader_text = ", ".join(metadata.loader_ids) or "—"
            display_name = (
                f"[{translate(metadata.kind, self.locale)}] {metadata.name or mod.path.stem}"
                if metadata.kind == "Plugin" else (metadata.name or mod.path.stem)
            )
            dependencies_text = ", ".join(metadata.dependencies) or "—"
            values = [display_name, mc_text, loader_text, dependencies_text,
                      compatibility, mod.name, tags or "—"]
            sorts = [display_name.casefold(), mc_text.casefold(), loader_text.casefold(),
                     dependencies_text.casefold(), compatibility.casefold(), mod.name.casefold(), tags.casefold()]
            icon = None
            if metadata.icon_bytes:
                pixmap = QPixmap()
                if pixmap.loadFromData(metadata.icon_bytes):
                    icon = QIcon(pixmap)
            for column, value in enumerate(values):
                self._set_item(self.library_table, row, column, value, sorts[column], str(mod.path), icon=icon if column == 0 else None)
                self.library_table.item(row, column).setData(Qt.ItemDataRole.UserRole + 3, mod.sha256)
                self.library_table.item(row, column).setToolTip(
                    f"{reason}\nMetadata: {metadata.source or 'not found'}\nProfile being checked: {target_text}\nPath: {mod.path}"
                )
        self.library_table.setSortingEnabled(True)
        self._fit_table_columns(self.library_table)

        # Update available versions in filter dropdown
        if hasattr(self, "mod_version_filter"):
            current_ver = self.mod_version_filter.currentText()
            all_versions = sorted({
                ver for meta in metadata_by_hash.values()
                for ver in minecraft_version_choices(meta.minecraft_ranges)
            }, key=_sort_key, reverse=True)
            self.mod_version_filter.blockSignals(True)
            self.mod_version_filter.clear()
            self.mod_version_filter.addItem(translate("Все версии", self.locale))
            for ver in all_versions:
                self.mod_version_filter.addItem(ver)
            idx = self.mod_version_filter.findText(current_ver)
            if idx >= 0:
                self.mod_version_filter.setCurrentIndex(idx)
            self.mod_version_filter.blockSignals(False)

        self._filter_library_table()

        plugin_count = sum(metadata.kind == "Plugin" for metadata in metadata_by_hash.values())
        self.status_label.setText(translate(f"Files in library: {len(self.mods)} (plugins: {plugin_count})", self.locale))
        self.refresh_environment_scan()
        self.preview_selected_profile()

    def check_selected_profile_conflicts(self) -> None:
        """Show conflicts and warnings for the selected profile."""
        profile = self._virtualization_profile()
        if not profile:
            QMessageBox.information(self, "Conflict check", "Select a profile on the Virtualization panel first.")
            return
        selected_hashes = set(profile.get("enabled_mod_hashes", []))
        selected_mods = []
        for mod in self.mods:
            if mod.sha256 not in selected_hashes:
                continue
            metadata = read_mod_metadata(mod.path)
            override = self.user_data.minecraft_versions_for(mod.sha256)
            if override:
                metadata.minecraft_ranges = override
            selected_mods.append((mod.name, metadata))
        conflicts = check_mod_conflicts(
            selected_mods, str(profile.get("minecraft_version", "")), str(profile.get("loader", ""))
        )
        if not conflicts:
            QMessageBox.information(self, "Conflict check", "No conflicts were found in the available metadata. This does not guarantee that the game will launch successfully.")
            return
        lines = [f"[{item.severity}] {item.mod_name}: {item.message}" for item in conflicts]
        title = f"Warnings found: {len(conflicts)}"
        QMessageBox.warning(self, "Conflict check", title + "\n\n" + "\n".join(lines[:40]) + ("\n… list shortened" if len(lines) > 40 else ""))

        # Check for missing dependencies and offer Modrinth lookup
        missing_dep_names = [
            item.mod_name for item in conflicts
            if "requires" in item.message.lower() or "требуется" in item.message.lower() or "missing" in item.message.lower()
        ]
        if missing_dep_names:
            prompt = translate("Открыть каталог Modrinth для поиска недостающих зависимостей?", self.locale)
            reply = QMessageBox.question(
                self,
                "Modrinth",
                prompt,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.open_modrinth_catalog(missing_dep_names[0])

    def edit_selected_mod_tags(self) -> None:
        """Edit tags for the selected file and store them by SHA-256."""
        row = self.library_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Mod tags", "Select a mod in the table first.")
            return
        sha_item = self.library_table.item(row, 0)
        sha256 = sha_item.data(Qt.ItemDataRole.UserRole + 3)
        current = ", ".join(self.user_data.tags_for(sha256))
        tags, accepted = QInputDialog.getText(self, "Mod tags", "Tags separated by commas:", text=current)
        if accepted:
            self.user_data.set_tags(sha256, [tag.strip() for tag in tags.split(",")])
            self.refresh_library()

    def edit_selected_mod_version(self) -> None:
        """Edit or clear the Minecraft-version override for the selected mod."""
        row = self.library_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Minecraft version", "Select a mod in the table first.")
            return
        item = self.library_table.item(row, 0)
        if item is None:
            return
        sha256 = item.data(Qt.ItemDataRole.UserRole + 3)
        mod = next((entry for entry in self.mods if entry.sha256 == sha256), None)
        if mod is None:
            return
        metadata = read_mod_metadata(mod.path)
        current_override = self.user_data.minecraft_versions_for(sha256)
        current = ", ".join(current_override or metadata.minecraft_ranges)
        value, accepted = QInputDialog.getText(
            self,
            "Minecraft version",
            "Minecraft versions separated by commas (empty resets the override):",
            text=current,
        )
        if not accepted:
            return
        values = minecraft_version_entries([value]) if value.strip() else []
        if values and not minecraft_version_choices(values):
            QMessageBox.warning(self, "Minecraft version", "Could not detect the Minecraft version.")
            return
        self.user_data.set_minecraft_versions(sha256, values)
        self.refresh_library()

    def create_profile(self) -> None:
        """Create a profile for the selected game environment."""
        if self.profile_instance_combo.count() == 0:
            QMessageBox.information(self, "Profile creation", "Select a game environment on the Game environments tab first.")
            return
        name, accepted = QInputDialog.getText(self, "New profile", "Profile name:")
        if not accepted or not name.strip():
            return
        dialog = ModSelectionDialog(
            self.mods,
            locale=self.locale,
            version_overrides=self.user_data.data.get("minecraft_version_overrides", {}),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        instance = self.profile_instance_combo.currentData()
        self.user_data.add_profile(name, instance, dialog.selected_hashes())
        self.refresh_profiles()
        self.status_label.setText(translate(
            f'Profile "{name.strip()}" created. Game files were not changed.', self.locale
        ))

    def _profile_row_changed(self, row: int, column: int, previous_row: int, previous_column: int) -> None:
        """Synchronize the selected profile row with the virtualization panel."""
        if row < 0 or not hasattr(self, "virtualization_profile_combo"):
            return
        item = self.profiles_table.item(row, 0)
        if item is None:
            return
        profile_id = item.data(Qt.ItemDataRole.UserRole + 1)
        index = self.virtualization_profile_combo.findData(profile_id)
        if index >= 0:
            self.virtualization_profile_combo.setCurrentIndex(index)

    def _selected_profile(self) -> dict | None:
        """Return the profile selected in the table."""
        row = self.profiles_table.currentRow()
        if row < 0:
            return None
        profile_id = self.profiles_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)
        return next((profile for profile in self.user_data.profiles() if profile.get("id") == profile_id), None)

    def edit_profile_mods(self) -> None:
        """Change the saved mod list for a profile."""
        profile = self._selected_profile()
        if profile is None:
            QMessageBox.information(self, "Profiles", "Select a profile first.")
            return
        selected = set(profile.get("enabled_mod_hashes", []))
        dialog = ModSelectionDialog(
            self.mods,
            selected,
            self.locale,
            self.user_data.data.get("minecraft_version_overrides", {}),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.user_data.update_profile_mods(profile["id"], dialog.selected_hashes())
            self.refresh_profiles()

    def rename_profile(self) -> None:
        """Rename the selected profile."""
        profile = self._selected_profile()
        if profile is None:
            QMessageBox.information(self, "Profiles", "Select a profile first.")
            return
        name, accepted = QInputDialog.getText(self, "Rename profile", "New name:",
                                              text=profile.get("name", ""))
        if accepted and name.strip():
            self.user_data.rename_profile(profile["id"], name)
            self.refresh_profiles()

    def delete_profile(self) -> None:
        """Delete a profile record without affecting mods or the Prism instance."""
        profile = self._selected_profile()
        if profile is None:
            QMessageBox.information(self, "Profiles", "Select a profile first.")
            return
        answer = QMessageBox.question(self, "Delete profile",
                                      f'Delete profile "{profile.get("name", "")}"? Game files will not be changed.')
        if answer == QMessageBox.StandardButton.Yes:
            self.user_data.delete_profile(profile["id"])
            self.refresh_profiles()

    def refresh_profiles(self) -> None:
        """Update the saved profiles table."""
        if not hasattr(self, "profiles_table"):
            return
        self.profiles_table.setSortingEnabled(False)
        profiles = self.user_data.profiles()
        self.profiles_table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            values = [str(profile.get("name", "")), str(profile.get("instance_id", "")),
                      str(profile.get("minecraft_version", "")),
                      " ".join(part for part in [str(profile.get("loader", "")),
                                                 str(profile.get("loader_version", ""))] if part),
                      str(len(profile.get("enabled_mod_hashes", [])))]
            for column, value in enumerate(values):
                sort_value = int(value) if column == 4 and value.isdigit() else _sort_key(value)
                self._set_item(self.profiles_table, row, column, value, sort_value,
                               str(profile.get("instance_path", "")))
            self.profiles_table.item(row, 0).setData(Qt.ItemDataRole.UserRole + 1, profile.get("id"))
        self.profiles_table.setSortingEnabled(True)
        self._fit_table_columns(self.profiles_table)
        self.refresh_virtualization_profiles()

    def _format_size(self, size: int) -> str:
        """Format a file size for display."""
        if size < 1024 * 1024:
            unit = "KB" if self.locale == "en" else "KB"
            return f"{size / 1024:.1f} {unit}"
        unit = "MB" if self.locale == "en" else "MB"
        return f"{size / (1024 * 1024):.2f} {unit}"

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handle drag-and-drop events over child tables."""
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if hasattr(event, "mimeData") and event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
        elif event.type() == QEvent.Type.Drop:
            if hasattr(event, "mimeData") and event.mimeData().hasUrls():
                self._handle_dropped_urls(list(event.mimeData().urls()))
                event.acceptProposedAction()
                return True
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept dragging files into the window."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Accept drag-over file motions."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Import dropped JAR files directly into the mod library."""
        if event.mimeData().hasUrls():
            self._handle_dropped_urls(list(event.mimeData().urls()))
            event.acceptProposedAction()

    def _handle_dropped_urls(self, urls: list[QUrl]) -> None:
        """Process URLs dropped onto the window or tables."""
        jar_paths: list[Path] = []
        for url in urls:
            path = Path(url.toLocalFile()) if url.isLocalFile() else Path(url.toString())
            if path.is_file() and path.suffix.lower() == ".jar":
                jar_paths.append(path)
            elif path.is_dir():
                try:
                    for f in path.rglob("*.jar"):
                        if f.is_file():
                            jar_paths.append(f)
                except OSError:
                    pass

        if not jar_paths:
            return

        imported, skipped, errors = import_mods(jar_paths, self.library_dir)
        self.refresh_library()

        profile = self._virtualization_profile() if hasattr(self, "virtualization_profile_combo") else None
        added_to_profile = 0
        if profile is not None:
            enabled_hashes = set(profile.get("enabled_mod_hashes", []))
            for mod in self.mods:
                if mod.name in [p.name for p in jar_paths] and mod.sha256 not in enabled_hashes:
                    enabled_hashes.add(mod.sha256)
                    added_to_profile += 1
            if added_to_profile > 0:
                profile["enabled_mod_hashes"] = sorted(enabled_hashes)
                self.user_data.save()
                self.refresh_virtualization_profiles()

        if profile is not None and added_to_profile > 0:
            msg = translate("Добавлено модов в профиль «{name}»: {count}.", self.locale).format(
                name=profile.get("name", ""), count=added_to_profile
            )
        else:
            msg = translate(
                "Импортировано: {imported}\nПропущено: {skipped}\n\nПодсказка: Выберите профиль, чтобы перетащенные моды добавились в него автоматически.",
                self.locale,
            ).format(imported=imported, skipped=skipped)
        if errors:
            msg += "\n\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "Mod import", msg)

    def _filter_library_table(self) -> None:
        """Filter library table rows by search text, version, and loader."""
        if not hasattr(self, "mod_search_input"):
            return
        query = self.mod_search_input.text().strip().casefold()
        ver_text = self.mod_version_filter.currentText()
        all_ver_txt = translate("Все версии", self.locale)
        ver_filter = "" if ver_text in ("Все версии", "All versions", all_ver_txt) else ver_text.casefold()

        ldr_text = self.mod_loader_filter.currentText()
        all_ldr_txt = translate("Все загрузчики", self.locale)
        ldr_filter = "" if ldr_text in ("Все загрузчики", "All loaders", all_ldr_txt) else ldr_text.casefold()

        total = self.library_table.rowCount()
        visible = 0
        for row in range(total):
            item_name = self.library_table.item(row, 0)
            item_ver = self.library_table.item(row, 1)
            item_ldr = self.library_table.item(row, 2)
            item_dep = self.library_table.item(row, 3)
            item_file = self.library_table.item(row, 5)
            item_tag = self.library_table.item(row, 6)

            text_pool = " ".join([
                item_name.text() if item_name else "",
                item_ver.text() if item_ver else "",
                item_ldr.text() if item_ldr else "",
                item_dep.text() if item_dep else "",
                item_file.text() if item_file else "",
                item_tag.text() if item_tag else "",
            ]).casefold()

            matches_query = not query or query in text_pool
            matches_ver = not ver_filter or (item_ver and ver_filter in item_ver.text().casefold())
            matches_ldr = not ldr_filter or (item_ldr and ldr_filter in item_ldr.text().casefold())

            show = matches_query and matches_ver and matches_ldr
            self.library_table.setRowHidden(row, not show)
            if show:
                visible += 1

        if query or ver_filter or ldr_filter:
            status_fmt = translate("Отображается: {visible} из {total} модов", self.locale)
            self.library_filter_status.setText(status_fmt.format(visible=visible, total=total))
        else:
            self.library_filter_status.setText("")

    def open_modrinth_catalog(self, initial_query: str = "") -> None:
        """Open the Modrinth catalog dialog for searching and downloading mods."""
        profile = self._virtualization_profile() if hasattr(self, "virtualization_profile_combo") else None
        default_loader = str(profile.get("loader", "")) if profile else ""
        default_version = str(profile.get("minecraft_version", "")) if profile else ""
        dialog = ModrinthSearchDialog(
            library_dir=self.library_dir,
            locale=self.locale,
            default_loader=default_loader,
            default_version=default_version,
            parent=self,
        )
        if initial_query:
            dialog.query_input.setText(initial_query)
            dialog.start_search()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_library()

    def check_library_updates(self) -> None:
        """Check for updates across all mods in the library via Modrinth."""
        if not self.mods:
            QMessageBox.information(self, "Updates", translate("В библиотеке нет модов.", self.locale))
            return
        dialog = ModUpdatesDialog(mods=self.mods, library_dir=self.library_dir, locale=self.locale, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_library()
            self.refresh_virtualization_profiles()

    def check_profile_updates(self) -> None:
        """Check for updates for mods active in the selected profile."""
        profile = self._virtualization_profile() if hasattr(self, "virtualization_profile_combo") else None
        if not profile:
            QMessageBox.information(self, "Updates", translate("Сначала выберите профиль на вкладке «Виртуализация».", self.locale))
            return
        enabled_hashes = set(profile.get("enabled_mod_hashes", []))
        profile_mods = [m for m in self.mods if m.sha256 in enabled_hashes]
        if not profile_mods:
            QMessageBox.information(self, "Updates", translate("В этом профиле не выбрано ни одного мода.", self.locale))
            return
        dialog = ModUpdatesDialog(mods=profile_mods, library_dir=self.library_dir, locale=self.locale, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_library()
            self.refresh_virtualization_profiles()

    def _get_instance_for_path(self, path: Path | None) -> PrismInstance | None:
        """Locate PrismInstance matching the given filesystem path."""
        if not path:
            return None
        for inst in self.instances:
            if inst.path == path or inst.path in path.parents or path in inst.path.parents:
                return inst
        return None

    def analyze_selected_instance_logs(self, target_instance: PrismInstance | None = None) -> None:
        """Open the crash and log analyzer for the selected or given game environment."""
        if target_instance is None:
            path = self._selected_path(self.table)
            target_instance = self._get_instance_for_path(path)
            if target_instance is None and path is not None and path.is_dir():
                dialog = CrashLogAnalyzerDialog(path, instance_name=path.name, locale=self.locale, parent=self)
                dialog.exec()
                return

        if target_instance is None:
            row = self.table.currentRow()
            if 0 <= row < len(self.instances):
                target_instance = self.instances[row]

        if target_instance is None:
            QMessageBox.information(
                self,
                "Crash report & log analyzer",
                translate("Сначала выберите игровое окружение.", self.locale),
            )
            return

        dialog = CrashLogAnalyzerDialog(
            target_instance.path,
            instance_name=target_instance.name,
            locale=self.locale,
            parent=self,
        )
        dialog.exec()

    def analyze_selected_environment_logs(self) -> None:
        """Open analyzer for environment selected on the Environment Check tab."""
        path = self._selected_path(self.environment_table)
        target = self._get_instance_for_path(path)
        if target is not None:
            self.analyze_selected_instance_logs(target)
        elif path is not None and path.is_dir():
            dialog = CrashLogAnalyzerDialog(path, instance_name=path.name, locale=self.locale, parent=self)
            dialog.exec()
        else:
            QMessageBox.information(
                self,
                "Crash report & log analyzer",
                translate("Сначала выберите игровое окружение.", self.locale),
            )

    def analyze_selected_profile_logs(self) -> None:
        """Open analyzer for instance attached to the currently active profile."""
        profile = self._virtualization_profile() if hasattr(self, "virtualization_profile_combo") else None
        if not profile:
            QMessageBox.information(
                self,
                "Crash report & log analyzer",
                translate("Сначала выберите профиль на вкладке «Виртуализация».", self.locale),
            )
            return
        target_path_raw = profile.get("target_path") or profile.get("instance_path")
        if not target_path_raw:
            QMessageBox.information(
                self,
                "Crash report & log analyzer",
                translate("Сначала выберите игровое окружение.", self.locale),
            )
            return
        target_path = Path(str(target_path_raw))
        inst = self._get_instance_for_path(target_path)
        name = inst.name if inst else target_path.name
        dialog = CrashLogAnalyzerDialog(target_path, instance_name=name, locale=self.locale, parent=self)
        dialog.exec()

    def export_selected_profile(self) -> None:
        """Export the selected profile and its mods/configs/assets/saves into a modpack archive."""
        profile = self._selected_profile() or self._virtualization_profile()
        if not profile:
            QMessageBox.information(
                self,
                "Export modpack",
                translate("Сначала выберите профиль на вкладке «Виртуализация».", self.locale),
            )
            return

        has_configs = False
        has_saves = False
        inst_path_str = profile.get("instance_path") or profile.get("target_path")
        if inst_path_str:
            inst_p = Path(inst_path_str)
            has_configs = bool(find_config_dir(inst_p))
            saves_dir = find_saves_dir(inst_p)
            has_saves = bool(saves_dir.is_dir() and any(saves_dir.iterdir()))

        has_rp = bool(profile.get("enabled_resourcepack_hashes"))
        has_sp = bool(profile.get("enabled_shaderpack_hashes"))

        dialog = ExportModpackDialog(
            profile_name=str(profile.get("name", "Modpack")),
            has_configs=has_configs,
            has_rp=has_rp,
            has_sp=has_sp,
            has_saves=has_saves,
            locale=self.locale,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        opts = dialog.options()

        default_filename = f"{profile.get('name', 'Modpack')}.morgpack"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            translate("Экспорт профиля в модпак", self.locale),
            str(Path.home() / default_filename),
            translate("Архивы модпаков (*.morgpack *.zip *.mrpack)", self.locale),
        )
        if not selected:
            return

        target_file = Path(selected)
        res = export_profile_to_modpack(
            profile=profile,
            library_dir=self.library_dir,
            output_archive=target_file,
            include_configs=opts["include_configs"],
            include_resourcepacks=opts["include_resourcepacks"],
            include_shaderpacks=opts["include_shaderpacks"],
            include_saves=opts["include_saves"],
            asset_library_dir=self.asset_library_dir,
            save_library_dir=self.save_library_dir,
        )

        parts = [
            f"{translate('Модов:', self.locale)} {res['mods_count']}",
        ]
        if res.get("configs_count"):
            parts.append(f"{translate('Конфигов:', self.locale)} {res['configs_count']}")
        if res.get("resourcepacks_count"):
            parts.append(f"{translate('Ресурспаков:', self.locale)} {res['resourcepacks_count']}")
        if res.get("shaderpacks_count"):
            parts.append(f"{translate('Шейдеров:', self.locale)} {res['shaderpacks_count']}")
        if res.get("saves_count"):
            parts.append(f"{translate('Миров:', self.locale)} {res['saves_count']}")

        success_msg = translate("Модпак успешно экспортирован:\n", self.locale) + "\n".join(parts)
        QMessageBox.information(self, translate("Экспорт завершён", self.locale), success_msg)

    def import_modpack(self) -> None:
        """Import a complete modpack archive into libraries, environment, and user_data."""
        selected, _ = QFileDialog.getOpenFileName(
            self,
            translate("Импорт сборки…", self.locale),
            str(Path.home()),
            translate("Архивы модпаков (*.morgpack *.zip *.mrpack)", self.locale) + ";;All files (*.*)",
        )
        if not selected:
            return

        archive_path = Path(selected)
        try:
            info = inspect_modpack(archive_path)
        except Exception as err:
            QMessageBox.warning(self, "Import modpack", f"Could not read modpack archive: {err}")
            return

        prompt = translate("Название профиля для импорта:", self.locale)
        profile_name, accepted = QInputDialog.getText(
            self,
            translate("Импорт сборки…", self.locale),
            prompt,
            text=info.get("name") or archive_path.stem,
        )
        if not accepted or not profile_name.strip():
            return

        target_inst = None
        if self.instances:
            inst = self.instances[0]
            target_inst = {
                "instance_id": inst.instance_id,
                "instance_path": str(inst.path),
                "minecraft_version": inst.minecraft_version,
                "loader": inst.loader,
                "loader_version": inst.loader_version,
            }

        res = import_modpack_archive(
            archive_path=archive_path,
            library_dir=self.library_dir,
            user_data=self.user_data,
            target_instance=target_inst,
            profile_name_override=profile_name.strip(),
            extract_configs=True,
            import_resourcepacks=True,
            import_shaderpacks=True,
            import_saves=True,
            asset_library_dir=self.asset_library_dir,
            save_library_dir=self.save_library_dir,
        )

        self.refresh_library()
        self.refresh_profiles()
        self.refresh_virtualization_profiles()
        self.refresh_saves()
        self.refresh_assets()

        parts = [
            f"{translate('Модов:', self.locale)} {res['mods_imported']}",
        ]
        if res.get("resourcepacks_imported"):
            parts.append(f"{translate('Ресурспаков:', self.locale)} {res['resourcepacks_imported']}")
        if res.get("shaderpacks_imported"):
            parts.append(f"{translate('Шейдеров:', self.locale)} {res['shaderpacks_imported']}")
        if res.get("configs_extracted"):
            parts.append(f"{translate('Конфигов:', self.locale)} {res['configs_extracted']}")
        if res.get("saves_imported"):
            parts.append(f"{translate('Миров:', self.locale)} {res['saves_imported']}")

        title_msg = translate("Модпак «{name}» успешно импортирован!\n", self.locale).format(name=profile_name.strip())
        success_msg = title_msg + "\n".join(parts)
        QMessageBox.information(self, translate("Импорт завершён", self.locale), success_msg)
