"""
Единая дизайн-система «Элютек».

Один источник цветов, шрифтов и стилей для всех окон приложения:
  * Tkinter / ttk — стартовое окно, настройки, лицензия (apply_ttk_theme);
  * PyQt5 — окно анализа с графиками (qt_stylesheet).

Скруглённые кнопки, поля, карточки и вкладки рисуются картинками (9-slice),
которые генерируются на лету через Pillow под текущую палитру.
Углы картинок прозрачные и показывают цвет `background` стиля, поэтому
у элементов, лежащих на карточке, есть варианты с префиксом «Card.».
"""

import sys
import tkinter as tk
from tkinter import ttk


FONT = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"
FONT_DISPLAY = "Segoe UI Semibold"
FONT_MONO = "Consolas"

PALETTES = {
    "dark": {
        "bg": "#0D0C13",          # фон окна — глубокий фиолетово-чёрный
        "surface": "#15141E",     # инспектор, карточки
        "surface_2": "#1D1B29",   # поля ввода, вторичные кнопки
        "surface_3": "#272436",   # hover
        "border": "#252233",
        "border_strong": "#38344C",
        "text": "#F3F1FA",
        "text_muted": "#A6A1BD",
        "text_faint": "#6E6987",
        "accent": "#8B7CFF",
        "accent_hover": "#A397FF",
        "accent_pressed": "#7464F2",
        "accent_soft": "#221E40",
        "on_accent": "#FFFFFF",
        "grad_a": "#7C6CFF",      # градиент главной кнопки и логотипа
        "grad_b": "#FF6FAE",
        "success": "#4ADE9B",
        "success_soft": "#132A22",
        "warning": "#FFB547",
        "warning_soft": "#2E2412",
        "danger": "#FF6B7A",
        "danger_hover": "#FF8794",
        "danger_soft": "#36161D",
        "chart_r": "#FF6B7A",
        "chart_g": "#4ADE9B",
        "chart_b": "#6AA8FF",
        "chart_grid": "#1F1D2A",
        "chart_axis": "#38344C",
        "video_bg": "#09080E",
    },
    "light": {
        "bg": "#F6F5FB",
        "surface": "#FFFFFF",
        "surface_2": "#F2F0F9",
        "surface_3": "#E8E5F3",
        "border": "#E7E4F0",
        "border_strong": "#D3CEE4",
        "text": "#17151F",
        "text_muted": "#67627C",
        "text_faint": "#A29DB6",
        "accent": "#6B57FF",
        "accent_hover": "#5944F0",
        "accent_pressed": "#4A36D8",
        "accent_soft": "#EEEBFF",
        "on_accent": "#FFFFFF",
        "grad_a": "#6B57FF",
        "grad_b": "#F2549A",
        "success": "#12A06A",
        "success_soft": "#E3F6EE",
        "warning": "#C47A06",
        "warning_soft": "#FDF2DE",
        "danger": "#E23D55",
        "danger_hover": "#C9304A",
        "danger_soft": "#FDE8EC",
        "chart_r": "#E23D55",
        "chart_g": "#12A06A",
        "chart_b": "#2F6BEB",
        "chart_grid": "#EFEDF6",
        "chart_axis": "#D3CEE4",
        "video_bg": "#E9E7F2",
    },
}


def palette(light=False):
    return dict(PALETTES["light" if light else "dark"])


def hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def hex_to_bgr(color):
    r, g, b = hex_to_rgb(color)
    return (b, g, r)


def set_native_titlebar(window, dark=True, caption=None, text=None, border=None):
    """Системный заголовок окна в цветах приложения.

    Тёмный/светлый режим работает с Windows 10 1809+; цвета фона полосы,
    текста и рамки (caption / text / border, '#RRGGBB') — с Windows 11,
    на более старых системах они молча игнорируются.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        if isinstance(window, int):
            hwnd = window
        else:
            window.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        dwm = ctypes.windll.dwmapi
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (новое / старое значение)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        # DWMWA_BORDER_COLOR / CAPTION_COLOR / TEXT_COLOR; COLORREF = 0x00BBGGRR.
        for attr, color in ((34, border), (35, caption), (36, text)):
            if color:
                r, g, b = hex_to_rgb(color)
                ref = ctypes.c_uint(r | (g << 8) | (b << 16))
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ref), ctypes.sizeof(ref))
    except Exception:
        pass


def style_titlebar(window, light=False):
    """Заголовок окна сливается с шапкой приложения (фон = surface)."""
    p = palette(light)
    set_native_titlebar(window, dark=not light, caption=p["surface"], text=p["text"],
                        border=p["border_strong"])


_POPDOWN_LIGHT = {
    # Native Windows look of the dropdown list, kept as is for the light theme.
    "background": "SystemWindow", "foreground": "SystemWindowText",
    "selectBackground": "SystemHighlight", "selectForeground": "SystemHighlightText",
}
_popdown_frame_default = {}


def style_combobox_popdowns(root, light=False):
    """Dropdown lists of ttk.Combobox in the app colours (dark theme only).

    The list is a plain Tk listbox in its own popdown window, so ttk styles do
    not reach it: new popdowns pick the colours up from the option database,
    already created ones are reconfigured directly.
    """
    p = palette(light)
    if light:
        colors = dict(_POPDOWN_LIGHT)
    else:
        colors = {"background": p["surface_2"], "foreground": p["text"],
                  "selectBackground": p["accent"], "selectForeground": p["on_accent"]}
    for option, value in colors.items():
        root.option_add(f"*TCombobox*Listbox.{option}", value)

    style = ttk.Style(root)
    if not _popdown_frame_default:
        _popdown_frame_default["bordercolor"] = style.lookup("ComboboxPopdownFrame", "bordercolor")
    style.configure("ComboboxPopdownFrame",
                    bordercolor=_popdown_frame_default["bordercolor"] if light else p["border_strong"])

    def _walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Combobox):
                try:
                    popdown = child.tk.call("ttk::combobox::PopdownWindow", child)
                    child.tk.call(f"{popdown}.f.l", "configure",
                                  "-background", colors["background"],
                                  "-foreground", colors["foreground"],
                                  "-selectbackground", colors["selectBackground"],
                                  "-selectforeground", colors["selectForeground"])
                except tk.TclError:
                    pass
            _walk(child)

    _walk(root)


def _resolve_fonts(widget):
    """Segoe UI Variable (Windows 11), если установлен, иначе Segoe UI."""
    global FONT, FONT_SEMIBOLD, FONT_DISPLAY
    try:
        from tkinter import font as tkfont
        families = set(tkfont.families(widget))
    except Exception:
        return
    if "Segoe UI Variable Text" in families:
        FONT = "Segoe UI Variable Text"
        FONT_SEMIBOLD = ("Segoe UI Variable Text Semibold"
                         if "Segoe UI Variable Text Semibold" in families else "Segoe UI Semibold")
        FONT_DISPLAY = ("Segoe UI Variable Display Semibold"
                        if "Segoe UI Variable Display Semibold" in families else FONT_SEMIBOLD)


# ---------------------------------------------------------------------------
# Генерация картинок для скруглённых элементов
# ---------------------------------------------------------------------------

_IMAGE_CACHE = {}
_SS = 4  # суперсэмплинг для сглаженных краёв


def _rounded(widget, w, h, r, fill=None, outline=None, width=1.0, inset=0.0):
    from PIL import Image, ImageDraw, ImageTk
    k = _SS
    img = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = [inset * k, inset * k, (w - inset) * k - 1, (h - inset) * k - 1]
    if fill is not None or outline is not None:
        d.rounded_rectangle(box, radius=r * k, fill=fill, outline=outline,
                            width=max(1, int(round(width * k))) if outline else 0)
    return ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS), master=widget)


def _draw_icon(widget, w, h, draw_fn):
    from PIL import Image, ImageDraw, ImageTk
    k = _SS
    img = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(img), k)
    return ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS), master=widget)


def _chevron(widget, w, h, color, direction="down"):
    def fn(d, k):
        cx, cy = w * k / 2, h * k / 2
        s = 3.2 * k
        if direction == "down":
            pts = [(cx - s, cy - s / 2), (cx, cy + s / 2), (cx + s, cy - s / 2)]
        else:
            pts = [(cx - s, cy + s / 2), (cx, cy - s / 2), (cx + s, cy + s / 2)]
        d.line(pts, fill=color, width=int(1.6 * k), joint="curve")
    return _draw_icon(widget, w, h, fn)


def _build_images(widget, p, light):
    key = (str(widget.tk), "light" if light else "dark")
    if key in _IMAGE_CACHE:
        return _IMAGE_CACHE[key]
    W = widget
    s2, s3, border, strong = p["surface_2"], p["surface_3"], p["border"], p["border_strong"]
    acc = p["accent"]
    im = {}

    # Кнопки: 34×34, радиус 9
    def btn(fill, outline=None):
        return _rounded(W, 38, 38, 12, fill=fill, outline=outline)

    im["btn"] = btn(s2, border)
    im["btn_hover"] = btn(s3, strong)
    im["btn_pressed"] = btn(strong, strong)
    im["btn_disabled"] = btn(s2, None)
    im["accent"] = btn(acc)
    im["accent_hover"] = btn(p["accent_hover"])
    im["accent_pressed"] = btn(p["accent_pressed"])
    im["accent_disabled"] = btn(s3)
    im["danger"] = btn(p["danger"])
    im["danger_hover"] = btn(p["danger_hover"])
    im["ghost"] = _rounded(W, 38, 38, 12)
    im["ghost_hover"] = btn(s2)
    im["ghost_pressed"] = btn(s3)

    # Поля ввода
    im["field"] = _rounded(W, 38, 38, 12, fill=s2, outline=border)
    im["field_hover"] = _rounded(W, 38, 38, 12, fill=s2, outline=strong)
    im["field_focus"] = _rounded(W, 38, 38, 12, fill=s2, outline=acc, width=1.6)
    im["field_disabled"] = _rounded(W, 38, 38, 12, fill=p["bg"], outline=border)

    # Карточки и группы
    im["card"] = _rounded(W, 60, 60, 22, fill=p["surface"], outline=border)
    im["group"] = _rounded(W, 44, 44, 14, fill=p["bg"], outline=border)
    im["video"] = _rounded(W, 56, 56, 22, fill=p["video_bg"], outline=border)

    # Вкладки-«таблетки»
    im["tab"] = _rounded(W, 38, 38, 12)
    im["tab_hover"] = _rounded(W, 38, 38, 12, fill=s2)
    im["tab_selected"] = _rounded(W, 38, 38, 12, fill=p["surface"], outline=border)

    # Сегментированный переключатель
    im["seg"] = _rounded(W, 38, 38, 12, fill=s2)
    im["seg_hover"] = _rounded(W, 38, 38, 12, fill=s3)
    im["seg_selected"] = _rounded(W, 38, 38, 12, fill=p["accent_soft"], outline=acc)

    # Чекбоксы (с отступом справа под текст)
    def check(fill, outline, mark):
        def fn(d, k):
            d.rounded_rectangle([1 * k, 1 * k, 17 * k - 1, 17 * k - 1], radius=5 * k,
                                fill=fill, outline=outline, width=int(1.5 * k))
            if mark:
                d.line([(5 * k, 9.2 * k), (7.8 * k, 12 * k), (13 * k, 6.4 * k)],
                       fill=p["on_accent"], width=int(2 * k), joint="curve")
        return _draw_icon(W, 26, 18, fn)

    im["check_off"] = check(s2, strong, False)
    im["check_hover"] = check(s3, acc, False)
    im["check_on"] = check(acc, acc, True)
    im["check_on_hover"] = check(p["accent_hover"], p["accent_hover"], True)
    im["check_disabled"] = check(p["bg"], border, False)

    # Радиокнопки
    def radio(fill, outline, dot):
        def fn(d, k):
            d.ellipse([1 * k, 1 * k, 17 * k - 1, 17 * k - 1], fill=fill, outline=outline, width=int(1.5 * k))
            if dot:
                d.ellipse([6 * k, 6 * k, 12 * k, 12 * k], fill=p["on_accent"])
        return _draw_icon(W, 26, 18, fn)

    im["radio_off"] = radio(s2, strong, False)
    im["radio_hover"] = radio(s3, acc, False)
    im["radio_on"] = radio(acc, acc, True)
    im["radio_disabled"] = radio(p["bg"], border, False)

    # Полосы прокрутки
    im["thumb_v"] = _rounded(W, 8, 28, 4, fill=s3)
    im["thumb_v_hover"] = _rounded(W, 8, 28, 4, fill=strong)
    im["thumb_h"] = _rounded(W, 28, 8, 4, fill=s3)
    im["thumb_h_hover"] = _rounded(W, 28, 8, 4, fill=strong)

    # Стрелки
    im["chev_down"] = _chevron(W, 22, 16, p["text_muted"], "down")
    im["chev_down_hover"] = _chevron(W, 22, 16, p["text"], "down")
    im["spin_up"] = _chevron(W, 18, 11, p["text_muted"], "up")
    im["spin_up_hover"] = _chevron(W, 18, 11, acc, "up")
    im["spin_down"] = _chevron(W, 18, 11, p["text_muted"], "down")
    im["spin_down_hover"] = _chevron(W, 18, 11, acc, "down")

    # Ползунок
    def knob(fill):
        def fn(d, k):
            d.ellipse([1 * k, 1 * k, 19 * k - 1, 19 * k - 1], fill=fill)
            d.ellipse([6 * k, 6 * k, 14 * k, 14 * k], fill=p["surface"])
        return _draw_icon(W, 20, 20, fn)

    im["knob"] = knob(acc)
    im["knob_hover"] = knob(p["accent_hover"])
    im["trough_h"] = _rounded(W, 20, 6, 3, fill=s3)
    im["trough_v"] = _rounded(W, 6, 20, 3, fill=s3)

    # Навигация: дорожка и выбранный сегмент
    im["track"] = _rounded(W, 40, 40, 14, fill=s2)
    im["nav"] = _rounded(W, 34, 34, 11)
    im["nav_hover"] = _rounded(W, 34, 34, 11, fill=s3)
    im["nav_selected"] = _rounded(W, 34, 34, 11, fill=p["surface"] if light else s3,
                                  outline=border if light else strong)

    # Скруглённые «чипы» статуса
    for kind in ("success", "warning", "danger"):
        im[f"chip_{kind}"] = _rounded(W, 26, 26, 13, fill=p[f"{kind}_soft"])
    im["chip_neutral"] = _rounded(W, 26, 26, 13, fill=s2)

    _IMAGE_CACHE[key] = im
    return im


def _element(style, name, default, *states, **kw):
    if name not in style.element_names():
        style.element_create(name, "image", default, *states, **kw)


def _install_elements(style, widget, p, light):
    """Создаёт image-элементы текущей темы и перенастраивает раскладки ttk."""
    m = "light" if light else "dark"
    im = _build_images(widget, p, light)
    E = lambda n: f"Elutek{m.title()}.{n}"  # noqa: E731

    _element(style, E("btn"), im["btn"], ("disabled", im["btn_disabled"]),
             ("pressed", im["btn_pressed"]), ("active", im["btn_hover"]), border=14, padding=0, sticky="nsew")
    _element(style, E("accent"), im["accent"], ("disabled", im["accent_disabled"]),
             ("pressed", im["accent_pressed"]), ("active", im["accent_hover"]), border=14, padding=0, sticky="nsew")
    _element(style, E("danger"), im["danger"], ("pressed", im["danger_hover"]),
             ("active", im["danger_hover"]), border=14, padding=0, sticky="nsew")
    _element(style, E("ghost"), im["ghost"], ("pressed", im["ghost_pressed"]),
             ("active", im["ghost_hover"]), border=14, padding=0, sticky="nsew")
    _element(style, E("field"), im["field"], ("disabled", im["field_disabled"]),
             ("focus", im["field_focus"]), ("hover", im["field_hover"]),
             border=14, padding=(10, 5), sticky="nsew")
    _element(style, E("card"), im["card"], border=24, sticky="nsew")
    _element(style, E("group"), im["group"], border=16, sticky="nsew")
    _element(style, E("video"), im["video"], border=24, sticky="nsew")
    _element(style, E("tab"), im["tab"], ("selected", im["tab_selected"]),
             ("active", im["tab_hover"]), border=14, padding=0, sticky="nsew")
    _element(style, E("seg"), im["seg"], ("selected", im["seg_selected"]),
             ("active", im["seg_hover"]), border=14, padding=0, sticky="nsew")
    _element(style, E("Checkbutton.indicator"), im["check_off"], ("disabled", im["check_disabled"]),
             ("selected", "active", im["check_on_hover"]), ("selected", im["check_on"]),
             ("active", im["check_hover"]), sticky="w")
    _element(style, E("Radiobutton.indicator"), im["radio_off"], ("disabled", im["radio_disabled"]),
             ("selected", im["radio_on"]), ("active", im["radio_hover"]), sticky="w")
    _element(style, E("Vertical.Scrollbar.thumb"), im["thumb_v"],
             ("pressed", im["thumb_v_hover"]), ("active", im["thumb_v_hover"]), border=4, sticky="nsew")
    _element(style, E("Horizontal.Scrollbar.thumb"), im["thumb_h"],
             ("pressed", im["thumb_h_hover"]), ("active", im["thumb_h_hover"]), border=4, sticky="nsew")
    _element(style, E("Combobox.downarrow"), im["chev_down"], ("active", im["chev_down_hover"]), sticky="")
    _element(style, E("Spinbox.uparrow"), im["spin_up"], ("active", im["spin_up_hover"]), sticky="")
    _element(style, E("Spinbox.downarrow"), im["spin_down"], ("active", im["spin_down_hover"]), sticky="")
    _element(style, E("Horizontal.Scale.slider"), im["knob"], ("active", im["knob_hover"]), sticky="")
    _element(style, E("Vertical.Scale.slider"), im["knob"], ("active", im["knob_hover"]), sticky="")
    _element(style, E("Horizontal.Scale.trough"), im["trough_h"], border=3, sticky="ew")
    _element(style, E("Vertical.Scale.trough"), im["trough_v"], border=3, sticky="ns")

    def button_layout(bg_element):
        return [(bg_element, {"sticky": "nswe", "children": [
            ("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})
        ]})]

    style.layout("TButton", button_layout(E("btn")))
    style.layout("Accent.TButton", button_layout(E("accent")))
    style.layout("Primary.TButton", button_layout(E("accent")))
    style.layout("Danger.TButton", button_layout(E("danger")))
    style.layout("Ghost.TButton", button_layout(E("ghost")))
    style.layout("Quiet.TButton", button_layout(E("ghost")))
    style.layout("Seg.TRadiobutton", [(E("seg"), {"sticky": "nswe", "children": [
        ("Radiobutton.padding", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})
    ]})])

    field = lambda name, children: [(E("field"), {"sticky": "nswe", "children": children})]  # noqa: E731
    style.layout("TEntry", field("Entry", [
        ("Entry.padding", {"sticky": "nswe", "children": [("Entry.textarea", {"sticky": "nswe"})]})
    ]))
    style.layout("TCombobox", field("Combobox", [
        (E("Combobox.downarrow"), {"side": "right", "sticky": "ns"}),
        ("Combobox.padding", {"sticky": "nswe", "children": [("Combobox.textarea", {"sticky": "nswe"})]}),
    ]))
    style.layout("TSpinbox", field("Spinbox", [
        ("null", {"side": "right", "sticky": "", "children": [
            (E("Spinbox.uparrow"), {"side": "top", "sticky": "e"}),
            (E("Spinbox.downarrow"), {"side": "bottom", "sticky": "e"}),
        ]}),
        ("Spinbox.padding", {"sticky": "nswe", "children": [("Spinbox.textarea", {"sticky": "nswe"})]}),
    ]))

    style.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
        (E("Checkbutton.indicator"), {"side": "left", "sticky": ""}),
        ("Checkbutton.label", {"side": "left", "sticky": "nswe"}),
    ]})])
    style.layout("TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [
        (E("Radiobutton.indicator"), {"side": "left", "sticky": ""}),
        ("Radiobutton.label", {"side": "left", "sticky": "nswe"}),
    ]})])

    for kind in ("success", "warning", "danger", "neutral"):
        _element(style, E(f"chip_{kind}"), im[f"chip_{kind}"], border=12, padding=0, sticky="nsew")
        style.layout(f"Chip{kind.title()}.TLabel", [(E(f"chip_{kind}"), {"sticky": "nswe", "children": [
            ("Label.padding", {"sticky": "nswe", "children": [("Label.label", {"sticky": "nswe"})]})
        ]})])

    _element(style, E("track"), im["track"], border=15, sticky="nsew")
    _element(style, E("nav"), im["nav"], ("selected", im["nav_selected"]),
             ("active", im["nav_hover"]), border=12, padding=0, sticky="nsew")
    style.layout("Track.TFrame", [(E("track"), {"sticky": "nswe"})])
    style.layout("Nav.TRadiobutton", [(E("nav"), {"sticky": "nswe", "children": [
        ("Radiobutton.padding", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})
    ]})])
    style.layout("Tile.TButton", button_layout(E("btn")))

    style.layout("Card.TFrame", [(E("card"), {"sticky": "nswe"})])
    style.layout("Field.TFrame", [(E("field"), {"sticky": "nswe"})])
    style.layout("Video.TFrame", [(E("video"), {"sticky": "nswe"})])
    style.layout("TLabelframe", [(E("group"), {"sticky": "nswe"})])
    style.layout("TNotebook", [(E("group"), {"sticky": "nswe"})])
    style.layout("TNotebook.Tab", [(E("tab"), {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
            ("Notebook.label", {"side": "top", "sticky": ""})
        ]})
    ]})])

    style.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        (E("Vertical.Scrollbar.thumb"), {"expand": "1", "sticky": "nswe"})
    ]})])
    style.layout("Horizontal.TScrollbar", [("Horizontal.Scrollbar.trough", {"sticky": "we", "children": [
        (E("Horizontal.Scrollbar.thumb"), {"expand": "1", "sticky": "nswe"})
    ]})])
    style.layout("Horizontal.TScale", [(E("Horizontal.Scale.trough"), {"sticky": "ew", "children": [
        (E("Horizontal.Scale.slider"), {"side": "left", "sticky": ""})
    ]})])
    style.layout("Vertical.TScale", [(E("Vertical.Scale.trough"), {"sticky": "ns", "children": [
        (E("Vertical.Scale.slider"), {"side": "top", "sticky": ""})
    ]})])


# ---------------------------------------------------------------------------
# Tkinter / ttk
# ---------------------------------------------------------------------------

def apply_ttk_theme(widget, light=False):
    """Настраивает все ttk-стили. Возвращает палитру для нативных tk-виджетов."""
    p = palette(light)
    style = ttk.Style(widget)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    _resolve_fonts(widget)

    bg, surface, s2, s3 = p["bg"], p["surface"], p["surface_2"], p["surface_3"]
    text, muted, faint = p["text"], p["text_muted"], p["text_faint"]
    border, strong = p["border"], p["border_strong"]
    accent = p["accent"]

    style.configure(
        ".", background=bg, foreground=text, font=(FONT, 10),
        bordercolor=border, lightcolor=bg, darkcolor=bg, troughcolor=bg,
        focuscolor=accent, selectbackground=accent, selectforeground=p["on_accent"],
        insertcolor=text, fieldbackground=s2, relief="flat",
    )

    try:
        _install_elements(style, widget, p, light)
    except Exception:
        pass

    # --- Контейнеры --------------------------------------------------------
    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=bg)          # углы карточки — цвет окна
    style.configure("CardFlat.TFrame", background=surface)
    style.configure("Sidebar.TFrame", background=surface)
    style.configure("Video.TFrame", background=bg)
    style.configure("Divider.TFrame", background=border)

    style.configure("TLabelframe", background=bg, padding=(14, 10, 14, 12),
                    labeloutside=True, labelmargins=(4, 0, 0, 6))
    style.configure("TLabelframe.Label", background=bg, foreground=muted, font=(FONT_SEMIBOLD, 10))

    # --- Текст ---------------------------------------------------------------
    style.configure("TLabel", background=bg, foreground=text)
    style.configure("Muted.TLabel", background=bg, foreground=muted)
    style.configure("Title.TLabel", background=bg, foreground=text, font=(FONT_DISPLAY, 20))
    style.configure("Subtitle.TLabel", background=bg, foreground=muted, font=(FONT, 10))
    style.configure("PageTitle.TLabel", background=bg, foreground=text, font=(FONT_DISPLAY, 16))

    style.configure("Card.TLabel", background=surface, foreground=text)
    style.configure("CardMuted.TLabel", background=surface, foreground=muted, font=(FONT, 9))
    style.configure("CardTitle.TLabel", background=surface, foreground=text, font=(FONT_SEMIBOLD, 11))
    style.configure("CardSection.TLabel", background=surface, foreground=faint, font=(FONT_SEMIBOLD, 8))
    style.configure("CardMono.TLabel", background=surface, foreground=muted, font=(FONT_MONO, 9))
    style.configure("Brand.TLabel", background=surface, foreground=text, font=(FONT_DISPLAY, 15))
    style.configure("BrandSub.TLabel", background=surface, foreground=muted, font=(FONT, 9))
    style.configure("Logo.TLabel", background=accent, foreground=p["on_accent"],
                    font=(FONT_DISPLAY, 15), anchor="center", padding=(11, 3))

    for kind in ("success", "warning", "danger", "neutral"):
        style.configure(f"Chip{kind.title()}.TLabel", background=bg,
                        foreground=muted if kind == "neutral" else p[kind],
                        font=(FONT_SEMIBOLD, 9), padding=(14, 6))
        style.configure(f"Card.Chip{kind.title()}.TLabel", background=surface)
    style.configure("Field.TFrame", background=surface)
    style.configure("Track.TFrame", background=surface)
    style.configure("Nav.TRadiobutton", background=s2, foreground=muted, padding=(10, 8),
                    font=(FONT_SEMIBOLD, 9), anchor="center")
    style.map("Nav.TRadiobutton", foreground=[("selected", text), ("active", text)], background=[])
    style.configure("Tile.TButton", background=surface, foreground=text, padding=(10, 14),
                    font=(FONT_SEMIBOLD, 10), anchor="center", justify="center")
    style.configure("Stage.TLabel", background=bg, foreground=muted, font=(FONT, 9))
    style.configure("StageStrong.TLabel", background=bg, foreground=text, font=(FONT_SEMIBOLD, 10))
    style.configure("Wordmark.TLabel", background=bg, foreground=text, font=(FONT_DISPLAY, 16))
    style.configure("WordmarkSub.TLabel", background=bg, foreground=faint, font=(FONT_SEMIBOLD, 9))
    style.configure("Orb.TLabel", background=bg, padding=0, borderwidth=0)
    style.configure("Hint.TLabel", background=surface, foreground=faint, font=(FONT, 9))

    style.configure("PreviewArea.TLabel", background=p["video_bg"], anchor="center",
                    borderwidth=0, padding=0)

    # --- Кнопки -------------------------------------------------------------
    style.configure("TButton", background=bg, foreground=text, padding=(14, 7),
                    font=(FONT_SEMIBOLD, 9), anchor="center", borderwidth=0)
    style.map("TButton", foreground=[("disabled", faint)], background=[])
    style.configure("Accent.TButton", foreground=p["on_accent"], font=(FONT_SEMIBOLD, 10), padding=(16, 8))
    style.map("Accent.TButton", foreground=[("disabled", faint)])
    style.configure("Primary.TButton", foreground=p["on_accent"], font=(FONT_SEMIBOLD, 12), padding=(18, 13))
    style.map("Primary.TButton", foreground=[("disabled", faint)])
    style.configure("Danger.TButton", foreground="#FFFFFF", font=(FONT_SEMIBOLD, 10), padding=(16, 8))
    style.configure("Ghost.TButton", foreground=muted, padding=(12, 7))
    style.map("Ghost.TButton", foreground=[("active", text)])
    style.configure("Quiet.TButton", foreground=muted, padding=(12, 7))
    style.map("Quiet.TButton", foreground=[("active", text)])
    style.configure("Icon.TButton", padding=(4, 3), font=(FONT_SEMIBOLD, 11))

    # Варианты для элементов на карточках/боковой панели (углы цвета surface).
    for name in ("TButton", "Accent.TButton", "Primary.TButton", "Danger.TButton",
                 "Ghost.TButton", "Quiet.TButton", "Icon.TButton",
                 "TEntry", "TCombobox", "TSpinbox", "TCheckbutton", "TRadiobutton",
                 "Seg.TRadiobutton", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(f"Card.{name}", background=surface)
    style.configure("Card.Vertical.TScrollbar", troughcolor=surface)
    style.configure("Card.Horizontal.TScrollbar", troughcolor=surface)
    style.configure("Card.Icon.TButton", padding=(4, 3), font=(FONT_SEMIBOLD, 11))

    # --- Поля ввода ------------------------------------------------------------
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, background=bg, fieldbackground=s2, foreground=text,
                        insertcolor=text, insertwidth=1, padding=(2, 2),
                        selectbackground=accent, selectforeground=p["on_accent"])
        style.map(name, foreground=[("disabled", faint)], fieldbackground=[],
                  selectbackground=[("!focus", s3)], selectforeground=[("!focus", text)])
    style.map("TCombobox", selectbackground=[("readonly", s2)], selectforeground=[("readonly", text)],
              foreground=[("disabled", faint)])
    # Углы полей в состоянии readonly/disabled иначе берут цвет из темы clam.
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.map(name, background=[("readonly", bg), ("disabled", bg)])
        style.map(f"Card.{name}", background=[("readonly", surface), ("disabled", surface)])

    root = widget.winfo_toplevel()
    for pattern, value in (
        ("*TCombobox*Listbox.background", surface),
        ("*TCombobox*Listbox.foreground", text),
        ("*TCombobox*Listbox.selectBackground", p["accent_soft"]),
        ("*TCombobox*Listbox.selectForeground", text),
        ("*TCombobox*Listbox.font", (FONT, 10)),
        ("*TCombobox*Listbox.borderWidth", 0),
        ("*Listbox.background", s2),
        ("*Listbox.foreground", text),
        ("*Listbox.selectBackground", p["accent_soft"]),
        ("*Listbox.selectForeground", text),
        ("*Listbox.highlightThickness", 0),
        ("*Listbox.borderWidth", 0),
        ("*Listbox.relief", "flat"),
        ("*Text.background", s2),
        ("*Text.foreground", text),
        ("*Text.insertBackground", text),
        ("*Text.selectBackground", accent),
        ("*Menu.background", surface),
        ("*Menu.foreground", text),
        ("*Menu.activeBackground", p["accent_soft"]),
        ("*Menu.activeForeground", text),
        ("*Toplevel.background", bg),
    ):
        try:
            root.option_add(pattern, value)
        except Exception:
            pass

    # --- Флажки и переключатели ---------------------------------------------
    for name, back in (("TCheckbutton", bg), ("TRadiobutton", bg),
                       ("Card.TCheckbutton", surface), ("Card.TRadiobutton", surface)):
        style.configure(name, background=back, foreground=text, padding=(0, 4), focuscolor=back)
        style.map(name, background=[], foreground=[("disabled", faint)])
    style.configure("Seg.TRadiobutton", background=bg, foreground=muted, padding=(12, 7),
                    font=(FONT_SEMIBOLD, 9), anchor="center")
    style.map("Seg.TRadiobutton", foreground=[("selected", accent), ("active", text)], background=[])
    style.configure("Card.Seg.TRadiobutton", background=surface)

    # --- Вкладки ------------------------------------------------------------
    style.configure("TNotebook", background=bg, padding=(6, 6, 6, 6), tabmargins=(0, 0, 0, 10))
    style.configure("TNotebook.Tab", background=bg, foreground=muted, padding=(14, 8),
                    font=(FONT_SEMIBOLD, 9))
    style.map("TNotebook.Tab", foreground=[("selected", text), ("active", text)],
              background=[], expand=[])

    # --- Прокрутка и ползунки ------------------------------------------------
    for name in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(name, troughcolor=bg, background=bg, bordercolor=bg, width=10, arrowsize=10)
    style.configure("Horizontal.TScale", background=bg)
    style.configure("Vertical.TScale", background=bg)
    style.configure("Horizontal.TProgressbar", background=accent, troughcolor=s2,
                    bordercolor=s2, lightcolor=accent, darkcolor=accent, thickness=6)

    # --- Таблицы -------------------------------------------------------------
    style.configure("Treeview", background=s2, fieldbackground=s2, foreground=text,
                    bordercolor=border, lightcolor=s2, darkcolor=s2, rowheight=30,
                    font=(FONT, 9), borderwidth=0)
    style.map("Treeview", background=[("selected", p["accent_soft"])], foreground=[("selected", text)])
    style.configure("Treeview.Heading", background=bg, foreground=muted,
                    bordercolor=bg, lightcolor=bg, darkcolor=bg,
                    relief="flat", padding=(8, 7), font=(FONT_SEMIBOLD, 9))
    style.map("Treeview.Heading", background=[("active", s2)], foreground=[("active", text)])

    style.configure("TSeparator", background=border)

    try:
        widget.configure(bg=bg)
    except Exception:
        pass
    try:
        set_native_titlebar(widget.winfo_toplevel(), dark=not light)
    except Exception:
        pass
    return p


def style_listbox(listbox, p, on_surface=False):
    try:
        listbox.configure(
            bg=p["surface_2"], fg=p["text"], selectbackground=p["accent_soft"],
            selectforeground=p["text"], highlightthickness=0, borderwidth=0,
            relief="flat", activestyle="none", font=(FONT, 10),
        )
    except Exception:
        pass


def style_text(text_widget, p):
    try:
        text_widget.configure(
            bg=p["surface_2"], fg=p["text"], insertbackground=p["text"],
            selectbackground=p["accent"], selectforeground=p["on_accent"],
            highlightthickness=1, highlightbackground=p["border"], highlightcolor=p["accent"],
            borderwidth=0, relief="flat",
        )
    except Exception:
        pass


def card(parent, title=None, subtitle=None, padding=18):
    """Скруглённая карточка с заголовком. Содержимое кладётся в `.body`."""
    outer = ttk.Frame(parent, style="Card.TFrame", padding=padding)
    if title:
        head = ttk.Frame(outer, style="CardFlat.TFrame")
        head.pack(fill="x", pady=(0, 12))
        ttk.Label(head, text=title, style="CardTitle.TLabel").pack(anchor="w")
        if subtitle:
            sub = ttk.Label(head, text=subtitle, style="CardMuted.TLabel", wraplength=320, justify="left")
            sub.pack(anchor="w", pady=(2, 0))
            head.bind("<Configure>", lambda e, lbl=sub: lbl.configure(wraplength=max(120, e.width - 4)))
    body = ttk.Frame(outer, style="CardFlat.TFrame")
    body.pack(fill="both", expand=True)
    outer.body = body
    return outer


# ---------------------------------------------------------------------------
# PyQt5
# ---------------------------------------------------------------------------

def qt_stylesheet(light=False):
    p = palette(light)
    return f"""
    QWidget {{ font-family: 'Segoe UI Variable Text', 'Segoe UI'; font-size: 9pt; color: {p['text']}; }}
    QMainWindow, QWidget#ElutekCentral, QDialog {{ background: {p['bg']}; color: {p['text']}; }}
    QScrollArea, QAbstractScrollArea, QScrollArea > QWidget,
    QScrollArea QWidget#qt_scrollarea_viewport, QWidget#graphHost {{ background: {p['bg']}; color: {p['text']}; }}
    QScrollArea#graphScroll {{ background: {p['bg']}; border: none; }}
    QLabel {{ color: {p['text']}; background: transparent; font-size: 9pt; }}

    QToolTip {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border_strong']};
                border-radius: 8px; padding: 6px 8px; }}

    QPushButton {{ background: {p['surface_2']}; color: {p['text']}; border: 1px solid {p['border']};
                   border-radius: 12px; padding: 7px 14px; font-size: 9pt; font-weight: 600; }}
    QPushButton:hover {{ background: {p['surface_3']}; border-color: {p['border_strong']}; }}
    QPushButton:pressed {{ background: {p['border_strong']}; }}
    QPushButton:checked {{ background: {p['accent_soft']}; color: {p['accent']}; border: 1px solid {p['accent']}; }}
    QPushButton:checked:hover {{ border-color: {p['accent_hover']}; }}
    QPushButton:disabled {{ color: {p['text_faint']}; }}
    QPushButton#dangerButton {{ background: {p['danger']}; color: #FFFFFF; border: 1px solid {p['danger']}; font-weight: 700; }}
    QPushButton#dangerButton:hover {{ background: {p['danger_hover']}; border-color: {p['danger_hover']}; }}
    QPushButton#accentButton {{ background: {p['accent']}; color: {p['on_accent']}; border: 1px solid {p['accent']}; }}
    QPushButton#accentButton:hover {{ background: {p['accent_hover']}; border-color: {p['accent_hover']}; }}

    QLabel#transitionAlert {{ background: {p['danger']}; color: #FFFFFF; border: 2px solid rgba(255,255,255,0.65);
                              border-radius: 18px; padding: 14px 24px; font-size: 15pt; font-weight: 800; }}
    QLabel#transitionAlert:hover {{ background: {p['danger_hover']}; border: 2px solid #FFFFFF; }}
    QFrame#transitionStatusPanel {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 16px; }}
    QLabel#transitionStatusHeader {{ color: {p['text']}; font-weight: 800; letter-spacing: 0.5px; }}
    QLabel#transitionStatusLine {{ color: {p['text_muted']}; font-weight: 600; }}
    QLabel#transitionStatusLine[state="active"] {{ color: {p['accent']}; font-weight: 800; }}
    QLabel#transitionStatusLine[state="done"] {{ color: {p['success']}; font-weight: 700; }}
    QLabel#transitionStatusDetail {{ color: {p['text_muted']}; border-top: 1px solid {p['border']}; padding-top: 6px;
                                     font-family: '{FONT_MONO}'; }}

    QFrame#cursorHud {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 10px; padding: 2px 10px; }}
    QLabel#cursorHudLabel {{ font-family: '{FONT_MONO}'; font-size: 9pt; font-weight: 600; color: {p['accent']}; }}

    QGroupBox {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 12px;
                 margin-top: 14px; padding: 12px 8px 8px 8px; }}
    QGroupBox::title {{ color: {p['text_muted']}; subcontrol-origin: margin; left: 12px; padding: 0 4px; font-weight: 700; }}
    QRadioButton, QCheckBox {{ color: {p['text']}; spacing: 8px; background: transparent; }}

    QLineEdit, QTextEdit, QPlainTextEdit, QListWidget, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {p['surface_2']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 10px;
        padding: 5px 9px; selection-background-color: {p['accent']}; selection-color: {p['on_accent']}; }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {p['accent']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border_strong']};
                                   selection-background-color: {p['accent_soft']}; selection-color: {p['text']}; outline: 0; }}
    QListWidget {{ alternate-background-color: {p['surface']}; outline: 0; }}
    QListWidget::item {{ padding: 6px 4px; border-radius: 6px; color: {p['text']}; }}
    QListWidget::item:selected {{ background: {p['accent_soft']}; color: {p['text']}; }}

    QSlider::groove:horizontal {{ height: 4px; background: {p['surface_3']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {p['accent']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {p['surface']}; border: 4px solid {p['accent']}; width: 10px; height: 10px;
                                  margin: -7px 0; border-radius: 9px; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; border: none; }}
    QScrollBar::handle:vertical {{ background: {p['surface_3']}; border-radius: 3px; min-height: 28px; }}
    QScrollBar::handle:vertical:hover {{ background: {p['border_strong']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; background: none; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; border: none; }}
    QScrollBar::handle:horizontal {{ background: {p['surface_3']}; border-radius: 3px; min-width: 28px; }}
    QScrollBar::handle:horizontal:hover {{ background: {p['border_strong']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; background: none; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

    QMenu {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border_strong']}; border-radius: 10px; padding: 4px; }}
    QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {p['accent_soft']}; color: {p['text']}; }}
    QMessageBox {{ background: {p['bg']}; }}
    """


# ---------------------------------------------------------------------------
# Градиентные элементы (Canvas + Pillow)
# ---------------------------------------------------------------------------

def _gradient_image(w, h, c1, c2, radius, factor=1.0, k=3):
    """Горизонтальный градиент со скруглёнными краями (RGBA, PIL.Image)."""
    import numpy as np
    from PIL import Image, ImageDraw
    W, H = max(2, w) * k, max(2, h) * k
    a = np.array(hex_to_rgb(c1), dtype=np.float32)
    b = np.array(hex_to_rgb(c2), dtype=np.float32)
    t = np.linspace(0.0, 1.0, W, dtype=np.float32)[None, :, None]
    row = a * (1 - t) + b * t
    # лёгкий вертикальный «блик» сверху
    v = np.linspace(1.08, 0.94, H, dtype=np.float32)[:, None, None]
    arr = np.clip(row * v * factor, 0, 255).astype(np.uint8)
    arr = np.broadcast_to(arr, (H, W, 3)).copy()
    img = Image.fromarray(arr, "RGB").convert("RGBA")
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=radius * k, fill=255)
    img.putalpha(mask)
    return img.resize((max(2, w), max(2, h)), Image.LANCZOS)


class GradientButton(tk.Canvas):
    """Кнопка-«таблетка» с градиентной заливкой, hover и нажатием."""

    def __init__(self, parent, text, command=None, colors=("#7C6CFF", "#FF6FAE"),
                 height=54, bg="#000000", font=None, fg="#FFFFFF"):
        super().__init__(parent, height=height, highlightthickness=0, borderwidth=0,
                         bg=bg, cursor="hand2", takefocus=1)
        self._text = text
        self._command = command
        self._colors = colors
        self._font = font or (FONT_SEMIBOLD, 12)
        self._fg = fg
        self._state = "normal"
        self._cache = {}
        self._photo = None
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", lambda e: self._set_state("hover"))
        self.bind("<Leave>", lambda e: self._set_state("normal"))
        self.bind("<ButtonPress-1>", lambda e: self._set_state("pressed"))
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Return>", lambda e: self._invoke())
        self.bind("<space>", lambda e: self._invoke())

    def _invoke(self):
        if self._command is not None:
            self._command()

    def _on_release(self, event):
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self._set_state("hover" if inside else "normal")
        if inside:
            self._invoke()

    def _set_state(self, state):
        if state != self._state:
            self._state = state
            self._redraw()

    def configure_theme(self, bg, colors, font=None):
        self._colors = colors
        if font is not None:
            self._font = font
        self._cache.clear()
        self.configure(bg=bg)
        self._redraw()

    def _redraw(self):
        from PIL import ImageTk
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        key = (w, h, self._state, self._colors)
        if key not in self._cache:
            factor = {"normal": 1.0, "hover": 1.1, "pressed": 0.88}[self._state]
            img = _gradient_image(w, h, self._colors[0], self._colors[1], radius=h // 2, factor=factor)
            self._cache = {k: v for k, v in self._cache.items() if k[:2] == (w, h)}
            self._cache[key] = ImageTk.PhotoImage(img, master=self)
        self._photo = self._cache[key]
        self.delete("all")
        self.create_image(0, 0, image=self._photo, anchor="nw")
        dy = 1 if self._state == "pressed" else 0
        self.create_text(w / 2, h / 2 + dy, text=self._text, fill=self._fg, font=self._font)


class StartButton(GradientButton):
    """Главная кнопка «Начать анализ»: градиентная таблетка с мягким свечением
    и иконкой Play в полупрозрачном круге."""

    GLOW = 7  # поле под свечение вокруг таблетки, px

    def __init__(self, parent, text, command=None, colors=("#7C6CFF", "#FF6FAE"),
                 height=58, bg="#000000", font=None, fg="#FFFFFF"):
        super().__init__(parent, text, command=command, colors=colors, height=height,
                         bg=bg, font=font or (FONT_SEMIBOLD, 11), fg=fg)

    def _render(self, w, h):
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter
        k = 3
        g = self.GLOW
        factor = {"normal": 1.0, "hover": 1.1, "pressed": 0.9}[self._state]
        glow_alpha = {"normal": 0.38, "hover": 0.6, "pressed": 0.22}[self._state]
        pw, ph = w - 2 * g, h - 2 * g
        dy = 1 if self._state == "pressed" else 0

        # Свечение: размытая таблетка того же градиента, чуть сдвинутая вниз.
        glow = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
        pill = _gradient_image(pw, ph, self._colors[0], self._colors[1], radius=ph // 2, k=k)
        shadow = pill.resize((pw * k, ph * k))
        alpha = shadow.getchannel("A").point(lambda a: int(a * glow_alpha))
        shadow.putalpha(alpha)
        glow.paste(shadow, (g * k, (g + 3) * k), shadow)
        glow = glow.filter(ImageFilter.GaussianBlur(5 * k)).resize((w, h), Image.LANCZOS)

        bg = Image.new("RGBA", (w, h), hex_to_rgb(self.cget("bg")) + (255,))
        bg.alpha_composite(glow)
        face = _gradient_image(pw, ph, self._colors[0], self._colors[1], radius=ph // 2, factor=factor)
        bg.alpha_composite(face, (g, g + dy))

        # Иконка: полупрозрачный белый круг с треугольником Play.
        d = 24
        ic = Image.new("RGBA", (d * k, d * k), (0, 0, 0, 0))
        di = ImageDraw.Draw(ic)
        di.ellipse((0, 0, d * k - 1, d * k - 1), fill=(255, 255, 255, 56))
        c = d * k / 2
        s = d * k * 0.2
        di.polygon([(c - s * 0.75, c - s), (c - s * 0.75, c + s), (c + s * 1.05, c)], fill=(255, 255, 255, 255))
        ic = ic.resize((d, d), Image.LANCZOS)
        return bg, ic

    def _redraw(self):
        from PIL import ImageTk
        from tkinter import font as tkfont
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 * self.GLOW or h < 2 * self.GLOW + 4:
            return
        key = (w, h, self._state, self._colors, self.cget("bg"))
        if key not in self._cache:
            bg, ic = self._render(w, h)
            self._cache = {kk: v for kk, v in self._cache.items() if kk[:2] == (w, h)}
            self._cache[key] = (ImageTk.PhotoImage(bg, master=self), ImageTk.PhotoImage(ic, master=self))
        self._photo, self._icon = self._cache[key]
        self.delete("all")
        self.create_image(0, 0, image=self._photo, anchor="nw")
        dy = 1 if self._state == "pressed" else 0
        text_w = tkfont.Font(root=self, font=self._font).measure(self._text)
        gap, icon_w = 10, self._icon.width()
        x0 = (w - (icon_w + gap + text_w)) / 2
        self.create_image(x0, h / 2 + dy, image=self._icon, anchor="w")
        self.create_text(x0 + icon_w + gap, h / 2 + dy, text=self._text, fill=self._fg,
                         font=self._font, anchor="w")


def gradient_orb(widget, p, size=38, letter="Э"):
    """Круглый градиентный логотип с буквой."""
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    k = 4
    img = _gradient_image(size, size, p["grad_a"], p["grad_b"], radius=size // 2, k=k)
    big = img.resize((size * k, size * k), Image.LANCZOS)
    d = ImageDraw.Draw(big)
    font = None
    for name in ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"):
        try:
            font = ImageFont.truetype(name, int(size * 0.5 * k))
            break
        except Exception:
            continue
    d.text((size * k / 2, size * k / 2), letter, fill=(255, 255, 255, 255),
           font=font or ImageFont.load_default(), anchor="mm")
    return ImageTk.PhotoImage(big.resize((size, size), Image.LANCZOS), master=widget)


def get_palette(light=True):
    """Backward-compatible semantic palette for the existing application UI."""
    p = palette(light)
    return {
        "background": p["bg"], "surface": p["surface"],
        "surface_alt": p["surface_2"], "surface_hover": p["surface_3"],
        "text": p["text"], "muted": p["text_muted"], "border": p["border"],
        "accent": p["accent"], "accent_hover": p["accent_hover"],
        "accent_soft": p["accent_soft"], "accent_on": p["on_accent"],
        "success": p["success"], "success_soft": p["success_soft"],
        "warning": p["warning"], "warning_soft": p["warning_soft"],
        "danger": p["danger"], "danger_hover": p["danger_hover"],
        "danger_soft": p["danger_soft"], "danger_on": p["on_accent"],
        "channel_r": p["chart_r"], "channel_g": p["chart_g"],
        "channel_b": p["chart_b"], "chart_grid": p["chart_grid"],
        "video_background": p["video_bg"],
    }
