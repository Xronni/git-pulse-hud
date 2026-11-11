#!/usr/bin/env python3
"""
GitPulse HUD — Repository Pulse and GitHub Analytics views.

Mixin for GitPulseWindow (see main.py); relies on attributes created there.
"""

import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GLib, Gtk, Pango

import i18n
from i18n import plural_ru, t
from pulse_widget import CommitVelocityWidget, PunchcardWidget, TrafficViewsChart


class InsightsViewMixin:
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
