#!/usr/bin/env python3
"""
GitPulse HUD — Quick Repository Switcher (Ctrl+K)
Spotlight-style instant repository navigation with live status badges.
"""

import os
import subprocess
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Pango, Gdk
from i18n import t


class QuickSwitcherDialog(Gtk.Window):
    def __init__(self, parent, recent_repos, current_repo, sound_engine, on_repo_selected, on_browse_folder):
        super().__init__(transient_for=parent, modal=True)
        self.recent_repos = recent_repos or []
        self.current_repo = current_repo or ""
        self.sound = sound_engine
        self.on_repo_selected = on_repo_selected
        self.on_browse_folder = on_browse_folder

        self.set_title(t("quick_switcher_title"))
        self.set_default_size(580, 420)
        self.add_css_class("quick-switcher-window")

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(18)
        main_box.set_margin_bottom(18)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        self.set_child(main_box)

        # Search Bar
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_box.add_css_class("switcher-search-box")
        s_icon = Gtk.Image.new_from_icon_name("system-search-symbolic")
        search_box.append(s_icon)

        self.entry = Gtk.SearchEntry()
        self.entry.set_placeholder_text(t("quick_switcher_placeholder"))
        self.entry.set_hexpand(True)
        self.entry.connect("search-changed", self._on_search_changed)
        self.entry.connect("activate", self._on_activate_first)
        search_box.append(self.entry)
        main_box.append(search_box)

        # Recent repositories section
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hdr.append(Gtk.Label(label=t("recent_repos"), css_classes=["hud-card-header"], xalign=0))
        hdr.append(Gtk.Box(hexpand=True))
        main_box.append(hdr)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scrolled.set_child(self.list_box)
        main_box.append(scrolled)

        # Bottom row
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_browse = Gtk.Button(label=t("btn_open_repo"), css_classes=["subtle-btn"])
        btn_browse.connect("clicked", self._on_browse)
        bottom_row.append(btn_browse)
        bottom_row.append(Gtk.Box(hexpand=True))

        btn_close = Gtk.Button(label=t("cancel"), css_classes=["flat"])
        btn_close.connect("clicked", lambda b: self.close())
        bottom_row.append(btn_close)
        main_box.append(bottom_row)

        # Key controller for Escape
        key_ctl = Gtk.EventControllerKey()
        key_ctl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctl)

        self._filtered_rows = []
        self._populate_list("")

    def _get_repo_quick_status(self, path):
        """Quickly gets branch and dirty status without blocking."""
        if not os.path.isdir(os.path.join(path, ".git")):
            return None, False, 0
        try:
            res_b = subprocess.run(["git", "branch", "--show-current"], cwd=path, capture_output=True, text=True, timeout=1.0)
            branch = res_b.stdout.strip() or "HEAD"
            res_s = subprocess.run(["git", "status", "--porcelain"], cwd=path, capture_output=True, text=True, timeout=1.0)
            dirty_count = len(res_s.stdout.splitlines()) if res_s.stdout else 0
            is_dirty = (dirty_count > 0)
            return branch, is_dirty, dirty_count
        except Exception:
            return "git", False, 0

    def _populate_list(self, query):
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        self._filtered_rows = []
        q = query.strip().lower()

        for path in self.recent_repos:
            if not os.path.exists(path):
                continue
            name = os.path.basename(path) or path
            if q and q not in name.lower() and q not in path.lower():
                continue

            btn = Gtk.Button()
            btn.add_css_class("switcher-item-btn")
            if os.path.abspath(path) == os.path.abspath(self.current_repo):
                btn.add_css_class("switcher-current-item")

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.set_margin_top(8)
            row.set_margin_bottom(8)
            row.set_margin_start(10)
            row.set_margin_end(10)

            folder_icon = Gtk.Image.new_from_icon_name("folder-symbolic")
            row.append(folder_icon)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            name_lbl = Gtk.Label(label=name, css_classes=["switcher-item-title"], xalign=0)
            info_box.append(name_lbl)

            path_lbl = Gtk.Label(label=path, css_classes=["switcher-item-path"], xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)
            info_box.append(path_lbl)
            row.append(info_box)

            # Status pills
            branch, is_dirty, dirty_count = self._get_repo_quick_status(path)
            if branch:
                b_badge = Gtk.Label(label=branch, css_classes=["branch-badge"])
                row.append(b_badge)

            if is_dirty:
                d_badge = Gtk.Label(label=f"● {dirty_count}", css_classes=["behind-badge"])
                row.append(d_badge)
            else:
                c_badge = Gtk.Label(label="clean", css_classes=["ahead-badge"])
                row.append(c_badge)

            btn.set_child(row)
            btn.connect("clicked", lambda b, p=path: self._select_repo(p))
            self.list_box.append(btn)
            self._filtered_rows.append(path)

    def _on_search_changed(self, entry):
        self._populate_list(entry.get_text())

    def _on_activate_first(self, entry):
        if self._filtered_rows:
            self._select_repo(self._filtered_rows[0])

    def _select_repo(self, path):
        self.sound.play("click")
        if self.on_repo_selected:
            self.on_repo_selected(path)
        self.close()

    def _on_browse(self, btn):
        self.close()
        if self.on_browse_folder:
            self.on_browse_folder()

    def _on_key_pressed(self, ctl, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
