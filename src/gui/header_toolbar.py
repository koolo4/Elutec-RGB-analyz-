"""
Панель глобальных действий в шапке: тема · настройки · лицензия.

Кнопки собраны в одну скруглённую «капсулу» с тонкими разделителями.
Каждый сегмент — отдельный tk.Label с картинкой, нарисованной Pillow
(суперсэмплинг), поэтому края гладкие, а наведение / нажатие подсвечивают
только свой сегмент. Иконки рисуются кодом и следуют палитре темы.
"""

import math
import os
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

HEIGHT = 36
ICON = 18
PAD_X = 11
GAP = 7
_SS = 4


def _rgb(value):
    text = str(value or '#ffffff').lstrip('#')
    if len(text) == 3:
        text = ''.join(ch * 2 for ch in text)
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (255, 255, 255)


def _font(size):
    windir = os.environ.get('WINDIR', 'C:\\Windows')
    for name in ('seguisb.ttf', 'segoeuib.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf'):
        for path in (name, os.path.join(windir, 'Fonts', name)):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def paint_icon(name, size=ICON, color='#ffffff'):
    """Иконка шапки (sun / moon / gear / key) как RGBA-картинка Pillow."""
    px = int(size) * _SS
    image = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    rgb = _rgb(color) + (255,)
    stroke = max(2, int(px * 0.09))
    c = px / 2.0

    if name == 'sun':
        r = px * 0.19
        draw.ellipse((c - r, c - r, c + r, c + r), fill=rgb)
        for step in range(8):
            a = math.radians(step * 45)
            dx, dy = math.cos(a), math.sin(a)
            draw.line((c + px * 0.32 * dx, c + px * 0.32 * dy, c + px * 0.44 * dx, c + px * 0.44 * dy),
                      fill=rgb, width=stroke)
    elif name == 'moon':
        draw.ellipse((px * 0.1, px * 0.1, px * 0.9, px * 0.9), fill=rgb)
        off = px * 0.55 * math.cos(math.radians(-45))
        cr = px * 0.4
        cx, cy = px * 0.5 + off, px * 0.5 - off
        draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=(0, 0, 0, 0))
    elif name == 'gear':
        teeth = 8
        r_out, r_in = px * 0.46, px * 0.33
        pts = []
        for i in range(teeth * 4):
            a = 2 * math.pi * i / (teeth * 4) - math.pi / 2
            r = r_out if i % 4 in (0, 1) else r_in
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        draw.polygon(pts, fill=rgb)
        draw.ellipse((c - r_in, c - r_in, c + r_in, c + r_in), fill=rgb)
        hole = px * 0.14
        draw.ellipse((c - hole, c - hole, c + hole, c + hole), fill=(0, 0, 0, 0))
    elif name == 'key':
        rx, ry, rr = px * 0.31, px * 0.69, px * 0.17
        draw.ellipse((rx - rr, ry - rr, rx + rr, ry + rr), outline=rgb, width=stroke)
        dx, dy = math.cos(math.radians(-45)), math.sin(math.radians(-45))
        sx, sy = rx + rr * dx, ry + rr * dy
        length = px * 0.44
        draw.line((sx, sy, sx + length * dx, sy + length * dy), fill=rgb, width=stroke)
        tx, ty = -dy, dx
        for frac in (0.55, 0.85):
            bx, by = sx + length * frac * dx, sy + length * frac * dy
            draw.line((bx, by, bx + px * 0.13 * tx, by + px * 0.13 * ty), fill=rgb, width=stroke)
    else:
        draw.ellipse((0, 0, px - 1, px - 1), outline=rgb, width=stroke)

    return image.resize((int(size), int(size)), Image.LANCZOS)


class _Segment:
    def __init__(self, bar, icon, text, command):
        self.bar = bar
        self.icon = icon
        self.text = text
        self.command = command
        self.badge = None
        self.state = 'normal'
        self.position = 'single'
        self.label = tk.Label(bar.frame, bd=0, highlightthickness=0, cursor='hand2')
        self.label.bind('<Enter>', lambda e: self._set_state('hover'), add='+')
        self.label.bind('<Leave>', lambda e: self._set_state('normal'), add='+')
        self.label.bind('<ButtonPress-1>', lambda e: self._set_state('pressed'), add='+')
        self.label.bind('<ButtonRelease-1>', self._on_release, add='+')

    def _set_state(self, state):
        if state != self.state:
            self.state = state
            self.redraw()

    def _on_release(self, event):
        inside = 0 <= event.x < self.label.winfo_width() and 0 <= event.y < self.label.winfo_height()
        self._set_state('hover' if inside else 'normal')
        if inside and callable(self.command):
            self.command()

    def width(self):
        w = PAD_X * 2 + ICON
        if self.text:
            w += GAP + int(math.ceil(self.bar.font.getlength(self.text) / _SS))
        return w

    def redraw(self):
        p = self.bar.palette
        w, h, k = self.width(), HEIGHT, _SS
        W, H = w * k, h * k
        r = (h / 2.0) * k
        img = Image.new('RGBA', (W, H), _rgb(p['surface']) + (255,))
        d = ImageDraw.Draw(img)
        fill = _rgb(p['surface_alt'])
        border = _rgb(p['border'])
        # Капсула общая для всех сегментов: каждый рисует свой кусок, выпуская
        # прямоугольник за край там, где соседний сегмент продолжает форму.
        left = 0 if self.position in ('left', 'single') else -2 * r
        right = W - 1 if self.position in ('right', 'single') else W + 2 * r
        d.rounded_rectangle((left, 0, right, H - 1), radius=r, fill=fill, outline=border, width=k)
        if self.position in ('mid', 'right'):
            d.line((0, H * 0.28, 0, H * 0.72), fill=border, width=k)

        accent = p['accent']
        if self.state in ('hover', 'pressed'):
            inset = 3 * k
            tone = p['accent_soft'] if self.state == 'pressed' else p['surface_hover']
            hl = (left + inset if left >= 0 else 2 * k, inset,
                  right - inset if right < W else W - 2 * k, H - 1 - inset)
            d.rounded_rectangle(hl, radius=r - inset, fill=_rgb(tone))
        fg = accent if self.state != 'normal' else p['text']

        x = PAD_X * k
        icon = paint_icon(self.icon, ICON * k, fg)
        img.alpha_composite(icon, (int(x), int((H - ICON * k) / 2)))
        if self.badge:
            br = 3.2 * k
            # Свободный нижний правый угол иконки ключа.
            bx, by = x + ICON * k - br * 0.4, (H + ICON * k) / 2 - br * 0.4
            d.ellipse((bx - br - k, by - br - k, bx + br + k, by + br + k), fill=fill)
            d.ellipse((bx - br, by - br, bx + br, by + br), fill=_rgb(self.badge))
        if self.text:
            tx = x + (ICON + GAP) * k
            bbox = self.bar.font.getbbox(self.text)
            ty = (H - (bbox[3] - bbox[1])) / 2 - bbox[1]
            d.text((tx, ty), self.text, font=self.bar.font, fill=_rgb(fg))

        photo = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS), master=self.label)
        self.label.configure(image=photo, bg=p['surface'])
        self.label.image = photo


class HeaderToolbar:
    """Скруглённая группа кнопок шапки."""

    def __init__(self, parent, palette):
        self.palette = palette
        self.font = _font(13 * _SS)
        self.frame = tk.Frame(parent, bd=0, highlightthickness=0, bg=palette['surface'])
        self._segments = []

    def add(self, icon, command, text=None):
        seg = _Segment(self, icon, text, command)
        self._segments.append(seg)
        seg.label.pack(side='left')
        count = len(self._segments)
        for i, s in enumerate(self._segments):
            s.position = 'single' if count == 1 else ('left' if i == 0 else ('right' if i == count - 1 else 'mid'))
            s.redraw()
        return seg

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
        return self

    def set_palette(self, palette):
        self.palette = palette
        self.frame.configure(bg=palette['surface'])
        for seg in self._segments:
            seg.redraw()

    @staticmethod
    def set_icon(segment, icon):
        if segment.icon != icon:
            segment.icon = icon
            segment.redraw()

    @staticmethod
    def set_badge(segment, color):
        if segment.badge != color:
            segment.badge = color
            segment.redraw()
