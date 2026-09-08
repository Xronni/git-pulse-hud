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
from repo_templates import (
    GITIGNORE_TEMPLATES,
    LICENSE_TEMPLATES,
    get_readme_template,
    get_gitignore_template,
    get_license_template,
    detect_project_stack
)


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
        self.set_default_size(580, 680)
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

        # 3. Repository Initialization Card (README, .gitignore, License)
        init_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        init_card.add_css_class("hud-card")

        init_hdr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        lbl_init_title = Gtk.Label(label=t("publish_init_section"), css_classes=["hud-card-header"], xalign=0)
        lbl_init_sub = Gtk.Label(label=t("publish_init_sub"), css_classes=["view-subtitle"], xalign=0, wrap=True)
        init_hdr_box.append(lbl_init_title)
        init_hdr_box.append(lbl_init_sub)
        init_card.append(init_hdr_box)

        # Check existing files in repository root
        root_path = self.git.root_path or ""
        readme_path = os.path.join(root_path, "README.md") if root_path else ""
        has_readme = bool(root_path and (os.path.exists(readme_path) or os.path.exists(os.path.join(root_path, "README")) or os.path.exists(os.path.join(root_path, "readme.md"))))

        gitignore_path = os.path.join(root_path, ".gitignore") if root_path else ""
        has_gitignore = bool(root_path and os.path.exists(gitignore_path))

        license_path = os.path.join(root_path, "LICENSE") if root_path else ""
        has_license = bool(root_path and (os.path.exists(license_path) or os.path.exists(os.path.join(root_path, "LICENSE.txt")) or os.path.exists(os.path.join(root_path, "LICENSE.md"))))

        detected_stack = detect_project_stack(root_path)

        # --- A. README Option ---
        readme_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        readme_row.add_css_class("init-option-row")
        readme_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        readme_vbox.set_hexpand(True)

        lbl_r_text = f"{t('publish_add_readme')} {t('publish_file_exists')}" if has_readme else t("publish_add_readme")
        self.check_readme = Gtk.CheckButton(label=lbl_r_text)
        self.check_readme.set_active(True)
        if has_readme:
            self.check_readme.set_sensitive(False)
        readme_vbox.append(self.check_readme)

        lbl_r_desc = Gtk.Label(label=t("publish_add_readme_desc"), css_classes=["view-subtitle"], xalign=0, wrap=True)
        readme_vbox.append(lbl_r_desc)
        readme_row.append(readme_vbox)
        init_card.append(readme_row)

        # --- B. .gitignore Option ---
        gi_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        gi_row.add_css_class("init-option-row")
        gi_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        gi_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        gi_vbox.set_hexpand(True)

        lbl_gi_text = f"{t('publish_add_gitignore')} {t('publish_file_exists')}" if has_gitignore else t("publish_add_gitignore")
        self.check_gitignore = Gtk.CheckButton(label=lbl_gi_text)
        self.check_gitignore.set_active(has_gitignore or (detected_stack is not None))
        if has_gitignore:
            self.check_gitignore.set_sensitive(False)
        gi_vbox.append(self.check_gitignore)

        lbl_gi_desc = Gtk.Label(label=t("publish_add_gitignore_desc"), css_classes=["view-subtitle"], xalign=0, wrap=True)
        gi_vbox.append(lbl_gi_desc)
        gi_top.append(gi_vbox)
        gi_row.append(gi_top)

        # Dropdown for .gitignore templates
        gi_dropdown_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        gi_dropdown_box.set_margin_start(24)
        lbl_gi_tpl = Gtk.Label(label=t("publish_gitignore_template"), css_classes=["hud-card-header"], xalign=0)
        gi_dropdown_box.append(lbl_gi_tpl)

        self.gitignore_templates_list = [t("publish_template_none")] + list(GITIGNORE_TEMPLATES.keys())
        self.dropdown_gitignore = Gtk.DropDown.new_from_strings(self.gitignore_templates_list)
        self.dropdown_gitignore.add_css_class("dropdown-picker")
        self.dropdown_gitignore.set_hexpand(True)

        # Pre-select detected stack if available
        if detected_stack and detected_stack in self.gitignore_templates_list:
            self.dropdown_gitignore.set_selected(self.gitignore_templates_list.index(detected_stack))
        else:
            self.dropdown_gitignore.set_selected(0)

        self.dropdown_gitignore.set_sensitive(not has_gitignore and self.check_gitignore.get_active())
        self.check_gitignore.connect("toggled", lambda cb: self.dropdown_gitignore.set_sensitive(cb.get_active()))
        gi_dropdown_box.append(self.dropdown_gitignore)
        gi_row.append(gi_dropdown_box)
        init_card.append(gi_row)

        # --- C. License Option ---
        lic_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        lic_row.add_css_class("init-option-row")
        lic_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lic_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        lic_vbox.set_hexpand(True)

        lbl_lic_text = f"{t('publish_choose_license')} {t('publish_file_exists')}" if has_license else t("publish_choose_license")
        self.check_license = Gtk.CheckButton(label=lbl_lic_text)
        self.check_license.set_active(has_license)
        if has_license:
            self.check_license.set_sensitive(False)
        lic_vbox.append(self.check_license)

        lbl_lic_desc = Gtk.Label(label=t("publish_choose_license_desc"), css_classes=["view-subtitle"], xalign=0, wrap=True)
        lic_vbox.append(lbl_lic_desc)
        lic_top.append(lic_vbox)
        lic_row.append(lic_top)

        # Dropdown for licenses
        lic_dropdown_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lic_dropdown_box.set_margin_start(24)
        lbl_lic_tpl = Gtk.Label(label=t("publish_license"), css_classes=["hud-card-header"], xalign=0)
        lic_dropdown_box.append(lbl_lic_tpl)

        self.license_templates_list = [t("publish_template_none")] + list(LICENSE_TEMPLATES.keys())
        self.dropdown_license = Gtk.DropDown.new_from_strings(self.license_templates_list)
        self.dropdown_license.add_css_class("dropdown-picker")
        self.dropdown_license.set_hexpand(True)

        # Default to MIT License if not already present
        if not has_license and "MIT License" in self.license_templates_list:
            self.dropdown_license.set_selected(self.license_templates_list.index("MIT License"))
        else:
            self.dropdown_license.set_selected(0)

        self.dropdown_license.set_sensitive(not has_license and self.check_license.get_active())
        self.check_license.connect("toggled", lambda cb: self.dropdown_license.set_sensitive(cb.get_active()))
        lic_dropdown_box.append(self.dropdown_license)
        lic_row.append(lic_dropdown_box)
        init_card.append(lic_row)

        self.main_box.append(init_card)

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

        create_readme = self.check_readme.get_active() and self.check_readme.get_sensitive()

        create_gitignore = self.check_gitignore.get_active() and self.check_gitignore.get_sensitive()
        gi_idx = self.dropdown_gitignore.get_selected()
        gitignore_key = self.gitignore_templates_list[gi_idx] if (create_gitignore and gi_idx > 0) else None

        create_license = self.check_license.get_active() and self.check_license.get_sensitive()
        lic_idx = self.dropdown_license.get_selected()
        license_key = self.license_templates_list[lic_idx] if (create_license and lic_idx > 0) else None

        self.btn_publish.set_sensitive(False)
        self.btn_publish.set_label(t("publishing"))
        self.lbl_error.set_visible(False)
        self.sound.play("click")

        threading.Thread(
            target=self._publish_worker,
            args=(repo_name, description, is_private, create_readme, create_gitignore, gitignore_key, create_license, license_key),
            daemon=True
        ).start()

    def _publish_worker(self, name, description, is_private, create_readme, create_gitignore, gitignore_key, create_license, license_key):
        # 0. Ensure Git author identity so commits never fail on a clean OS
        author_name = "Developer"
        author_email = "developer@users.noreply.github.com"
        login = "developer"
        if self.user_profile and isinstance(self.user_profile, dict):
            login = self.user_profile.get("login") or "developer"
            author_name = self.user_profile.get("name") or login
            author_email = self.user_profile.get("email") or f"{login}@users.noreply.github.com"
        self.git.ensure_author_identity(name=author_name, email=author_email)

        # 1. Generate selected initialization files if requested
        root_path = self.git.root_path
        files_created = []
        if root_path and os.path.isdir(root_path):
            if create_readme:
                readme_path = os.path.join(root_path, "README.md")
                if not os.path.exists(readme_path):
                    try:
                        content = get_readme_template(
                            repo_name=name,
                            description=description,
                            author=login,
                            license_name=license_key
                        )
                        with open(readme_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        files_created.append("README.md")
                    except Exception as e:
                        print(f"Error creating README.md: {e}")

            if create_gitignore and gitignore_key:
                gi_path = os.path.join(root_path, ".gitignore")
                if not os.path.exists(gi_path):
                    try:
                        content = get_gitignore_template(gitignore_key)
                        if content:
                            with open(gi_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            files_created.append(".gitignore")
                    except Exception as e:
                        print(f"Error creating .gitignore: {e}")

            if create_license and license_key:
                lic_path = os.path.join(root_path, "LICENSE")
                if not os.path.exists(lic_path):
                    try:
                        content = get_license_template(license_key, author=author_name)
                        if content:
                            with open(lic_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            files_created.append("LICENSE")
                    except Exception as e:
                        print(f"Error creating LICENSE: {e}")

        # 2. Handle commit creation:
        # Case A: Repository has no commits yet -> stage all and create initial commit
        if not self.git.has_commits():
            # If folder is empty, create fallback README.md
            status = self.git.get_status_files()
            has_any_files = bool(status.get("staged") or status.get("unstaged") or status.get("untracked"))
            readme_path = os.path.join(self.git.root_path, "README.md")
            if not has_any_files and not os.path.exists(readme_path):
                try:
                    with open(readme_path, "w", encoding="utf-8") as f:
                        f.write(f"# {name}\n\n{description}\n" if description else f"# {name}\n")
                except Exception:
                    pass

            self.git.stage_all()
            ok_commit, msg_commit = self.git.commit("feat: initial commit")
            if not self.git.has_commits():
                # Allow empty commit as last resort
                subprocess.run(
                    ["git", "commit", "--allow-empty", "-m", "feat: initial commit"],
                    cwd=self.git.root_path,
                    capture_output=True,
                    text=True,
                    check=False
                )

            # Ensure we actually have commits now
            if not self.git.has_commits():
                GLib.idle_add(self._on_publish_failed, f"Could not create initial commit: {msg_commit}")
                return
        else:
            # Case B: Repository already had commits, but we generated new initialization files
            if files_created:
                self.git.stage_all()
                self.git.commit(f"chore: add {', '.join(files_created)}")

        # Ensure branch is named 'main'
        cur_branch = self.git.get_current_branch()
        if not cur_branch or "HEAD" in cur_branch or cur_branch == "no commits":
            subprocess.run(["git", "branch", "-M", "main"], cwd=self.git.root_path, check=False)
            cur_branch = "main"

        # 3. Call GitHub API to create repository
        repo_data, err = self.telemetry.create_remote_repo(name, description, is_private)
        if err or not repo_data:
            GLib.idle_add(self._on_publish_failed, err or "Failed to create repository")
            return

        html_url = repo_data.get("html_url", f"https://github.com/{name}")
        clone_url = repo_data.get("clone_url")
        owner_login = repo_data.get("owner", {}).get("login", "")

        # 4. Add or update remote origin
        if self.git.has_remote("origin"):
            self.git.set_remote_url("origin", clone_url)
        else:
            self.git.add_remote("origin", clone_url)

        # 5. Push initial branch using authenticated URL
        tok = self.telemetry.token
        ok_push, msg_push = self.git.push_initial(remote="origin", branch=cur_branch, token=tok)
        if not ok_push:
            GLib.idle_add(self._on_publish_failed, msg_push)
            return

        # 6. Success
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
