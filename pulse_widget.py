#!/usr/bin/env python3
"""
GitPulse HUD — Pulse & Analytics Cairo Widgets
Custom GTK4 vector DrawingArea components for Commit Velocity, Views Trends, and 24h Punchcard.
"""

import math
import cairo
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk


def rounded_rectangle(cr, x, y, w, h, r):
    """Utility to draw a rounded rectangle in Cairo."""
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


class CommitVelocityWidget(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_content_width(360)
        self.set_content_height(140)
        self.data = []  # [{'label': '01 Sep', 'count': 5}, ...]
        self.set_draw_func(self._on_draw)

    def set_data(self, data):
        self.data = data or []
        self.queue_draw()

    def _on_draw(self, area, cr, width, height):
        # Dark subtle background
        rounded_rectangle(cr, 0, 0, width, height, 12)
        cr.set_source_rgba(0.08, 0.08, 0.12, 0.6)
        cr.fill()

        # Border
        rounded_rectangle(cr, 0.5, 0.5, width - 1, height - 1, 12)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.0)
        cr.stroke()

        if not self.data:
            cr.set_source_rgba(0.6, 0.6, 0.7, 0.6)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(12)
            msg = "No commit data in recent timeframe"
            extents = cr.text_extents(msg)
            cr.move_to((width - extents.width) / 2, height / 2 + 4)
            cr.show_text(msg)
            return

        pad_x = 16
        pad_top = 22
        pad_bottom = 26
        chart_w = width - 2 * pad_x
        chart_h = height - pad_top - pad_bottom

        counts = [item.get("count", 0) for item in self.data]
        max_count = max(counts) if counts else 1
        if max_count == 0:
            max_count = 1

        n_bars = len(self.data)
        bar_step = chart_w / n_bars
        bar_w = max(4, bar_step * 0.65)

        # Baseline rule
        cr.move_to(pad_x, pad_top + chart_h)
        cr.line_to(pad_x + chart_w, pad_top + chart_h)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.1)
        cr.set_line_width(1.0)
        cr.stroke()

        # Draw bars
        for i, item in enumerate(self.data):
            count = item.get("count", 0)
            bx = pad_x + i * bar_step + (bar_step - bar_w) / 2
            bh = (count / max_count) * chart_h if count > 0 else 3
            by = pad_top + chart_h - bh

            # Rounded bar
            rounded_rectangle(cr, bx, by, bar_w, bh, min(4, bar_w / 2))

            if count > 0:
                # Cyan-Indigo Gradient
                pat = cairo.LinearGradient(bx, by, bx, by + bh)
                pat.add_color_stop_rgba(0, 0.22, 0.74, 0.97, 0.95)  # Sky blue
                pat.add_color_stop_rgba(1, 0.39, 0.40, 0.95, 0.75)  # Indigo
                cr.set_source(pat)
            else:
                # Empty bar placeholder
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)

            cr.fill()

            # Date label for every Nth bar
            if i % max(1, n_bars // 5) == 0 or i == n_bars - 1:
                cr.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(9)
                cr.set_source_rgba(0.65, 0.68, 0.75, 0.8)
                lbl = item.get("label", "")
                extents = cr.text_extents(lbl)
                cr.move_to(bx + bar_w / 2 - extents.width / 2, height - 8)
                cr.show_text(lbl)


class PunchcardWidget(Gtk.DrawingArea):
    """Visualizes 24-hour developer focus rhythm / hourly commit activity."""
    def __init__(self):
        super().__init__()
        self.set_content_width(360)
        self.set_content_height(48)
        self.hours = [0] * 24
        self.set_draw_func(self._on_draw)

    def set_hours(self, hours):
        self.hours = hours or [0] * 24
        self.queue_draw()

    def _on_draw(self, area, cr, width, height):
        rounded_rectangle(cr, 0, 0, width, height, 10)
        cr.set_source_rgba(0.08, 0.08, 0.12, 0.6)
        cr.fill()

        rounded_rectangle(cr, 0.5, 0.5, width - 1, height - 1, 10)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.0)
        cr.stroke()

        pad_x = 12
        pad_y = 10
        total_w = width - 2 * pad_x
        cell_h = height - 2 * pad_y - 12
        cell_w = total_w / 24

        max_val = max(self.hours) if self.hours else 1
        if max_val == 0:
            max_val = 1

        for h in range(24):
            val = self.hours[h] if h < len(self.hours) else 0
            ratio = val / max_val
            x = pad_x + h * cell_w + 1.5
            w = max(2, cell_w - 3)
            y = pad_y
            rounded_rectangle(cr, x, y, w, cell_h, 2)

            if val > 0:
                # Emerald glow
                alpha = 0.25 + 0.75 * ratio
                cr.set_source_rgba(0.13, 0.85, 0.55, alpha)
            else:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.05)
            cr.fill()

        # Hour markers
        cr.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(8)
        cr.set_source_rgba(0.6, 0.62, 0.7, 0.7)
        for h in [0, 6, 12, 18, 23]:
            lbl = f"{h:02d}h"
            ext = cr.text_extents(lbl)
            x = pad_x + h * cell_w + (cell_w - ext.width) / 2
            cr.move_to(x, height - 3)
            cr.show_text(lbl)


class TrafficViewsChart(Gtk.DrawingArea):
    """Draws 14-day Page Views and Unique Visitors chart."""
    def __init__(self):
        super().__init__()
        self.set_content_width(360)
        self.set_content_height(140)
        self.history = []  # [{'date': '...', 'count': 12, 'uniques': 4}]
        self.set_draw_func(self._on_draw)

    def set_history(self, history):
        self.history = history or []
        self.queue_draw()

    def _on_draw(self, area, cr, width, height):
        rounded_rectangle(cr, 0, 0, width, height, 12)
        cr.set_source_rgba(0.08, 0.08, 0.12, 0.6)
        cr.fill()

        rounded_rectangle(cr, 0.5, 0.5, width - 1, height - 1, 12)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.0)
        cr.stroke()

        if not self.history:
            cr.set_source_rgba(0.6, 0.6, 0.7, 0.7)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(11)
            msg = "Add GitHub token to view 14-day traffic trend"
            extents = cr.text_extents(msg)
            cr.move_to((width - extents.width) / 2, height / 2 + 4)
            cr.show_text(msg)
            return

        pad_x = 20
        pad_top = 22
        pad_bottom = 24
        chart_w = width - 2 * pad_x
        chart_h = height - pad_top - pad_bottom

        max_views = max([x.get("count", 0) for x in self.history] or [1])
        if max_views == 0:
            max_views = 1

        n_pts = len(self.history)
        step = chart_w / max(1, n_pts - 1)

        # Baseline
        cr.move_to(pad_x, pad_top + chart_h)
        cr.line_to(pad_x + chart_w, pad_top + chart_h)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.1)
        cr.set_line_width(1.0)
        cr.stroke()

        # 1. Total Views line & area (Emerald)
        cr.new_path()
        cr.move_to(pad_x, pad_top + chart_h)
        for i, pt in enumerate(self.history):
            vx = pad_x + i * step
            vy = pad_top + chart_h - (pt.get("count", 0) / max_views) * chart_h
            if i == 0:
                cr.line_to(vx, vy)
            else:
                cr.line_to(vx, vy)
        cr.line_to(pad_x + (n_pts - 1) * step, pad_top + chart_h)
        cr.close_path()

        pat = cairo.LinearGradient(0, pad_top, 0, pad_top + chart_h)
        pat.add_color_stop_rgba(0, 0.13, 0.85, 0.55, 0.35)
        pat.add_color_stop_rgba(1, 0.13, 0.85, 0.55, 0.02)
        cr.set_source(pat)
        cr.fill_preserve()

        cr.set_source_rgba(0.13, 0.85, 0.55, 0.9)
        cr.set_line_width(2.0)
        cr.stroke()

        # 2. Unique Visitors line (Cyan)
        cr.new_path()
        for i, pt in enumerate(self.history):
            ux = pad_x + i * step
            uy = pad_top + chart_h - (pt.get("uniques", 0) / max_views) * chart_h
            if i == 0:
                cr.move_to(ux, uy)
            else:
                cr.line_to(ux, uy)
        cr.set_source_rgba(0.22, 0.74, 0.97, 0.9)
        cr.set_line_width(1.8)
        cr.stroke()

        # Legend at top
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9)
        cr.set_source_rgba(0.13, 0.85, 0.55, 0.9)
        cr.arc(pad_x + 6, 12, 3, 0, 2 * math.pi)
        cr.fill()
        cr.move_to(pad_x + 14, 15)
        cr.show_text("Page Views")

        cr.set_source_rgba(0.22, 0.74, 0.97, 0.9)
        cr.arc(pad_x + 90, 12, 3, 0, 2 * math.pi)
        cr.fill()
        cr.move_to(pad_x + 98, 15)
        cr.show_text("Uniques")
