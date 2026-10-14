"""
Анимированный логотип «ЭЛЮТЕК» для шапки приложения.

Повторяет фирменный логотип (ЭЛЮТЕК-логотип-анимация.html): слово «ЭЛЮТЕК»
из трёх цветных слоёв R / G / B, которые плавно расходятся и сходятся
(цикл 3,6 с), и подпись «RGB SARA-АНАЛИЗ» под ним.

Слои смешиваются как в CSS: в тёмной теме — «screen» (в пересечении белый),
в светлой — «multiply» (в пересечении тёмный), чтобы логотип читался на
любом фоне. Кадры рендерятся через Pillow + NumPy и кэшируются.
"""

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WORD = 'ЭЛЮТЕК'
SUBTITLE_TAIL = ' SARA-АНАЛИЗ'
PERIOD_S = 3.6
FRAMES = 48  # кадров на цикл (~13 кадров/с)

# Цвета слоёв и подписи из оригинального логотипа.
LAYER_COLORS = ((0xFF, 0x00, 0x33), (0x00, 0xFF, 0x66), (0x00, 0x44, 0xFF))
SUB_RGB_DARK = ('#FF4D6A', '#3DFF8B', '#5C8BFF')
SUB_RGB_LIGHT = ('#E0203F', '#0E9F4E', '#2D5BE0')

# Смещения слоёв (в px при кегле 108) в начале/середине цикла: (x, y).
_OFFSETS = (
    ((-9, -3), (-2, 0)),  # R
    ((2, 6), (0, 1)),     # G
    ((9, -3), (2, 0)),    # B
)
_REF_SIZE = 108.0

_SS = 3  # суперсэмплинг для гладких субпиксельных сдвигов


def _font_dirs():
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [os.path.join(here, 'assets', 'fonts')]
    base = getattr(sys, '_MEIPASS', None)
    if base:
        dirs.append(os.path.join(base, 'src', 'gui', 'assets', 'fonts'))
    return dirs


def _load_font(candidates, size):
    for name in candidates:
        paths = [name]
        for d in _font_dirs():
            paths.append(os.path.join(d, name))
        paths.append(os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', name))
        for path in paths:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _word_font(size):
    # Unbounded Black — шрифт оригинала; если его нет, ближайшие жирные гротески.
    return _load_font(
        ('Unbounded-Black.ttf', 'Unbounded-VariableFont_wght.ttf', 'seguibl.ttf',
         'ariblk.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf'),
        size,
    )


def _mono_font(size):
    return _load_font(
        ('JetBrainsMono-Bold.ttf', 'consolab.ttf', 'CascadiaMono.ttf', 'DejaVuSansMono-Bold.ttf'),
        size,
    )


def _hex(color):
    color = color.lstrip('#')
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


class BrandLogo:
    """Готовит кадры логотипа под заданный фон и тему."""

    def __init__(self, word_size=30, sub_size=10):
        self.word_size = word_size
        self.sub_size = sub_size
        self._mask = None
        self._mask_box = None
        self._cache_key = None
        self._frames = [None] * FRAMES

    # ---------- геометрия ----------
    def _word_mask(self):
        if self._mask is not None:
            return self._mask, self._mask_box
        size = self.word_size * _SS
        font = _word_font(size)
        spacing = 2 * self.word_size / _REF_SIZE * _SS
        widths = [font.getlength(ch) for ch in WORD]
        text_w = int(math.ceil(sum(widths) + spacing * (len(WORD) - 1)))
        bbox = font.getbbox(WORD)
        text_h = bbox[3] - bbox[1]
        pad = int(math.ceil(10 * self.word_size / _REF_SIZE * _SS)) + _SS
        mask = Image.new('L', (text_w + 2 * pad, text_h + 2 * pad), 0)
        draw = ImageDraw.Draw(mask)
        x = pad
        for ch, w in zip(WORD, widths):
            draw.text((x, pad - bbox[1]), ch, font=font, fill=255)
            x += w + spacing
        self._mask = mask
        self._mask_box = (pad, text_w, text_h)
        return mask, self._mask_box

    def _shift(self, mask, dx, dy):
        # Субпиксельный сдвиг маски (в пикселях суперсэмплинга).
        return mask.transform(mask.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR)

    # ---------- рендер ----------
    def _render(self, phase, bg_rgb, light, text_rgb):
        mask, (pad, text_w, text_h) = self._word_mask()
        k = self.word_size / _REF_SIZE * _SS
        # CSS ease-in-out между крайними положениями: 0 → 50% → 100%.
        p = (1 - math.cos(2 * math.pi * phase)) / 2
        bg = np.empty((mask.size[1], mask.size[0], 3), dtype=np.float32)
        bg[:] = np.array(bg_rgb, dtype=np.float32) / 255.0
        out = bg.copy() if not light else np.ones_like(bg)
        for color, ((x0, y0), (x1, y1)) in zip(LAYER_COLORS, _OFFSETS):
            dx = (x0 + (x1 - x0) * p) * k
            dy = (y0 + (y1 - y0) * p) * k
            a = np.asarray(self._shift(mask, dx, dy), dtype=np.float32)[..., None] / 255.0
            c = np.array(color, dtype=np.float32) / 255.0
            if light:
                # multiply: белый лист, каждый слой «окрашивает» как фильтр
                out *= 1 - a * (1 - c)
            else:
                # screen: свет складывается, пересечение уходит в белый
                out = 1 - (1 - out) * (1 - a * c)
        if light:
            out *= bg
        word = Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8), 'RGB')
        word = word.resize((max(1, word.size[0] // _SS), max(1, word.size[1] // _SS)), Image.LANCZOS)

        # Подпись «RGB SARA-АНАЛИЗ» моноширинным шрифтом с разрядкой.
        sub_font = _mono_font(self.sub_size)
        tracking = self.sub_size * 6 / 22
        rgb_cols = SUB_RGB_LIGHT if light else SUB_RGB_DARK
        chars = [(ch, rgb_cols[i]) for i, ch in enumerate('RGB')]
        chars += [(ch, text_rgb) for ch in SUBTITLE_TAIL]
        sub_w = int(math.ceil(sum(sub_font.getlength(ch) + tracking for ch, _ in chars)))
        sub_bbox = sub_font.getbbox('RGBSARA-АНАЛИЗ')
        sub_h = sub_bbox[3] - sub_bbox[1]

        edge = pad // _SS
        gap = max(3, round(self.word_size * 22 / _REF_SIZE))
        word_h = text_h // _SS
        width = max(word.size[0], edge + sub_w + 2)
        height = edge + word_h + gap + sub_h + 2
        canvas = Image.new('RGB', (width, height), bg_rgb)
        canvas.paste(word.crop((0, 0, word.size[0], min(word.size[1], edge + word_h + edge // 2))), (0, 0))
        draw = ImageDraw.Draw(canvas)
        x = edge
        y = edge + word_h + gap - sub_bbox[1]
        for ch, col in chars:
            draw.text((x, y), ch, font=sub_font, fill=col)
            x += sub_font.getlength(ch) + tracking
        return canvas

    def frame(self, index, bg_color, light, text_color):
        """PIL-кадр цикла анимации. Кадры рендерятся по требованию и
        кэшируются, пока не сменится тема (фон / цвет текста)."""
        key = (bg_color, bool(light), text_color)
        if key != self._cache_key:
            self._frames = [None] * FRAMES
            self._cache_key = key
        index %= FRAMES
        if self._frames[index] is None:
            self._frames[index] = self._render(index / FRAMES, _hex(bg_color), bool(light), _hex(text_color))
        return self._frames[index]


def app_icon(size=64):
    """Иконка окна: «Э» с RGB-расслоением на тёмном скруглённом квадрате."""
    k = 4
    S = size * k
    bg = Image.new('RGB', (S, S), (0, 0, 0))
    mask = Image.new('L', (S, S), 0)
    font = _word_font(int(S * 0.62))
    bbox = font.getbbox('Э')
    tx = (S - (bbox[2] - bbox[0])) / 2 - bbox[0]
    ty = (S - (bbox[3] - bbox[1])) / 2 - bbox[1]
    ImageDraw.Draw(mask).text((tx, ty), 'Э', font=font, fill=255)
    shift = S * 0.035
    out = np.full((S, S, 3), _hex('#15141E'), dtype=np.float32) / 255.0
    for color, (dx, dy) in zip(LAYER_COLORS, ((-shift, -shift * 0.4), (0, shift * 0.6), (shift, -shift * 0.4))):
        layer = mask.transform(mask.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR)
        a = np.asarray(layer, dtype=np.float32)[..., None] / 255.0
        out = 1 - (1 - out) * (1 - a * (np.array(color, dtype=np.float32) / 255.0))
    img = Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8), 'RGB').convert('RGBA')
    shape = Image.new('L', (S, S), 0)
    ImageDraw.Draw(shape).rounded_rectangle((0, 0, S - 1, S - 1), radius=S * 0.24, fill=255)
    img.putalpha(shape)
    return img.resize((size, size), Image.LANCZOS)


class AnimatedLogo:
    """tk.Label с анимированным логотипом; цикл останавливается вместе с виджетом."""

    def __init__(self, parent, bg_color, light, text_color, word_size=30, sub_size=10):
        import tkinter as tk
        self._logo = BrandLogo(word_size=word_size, sub_size=sub_size)
        self._photos = {}
        self._index = 0
        self._theme = (bg_color, bool(light), text_color)
        self.label = tk.Label(parent, bd=0, highlightthickness=0, bg=bg_color)
        self._draw()
        self._schedule()

    def pack(self, **kwargs):
        self.label.pack(**kwargs)
        return self

    def set_theme(self, bg_color, light, text_color):
        theme = (bg_color, bool(light), text_color)
        if theme != self._theme:
            self._theme = theme
            self._photos = {}
            self._draw()

    def _draw(self):
        from PIL import ImageTk
        photo = self._photos.get(self._index)
        if photo is None:
            bg_color, light, text_color = self._theme
            frame = self._logo.frame(self._index, bg_color, light, text_color)
            photo = ImageTk.PhotoImage(frame, master=self.label)
            self._photos[self._index] = photo
        try:
            self.label.configure(image=photo, bg=self._theme[0])
            self.label.image = photo
        except Exception:
            pass

    def _schedule(self):
        try:
            self.label.after(int(PERIOD_S * 1000 / FRAMES), self._tick)
        except Exception:
            pass

    def _tick(self):
        try:
            if not self.label.winfo_exists():
                return
        except Exception:
            return
        self._index = (self._index + 1) % FRAMES
        self._draw()
        self._schedule()
