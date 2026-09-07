#!/usr/bin/env python3
"""
GitPulse HUD — AAA Grade Vector Cairo Charts via Gdk.MemoryTexture
100% immune to PyGObject foreign struct converter issues.
High-resolution 2x supersampled vector rendering.
"""

import math
import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib


def rounded_rectangle(cr, x, y, w, h, r):
    if w < 2 * r:
        r = w / 2
    if h < 2 * r:
        r = h / 2
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def surface_to_texture(surface, w, h):
    surface.flush()
    data = surface.get_data()
    glib_bytes = GLib.Bytes.new(data.tobytes())
    stride = surface.get_stride()
    return Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, glib_bytes, stride)


class CommitVelocityWidget(Gtk.Box):
    def __init__(self, w=640, h=175):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.w = w
        self.h = h
        self.scale = 2
        self.data = []
        
        self.picture = Gtk.Picture()
        self.picture.set_can_shrink(True)
        self.picture.set_content_fit(Gtk.ContentFit.FILL)
        self.picture.set_size_request(w, h)
        self.append(self.picture)
        
        self._render()

    def set_data(self, data):
        self.data = data or []
        self._render()

    def _render(self):
        w, h, s = self.w, self.h, self.scale
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * s, h * s)
        cr = cairo.Context(surface)
        cr.scale(s, s)

        # Inset backdrop
        rounded_rectangle(cr, 0, 0, w, h, 10)
        cr.set_source_rgb(0.065, 0.075, 0.10)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.05)
        cr.set_line_width(1.0)
        cr.stroke()

        counts = [item.get("count", 0) for item in self.data] if self.data else []
        has_commits = any(c > 0 for c in counts)

        if not self.data or not has_commits:
            cr.set_source_rgba(0.55, 0.60, 0.72, 0.85)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12)
            msg = "No commit activity in the last 14 days"
            ext = cr.text_extents(msg)
            cr.move_to((w - ext.width) / 2, h / 2 - 2)
            cr.show_text(msg)

            cr.set_source_rgba(0.40, 0.45, 0.55, 0.75)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            sub = "Activity will appear here as commits are made to this branch"
            sub_ext = cr.text_extents(sub)
            cr.move_to((w - sub_ext.width) / 2, h / 2 + 18)
            cr.show_text(sub)

            tex = surface_to_texture(surface, w * s, h * s)
            self.picture.set_paintable(tex)
            return

        pad_x = 24
        pad_top = 32
        pad_bottom = 26
        chart_w = w - 2 * pad_x
        chart_h = h - pad_top - pad_bottom

        max_count = max(counts) if counts else 1
        if max_count == 0:
            max_count = 1

        # Horizontal subtle grid lines
        cr.set_line_width(0.8)
        for g in [0.33, 0.66, 1.0]:
            gy = pad_top + chart_h - g * chart_h
            cr.move_to(pad_x, gy)
            cr.line_to(pad_x + chart_w, gy)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.035)
            cr.stroke()

        # Baseline
        cr.move_to(pad_x, pad_top + chart_h)
        cr.line_to(pad_x + chart_w, pad_top + chart_h)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.stroke()

        n_bars = len(self.data)
        bar_step = chart_w / n_bars
        bar_w = max(10, bar_step * 0.55)

        for i, item in enumerate(self.data):
            count = item.get("count", 0)
            bx = pad_x + i * bar_step + (bar_step - bar_w) / 2
            bh = (count / max_count) * chart_h if count > 0 else 3
            by = pad_top + chart_h - bh

            rounded_rectangle(cr, bx, by, bar_w, bh, min(4, bar_w / 2))

            if count > 0:
                pat = cairo.LinearGradient(bx, by, bx, by + bh)
                pat.add_color_stop_rgb(0, 0.22, 0.74, 0.97)  # Cyan #38bdf8
                pat.add_color_stop_rgb(1, 0.39, 0.40, 0.95)  # Indigo #6366f1
                cr.set_source(pat)
            else:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.05)

            cr.fill()

            # Number badge above active bars
            if count > 0:
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                cr.set_font_size(10)
                cr.set_source_rgb(0.38, 0.85, 0.98)
                val_str = str(count)
                val_ext = cr.text_extents(val_str)
                cr.move_to(bx + bar_w / 2 - val_ext.width / 2, by - 6)
                cr.show_text(val_str)

            # Date Label below baseline
            if i % max(1, n_bars // 7) == 0 or i == n_bars - 1:
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(9)
                cr.set_source_rgba(0.50, 0.55, 0.65, 0.9)
                lbl = item.get("label", "")
                ext = cr.text_extents(lbl)
                cr.move_to(bx + bar_w / 2 - ext.width / 2, h - 8)
                cr.show_text(lbl)

        tex = surface_to_texture(surface, w * s, h * s)
        self.picture.set_paintable(tex)


class PunchcardWidget(Gtk.Box):
    def __init__(self, w=640, h=62):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.w = w
        self.h = h
        self.scale = 2
        self.hours = [0] * 24
        
        self.picture = Gtk.Picture()
        self.picture.set_can_shrink(True)
        self.picture.set_content_fit(Gtk.ContentFit.FILL)
        self.picture.set_size_request(w, h)
        self.append(self.picture)
        
        self._render()

    def set_hours(self, hours):
        self.hours = hours or [0] * 24
        self._render()

    def _render(self):
        w, h, s = self.w, self.h, self.scale
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * s, h * s)
        cr = cairo.Context(surface)
        cr.scale(s, s)

        rounded_rectangle(cr, 0, 0, w, h, 10)
        cr.set_source_rgb(0.065, 0.075, 0.10)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.05)
        cr.set_line_width(1.0)
        cr.stroke()

        pad_x = 20
        pad_y = 10
        total_w = w - 2 * pad_x
        cell_h = h - 2 * pad_y - 14
        cell_w = total_w / 24

        max_val = max(self.hours) if self.hours else 1
        if max_val == 0:
            max_val = 1

        for hour in range(24):
            val = self.hours[hour] if hour < len(self.hours) else 0
            ratio = val / max_val
            x = pad_x + hour * cell_w + 1.5
            bw = max(4, cell_w - 3)
            y = pad_y
            rounded_rectangle(cr, x, y, bw, cell_h, 3)

            if val > 0:
                alpha = 0.35 + 0.65 * ratio
                cr.set_source_rgba(0.13, 0.85, 0.55, alpha)
            else:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.04)
            cr.fill()

        # Hour Markers
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9)
        cr.set_source_rgba(0.50, 0.55, 0.65, 0.85)
        for hour in [0, 4, 8, 12, 16, 20, 23]:
            lbl = f"{hour:02d}:00"
            ext = cr.text_extents(lbl)
            x = pad_x + hour * cell_w + (cell_w - ext.width) / 2
            cr.move_to(x, h - 5)
            cr.show_text(lbl)

        tex = surface_to_texture(surface, w * s, h * s)
        self.picture.set_paintable(tex)


class TrafficViewsChart(Gtk.Box):
    def __init__(self, w=600, h=165):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.w = w
        self.h = h
        self.scale = 2
        self.history = []
        
        self.picture = Gtk.Picture()
        self.picture.set_can_shrink(True)
        self.picture.set_content_fit(Gtk.ContentFit.FILL)
        self.picture.set_size_request(w, h)
        self.append(self.picture)
        
        self._render()

    def set_history(self, history):
        self.history = history or []
        self._render()

    def _render(self):
        w, h, s = self.w, self.h, self.scale
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * s, h * s)
        cr = cairo.Context(surface)
        cr.scale(s, s)

        rounded_rectangle(cr, 0, 0, w, h, 10)
        cr.set_source_rgb(0.065, 0.075, 0.10)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.05)
        cr.set_line_width(1.0)
        cr.stroke()

        if not self.history:
            cr.set_source_rgba(0.55, 0.60, 0.72, 0.85)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12)
            msg = "Configure GitHub Access Token to view 14-day traffic trend"
            ext = cr.text_extents(msg)
            cr.move_to((w - ext.width) / 2, h / 2 - 2)
            cr.show_text(msg)

            cr.set_source_rgba(0.40, 0.45, 0.55, 0.75)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            sub = "Page views and visitor telemetry require repository access permissions"
            sub_ext = cr.text_extents(sub)
            cr.move_to((w - sub_ext.width) / 2, h / 2 + 18)
            cr.show_text(sub)

            tex = surface_to_texture(surface, w * s, h * s)
            self.picture.set_paintable(tex)
            return

        pad_x = 24
        pad_top = 34
        pad_bottom = 24
        chart_w = w - 2 * pad_x
        chart_h = h - pad_top - pad_bottom

        counts = [x.get("count", 0) for x in self.history] or [0]
        uniques = [x.get("uniques", 0) for x in self.history] or [0]
        max_views = max(max(counts), max(uniques), 1)

        n_pts = len(self.history)
        step = chart_w / max(1, n_pts - 1)

        # Baseline & grid
        cr.set_line_width(0.8)
        for g in [0.5, 1.0]:
            gy = pad_top + chart_h - g * chart_h
            cr.move_to(pad_x, gy)
            cr.line_to(pad_x + chart_w, gy)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.035)
            cr.stroke()

        cr.move_to(pad_x, pad_top + chart_h)
        cr.line_to(pad_x + chart_w, pad_top + chart_h)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.stroke()

        # Page views filled area
        cr.new_path()
        cr.move_to(pad_x, pad_top + chart_h)
        for i, pt in enumerate(self.history):
            vx = pad_x + i * step
            vy = pad_top + chart_h - (pt.get("count", 0) / max_views) * chart_h
            cr.line_to(vx, vy)
        cr.line_to(pad_x + (n_pts - 1) * step, pad_top + chart_h)
        cr.close_path()

        pat = cairo.LinearGradient(0, pad_top, 0, pad_top + chart_h)
        pat.add_color_stop_rgba(0, 0.13, 0.85, 0.55, 0.30)
        pat.add_color_stop_rgba(1, 0.13, 0.85, 0.55, 0.02)
        cr.set_source(pat)
        cr.fill_preserve()

        cr.set_source_rgba(0.13, 0.85, 0.55, 0.95)
        cr.set_line_width(2.0)
        cr.stroke()

        # Unique visitors line
        cr.new_path()
        for i, pt in enumerate(self.history):
            ux = pad_x + i * step
            uy = pad_top + chart_h - (pt.get("uniques", 0) / max_views) * chart_h
            if i == 0:
                cr.move_to(ux, uy)
            else:
                cr.line_to(ux, uy)
        cr.set_source_rgba(0.22, 0.74, 0.97, 0.95)
        cr.set_line_width(1.8)
        cr.stroke()

        # Legend
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        cr.set_source_rgba(0.13, 0.85, 0.55, 0.95)
        cr.arc(pad_x + 6, 17, 3.5, 0, 2 * math.pi)
        cr.fill()
        cr.move_to(pad_x + 15, 20)
        cr.show_text("Page Views")

        cr.set_source_rgba(0.22, 0.74, 0.97, 0.95)
        cr.arc(pad_x + 110, 17, 3.5, 0, 2 * math.pi)
        cr.fill()
        cr.move_to(pad_x + 119, 20)
        cr.show_text("Unique Visitors")

        tex = surface_to_texture(surface, w * s, h * s)
        self.picture.set_paintable(tex)
