#!/usr/bin/env python3
"""
GitPulse HUD — AAA Grade GTK4 / Libadwaita Git Companion
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
        self.set_default_size(980, 680)
        self.add_css_class("git-pulse-window")

        self.config = self._load_config()
        i18n.set_language(self.config.get("language", "ru"))

        self.sound = SoundEngine(enabled=self.config.get("sound_enabled", True))
        
        initial_repo = self.config.get("last_repo")
        if not initial_repo or not os.path.exists(initial_repo):
            initial_repo = os.getcwd()
        self.git = GitEngine(initial_repo)
        if not self.git.is_valid():
            parent_spotify = "/home/xronni/Документы/other/projects/spotify-mini-player"
            if os.path.exists(parent_spotify):
                self.git.set_repo(parent_spotify)

        self.telemetry = GitHubTelemetry(token=self.config.get("github_token", ""))
        self.active_view = "changes"
        self.selected_type = "feat"

        self._build_main_layout()
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

    def _build_main_layout(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(root_box)

        # 1. Left Sidebar
        self._build_sidebar(root_box)

        # 2. Main Content
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.content_box.add_css_class("content-area")
        self.content_box.set_hexpand(True)
        self.content_box.set_vexpand(True)
        root_box.append(self.content_box)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(180)
        self.stack.set_vexpand(True)
        self.content_box.append(self.stack)

        self._build_view_changes()
        self._build_view_history()
        self._build_view_pulse()
        self._build_view_telemetry()

    def _build_sidebar(self, parent):
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.add_css_class("sidebar-box")
        sidebar.set_size_request(240, -1)
        parent.append(sidebar)

        # Brand Header with crisp full-bleed icon
        brand_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        if os.path.exists(ICON_FILE):
            icon_img = Gtk.Image.new_from_file(ICON_FILE)
            icon_img.set_pixel_size(36)
            icon_img.add_css_class("brand-icon")
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

        lbl_sub = Gtk.Label(label="Git Staging & Telemetry")
        lbl_sub.add_css_class("brand-subtitle")
        lbl_sub.set_xalign(0)
        title_box.append(lbl_sub)

        brand_row.append(title_box)
        sidebar.append(brand_row)

        # Active Repository Card (Clean & Unified)
        repo_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        repo_card.add_css_class("sidebar-repo-card")

        top_r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.sidebar_repo_name = Gtk.Label(label=self.git.get_repo_name())
        self.sidebar_repo_name.add_css_class("repo-name-text")
        self.sidebar_repo_name.set_ellipsize(Pango.EllipsizeMode.END)
        self.sidebar_repo_name.set_xalign(0)
        self.sidebar_repo_name.set_hexpand(True)
        top_r.append(self.sidebar_repo_name)

        btn_open = Gtk.Button()
        btn_open.set_icon_name("folder-open-symbolic")
        btn_open.set_tooltip_text(t("btn_open_repo"))
        btn_open.add_css_class("subtle-icon-btn")
        btn_open.connect("clicked", self._on_choose_repo)
        top_r.append(btn_open)
        repo_card.append(top_r)

        # Badges row: branch and ahead/behind
        pills_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.sidebar_branch = Gtk.Label(label=self.git.get_current_branch())
        self.sidebar_branch.add_css_class("branch-badge")
        pills_row.append(self.sidebar_branch)

        self.sidebar_ahead = Gtk.Label(label="↑0 ↓0")
        self.sidebar_ahead.add_css_class("ahead-badge")
        pills_row.append(self.sidebar_ahead)

        repo_card.append(pills_row)
        sidebar.append(repo_card)

        # Navigation Items
        self.nav_buttons = {}
        items = [
            ("changes", "document-edit-symbolic", t("tab_changes")),
            ("history", "document-open-recent-symbolic", t("tab_history")),
            ("pulse", "utilities-system-monitor-symbolic", t("tab_pulse")),
            ("telemetry", "network-workgroup-symbolic", t("tab_telemetry")),
        ]

        for nav_id, icon_name, label_text in items:
            btn = Gtk.Button()
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            img = Gtk.Image.new_from_icon_name(icon_name)
            lbl = Gtk.Label(label=label_text)
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
            self.nav_buttons[nav_id] = (btn, lbl)

        # Push footer down
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)

        # Bottom Segmented Controls Rail
        footer_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        footer_card.add_css_class("sidebar-footer")

        self.btn_sound = Gtk.Button()
        self.btn_sound.set_icon_name("audio-volume-high-symbolic" if self.sound.enabled else "audio-volume-muted-symbolic")
        self.btn_sound.set_tooltip_text(t("sound_fx"))
        self.btn_sound.add_css_class("footer-btn")
        self.btn_sound.set_hexpand(True)
        self.btn_sound.connect("clicked", self._on_toggle_sound)
        footer_card.append(self.btn_sound)

        self.btn_lang = Gtk.Button(label="RU" if i18n.get_language() == "ru" else "EN")
        self.btn_lang.set_tooltip_text("Switch language / Сменить язык")
        self.btn_lang.add_css_class("footer-btn")
        self.btn_lang.set_hexpand(True)
        self.btn_lang.connect("clicked", self._on_toggle_lang)
        footer_card.append(self.btn_lang)

        btn_token = Gtk.Button()
        btn_token.set_icon_name("dialog-password-symbolic")
        btn_token.set_tooltip_text(t("token_settings"))
        btn_token.add_css_class("footer-btn")
        btn_token.set_hexpand(True)
        btn_token.connect("clicked", self._on_token_dialog)
        footer_card.append(btn_token)

        btn_refresh = Gtk.Button()
        btn_refresh.set_icon_name("view-refresh-symbolic")
        btn_refresh.set_tooltip_text(t("btn_refresh"))
        btn_refresh.add_css_class("footer-btn")
        btn_refresh.set_hexpand(True)
        btn_refresh.connect("clicked", lambda b: self._load_repo_data())
        footer_card.append(btn_refresh)

        sidebar.append(footer_card)

    def _switch_nav(self, nav_id):
        self.active_view = nav_id
        self.sound.play("click")
        for nid, (btn, lbl) in self.nav_buttons.items():
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
        title_box.append(Gtk.Label(label=t("tab_changes"), css_classes=["view-title"], xalign=0))
        self.lbl_changes_sub = Gtk.Label(
            label="Управление рабочим деревом и Conventional Commits" if i18n.get_language() == "ru" else "Working tree & conventional commits",
            css_classes=["view-subtitle"],
            xalign=0
        )
        title_box.append(self.lbl_changes_sub)
        top_row.append(title_box)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_row.append(spacer)

        btn_stash = Gtk.Button(label=t("btn_stash"))
        btn_stash.add_css_class("subtle-btn")
        btn_stash.connect("clicked", self._on_stash)
        top_row.append(btn_stash)

        btn_pop = Gtk.Button(label=t("btn_pop"))
        btn_pop.add_css_class("subtle-btn")
        btn_pop.connect("clicked", self._on_pop_stash)
        top_row.append(btn_pop)

        page.append(top_row)

        # Scrolled file list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.append(scrolled)

        self.files_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.set_child(self.files_container)

        # Commit Composer Card
        commit_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        commit_card.add_css_class("hud-card")

        commit_card.append(Gtk.Label(label=t("commit_builder"), css_classes=["hud-card-header"], xalign=0))

        # Type Chips
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

        # Scope & Desc
        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry_scope = Gtk.Entry()
        self.entry_scope.set_placeholder_text(t("commit_scope_placeholder"))
        self.entry_scope.set_width_chars(14)
        self.entry_scope.connect("changed", lambda *a: self._update_commit_preview())
        input_row.append(self.entry_scope)

        self.entry_desc = Gtk.Entry()
        self.entry_desc.set_placeholder_text(t("commit_desc_placeholder"))
        self.entry_desc.set_hexpand(True)
        self.entry_desc.connect("changed", lambda *a: self._update_commit_preview())
        self.entry_desc.connect("activate", lambda *a: self._on_commit())
        input_row.append(self.entry_desc)

        commit_card.append(input_row)

        # Preview & Actions
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.preview_lbl = Gtk.Label(label="feat: ...")
        self.preview_lbl.add_css_class("commit-preview-box")
        self.preview_lbl.set_xalign(0)
        self.preview_lbl.set_hexpand(True)
        bottom_row.append(self.preview_lbl)

        btn_commit = Gtk.Button(label=t("btn_commit"))
        btn_commit.add_css_class("subtle-btn")
        btn_commit.connect("clicked", lambda b: self._on_commit(push=False))
        bottom_row.append(btn_commit)

        btn_commit_push = Gtk.Button(label=t("btn_commit_push"))
        btn_commit_push.add_css_class("primary-btn")
        btn_commit_push.connect("clicked", lambda b: self._on_commit(push=True))
        bottom_row.append(btn_commit_push)

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
        title_box.append(Gtk.Label(label=t("tab_history"), css_classes=["view-title"], xalign=0))
        self.lbl_hist_sub = Gtk.Label(
            label="Хронология коммитов и изменений" if i18n.get_language() == "ru" else "Chronological timeline of commits",
            css_classes=["view-subtitle"],
            xalign=0
        )
        title_box.append(self.lbl_hist_sub)
        top_row.append(title_box)
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

        commits = self.git.get_recent_commits(25)
        for c in commits:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("file-item-row")

            btn_hash = Gtk.Button(label=c["hash"])
            btn_hash.add_css_class("subtle-btn")
            btn_hash.set_tooltip_text(t("copy_hash"))
            btn_hash.connect("clicked", lambda b, h=c["hash"]: self._copy_to_clipboard(h))
            row.append(btn_hash)

            msg_lbl = Gtk.Label(label=c["message"])
            msg_lbl.set_xalign(0)
            msg_lbl.set_hexpand(True)
            msg_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(msg_lbl)

            author_lbl = Gtk.Label(label=c["author"])
            author_lbl.add_css_class("stat-label")
            row.append(author_lbl)

            date_lbl = Gtk.Label(label=c["relative_date"])
            date_lbl.add_css_class("stat-label")
            row.append(date_lbl)

            self.history_container.append(row)

    # --- VIEW 3: REPO PULSE & ANALYTICS ---

    def _build_view_pulse(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.append(Gtk.Label(label=t("tab_pulse"), css_classes=["view-title"], xalign=0))
        self.lbl_pulse_sub = Gtk.Label(
            label="Ритм активности и динамика разработки" if i18n.get_language() == "ru" else "Activity rhythm & repository velocity",
            css_classes=["view-subtitle"],
            xalign=0
        )
        title_box.append(self.lbl_pulse_sub)
        top_row.append(title_box)
        page.append(top_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.append(scrolled)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        scrolled.set_child(inner)

        # 4 Hero Metric Cards with proper Russian pluralization and color accents
        stats_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.card_commits = self._make_metric_card("0", t("stat_commits"), accent="#6366f1")
        self.card_authors = self._make_metric_card("0", t("stat_contributors"), accent="#10b981")
        self.card_files = self._make_metric_card("0", t("stat_files"), accent="#38bdf8")
        self.card_stashes = self._make_metric_card("0", t("stat_stashes"), accent="#f59e0b")

        for c in [self.card_commits, self.card_authors, self.card_files, self.card_stashes]:
            c.set_hexpand(True)
            stats_row.append(c)
        inner.append(stats_row)

        # Commit Velocity Chart Card
        vel_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vel_card.add_css_class("hud-card")
        vel_card.append(Gtk.Label(label=t("velocity_title"), css_classes=["hud-card-header"], xalign=0))
        self.vel_chart = CommitVelocityWidget()
        vel_card.append(self.vel_chart)
        inner.append(vel_card)

        # 24h Activity Distribution Card
        punch_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        punch_card.add_css_class("hud-card")
        punch_card.append(Gtk.Label(label=t("punchcard_title"), css_classes=["hud-card-header"], xalign=0))
        self.punchcard = PunchcardWidget()
        punch_card.append(self.punchcard)
        inner.append(punch_card)

        self.stack.add_named(page, "pulse")

    def _make_metric_card(self, value_text, label_text, accent="#6366f1"):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("metric-card")
        
        lbl_v = Gtk.Label(label=value_text, css_classes=["metric-number"], xalign=0)
        card.append(lbl_v)

        lbl_l = Gtk.Label(label=label_text, css_classes=["metric-label"], xalign=0)
        card.append(lbl_l)
        
        card.val_widget = lbl_v
        card.lbl_widget = lbl_l
        return card

    def _refresh_pulse_view(self):
        if not self.git.is_valid():
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
            self.card_stashes.lbl_widget.set_text(plural_ru(s_count, "в stash", "в stash", "в stash"))
        else:
            self.card_commits.lbl_widget.set_text("Commits")
            self.card_authors.lbl_widget.set_text("Contributors")
            self.card_files.lbl_widget.set_text("Files")
            self.card_stashes.lbl_widget.set_text("Stashes")

        self.vel_chart.set_data(self.git.get_commit_velocity(14))
        self.punchcard.set_hours(self.git.get_punchcard())

    # --- VIEW 4: GITHUB TELEMETRY ---

    def _build_view_telemetry(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.append(Gtk.Label(label=t("tab_telemetry"), css_classes=["view-title"], xalign=0))
        self.lbl_telem_sub = Gtk.Label(
            label="Трафик, уникальные посетители и скачивания релизов" if i18n.get_language() == "ru" else "Traffic, unique visitors & release downloads",
            css_classes=["view-subtitle"],
            xalign=0
        )
        title_box.append(self.lbl_telem_sub)
        top_row.append(title_box)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        top_row.append(spacer)

        btn_tok = Gtk.Button(label=t("token_settings"))
        btn_tok.add_css_class("subtle-btn")
        btn_tok.connect("clicked", self._on_token_dialog)
        top_row.append(btn_tok)

        page.append(top_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.append(scrolled)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        scrolled.set_child(inner)

        # 6 Hero Telemetry Cards
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

        # Middle Row: Traffic Chart & Reactions
        mid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)

        chart_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        chart_card.add_css_class("hud-card")
        chart_card.set_hexpand(True)
        chart_card.append(Gtk.Label(label="14-Day Traffic & Unique Visitors", css_classes=["hud-card-header"], xalign=0))
        self.views_chart = TrafficViewsChart()
        chart_card.append(self.views_chart)
        mid_row.append(chart_card)

        rx_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        rx_card.add_css_class("hud-card")
        rx_card.set_size_request(240, -1)
        rx_card.append(Gtk.Label(label=t("reactions"), css_classes=["hud-card-header"], xalign=0))

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

        # Bottom Row: Top Referrers & Releases
        bot_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)

        ref_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        ref_card.add_css_class("hud-card")
        ref_card.set_hexpand(True)
        ref_card.append(Gtk.Label(label=t("top_referrers"), css_classes=["hud-card-header"], xalign=0))
        self.referrers_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ref_card.append(self.referrers_container)
        bot_row.append(ref_card)

        rel_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        rel_card.add_css_class("hud-card")
        rel_card.set_hexpand(True)
        rel_card.append(Gtk.Label(label=t("release_downloads"), css_classes=["hud-card-header"], xalign=0))
        self.releases_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        rel_card.append(self.releases_container)
        bot_row.append(rel_card)

        inner.append(bot_row)

        self.stack.add_named(page, "telemetry")

    def _refresh_telemetry_view(self):
        owner, repo = self.git.get_github_coords()
        if not owner or not repo:
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
        else:
            self.ins_views.val_widget.set_text("Token Req")
            self.ins_uniques.val_widget.set_text("Token Req")
            self.views_chart.set_history([])

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
                v_lbl = Gtk.Label(label=f"{ref['views']} views", css_classes=["ahead-badge"])
                row.append(v_lbl)
                u_lbl = Gtk.Label(label=f"{ref['uniques']} uniques", css_classes=["branch-badge"])
                row.append(u_lbl)
                self.referrers_container.append(row)
        else:
            msg = t("no_referrers") if data.get("has_traffic_access") else "Configure GitHub token to see referrers"
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
                    d_lbl = Gtk.Label(label=f"{a['downloads']} dl", css_classes=["branch-badge"])
                    row.append(d_lbl)
                    self.releases_container.append(row)
        else:
            self.releases_container.append(Gtk.Label(label=t("no_releases"), css_classes=["stat-label"], xalign=0))

    # --- DATA REFRESH ---

    def _load_repo_data(self):
        if not self.git.is_valid():
            self.sidebar_repo_name.set_text("No Repository")
            self.sidebar_branch.set_text("—")
            self.sidebar_ahead.set_text("—")
            self._render_empty_changes(t("clean_tree"), t("clean_tree_sub"))
            return

        self.sidebar_repo_name.set_text(self.git.get_repo_name())
        self.sidebar_branch.set_text(self.git.get_current_branch())
        ahead, behind = self.git.get_ahead_behind()
        self.sidebar_ahead.set_text(f"↑{ahead} ↓{behind}")

        self._refresh_changes_view()
        self._update_commit_preview()

    def _refresh_changes_view(self):
        while child := self.files_container.get_first_child():
            self.files_container.remove(child)

        status = self.git.get_status_files()
        staged = status.get("staged", [])
        unstaged = status.get("unstaged", [])
        untracked = status.get("untracked", [])

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

    def _render_empty_changes(self, title, subtitle):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(60)
        box.set_margin_bottom(60)
        t_lbl = Gtk.Label(label=title, css_classes=["view-title"])
        box.append(t_lbl)
        s_lbl = Gtk.Label(label=subtitle, css_classes=["view-subtitle"])
        box.append(s_lbl)
        self.files_container.append(box)

    def _add_file_row(self, item, is_staged):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("file-item-row")

        check = Gtk.CheckButton()
        check.set_active(is_staged)
        check.connect("toggled", lambda cb: self._toggle_stage_file(item["path"], is_staged))
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

        path_lbl = Gtk.Label(label=item["path"], xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
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
        btn_diff.set_tooltip_text("View Diff")
        btn_diff.add_css_class("subtle-icon-btn")
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

    def _do_push(self):
        def _bg():
            ok, out = self.git.push()
            def _done():
                if ok:
                    self.sound.play("push")
                    self._load_repo_data()
                else:
                    self.sound.play("error")
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
                    self._save_config()
                    self._load_repo_data()
                else:
                    self.sound.play("error")
        except Exception:
            pass

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
        self.btn_lang.set_label("RU" if new_lang == "ru" else "EN")
        self.sound.play("click")

        # Update sidebar labels
        self.nav_buttons["changes"][1].set_text(t("tab_changes"))
        self.nav_buttons["history"][1].set_text(t("tab_history"))
        self.nav_buttons["pulse"][1].set_text(t("tab_pulse"))
        self.nav_buttons["telemetry"][1].set_text(t("tab_telemetry"))

        # Update subtitles
        self.lbl_changes_sub.set_text("Управление рабочим деревом и Conventional Commits" if new_lang == "ru" else "Working tree & conventional commits")
        self.lbl_hist_sub.set_text("Хронология коммитов и изменений" if new_lang == "ru" else "Chronological timeline of commits")
        self.lbl_pulse_sub.set_text("Ритм активности и динамика разработки" if new_lang == "ru" else "Activity rhythm & repository velocity")
        self.lbl_telem_sub.set_text("Трафик, уникальные посетители и скачивания релизов" if new_lang == "ru" else "Traffic, unique visitors & release downloads")

        self._load_repo_data()
        if self.active_view == "pulse":
            self._refresh_pulse_view()

    def _on_token_dialog(self, btn):
        self.sound.play("click")
        dlg = Gtk.Window(transient_for=self, modal=True)
        dlg.set_title(t("token_settings"))
        dlg.set_default_size(480, 200)
        dlg.add_css_class("token-modal-window")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(22)
        box.set_margin_bottom(22)
        box.set_margin_start(22)
        box.set_margin_end(22)
        dlg.set_child(box)

        lbl = Gtk.Label(label=t("token_hint"), wrap=True, xalign=0, css_classes=["token-hint-label"])
        box.append(lbl)

        entry = Gtk.Entry()
        entry.set_placeholder_text("ghp_xxxxxxxxxxxxxxxxxxxx")
        entry.set_text(self.config.get("github_token", ""))
        entry.add_css_class("token-entry")
        box.append(entry)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_row.append(Gtk.Box(hexpand=True))

        btn_cancel = Gtk.Button(label=t("cancel"), css_classes=["subtle-btn"])
        btn_cancel.connect("clicked", lambda b: dlg.close())
        btn_row.append(btn_cancel)

        btn_save = Gtk.Button(label=t("save"), css_classes=["primary-btn"])
        def _save():
            tok = entry.get_text().strip()
            self.config["github_token"] = tok
            self.telemetry.set_token(tok)
            self._save_config()
            self.sound.play("commit")
            dlg.close()
            if self.active_view == "telemetry":
                self._refresh_telemetry_view()
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
