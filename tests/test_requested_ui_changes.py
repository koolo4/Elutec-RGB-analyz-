"""Regression tests for the requested UI / streaming changes."""
import time
from pathlib import Path

import numpy as np


def _read(rel):
    return Path(rel).read_text(encoding="utf-8")


def test_right_readout_panel_removed_and_roi_colour_moved_to_history():
    src = _read("src/gui/setup_app.py")
    assert "ROI / READOUT" not in src
    assert "Показатели" not in src
    # Colour swatch is created inside the signal-history frame, above its canvas.
    chart_at = src.index("frame_chart = ttk.Frame")
    colour_at = src.index("self.preview_color_canvas = tk.Canvas(readout", chart_at)
    graph_at = src.index("self.preview_rgb_canvas = tk.Canvas(frame_chart", chart_at)
    assert chart_at < colour_at < graph_at
    assert "Средний цвет ROI" in src[colour_at:graph_at]


def test_network_button_and_source_entry_panel_removed():
    src = _read("src/gui/setup_app.py")
    assert "Сеть / RTSP" not in src
    assert "scan_network_cameras" not in src
    assert "entry_source" not in src
    assert "ИНДЕКС / URL" not in src
    assert "Переподключить" not in src
    assert "text='Применить'" not in src
    # The source is still tracked internally for device/file selection.
    assert "self.source_var" in src
    assert "_current_source_text" in src


def test_parameters_renamed_to_settings():
    setup = _read("src/gui/setup_app.py")
    settings = _read("src/gui/settings_window.py")
    assert "text='Настройки'" in setup
    assert 'self.win.title("Настройки анализа")' in settings
    assert "Параметры" not in setup
    assert "Параметры" not in settings


def test_log10_not_displayed_by_default():
    settings = _read("src/gui/settings_window.py")
    assert '"show_log": False' in settings
    assert '"show_log": True' not in settings
    setup = _read("src/gui/setup_app.py")
    assert "'show_log': False" in setup
    assert 'Log10(B/R):' not in setup  # no log readout on the setup window
    live = _read("src/gui/live_graph.py")
    assert "self.log_btn.setChecked(False)" in live
    assert "self.show_log = False" in live
    runner = _read("src/analysis/runner.py")
    assert "config.get('show_log', False)" in runner


def test_roi_steppers_are_tiny_stacked_on_the_right():
    src = _read("src/gui/setup_app.py")
    assert "stepper.pack(side='right')" in src
    assert "width=1, style='Tiny.TButton'" in src
    plus_at = src.index("ttk.Button(stepper, text='+', width=1")
    minus_at = src.index("ttk.Button(stepper, text='−', width=1")
    assert plus_at < minus_at  # '+' above '-' in one vertical stack
    assert src[plus_at:minus_at].count("side='top'") >= 1


def test_project_window_size_changed():
    src = _read("src/gui/project_window.py")
    assert 'self.win.geometry("1020x560")' in src
    assert "self.win.minsize(880, 460)" in src


def test_preview_keeps_refreshing_while_roi_is_dragged():
    src = _read("src/gui/setup_app.py")
    start = src.index("    def update_preview(self):")
    end = src.index("    def _render_empty_preview_placeholder(self):", start)
    body = src[start:end]
    assert "roi_drag" not in body.split("raw_frame = None")[0]
    # Capture stays in its own thread and only the latest frame is consumed.
    assert "class PreviewWorker" in src
    assert "get_latest_frame" in body


def test_camera_worker_does_not_pause_on_roi_drag():
    src = _read("src/analysis/camera_worker.py")
    assert "_roi_dragging" not in src

    from src.analysis.camera_worker import CameraWorker

    class DummyCap:
        def isOpened(self):
            return True

        def get(self, prop):
            return 25.0

        def set(self, prop, val):
            return True

        def read(self):
            return True, np.full((80, 100, 3), 120, dtype=np.uint8)

    config = {
        "source_is_file": False,
        "roi_x": 10, "roi_y": 10, "roi_w": 40, "roi_h": 40,
        "roi_shape": "rect",
        "analysis_interval_ms": 1,
        "_roi_dragging": True,  # dragging must not stall acquisition/analysis
    }
    worker = CameraWorker(DummyCap(), config, time.time(), save_interval_ms=1)
    worker.start()
    try:
        deadline = time.time() + 2.0
        while time.time() < deadline and (worker.frame_count < 3 or not worker.saved_data):
            time.sleep(0.01)
    finally:
        worker.stop()
    assert worker.frame_count >= 3
    assert worker.latest_frame is not None
    assert len(worker.saved_data) >= 1


def test_resolution_modes_start_at_640x480_and_recommended_is_default():
    from src.utils.helpers import filter_supported_resolutions, recommended_resolution

    modes = filter_supported_resolutions(
        [(320, 240), (640, 480), (1920, 1080), (1280, 720), (640, 480), (3840, 2160)]
    )
    assert modes == [(640, 480), (1280, 720), (1920, 1080), (3840, 2160)]
    assert recommended_resolution(modes) == (1280, 720)
    assert recommended_resolution([(3840, 2160)]) == (3840, 2160)
    assert recommended_resolution([]) == (None, None)


def test_resolution_choice_for_usb_and_detector():
    from src.utils.helpers import choose_resolution

    modes = [(640, 480), (1280, 720), (1920, 1080)]
    assert choose_resolution(modes, "auto") == (1280, 720)  # Auto = recommended
    assert choose_resolution(modes, "1920x1080") == (1920, 1080)
    # A stale choice the device no longer offers falls back to recommended.
    assert choose_resolution(modes, "800x600") == (1280, 720)

    setup = _read("src/gui/setup_app.py")
    # USB cameras and the MiiCam detector both go through the same choice,
    # and the combo always starts from the recommended mode.
    assert "choose_resolution(modes, self.config.get('camera_resolution', 'auto'))" in setup
    assert "_choose_detector_resolution" in setup
    assert "self.config['camera_resolution'] = 'auto'" in setup
    assert "Авто (рекомендуемое)" in setup
