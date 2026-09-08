#!/usr/bin/env python3
"""
GitPulse HUD — Publish Repository to GitHub
Interactive modal dialog enabling developers to publish a local project or newly
initialized repository directly to GitHub via GitHub REST API in a single click.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, Gio, GLib
import os
import re
import threading
import subprocess
from i18n import t


class PublishToGitHubDialog(Gtk.Window):
    def __init__(self, parent, git_engine, telemetry_client, sound_engine, config, on_published=None):
        super().__init__(transient_for=parent, modal=True)
        self.git = git_engine
        self.telemetry = telemetry_client
        self.sound = sound_engine
        self.config = config
        self.on_published = on_published
        self.user_profile = None

        self.set_title(t("publish_dialog_title"))
        self.set_default_size(560, 600)
        self.add_css_class("token-modal-window")

        # Libadwaita Titlebar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(
            title=t("publish_dialog_title"),
            subtitle=t("publish_dialog_sub")
        )
        header.set_title_widget(title_widget)
        self.set_titlebar(header)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_child(scrolled)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.set_margin_top(16)
        self.main_box.set_margin_bottom(20)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)
        scrolled.set_child(self.main_box)

        # Build initial UI
        self._build_form_ui()
        self._load_user_profile_async()

    def _build_form_ui(self):
        # 1. GitHub Account status card
        self.account_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.account_card.add_css_class("hud-card")

        acc_icon = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
        acc_icon.set_pixel_size(32)
        self.account_card.append(acc_icon)

        acc_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        acc_vbox.set_hexpand(True)

        self.lbl_acc_title = Gtk.Label(label=t("publish_account"), css_classes=["hud-card-header"], xalign=0)
        acc_vbox.append(self.lbl_acc_title)

        self.lbl_acc_desc = Gtk.Label(label="...", css_classes=["view-subtitle"], xalign=0)
        acc_vbox.append(self.lbl_acc_desc)
        self.account_card.append(acc_vbox)

        self.btn_cfg_token = Gtk.Button(label="🔑 " + t("token_settings"))
        self.btn_cfg_token.add_css_class("subtle-btn")
        self.btn_cfg_token.connect("clicked", self._on_open_token_dialog)
        self.account_card.append(self.btn_cfg_token)

        self.main_box.append(self.account_card)

        # 2. Repo Settings Card
        form_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        form_card.add_css_class("hud-card")

        # Repository name entry
        lbl_name = Gtk.Label(label=t("publish_repo_name"), css_classes=["hud-card-header"], xalign=0)
        form_card.append(lbl_name)

        self.entry_name = Gtk.Entry()
        default_name = self._sanitize_repo_name(self.git.get_repo_name())
        self.entry_name.set_text(default_name)
        self.entry_name.set_placeholder_text("my-project")
        self.entry_name.add_css_class("token-entry")
        form_card.append(self.entry_name)

        # Description entry
        lbl_desc = Gtk.Label(label=t("publish_repo_desc"), css_classes=["hud-card-header"], xalign=0)
        form_card.append(lbl_desc)

        self.entry_desc = Gtk.Entry()
        self.entry_desc.set_placeholder_text("Description of this repository...")
        form_card.append(self.entry_desc)

        # Visibility options
        lbl_vis = Gtk.Label(label=t("publish_visibility"), css_classes=["hud-card-header"], xalign=0)
        form_card.append(lbl_vis)

        vis_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.radio_public = Gtk.CheckButton(label=t("publish_public"))
        self.radio_public.set_active(True)
        vis_box.append(self.radio_public)

        self.radio_private = Gtk.CheckButton(label=t("publish_private"))
        self.radio_private.set_group(self.radio_public)
        vis_box.append(self.radio_private)
        form_card.append(vis_box)

        # Initial commit note if needed
        if not self.git.has_commits():
            note_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            note_box.add_css_class("command-snippet-box")
            lbl_note = Gtk.Label(
                label="💡 " + t("publish_initial_commit_note"),
                wrap=True,
                xalign=0,
                css_classes=["view-subtitle"]
            )
            note_box.append(lbl_note)
            form_card.append(note_box)

        self.main_box.append(form_card)

        # Error label
        self.lbl_error = Gtk.Label(wrap=True, xalign=0, css_classes=["status-del"])
        self.lbl_error.set_visible(False)
        self.main_box.append(self.lbl_error)

        # Actions Card
        act_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        act_box.append(Gtk.Box(hexpand=True))

        btn_cancel = Gtk.Button(label=t("cancel"), css_classes=["subtle-btn"])
        btn_cancel.connect("clicked", lambda b: self.close())
        act_box.append(btn_cancel)

        self.btn_publish = Gtk.Button(label="☁️ " + t("publish_action"))
        self.btn_publish.add_css_class("primary-btn")
        self.btn_publish.connect("clicked", self._on_publish_clicked)
        act_box.append(self.btn_publish)

        self.main_box.append(act_box)

    def _sanitize_repo_name(self, name):
        if not name or name == "No Repository":
            name = "my-project"
        clean = re.sub(r"[^\w.-]", "-", name).strip("-")
        return clean or "my-project"

    def _load_user_profile_async(self):
        def _fetch():
            tok = self.telemetry.token
            if not tok:
                GLib.idle_add(self._update_profile_ui, None, t("publish_account_not_connected"))
                return
            data, err = self.telemetry.get_user_profile()
            GLib.idle_add(self._update_profile_ui, data, err)

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_profile_ui(self, data, err):
        if data and "login" in data:
            self.user_profile = data
            login = data.get("login", "")
            name = data.get("name") or login
            self.lbl_acc_desc.set_text(f"{t('publish_account_connected')}: @{login} ({name})")
            self.btn_cfg_token.set_label("✓ " + t("token_active_badge"))
            self.btn_cfg_token.remove_css_class("suggested-action")
            self.btn_publish.set_sensitive(True)
        else:
            self.lbl_acc_desc.set_text(f"⚠️ {t('publish_account_not_connected')}")
            self.btn_cfg_token.set_label("🔑 " + t("token_settings"))
            self.btn_cfg_token.add_css_class("suggested-action")
            self.btn_publish.set_sensitive(False)

    def _on_open_token_dialog(self, btn):
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
        self._load_user_profile_async()

    def _on_publish_clicked(self, btn):
        repo_name = self.entry_name.get_text().strip()
        if not repo_name:
            self._show_error("Please enter a valid repository name.")
            return

        description = self.entry_desc.get_text().strip()
        is_private = self.radio_private.get_active()

        self.btn_publish.set_sensitive(False)
        self.btn_publish.set_label(t("publishing"))
        self.lbl_error.set_visible(False)
        self.sound.play("click")

        threading.Thread(
            target=self._publish_worker,
            args=(repo_name, description, is_private),
            daemon=True
        ).start()

    def _publish_worker(self, name, description, is_private):
        # 1. Handle uncommitted files / initial commit if repo is empty
        if not self.git.has_commits():
            self.git.stage_all()
            ok_commit, msg_commit = self.git.commit("feat: initial commit")
            if not ok_commit and "nothing to commit" not in msg_commit.lower():
                # Try creating a minimal README if directory was empty
                readme_path = os.path.join(self.git.root_path, "README.md")
                if not os.path.exists(readme_path):
                    with open(readme_path, "w", encoding="utf-8") as f:
                        f.write(f"# {name}\n\n{description}\n")
                    self.git.stage_all()
                    self.git.commit("feat: initial commit")

        # 2. Call GitHub API to create repository
        repo_data, err = self.telemetry.create_remote_repo(name, description, is_private)
        if err or not repo_data:
            GLib.idle_add(self._on_publish_failed, err or "Failed to create repository")
            return

        html_url = repo_data.get("html_url", f"https://github.com/{name}")
        clone_url = repo_data.get("clone_url")
        owner_login = repo_data.get("owner", {}).get("login", "")

        # 3. Add or update remote origin
        if self.git.has_remote("origin"):
            self.git.set_remote_url("origin", clone_url)
        else:
            self.git.add_remote("origin", clone_url)

        # 4. Push initial branch using authenticated URL
        tok = self.telemetry.token
        push_url = f"https://{tok}@github.com/{owner_login}/{name}.git" if tok else clone_url
        cur_branch = self.git.get_current_branch()
        if not cur_branch or "HEAD" in cur_branch or cur_branch == "no commits":
            cur_branch = "main"

        try:
            res = subprocess.run(
                ["git", "-c", "core.quotepath=false", "push", "-u", push_url, f"HEAD:{cur_branch}"],
                cwd=self.git.root_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            # Revert remote URL back to clean HTTPS without embedded token
            self.git.set_remote_url("origin", clone_url)

            if res.returncode != 0:
                GLib.idle_add(self._on_publish_failed, res.stderr.strip() or res.stdout.strip())
                return
        except Exception as e:
            self.git.set_remote_url("origin", clone_url)
            GLib.idle_add(self._on_publish_failed, str(e))
            return

        # 5. Success
        GLib.idle_add(self._on_publish_success, repo_data)

    def _on_publish_failed(self, error_msg):
        self.sound.play("error")
        self.btn_publish.set_sensitive(True)
        self.btn_publish.set_label("☁️ " + t("publish_action"))
        self._show_error(f"Error publishing: {error_msg}")

    def _show_error(self, msg):
        self.lbl_error.set_text(msg)
        self.lbl_error.set_visible(True)

    def _on_publish_success(self, repo_data):
        self.sound.play("commit")
        while child := self.main_box.get_first_child():
            self.main_box.remove(child)

        success_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        success_card.add_css_class("hud-card")
        success_card.set_margin_top(30)
        success_card.set_margin_bottom(30)
        success_card.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        icon.set_pixel_size(54)
        success_card.append(icon)

        lbl_title = Gtk.Label(label=t("publish_success_title"), css_classes=["view-title"])
        success_card.append(lbl_title)

        html_url = repo_data.get("html_url", "")
        lbl_desc = Gtk.Label(
            label=f"{t('publish_success_desc')}\n\n{html_url}",
            css_classes=["view-subtitle"],
            wrap=True,
            xalign=0.5
        )
        lbl_desc.set_selectable(True)
        success_card.append(lbl_desc)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_row.set_halign(Gtk.Align.CENTER)

        btn_open = Gtk.Button(label="🌐 " + t("open_on_github"), css_classes=["primary-btn"])
        def _open_url(b):
            try:
                Gio.AppInfo.launch_default_for_uri(html_url, None)
            except Exception:
                subprocess.Popen(["xdg-open", html_url])
        btn_open.connect("clicked", _open_url)
        btn_row.append(btn_open)

        btn_done = Gtk.Button(label=t("close"), css_classes=["subtle-btn"])
        btn_done.connect("clicked", lambda b: self.close())
        btn_row.append(btn_done)

        success_card.append(btn_row)
        self.main_box.append(success_card)

        if self.on_published:
            self.on_published(repo_data)
