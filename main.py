#!/usr/bin/env python3
"""
GitPulse HUD — Professional GTK4 / Libadwaita Git Companion
Author: Xronni (https://github.com/Xronni)
"""

import sys
import os
import json
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Adw, Gdk, GLib, Pango

from git_engine import GitEngine
from sound_engine import SoundEngine
from github_telemetry import GitHubTelemetry
from secret_scanner import scan_staged_files
from stash_dialog import StashInspectorDialog
from release_dialog import ReleaseDrafterDialog
from quick_switcher import QuickSwitcherDialog
from branch_switcher import BranchSwitcherPopover
from window_sync import SyncMixin
from window_changes import ChangesViewMixin
from window_history import HistoryViewMixin
from window_insights import InsightsViewMixin
from async_tasks import run_in_background
from ui_dialogs import show_error_dialog
import i18n
from i18n import t

CONFIG_DIR = os.path.expanduser("~/.config/git-pulse")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CSS_FILE = os.path.join(APP_DIR, "style.css")
ICON_FILE = os.path.join(APP_DIR, "assets", "icon.png")


class GitPulseWindow(ChangesViewMixin, HistoryViewMixin, InsightsViewMixin, SyncMixin, Adw.ApplicationWindow):
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
        home_abs = os.path.abspath(os.path.expanduser("~"))
        if initial_repo and os.path.exists(initial_repo) and os.path.abspath(initial_repo) not in [home_abs, "/", "/root"]:
            self.git = GitEngine(initial_repo)
        else:
            self.git = GitEngine(None)
            self.config["last_repo"] = ""

        self.telemetry = GitHubTelemetry(token=self.config.get("github_token", ""))
        if not self.config.get("github_token") and self.telemetry.token:
            self.config["github_token"] = self.telemetry.token
            self._save_config()
        self.active_view = "changes"
        self.selected_type = "feat"
        self.last_scan_findings = []

        self.config.setdefault("recent_repos", [])
        self.config["recent_repos"] = [
            r for r in self.config["recent_repos"]
            if r and os.path.exists(r) and os.path.abspath(r) not in [home_abs, "/", "/root"]
        ]
        if self.git.is_valid() and self.git.root_path not in self.config["recent_repos"]:
            self.config["recent_repos"].insert(0, self.git.root_path)

        # Global key controller (Ctrl+K for Quick Switcher)
        key_ctl = Gtk.EventControllerKey()
        key_ctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctl.connect("key-pressed", self._on_global_key_pressed)
        self.add_controller(key_ctl)

        self._refresh_timer_id = None
        self._refresh_finish_timer_id = None

        self._build_main_layout()
        self._update_all_strings()
        self._load_repo_data()
        self._start_sync_timers()

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
        # Toasts for non-blocking notifications (errors still use modal dialogs)
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(root_box)
        # Adw.ApplicationWindow has no titlebar of its own: add a header bar via ToolbarView.
        # Being an Adw window also lets Adw.AlertDialog render inside it.
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())
        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)

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
        repo_click.connect("released", lambda g, n, x, y: self._on_repo_card_clicked(repo_card, x, y))
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

        self.sidebar_pills_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.sidebar_branch = Gtk.Button(css_classes=["branch-badge", "branch-badge-btn"])
        self.sidebar_branch_lbl = Gtk.Label(ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=16)
        self.sidebar_branch.set_child(self.sidebar_branch_lbl)
        self.sidebar_branch.set_tooltip_text(t("branch_switch_tooltip"))
        self.sidebar_branch.connect("clicked", self._on_branch_switcher_clicked)
        self._set_sidebar_branch(self.git.get_current_branch() if self.git.is_valid() else "")
        self.sidebar_pills_row.append(self.sidebar_branch)

        self.sidebar_ahead = Gtk.Label(label="↑0 ↓0")
        self.sidebar_ahead.add_css_class("ahead-badge")
        self.sidebar_pills_row.append(self.sidebar_ahead)

        repo_card.append(self.sidebar_pills_row)
        self._build_sync_row(repo_card)
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
            btn.set_tooltip_text(f"Ctrl+{len(self.nav_buttons) + 1}")
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

    # --- COMPLETE STRINGS LOCALIZATION ---

    def _update_all_strings(self):
        # Sidebar
        self.lbl_sub.set_text(t("app_subtitle"))
        self.btn_open_repo.set_tooltip_text(t("btn_open_repo"))
        if not self.git.is_valid():
            self.sidebar_repo_name.set_text(t("open_project_hint"))
        else:
            self.sidebar_repo_name.set_text(self.git.get_repo_name())
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
        self.btn_stash_shelf.set_visible(self.git.is_valid())
        is_published = self.git.is_valid() and self.git.has_remote("origin")
        ahead, _ = self.git.get_ahead_behind() if self.git.is_valid() else (0, 0)
        if ahead > 0 and is_published:
            self.btn_push_only.set_label(f"↑ {t('btn_push')} ({ahead})")
            self.btn_push_only.set_visible(True)
        elif ahead > 0 and not is_published:
            self.btn_push_only.set_label(f"☁️ {t('publish_btn')}")
            self.btn_push_only.set_visible(True)
        else:
            self.btn_push_only.set_visible(False)
        self.lbl_composer_hdr.set_text(t("commit_builder"))
        self.check_breaking.set_label(t("breaking_change"))
        self.entry_scope.set_placeholder_text(t("commit_scope_placeholder"))
        self.entry_desc.set_placeholder_text(t("commit_desc_placeholder"))
        self.btn_commit.set_label(t("btn_commit"))
        if is_published:
            self.btn_commit_push.set_label(f"🚀 {t('btn_commit_push')}")
        else:
            self.btn_commit_push.set_label(f"☁️ {t('btn_commit_publish')}")

        # View 2
        self.lbl_view2_title.set_text(t("tab_history"))
        self.lbl_hist_sub.set_text(t("sub_history"))
        cur_branch = self.git.get_current_branch() if self.git.is_valid() else "—"
        self.btn_branch_switch.set_label(f"🌿 {cur_branch} ▾")
        self.btn_branch_switch.set_tooltip_text(t("branch_switch_tooltip"))
        self.sidebar_branch.set_tooltip_text(t("branch_switch_tooltip"))

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
        # Re-render the scanner pill label in the new language
        self._apply_secret_scan(self.last_scan_findings)

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

    @staticmethod
    def _collect_repo_snapshot(git):
        """Everything the views need from git. Runs on a worker thread: no widget access here."""
        ahead, behind = git.get_ahead_behind()
        is_clean, findings = scan_staged_files(git)
        return {
            "root": git.root_path,
            "name": git.get_repo_name(),
            "branch": git.get_current_branch(),
            "ahead": ahead,
            "behind": behind,
            "has_origin": git.has_remote("origin"),
            "upstream": git.get_upstream(),
            "has_commits": git.has_commits(),
            "merging": git.is_merging(),
            "status": git.get_status_files(),
            "scan_findings": [] if is_clean else findings,
        }

    def _load_repo_data(self):
        """Reloads repository state in the background and then rebuilds the sidebar and changes view."""
        self._load_generation = getattr(self, "_load_generation", 0) + 1
        if not self.git.is_valid():
            self.snapshot = None
            self.sidebar_repo_name.set_text(t("open_project_hint"))
            self._set_sidebar_branch("")
            self.sidebar_ahead.set_text("")
            self.sidebar_pills_row.set_visible(False)
            self.sidebar_sync_row.set_visible(False)
            self.btn_stash_shelf.set_visible(False)
            self.btn_push_only.set_visible(False)
            self.commit_card.set_visible(False)
            self._render_no_repo_placeholder()
            return

        generation = self._load_generation
        git = self.git
        run_in_background(lambda: self._collect_repo_snapshot(git),
                          lambda snap: self._apply_repo_snapshot(generation, snap))

    def _apply_repo_snapshot(self, generation, snap):
        if generation != self._load_generation or snap["root"] != self.git.root_path:
            return  # a newer reload was requested, or the repository changed meanwhile
        self.snapshot = snap
        ahead, behind, has_remote = snap["ahead"], snap["behind"], snap["has_origin"]

        self.sidebar_pills_row.set_visible(True)
        self.btn_stash_shelf.set_visible(True)
        self.sidebar_repo_name.set_text(snap["name"])
        self._set_sidebar_branch(snap["branch"])
        self.sidebar_ahead.set_text(f"↑{ahead} ↓{behind}")
        self._refresh_sync_status(ahead, behind, has_origin=has_remote, upstream=snap["upstream"])
        self._mark_state_fresh()
        if ahead > 0 and has_remote:
            self.btn_push_only.set_label(f"↑ {t('btn_push')} ({ahead})")
            self.btn_push_only.set_visible(True)
        elif ahead > 0 and not has_remote:
            self.btn_push_only.set_label(f"☁️ {t('publish_btn')}")
            self.btn_push_only.set_visible(True)
        else:
            self.btn_push_only.set_visible(False)

        self._refresh_changes_view(snap)
        self._update_commit_preview()

    def _toast(self, message, timeout=3):
        toast = Adw.Toast(title=message)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)

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
                home_abs = os.path.abspath(os.path.expanduser("~"))
                if not path or os.path.abspath(path) in [home_abs, "/", "/root"]:
                    self.sound.play("error")
                    self._show_error_dialog(t("btn_open_repo"), "Cannot open system root or home directory as a repository.")
                    return

                if self.git.find_repo_root(path):
                    self._switch_to_repo_path(path)
                else:
                    self.sound.play("pop")
                    self.git.repo_path = os.path.abspath(path)
                    self.git.root_path = None
                    self._load_repo_data()
        except Exception as e:
            print(f"[Repo] Folder select error: {e}")

    def _on_init_repo_clicked(self, btn):
        self.sound.play("click")
        target_path = self.git.repo_path
        home_abs = os.path.abspath(os.path.expanduser("~"))
        if not target_path or not os.path.exists(target_path) or os.path.abspath(target_path) in [home_abs, "/", "/root"]:
            self._on_choose_repo(None)
            return

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

    def _on_publish_dialog(self, btn=None):
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

    def _latin_keyval(self, keyval, keycode, state):
        """Maps a key to the first (Latin) layout so Ctrl+K works on a Russian layout too."""
        code = Gdk.keyval_to_unicode(keyval)
        if not code or chr(code).isascii():
            return keyval
        display = self.get_display()
        for group in range(4):  # layouts may be ordered "ru,us" as well as "us,ru"
            ok, latin, *_ = display.translate_key(keycode, state, group)
            latin_code = Gdk.keyval_to_unicode(latin) if ok else 0
            if latin_code and chr(latin_code).isascii():
                return latin
        return keyval

    def _on_global_key_pressed(self, controller, keyval, keycode, state):
        mods = state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.ALT_MASK)
        ctrl = bool(mods & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(mods & Gdk.ModifierType.SHIFT_MASK)
        key = Gdk.keyval_to_lower(self._latin_keyval(keyval, keycode, state))

        if key == Gdk.KEY_F5 and not ctrl:
            self._on_refresh_clicked()
            return True
        if not ctrl or (mods & Gdk.ModifierType.ALT_MASK):
            return False

        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if self.active_view == "changes" and self.commit_card.get_visible() and self.btn_commit.get_sensitive():
                self._on_commit(push=shift)
                return True
            return False
        actions = {
            (Gdk.KEY_k, False): self._on_open_quick_switcher,
            (Gdk.KEY_b, False): lambda: self._on_branch_switcher_clicked(self.sidebar_branch),
            (Gdk.KEY_r, False): self._on_refresh_clicked,
            (Gdk.KEY_p, False): self._do_push,
            (Gdk.KEY_p, True): self._do_pull,
            (Gdk.KEY_f, True): lambda: self._do_fetch(silent=False),
            (Gdk.KEY_1, False): lambda: self._switch_nav("changes"),
            (Gdk.KEY_2, False): lambda: self._switch_nav("history"),
            (Gdk.KEY_3, False): lambda: self._switch_nav("pulse"),
            (Gdk.KEY_4, False): lambda: self._switch_nav("telemetry"),
        }
        action = actions.get((key, shift))
        if action:
            action()
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
            self._reset_sync_state()
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

    @staticmethod
    def _click_hits_button(container, x, y):
        widget = container.pick(x, y, Gtk.PickFlags.DEFAULT)
        while widget is not None and widget is not container:
            if isinstance(widget, Gtk.Button):
                return True
            widget = widget.get_parent()
        return False

    def _on_repo_card_clicked(self, card, x, y):
        # Buttons inside the card (branch badge, sync row, open folder) handle their own clicks
        if not self._click_hits_button(card, x, y):
            self._on_open_quick_switcher()

    def _set_sidebar_branch(self, name):
        self.sidebar_branch_lbl.set_text(f"{name} ▾" if name else "")
        self.sidebar_branch.set_visible(bool(name))

    def _on_branch_switcher_clicked(self, btn):
        if not self.git.is_valid():
            return
        self.sound.play("click")
        # One popover per anchor widget, created lazily and reused
        if not hasattr(self, "_branch_popovers"):
            self._branch_popovers = {}
        pop = self._branch_popovers.get(btn)
        if pop is None:
            pop = BranchSwitcherPopover(
                window=self,
                git_engine=self.git,
                sound_engine=self.sound,
                get_token=lambda: self.telemetry.token,
                on_changed=self._on_branches_changed,
                on_error=self._show_error_dialog,
            )
            pop.set_parent(btn)
            self._branch_popovers[btn] = pop
        pop.open()

    def _on_branches_changed(self):
        self._load_repo_data()
        if self.active_view == "history":
            self._refresh_history_view()
        elif self.active_view == "pulse":
            self._refresh_pulse_view()

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
            token=self.telemetry.token,
            on_tag_created=self._load_repo_data
        )
        dlg.present()

    def _show_error_dialog(self, title, msg):
        show_error_dialog(self, title, msg, on_open_token_guide=lambda: self._on_token_dialog(None))


class GitPulseApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.xronni.gitpulse")

    def do_activate(self):
        # The whole UI is designed dark; keep Adw widgets (dialogs, header bars) consistent
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
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
