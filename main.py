#!/usr/bin/env python3
"""
GitPulse HUD — Modern GTK4 / Libadwaita Git & Analytics Companion
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
from pulse_widget import CommitVelocityWidget, PunchcardWidget, TrafficViewsChart
from diff_viewer import DiffViewerDialog
import i18n
from i18n import t

CONFIG_DIR = os.path.expanduser("~/.config/git-pulse")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CSS_FILE = os.path.join(APP_DIR, "style.css")
ICON_FILE = os.path.join(APP_DIR, "assets", "icon.png")


class GitPulseWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("GitPulse HUD")
        self.set_default_size(780, 620)
        self.add_css_class("git-pulse-window")

        # Load configuration
        self.config = self._load_config()
        i18n.set_language(self.config.get("language", "ru"))

        # Initialize Engines
        self.sound = SoundEngine(enabled=self.config.get("sound_enabled", True))
        
        # Determine initial repo: config last_repo -> current working dir -> parent dir
        initial_repo = self.config.get("last_repo")
        if not initial_repo or not os.path.exists(initial_repo):
            initial_repo = os.getcwd()
        self.git = GitEngine(initial_repo)
        
        # If current dir isn't a repo, try default parent projects
        if not self.git.is_valid():
            parent_spotify = "/home/xronni/Документы/other/projects/spotify-mini-player"
            if os.path.exists(parent_spotify):
                self.git.set_repo(parent_spotify)

        self.telemetry = GitHubTelemetry(token=self.config.get("github_token", ""))
        self.insights_cache = None
        self.active_tab = "stage"

        # Build UI
        self._build_ui()
        self._load_repo_data()

    def _load_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "last_repo": os.getcwd(),
            "sound_enabled": True,
            "language": "ru",
            "github_token": "",
            "recent_repos": []
        }

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def _build_ui(self):
        # Outer Frame / Acrylic card
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer_box)

        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.card.add_css_class("git-pulse-card")
        self.card.set_vexpand(True)
        self.card.set_hexpand(True)
        self.card.set_margin_top(8)
        self.card.set_margin_bottom(8)
        self.card.set_margin_start(8)
        self.card.set_margin_end(8)
        outer_box.append(self.card)

        # 1. Top Header Bar
        self._build_header()

        # 2. Navigation Tabs Bar
        self._build_nav_tabs()

        # 3. Stack of Views
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.set_vexpand(True)
        self.card.append(self.stack)

        self._build_view_staging()
        self._build_view_pulse()
        self._build_view_insights()

        # 4. Bottom Status Bar
        self._build_status_bar()

    def _build_header(self):
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.add_css_class("header-box")

        # App Icon & Title
        if os.path.exists(ICON_FILE):
            icon_img = Gtk.Image.new_from_file(ICON_FILE)
            icon_img.set_pixel_size(24)
            header_box.append(icon_img)

        title_lbl = Gtk.Label(label="GitPulse")
        title_lbl.add_css_class("heading")
        title_lbl.set_markup("<b>GitPulse</b>")
        header_box.append(title_lbl)

        # Repo Name Badge
        self.repo_badge = Gtk.Label(label=self.git.get_repo_name())
        self.repo_badge.add_css_class("repo-badge")
        header_box.append(self.repo_badge)

        # Branch Pill
        self.branch_pill = Gtk.Label(label=" " + self.git.get_current_branch())
        self.branch_pill.add_css_class("branch-pill")
        header_box.append(self.branch_pill)

        # Ahead/Behind Pill
        self.ab_pill = Gtk.Label(label="↑0 ↓0")
        self.ab_pill.add_css_class("ahead-behind-pill")
        header_box.append(self.ab_pill)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        # Action Buttons
        # Open Repo
        btn_open = Gtk.Button(label="📁")
        btn_open.set_tooltip_text(t("btn_open_repo"))
        btn_open.add_css_class("icon-btn")
        btn_open.connect("clicked", self._on_choose_repo)
        header_box.append(btn_open)

        # Refresh
        btn_refresh = Gtk.Button(label="🔄")
        btn_refresh.set_tooltip_text(t("btn_refresh"))
        btn_refresh.add_css_class("icon-btn")
        btn_refresh.connect("clicked", lambda b: self._load_repo_data())
        header_box.append(btn_refresh)

        # Sound FX Toggle
        self.btn_sound = Gtk.Button(label="🔊" if self.sound.enabled else "🔇")
        self.btn_sound.set_tooltip_text(t("sound_fx"))
        self.btn_sound.add_css_class("icon-btn")
        self.btn_sound.connect("clicked", self._on_toggle_sound)
        header_box.append(self.btn_sound)

        # GitHub Token Settings
        btn_token = Gtk.Button(label="🔑")
        btn_token.set_tooltip_text(t("token_settings"))
        btn_token.add_css_class("icon-btn")
        btn_token.connect("clicked", self._on_token_dialog)
        header_box.append(btn_token)

        # Language Switcher
        self.btn_lang = Gtk.Button(label="RU" if i18n.get_language() == "ru" else "EN")
        self.btn_lang.set_tooltip_text("Switch language / Сменить язык")
        self.btn_lang.add_css_class("icon-btn")
        self.btn_lang.connect("clicked", self._on_toggle_lang)
        header_box.append(self.btn_lang)

        self.card.append(header_box)

    def _build_nav_tabs(self):
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav_box.add_css_class("nav-tab-box")

        self.btn_tab_stage = Gtk.Button(label=t("tab_stage"))
        self.btn_tab_stage.add_css_class("nav-tab-btn")
        self.btn_tab_stage.add_css_class("active")
        self.btn_tab_stage.connect("clicked", lambda b: self._switch_tab("stage"))
        nav_box.append(self.btn_tab_stage)

        self.btn_tab_pulse = Gtk.Button(label=t("tab_pulse"))
        self.btn_tab_pulse.add_css_class("nav-tab-btn")
        self.btn_tab_pulse.connect("clicked", lambda b: self._switch_tab("pulse"))
        nav_box.append(self.btn_tab_pulse)

        self.btn_tab_insights = Gtk.Button(label=t("tab_insights"))
        self.btn_tab_insights.add_css_class("nav-tab-btn")
        self.btn_tab_insights.connect("clicked", lambda b: self._switch_tab("insights"))
        nav_box.append(self.btn_tab_insights)

        self.card.append(nav_box)

    def _switch_tab(self, tab_id):
        self.active_tab = tab_id
        self.sound.play("click")
        self.btn_tab_stage.remove_css_class("active")
        self.btn_tab_pulse.remove_css_class("active")
        self.btn_tab_insights.remove_css_class("active")

        if tab_id == "stage":
            self.btn_tab_stage.add_css_class("active")
            self.stack.set_visible_child_name("stage")
        elif tab_id == "pulse":
            self.btn_tab_pulse.add_css_class("active")
            self.stack.set_visible_child_name("pulse")
            self._refresh_pulse_view()
        elif tab_id == "insights":
            self.btn_tab_insights.add_css_class("active")
            self.stack.set_visible_child_name("insights")
            self._refresh_insights_view()

    # --- VIEW 1: STAGING & CONVENTIONAL COMMITS ---

    def _build_view_staging(self):
        box_stage = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box_stage.set_vexpand(True)

        # Scrolled container for file status lists
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box_stage.append(scrolled)

        self.files_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.files_container.set_margin_start(4)
        self.files_container.set_margin_end(4)
        scrolled.set_child(self.files_container)

        # Conventional Commit Builder Card
        commit_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        commit_card.add_css_class("commit-card")

        # Row 1: Type Dropdown + Scope Entry + Breaking Change Checkbox
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        lbl_type = Gtk.Label(label=t("commit_type") + ":")
        row1.append(lbl_type)

        types = ["feat", "fix", "refactor", "docs", "perf", "chore", "test", "style", "ci"]
        self.combo_type = Gtk.DropDown.new_from_strings(types)
        self.combo_type.connect("notify::selected", lambda *a: self._update_commit_preview())
        row1.append(self.combo_type)

        self.entry_scope = Gtk.Entry()
        self.entry_scope.set_placeholder_text(t("commit_scope"))
        self.entry_scope.set_width_chars(12)
        self.entry_scope.connect("changed", lambda *a: self._update_commit_preview())
        row1.append(self.entry_scope)

        self.check_breaking = Gtk.CheckButton(label=t("breaking_change"))
        self.check_breaking.connect("toggled", lambda *a: self._update_commit_preview())
        row1.append(self.check_breaking)

        commit_card.append(row1)

        # Row 2: Description Entry
        self.entry_desc = Gtk.Entry()
        self.entry_desc.set_placeholder_text(t("commit_desc"))
        self.entry_desc.connect("changed", lambda *a: self._update_commit_preview())
        self.entry_desc.connect("activate", lambda *a: self._on_commit())
        commit_card.append(self.entry_desc)

        # Row 3: Live Preview Pill
        self.preview_lbl = Gtk.Label(label="feat: ...")
        self.preview_lbl.add_css_class("preview-pill")
        self.preview_lbl.set_xalign(0)
        commit_card.append(self.preview_lbl)

        # Row 4: Action Buttons (Stash, Pop, Commit, Commit & Push)
        row_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        btn_stash = Gtk.Button(label="📥 " + t("btn_stash"))
        btn_stash.connect("clicked", self._on_stash)
        row_actions.append(btn_stash)

        btn_pop = Gtk.Button(label="📤 " + t("btn_pop"))
        btn_pop.connect("clicked", self._on_pop_stash)
        row_actions.append(btn_pop)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        row_actions.append(spacer)

        btn_commit = Gtk.Button(label="✔ " + t("btn_commit"))
        btn_commit.add_css_class("suggested-action")
        btn_commit.connect("clicked", lambda b: self._on_commit())
        row_actions.append(btn_commit)

        btn_commit_push = Gtk.Button(label="🚀 " + t("btn_commit_push"))
        btn_commit_push.add_css_class("suggested-action")
        btn_commit_push.connect("clicked", lambda b: self._on_commit(push=True))
        row_actions.append(btn_commit_push)

        commit_card.append(row_actions)
        box_stage.append(commit_card)

        self.stack.add_named(box_stage, "stage")

    def _update_commit_preview(self):
        types = ["feat", "fix", "refactor", "docs", "perf", "chore", "test", "style", "ci"]
        c_type = types[self.combo_type.get_selected()]
        scope = self.entry_scope.get_text().strip()
        breaking = "!" if self.check_breaking.get_active() else ""
        desc = self.entry_desc.get_text().strip() or "..."
        
        if scope:
            msg = f"{c_type}({scope}){breaking}: {desc}"
        else:
            msg = f"{c_type}{breaking}: {desc}"
        self.preview_lbl.set_text(msg)

    # --- VIEW 2: REPO PULSE & ANALYTICS ---

    def _build_view_pulse(self):
        box_pulse = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box_pulse.set_vexpand(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box_pulse.append(scrolled)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scrolled.set_child(inner)

        # Upper row: Commit Velocity Chart & Stats Cards
        chart_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        # Velocity Chart Box
        vel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vel_lbl = Gtk.Label(label="📈 " + t("velocity_title"))
        vel_lbl.set_xalign(0)
        vel_lbl.add_css_class("heading")
        vel_box.append(vel_lbl)

        self.vel_chart = CommitVelocityWidget()
        vel_box.append(self.vel_chart)
        vel_box.set_hexpand(True)
        chart_row.append(vel_box)

        # 4 Stat Cards
        stats_grid = Gtk.Grid()
        stats_grid.set_column_spacing(8)
        stats_grid.set_row_spacing(8)

        self.card_commits = self._make_stat_card("0", t("stat_commits"))
        self.card_authors = self._make_stat_card("0", t("stat_contributors"))
        self.card_files = self._make_stat_card("0", t("stat_files"))
        self.card_stashes = self._make_stat_card("0", t("stat_stashes"))

        stats_grid.attach(self.card_commits, 0, 0, 1, 1)
        stats_grid.attach(self.card_authors, 1, 0, 1, 1)
        stats_grid.attach(self.card_files, 0, 1, 1, 1)
        stats_grid.attach(self.card_stashes, 1, 1, 1, 1)
        chart_row.append(stats_grid)

        inner.append(chart_row)

        # 24h Punchcard Rhythm
        punch_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        punch_lbl = Gtk.Label(label="⏱ " + t("punchcard_title"))
        punch_lbl.set_xalign(0)
        punch_lbl.add_css_class("heading")
        punch_box.append(punch_lbl)

        self.punchcard = PunchcardWidget()
        punch_box.append(self.punchcard)
        inner.append(punch_box)

        # Recent Commits Timeline Feed
        feed_lbl = Gtk.Label(label="📜 " + t("recent_commits"))
        feed_lbl.set_xalign(0)
        feed_lbl.add_css_class("heading")
        inner.append(feed_lbl)

        self.feed_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.append(self.feed_container)

        self.stack.add_named(box_pulse, "pulse")

    def _make_stat_card(self, val_text, label_text):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        card.add_css_class("stat-card")
        
        lbl_val = Gtk.Label(label=val_text)
        lbl_val.add_css_class("stat-value")
        card.append(lbl_val)

        lbl_desc = Gtk.Label(label=label_text)
        lbl_desc.add_css_class("stat-label")
        card.append(lbl_desc)

        card.val_widget = lbl_val
        return card

    # --- VIEW 3: GITHUB TELEMETRY & INSIGHTS ---

    def _build_view_insights(self):
        box_ins = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box_ins.set_vexpand(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box_ins.append(scrolled)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scrolled.set_child(inner)

        # Top Stat Cards: Views, Uniques, Stars, Forks, Downloads, Issues
        self.insights_stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.ins_views = self._make_stat_card("—", t("views_14d"))
        self.ins_uniques = self._make_stat_card("—", t("uniques_14d"))
        self.ins_stars = self._make_stat_card("0", t("stars"))
        self.ins_forks = self._make_stat_card("0", t("forks"))
        self.ins_downloads = self._make_stat_card("0", t("downloads"))
        self.ins_issues = self._make_stat_card("0", t("open_issues"))

        for c in [self.ins_views, self.ins_uniques, self.ins_stars, self.ins_forks, self.ins_downloads, self.ins_issues]:
            c.set_hexpand(True)
            self.insights_stats_box.append(c)
        inner.append(self.insights_stats_box)

        # Middle row: Traffic Chart & Reactions
        mid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        # Traffic Chart
        chart_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        chart_lbl = Gtk.Label(label="👀 " + t("views_14d") + " & " + t("uniques_14d"))
        chart_lbl.set_xalign(0)
        chart_lbl.add_css_class("heading")
        chart_box.append(chart_lbl)

        self.views_chart = TrafficViewsChart()
        chart_box.append(self.views_chart)
        chart_box.set_hexpand(True)
        mid_row.append(chart_box)

        # Community Reactions Card
        rx_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        rx_lbl = Gtk.Label(label=t("reactions"))
        rx_lbl.set_xalign(0)
        rx_lbl.add_css_class("heading")
        rx_box.append(rx_lbl)

        self.rx_grid = Gtk.Grid()
        self.rx_grid.set_column_spacing(10)
        self.rx_grid.set_row_spacing(8)
        self.rx_labels = {}
        emojis = [("👍", "+1"), ("❤️", "heart"), ("🚀", "rocket"), ("🎉", "hooray"), ("👀", "eyes"), ("😄", "laugh")]
        for i, (emoji, key) in enumerate(emojis):
            row = i // 2
            col = (i % 2) * 2
            e_lbl = Gtk.Label(label=emoji)
            c_lbl = Gtk.Label(label="0")
            c_lbl.add_css_class("stat-value")
            c_lbl.set_markup("<b>0</b>")
            self.rx_labels[key] = c_lbl
            self.rx_grid.attach(e_lbl, col, row, 1, 1)
            self.rx_grid.attach(c_lbl, col + 1, row, 1, 1)

        rx_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        rx_card.add_css_class("stat-card")
        rx_card.append(self.rx_grid)
        rx_box.append(rx_card)
        mid_row.append(rx_box)

        inner.append(mid_row)

        # Lower row: Referrers (Where visitors come from) & Release Downloads List
        low_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        # Top Referrers Box
        ref_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        ref_lbl = Gtk.Label(label="🌐 " + t("top_referrers"))
        ref_lbl.set_xalign(0)
        ref_lbl.add_css_class("heading")
        ref_box.append(ref_lbl)

        self.referrers_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ref_box.append(self.referrers_container)
        ref_box.set_hexpand(True)
        low_row.append(ref_box)

        # Release Assets Box
        rel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        rel_lbl = Gtk.Label(label="📦 " + t("release_downloads"))
        rel_lbl.set_xalign(0)
        rel_lbl.add_css_class("heading")
        rel_box.append(rel_lbl)

        self.releases_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rel_box.append(self.releases_container)
        rel_box.set_hexpand(True)
        low_row.append(rel_box)

        inner.append(low_row)

        self.stack.add_named(box_ins, "insights")

    def _build_status_bar(self):
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.status_box.add_css_class("status-bar")

        self.lbl_path = Gtk.Label(label=self.git.root_path or "No Git Repo")
        self.lbl_path.set_xalign(0)
        self.lbl_path.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.status_box.append(self.lbl_path)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.status_box.append(spacer)

        self.lbl_sync = Gtk.Label(label="Ready")
        self.status_box.append(self.lbl_sync)

        self.card.append(self.status_box)

    # --- DATA LOADING & UPDATES ---

    def _load_repo_data(self):
        if not self.git.is_valid():
            self.repo_badge.set_text("No Repo")
            self.branch_pill.set_text("—")
            self.ab_pill.set_text("—")
            self._render_empty_staging("Please open a valid Git repository.")
            return

        # Update Top Header
        self.repo_badge.set_text(self.git.get_repo_name())
        self.branch_pill.set_text(" " + self.git.get_current_branch())
        ahead, behind = self.git.get_ahead_behind()
        self.ab_pill.set_text(f"↑{ahead} ↓{behind}")
        self.lbl_path.set_text(self.git.root_path)

        # Update Staging list
        self._refresh_staging_view()
        self._update_commit_preview()

        # Update status
        now_str = datetime.now().strftime("%H:%M:%S")
        self.lbl_sync.set_text(f"Updated at {now_str}")

    def _refresh_staging_view(self):
        # Clear previous rows
        while child := self.files_container.get_first_child():
            self.files_container.remove(child)

        status = self.git.get_status_files()
        staged = status.get("staged", [])
        unstaged = status.get("unstaged", [])
        untracked = status.get("untracked", [])

        if not staged and not unstaged and not untracked:
            self._render_empty_staging(t("clean_tree"))
            return

        # 1. Staged Section
        if staged:
            staged_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl = Gtk.Label(label=f"✔ {t('staged_changes')} ({len(staged)})")
            lbl.add_css_class("heading")
            staged_hdr.append(lbl)

            btn_unstage_all = Gtk.Button(label=t("unstage_all"))
            btn_unstage_all.add_css_class("flat")
            btn_unstage_all.connect("clicked", self._on_unstage_all)
            staged_hdr.append(btn_unstage_all)
            self.files_container.append(staged_hdr)

            for item in staged:
                self._add_file_row(item, is_staged=True)

        # 2. Unstaged Section
        if unstaged:
            unstaged_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            unstaged_hdr.set_margin_top(8)
            lbl = Gtk.Label(label=f"✎ {t('unstaged_changes')} ({len(unstaged)})")
            lbl.add_css_class("heading")
            unstaged_hdr.append(lbl)

            btn_stage_all = Gtk.Button(label=t("stage_all"))
            btn_stage_all.add_css_class("flat")
            btn_stage_all.connect("clicked", self._on_stage_all)
            unstaged_hdr.append(btn_stage_all)
            self.files_container.append(unstaged_hdr)

            for item in unstaged:
                self._add_file_row(item, is_staged=False)

        # 3. Untracked Section
        if untracked:
            untracked_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            untracked_hdr.set_margin_top(8)
            lbl = Gtk.Label(label=f"➕ {t('untracked_files')} ({len(untracked)})")
            lbl.add_css_class("heading")
            untracked_hdr.append(lbl)
            self.files_container.append(untracked_hdr)

            for item in untracked:
                self._add_file_row(item, is_staged=False)

    def _render_empty_staging(self, message):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        lbl = Gtk.Label(label=message)
        lbl.add_css_class("heading")
        box.append(lbl)
        self.files_container.append(box)

    def _add_file_row(self, item, is_staged):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("file-row")

        # Checkbox for staging/unstaging
        check = Gtk.CheckButton()
        check.set_active(is_staged)
        check.connect("toggled", lambda cb: self._toggle_stage_file(item["path"], is_staged))
        row.append(check)

        # Status badge
        st_char = item.get("status", "M")
        badge = Gtk.Label(label=st_char)
        if st_char in ["M", "T"]:
            badge.add_css_class("badge-status-m")
        elif st_char in ["A", "?"]:
            badge.add_css_class("badge-status-a")
        else:
            badge.add_css_class("badge-status-d")
        row.append(badge)

        # Path label
        path_lbl = Gtk.Label(label=item["path"])
        path_lbl.set_xalign(0)
        path_lbl.set_hexpand(True)
        path_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        row.append(path_lbl)

        # Additions & Deletions
        add = item.get("lines_add", 0)
        dels = item.get("lines_del", 0)
        if add > 0 or dels > 0:
            stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            if add > 0:
                l_add = Gtk.Label(label=f"+{add}")
                l_add.add_css_class("badge-add")
                stats_box.append(l_add)
            if dels > 0:
                l_del = Gtk.Label(label=f"-{dels}")
                l_del.add_css_class("badge-del")
                stats_box.append(l_del)
            row.append(stats_box)

        # Diff View Button
        btn_diff = Gtk.Button(label="🔍")
        btn_diff.set_tooltip_text("View Diff")
        btn_diff.add_css_class("icon-btn")
        btn_diff.connect("clicked", lambda b: self._show_diff(item["path"], is_staged))
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

        types = ["feat", "fix", "refactor", "docs", "perf", "chore", "test", "style", "ci"]
        c_type = types[self.combo_type.get_selected()]
        scope = self.entry_scope.get_text().strip()
        breaking = "!" if self.check_breaking.get_active() else ""
        
        if scope:
            full_msg = f"{c_type}({scope}){breaking}: {desc}"
        else:
            full_msg = f"{c_type}{breaking}: {desc}"

        ok, out = self.git.commit(full_msg)
        if ok:
            self.sound.play("commit")
            self.entry_desc.set_text("")
            self._load_repo_data()
            if push:
                self._do_push()
        else:
            self.sound.play("error")
            self.lbl_sync.set_text(t("error_commit") + f": {out[:40]}")

    def _do_push(self):
        def _bg():
            ok, out = self.git.push()
            def _done():
                if ok:
                    self.sound.play("push")
                    self.lbl_sync.set_text(t("push_success"))
                    self._load_repo_data()
                else:
                    self.sound.play("error")
                    self.lbl_sync.set_text(t("error_push") + f": {out[:40]}")
            GLib.idle_add(_done)
        threading.Thread(target=_bg, daemon=True).start()

    def _on_stash(self, btn):
        ok, out = self.git.stash_save()
        if ok:
            self.sound.play("pop")
            self.lbl_sync.set_text(t("stash_success"))
            self._load_repo_data()

    def _on_pop_stash(self, btn):
        ok, out = self.git.stash_pop()
        if ok:
            self.sound.play("pop")
            self.lbl_sync.set_text(t("pop_success"))
            self._load_repo_data()

    # --- REPO PULSE VIEW LOGIC ---

    def _refresh_pulse_view(self):
        if not self.git.is_valid():
            return

        summary = self.git.get_repo_summary()
        self.card_commits.val_widget.set_text(str(summary["total_commits"]))
        self.card_authors.val_widget.set_text(str(summary["contributors"]))
        self.card_files.val_widget.set_text(str(summary["files_count"]))
        self.card_stashes.val_widget.set_text(str(summary["stashes"]))

        # Update Velocity Chart
        velocity_data = self.git.get_commit_velocity(14)
        self.vel_chart.set_data(velocity_data)

        # Update Punchcard
        hours = self.git.get_punchcard()
        self.punchcard.set_hours(hours)

        # Update Feed
        while child := self.feed_container.get_first_child():
            self.feed_container.remove(child)

        commits = self.git.get_recent_commits(8)
        for c in commits:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("file-row")

            btn_hash = Gtk.Button(label=c["hash"])
            btn_hash.add_css_class("branch-pill")
            btn_hash.set_tooltip_text(t("copy_hash"))
            btn_hash.connect("clicked", lambda b, h=c["hash"]: self._copy_to_clipboard(h))
            row.append(btn_hash)

            msg_lbl = Gtk.Label(label=c["message"])
            msg_lbl.set_xalign(0)
            msg_lbl.set_hexpand(True)
            msg_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(msg_lbl)

            author_lbl = Gtk.Label(label=c["author"])
            author_lbl.add_css_class("ahead-behind-pill")
            row.append(author_lbl)

            date_lbl = Gtk.Label(label=c["relative_date"])
            date_lbl.add_css_class("stat-label")
            row.append(date_lbl)

            self.feed_container.append(row)

    def _copy_to_clipboard(self, text):
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)
        self.sound.play("click")
        self.lbl_sync.set_text(t("hash_copied"))

    # --- GITHUB INSIGHTS VIEW LOGIC ---

    def _refresh_insights_view(self):
        owner, repo = self.git.get_github_coords()
        if not owner or not repo:
            self.lbl_sync.set_text("Remote is not a GitHub repository.")
            return

        def _worker():
            data = self.telemetry.fetch_full_insights(owner, repo)
            GLib.idle_add(lambda: self._apply_insights_data(data))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_insights_data(self, data):
        self.insights_cache = data
        self.ins_stars.val_widget.set_text(str(data["stars"]))
        self.ins_forks.val_widget.set_text(str(data["forks"]))
        self.ins_downloads.val_widget.set_text(str(data["total_downloads"]))
        self.ins_issues.val_widget.set_text(str(data["open_issues"]))

        if data.get("has_traffic_access"):
            self.ins_views.val_widget.set_text(str(data["views_total"]))
            self.ins_uniques.val_widget.set_text(str(data["views_uniques"]))
            self.views_chart.set_history(data.get("views_history", []))
        else:
            self.ins_views.val_widget.set_text("🔑 Req")
            self.ins_uniques.val_widget.set_text("🔑 Req")
            self.views_chart.set_history([])

        # Update Reactions
        rx = data.get("reactions", {})
        for key, widget in self.rx_labels.items():
            widget.set_markup(f"<b>{rx.get(key, 0)}</b>")

        # Update Referrers
        while child := self.referrers_container.get_first_child():
            self.referrers_container.remove(child)

        referrers = data.get("referrers", [])
        if referrers:
            for ref in referrers:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.add_css_class("referrer-row")

                site_lbl = Gtk.Label(label=ref["site"])
                site_lbl.set_xalign(0)
                site_lbl.set_hexpand(True)
                row.append(site_lbl)

                v_badge = Gtk.Label(label=f"👀 {ref['views']}")
                v_badge.add_css_class("referrer-badge")
                row.append(v_badge)

                u_badge = Gtk.Label(label=f"👤 {ref['uniques']}")
                u_badge.add_css_class("referrer-badge")
                row.append(u_badge)

                self.referrers_container.append(row)
        else:
            msg = t("no_referrers") if data.get("has_traffic_access") else "🔑 Add GitHub token to see referrers (Habr, Reddit, etc.)"
            lbl = Gtk.Label(label=msg)
            lbl.add_css_class("stat-label")
            self.referrers_container.append(lbl)

        # Update Release Downloads
        while child := self.releases_container.get_first_child():
            self.releases_container.remove(child)

        releases = data.get("releases", [])
        if releases:
            for rel in releases:
                for a in rel.get("assets", []):
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                    row.add_css_class("release-asset-row")

                    name_lbl = Gtk.Label(label=a["name"])
                    name_lbl.set_xalign(0)
                    name_lbl.set_hexpand(True)
                    name_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                    row.append(name_lbl)

                    d_badge = Gtk.Label(label=f"📦 {a['downloads']} dl")
                    d_badge.add_css_class("referrer-badge")
                    row.append(d_badge)

                    self.releases_container.append(row)
        else:
            lbl = Gtk.Label(label=t("no_releases"))
            lbl.add_css_class("stat-label")
            self.releases_container.append(lbl)

    # --- DIALOGS & SETTINGS ---

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
                    self._save_config()
                    self._load_repo_data()
                else:
                    self.sound.play("error")
                    self.lbl_sync.set_text("Selected folder is not a Git repository.")
        except Exception:
            pass

    def _on_toggle_sound(self, btn):
        self.sound.enabled = not self.sound.enabled
        self.config["sound_enabled"] = self.sound.enabled
        self._save_config()
        self.btn_sound.set_label("🔊" if self.sound.enabled else "🔇")
        if self.sound.enabled:
            self.sound.play("click")

    def _on_toggle_lang(self, btn):
        new_lang = "en" if i18n.get_language() == "ru" else "ru"
        i18n.set_language(new_lang)
        self.config["language"] = new_lang
        self._save_config()
        self.btn_lang.set_label("RU" if new_lang == "ru" else "EN")
        self.sound.play("click")
        # Update tab labels
        self.btn_tab_stage.set_label(t("tab_stage"))
        self.btn_tab_pulse.set_label(t("tab_pulse"))
        self.btn_tab_insights.set_label(t("tab_insights"))
        self._load_repo_data()

    def _on_token_dialog(self, btn):
        self.sound.play("click")
        dlg = Gtk.Window(transient_for=self, modal=True)
        dlg.set_title(t("token_settings"))
        dlg.set_default_size(480, 220)
        dlg.add_css_class("diff-dialog")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        dlg.set_child(box)

        lbl = Gtk.Label(label=t("token_hint"))
        lbl.set_wrap(True)
        lbl.set_xalign(0)
        box.append(lbl)

        entry = Gtk.Entry()
        entry.set_placeholder_text("ghp_xxxxxxxxxxxxxxxxxxxx")
        entry.set_text(self.config.get("github_token", ""))
        box.append(entry)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btn_row.append(spacer)

        btn_cancel = Gtk.Button(label=t("cancel"))
        btn_cancel.connect("clicked", lambda b: dlg.close())
        btn_row.append(btn_cancel)

        btn_save = Gtk.Button(label=t("save"))
        btn_save.add_css_class("suggested-action")
        def _save():
            tok = entry.get_text().strip()
            self.config["github_token"] = tok
            self.telemetry.set_token(tok)
            self._save_config()
            self.sound.play("commit")
            self.lbl_sync.set_text(t("token_saved"))
            dlg.close()
            if self.active_tab == "insights":
                self._refresh_insights_view()
        btn_save.connect("clicked", lambda b: _save())
        btn_row.append(btn_save)

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
