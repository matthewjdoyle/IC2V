"""
PySide6 desktop interface and path-based OS integration entry point.

Author: M J Doyle
"""

from __future__ import annotations

from pathlib import Path
import os
import platform
import subprocess
import sys
import threading

from PySide6.QtCore import QThread, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from . import encoding, preferences
from .collection import ConversionCancelled, ConversionError, parse_background, parse_size
from .service import (
    CancellationToken, ConversionRequest, NestedMode, PlannedCollection,
    ProgressEvent, convert_request, desktop_ffmpeg, plan_collections,
)


class ConversionWorker(QThread):
    job_started = Signal(int)
    progress = Signal(int, object)
    job_finished = Signal(int, str, str)

    def __init__(self, requests: list[ConversionRequest],
                 job_indices: list[int] | None = None) -> None:
        super().__init__()
        self.requests = requests
        self.job_indices = job_indices or list(range(len(requests)))
        self._lock = threading.Lock()
        self._token: CancellationToken | None = None
        self._stop_all = False

    def cancel_current(self) -> None:
        with self._lock:
            if self._token is not None:
                self._token.cancel()

    def cancel_all(self) -> None:
        with self._lock:
            self._stop_all = True
            if self._token is not None:
                self._token.cancel()

    def run(self) -> None:
        checked: set[tuple[str, str]] = set()
        for request_index, request in enumerate(self.requests):
            index = self.job_indices[request_index]
            with self._lock:
                if self._stop_all:
                    for pending in self.job_indices[request_index:]:
                        self.job_finished.emit(pending, "cancelled", "Not started")
                    break
                token = CancellationToken()
                self._token = token
            self.job_started.emit(index)
            try:
                executable = request.ffmpeg or desktop_ffmpeg()
                encoder_key = (executable, request.format)
                if encoder_key not in checked:
                    encoding.check_encoder(executable, request.format)
                    checked.add(encoder_key)
                effective = ConversionRequest(
                    input_dir=request.input_dir,
                    output=request.output,
                    format=request.format,
                    fps=request.fps,
                    size=request.size,
                    background=request.background,
                    image_fit=request.image_fit,
                    ffmpeg=executable,
                    paths=request.paths,
                )
                result = convert_request(
                    effective,
                    lambda event, job=index: self.progress.emit(job, event),
                    token,
                    verify_encoder=False,
                )
                details = "\n".join((*result.warnings, str(result.output)))
                self.job_finished.emit(index, "complete", details)
            except ConversionCancelled:
                self.job_finished.emit(index, "cancelled", "Conversion cancelled")
            except Exception as exc:
                self.job_finished.emit(index, "failed", str(exc))
            finally:
                with self._lock:
                    self._token = None


class DropList(QListWidget):
    directories_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setAccessibleName("Planned video jobs")

    def dragEnterEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        if paths and all(path.is_dir() for path in paths):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        self.directories_dropped.emit([url.toLocalFile() for url in event.mimeData().urls()])
        event.acceptProposedAction()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.count():
            return
        painter = QPainter(self.viewport())
        frame = self.viewport().rect().adjusted(56, 54, -56, -88)
        frame.setHeight(min(frame.height(), 116))
        frame.moveCenter(self.viewport().rect().center())
        frame.translate(0, -18)
        painter.setPen(QPen(QColor("#77818c"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(frame)
        painter.setPen(QColor("#f5f7fa"))
        font = painter.font()
        font.setPointSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(frame.adjusted(16, 20, -16, -50), Qt.AlignmentFlag.AlignCenter,
                         "Drop folders here")


class MainWindow(QMainWindow):
    def __init__(self, initial_paths: list[str] | None = None) -> None:
        super().__init__()
        self.worker: ConversionWorker | None = None
        self.sources: list[Path] = []
        self.jobs: list[PlannedCollection] = []
        self.outputs: dict[int, Path] = {}
        self._close_when_done = False
        self._startup_errors: list[str] = []
        self.setWindowTitle("IC2V")
        self.resize(1120, 800)
        self.setMinimumSize(900, 700)
        self.setAcceptDrops(True)
        self._build_ui()
        self._load_preferences()
        self.add_directories(initial_paths or [])

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(30, 22, 30, 24)
        outer.setSpacing(14)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_source_panel())
        splitter.addWidget(self._build_settings_panel())
        splitter.setSizes([610, 450])
        outer.addWidget(splitter, 1)
        outer.addWidget(self._build_footer())

        self.setCentralWidget(root)
        self.setStyleSheet(STYLESHEET)
        self._set_running(False)

    def _build_source_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("sourcePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        title = QLabel("Frame folders")
        title.setObjectName("sourceTitle")
        self.job_summary = QLabel("Σ  0 outputs")
        self.job_summary.setObjectName("jobSummary")
        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(self.job_summary)
        layout.addLayout(heading)
        self.queue = DropList()
        self.queue.setObjectName("queue")
        self.queue.setToolTip("Drop folders here or add them with the button below.")
        self.queue.directories_dropped.connect(self.add_directories)
        self.queue.currentRowChanged.connect(self._selection_changed)
        layout.addWidget(self.queue, 1)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("＋  Add folder")
        self.add_button.setObjectName("sourceButton")
        self.add_button.clicked.connect(self._choose_folders)
        self.remove_button = QPushButton("Remove source")
        self.remove_button.setObjectName("sourceButton")
        self.remove_button.clicked.connect(self._remove_selected)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        return panel

    def _build_settings_panel(self) -> QScrollArea:
        panel = QFrame()
        panel.setObjectName("settingsPanel")
        panel.setMinimumWidth(430)
        panel.setMinimumHeight(450)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        title = QLabel("Nested folders")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.nested_mode = QComboBox()
        self.nested_mode.setAccessibleName("Nested folder handling")
        self.nested_mode.addItem("First level only", NestedMode.DIRECT.value)
        self.nested_mode.addItem("Combine all nested folders", NestedMode.FLATTEN.value)
        self.nested_mode.addItem("One video per folder", NestedMode.SEPARATE.value)
        self.nested_mode.currentIndexChanged.connect(self._mode_changed)
        layout.addWidget(self.nested_mode)
        self.mode_note = QLabel()
        self.mode_note.setObjectName("modeNote")
        self.mode_note.setWordWrap(True)
        layout.addWidget(self.mode_note)
        self._update_mode_note()
        output_title = QLabel("Video settings")
        output_title.setObjectName("sectionTitle")
        layout.addWidget(output_title)
        layout.addLayout(self._build_settings_form())
        self.destination_hint = QLabel("Outputs are saved beside their source folders.")
        self.destination_hint.setWordWrap(True)
        self.destination_hint.setObjectName("destinationHint")
        layout.addWidget(self.destination_hint)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setMinimumWidth(430)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(panel)
        return scroll

    def _build_settings_form(self) -> QFormLayout:
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.format = QComboBox()
        self.format.addItems(["mp4", "mov", "webm", "gif"])
        self.format.currentTextChanged.connect(self._format_changed)
        form.addRow("Format", self.format)
        self.fps = QComboBox()
        self.fps.setEditable(True)
        self.fps.addItems(["6", "12", "24", "30"])
        form.addRow("Frame rate (fps)", self.fps)
        self.auto_size = QCheckBox("Fit the largest frame")
        self.auto_size.toggled.connect(lambda checked: self.size.setEnabled(not checked))
        form.addRow("Canvas", self.auto_size)
        self.size = QLineEdit("1920x1080")
        self.size.setPlaceholderText("WIDTHxHEIGHT")
        form.addRow("Raster size", self.size)
        self.image_fit = QComboBox()
        self.image_fit.addItem("Expand/shrink to fit canvas", "contain")
        self.image_fit.addItem("Shrink to fit canvas", "shrink")
        self.image_fit.addItem("Preserve image size", "preserve")
        form.addRow("Image scaling", self.image_fit)
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self.color_swatch = QLabel()
        self.color_swatch.setObjectName("colorSwatch")
        self.background = QLineEdit("black")
        self.background.setPlaceholderText("black or #ffffff")
        self.background.textChanged.connect(self._update_swatch)
        color_button = QPushButton("Choose")
        color_button.clicked.connect(self._choose_color)
        color_row.addWidget(self.color_swatch)
        color_row.addWidget(self.background, 1)
        color_row.addWidget(color_button)
        form.addRow("Background", color_row)
        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("Beside each source folder")
        self.output_dir.textChanged.connect(self._output_changed)
        output_button = QPushButton("Browse")
        output_button.clicked.connect(self._choose_output)
        output_row.addWidget(self.output_dir, 1)
        output_row.addWidget(output_button)
        form.addRow("Save to", output_row)
        return form

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footer")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(16, 11, 16, 11)
        layout.setSpacing(7)
        row = QHBoxLayout()
        copy = QVBoxLayout()
        copy.setSpacing(1)
        self.status = QLabel("Add a folder containing PNG files.")
        self.status.setObjectName("status")
        self.status_detail = QLabel("")
        self.status_detail.setObjectName("statusDetail")
        copy.addWidget(self.status)
        copy.addWidget(self.status_detail)
        self.reveal_button = QPushButton("Show output")
        self.reveal_button.clicked.connect(self._reveal_output)
        self.reveal_button.setEnabled(False)
        self.reveal_folder_button = QPushButton("Show in folder")
        self.reveal_folder_button.clicked.connect(self._reveal_folder)
        self.reveal_folder_button.setEnabled(False)
        row.addLayout(copy, 1)
        row.addWidget(self.reveal_button)
        row.addWidget(self.reveal_folder_button)
        layout.addLayout(row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        actions = QHBoxLayout()
        self.cancel_current_button = QPushButton("Cancel current")
        self.cancel_current_button.clicked.connect(self._cancel_current)
        self.cancel_all_button = QPushButton("Abort queue")
        self.cancel_all_button.clicked.connect(self._cancel_all)
        self.convert_button = QPushButton("Convert")
        self.convert_button.setObjectName("primary")
        self.convert_button.clicked.connect(self._start)
        actions.addWidget(self.cancel_current_button)
        actions.addWidget(self.cancel_all_button)
        actions.addStretch()
        actions.addWidget(self.convert_button)
        layout.addLayout(actions)
        return footer

    def _load_preferences(self) -> None:
        saved = preferences.read_desktop(self._startup_errors.append)
        self.format.setCurrentText(saved.format)
        self.fps.setCurrentText(f"{saved.fps:g}")
        self.auto_size.setChecked(saved.automatic_size)
        self.size.setText(saved.size)
        self.size.setEnabled(not saved.automatic_size)
        self.background.setText(saved.background)
        mode_index = self.nested_mode.findData(saved.nested_mode)
        self.nested_mode.setCurrentIndex(max(mode_index, 0))
        fit_index = self.image_fit.findData(saved.image_fit)
        self.image_fit.setCurrentIndex(max(fit_index, 0))
        self._update_mode_note()
        self._update_swatch(saved.background)

    def _current_mode(self) -> NestedMode:
        value = self.nested_mode.currentData()
        return NestedMode(value) if value is not None else NestedMode.DIRECT

    def add_directories(self, paths: list[str]) -> None:
        existing = {os.path.normcase(str(path)) for path in self.sources}
        for raw in paths:
            path = Path(raw).resolve()
            key = os.path.normcase(str(path))
            if not path.is_dir():
                self._startup_errors.append(f"Not a folder: {path}")
            elif key not in existing:
                self.sources.append(path)
                existing.add(key)
        self._rebuild_jobs()
        if self._startup_errors:
            errors, self._startup_errors = self._startup_errors, []
            QTimer.singleShot(0, lambda: QMessageBox.warning(
                self, "Some folders were not added", "\n".join(errors)))

    def _choose_folders(self) -> None:
        dialog = QFileDialog(self, "Add frame folders")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if dialog.exec():
            self.add_directories(dialog.selectedFiles())

    def _remove_selected(self) -> None:
        selected_roots = {
            self.jobs[self.queue.row(item)].source_root for item in self.queue.selectedItems()
        }
        self.sources = [source for source in self.sources if source not in selected_roots]
        self._rebuild_jobs()

    def _mode_changed(self, _index: int) -> None:
        self._update_mode_note()
        if hasattr(self, "queue"):
            self._rebuild_jobs()

    def _update_mode_note(self) -> None:
        notes = {
            NestedMode.DIRECT: "Use PNGs directly inside each selected folder.",
            NestedMode.FLATTEN: "Combine PNGs from all nested folders into one video.",
            NestedMode.SEPARATE: "Create one video for every folder that contains PNGs.",
        }
        if hasattr(self, "mode_note"):
            self.mode_note.setText(notes[self._current_mode()])

    def _format_changed(self, _format: str) -> None:
        if hasattr(self, "queue"):
            self._render_jobs()

    def _output_changed(self, _value: str) -> None:
        if hasattr(self, "queue"):
            self._render_jobs()

    def _rebuild_jobs(self) -> None:
        try:
            self.jobs = plan_collections(self.sources, self._current_mode())
        except (ConversionError, OSError) as exc:
            QMessageBox.warning(self, "Could not inspect folders", str(exc))
            self.jobs = []
        self.outputs.clear()
        self._render_jobs()

    def _render_jobs(self) -> None:
        self.queue.clear()
        fmt = self.format.currentText() if hasattr(self, "format") else "mp4"
        valid = 0
        for run, job in enumerate(self.jobs, 1):
            if job.frame_count:
                valid += 1
                detail = f"{job.frame_count} PNG frame{'s' if job.frame_count != 1 else ''}"
            else:
                detail = "No PNG frames found"
            output_name = self._preview_output_name(job, fmt)
            item = QListWidgetItem(
                f"{run:02d}   {job.label}\n{detail}    →  {output_name}"
            )
            item.setToolTip(str(job.input_dir))
            if not job.frame_count:
                item.setForeground(QColor("#d8a65b"))
            self.queue.addItem(item)
        self.job_summary.setText(f"Σ  {valid} output{'s' if valid != 1 else ''}")
        self._refresh_destinations()
        self._update_ready_state()

    def _choose_color(self) -> None:
        initial = QColor(self.background.text())
        color = QColorDialog.getColor(initial if initial.isValid() else QColor("black"), self)
        if color.isValid():
            self.background.setText(color.name())

    def _update_swatch(self, value: str) -> None:
        color = QColor(value)
        shown = color.name() if color.isValid() else "#ffffff"
        self.color_swatch.setStyleSheet(
            f"background: {shown}; border: 1px solid #f5f7fa; border-radius: 0;"
        )

    def _choose_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if selected:
            self.output_dir.setText(selected)

    def _settings(self) -> tuple[float, tuple[int, int] | None, tuple[int, int, int], str]:
        fps = preferences.validate_fps(self.fps.currentText())
        size = None if self.auto_size.isChecked() else parse_size(self.size.text().strip())
        background = parse_background(self.background.text().strip())
        image_fit = self.image_fit.currentData()
        return fps, size, background, image_fit

    def _job_output(self, job: PlannedCollection, fmt: str,
                    output_root: Path | None) -> Path:
        if output_root is not None:
            return output_root / f"{job.output_stem}.{fmt}"
        return job.input_dir.parent / f"{job.input_dir.name}.{fmt}"

    def _preview_output_name(self, job: PlannedCollection, fmt: str) -> str:
        stem = job.output_stem if self.output_dir.text().strip() else job.input_dir.name
        return f"{stem}.{fmt}"

    def _requests(self) -> list[ConversionRequest]:
        fps, size, background, image_fit = self._settings()
        output_root = Path(self.output_dir.text()).resolve() if self.output_dir.text().strip() else None
        if output_root is not None and not output_root.is_dir():
            raise ValueError("The selected output folder does not exist.")
        fmt = self.format.currentText()
        return [
            ConversionRequest(
                job.input_dir, self._job_output(job, fmt, output_root), fmt, fps,
                size, background, image_fit, paths=job.paths,
            )
            for job in self.jobs if job.frame_count
        ]

    def _start(self) -> None:
        try:
            requests = self._requests()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Check video settings", str(exc))
            return
        if not requests:
            return
        saved = preferences.DesktopPreferences(
            self.format.currentText(), float(self.fps.currentText()), self.auto_size.isChecked(),
            self.size.text().strip(), self.background.text().strip(), self._current_mode().value,
            self.image_fit.currentData(),
        )
        warnings: list[str] = []
        preferences.save_desktop(saved, warnings.append)
        self.outputs.clear()
        for index, job in enumerate(self.jobs):
            if job.frame_count:
                self._set_item_status(index, "Queued")
        job_indices = [index for index, job in enumerate(self.jobs) if job.frame_count]
        self.worker = ConversionWorker(requests, job_indices)
        self.worker.job_started.connect(self._job_started)
        self.worker.progress.connect(self._job_progress)
        self.worker.job_finished.connect(self._job_finished)
        self.worker.finished.connect(self._queue_finished)
        self._set_running(True)
        self.status.setText("Starting conversion…")
        self.status_detail.setText(warnings[-1] if warnings else "")
        self.worker.start()

    def _job_started(self, index: int) -> None:
        self.queue.setCurrentRow(index)
        self._set_item_status(index, "Encoding")
        output_name = f"{self.jobs[index].output_stem}.{self.format.currentText()}"
        self.status.setText(f"Creating {output_name}")
        self.status_detail.setText("")
        self.progress_bar.setRange(0, 0)

    def _job_progress(self, index: int, event: ProgressEvent) -> None:
        self.status_detail.setText(event.message)
        if event.total:
            self.progress_bar.setRange(0, event.total)
            self.progress_bar.setValue(event.completed or 0)
        else:
            self.progress_bar.setRange(0, 0)

    def _job_finished(self, index: int, state: str, details: str) -> None:
        labels = {"complete": "Complete", "failed": "Failed", "cancelled": "Cancelled"}
        self._set_item_status(index, labels[state])
        self.queue.item(index).setToolTip(details)
        if state == "complete":
            output = Path(details.splitlines()[-1])
            self.outputs[index] = output
            self.status_detail.setText(f"Saved {output.name}")
            self.reveal_button.setEnabled(True)
            self.reveal_folder_button.setEnabled(True)
        elif state == "failed":
            self.status.setText("One output could not be created")
            self.status_detail.setText(details)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if state == "complete" else 0)

    def _queue_finished(self) -> None:
        self._set_running(False)
        complete = len(self.outputs)
        requested = len([job for job in self.jobs if job.frame_count])
        self.status.setText(f"Created {complete} of {requested} outputs.")
        self.status_detail.setText("Select a completed item to show its folder.")
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()
        if self._close_when_done:
            QTimer.singleShot(0, self.close)

    def _set_item_status(self, index: int, status: str) -> None:
        job = self.jobs[index]
        fmt = self.format.currentText()
        self.queue.item(index).setText(
            f"{index + 1:02d}   {job.label}\n{status}    {job.frame_count} PNG frame"
            f"{'s' if job.frame_count != 1 else ''}    →  {self._preview_output_name(job, fmt)}"
        )

    def _set_running(self, running: bool) -> None:
        for widget in (
            self.add_button, self.remove_button, self.format, self.fps, self.auto_size,
            self.size, self.background, self.image_fit, self.output_dir, self.nested_mode,
            self.convert_button,
        ):
            widget.setEnabled(not running)
        if not running:
            self.size.setEnabled(not self.auto_size.isChecked())
        self.cancel_current_button.setVisible(running)
        self.cancel_all_button.setVisible(running)
        self._update_ready_state()

    def _update_ready_state(self) -> None:
        if self.worker is not None:
            return
        valid = len([job for job in self.jobs if job.frame_count])
        self.convert_button.setEnabled(valid > 0)
        self.remove_button.setEnabled(bool(self.queue.selectedItems()))
        fmt = self.format.currentText() if hasattr(self, "format") else "mp4"
        noun = "GIF" if fmt == "gif" else "video"
        self.convert_button.setText(
            f"Create {noun}" if valid == 1 else f"Create {valid} {noun}s"
        )
        if valid:
            self.status.setText(f"{valid} output{'s' if valid != 1 else ''} ready to create.")
            self.status_detail.setText("")
        elif self.sources:
            self.status.setText("No PNG files found with this nested-folder setting.")
            self.status_detail.setText("")
        else:
            self.status.setText("Add a folder containing PNG files.")
            self.status_detail.setText("")

    def _selection_changed(self, _row: int) -> None:
        self._update_ready_state()
        has_output = self.queue.currentRow() in self.outputs
        self.reveal_button.setEnabled(has_output)
        self.reveal_folder_button.setEnabled(has_output)

    def _refresh_destinations(self, _value: str | None = None) -> None:
        if not hasattr(self, "destination_hint"):
            return
        valid = len([job for job in self.jobs if job.frame_count])
        if self.output_dir.text().strip():
            text = f"All {valid or ''} outputs will be saved in the selected folder."
        elif self._current_mode() == NestedMode.SEPARATE:
            text = "Each output will be saved beside the folder that contains its PNG frames."
        else:
            text = "Each output will be saved beside its selected source folder."
        self.destination_hint.setText(text.replace("All  outputs", "Outputs"))

    def _reveal_output(self) -> None:
        output = self.outputs.get(self.queue.currentRow())
        if output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

    def _reveal_folder(self) -> None:
        output = self.outputs.get(self.queue.currentRow())
        if output:
            if platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", str(output)])
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-R", str(output)])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.parent)))

    def _cancel_current(self) -> None:
        if self.worker:
            self.worker.cancel_current()
            self.status.setText("Cancelling current output…")

    def _cancel_all(self) -> None:
        if self.worker:
            self.worker.cancel_all()
            self.status.setText("Cancelling the queue…")

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            answer = QMessageBox.question(
                self, "Cancel conversions?", "Closing IC2V will cancel the current queue.",
                QMessageBox.StandardButton.Close | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Close:
                self._close_when_done = True
                self.worker.cancel_all()
            event.ignore()
            return
        event.accept()


STYLESHEET = """
QWidget#appRoot { background: #090B0E; color: #F5F7FA; font-family: "Segoe UI Variable", "Segoe UI"; font-size: 10pt; }
QLabel, QCheckBox { background: transparent; }
QLabel#modeNote { color: #AEB7C2; font-size: 8.5pt; padding-bottom: 4px; }
QLabel#sectionTitle { color: #FFFFFF; font-size: 12pt; font-weight: 650; margin-top: 2px; }
QFrame#sourcePanel { background: #0E1115; border: 1px solid #65717D; border-radius: 0; }
QFrame#sourcePanel QLabel#sourceTitle { color: #FFFFFF; font-size: 13pt; font-weight: 650; }
QLabel#jobSummary { background: #080A0D; color: #FFFFFF; border: 1px solid #65717D; border-radius: 0; padding: 4px 8px; font-family: "Cascadia Mono", "Consolas"; font-size: 8.5pt; }
QFrame#settingsPanel { background: #15191E; color: #F5F7FA; border: 1px solid #65717D; border-radius: 0; }
QScrollArea#settingsScroll { background: transparent; border: 0; }
QScrollArea#settingsScroll > QWidget > QWidget { background: transparent; }
QListWidget#queue { background: #080A0D; color: #F5F7FA; border: 1px solid #65717D; border-radius: 0; outline: none; padding: 4px; font-family: "Cascadia Mono", "Consolas"; font-size: 9pt; }
QListWidget#queue::item { border-bottom: 1px solid #363D45; padding: 12px 10px; }
QListWidget#queue::item:selected { background: #F5F7FA; color: #090B0E; }
QLineEdit, QComboBox { background: #080A0D; color: #F5F7FA; border: 1px solid #919CA8; border-radius: 0; padding: 6px 8px; min-height: 18px; selection-background-color: #F5F7FA; selection-color: #090B0E; font-family: "Cascadia Mono", "Consolas"; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #FFFFFF; padding: 5px 7px; }
QLineEdit:disabled, QComboBox:disabled { background: #22282F; color: #7F8994; border-color: #4A535D; }
QComboBox::drop-down { background: #15191E; border: 0; border-left: 1px solid #65717D; border-radius: 0; width: 28px; }
QComboBox QAbstractItemView { background: #080A0D; color: #F5F7FA; border: 1px solid #F5F7FA; border-radius: 0; outline: 0; selection-background-color: #F5F7FA; selection-color: #090B0E; }
QComboBox QAbstractItemView::item { color: #F5F7FA; background: #080A0D; min-height: 28px; padding: 3px 8px; }
QComboBox QAbstractItemView::item:selected { color: #090B0E; background: #F5F7FA; }
QCheckBox { color: #F5F7FA; spacing: 8px; }
QCheckBox::indicator { width: 14px; height: 14px; background: #080A0D; border: 1px solid #919CA8; border-radius: 0; }
QCheckBox::indicator:checked { background: #F5F7FA; border-color: #FFFFFF; }
QCheckBox::indicator:disabled { background: #22282F; border-color: #4A535D; }
QLabel#colorSwatch { min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; }
QLabel#destinationHint { background: #0E1115; color: #C8CFD7; border: 1px solid #4A535D; border-radius: 0; padding: 8px 10px; font-family: "Cascadia Mono", "Consolas"; font-size: 8.5pt; }
QPushButton { background: #15191E; color: #F5F7FA; border: 1px solid #919CA8; border-radius: 0; padding: 7px 13px; }
QPushButton:hover { background: #2A3139; border-color: #FFFFFF; }
QPushButton:focus { border: 2px solid #FFFFFF; padding: 6px 12px; }
QPushButton:disabled { background: #22282F; color: #7F8994; border-color: #4A535D; }
QPushButton#sourceButton { background: #15191E; color: #F5F7FA; border-color: #65717D; font-family: "Cascadia Mono", "Consolas"; font-size: 8.5pt; }
QPushButton#sourceButton:hover { background: #2A3139; border-color: #FFFFFF; }
QPushButton#primary { background: #F5F7FA; color: #090B0E; border-color: #FFFFFF; border-radius: 0; font-weight: 650; padding: 10px 20px; min-width: 142px; }
QPushButton#primary:hover { background: #DDE3E9; }
QPushButton#primary:disabled { background: #343B43; color: #7F8994; border-color: #4A535D; }
QFrame#footer { background: #15191E; border: 1px solid #65717D; border-radius: 0; }
QLabel#status { color: #FFFFFF; font-weight: 650; }
QLabel#statusDetail { color: #AEB7C2; font-family: "Cascadia Mono", "Consolas"; font-size: 8.5pt; }
QProgressBar { background: #343B43; border: 0; border-radius: 0; min-height: 5px; max-height: 5px; }
QProgressBar::chunk { background: #F5F7FA; border-radius: 0; }
QSplitter::handle { width: 12px; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 0; }
QScrollBar::handle:vertical { background: #65717D; border-radius: 0; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #919CA8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #080A0D; color: #F5F7FA; border: 1px solid #F5F7FA; border-radius: 0; padding: 5px; font-family: "Cascadia Mono", "Consolas"; }
"""


def main(paths: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if paths is None else paths)
    if arguments and arguments[0] == "--smoke-test":
        try:
            executable = desktop_ffmpeg()
            for fmt in encoding.ENCODERS:
                encoding.check_encoder(executable, fmt)
            if len(arguments) == 3:
                source, output = Path(arguments[1]), Path(arguments[2])
                convert_request(ConversionRequest(
                    source, output, output.suffix.lower().lstrip("."), 12,
                    ffmpeg=executable,
                ), verify_encoder=False)
            elif len(arguments) != 1:
                raise ValueError("Smoke test expects either no paths or INPUT OUTPUT.")
            return 0
        except (ConversionError, ValueError, OSError) as exc:
            print(f"IC2V smoke test failed: {exc}", file=sys.stderr)
            return 1
    app = QApplication([sys.argv[0], *arguments])
    app.setApplicationName("IC2V")
    app.setOrganizationName("IC2V")

    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ic2v.desktop.app.1")
        except Exception:
            pass

    icon = Path(__file__).with_name("assets") / "ic2v.ico"
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow(arguments)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
