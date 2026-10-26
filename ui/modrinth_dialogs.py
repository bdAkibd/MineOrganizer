"""Dialogs for searching, updating, and downloading mods via Modrinth."""

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from models.mod_file import ModFile
from services.app_identity import app_icon_path
from services.localization import translate
from services.mod_library import file_sha1, file_sha256, import_mods
from services.mod_metadata import read_mod_metadata
from services.modrinth_service import (
    ModrinthSearchResult,
    ModrinthVersion,
    check_mod_updates,
    download_file,
    get_project_versions,
    search_modrinth,
)


class ModSearchWorker(QThread):
    """Background thread to search Modrinth without blocking the UI."""

    results_ready = Signal(list, int)
    error_occurred = Signal(str, int)

    def __init__(self, query: str, loader: str, mc_version: str, seq: int = 0) -> None:
        super().__init__()
        self.query = query
        self.loader = loader
        self.mc_version = mc_version
        self.seq = seq

    def run(self) -> None:
        try:
            results = search_modrinth(
                query=self.query,
                loader=self.loader,
                minecraft_version=self.mc_version,
                limit=30,
            )
            self.results_ready.emit(results, self.seq)
        except Exception as error:
            self.error_occurred.emit(str(error), self.seq)


class ModVersionsWorker(QThread):
    """Background thread to fetch project versions."""

    versions_ready = Signal(list, int)
    error_occurred = Signal(str, int)

    def __init__(self, project_id_or_slug: str, loader: str, mc_version: str, seq: int = 0) -> None:
        super().__init__()
        self.project_id = project_id_or_slug
        self.loader = loader
        self.mc_version = mc_version
        self.seq = seq

    def run(self) -> None:
        try:
            versions = get_project_versions(
                self.project_id,
                loader=self.loader,
                minecraft_version=self.mc_version,
            )
            self.versions_ready.emit(versions, self.seq)
        except Exception as error:
            self.error_occurred.emit(str(error), self.seq)


class ModDownloadWorker(QThread):
    """Background thread to download files."""

    progress = Signal(int, int)
    finished = Signal(bool, str, str)  # success, file_path_or_error, project_slug

    def __init__(self, url: str, destination_path: Path, slug: str = "") -> None:
        super().__init__()
        self.url = url
        self.dest = destination_path
        self.slug = slug

    def run(self) -> None:
        try:
            download_file(self.url, self.dest, progress_callback=self._on_progress)
            self.finished.emit(True, str(self.dest), self.slug)
        except Exception as error:
            self.finished.emit(False, str(error), self.slug)

    def _on_progress(self, current: int, total: int) -> None:
        self.progress.emit(current, total)


class ModUpdatesWorker(QThread):
    """Background thread to check for mod updates."""

    updates_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, sha1_hashes: list[str], game_versions: list[str], loaders: list[str]) -> None:
        super().__init__()
        self.sha1_hashes = sha1_hashes
        self.game_versions = game_versions
        self.loaders = loaders

    def run(self) -> None:
        try:
            updates = check_mod_updates(
                self.sha1_hashes,
                algorithm="sha1",
                game_versions=self.game_versions,
                loaders=self.loaders,
            )
            self.updates_ready.emit(updates)
        except Exception as error:
            self.error_occurred.emit(str(error))


class ModrinthSearchDialog(QDialog):
    """Dialog to search Modrinth, view details, and download mods directly into the library."""

    def __init__(
        self,
        library_dir: Path,
        locale: str = "en",
        default_loader: str = "",
        default_version: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.library_dir = library_dir
        self.locale = locale
        self.selected_result: ModrinthSearchResult | None = None
        self.available_versions: list[ModrinthVersion] = []
        self.downloaded_files: list[Path] = []
        self._running_workers: set[QThread] = set()
        self._search_seq = 0
        self._version_seq = 0

        self.setWindowTitle(translate("Modrinth mod catalog", self.locale))
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.resize(880, 580)

        main_layout = QVBoxLayout(self)

        # Search bar and filters
        search_row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText(translate("Search Modrinth mods…", self.locale))
        self.query_input.returnPressed.connect(self.start_search)
        search_row.addWidget(self.query_input, 3)

        self.loader_filter = QComboBox()
        self.loader_filter.addItems([
            translate("All loaders", self.locale),
            "Fabric",
            "Forge",
            "NeoForge",
            "Quilt",
        ])
        if default_loader:
            idx = self.loader_filter.findText(default_loader, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.loader_filter.setCurrentIndex(idx)
        self.loader_filter.currentIndexChanged.connect(self.start_search)
        search_row.addWidget(self.loader_filter, 1)

        self.version_filter = QComboBox()
        self.version_filter.addItem(translate("All versions", self.locale))
        popular_versions = [
            "1.21.4", "1.21.3", "1.21.1", "1.21",
            "1.20.6", "1.20.4", "1.20.2", "1.20.1",
            "1.19.4", "1.19.2", "1.18.2", "1.16.5", "1.12.2",
        ]
        self.version_filter.addItems(popular_versions)
        if default_version:
            idx = self.version_filter.findText(default_version)
            if idx >= 0:
                self.version_filter.setCurrentIndex(idx)
            else:
                self.version_filter.insertItem(1, default_version)
                self.version_filter.setCurrentIndex(1)
        self.version_filter.currentIndexChanged.connect(self.start_search)
        search_row.addWidget(self.version_filter, 1)

        self.search_button = QPushButton(translate("Search", self.locale))
        self.search_button.clicked.connect(self.start_search)
        search_row.addWidget(self.search_button)
        main_layout.addLayout(search_row)

        # Status / progress
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Splitter: Results list on left, details on right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Search results list
        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_list.currentItemChanged.connect(self._on_result_selected)
        splitter.addWidget(self.results_list)

        # Right: Details & versions panel
        details_panel = QWidget()
        details_layout = QVBoxLayout(details_panel)

        self.mod_title_label = QLabel()
        self.mod_title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.mod_title_label.setWordWrap(True)
        details_layout.addWidget(self.mod_title_label)

        self.mod_desc_browser = QTextBrowser()
        self.mod_desc_browser.setMaximumHeight(130)
        self.mod_desc_browser.setOpenExternalLinks(True)
        details_layout.addWidget(self.mod_desc_browser)

        details_layout.addWidget(QLabel(translate("Available versions:", self.locale)))
        self.versions_combo = QComboBox()
        self.versions_combo.currentIndexChanged.connect(self._on_version_changed)
        details_layout.addWidget(self.versions_combo)

        self.deps_label = QLabel()
        self.deps_label.setStyleSheet("color: #475569; font-size: 12px;")
        self.deps_label.setWordWrap(True)
        details_layout.addWidget(self.deps_label)

        self.download_button = QPushButton(translate("Download mod", self.locale))
        self.download_button.setEnabled(False)
        self.download_button.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.download_button.clicked.connect(self.download_selected_version)
        details_layout.addWidget(self.download_button)

        details_layout.addStretch(1)
        splitter.addWidget(details_panel)
        splitter.setSizes([460, 400])

        main_layout.addWidget(splitter, 1)

        # Bottom buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _track_worker(self, worker: QThread) -> None:
        """Keep a strong reference to running workers to prevent garbage collection crashes."""
        self._running_workers.add(worker)
        worker.finished.connect(lambda: self._running_workers.discard(worker))

    def _cleanup_workers(self) -> None:
        """Gracefully stop and wait for all running workers before destruction."""
        for w in list(self._running_workers):
            if w.isRunning():
                w.requestInterruption()
                w.quit()
        for w in list(self._running_workers):
            if w.isRunning():
                w.wait(1000)
        self._running_workers.clear()

    def reject(self) -> None:
        self._cleanup_workers()
        super().reject()

    def closeEvent(self, event) -> None:
        self._cleanup_workers()
        super().closeEvent(event)

    def _get_current_loader(self) -> str:
        text = self.loader_filter.currentText()
        all_label = translate("All loaders", self.locale)
        return "" if text == all_label else text.lower()

    def _get_current_version(self) -> str:
        text = self.version_filter.currentText()
        all_label = translate("All versions", self.locale)
        return "" if text == all_label else text

    def start_search(self) -> None:
        """Execute a Modrinth search query."""
        query = self.query_input.text().strip()
        if not query:
            return

        self.status_label.setText(translate("Searching Modrinth…", self.locale))
        self.search_button.setEnabled(False)
        self.results_list.clear()

        loader = self._get_current_loader()
        mc_ver = self._get_current_version()

        self._search_seq += 1
        seq = self._search_seq

        worker = ModSearchWorker(query, loader, mc_ver, seq)
        self._track_worker(worker)
        worker.results_ready.connect(self._on_search_completed)
        worker.error_occurred.connect(self._on_search_error)
        worker.start()

    def _on_search_completed(self, results: list[ModrinthSearchResult], seq: int) -> None:
        if seq != self._search_seq:
            return
        self.search_button.setEnabled(True)
        self.status_label.setText(
            translate("Found {count} mods", self.locale).format(count=len(results))
        )
        for item in results:
            downloads_formatted = f"{item.downloads:,}".replace(",", " ")
            text = f"{item.title}  by {item.author}\n  Downloads: {downloads_formatted} | Loaders: {', '.join(item.loaders[:3])}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.results_list.addItem(list_item)

        if results:
            self.results_list.setCurrentRow(0)

    def _on_search_error(self, error: str, seq: int) -> None:
        if seq != self._search_seq:
            return
        self.search_button.setEnabled(True)
        self.status_label.setText(translate("Error connecting to Modrinth", self.locale))

    def _on_result_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if not current:
            self.mod_title_label.setText("")
            self.mod_desc_browser.clear()
            self.versions_combo.clear()
            self.download_button.setEnabled(False)
            return

        result: ModrinthSearchResult = current.data(Qt.ItemDataRole.UserRole)
        self.selected_result = result
        self.mod_title_label.setText(f"{result.title} (by {result.author})")
        self.mod_desc_browser.setPlainText(result.description)
        self.versions_combo.clear()
        self.deps_label.setText("")
        self.download_button.setEnabled(False)

        # Fetch versions in background
        loader = self._get_current_loader()
        mc_ver = self._get_current_version()
        self.status_label.setText(translate("Loading versions…", self.locale))

        self._version_seq += 1
        seq = self._version_seq

        worker = ModVersionsWorker(result.project_id or result.slug, loader, mc_ver, seq)
        self._track_worker(worker)
        worker.versions_ready.connect(self._on_versions_loaded)
        worker.error_occurred.connect(self._on_version_error)
        worker.start()

    def _on_versions_loaded(self, versions: list[ModrinthVersion], seq: int) -> None:
        if seq != self._version_seq:
            return
        self.available_versions = versions
        self.versions_combo.clear()
        self.status_label.setText("")

        if not versions:
            self.versions_combo.addItem(translate("No compatible versions found", self.locale))
            self.download_button.setEnabled(False)
            return

        for ver in versions:
            mc_info = ", ".join(ver.game_versions[:2])
            ldr_info = ", ".join(ver.loaders)
            label = f"{ver.version_number} ({ver.name}) — {mc_info} [{ldr_info}]"
            self.versions_combo.addItem(label, ver)

        self.download_button.setEnabled(True)
        self._on_version_changed(0)

    def _on_version_error(self, error: str, seq: int) -> None:
        if seq != self._version_seq:
            return
        self.status_label.setText(translate("Error loading versions", self.locale))

    def _on_version_changed(self, index: int) -> None:
        ver = self.versions_combo.currentData()
        if not isinstance(ver, ModrinthVersion):
            self.deps_label.setText("")
            return

        req_deps = [dep for dep in ver.dependencies if dep.dependency_type == "required"]
        if req_deps:
            self.deps_label.setText(
                translate("Required dependencies: {count}", self.locale).format(count=len(req_deps))
            )
        else:
            self.deps_label.setText(translate("No required dependencies", self.locale))

    def download_selected_version(self) -> None:
        """Download the selected version file into the library directory."""
        ver = self.versions_combo.currentData()
        if not isinstance(ver, ModrinthVersion) or not ver.files:
            return

        target_file = ver.files[0]
        destination = self.library_dir / target_file.filename

        if destination.exists():
            answer = QMessageBox.question(
                self,
                translate("File exists", self.locale),
                translate("File {name} already exists. Overwrite?", self.locale).format(name=target_file.filename),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.download_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(
            translate("Downloading {name}…", self.locale).format(name=target_file.filename)
        )

        worker = ModDownloadWorker(target_file.url, destination, self.selected_result.slug if self.selected_result else "")
        self._track_worker(worker)
        worker.progress.connect(self._on_download_progress)
        worker.finished.connect(self._on_download_finished)
        worker.start()

    def _on_download_progress(self, current: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setMaximum(0)

    def _on_download_finished(self, success: bool, result_msg: str, slug: str) -> None:
        self.download_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            saved_path = Path(result_msg)
            self.downloaded_files.append(saved_path)
            self.status_label.setText(
                translate("Downloaded: {name}", self.locale).format(name=saved_path.name)
            )
            QMessageBox.information(
                self,
                translate("Download completed", self.locale),
                translate("Mod {name} downloaded into library.", self.locale).format(name=saved_path.name),
            )
        else:
            self.status_label.setText(translate("Download failed", self.locale))
            QMessageBox.warning(
                self,
                translate("Download error", self.locale),
                translate("Could not download file: {error}", self.locale).format(error=result_msg),
            )


class ModUpdatesDialog(QDialog):
    """Dialog showing available updates for library or profile mods, with batch upgrade."""

    def __init__(
        self,
        mods: list[ModFile],
        library_dir: Path,
        locale: str = "en",
        game_version: str = "",
        loader: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mods = mods
        self.library_dir = library_dir
        self.locale = locale
        self.game_version = game_version
        self.loader = loader
        self.updates_found: list[dict[str, Any]] = []
        self.updated_mods_map: dict[str, str] = {}  # old_sha256 -> new_sha256
        self._running_workers: set[QThread] = set()

        self.setWindowTitle(translate("Mod updates", self.locale))
        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.resize(760, 480)

        layout = QVBoxLayout(self)

        self.info_label = QLabel(translate("Checking for updates via Modrinth…", self.locale))
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            translate("Update", self.locale),
            translate("Mod", self.locale),
            translate("Current version", self.locale),
            translate("New version", self.locale),
            translate("File", self.locale),
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        bottom_row = QHBoxLayout()
        self.select_all_btn = QPushButton(translate("Select all", self.locale))
        self.select_all_btn.clicked.connect(self._select_all)
        bottom_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton(translate("Deselect all", self.locale))
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        bottom_row.addWidget(self.deselect_all_btn)

        bottom_row.addStretch(1)

        self.apply_button = QPushButton(translate("Update selected", self.locale))
        self.apply_button.setStyleSheet("font-weight: bold; padding: 7px 14px;")
        self.apply_button.clicked.connect(self.apply_updates)
        self.apply_button.setEnabled(False)
        bottom_row.addWidget(self.apply_button)

        self.close_button = QPushButton(translate("Close", self.locale))
        self.close_button.clicked.connect(self.accept)
        bottom_row.addWidget(self.close_button)

        layout.addLayout(bottom_row)

        self._start_update_check()

    def _track_worker(self, worker: QThread) -> None:
        self._running_workers.add(worker)
        worker.finished.connect(lambda: self._running_workers.discard(worker))

    def _cleanup_workers(self) -> None:
        """Gracefully stop and wait for all running workers before destruction."""
        for w in list(self._running_workers):
            if w.isRunning():
                w.requestInterruption()
                w.quit()
        for w in list(self._running_workers):
            if w.isRunning():
                w.wait(1000)
        self._running_workers.clear()

    def reject(self) -> None:
        self._cleanup_workers()
        super().reject()

    def accept(self) -> None:
        self._cleanup_workers()
        super().accept()

    def closeEvent(self, event) -> None:
        self._cleanup_workers()
        super().closeEvent(event)

    def _start_update_check(self) -> None:
        """Compute SHA-1 hashes and query Modrinth for updates."""
        self.sha1_to_mod: dict[str, ModFile] = {}
        for mod in self.mods:
            try:
                sha1 = file_sha1(mod.path)
                self.sha1_to_mod[sha1] = mod
            except OSError:
                continue

        hashes = list(self.sha1_to_mod.keys())
        game_versions = [self.game_version] if self.game_version else None
        loaders = [self.loader] if self.loader else None

        worker = ModUpdatesWorker(hashes, game_versions or [], loaders or [])
        self._track_worker(worker)
        worker.updates_ready.connect(self._on_updates_ready)
        worker.error_occurred.connect(self._on_error)
        worker.start()

    def _on_updates_ready(self, updates: dict[str, Any]) -> None:
        self.progress_bar.setVisible(False)
        self.table.setRowCount(0)
        self.updates_found.clear()

        for sha1, update_data in updates.items():
            mod = self.sha1_to_mod.get(sha1)
            if not mod or not isinstance(update_data, dict):
                continue

            metadata = read_mod_metadata(mod.path)
            new_ver = str(update_data.get("version_number") or "")
            cur_ver = metadata.version or "—"

            files = update_data.get("files", [])
            primary_file = files[0] if files else {}
            download_url = primary_file.get("url", "")
            filename = primary_file.get("filename", "")

            # Only suggest if version differs
            if cur_ver != new_ver and download_url:
                entry = {
                    "mod": mod,
                    "metadata": metadata,
                    "new_version": new_ver,
                    "new_filename": filename,
                    "download_url": download_url,
                    "old_sha256": mod.sha256,
                }
                self.updates_found.append(entry)

                row = self.table.rowCount()
                self.table.insertRow(row)

                check_item = QTableWidgetItem()
                check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                check_item.setCheckState(Qt.CheckState.Checked)
                self.table.setItem(row, 0, check_item)

                name_item = QTableWidgetItem(metadata.name or mod.name)
                self.table.setItem(row, 1, name_item)

                cur_item = QTableWidgetItem(cur_ver)
                self.table.setItem(row, 2, cur_item)

                new_item = QTableWidgetItem(new_ver)
                new_item.setForeground(Qt.GlobalColor.darkGreen)
                self.table.setItem(row, 3, new_item)

                file_item = QTableWidgetItem(filename)
                self.table.setItem(row, 4, file_item)

        count = len(self.updates_found)
        if count == 0:
            self.info_label.setText(translate("All mods are up to date!", self.locale))
            self.apply_button.setEnabled(False)
        else:
            self.info_label.setText(
                translate("Found {count} update(s) available:", self.locale).format(count=count)
            )
            self.apply_button.setEnabled(True)

    def _on_error(self, error: str) -> None:
        self.progress_bar.setVisible(False)
        self.info_label.setText(translate("Error checking for updates.", self.locale))

    def _select_all(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _deselect_all(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

    def apply_updates(self) -> None:
        """Download chosen updates into the library."""
        selected_entries = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected_entries.append(self.updates_found[row])

        if not selected_entries:
            QMessageBox.information(
                self,
                translate("Updates", self.locale),
                translate("No updates selected.", self.locale),
            )
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_entries))
        self.progress_bar.setValue(0)
        self.apply_button.setEnabled(False)

        updated_count = 0
        for idx, entry in enumerate(selected_entries):
            url = entry["download_url"]
            dest_name = entry["new_filename"] or f"{entry['mod'].name}-updated.jar"
            dest_path = self.library_dir / dest_name
            try:
                download_file(url, dest_path)
                new_sha256 = file_sha256(dest_path)
                self.updated_mods_map[entry["old_sha256"]] = new_sha256
                updated_count += 1
            except Exception:
                pass
            self.progress_bar.setValue(idx + 1)

        self.progress_bar.setVisible(False)
        QMessageBox.information(
            self,
            translate("Updates", self.locale),
            translate("Successfully updated {count} mod(s)!", self.locale).format(count=updated_count),
        )
        self.accept()
