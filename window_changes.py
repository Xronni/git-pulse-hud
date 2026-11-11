#!/usr/bin/env python3
"""
GitPulse HUD — Files & Changes view: file lists, staging, discard, commit composer (amend, body), secret scanner.

Mixin for GitPulseWindow (see main.py); relies on attributes created there.
"""

import os
import re

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Pango

from diff_viewer import DiffViewerDialog
import i18n
from i18n import plural_ru, t
from ui_dialogs import show_choice_dialog, show_secret_findings_dialog


class ChangesViewMixin:
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
        self.files_container.set_vexpand(True)
        self.files_container.set_hexpand(True)
        scrolled.set_child(self.files_container)

        # Commit Composer Card
        self.commit_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.commit_card.add_css_class("hud-card")

        self.lbl_composer_hdr = Gtk.Label(label=t("commit_builder"), css_classes=["hud-card-header"], xalign=0)
        self.commit_card.append(self.lbl_composer_hdr)

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

        self.check_amend = Gtk.CheckButton(label=t("amend_last"))
        self.check_amend.set_tooltip_text(t("amend_tooltip"))
        self.check_amend.connect("toggled", self._on_amend_toggled)
        types_row.append(self.check_amend)

        self.commit_card.append(types_row)

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

        self.btn_body_toggle = Gtk.ToggleButton(icon_name="format-justify-left-symbolic", css_classes=["subtle-icon-btn"])
        self.btn_body_toggle.set_tooltip_text(t("commit_body_toggle"))
        self.btn_body_toggle.connect("toggled", lambda b: self._set_body_visible(b.get_active()))
        input_row.append(self.btn_body_toggle)

        self.commit_card.append(input_row)

        # Optional multi-line commit body
        self.body_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        body_scroll = Gtk.ScrolledWindow(min_content_height=64, max_content_height=120, propagate_natural_height=True)
        body_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        body_scroll.add_css_class("commit-body-box")
        self.text_body = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False)
        self.text_body.add_css_class("commit-body-text")
        self.text_body.set_tooltip_text(t("commit_body_placeholder"))
        body_scroll.set_child(self.text_body)
        self.body_revealer.set_child(body_scroll)
        self.commit_card.append(self.body_revealer)

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
        self.btn_commit.set_tooltip_text("Ctrl+Enter")
        self.btn_commit.add_css_class("subtle-btn")
        self.btn_commit.connect("clicked", lambda b: self._on_commit(push=False))
        bottom_row.append(self.btn_commit)

        self.btn_commit_push = Gtk.Button(label=t("btn_commit_push"))
        self.btn_commit_push.set_tooltip_text("Ctrl+Shift+Enter")
        self.btn_commit_push.add_css_class("primary-btn")
        self.btn_commit_push.connect("clicked", lambda b: self._on_commit(push=True))
        bottom_row.append(self.btn_commit_push)

        self.commit_card.append(bottom_row)
        page.append(self.commit_card)

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
        if getattr(self, "check_amend", None) and self.check_amend.get_active() and not self.entry_desc.get_text().strip():
            # Amend without a new description keeps the previous message
            subject, _ = self.git.get_last_commit_message()
            self.preview_lbl.set_text(f"↺ {subject}")
            return
        scope = self.entry_scope.get_text().strip()
        desc = self.entry_desc.get_text().strip() or "..."
        breaking = "!" if self.check_breaking.get_active() else ""
        if scope:
            full = f"{self.selected_type}({scope}){breaking}: {desc}"
        else:
            full = f"{self.selected_type}{breaking}: {desc}"
        self.preview_lbl.set_text(full)

    def _refresh_changes_view(self, snap):
        while child := self.files_container.get_first_child():
            self.files_container.remove(child)

        status = snap["status"]
        staged = status.get("staged", [])
        unstaged = status.get("unstaged", [])
        untracked = status.get("untracked", [])
        conflicted = status.get("conflicted", [])

        has_files = bool(staged or unstaged or untracked or conflicted)

        # Show Publish to GitHub banner if repo has no origin remote AND there are files to commit
        if not snap["has_origin"] and has_files:
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
            btn_publish_card.connect("clicked", lambda b: self._on_publish_dialog())
            publish_card.append(btn_publish_card)

            self.files_container.append(publish_card)

        self._apply_secret_scan(snap["scan_findings"])

        if not has_files:
            self.commit_card.set_visible(False)
            self._render_empty_changes(snap)
            return

        self.commit_card.set_visible(True)
        can_commit = len(staged) > 0 or self.check_amend.get_active()
        has_origin = snap["has_origin"]
        self.btn_commit.set_sensitive(can_commit)
        self.btn_commit_push.set_sensitive(can_commit)
        if has_origin:
            self.btn_commit_push.set_label(f"🚀 {t('btn_commit_push')}")
        else:
            self.btn_commit_push.set_label(f"☁️ {t('btn_commit_publish')}")

        if conflicted:
            hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl = Gtk.Label(label=f"⚠ {t('conflicted_title')} ({len(conflicted)})", css_classes=["hud-card-header", "conflict-header"], xalign=0)
            hdr.append(lbl)
            hdr.append(Gtk.Box(hexpand=True))
            if snap["merging"]:
                btn_abort = Gtk.Button(label=t("merge_abort"), css_classes=["flat", "danger-text"])
                btn_abort.connect("clicked", self._on_abort_merge)
                hdr.append(btn_abort)
            self.files_container.append(hdr)
            for item in conflicted:
                self._add_file_row(item, is_staged=False)

        if staged:
            hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            if conflicted:
                hdr.set_margin_top(12)
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
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_vexpand(True)
        box.set_hexpand(True)

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

        if self.git.repo_path and os.path.isdir(self.git.repo_path) and not self.git.is_valid():
            folder_name = os.path.basename(self.git.repo_path)
            btn_init = Gtk.Button(label=f"✨ {t('btn_init_repo')} ({folder_name})")
            btn_init.add_css_class("suggested-action")
            btn_init.connect("clicked", self._on_init_repo_clicked)
            btn_row.append(btn_init)

        box.append(btn_row)

        self.files_container.append(box)

    def _render_empty_changes(self, snap):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_vexpand(True)
        box.set_hexpand(True)

        has_remote = snap["has_origin"]
        has_commits = snap["has_commits"]
        ahead, behind = snap["ahead"], snap["behind"]

        if not has_remote:
            if has_commits:
                icon = Gtk.Image.new_from_icon_name("send-to-symbolic")
                icon.set_pixel_size(48)
                box.append(icon)

                t_lbl = Gtk.Label(label=t("local_commit_ready"), css_classes=["view-title"])
                box.append(t_lbl)

                s_lbl = Gtk.Label(label=t("local_commit_sub"), css_classes=["view-subtitle"], wrap=True, justify=Gtk.Justification.CENTER)
                s_lbl.set_max_width_chars(50)
                box.append(s_lbl)

                btn_pub = Gtk.Button(label=f"☁️ {t('publish_btn')}")
                btn_pub.add_css_class("primary-btn")
                btn_pub.set_margin_top(12)
                btn_pub.connect("clicked", lambda b: self._on_publish_dialog())
                box.append(btn_pub)
            else:
                icon = Gtk.Image.new_from_icon_name("folder-symbolic")
                icon.set_pixel_size(48)
                box.append(icon)

                t_lbl = Gtk.Label(label=t("clean_tree"), css_classes=["view-title"])
                box.append(t_lbl)

                s_lbl = Gtk.Label(label=t("empty_repo_sub"), css_classes=["view-subtitle"], wrap=True, justify=Gtk.Justification.CENTER)
                s_lbl.set_max_width_chars(50)
                box.append(s_lbl)

                btn_pub = Gtk.Button(label=f"☁️ {t('publish_btn')}")
                btn_pub.add_css_class("primary-btn")
                btn_pub.set_margin_top(12)
                btn_pub.connect("clicked", lambda b: self._on_publish_dialog())
                box.append(btn_pub)
        elif ahead > 0:
            icon = Gtk.Image.new_from_icon_name("software-update-available-symbolic")
            icon.set_pixel_size(48)
            box.append(icon)

            t_lbl = Gtk.Label(label=t("unpushed_title"), css_classes=["view-title"])
            box.append(t_lbl)

            s_lbl = Gtk.Label(label=f"{t('unpushed_sub')} ({ahead})", css_classes=["view-subtitle"], wrap=True, justify=Gtk.Justification.CENTER)
            s_lbl.set_max_width_chars(50)
            box.append(s_lbl)

            btn_sync = Gtk.Button(label=f"🚀 {t('btn_push_ahead')} ({ahead})")
            btn_sync.add_css_class("primary-btn")
            btn_sync.set_margin_top(12)
            btn_sync.connect("clicked", lambda b: self._do_push())
            box.append(btn_sync)
        elif behind > 0:
            icon = Gtk.Image.new_from_icon_name("software-update-available-symbolic")
            icon.set_pixel_size(48)
            box.append(icon)

            t_lbl = Gtk.Label(label=t("behind_title"), css_classes=["view-title"])
            box.append(t_lbl)

            s_lbl = Gtk.Label(label=f"{t('behind_sub')} ({behind})", css_classes=["view-subtitle"], wrap=True, justify=Gtk.Justification.CENTER)
            s_lbl.set_max_width_chars(50)
            box.append(s_lbl)

            btn_pull = Gtk.Button(label=f"↓ {t('btn_pull')} ({behind})")
            btn_pull.add_css_class("primary-btn")
            btn_pull.set_margin_top(12)
            btn_pull.connect("clicked", lambda b: self._do_pull())
            box.append(btn_pull)
        else:
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.set_pixel_size(48)
            box.append(icon)

            t_lbl = Gtk.Label(label=t("clean_tree"), css_classes=["view-title"])
            box.append(t_lbl)

            s_lbl = Gtk.Label(label=t("clean_tree_sub"), css_classes=["view-subtitle"], wrap=True, justify=Gtk.Justification.CENTER)
            s_lbl.set_max_width_chars(50)
            box.append(s_lbl)

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
        if st_char in ["M", "T", "R", "C"]:
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

        if not is_staged and st_char != "U":
            btn_discard = Gtk.Button(icon_name="edit-undo-symbolic", css_classes=["subtle-icon-btn"])
            btn_discard.set_tooltip_text(t("discard_tooltip"))
            btn_discard.connect("clicked", lambda b, fp=filepath, untracked=(st_char == "?"): self._on_discard_file(fp, untracked))
            row.append(btn_discard)

        btn_diff = Gtk.Button()
        btn_diff.set_icon_name("edit-find-symbolic")
        btn_diff.set_tooltip_text(t("view_diff"))
        btn_diff.add_css_class("subtle-icon-btn")
        btn_diff.connect("clicked", lambda b, fp=filepath, st=is_staged: self._show_diff(fp, st))
        row.append(btn_diff)

        self.files_container.append(row)

    def _on_discard_file(self, filepath, untracked):
        desc = (t("discard_desc_untracked") if untracked else t("discard_desc")).format(path=filepath)

        def on_choice(choice, _value):
            if choice != "discard":
                return
            ok, out = self.git.discard_file(filepath, untracked=untracked)
            if ok:
                self.sound.play("pop")
                self._toast(t("discard_done").format(path=os.path.basename(filepath)))
            else:
                self.sound.play("error")
                self._show_error_dialog(t("discard_title"), out)
            self._load_repo_data()

        show_choice_dialog(self, t("discard_title"), desc,
                           [("cancel", t("cancel"), "subtle"), ("discard", t("discard_btn"), "destructive")],
                           on_choice)

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

    def _commit_header(self):
        desc = self.entry_desc.get_text().strip()
        if not desc:
            return ""
        scope = self.entry_scope.get_text().strip()
        breaking = "!" if self.check_breaking.get_active() else ""
        if scope:
            return f"{self.selected_type}({scope}){breaking}: {desc}"
        return f"{self.selected_type}{breaking}: {desc}"

    def _commit_body(self):
        buf = self.text_body.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()

    def _set_body_visible(self, visible):
        self.body_revealer.set_reveal_child(visible)
        if self.btn_body_toggle.get_active() != visible:
            self.btn_body_toggle.set_active(visible)
        if visible:
            self.text_body.grab_focus()

    def _on_amend_toggled(self, check):
        if check.get_active() and not self.entry_desc.get_text().strip():
            self._fill_composer_from_head()
        if not check.get_active():
            self.entry_desc.set_placeholder_text(t("commit_desc_placeholder"))
        self._update_commit_preview()
        if hasattr(self, "files_container") and self.git.is_valid():
            # Re-evaluate whether the commit buttons are enabled
            snap = getattr(self, "snapshot", None)
            staged = bool(snap and snap["status"]["staged"])
            self.btn_commit.set_sensitive(staged or check.get_active())
            self.btn_commit_push.set_sensitive(staged or check.get_active())

    def _fill_composer_from_head(self):
        """Pre-fills type/scope/breaking/description/body from the last commit (for amend)."""
        subject, body = self.git.get_last_commit_message()
        m = re.match(r"^(\w+)(?:\(([^)]*)\))?(!)?:\s*(.*)$", subject)
        if not (m and m.group(1) in self.type_chips):
            # Not a Conventional Commit (e.g. a merge): keep the message unless the user types a new one
            self.entry_desc.set_placeholder_text(t("amend_keep_message"))
            return
        self._select_type(m.group(1))
        self.entry_scope.set_text(m.group(2) or "")
        self.check_breaking.set_active(bool(m.group(3)))
        self.entry_desc.set_text(m.group(4))
        self.text_body.get_buffer().set_text(body)
        if body:
            self._set_body_visible(True)

    def _on_commit(self, push=False):
        amend = self.check_amend.get_active()
        if not self.entry_desc.get_text().strip() and not amend:
            self.sound.play("error")
            return

        def _proceed():
            if self.last_scan_findings:
                self._show_secret_warning_dialog(on_confirm=lambda: self._execute_commit(push=push))
            else:
                self._execute_commit(push=push)

        if amend and self.git.is_head_pushed():
            show_choice_dialog(
                self, t("amend_pushed_title"), t("amend_pushed_desc"),
                [("cancel", t("cancel"), "subtle"), ("amend", t("amend_btn"), "destructive")],
                lambda choice, _v: _proceed() if choice == "amend" else None)
            return
        _proceed()

    def _execute_commit(self, push=False):
        amend = self.check_amend.get_active()
        header = self._commit_header()
        if not header and not amend:
            return

        ok, out = self.git.commit(header, body=self._commit_body(), amend=amend)
        if ok:
            self.sound.play("commit")
            self.entry_desc.set_text("")
            self.text_body.get_buffer().set_text("")
            self._set_body_visible(False)
            self.check_amend.set_active(False)
            self._toast(t("amend_done") if amend else t("commit_done"))
            self._load_repo_data()
            if push:
                if not self.git.has_remote("origin"):
                    self._on_publish_dialog()
                else:
                    self._do_push()
        else:
            self.sound.play("error")
            err_msg = out.strip() if out else "Nothing to commit or commit failed."
            self._show_error_dialog(t("commit_failed"), err_msg)

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

    def _on_abort_merge(self, btn):
        ok, out = self.git.merge_abort()
        if ok:
            self.sound.play("pop")
        else:
            self.sound.play("error")
            self._show_error_dialog(t("merge_failed"), out)
        self._load_repo_data()

    def _apply_secret_scan(self, findings):
        self.last_scan_findings = findings
        if findings:
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
            desc = ("No private keys, tokens, or sensitive credentials detected in staged files."
                    if i18n.get_language() == "en" else
                    "В подготовленных изменениях не обнаружено приватных ключей, токенов или секретов.")
            show_choice_dialog(self, f"🛡️ {t('scanner_clean')}", desc, [("ok", "OK", "primary")])

    def _show_secret_warning_dialog(self, on_confirm=None):
        self.sound.play("error")
        show_secret_findings_dialog(self, self.last_scan_findings, on_confirm)
