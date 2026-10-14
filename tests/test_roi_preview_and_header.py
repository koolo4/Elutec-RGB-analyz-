"""Regression tests for the ROI mouse mapping, preview size and app header.

The preview keeps the camera aspect ratio and is centred inside its label, so
mouse coordinates must be shifted by the letterbox offset before being divided
by the scale.  When that was missing the ROI could not be grabbed at all on a
non-matching frame aspect ratio.
"""
from pathlib import Path

from src.utils.helpers import (
    preview_view_geometry, preview_point_to_frame, preview_handle_tolerance,
    MAX_PREVIEW_UPSCALE,
)


def _read(rel):
    return Path(rel).read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Preview geometry / coordinate mapping
# --------------------------------------------------------------------------

def test_view_geometry_keeps_aspect_ratio_and_centres_the_image():
    view = preview_view_geometry(1000, 230, 1920, 1080)
    assert view is not None
    assert view["scale"] == 230 / 1080
    assert view["disp_h"] == 230
    assert view["disp_w"] == round(1920 * (230 / 1080))
    # The image is centred: the horizontal margin is the letterbox offset.
    assert view["offset_x"] == (1000 - view["disp_w"]) / 2
    assert view["offset_y"] == 0
    assert (view["frame_w"], view["frame_h"]) == (1920, 1080)


def test_click_inside_drawn_roi_maps_inside_the_roi():
    """Regression: the ROI must be grabbable where it is painted."""
    view = preview_view_geometry(1000, 230, 3072, 2048)
    roi = (1300, 900, 400, 400)  # x, y, w, h in frame pixels
    roi_cx = roi[0] + roi[2] / 2
    roi_cy = roi[1] + roi[3] / 2

    # Where the operator sees the ROI centre on screen ...
    label_x = view["offset_x"] + roi_cx * view["scale"]
    label_y = view["offset_y"] + roi_cy * view["scale"]

    # ... clicking there must land inside the ROI rectangle.
    point = preview_point_to_frame(view, label_x, label_y)
    assert point is not None
    x, y = point
    assert roi[0] <= x <= roi[0] + roi[2]
    assert roi[1] <= y <= roi[1] + roi[3]

    # The old mapping (dividing without the letterbox offset) missed badly.
    naive_x = int(round(label_x / view["scale"]))
    assert naive_x > view["frame_w"]


def test_round_trip_is_pixel_accurate_for_the_whole_frame():
    view = preview_view_geometry(900, 420, 1920, 1080)
    for fx, fy in ((0, 0), (960, 540), (1919, 1079), (640, 480)):
        label_x = view["offset_x"] + fx * view["scale"]
        label_y = view["offset_y"] + fy * view["scale"]
        mapped = preview_point_to_frame(view, label_x, label_y)
        assert mapped is not None
        assert abs(mapped[0] - fx) <= 1
        assert abs(mapped[1] - fy) <= 1


def test_letterbox_margin_is_rejected_but_clamped_while_dragging():
    view = preview_view_geometry(1000, 230, 1920, 1080)
    assert preview_point_to_frame(view, 5, 115) is None   # left margin
    assert preview_point_to_frame(view, 995, 115) is None  # right margin
    clamped = preview_point_to_frame(view, 5, 115, clamp=True)
    assert clamped == (0, clamped[1])
    assert clamped[0] == 0


def test_preview_fills_the_card_and_allows_small_frames_to_grow():
    # A 1920x1080 frame in a 1000x600 card is limited by the card width, so it
    # fills the width and keeps the aspect ratio.
    view = preview_view_geometry(1000, 600, 1920, 1080)
    assert view["scale"] == 1000 / 1920
    assert view["disp_w"] == 1000
    assert view["offset_x"] == 0
    assert view["offset_y"] == (600 - view["disp_h"]) / 2
    # A small sensor is allowed to fill the card (no more 1.0 ceiling) ...
    small = preview_view_geometry(1000, 600, 640, 480)
    assert small["scale"] == 600 / 480
    assert small["disp_h"] == 600
    assert small["disp_w"] == 800
    # ... but a very small frame cannot be blown up indefinitely.
    tiny = preview_view_geometry(1000, 600, 160, 120)
    assert tiny["scale"] == MAX_PREVIEW_UPSCALE


def test_view_geometry_rejects_invalid_input():
    assert preview_view_geometry(0, 0, 1920, 1080) is None
    assert preview_view_geometry(800, 600, 0, 0) is None
    assert preview_point_to_frame(None, 10, 10) is None


def test_handle_tolerance_scales_with_the_preview_scale():
    # On a 3072-wide sensor shown at ~0.11x, 12 frame pixels are ~1 screen
    # pixel: the tolerance has to grow to stay usable.
    tolerance = preview_handle_tolerance(0.112, 12, 9)
    assert tolerance >= 80
    assert tolerance * 0.112 >= 9
    # ... but it never eats the whole interior of a small ROI.
    bounded = preview_handle_tolerance(0.112, 12, 9, roi_size=200)
    assert bounded <= 50
    # A 1:1 preview keeps the plain minimum.
    assert preview_handle_tolerance(1.0, 12, 9) == 12
    assert preview_handle_tolerance(0, 12, 9) == 12


# --------------------------------------------------------------------------
# Setup window wiring
# --------------------------------------------------------------------------

def _load_preview_mapper():
    """Extract SetupApp._preview_mouse_to_frame and make it runnable."""
    import ast
    import textwrap
    from types import SimpleNamespace

    source = _read("src/gui/setup_app.py")
    tree = ast.parse(source)
    segment = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_preview_mouse_to_frame":
            segment = ast.get_source_segment(source, node)
    assert segment, "SetupApp._preview_mouse_to_frame not found"

    namespace = {"preview_point_to_frame": preview_point_to_frame}
    exec(textwrap.dedent(segment), namespace)
    method = namespace["_preview_mouse_to_frame"]

    class _FakeSetupApp:
        preview_scale = 1.0
        _preview_view = None

    def call(label_x, label_y, view, clamp=False, scale=1.0):
        app = _FakeSetupApp()
        app._preview_view = view
        app.preview_scale = scale
        return method(app, SimpleNamespace(x=label_x, y=label_y), clamp=clamp)

    return call


def test_click_on_the_letterbox_margin_never_starts_a_drag():
    """Regression: a click beside the video must not move the ROI."""
    call = _load_preview_mapper()
    view = preview_view_geometry(1000, 230, 1920, 1080)  # wide letterbox
    assert call(5, 115, view) is None
    assert call(995, 115, view) is None
    # ... but dragging that leaves the image keeps working (clamped).
    assert call(5, 115, view, clamp=True)[0] == 0

    # The ROI is grabbable exactly where it is painted.
    roi = (700, 400, 300, 300)
    label_x = view["offset_x"] + (roi[0] + roi[2] / 2) * view["scale"]
    label_y = view["offset_y"] + (roi[1] + roi[3] / 2) * view["scale"]
    mapped = call(label_x, label_y, view)
    assert mapped is not None
    assert roi[0] <= mapped[0] <= roi[0] + roi[2]
    assert roi[1] <= mapped[1] <= roi[1] + roi[3]

    # Before the first frame is measured the legacy mapping is still used.
    assert call(200, 100, None, scale=0.5) == (400, 200)
    assert call(200, 100, None, scale=0.0) is None


def test_setup_app_uses_the_shared_preview_geometry():
    src = _read("src/gui/setup_app.py")
    assert "preview_view_geometry" in src
    assert "preview_point_to_frame" in src
    assert "preview_handle_tolerance" in src
    # The old hard caps that kept the video small are gone.
    assert "960.0 / max(1, width)" not in src
    assert "540.0 / max(1, height)" not in src
    # The render loop publishes the view used by the mouse handlers.
    assert "_preview_view = view" in src
    assert "self._preview_mouse_to_frame(event)" in src
    assert "self._preview_mouse_to_frame(event, clamp=True)" in src
    # Clicking the empty margin must not start a drag.
    assert "must not start a phantom drag" in src


def test_capture_card_takes_more_room_and_window_starts_maximised():
    src = _read("src/gui/setup_app.py")
    assert "frame_prev = ttk.Frame(content, style='Card.TFrame', padding=10, height=430)" in src
    assert "self.preview_rgb_canvas = tk.Canvas(frame_chart, height=138" in src
    assert "self.root.state('zoomed')" in src


def test_analysis_window_maps_clicks_through_the_live_window_size():
    src = _read("src/analysis/runner.py")
    assert "getWindowImageRect" in src
    assert "sx = frame_w / max(1, window_w)" in src


# --------------------------------------------------------------------------
# Header: project name instead of the old caption, icon-only global actions
# --------------------------------------------------------------------------

def test_header_caption_replaced_by_project_context():
    src = _read("src/gui/setup_app.py")
    assert "РАБОЧАЯ КОНСОЛЬ" not in src
    assert "Визуальный контроль фракционирования" not in src
    assert "self.project_name_btn" in src
    assert "self.project_name_frame" in src
    assert "self.project_pick_btn" in src
    assert "ТЕКУЩИЙ ПРОЕКТ" in src
    # The duplicate project button was removed from the right-hand group.
    assert "self.project_btn" not in src
    # Clicking the project name opens the project manager.
    assert "text='—', command=self.open_project_manager" in src


def test_project_controls_switch_between_picker_and_name():
    src = _read("src/gui/setup_app.py")
    start = src.index("def _update_project_controls")
    block = src[start:src.index("def open_project_manager", start)]
    assert "has_project" in block
    assert "project_name_frame.pack(side='left')" in block
    assert "project_pick_btn.pack(side='left', pady=(6, 0))" in block
    assert "pack_forget()" in block


def test_theme_and_licence_buttons_are_icons():
    src = _read("src/gui/setup_app.py")
    # Icon painters for sun / moon / key, drawn from the active palette.
    for name in ("'sun'", "'moon'", "'key'"):
        assert name in src
    assert "def _header_icon" in src
    assert "def _refresh_header_icons" in src
    assert "self._header_icon('moon' if bool(self.config.get('light_theme', False)) else 'sun')" in src
    # Both buttons are created without a text label.
    assert "self.lic_btn = ttk.Button(header, text='', command=self.open_license_dialog, style='Icon.TButton')" in src
    assert "self.theme_btn = ttk.Button(header, text='', command=self.toggle_theme, style='Icon.TButton')" in src
    # No more long text labels for theme / licence states.
    assert "'Светлая тема'" not in src
    assert "'Тёмная тема'" not in src
    assert "Активировать лицензию" not in src
    # Icon styles exist and tooltips explain the icon-only buttons.
    assert "style.configure('Icon.TButton'" in src
    assert "style.configure('ProjectLink.TButton'" in src
    assert "def _attach_tooltip" in src
    assert "def _theme_tooltip" in src
    assert "def _license_tooltip" in src


def test_licence_icon_colour_tracks_the_licence_status():
    src = _read("src/gui/setup_app.py")
    start = src.index("def _update_license_ui")
    block = src[start:src.index("def open_license_dialog", start)]
    assert "LICENSE_STATUS_LICENSED" in block
    assert "_license_status_text" in block
    assert "self._header_icon('key'" in block
    assert "self.lic_btn.configure(image=icon)" in block


# --------------------------------------------------------------------------
# The icon painters are executed for real (Pillow only, no display needed)
# --------------------------------------------------------------------------

def _load_icon_painters():
    """Extract ``_header_icon`` / ``_hex_to_rgb`` from the app and exec them."""
    import ast
    import textwrap

    import pytest

    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    source = _read("src/gui/setup_app.py")
    tree = ast.parse(source)
    segments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("_header_icon", "_hex_to_rgb"):
            segment = ast.get_source_segment(source, node)
            # ``get_source_segment`` starts at ``def``, so the decorator of the
            # static helper has to be restored by hand.
            if node.name == "_hex_to_rgb":
                segment = "@staticmethod\n" + segment
            segments.append(segment)
    assert len(segments) == 2, segments

    class _FakePhotoImage:
        """Stands in for PIL.ImageTk.PhotoImage and keeps the drawn image."""

        def __init__(self, image=None, **kwargs):
            self.image = image

    namespace = {
        "Image": Image,
        "ImageDraw": ImageDraw,
        "ImageTk": type("ImageTk", (), {"PhotoImage": _FakePhotoImage}),
        "math": __import__("math"),
        "get_palette": lambda light=False: {"text": "#e6edf3", "accent": "#6ea8fe"},
    }
    exec("class Icons:\n" + textwrap.indent("\n\n".join(segments), "    "), namespace)
    return namespace["Icons"]


def _paint(name, color="#e6edf3"):
    import numpy as np

    icons = _load_icon_painters()
    instance = icons()
    instance._ui_palette = {"text": "#e6edf3", "accent": "#6ea8fe"}
    photo = icons._header_icon(instance, name, color=color)
    return np.asarray(photo.image), instance


def test_icon_painters_draw_expected_shapes():
    import numpy as np

    for name in ("sun", "moon", "key"):
        pixels, _ = _paint(name)
        assert pixels.shape[:2] == (18, 18)
        alpha = pixels[:, :, 3]
        # Something is drawn (visible strokes) on a transparent background.
        assert alpha.max() == 255
        assert (alpha == 0).any()

    sun, _ = _paint("sun")
    assert int((sun[:, :, 3] > 0).sum()) > 60
    # The moon is a disc with a transparent bite taken out of it.
    moon, _ = _paint("moon")
    assert moon[9, 9, 3] == 255
    assert moon[2, 12, 3] == 0
    # A different colour produces a different image.
    accented, _ = _paint("key", color="#6ea8fe")
    plain, _ = _paint("key", color="#e6edf3")
    assert not np.array_equal(accented, plain)


def test_icon_painters_cache_images_per_name_and_colour():
    icons = _load_icon_painters()
    instance = icons()
    instance._ui_palette = {"text": "#e6edf3", "accent": "#6ea8fe"}
    first = icons._header_icon(instance, "sun")
    assert icons._header_icon(instance, "sun") is first
    assert icons._header_icon(instance, "sun", color="#6ea8fe") is not first

