#!/usr/bin/env python3
"""
GitPulse HUD — Stash Shelf & Inspector Dialog
Inspect, apply, pop, and drop git stashes with instant diff preview.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Pango
from i18n import t, format_relative_time


class StashInspectorDialog(Gtk.Window):
    def __init__(self, parent, git_engine, sound_engine, on_changed=None):
        super().__init__(transient_for=parent, modal=True)
        self.git = git_engine
        self.sound = sound_engine
        self.on_changed = on_changed
        self.selected_index = None

        self.set_title(t("stash_shelf"))
        self.set_default_size(840, 520)
        self.add_css_class("stash-dialog-window")

        # Header Bar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(
            title=t("stash_shelf"),
            subtitle=t("stash_shelf_sub")
        )
        header.set_title_widget(title_widget)
        self.set_titlebar(header)

        # Main horizontal split
        self.content_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.content_paned.set_position(310)
        self.content_paned.set_vexpand(True)
        self.content_paned.set_hexpand(True)
        self.set_child(self.content_paned)

        # Left: Stash list
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left_box.set_margin_top(12)
        left_box.set_margin_bottom(12)
        left_box.set_margin_start(14)
        left_box.set_margin_end(8)
        left_box.set_size_request(280, -1)

        scrolled_left = Gtk.ScrolledWindow()
        scrolled_left.set_vexpand(True)
        scrolled_left.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.stash_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scrolled_left.set_child(self.stash_list_box)
        left_box.append(scrolled_left)

        self.content_paned.set_start_child(left_box)

        # Right: Diff preview and actions
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_box.set_margin_top(12)
        right_box.set_margin_bottom(12)
        right_box.set_margin_start(8)
        right_box.set_margin_end(14)
        right_box.set_hexpand(True)

        scrolled_diff = Gtk.ScrolledWindow()
        scrolled_diff.set_vexpand(True)
        scrolled_diff.set_hexpand(True)

        self.diff_view = Gtk.TextView()
        self.diff_view.set_editable(False)
        self.diff_view.set_cursor_visible(False)
        self.diff_view.set_monospace(True)
        self.diff_view.set_left_margin(12)
        self.diff_view.set_right_margin(12)
        self.diff_view.set_top_margin(10)
        self.diff_view.set_bottom_margin(10)
        self.diff_buffer = self.diff_view.get_buffer()
        scrolled_diff.set_child(self.diff_view)
        right_box.append(scrolled_diff)

        # Bottom Action Bar
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_row.set_halign(Gtk.Align.END)

        self.btn_apply = Gtk.Button(label=t("apply"))
        self.btn_apply.add_css_class("subtle-btn")
        self.btn_apply.connect("clicked", self._on_apply)
        action_row.append(self.btn_apply)

        self.btn_pop = Gtk.Button(label=t("pop"))
        self.btn_pop.add_css_class("primary-btn")
        self.btn_pop.connect("clicked", self._on_pop)
        action_row.append(self.btn_pop)

        self.btn_drop = Gtk.Button(label=t("drop"))
        self.btn_drop.add_css_class("destructive-action")
        self.btn_drop.connect("clicked", self._on_drop)
        action_row.append(self.btn_drop)

        right_box.append(action_row)
        self.content_paned.set_end_child(right_box)

        self._reload_stashes()

    def _reload_stashes(self):
        while child := self.stash_list_box.get_first_child():
            self.stash_list_box.remove(child)

        stashes = self.git.stash_list()
        if not stashes:
            self.diff_buffer.set_text(t("no_stashes"))
            self.btn_apply.set_sensitive(False)
            self.btn_pop.set_sensitive(False)
            self.btn_drop.set_sensitive(False)
            empty_lbl = Gtk.Label(label=t("no_stashes"), css_classes=["stat-label"])
            empty_lbl.set_wrap(True)
            empty_lbl.set_margin_top(40)
            self.stash_list_box.append(empty_lbl)
            self.selected_index = None
            return

        self.btn_apply.set_sensitive(True)
        self.btn_pop.set_sensitive(True)
        self.btn_drop.set_sensitive(True)

        for s in stashes:
            row = Gtk.Button()
            row.add_css_class("stash-item-btn")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            box.set_margin_start(8)
            box.set_margin_end(8)

            top_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            idx_badge = Gtk.Label(label=f"stash@{{{s['index']}}}", css_classes=["branch-badge"])
            top_line.append(idx_badge)
            top_line.append(Gtk.Box(hexpand=True))
            d_lbl = Gtk.Label(label=format_relative_time(s["date"]), css_classes=["stat-label"])
            top_line.append(d_lbl)
            box.append(top_line)

            msg_lbl = Gtk.Label(label=s["message"], xalign=0, ellipsize=Pango.EllipsizeMode.END)
            box.append(msg_lbl)

            row.set_child(box)
            row.connect("clicked", lambda b, idx=s["index"]: self._select_stash(idx))
            self.stash_list_box.append(row)

        # Select first stash by default
        self._select_stash(stashes[0]["index"])

    def _select_stash(self, index):
        self.selected_index = index
        diff_text = self.git.stash_diff(index)
        self._populate_diff(diff_text)
        self.sound.play("click")

    def _populate_diff(self, diff_text):
        buf = self.diff_buffer
        buf.set_text("")

        # Create styling tags if not existing
        table = buf.get_tag_table()
        if not table.lookup("add"):
            buf.create_tag("add", foreground="#3fb950", background="rgba(46, 160, 67, 0.15)")
            buf.create_tag("del", foreground="#f85149", background="rgba(248, 81, 73, 0.15)")
            buf.create_tag("hunk", foreground="#58a6ff", weight=Pango.Weight.BOLD)
            buf.create_tag("header", foreground="#8b949e", weight=Pango.Weight.BOLD)

        tag_add = table.lookup("add")
        tag_del = table.lookup("del")
        tag_hunk = table.lookup("hunk")
        tag_header = table.lookup("header")

        for line in diff_text.splitlines():
            iter_end = buf.get_end_iter()
            if line.startswith("+++") or line.startswith("---") or line.startswith("diff ") or line.startswith("index "):
                buf.insert_with_tags(iter_end, line + "\n", tag_header)
            elif line.startswith("@@"):
                buf.insert_with_tags(iter_end, line + "\n", tag_hunk)
            elif line.startswith("+"):
                buf.insert_with_tags(iter_end, line + "\n", tag_add)
            elif line.startswith("-"):
                buf.insert_with_tags(iter_end, line + "\n", tag_del)
            else:
                buf.insert(iter_end, line + "\n")

    def _on_apply(self, btn):
        if self.selected_index is None:
            return
        ok, out = self.git.stash_apply(self.selected_index)
        if ok:
            self.sound.play("commit")
            if self.on_changed:
                self.on_changed()
            self.close()
        else:
            self.sound.play("error")

    def _on_pop(self, btn):
        if self.selected_index is None:
            return
        ok, out = self.git.stash_pop(self.selected_index)
        if ok:
            self.sound.play("commit")
            if self.on_changed:
                self.on_changed()
            self.close()
        else:
            self.sound.play("error")

    def _on_drop(self, btn):
        if self.selected_index is None:
            return
        ok, out = self.git.stash_drop(self.selected_index)
        if ok:
            self.sound.play("pop")
            self._reload_stashes()
            if self.on_changed:
                self.on_changed()
        else:
            self.sound.play("error")
