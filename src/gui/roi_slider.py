"""
Ползунок в стиле приложения для полей области анализа (ROI).

Тонкая дорожка, заполненная акцентом часть и круглая ручка (рисуется
Pillow, чтобы края были гладкими). Двусторонне связан с tk.IntVar:
перетаскивание меняет переменную, а правка поля / кнопки +− двигают ручку.
Диапазон берётся из функции, поэтому следует за размером кадра.
"""

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from .header_toolbar import _rgb

HEIGHT = 22
PAD = 9
_SS = 4


def _knob(radius, fill, ring):
    size = radius * 2 + 2
    k = _SS
    img = Image.new('RGBA', (size * k, size * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((k, k, (size - 1) * k, (size - 1) * k), fill=_rgb(ring) + (255,))
    inset = 3 * k
    d.ellipse((k + inset, k + inset, (size - 1) * k - inset, (size - 1) * k - inset), fill=_rgb(fill) + (255,))
    return img.resize((size, size), Image.LANCZOS)


class RoiSlider:
    def __init__(self, parent, palette, var, range_fn, on_change=None):
        self.palette = palette
        self.var = var
        self.range_fn = range_fn
        self.on_change = on_change
        self.hover = False
        self.dragging = False
        self._knobs = {}
        self.canvas = tk.Canvas(parent, height=HEIGHT, bd=0, highlightthickness=0,
                                bg=palette['surface'], cursor='hand2')
        self.canvas.bind('<Configure>', lambda e: self.redraw())
        self.canvas.bind('<Enter>', lambda e: self._set_hover(True))
        self.canvas.bind('<Leave>', lambda e: self._set_hover(False))
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        var.trace_add('write', lambda *args: self.redraw())

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)
        return self

    def set_palette(self, palette):
        self.palette = palette
        self._knobs = {}
        self.canvas.configure(bg=palette['surface'])
        self.redraw()

    def _bounds(self):
        lo, hi = self.range_fn()
        lo, hi = int(lo), int(hi)
        return lo, max(lo + 1, hi)

    def _value(self):
        try:
            return int(self.var.get())
        except (tk.TclError, ValueError):
            return None

    def _x_for(self, value):
        lo, hi = self._bounds()
        w = self.canvas.winfo_width()
        t = (min(max(value, lo), hi) - lo) / float(hi - lo)
        return PAD + t * max(1, w - 2 * PAD)

    def _value_at(self, x):
        lo, hi = self._bounds()
        w = self.canvas.winfo_width()
        t = (x - PAD) / float(max(1, w - 2 * PAD))
        return int(round(lo + min(max(t, 0.0), 1.0) * (hi - lo)))

    def _set_hover(self, hover):
        self.hover = hover
        self.redraw()

    def _on_press(self, event):
        self.dragging = True
        self._apply(event.x)

    def _on_drag(self, event):
        if self.dragging:
            self._apply(event.x)

    def _on_release(self, event):
        self.dragging = False
        self.redraw()

    def _apply(self, x):
        value = self._value_at(x)
        if value != self._value():
            self.var.set(value)
            if callable(self.on_change):
                self.on_change()

    def redraw(self):
        c = self.canvas
        w = c.winfo_width()
        if w < 2 * PAD + 4:
            return
        p = self.palette
        value = self._value()
        lo, _ = self._bounds()
        kx = self._x_for(lo if value is None else value)
        cy = HEIGHT / 2
        c.delete('all')
        c.create_line(PAD, cy, w - PAD, cy, fill=p['surface_hover'], width=4, capstyle='round')
        if kx > PAD:
            c.create_line(PAD, cy, kx, cy, fill=p['accent'], width=4, capstyle='round')
        active = self.hover or self.dragging
        radius = 8 if active else 7
        key = (radius, active)
        knob = self._knobs.get(key)
        if knob is None:
            fill = p['accent_hover'] if active else p['accent']
            knob = ImageTk.PhotoImage(_knob(radius, fill, p['text'] if active else p['surface']), master=c)
            self._knobs[key] = knob
        c.create_image(kx, cy, image=knob)
