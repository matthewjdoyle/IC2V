"""
Headless smoke tests for the optional PySide6 interface.

Author: M J Doyle
"""

import os

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from ic2v import preferences
from ic2v.gui import ConversionWorker, MainWindow
from ic2v.service import ConversionRequest, ConversionResult, NestedMode


def test_empty_window_paints_without_type_errors(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.queue.viewport().repaint()
    QApplication.processEvents()


def test_initial_paths_populate_independent_jobs(qtbot, images):
    window = MainWindow([str(images)])
    qtbot.addWidget(window)
    assert window.queue.count() == 1
    assert "3 PNG frames" in window.queue.item(0).text()
    assert window.convert_button.isEnabled()


def test_nested_folder_modes_rebuild_the_output_plan(qtbot, images):
    nested = images / "scene2"
    nested.mkdir()
    (nested / "frame1.png").touch()
    (nested / "frame2.png").touch()
    window = MainWindow([str(images)])
    qtbot.addWidget(window)
    assert window.nested_mode.currentData() == NestedMode.DIRECT.value
    assert window.queue.count() == 1
    assert "3 PNG frames" in window.queue.item(0).text()
    window.nested_mode.setCurrentIndex(
        window.nested_mode.findData(NestedMode.FLATTEN.value)
    )
    assert window.queue.count() == 1
    assert "5 PNG frames" in window.queue.item(0).text()
    window.nested_mode.setCurrentIndex(
        window.nested_mode.findData(NestedMode.SEPARATE.value)
    )
    assert window.queue.count() == 2
    assert "images / scene2" in window.queue.item(1).text()
    assert "→  scene2.mp4" in window.queue.item(1).text()


def test_saved_nested_mode_selects_dropdown(qtbot):
    warnings = []
    preferences.save_desktop(
        preferences.DesktopPreferences(nested_mode=NestedMode.SEPARATE.value),
        warnings.append,
    )
    window = MainWindow()
    qtbot.addWidget(window)
    assert not warnings
    assert window.nested_mode.currentData() == NestedMode.SEPARATE.value
    assert "every folder" in window.mode_note.text()


def test_nested_mode_picker_is_locked_during_conversion(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window._set_running(True)
    assert not window.nested_mode.isEnabled()
    window._set_running(False)
    assert window.nested_mode.isEnabled()


def test_empty_sources_do_not_shift_worker_job_indices(qtbot, images, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    window = MainWindow([str(empty), str(images)])
    qtbot.addWidget(window)
    assert window.queue.count() == 2
    assert "No PNG frames found" in window.queue.item(0).text()
    requests = window._requests()
    assert len(requests) == 1
    assert requests[0].input_dir == images


def test_invalid_initial_path_is_rejected(qtbot, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr("ic2v.gui.QMessageBox.warning", lambda *args: warnings.append(args[-1]))
    window = MainWindow([str(tmp_path / "missing")])
    qtbot.addWidget(window)
    qtbot.wait(1)
    assert window.queue.count() == 0
    assert warnings and "Not a folder" in warnings[0]


def test_worker_runs_multiple_collections_sequentially(qtbot, images, tmp_path, monkeypatch):
    second = tmp_path / "second"
    second.mkdir()
    requests = [
        ConversionRequest(images, tmp_path / "first.mp4", ffmpeg="ffmpeg"),
        ConversionRequest(second, tmp_path / "second.mp4", ffmpeg="ffmpeg"),
    ]
    calls = []
    monkeypatch.setattr("ic2v.gui.encoding.check_encoder", lambda *_: None)

    def convert(request, *_args, **_kwargs):
        calls.append(request.input_dir)
        return ConversionResult(request.input_dir, request.output)

    monkeypatch.setattr("ic2v.gui.convert_request", convert)
    worker = ConversionWorker(requests)
    results = []
    worker.job_finished.connect(lambda *result: results.append(result))
    with qtbot.waitSignal(worker.finished, timeout=2000):
        worker.start()
    assert calls == [images, second]
    assert [result[1] for result in results] == ["complete", "complete"]
