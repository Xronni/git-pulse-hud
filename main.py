#!/usr/bin/env python3
"""
GitPulse HUD — Professional GTK4 / Libadwaita Git Companion
Author: Xronni (https://github.com/Xronni)
"""

import sys
import os
import json
import threading
from datetime import datetime

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Adw, Gdk, GdkPixbuf, GLib, Pango

from git_engine import GitEngine
from sound_engine import SoundEngine
from github_telemetry import GitHubTelemetry
from pulse_widget import CommitVelocityWidget, PunchcardWidget, TrafficViewsChart, BranchGraphNodeWidget
from diff_viewer import DiffViewerDialog
from secret_scanner import scan_staged_files
from stash_dialog import StashInspectorDialog
from release_dialog import ReleaseDrafterDialog
from quick_switcher import QuickSwitcherDialog
import i18n
from i18n import t

CONFIG_DIR = os.path.expanduser("~/.config/git-pulse")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CSS_FILE = os.path.join(APP_DIR, "style.css")
ICON_FILE = os.path.join(APP_DIR, "assets", "icon.png")


def plural_ru(n, one, few, many):
    try:
        n = int(n)
    except (ValueError, TypeError):
        return f"{n} {many}"
    if n % 10 == 1 and n % 100 != 11:
        return one
    elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return few
    else:
        return many


class GitPulseWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("GitPulse")

        self.config = self._load_config()
        i18n.set_language(self.config.get("language", "en"))

        win_w = self.config.get("window_width", 980)
        win_h = self.config.get("window_height", 680)
        self.set_default_size(max(980, win_w), max(680, win_h))
        self.set_size_request(940, 620)
        self.add_css_class("git-pulse-window")

        self.sound = SoundEngine(enabled=self.config.get("sound_enabled", True))
        
        initial_repo = self.config.get("last_repo", "")
        if initial_repo and os.path.exists(initial_repo):
            self.git = GitEngine(initial_repo)
        else:
            self.git = GitEngine("")

        self.telemetry = GitHubTelemetry(token=self.config.get("github_token", ""))
        self.active_view = "changes"
        self.selected_type = "feat"
        self.last_scan_findings = []

        self.config.setdefault("recent_repos", [])
        if initial_repo and os.path.exists(initial_repo):
            if initial_repo not in self.config["recent_repos"]:
                self.config["recent_repos"].insert(0, initial_repo)

        # Global key controller (Ctrl+K for Quick Switcher)
        key_ctl = Gtk.EventControllerKey()
        key_ctl.connect("key-pressed", self._on_global_key_pressed)
        self.add_controller(key_ctl)

        self._refresh_timer_id = None
        self._refresh_finish_timer_id = None

        self._build_main_layout()
        self._update_all_strings()
        self._load_repo_data()

        # Prompt for repo selection on first launch or if repository is not set
        if not self.config.get("first_run_completed") or not self.git.is_valid():
            GLib.idle_add(lambda: self._prompt_first_run_repo())

        self.connect("close-request", self._on_window_close)

    def _on_window_close(self, win):
        curr_w = self.get_width()
        curr_h = self.get_height()
        if curr_w >= 900 and curr_h >= 600:
            self.config["window_width"] = curr_w
            self.config["window_height"] = curr_h
        self._save_config()
        return False

    def _prompt_first_run_repo(self):
        self._on_choose_repo(None)

    def _load_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        default_cfg = {
            "last_repo": "",
            "sound_enabled": True,
            "language": "en",
            "github_token": "",
            "recent_repos": [],
            "first_run_completed": False,
            "window_width": 980,
            "window_height": 680
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        default_cfg.update(loaded)
            except Exception as e:
                print(f"[Config] Error loading config: {e}")
        return default_cfg

    def _save_config(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp_file = CONFIG_FILE + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, CONFIG_FILE)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def _build_main_layout(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(root_box)

        # 1. Left Navigation Sidebar
        self._build_sidebar(root_box)

        # 2. Main Content Overlay (contains stack + floating HUD banner)
        self.content_overlay = Gtk.Overlay()
        self.content_overlay.set_hexpand(True)
        self.content_overlay.set_vexpand(True)
        root_box.append(self.content_overlay)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.content_box.add_css_class("content-area")
        self.content_box.set_hexpand(True)
        self.content_box.set_vexpand(True)
        self.content_overlay.set_child(self.content_box)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(180)
        self.stack.set_vexpand(True)
        self.content_box.append(self.stack)

        # Floating HUD Notification Banner with Spinner (smooth revealer)
        self.refresh_revealer = Gtk.Revealer()
        self.refresh_revealer.set_can_focus(False)
        self.refresh_revealer.set_focusable(False)
        self.refresh_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.refresh_revealer.set_transition_duration(280)
        self.refresh_revealer.set_valign(Gtk.Align.START)
        self.refresh_revealer.set_halign(Gtk.Align.CENTER)
        self.refresh_revealer.set_margin_top(14)

        self.refresh_banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.refresh_banner.set_can_focus(False)
        self.refresh_banner.set_focusable(False)
        self.refresh_banner.add_css_class("refresh-banner")
        self.refresh_spinner = Gtk.Spinner()
        self.refresh_spinner.set_can_focus(False)
        self.refresh_spinner.set_focusable(False)
        self.refresh_banner.append(self.refresh_spinner)
        self.refresh_lbl = Gtk.Label(label=t("refreshing"))
        self.refresh_lbl.set_can_focus(False)
        self.refresh_lbl.set_focusable(False)
        self.refresh_lbl.add_css_class("refresh-banner-text")
        self.refresh_banner.append(self.refresh_lbl)

        self.refresh_revealer.set_child(self.refresh_banner)
        self.refresh_revealer.set_reveal_child(False)
        self.content_overlay.add_overlay(self.refresh_revealer)

        self._build_view_changes()
        self._build_view_history()
        self._build_view_pulse()
        self._build_view_telemetry()

    def _build_sidebar(self, parent):
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.add_css_class("sidebar-box")
        sidebar.set_size_request(240, -1)
        sidebar.set_hexpand(False)
        parent.append(sidebar)

        # Brand Header with clean transparent squircle icon
        brand_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        if os.path.exists(ICON_FILE):
            icon_img = Gtk.Image.new_from_file(ICON_FILE)
            icon_img.set_pixel_size(36)
            brand_row.append(icon_img)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        top_t = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_title = Gtk.Label(label="GitPulse")
        lbl_title.add_css_class("brand-title")
        lbl_title.set_xalign(0)
        top_t.append(lbl_title)

        lbl_badge = Gtk.Label(label="HUD")
        lbl_badge.add_css_class("brand-badge")
        top_t.append(lbl_badge)
        title_box.append(top_t)

        self.lbl_sub = Gtk.Label(label=t("app_subtitle"))
        self.lbl_sub.add_css_class("brand-subtitle")
        self.lbl_sub.set_ellipsize(Pango.EllipsizeMode.END)
        self.lbl_sub.set_max_width_chars(20)
        self.lbl_sub.set_xalign(0)
        title_box.append(self.lbl_sub)

        brand_row.append(title_box)
        sidebar.append(brand_row)

        # Active Repository Card
        repo_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        repo_card.add_css_class("sidebar-repo-card")
        repo_card.set_tooltip_text(t("quick_switcher_placeholder"))
        repo_click = Gtk.GestureClick()
        repo_click.connect("pressed", lambda g, n, x, y: self._on_open_quick_switcher())
        repo_card.add_controller(repo_click)

        top_r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.sidebar_repo_name = Gtk.Label(label=self.git.get_repo_name())
        self.sidebar_repo_name.add_css_class("repo-name-text")
        self.sidebar_repo_name.set_ellipsize(Pango.EllipsizeMode.END)
        self.sidebar_repo_name.set_xalign(0)
        self.sidebar_repo_name.set_hexpand(True)
        top_r.append(self.sidebar_repo_name)

        self.btn_open_repo = Gtk.Button()
        self.btn_open_repo.set_icon_name("folder-open-symbolic")
        self.btn_open_repo.set_tooltip_text(t("btn_open_repo"))
        self.btn_open_repo.add_css_class("subtle-icon-btn")
        self.btn_open_repo.connect("clicked", self._on_choose_repo)
        top_r.append(self.btn_open_repo)
        repo_card.append(top_r)

        pills_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.sidebar_branch = Gtk.Label(label=self.git.get_current_branch())
        self.sidebar_branch.add_css_class("branch-badge")
        pills_row.append(self.sidebar_branch)

        self.sidebar_ahead = Gtk.Label(label="↑0 ↓0")
        self.sidebar_ahead.add_css_class("ahead-badge")
        pills_row.append(self.sidebar_ahead)

        repo_card.append(pills_row)
        sidebar.append(repo_card)

        # Navigation Buttons
        self.nav_buttons = {}
        items = [
            ("changes", "document-edit-symbolic", "tab_changes"),
            ("history", "document-open-recent-symbolic", "tab_history"),
            ("pulse", "utilities-system-monitor-symbolic", "tab_pulse"),
            ("telemetry", "network-workgroup-symbolic", "tab_telemetry"),
        ]

        for nav_id, icon_name, trans_key in items:
            btn = Gtk.Button()
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            img = Gtk.Image.new_from_icon_name(icon_name)
            lbl = Gtk.Label(label=t(trans_key))
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_max_width_chars(18)
            lbl.set_xalign(0)
            lbl.set_hexpand(True)
            btn_box.append(img)
            btn_box.append(lbl)
            btn.set_child(btn_box)
            btn.add_css_class("nav-btn")
            if nav_id == "changes":
                btn.add_css_class("active")
            btn.connect("clicked", lambda b, nid=nav_id: self._switch_nav(nid))
            sidebar.append(btn)
            self.nav_buttons[nav_id] = (btn, lbl, trans_key)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)

        # Footer Segmented Controls
        footer_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        footer_card.add_css_class("sidebar-footer")

        self.btn_sound = Gtk.Button()
        self.btn_sound.set_icon_name("audio-volume-high-symbolic" if self.sound.enabled else "audio-volume-muted-symbolic")
        self.btn_sound.set_tooltip_text(t("sound_fx"))
        self.btn_sound.add_css_class("footer-btn")
        self.btn_sound.set_hexpand(True)
        self.btn_sound.connect("clicked", self._on_toggle_sound)
        footer_card.append(self.btn_sound)

        self.btn_lang = Gtk.Button(label="EN" if i18n.get_language() == "en" else "RU")
        self.btn_lang.set_tooltip_text(t("lang_toggle_tooltip"))
        self.btn_lang.add_css_class("footer-btn")
        self.btn_lang.set_hexpand(True)
        self.btn_lang.connect("clicked", self._on_toggle_lang)
        footer_card.append(self.btn_lang)

        self.btn_token_cfg = Gtk.Button()
        self.btn_token_cfg.set_icon_name("dialog-password-symbolic")
        self.btn_token_cfg.set_tooltip_text(t("token_guide_title"))
        self.btn_token_cfg.add_css_class("footer-btn")
        self.btn_token_cfg.set_hexpand(True)
        self.btn_token_cfg.connect("clicked", self._on_token_dialog)
        footer_card.append(self.btn_token_cfg)

        self.btn_refresh_ui = Gtk.Button()
        self.btn_refresh_ui.set_tooltip_text(t("btn_refresh"))
        self.btn_refresh_ui.add_css_class("footer-btn")
        self.btn_refresh_ui.set_hexpand(True)

        self.btn_refresh_stack = Gtk.Stack()
        self.btn_refresh_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic")
        self.btn_refresh_spinner = Gtk.Spinner()
        self.btn_refresh_stack.add_named(self.btn_refresh_icon, "icon")
        self.btn_refresh_stack.add_named(self.btn_refresh_spinner, "spinner")
        self.btn_refresh_stack.set_visible_child_name("icon")
        self.btn_refresh_ui.set_child(self.btn_refresh_stack)

        self.btn_refresh_ui.connect("clicked", lambda b: self._on_refresh_clicked())
        footer_card.append(self.btn_refresh_ui)

        sidebar.append(footer_card)

    def _switch_nav(self, nav_id):
        self.active_view = nav_id
        self.sound.play("click")
        for nid, (btn, lbl, key) in self.nav_buttons.items():
            if nid == nav_id:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

        self.stack.set_visible_child_name(nav_id)
        if nav_id == "history":
            self._refresh_history_view()
        elif nav_id == "pulse":
            self._refresh_pulse_view()
        elif nav_id == "telemetry":
            self._refresh_telemetry_view()

    # --- VIEW 1: CHANGES & STAGING ---

    def _build_view_changes(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.lbl_view1_title = Gtk.Label(label=t("tab_changes"), css_classes=["view-title"], xalign=0)
        self.lbl_view1_title.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.lbl_view1_title)
        self.lbl_changes_sub = Gtk.Label(label=t("sub_changes"), css_classes=["view-subtitle"], xalign=0)
        self.lbl_changes_sub.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.lbl_changes_sub)
        top_row.append(title_box)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_row.append(spacer)

        self.btn_stash_shelf = Gtk.Button(label=f"📦 {t('stashes')}")
        self.btn_stash_shelf.add_css_class("subtle-btn")
        self.btn_stash_shelf.connect("clicked", lambda b: self._on_open_stashes())
        top_row.append(self.btn_stash_shelf)

        self.btn_publish_top = Gtk.Button(label=f"☁️ {t('publish_btn')}")
        self.btn_publish_top.add_css_class("suggested-action")
        self.btn_publish_top.connect("clicked", self._on_publish_dialog)
        self.btn_publish_top.set_visible(False)
        top_row.append(self.btn_publish_top)

        self.btn_push_only = Gtk.Button(label=f"↑ {t('btn_push')}")
        self.btn_push_only.add_css_class("primary-btn")
        self.btn_push_only.connect("clicked", lambda b: self._do_push())
        self.btn_push_only.set_visible(False)
        top_row.append(self.btn_push_only)

        page.append(top_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.append(scrolled)

        self.files_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.set_child(self.files_container)

        # Commit Composer Card
        commit_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        commit_card.add_css_class("hud-card")

        self.lbl_composer_hdr = Gtk.Label(label=t("commit_builder"), css_classes=["hud-card-header"], xalign=0)
        commit_card.append(self.lbl_composer_hdr)

        # Conventional Commit Type Chips
        types_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.type_chips = {}
        conventional_types = ["feat", "fix", "refactor", "docs", "perf", "chore", "test", "style"]
        for ctype in conventional_types:
            chip = Gtk.Button(label=ctype)
            chip.add_css_class("chip-btn")
            if ctype == "feat":
                chip.add_css_class("active")
            chip.connect("clicked", lambda b, ct=ctype: self._select_type(ct))
            types_row.append(chip)
            self.type_chips[ctype] = chip

        types_row.append(Gtk.Box(hexpand=True))

        self.check_breaking = Gtk.CheckButton(label=t("breaking_change"))
        self.check_breaking.connect("toggled", lambda *a: self._update_commit_preview())
        types_row.append(self.check_breaking)

        commit_card.append(types_row)

        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry_scope = Gtk.Entry()
        self.entry_scope.set_placeholder_text(t("commit_scope_placeholder"))
        self.entry_scope.set_width_chars(16)
        self.entry_scope.connect("changed", lambda *a: self._update_commit_preview())
        input_row.append(self.entry_scope)

        self.entry_desc = Gtk.Entry()
        self.entry_desc.set_placeholder_text(t("commit_desc_placeholder"))
        self.entry_desc.set_hexpand(True)
        self.entry_desc.connect("changed", lambda *a: self._update_commit_preview())
        self.entry_desc.connect("activate", lambda *a: self._on_commit())
        input_row.append(self.entry_desc)

        commit_card.append(input_row)

        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.preview_lbl = Gtk.Label(label="feat: ...")
        self.preview_lbl.add_css_class("commit-preview-box")
        self.preview_lbl.set_xalign(0)
        self.preview_lbl.set_hexpand(True)
        bottom_row.append(self.preview_lbl)

        # Pre-Commit Security Scanner Pill
        self.scanner_status_pill = Gtk.Button(label=f"🛡️ {t('scanner_clean')}")
        self.scanner_status_pill.add_css_class("scanner-pill-clean")
        self.scanner_status_pill.connect("clicked", self._on_scanner_pill_clicked)
        bottom_row.append(self.scanner_status_pill)

        self.btn_commit = Gtk.Button(label=t("btn_commit"))
        self.btn_commit.add_css_class("subtle-btn")
        self.btn_commit.connect("clicked", lambda b: self._on_commit(push=False))
        bottom_row.append(self.btn_commit)

        self.btn_commit_push = Gtk.Button(label=t("btn_commit_push"))
        self.btn_commit_push.add_css_class("primary-btn")
        self.btn_commit_push.connect("clicked", lambda b: self._on_commit(push=True))
        bottom_row.append(self.btn_commit_push)

        commit_card.append(bottom_row)
        page.append(commit_card)

        self.stack.add_named(page, "changes")

    def _select_type(self, ctype):
        self.selected_type = ctype
        self.sound.play("click")
        for ct, chip in self.type_chips.items():
            if ct == ctype:
                chip.add_css_class("active")
            else:
                chip.remove_css_class("active")
        self._update_commit_preview()

    def _update_commit_preview(self):
        scope = self.entry_scope.get_text().strip()
        desc = self.entry_desc.get_text().strip() or "..."
        breaking = "!" if self.check_breaking.get_active() else ""
        if scope:
            full = f"{self.selected_type}({scope}){breaking}: {desc}"
        else:
            full = f"{self.selected_type}{breaking}: {desc}"
        self.preview_lbl.set_text(full)

    # --- VIEW 2: COMMIT HISTORY ---

    def _build_view_history(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.lbl_view2_title = Gtk.Label(label=t("tab_history"), css_classes=["view-title"], xalign=0)
        self.lbl_view2_title.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.lbl_view2_title)
        self.lbl_hist_sub = Gtk.Label(label=t("sub_history"), css_classes=["view-subtitle"], xalign=0)
        self.lbl_hist_sub.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.lbl_hist_sub)
        top_row.append(title_box)
        top_row.append(Gtk.Box(hexpand=True))

        self.btn_branch_switch = Gtk.Button(label="🌿 main ▾", css_classes=["branch-switch-btn"])
        self.btn_branch_switch.connect("clicked", self._on_branch_switcher_clicked)
        top_row.append(self.btn_branch_switch)

        page.append(top_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.append(scrolled)

        self.history_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scrolled.set_child(self.history_container)

        self.stack.add_named(page, "history")

    def _refresh_history_view(self):
        while child := self.history_container.get_first_child():
            self.history_container.remove(child)

        if not self.git.is_valid():
            self.btn_branch_switch.set_label("🌿 — ▾")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(60)
            box.set_margin_bottom(60)
            box.set_halign(Gtk.Align.CENTER)
            icon = Gtk.Image.new_from_icon_name("folder-open-symbolic")
            icon.set_pixel_size(44)
            box.append(icon)
            lbl = Gtk.Label(label=t("no_repo_title"), css_classes=["view-title"])
            box.append(lbl)
            sub = Gtk.Label(label=t("no_repo_desc"), css_classes=["view-subtitle"])
            box.append(sub)
            self.history_container.append(box)
            return

        cur_branch = self.git.get_current_branch()
        self.btn_branch_switch.set_label(f"🌿 {cur_branch} ▾")

        commits = self.git.get_commit_graph(45)
        if not commits:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(60)
            box.set_margin_bottom(60)
            box.set_halign(Gtk.Align.CENTER)
            icon = Gtk.Image.new_from_icon_name("document-open-recent-symbolic")
            icon.set_pixel_size(44)
            box.append(icon)
            lbl = Gtk.Label(label=t("no_velocity_title"), css_classes=["view-title"])
            box.append(lbl)
            sub = Gtk.Label(label=t("no_velocity_desc"), css_classes=["view-subtitle"])
            box.append(sub)
            self.history_container.append(box)
            return

        for c in commits:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("file-item-row")

            # Cairo Branch Graph Node
            graph_node = BranchGraphNodeWidget(
                col=c.get("col", 0),
                max_cols=c.get("max_cols", 1),
                is_merge=c.get("is_merge", False)
            )
            row.append(graph_node)

            btn_hash = Gtk.Button(label=c["hash"])
            btn_hash.add_css_class("subtle-btn")
            btn_hash.set_tooltip_text(t("copy_hash"))
            btn_hash.connect("clicked", lambda b, h=c["hash"]: self._copy_to_clipboard(h))
            row.append(btn_hash)

            if c.get("branch"):
                b_lbl = Gtk.Label(label=c["branch"], css_classes=["branch-badge"])
                row.append(b_lbl)

            msg_lbl = Gtk.Label(label=c["message"])
            msg_lbl.set_xalign(0)
            msg_lbl.set_hexpand(True)
            msg_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(msg_lbl)

            author_lbl = Gtk.Label(label=c["author"])
            author_lbl.add_css_class("stat-label")
            row.append(author_lbl)

            date_lbl = Gtk.Label(label=i18n.format_relative_time(c["relative_date"]))
            date_lbl.add_css_class("stat-label")
            row.append(date_lbl)

            self.history_container.append(row)

    # --- VIEW 3: REPO PULSE & ANALYTICS ---

    def _build_view_pulse(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.lbl_view3_title = Gtk.Label(label=t("tab_pulse"), css_classes=["view-title"], xalign=0)
        self.lbl_view3_title.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.lbl_view3_title)
        self.lbl_pulse_sub = Gtk.Label(label=t("sub_pulse"), css_classes=["view-subtitle"], xalign=0)
        self.lbl_pulse_sub.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.lbl_pulse_sub)
        top_row.append(title_box)
        page.append(top_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.append(scrolled)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        scrolled.set_child(inner)

        stats_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.card_commits = self._make_metric_card("0", t("stat_commits"))
        self.card_authors = self._make_metric_card("0", t("stat_contributors"))
        self.card_files = self._make_metric_card("0", t("stat_files"))
        self.card_stashes = self._make_metric_card("0", t("stat_stashes"))
        self.card_stashes.add_css_class("clickable-card")
        self.card_stashes.set_tooltip_text(t("stash_shelf"))
        stash_click = Gtk.GestureClick()
        stash_click.connect("pressed", lambda g, n, x, y: self._on_open_stashes())
        self.card_stashes.add_controller(stash_click)

        for c in [self.card_commits, self.card_authors, self.card_files, self.card_stashes]:
            c.set_hexpand(True)
            stats_row.append(c)
        inner.append(stats_row)

        vel_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vel_card.add_css_class("hud-card")
        self.lbl_vel_hdr = Gtk.Label(label=t("velocity_title"), css_classes=["hud-card-header"], xalign=0)
        self.lbl_vel_hdr.set_ellipsize(Pango.EllipsizeMode.END)
        vel_card.append(self.lbl_vel_hdr)
        self.vel_chart = CommitVelocityWidget()
        vel_card.append(self.vel_chart)
        inner.append(vel_card)

        punch_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        punch_card.add_css_class("hud-card")
        self.lbl_punch_hdr = Gtk.Label(label=t("punchcard_title"), css_classes=["hud-card-header"], xalign=0)
        self.lbl_punch_hdr.set_ellipsize(Pango.EllipsizeMode.END)
        punch_card.append(self.lbl_punch_hdr)
        self.punchcard = PunchcardWidget()
        punch_card.append(self.punchcard)
        inner.append(punch_card)

        self.stack.add_named(page, "pulse")

    def _make_metric_card(self, value_text, label_text):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("metric-card")
        
        lbl_v = Gtk.Label(label=value_text, css_classes=["metric-number"], xalign=0)
        card.append(lbl_v)

        lbl_l = Gtk.Label(label=label_text, css_classes=["metric-label"], xalign=0)
        lbl_l.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_l.set_max_width_chars(15)
        card.append(lbl_l)
        
        card.val_widget = lbl_v
        card.lbl_widget = lbl_l
        return card

    def _refresh_pulse_view(self):
        if not self.git.is_valid():
            self.card_commits.val_widget.set_text("—")
            self.card_authors.val_widget.set_text("—")
            self.card_files.val_widget.set_text("—")
            self.card_stashes.val_widget.set_text("—")
            self.vel_chart.set_data([])
            self.punchcard.set_hours([0] * 24)
            return
        summary = self.git.get_repo_summary()
        c_count = int(summary["total_commits"])
        a_count = int(summary["contributors"])
        f_count = int(summary["files_count"])
        s_count = int(summary["stashes"])

        self.card_commits.val_widget.set_text(str(c_count))
        self.card_authors.val_widget.set_text(str(a_count))
        self.card_files.val_widget.set_text(str(f_count))
        self.card_stashes.val_widget.set_text(str(s_count))

        if i18n.get_language() == "ru":
            self.card_commits.lbl_widget.set_text(plural_ru(c_count, "коммит", "коммита", "коммитов"))
            self.card_authors.lbl_widget.set_text(plural_ru(a_count, "автор", "автора", "авторов"))
            self.card_files.lbl_widget.set_text(plural_ru(f_count, "файл", "файла", "файлов"))
            self.card_stashes.lbl_widget.set_text(plural_ru(s_count, "в тайнике", "в тайнике", "в тайнике"))
        else:
            self.card_commits.lbl_widget.set_text("Commits")
            self.card_authors.lbl_widget.set_text("Authors")
            self.card_files.lbl_widget.set_text("Files")
            self.card_stashes.lbl_widget.set_text("In Stash")

        self.vel_chart.set_data(self.git.get_commit_velocity(14))
        self.punchcard.set_hours(self.git.get_punchcard())

    # --- VIEW 4: GITHUB TELEMETRY ---

    def _build_view_telemetry(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.lbl_view4_title = Gtk.Label(label=t("tab_telemetry"), css_classes=["view-title"], xalign=0)
        self.lbl_view4_title.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.lbl_view4_title)
        self.lbl_telem_sub = Gtk.Label(label=t("sub_telemetry"), css_classes=["view-subtitle"], xalign=0)
        self.lbl_telem_sub.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.lbl_telem_sub)
        top_row.append(title_box)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_row.append(spacer)

        self.btn_tok = Gtk.Button(label=t("token_settings"))
        self.btn_tok.add_css_class("subtle-btn")
        self.btn_tok.connect("clicked", self._on_token_dialog)
        top_row.append(self.btn_tok)

        self.btn_draft_rel = Gtk.Button(label=t("draft_release"))
        self.btn_draft_rel.add_css_class("primary-btn")
        self.btn_draft_rel.connect("clicked", lambda b: self._open_release_drafter())
        top_row.append(self.btn_draft_rel)

        page.append(top_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.append(scrolled)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        scrolled.set_child(inner)

        metrics_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.ins_views = self._make_metric_card("—", t("views_14d"))
        self.ins_uniques = self._make_metric_card("—", t("uniques_14d"))
        self.ins_stars = self._make_metric_card("0", t("stars"))
        self.ins_forks = self._make_metric_card("0", t("forks"))
        self.ins_downloads = self._make_metric_card("0", t("downloads"))
        self.ins_issues = self._make_metric_card("0", t("open_issues"))

        for c in [self.ins_views, self.ins_uniques, self.ins_stars, self.ins_forks, self.ins_downloads, self.ins_issues]:
            c.set_hexpand(True)
            metrics_row.append(c)
        inner.append(metrics_row)

        # Explanatory Token Banner Card
        self.token_banner_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.token_banner_card.add_css_class("token-banner-card")

        t_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        t_icon.set_pixel_size(24)
        self.token_banner_card.append(t_icon)

        t_textbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        t_textbox.set_hexpand(True)
        self.lbl_token_banner_title = Gtk.Label(label=t("token_banner_title"), css_classes=["token-banner-title"], xalign=0)
        self.lbl_token_banner_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.lbl_token_banner_desc = Gtk.Label(label=t("token_banner_desc"), css_classes=["token-banner-desc"], xalign=0, wrap=True)
        t_textbox.append(self.lbl_token_banner_title)
        t_textbox.append(self.lbl_token_banner_desc)
        self.token_banner_card.append(t_textbox)

        self.btn_token_banner = Gtk.Button(label=t("token_banner_btn"))
        self.btn_token_banner.add_css_class("primary-btn")
        self.btn_token_banner.connect("clicked", self._on_token_dialog)
        self.token_banner_card.append(self.btn_token_banner)
        inner.append(self.token_banner_card)

        mid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)

        chart_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        chart_card.add_css_class("hud-card")
        chart_card.set_hexpand(True)
        self.lbl_traffic_hdr = Gtk.Label(label=t("traffic_chart_title"), css_classes=["hud-card-header"], xalign=0)
        self.lbl_traffic_hdr.set_ellipsize(Pango.EllipsizeMode.END)
        chart_card.append(self.lbl_traffic_hdr)
        self.views_chart = TrafficViewsChart()
        chart_card.append(self.views_chart)
        mid_row.append(chart_card)

        rx_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        rx_card.add_css_class("hud-card")
        rx_card.set_size_request(240, -1)
        self.lbl_rx_hdr = Gtk.Label(label=t("reactions"), css_classes=["hud-card-header"], xalign=0)
        self.lbl_rx_hdr.set_ellipsize(Pango.EllipsizeMode.END)
        rx_card.append(self.lbl_rx_hdr)

        rx_grid = Gtk.Grid()
        rx_grid.set_column_spacing(12)
        rx_grid.set_row_spacing(10)
        self.rx_labels = {}
        items = [("👍", "+1"), ("❤️", "heart"), ("🚀", "rocket"), ("🎉", "hooray"), ("👀", "eyes"), ("😄", "laugh")]
        for i, (symbol, key) in enumerate(items):
            r = i // 2
            c = (i % 2) * 2
            s_lbl = Gtk.Label(label=symbol)
            v_lbl = Gtk.Label(label="0", css_classes=["stat-value"])
            self.rx_labels[key] = v_lbl
            rx_grid.attach(s_lbl, c, r, 1, 1)
            rx_grid.attach(v_lbl, c + 1, r, 1, 1)
        rx_card.append(rx_grid)
        mid_row.append(rx_card)

        inner.append(mid_row)

        bot_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)

        ref_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        ref_card.add_css_class("hud-card")
        ref_card.set_hexpand(True)
        self.lbl_ref_hdr = Gtk.Label(label=t("top_referrers"), css_classes=["hud-card-header"], xalign=0)
        self.lbl_ref_hdr.set_ellipsize(Pango.EllipsizeMode.END)
        ref_card.append(self.lbl_ref_hdr)
        self.referrers_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ref_card.append(self.referrers_container)
        bot_row.append(ref_card)

        rel_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        rel_card.add_css_class("hud-card")
        rel_card.set_hexpand(True)
        self.lbl_rel_hdr = Gtk.Label(label=t("release_downloads"), css_classes=["hud-card-header"], xalign=0)
        self.lbl_rel_hdr.set_ellipsize(Pango.EllipsizeMode.END)
        rel_card.append(self.lbl_rel_hdr)
        self.releases_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rel_card.append(self.releases_container)
        bot_row.append(rel_card)

        inner.append(bot_row)

        self.stack.add_named(page, "telemetry")

    def _refresh_telemetry_view(self):
        if not self.git.is_valid():
            self.token_banner_card.set_visible(True)
            self.views_chart.set_history([])
            return

        owner, repo = self.git.get_github_coords()
        if not owner or not repo:
            self.token_banner_card.set_visible(True)
            self.views_chart.set_history([])
            return

        def _worker():
            data = self.telemetry.fetch_full_insights(owner, repo)
            GLib.idle_add(lambda: self._apply_telemetry_data(data))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_telemetry_data(self, data):
        self.ins_stars.val_widget.set_text(str(data["stars"]))
        self.ins_forks.val_widget.set_text(str(data["forks"]))
        self.ins_downloads.val_widget.set_text(str(data["total_downloads"]))
        self.ins_issues.val_widget.set_text(str(data["open_issues"]))

        if data.get("has_traffic_access"):
            self.ins_views.val_widget.set_text(str(data["views_total"]))
            self.ins_uniques.val_widget.set_text(str(data["views_uniques"]))
            self.views_chart.set_history(data.get("views_history", []))
            self.token_banner_card.set_visible(False)
        else:
            self.ins_views.val_widget.set_text("—")
            self.ins_uniques.val_widget.set_text("—")
            self.views_chart.set_history([])
            self.token_banner_card.set_visible(True)

        rx = data.get("reactions", {})
        for key, widget in self.rx_labels.items():
            widget.set_text(str(rx.get(key, 0)))

        while child := self.referrers_container.get_first_child():
            self.referrers_container.remove(child)

        referrers = data.get("referrers", [])
        if referrers:
            for ref in referrers:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.add_css_class("file-item-row")
                lbl = Gtk.Label(label=ref["site"], xalign=0, hexpand=True)
                row.append(lbl)
                v_lbl = Gtk.Label(label=f"{ref['views']} {t('views_count')}", css_classes=["ahead-badge"])
                row.append(v_lbl)
                u_lbl = Gtk.Label(label=f"{ref['uniques']} {t('uniques_count')}", css_classes=["branch-badge"])
                row.append(u_lbl)
                self.referrers_container.append(row)
        else:
            msg = t("no_referrers")
            self.referrers_container.append(Gtk.Label(label=msg, css_classes=["stat-label"], xalign=0))

        while child := self.releases_container.get_first_child():
            self.releases_container.remove(child)

        releases = data.get("releases", [])
        if releases:
            for rel in releases:
                for a in rel.get("assets", []):
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                    row.add_css_class("file-item-row")
                    n_lbl = Gtk.Label(label=a["name"], xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
                    row.append(n_lbl)
                    d_badge = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                    d_badge.add_css_class("branch-badge")
                    d_badge.append(Gtk.Label(label=str(a.get("downloads", 0))))
                    d_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
                    d_icon.set_pixel_size(12)
                    d_badge.append(d_icon)
                    row.append(d_badge)
                    self.releases_container.append(row)
        else:
            self.releases_container.append(Gtk.Label(label=t("no_releases"), css_classes=["stat-label"], xalign=0))

    # --- COMPLETE STRINGS LOCALIZATION ---

    def _update_all_strings(self):
        # Sidebar
        self.lbl_sub.set_text(t("app_subtitle"))
        self.btn_open_repo.set_tooltip_text(t("btn_open_repo"))
        for nid, (btn, lbl, key) in self.nav_buttons.items():
            lbl.set_text(t(key))
        self.btn_sound.set_tooltip_text(t("sound_fx"))
        self.btn_lang.set_tooltip_text(t("lang_toggle_tooltip"))
        self.btn_token_cfg.set_tooltip_text(t("token_guide_title"))
        self.btn_refresh_ui.set_tooltip_text(t("btn_refresh"))

        # View 1
        self.lbl_view1_title.set_text(t("tab_changes"))
        self.lbl_changes_sub.set_text(t("sub_changes"))
        self.btn_stash_shelf.set_label(f"📦 {t('stashes')}")
        self.btn_publish_top.set_label(f"☁️ {t('publish_btn')}")
        is_published = self.git.is_valid() and self.git.has_remote("origin")
        self.btn_publish_top.set_visible(self.git.is_valid() and not is_published)
        ahead, _ = self.git.get_ahead_behind() if self.git.is_valid() else (0, 0)
        if ahead > 0 and is_published:
            self.btn_push_only.set_label(f"↑ {t('btn_push')} ({ahead})")
            self.btn_push_only.set_visible(True)
        else:
            self.btn_push_only.set_visible(False)
        self.lbl_composer_hdr.set_text(t("commit_builder"))
        self.check_breaking.set_label(t("breaking_change"))
        self.entry_scope.set_placeholder_text(t("commit_scope_placeholder"))
        self.entry_desc.set_placeholder_text(t("commit_desc_placeholder"))
        self.btn_commit.set_label(t("btn_commit"))
        self.btn_commit_push.set_label(t("btn_commit_push"))

        # View 2
        self.lbl_view2_title.set_text(t("tab_history"))
        self.lbl_hist_sub.set_text(t("sub_history"))
        cur_branch = self.git.get_current_branch() if self.git.is_valid() else "—"
        self.btn_branch_switch.set_label(f"🌿 {cur_branch} ▾")

        # View 3
        self.lbl_view3_title.set_text(t("tab_pulse"))
        self.lbl_pulse_sub.set_text(t("sub_pulse"))
        self.lbl_vel_hdr.set_text(t("velocity_title"))
        self.lbl_punch_hdr.set_text(t("punchcard_title"))
        self.card_commits.lbl_widget.set_text(t("stat_commits"))
        self.card_authors.lbl_widget.set_text(t("stat_contributors"))
        self.card_files.lbl_widget.set_text(t("stat_files"))
        self.card_stashes.lbl_widget.set_text(t("stat_stashes"))

        # View 4
        self.lbl_view4_title.set_text(t("tab_telemetry"))
        self.lbl_telem_sub.set_text(t("sub_telemetry"))
        self.btn_tok.set_label(t("token_settings"))
        self.btn_draft_rel.set_label(t("draft_release"))
        self.ins_views.lbl_widget.set_text(t("views_14d"))
        self.ins_uniques.lbl_widget.set_text(t("uniques_14d"))
        self.ins_stars.lbl_widget.set_text(t("stars"))
        self.ins_forks.lbl_widget.set_text(t("forks"))
        self.ins_downloads.lbl_widget.set_text(t("downloads"))
        self.ins_issues.lbl_widget.set_text(t("open_issues"))
        self.lbl_traffic_hdr.set_text(t("traffic_chart_title"))
        self.lbl_rx_hdr.set_text(t("reactions"))
        self.lbl_ref_hdr.set_text(t("top_referrers"))
        self.lbl_rel_hdr.set_text(t("release_downloads"))
        self.lbl_token_banner_title.set_text(t("token_banner_title"))
        self.lbl_token_banner_desc.set_text(t("token_banner_desc"))
        self.btn_token_banner.set_label(t("token_banner_btn"))
        self.refresh_lbl.set_text(t("refreshing"))
        self._run_secret_scan()

    # --- DATA REFRESH ---

    def _on_refresh_clicked(self):
        # Cancel any pending dismissal timers
        if getattr(self, "_refresh_timer_id", None):
            GLib.source_remove(self._refresh_timer_id)
            self._refresh_timer_id = None
        if getattr(self, "_refresh_finish_timer_id", None):
            GLib.source_remove(self._refresh_finish_timer_id)
            self._refresh_finish_timer_id = None

        self.sound.play("click")
        self.btn_refresh_stack.set_visible_child_name("spinner")
        self.btn_refresh_spinner.start()
        self.btn_refresh_ui.set_sensitive(False)

        self.refresh_lbl.set_text(t("refreshing"))
        self.refresh_spinner.start()
        self.refresh_revealer.set_reveal_child(True)

        def _worker():
            telem_data = None
            if self.active_view == "telemetry" and self.git.is_valid():
                owner, repo = self.git.get_github_coords()
                if owner and repo:
                    telem_data = self.telemetry.fetch_full_insights(owner, repo)
            GLib.idle_add(lambda: self._finish_refresh(telem_data))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_refresh(self, telem_data=None):
        self._load_repo_data()
        if self.active_view == "pulse":
            self._refresh_pulse_view()
        elif self.active_view == "history":
            self._refresh_history_view()
        elif self.active_view == "telemetry":
            if telem_data is not None:
                self._apply_telemetry_data(telem_data)
            else:
                self._refresh_telemetry_view()

        # Update text to indicate completion
        self.refresh_lbl.set_text(t("refresh_done"))
        self.sound.play("commit")

        # Keep spinner continuously spinning and notification visible for 2 seconds
        def _start_hide():
            self.refresh_revealer.set_reveal_child(False)
            self._refresh_timer_id = None
            return False

        def _complete_hide():
            self.refresh_spinner.stop()
            self.btn_refresh_spinner.stop()
            self.btn_refresh_stack.set_visible_child_name("icon")
            self.btn_refresh_ui.set_sensitive(True)
            self.refresh_lbl.set_text(t("refreshing"))
            self._refresh_finish_timer_id = None
            return False

        self._refresh_timer_id = GLib.timeout_add(1500, _start_hide)
        self._refresh_finish_timer_id = GLib.timeout_add(1800, _complete_hide)

    def _load_repo_data(self):
        if not self.git.is_valid():
            self.sidebar_repo_name.set_text(t("no_repo_title"))
            self.sidebar_branch.set_text("—")
            self.sidebar_ahead.set_text("—")
            self._render_no_repo_placeholder()
            return

        self.sidebar_repo_name.set_text(self.git.get_repo_name())
        self.sidebar_branch.set_text(self.git.get_current_branch())
        ahead, behind = self.git.get_ahead_behind()
        self.sidebar_ahead.set_text(f"↑{ahead} ↓{behind}")
        has_remote = self.git.has_remote("origin")
        self.btn_publish_top.set_visible(not has_remote)
        if ahead > 0 and has_remote:
            self.btn_push_only.set_label(f"↑ {t('btn_push')} ({ahead})")
            self.btn_push_only.set_visible(True)
        else:
            self.btn_push_only.set_visible(False)

        self._refresh_changes_view()
        self._update_commit_preview()

    def _refresh_changes_view(self):
        while child := self.files_container.get_first_child():
            self.files_container.remove(child)

        # Show Publish to GitHub banner if repo has no origin remote
        if not self.git.has_remote("origin"):
            publish_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
            publish_card.add_css_class("token-banner-card")

            p_icon = Gtk.Image.new_from_icon_name("send-to-symbolic")
            p_icon.set_pixel_size(32)
            publish_card.append(p_icon)

            p_textbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            p_textbox.set_hexpand(True)
            p_title = Gtk.Label(label=t("publish_card_title"), css_classes=["token-banner-title"], xalign=0)
            p_desc = Gtk.Label(label=t("publish_card_desc"), css_classes=["token-banner-desc"], xalign=0, wrap=True)
            p_textbox.append(p_title)
            p_textbox.append(p_desc)
            publish_card.append(p_textbox)

            btn_publish_card = Gtk.Button(label=t("publish_btn"))
            btn_publish_card.add_css_class("primary-btn")
            btn_publish_card.connect("clicked", self._on_publish_dialog)
            publish_card.append(btn_publish_card)

            self.files_container.append(publish_card)

        status = self.git.get_status_files()
        staged = status.get("staged", [])
        unstaged = status.get("unstaged", [])
        untracked = status.get("untracked", [])

        self._run_secret_scan()

        if not staged and not unstaged and not untracked:
            self._render_empty_changes(t("clean_tree"), t("clean_tree_sub"))
            return

        if staged:
            hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl = Gtk.Label(label=f"{t('staged_title')} ({len(staged)})", css_classes=["hud-card-header"], xalign=0)
            hdr.append(lbl)
            hdr.append(Gtk.Box(hexpand=True))
            btn_unstage_all = Gtk.Button(label=t("unstage_all"), css_classes=["flat"])
            btn_unstage_all.connect("clicked", self._on_unstage_all)
            hdr.append(btn_unstage_all)
            self.files_container.append(hdr)

            for item in staged:
                self._add_file_row(item, is_staged=True)

        if unstaged:
            hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            hdr.set_margin_top(12)
            lbl = Gtk.Label(label=f"{t('unstaged_title')} ({len(unstaged)})", css_classes=["hud-card-header"], xalign=0)
            hdr.append(lbl)
            hdr.append(Gtk.Box(hexpand=True))
            btn_stage_all = Gtk.Button(label=t("stage_all"), css_classes=["flat"])
            btn_stage_all.connect("clicked", self._on_stage_all)
            hdr.append(btn_stage_all)
            self.files_container.append(hdr)

            for item in unstaged:
                self._add_file_row(item, is_staged=False)

        if untracked:
            hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            hdr.set_margin_top(12)
            lbl = Gtk.Label(label=f"{t('untracked_title')} ({len(untracked)})", css_classes=["hud-card-header"], xalign=0)
            hdr.append(lbl)
            self.files_container.append(hdr)

            for item in untracked:
                self._add_file_row(item, is_staged=False)

    def _render_no_repo_placeholder(self):
        while child := self.files_container.get_first_child():
            self.files_container.remove(child)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.add_css_class("welcome-placeholder-card")
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("folder-open-symbolic")
        icon.set_pixel_size(48)
        box.append(icon)

        t_lbl = Gtk.Label(label=t("no_repo_title"), css_classes=["view-title"])
        box.append(t_lbl)

        d_lbl = Gtk.Label(label=t("no_repo_desc"), css_classes=["view-subtitle"], wrap=True)
        d_lbl.set_max_width_chars(50)
        box.append(d_lbl)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_row.set_halign(Gtk.Align.CENTER)

        btn = Gtk.Button(label=t("btn_open_repo"))
        btn.add_css_class("primary-btn")
        btn.connect("clicked", self._on_choose_repo)
        btn_row.append(btn)

        btn_init = Gtk.Button(label="✨ " + t("btn_init_repo"))
        btn_init.add_css_class("suggested-action")
        btn_init.connect("clicked", self._on_init_repo_clicked)
        btn_row.append(btn_init)

        box.append(btn_row)

        self.files_container.append(box)

    def _render_empty_changes(self, title, subtitle):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        icon.set_pixel_size(44)
        box.append(icon)

        t_lbl = Gtk.Label(label=title, css_classes=["view-title"])
        box.append(t_lbl)

        s_lbl = Gtk.Label(label=subtitle, css_classes=["view-subtitle"])
        box.append(s_lbl)

        ahead, behind = self.git.get_ahead_behind()
        if ahead > 0:
            btn_sync = Gtk.Button(label=f"🚀 {t('btn_push_ahead')} ({ahead})")
            btn_sync.add_css_class("primary-btn")
            btn_sync.set_margin_top(12)
            btn_sync.connect("clicked", lambda b: self._do_push())
            box.append(btn_sync)

        self.files_container.append(box)

    def _add_file_row(self, item, is_staged):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("file-item-row")

        filepath = item.get("path", "")

        check = Gtk.CheckButton()
        check.set_active(is_staged)
        check.connect("toggled", lambda cb, fp=filepath, st=is_staged: self._toggle_stage_file(fp, st))
        row.append(check)

        st_char = item.get("status", "M")
        badge = Gtk.Label(label=st_char, css_classes=["status-tag"])
        if st_char in ["M", "T"]:
            badge.add_css_class("status-mod")
        elif st_char in ["A", "?"]:
            badge.add_css_class("status-add")
        else:
            badge.add_css_class("status-del")
        row.append(badge)

        path_lbl = Gtk.Label(label=filepath, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        row.append(path_lbl)

        add = item.get("lines_add", 0)
        dels = item.get("lines_del", 0)
        if add > 0 or dels > 0:
            stat_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            if add > 0:
                stat_box.append(Gtk.Label(label=f"+{add}", css_classes=["line-add"]))
            if dels > 0:
                stat_box.append(Gtk.Label(label=f"-{dels}", css_classes=["line-del"]))
            row.append(stat_box)

        btn_diff = Gtk.Button()
        btn_diff.set_icon_name("edit-find-symbolic")
        btn_diff.set_tooltip_text(t("view_diff"))
        btn_diff.add_css_class("subtle-icon-btn")
        btn_diff.connect("clicked", lambda b, fp=filepath, st=is_staged: self._show_diff(fp, st))
        row.append(btn_diff)

        self.files_container.append(row)

    def _toggle_stage_file(self, filepath, currently_staged):
        if currently_staged:
            self.git.unstage_file(filepath)
            self.sound.play("pop")
        else:
            self.git.stage_file(filepath)
            self.sound.play("click")
        self._load_repo_data()

    def _on_stage_all(self, btn):
        self.git.stage_all()
        self.sound.play("click")
        self._load_repo_data()

    def _on_unstage_all(self, btn):
        self.git.unstage_all()
        self.sound.play("pop")
        self._load_repo_data()

    def _show_diff(self, filepath, is_staged):
        self.sound.play("click")
        diff_text = self.git.get_file_diff(filepath, staged=is_staged)
        dlg = DiffViewerDialog(
            self,
            filename=filepath,
            diff_text=diff_text,
            is_staged=is_staged,
            on_stage_toggle=self._toggle_stage_file
        )
        dlg.present()

    def _on_commit(self, push=False):
        desc = self.entry_desc.get_text().strip()
        if not desc:
            self.sound.play("error")
            return

        if self.last_scan_findings:
            self._show_secret_warning_dialog(on_confirm=lambda: self._execute_commit(push=push))
            return

        self._execute_commit(push=push)

    def _execute_commit(self, push=False):
        desc = self.entry_desc.get_text().strip()
        if not desc:
            return

        scope = self.entry_scope.get_text().strip()
        breaking = "!" if self.check_breaking.get_active() else ""
        if scope:
            msg = f"{self.selected_type}({scope}){breaking}: {desc}"
        else:
            msg = f"{self.selected_type}{breaking}: {desc}"

        ok, out = self.git.commit(msg)
        if ok:
            self.sound.play("commit")
            self.entry_desc.set_text("")
            self._load_repo_data()
            if push:
                self._do_push()
        else:
            self.sound.play("error")
            err_msg = out.strip() if out else "Nothing to commit or commit failed."
            self._show_error_dialog(t("commit_failed"), err_msg)

    def _do_push(self):
        def _bg():
            ok, out = self.git.push()
            def _done():
                if ok:
                    self.sound.play("push")
                    self._load_repo_data()
                else:
                    self.sound.play("error")
                    err_msg = out.strip() if out else "Unknown error during push."
                    self._show_error_dialog(t("push_failed"), err_msg)
            GLib.idle_add(_done)
        threading.Thread(target=_bg, daemon=True).start()

    def _on_stash(self, btn):
        ok, out = self.git.stash_save()
        if ok:
            self.sound.play("pop")
            self._load_repo_data()

    def _on_pop_stash(self, btn):
        ok, out = self.git.stash_pop()
        if ok:
            self.sound.play("pop")
            self._load_repo_data()

    def _copy_to_clipboard(self, text):
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)
        self.sound.play("click")

    # --- SETTINGS & DIALOGS ---

    def _on_choose_repo(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title(t("btn_open_repo"))
        dialog.select_folder(self, None, self._on_repo_folder_selected)

    def _on_repo_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                if self.git.set_repo(path):
                    self.sound.play("click")
                    self.config["last_repo"] = path
                    self.config["first_run_completed"] = True
                    if "recent_repos" not in self.config or not isinstance(self.config["recent_repos"], list):
                        self.config["recent_repos"] = []
                    if path not in self.config["recent_repos"]:
                        self.config["recent_repos"].insert(0, path)
                    self._save_config()
                    self._load_repo_data()
                    if self.active_view == "pulse":
                        self._refresh_pulse_view()
                    elif self.active_view == "history":
                        self._refresh_history_view()
                    elif self.active_view == "telemetry":
                        self._refresh_telemetry_view()
                else:
                    self.sound.play("error")
                    self.git.repo_path = path
                    self.git.root_path = None
                    self._load_repo_data()
        except Exception as e:
            print(f"[Repo] Folder select error: {e}")

    def _on_init_repo_clicked(self, btn):
        self.sound.play("click")
        target_path = self.git.repo_path or os.getcwd()
        ok, msg = self.git.init_repo(target_path)
        if ok:
            self.sound.play("commit")
            self.config["last_repo"] = target_path
            self.config["first_run_completed"] = True
            if "recent_repos" not in self.config or not isinstance(self.config["recent_repos"], list):
                self.config["recent_repos"] = []
            if target_path not in self.config["recent_repos"]:
                self.config["recent_repos"].insert(0, target_path)
            self._save_config()
            self._load_repo_data()
        else:
            self.sound.play("error")
            self._show_error_dialog(t("btn_init_repo"), msg)

    def _on_publish_dialog(self, btn):
        self.sound.play("click")
        from publish_dialog import PublishToGitHubDialog
        dlg = PublishToGitHubDialog(
            parent=self,
            git_engine=self.git,
            telemetry_client=self.telemetry,
            sound_engine=self.sound,
            config=self.config,
            on_published=self._on_published_success
        )
        dlg.present()

    def _on_published_success(self, repo_data):
        self._load_repo_data()
        if self.active_view == "telemetry":
            self._refresh_telemetry_view()

    def _on_toggle_sound(self, btn):
        self.sound.enabled = not self.sound.enabled
        self.config["sound_enabled"] = self.sound.enabled
        self._save_config()
        self.btn_sound.set_icon_name("audio-volume-high-symbolic" if self.sound.enabled else "audio-volume-muted-symbolic")
        if self.sound.enabled:
            self.sound.play("click")

    def _on_toggle_lang(self, btn):
        new_lang = "en" if i18n.get_language() == "ru" else "ru"
        i18n.set_language(new_lang)
        self.config["language"] = new_lang
        self._save_config()
        self.btn_lang.set_label("EN" if new_lang == "en" else "RU")

        # Synchronously re-localize ALL text widgets across every screen
        self._update_all_strings()

        # Trigger smooth refresh animation with spinner on language switch
        self._on_refresh_clicked()

    def _on_token_dialog(self, btn):
        self.sound.play("click")
        from token_dialog import GitTokenGuideDialog
        dlg = GitTokenGuideDialog(
            parent=self,
            config=self.config,
            telemetry_client=self.telemetry,
            sound_engine=self.sound,
            on_saved=self._on_token_saved
        )
        dlg.present()

    def _on_token_saved(self):
        self._save_config()
        if self.active_view == "telemetry":
            self._refresh_telemetry_view()



    # --- GLOBAL ACTIONS & MODALS ---

    def _on_global_key_pressed(self, controller, keyval, keycode, state):
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if is_ctrl:
            if keyval in (
                Gdk.KEY_k, Gdk.KEY_K,
                Gdk.KEY_Cyrillic_el, Gdk.KEY_Cyrillic_EL,
                Gdk.KEY_Cyrillic_ka, Gdk.KEY_Cyrillic_KA
            ):
                self._on_open_quick_switcher()
                return True
        return False

    def _on_open_quick_switcher(self):
        self.sound.play("click")
        dlg = QuickSwitcherDialog(
            parent=self,
            recent_repos=self.config.get("recent_repos", []),
            current_repo=self.git.repo_path if self.git.is_valid() else "",
            sound_engine=self.sound,
            on_repo_selected=self._switch_to_repo_path,
            on_browse_folder=lambda: self._on_choose_repo(None)
        )
        dlg.present()

    def _switch_to_repo_path(self, path):
        if self.git.set_repo(path):
            self.sound.play("click")
            self.config["last_repo"] = path
            self.config["first_run_completed"] = True
            recent = self.config.get("recent_repos", [])
            if not isinstance(recent, list):
                recent = []
            if path in recent:
                recent.remove(path)
            recent.insert(0, path)
            self.config["recent_repos"] = recent
            self._save_config()
            self._load_repo_data()
            if self.active_view == "pulse":
                self._refresh_pulse_view()
            elif self.active_view == "history":
                self._refresh_history_view()
            elif self.active_view == "telemetry":
                self._refresh_telemetry_view()
        else:
            self.sound.play("error")

    def _on_branch_switcher_clicked(self, btn):
        if not self.git.is_valid():
            return
        self.sound.play("click")
        branches = self.git.list_branches_detailed()
        if not branches:
            return

        popover = Gtk.Popover()
        popover.set_parent(btn)
        popover.set_has_arrow(True)
        popover.set_autohide(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_size_request(220, -1)

        hdr = Gtk.Label(label=t("switch_branch"), css_classes=["stat-label"], xalign=0)
        hdr.set_margin_bottom(4)
        box.append(hdr)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_max_content_height(280)
        scrolled.set_propagate_natural_height(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        list_b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scrolled.set_child(list_b)
        box.append(scrolled)

        for b in branches:
            b_name = b["name"]
            is_cur = b["current"]
            b_btn = Gtk.Button()
            b_btn.add_css_class("flat")
            b_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            b_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic" if is_cur else "folder-symbolic")
            b_icon.set_pixel_size(14)
            b_icon.set_opacity(1.0 if is_cur else 0.3)
            b_row.append(b_icon)
            lbl = Gtk.Label(label=b_name, xalign=0, hexpand=True)
            if is_cur:
                lbl.add_css_class("status-tag")
            b_row.append(lbl)
            b_btn.set_child(b_row)

            def _checkout(bn=b_name, pop=popover):
                pop.popdown()
                if bn != self.git.get_current_branch():
                    ok, out = self.git.checkout_branch(bn)
                    if ok:
                        self.sound.play("click")
                        self._load_repo_data()
                        self._refresh_history_view()
                    else:
                        self.sound.play("error")
                        self._show_error_dialog(t("checkout_failed"), out)

            b_btn.connect("clicked", lambda _, bn=b_name, p=popover: _checkout(bn, p))
            list_b.append(b_btn)

        popover.set_child(box)
        popover.popup()

    def _on_open_stashes(self):
        if not self.git.is_valid():
            return
        self.sound.play("click")
        dlg = StashInspectorDialog(
            parent=self,
            git_engine=self.git,
            sound_engine=self.sound,
            on_changed=self._load_repo_data
        )
        dlg.present()

    def _open_release_drafter(self):
        if not self.git.is_valid():
            return
        self.sound.play("click")
        dlg = ReleaseDrafterDialog(
            parent=self,
            git_engine=self.git,
            sound_engine=self.sound,
            on_tag_created=self._load_repo_data
        )
        dlg.present()

    def _run_secret_scan(self):
        is_clean, findings = scan_staged_files(self.git)
        self.last_scan_findings = findings
        if not is_clean:
            self.scanner_status_pill.remove_css_class("scanner-pill-clean")
            self.scanner_status_pill.add_css_class("scanner-pill-warn")
            count = len(findings)
            if i18n.get_language() == "ru":
                warn_text = f"⚠️ {count} {plural_ru(count, 'утечка!', 'утечки!', 'утечек!')}"
            else:
                warn_text = f"⚠️ {count} secret{'s' if count > 1 else ''}!"
            self.scanner_status_pill.set_label(warn_text)
            self.scanner_status_pill.set_tooltip_text(t("scanner_warning"))
        else:
            self.scanner_status_pill.remove_css_class("scanner-pill-warn")
            self.scanner_status_pill.add_css_class("scanner-pill-clean")
            self.scanner_status_pill.set_label(f"🛡️ {t('scanner_clean')}")
            self.scanner_status_pill.set_tooltip_text(t("scanner_clean"))

    def _on_scanner_pill_clicked(self, btn):
        self.sound.play("click")
        if self.last_scan_findings:
            self._show_secret_warning_dialog(on_confirm=None)
        else:
            dlg = Gtk.Window(transient_for=self, modal=True)
            dlg.set_title(t("scanner_clean"))
            dlg.set_default_size(440, 180)
            dlg.add_css_class("token-modal-window")

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            box.set_margin_top(20)
            box.set_margin_bottom(20)
            box.set_margin_start(20)
            box.set_margin_end(20)
            dlg.set_child(box)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            icon = Gtk.Image.new_from_icon_name("security-high-symbolic")
            icon.set_pixel_size(36)
            row.append(icon)

            t_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            t_box.set_hexpand(True)
            lbl_title = Gtk.Label(label=t("scanner_clean"), css_classes=["view-title"], xalign=0)
            t_box.append(lbl_title)
            desc_text = "No private keys, tokens, or sensitive credentials detected in staged files." if i18n.get_language() == "en" else "В подготовленных изменениях не обнаружено приватных ключей, токенов или секретов."
            lbl_desc = Gtk.Label(label=desc_text, css_classes=["view-subtitle"], xalign=0, wrap=True)
            t_box.append(lbl_desc)
            row.append(t_box)
            box.append(row)

            btn_ok = Gtk.Button(label="OK", css_classes=["primary-btn"])
            btn_ok.set_halign(Gtk.Align.END)
            btn_ok.connect("clicked", lambda b: dlg.close())
            box.append(btn_ok)
            dlg.present()

    def _show_secret_warning_dialog(self, on_confirm=None):
        self.sound.play("error")
        dlg = Gtk.Window(transient_for=self, modal=True)
        dlg.set_title(t("secrets_dialog_title"))
        dlg.set_default_size(560, 360)
        dlg.add_css_class("token-modal-window")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(20)
        box.set_margin_end(20)
        dlg.set_child(box)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        icon.set_pixel_size(32)
        hdr.append(icon)

        t_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        t_box.set_hexpand(True)
        lbl_title = Gtk.Label(label=t("secrets_dialog_title"), css_classes=["view-title"], xalign=0)
        t_box.append(lbl_title)
        lbl_desc = Gtk.Label(label=t("secrets_dialog_desc"), css_classes=["view-subtitle"], xalign=0, wrap=True)
        t_box.append(lbl_desc)
        hdr.append(t_box)
        box.append(hdr)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scrolled.set_child(list_box)
        box.append(scrolled)

        for finding in self.last_scan_findings:
            f_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            f_row.add_css_class("file-item-row")
            tag = Gtk.Label(label=finding.get("rule", "Secret"), css_classes=["status-del"])
            f_row.append(tag)
            fn = f"{os.path.basename(finding.get('file', ''))}:{finding.get('line', 0)}"
            fn_lbl = Gtk.Label(label=fn, css_classes=["stat-label"])
            f_row.append(fn_lbl)
            val_lbl = Gtk.Label(label=finding.get("preview", ""), xalign=0, hexpand=True)
            f_row.append(val_lbl)
            list_box.append(f_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_row.append(Gtk.Box(hexpand=True))

        btn_cancel = Gtk.Button(label=t("cancel"), css_classes=["subtle-btn"])
        btn_cancel.connect("clicked", lambda b: dlg.close())
        btn_row.append(btn_cancel)

        if on_confirm:
            btn_commit_anyway = Gtk.Button(label=t("commit_anyway"), css_classes=["primary-btn"])
            def _commit_proceed():
                dlg.close()
                on_confirm()
            btn_commit_anyway.connect("clicked", lambda b: _commit_proceed())
            btn_row.append(btn_commit_anyway)

        box.append(btn_row)
        dlg.present()

    def _show_error_dialog(self, title, msg):
        dlg = Gtk.Window(transient_for=self, modal=True)
        dlg.set_title(title)
        dlg.set_default_size(460, 180)
        dlg.add_css_class("token-modal-window")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        dlg.set_child(box)

        lbl = Gtk.Label(label=f"{title}\n{msg}", wrap=True, xalign=0)
        box.append(lbl)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_row.append(Gtk.Box(hexpand=True))

        lower_msg = (msg or "").lower()
        if any(w in lower_msg for w in ["auth", "token", "permission", "denied", "credential", "403", "401"]):
            btn_token = Gtk.Button(label=f"🔑 {t('token_guide_title')}", css_classes=["subtle-btn"])
            def _open_guide(b):
                dlg.close()
                self._on_token_dialog(None)
            btn_token.connect("clicked", _open_guide)
            btn_row.append(btn_token)

        btn = Gtk.Button(label="OK", css_classes=["primary-btn"])
        btn.connect("clicked", lambda b: dlg.close())
        btn_row.append(btn)

        box.append(btn_row)
        dlg.present()


class GitPulseApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.xronni.gitpulse")

    def do_activate(self):
        self._load_css()
        win = GitPulseWindow(self)
        win.present()

    def _load_css(self):
        if os.path.exists(CSS_FILE):
            provider = Gtk.CssProvider()
            provider.load_from_path(CSS_FILE)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )


def main():
    app = GitPulseApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
