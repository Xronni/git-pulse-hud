#!/usr/bin/env python3
"""
GitPulse HUD — Clean GitHub/VSCode Style Diff Viewer
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Pango
from i18n import t


class DiffViewerDialog(Gtk.Window):
    def __init__(self, parent, filename, diff_text, is_staged=False, on_stage_toggle=None):
        super().__init__(transient_for=parent, modal=True)
        self.set_title(f"{t('diff_title')} — {filename}")
        self.set_default_size(780, 540)
        self.add_css_class("diff-window-view")

        self.filename = filename
        self.is_staged = is_staged
        self.on_stage_toggle = on_stage_toggle

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)

        # Header Bar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(
            title=filename,
            subtitle=t("staged_diff_sub") if is_staged else t("unstaged_diff_sub")
        )
        header.set_title_widget(title_widget)

        # Quick action button in header
        btn_action = Gtk.Button(label=t("unstage_file") if is_staged else t("stage_file"))
        btn_action.add_css_class("suggested-action" if not is_staged else "destructive-action")
        btn_action.connect("clicked", self._on_action_clicked)
        header.pack_end(btn_action)

        main_box.append(header)

        # Diff Scrolled Window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        main_box.append(scrolled)

        # Text View for diff
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_monospace(True)
        text_view.set_left_margin(16)
        text_view.set_right_margin(16)
        text_view.set_top_margin(12)
        text_view.set_bottom_margin(12)
        scrolled.set_child(text_view)

        buffer = text_view.get_buffer()
        self._populate_diff(buffer, diff_text)

    def _populate_diff(self, buffer, diff_text):
        tag_add = buffer.create_tag("add", foreground="#3fb950", background="rgba(46, 160, 67, 0.15)")
        tag_del = buffer.create_tag("del", foreground="#f85149", background="rgba(248, 81, 73, 0.15)")
        tag_hunk = buffer.create_tag("hunk", foreground="#58a6ff", weight=Pango.Weight.BOLD)
        tag_header = buffer.create_tag("header", foreground="#8b949e", weight=Pango.Weight.BOLD)

        lines = diff_text.splitlines()
        if not lines:
            iter_end = buffer.get_end_iter()
            buffer.insert(iter_end, t("no_diff_detected"))
            return

        for line in lines:
            iter_end = buffer.get_end_iter()
            if line.startswith("+++") or line.startswith("---") or line.startswith("diff ") or line.startswith("index "):
                buffer.insert_with_tags(iter_end, line + "\n", tag_header)
            elif line.startswith("@@"):
                buffer.insert_with_tags(iter_end, line + "\n", tag_hunk)
            elif line.startswith("+"):
                buffer.insert_with_tags(iter_end, line + "\n", tag_add)
            elif line.startswith("-"):
                buffer.insert_with_tags(iter_end, line + "\n", tag_del)
            else:
                buffer.insert(iter_end, line + "\n")

    def _on_action_clicked(self, btn):
        if self.on_stage_toggle:
            self.on_stage_toggle(self.filename, self.is_staged)
        self.close()
