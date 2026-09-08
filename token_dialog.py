#!/usr/bin/env python3
"""
GitPulse HUD — GitHub Token & Credentials Setup Guide
Interactive modal dialog guiding users on creating, configuring, and storing
Personal Access Tokens for both GitPulse telemetry and terminal Git push.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, Gio, Pango
import subprocess
from i18n import t


class GitTokenGuideDialog(Gtk.Window):
    def __init__(self, parent, config, telemetry_client, sound_engine, on_saved=None):
        super().__init__(transient_for=parent, modal=True)
        self.config = config
        self.telemetry = telemetry_client
        self.sound = sound_engine
        self.on_saved = on_saved

        self.set_title(t("token_guide_title"))
        self.set_default_size(620, 680)
        self.add_css_class("token-modal-window")

        # Header bar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(
            title=t("token_guide_title"),
            subtitle=t("token_guide_sub")
        )
        header.set_title_widget(title_widget)
        self.set_titlebar(header)

        # Scrolled container
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_child(scrolled)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        scrolled.set_child(main_box)

        # --- CARD 1: 1-Click Browser Generator Button ---
        open_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        open_card.add_css_class("hud-card")

        btn_open_github = Gtk.Button(label=t("open_github_token_page"))
        btn_open_github.add_css_class("primary-btn")
        btn_open_github.connect("clicked", self._on_open_browser_clicked)
        open_card.append(btn_open_github)

        lbl_open_desc = Gtk.Label(
            label=t("open_github_token_desc"),
            css_classes=["view-subtitle"],
            wrap=True,
            xalign=0
        )
        open_card.append(lbl_open_desc)
        main_box.append(open_card)

        # --- CARD 2: Step-by-Step Instructions ---
        steps_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        steps_card.add_css_class("hud-card")

        lbl_steps_title = Gtk.Label(
            label=t("token_steps_title"),
            css_classes=["hud-card-header"],
            xalign=0
        )
        steps_card.append(lbl_steps_title)

        for step_key in ["token_step_1", "token_step_2", "token_step_3"]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl_step = Gtk.Label(
                label=t(step_key),
                wrap=True,
                xalign=0,
                hexpand=True,
                css_classes=["token-step-text"]
            )
            row.append(lbl_step)
            steps_card.append(row)

        main_box.append(steps_card)

        # --- CARD 3: Token Input & Status ---
        input_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        input_card.add_css_class("hud-card")

        header_input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_in_hdr = Gtk.Label(
            label=t("token_settings"),
            css_classes=["hud-card-header"],
            xalign=0,
            hexpand=True
        )
        header_input_row.append(lbl_in_hdr)

        # Status badge
        self.status_badge = Gtk.Label(css_classes=["status-tag"])
        header_input_row.append(self.status_badge)
        input_card.append(header_input_row)

        # Entry
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.entry.set_visibility(False)
        self.entry.add_css_class("token-entry")
        current_token = self.config.get("github_token", "")
        self.entry.set_text(current_token)
        input_card.append(self.entry)

        # Eye toggle to show/hide token
        self.btn_show_token = Gtk.CheckButton(label="Показать токен / Reveal token")
        self.btn_show_token.connect("toggled", lambda cb: self.entry.set_visibility(cb.get_active()))
        input_card.append(self.btn_show_token)

        # Actions in input card
        act_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        self.btn_clear = Gtk.Button(label=t("clear_token"), css_classes=["subtle-btn"])
        self.btn_clear.connect("clicked", self._on_clear_token)
        act_row.append(self.btn_clear)

        act_row.append(Gtk.Box(hexpand=True))

        btn_cancel = Gtk.Button(label=t("cancel"), css_classes=["subtle-btn"])
        btn_cancel.connect("clicked", lambda b: self.close())
        act_row.append(btn_cancel)

        self.btn_save = Gtk.Button(label=t("save"), css_classes=["primary-btn"])
        self.btn_save.connect("clicked", self._on_save_token)
        act_row.append(self.btn_save)

        input_card.append(act_row)
        main_box.append(input_card)

        # --- CARD 4: Git Push Terminal Setup ---
        push_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        push_card.add_css_class("hud-card")

        lbl_push_title = Gtk.Label(
            label=t("token_git_push_title"),
            css_classes=["hud-card-header"],
            xalign=0
        )
        push_card.append(lbl_push_title)

        lbl_push_desc = Gtk.Label(
            label=t("token_git_push_desc"),
            css_classes=["view-subtitle"],
            wrap=True,
            xalign=0
        )
        push_card.append(lbl_push_desc)

        # Command row with copy button
        cmd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cmd_box.add_css_class("command-snippet-box")

        cmd_text = t("token_git_push_cmd")
        lbl_cmd = Gtk.Label(
            label=cmd_text,
            css_classes=["command-code-text"],
            xalign=0,
            hexpand=True
        )
        lbl_cmd.set_selectable(True)
        cmd_box.append(lbl_cmd)

        self.btn_copy_cmd = Gtk.Button(label=t("copy_command"))
        self.btn_copy_cmd.add_css_class("subtle-btn")
        self.btn_copy_cmd.connect("clicked", lambda b, c=cmd_text: self._on_copy_command(c))
        cmd_box.append(self.btn_copy_cmd)
        push_card.append(cmd_box)

        lbl_push_note = Gtk.Label(
            label=t("token_git_push_note"),
            css_classes=["view-subtitle"],
            wrap=True,
            xalign=0
        )
        push_card.append(lbl_push_note)

        main_box.append(push_card)

        self._update_status_display()

    def _update_status_display(self):
        tok = self.config.get("github_token", "").strip()
        if tok:
            masked = tok[:4] + "••••••••" + tok[-4:] if len(tok) >= 8 else "••••"
            self.status_badge.set_label(f"✓ {t('token_active_badge')} ({masked})")
            self.status_badge.remove_css_class("status-del")
            self.status_badge.add_css_class("status-add")
            self.btn_clear.set_sensitive(True)
        else:
            self.status_badge.set_label(t("token_not_set"))
            self.status_badge.remove_css_class("status-add")
            self.status_badge.add_css_class("status-del")
            self.btn_clear.set_sensitive(False)

    def _on_open_browser_clicked(self, btn):
        self.sound.play("click")
        # Generates a token URL preselecting repo and read:packages scopes
        url = "https://github.com/settings/tokens/new?description=GitPulse+HUD&scopes=repo,read:packages"
        try:
            Gio.AppInfo.launch_default_for_uri(url, None)
        except Exception:
            subprocess.Popen(["xdg-open", url])

    def _on_copy_command(self, cmd_text):
        clipboard = self.get_display().get_clipboard()
        clipboard.set(cmd_text)
        self.sound.play("commit")
        self.btn_copy_cmd.set_label(t("command_copied"))

    def _on_clear_token(self, btn):
        self.sound.play("pop")
        self.entry.set_text("")
        self.config["github_token"] = ""
        self.telemetry.set_token("")
        self._update_status_display()
        if self.on_saved:
            self.on_saved()

    def _on_save_token(self, btn):
        tok = self.entry.get_text().strip()
        self.config["github_token"] = tok
        self.telemetry.set_token(tok)
        self.sound.play("commit")
        self._update_status_display()
        if self.on_saved:
            self.on_saved()
        self.close()
