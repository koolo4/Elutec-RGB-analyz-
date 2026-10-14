"""
Карточки выбора источника сигнала: «RGB-детектор» и «USB-камера».

Каждая карточка — во всю ширину панели: плитка с иконкой, название,
короткое пояснение и справа стрелка либо метка «Подключено» у активного
источника. Рисуется Pillow (суперсэмплинг), перерисовывается при смене
ширины, наведении, нажатии и теме.
"""

import os
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from .header_toolbar import _rgb

HEIGHT = 56
TILE = 34
_SS = 3


def _load(names, size):
    windir = os.environ.get('WINDIR', 'C:\\Windows')
    for name in names:
        for path in (name, os.path.join(windir, 'Fonts', name)):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _paint_source_icon(name, size, color, palette):
    """Иконка источника (rgb / usb) как RGBA-картинка размера size×size."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c = size / 2.0
    if name == 'rgb':
        # Три пересекающихся круга R/G/B — как каналы, которые меряет детектор.
        r = size * 0.27
        d = size * 0.15
        centers = ((c, c - d), (c - d * 1.05, c + d * 0.65), (c + d * 1.05, c + d * 0.65))
        for (cx, cy), key in zip(centers, ('channel_r', 'channel_g', 'channel_b')):
            layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            ImageDraw.Draw(layer).ellipse((cx - r, cy - r, cx + r, cy + r), fill=_rgb(palette[key]) + (205,))
            img.alpha_composite(layer)
    elif name == 'usb':
        # Видеокамера: корпус + объектив + «рупор».
        d = ImageDraw.Draw(img)
        rgb = _rgb(color) + (255,)
        w = max(2, int(size * 0.075))
        d.rounded_rectangle((size * 0.12, size * 0.3, size * 0.66, size * 0.72), radius=size * 0.08,
                            outline=rgb, width=w)
        d.polygon([(size * 0.7, size * 0.45), (size * 0.88, size * 0.34),
                   (size * 0.88, size * 0.68), (size * 0.7, size * 0.57)], fill=rgb)
        lr = size * 0.075
        d.ellipse((size * 0.39 - lr, size * 0.51 - lr, size * 0.39 + lr, size * 0.51 + lr), fill=rgb)
    return img


class SourceButton:
    def __init__(self, parent, palette, icon, title, subtitle, command):
        self.palette = palette
        self.icon = icon
        self.title = title
        self.subtitle = subtitle
        self.command = command
        self.state = 'normal'
        self.active = False
        self._width = 0
        self.frame = tk.Frame(parent, bd=0, highlightthickness=0, bg=palette['surface'], height=HEIGHT)
        self.frame.pack_propagate(False)
        self.label = tk.Label(self.frame, bd=0, highlightthickness=0, cursor='hand2', bg=palette['surface'])
        self.label.pack(fill='both', expand=True)
        self.frame.bind('<Configure>', self._on_resize)
        self.label.bind('<Enter>', lambda e: self._set_state('hover'))
        self.label.bind('<Leave>', lambda e: self._set_state('normal'))
        self.label.bind('<ButtonPress-1>', lambda e: self._set_state('pressed'))
        self.label.bind('<ButtonRelease-1>', self._on_release)
        self._fonts = (_load(('seguisb.ttf', 'segoeuib.ttf', 'arialbd.ttf'), 13 * _SS),
                       _load(('segoeui.ttf', 'arial.ttf'), 11 * _SS))

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
        return self

    def _on_resize(self, event):
        if event.width != self._width:
            self._width = event.width
            self.redraw()

    def _set_state(self, state):
        if state != self.state:
            self.state = state
            self.redraw()

    def _on_release(self, event):
        inside = 0 <= event.x < self.label.winfo_width() and 0 <= event.y < self.label.winfo_height()
        self._set_state('hover' if inside else 'normal')
        if inside and callable(self.command):
            self.command()

    def set_active(self, active):
        active = bool(active)
        if active != self.active:
            self.active = active
            self.redraw()

    def set_palette(self, palette):
        self.palette = palette
        self.frame.configure(bg=palette['surface'])
        self.redraw()

    def redraw(self):
        w = self._width
        if w < 60:
            return
        p, k = self.palette, _SS
        W, H = w * k, HEIGHT * k
        img = Image.new('RGBA', (W, H), _rgb(p['surface']) + (255,))
        d = ImageDraw.Draw(img)

        fill, outline, outline_w = p['surface_alt'], p['border'], 1
        if self.state == 'hover':
            fill = p['surface_hover']
        if self.active:
            fill, outline, outline_w = p['accent_soft'], p['accent'], 1.5
        if self.state == 'pressed':
            fill = p['accent_soft']
        d.rounded_rectangle((k // 2, k // 2, W - 1 - k // 2, H - 1 - k // 2), radius=12 * k,
                            fill=_rgb(fill), outline=_rgb(outline), width=max(1, int(outline_w * k)))

        # Плитка с иконкой.
        tx, ty = 11 * k, (H - TILE * k) // 2
        tile_fill = p['accent'] if self.active else p['surface']
        d.rounded_rectangle((tx, ty, tx + TILE * k, ty + TILE * k), radius=9 * k, fill=_rgb(tile_fill))
        icon_color = p['accent_on'] if self.active else (p['accent'] if self.state != 'normal' else p['text'])
        icon = _paint_source_icon(self.icon, 22 * k, icon_color, p)
        img.alpha_composite(icon, (tx + (TILE - 22) * k // 2, ty + (TILE - 22) * k // 2))

        # Название и пояснение.
        f_title, f_sub = self._fonts
        x = tx + (TILE + 11) * k
        right = W - 14 * k
        title_y = H / 2 - 1 * k
        d.text((x, title_y), self.title, font=f_title, fill=_rgb(p['text']), anchor='ls')
        # Пояснение обрезается многоточием, чтобы не заезжать на стрелку.
        sub_max = (right - x) if self.active else (right - x - 12 * k)
        sub = self.subtitle
        while sub and f_sub.getlength(sub) > sub_max:
            sub = sub[:-2].rstrip() + '…'
        d.text((x, H / 2 + 4 * k), sub, font=f_sub, fill=_rgb(p['muted']), anchor='lt')

        # Справа: метка активного источника (в строке названия) или стрелка.
        if self.active:
            label = 'Подключено'
            lw = f_sub.getlength(label)
            dot = 3 * k
            d.text((right, title_y), label, font=f_sub, fill=_rgb(p['accent']), anchor='rs')
            cx, cy = right - lw - 8 * k, title_y - 4.5 * k
            d.ellipse((cx - dot, cy - dot, cx + dot, cy + dot), fill=_rgb(p['success']))
        else:
            color = p['accent'] if self.state != 'normal' else p['muted']
            s = 4 * k
            cx = right - s / 2 + (2 * k if self.state == 'hover' else 0)
            d.line([(cx - s / 2, H / 2 - s), (cx + s / 2, H / 2), (cx - s / 2, H / 2 + s)],
                   fill=_rgb(color), width=int(1.8 * k), joint='curve')

        photo = ImageTk.PhotoImage(img.resize((w, HEIGHT), Image.LANCZOS), master=self.label)
        self.label.configure(image=photo, bg=p['surface'])
        self.label.image = photo
