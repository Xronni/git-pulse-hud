#!/usr/bin/env python3
"""
GitPulse HUD — Commit History view: branch graph, commit diff on click, edit last commit message.

Mixin for GitPulseWindow (see main.py); relies on attributes created there.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Pango

from diff_viewer import DiffViewerDialog
import i18n
from i18n import t
from pulse_widget import BranchGraphNodeWidget
from ui_dialogs import show_choice_dialog


class HistoryViewMixin:
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
        self.btn_branch_switch.set_tooltip_text(t("branch_switch_tooltip"))
        self.btn_branch_switch.connect("clicked", self._on_branch_switcher_clicked)
        top_row.append(self.btn_branch_switch)

        page.append(top_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.append(scrolled)

        self.history_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.history_container.set_vexpand(True)
        self.history_container.set_hexpand(True)
        scrolled.set_child(self.history_container)

        self.stack.add_named(page, "history")

    def _refresh_history_view(self):
        while child := self.history_container.get_first_child():
            self.history_container.remove(child)

        if not self.git.is_valid():
            self.btn_branch_switch.set_label("🌿 — ▾")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_vexpand(True)
            box.set_hexpand(True)
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
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_vexpand(True)
            box.set_hexpand(True)
            icon = Gtk.Image.new_from_icon_name("document-open-recent-symbolic")
            icon.set_pixel_size(44)
            box.append(icon)
            lbl = Gtk.Label(label=t("no_velocity_title"), css_classes=["view-title"])
            box.append(lbl)
            sub = Gtk.Label(label=t("no_velocity_desc"), css_classes=["view-subtitle"])
            box.append(sub)
            self.history_container.append(box)
            return

        for idx, c in enumerate(commits):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("file-item-row")
            row.add_css_class("history-row")
            row.set_tooltip_text(t("history_row_tooltip"))
            row_click = Gtk.GestureClick()
            row_click.connect("released", lambda g, n, x, y, r=row, h=c["hash"], m=c["message"]:
                              self._on_history_row_clicked(r, x, y, h, m))
            row.add_controller(row_click)

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

            if idx == 0 and not self.git.is_detached():
                btn_reword = Gtk.Button(icon_name="document-edit-symbolic", css_classes=["subtle-icon-btn"])
                btn_reword.set_tooltip_text(t("reword_tooltip"))
                btn_reword.connect("clicked", lambda b: self._on_reword_head())
                row.append(btn_reword)

            self.history_container.append(row)

    def _on_history_row_clicked(self, row, x, y, commit_hash, message):
        if self._click_hits_button(row, x, y):
            return
        self.sound.play("click")
        dlg = DiffViewerDialog(
            self,
            filename=f"{commit_hash} — {message}",
            diff_text=self.git.show_commit(commit_hash),
            subtitle=t("commit_diff_sub"),
        )
        dlg.present()

    def _on_reword_head(self):
        subject, _ = self.git.get_last_commit_message()

        def apply(choice, new_subject):
            if choice != "reword" or not new_subject or new_subject == subject:
                return
            ok, out = self.git.reword_head(new_subject)
            if ok:
                self.sound.play("commit")
                self._toast(t("amend_done"))
                self._load_repo_data()
                self._refresh_history_view()
            else:
                self.sound.play("error")
                self._show_error_dialog(t("commit_failed"), out)

        desc = t("reword_desc")
        if self.git.is_head_pushed():
            desc += "\n\n" + t("amend_pushed_desc")
        show_choice_dialog(self, t("reword_title"), desc,
                           [("cancel", t("cancel"), "subtle"), ("reword", t("reword_btn"), "primary")],
                           apply, entry_text=subject, entry_validator=lambda v: bool(v.strip()))
