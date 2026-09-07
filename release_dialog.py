#!/usr/bin/env python3
"""
GitPulse HUD — One-Click Release Drafter & Changelog Synthesizer
Automatically generates structured Conventional Commit release notes and creates git tags.
"""

import re
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from i18n import t


class ReleaseDrafterDialog(Gtk.Window):
    def __init__(self, parent, git_engine, sound_engine, on_tag_created=None):
        super().__init__(transient_for=parent, modal=True)
        self.git = git_engine
        self.sound = sound_engine
        self.on_tag_created = on_tag_created

        self.set_title(t("release_drafter_title"))
        self.set_default_size(680, 560)
        self.add_css_class("release-dialog-window")

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_box)

        # Header Bar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(
            title=t("release_drafter_title"),
            subtitle=t("release_drafter_sub")
        )
        header.set_title_widget(title_widget)
        main_box.append(header)

        # Form content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(20)
        content.set_margin_end(20)
        main_box.append(content)

        # Tag & Title row
        inputs_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        tag_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        tag_box.set_size_request(160, -1)
        tag_lbl = Gtk.Label(label=t("tag_name"), css_classes=["stat-label"], xalign=0)
        tag_box.append(tag_lbl)
        self.tag_entry = Gtk.Entry()
        self.tag_entry.add_css_class("token-entry")
        tag_box.append(self.tag_entry)
        inputs_row.append(tag_box)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_hexpand(True)
        title_lbl = Gtk.Label(label=t("release_name"), css_classes=["stat-label"], xalign=0)
        title_box.append(title_lbl)
        self.title_entry = Gtk.Entry()
        self.title_entry.add_css_class("token-entry")
        title_box.append(self.title_entry)
        inputs_row.append(title_box)

        content.append(inputs_row)

        # Changelog Preview Header
        content.append(Gtk.Label(label=t("changelog_preview"), css_classes=["hud-card-header"], xalign=0))

        # Markdown TextView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.add_css_class("changelog-scrolled")

        self.text_view = Gtk.TextView()
        self.text_view.set_monospace(True)
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(10)
        self.text_view.set_bottom_margin(10)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_buffer = self.text_view.get_buffer()
        scrolled.set_child(self.text_view)
        content.append(scrolled)

        # Action Buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_row.append(Gtk.Box(hexpand=True))

        self.btn_copy = Gtk.Button(label=t("copy_markdown"))
        self.btn_copy.add_css_class("subtle-btn")
        self.btn_copy.connect("clicked", self._on_copy_markdown)
        btn_row.append(self.btn_copy)

        self.btn_create_tag = Gtk.Button(label=t("create_tag"))
        self.btn_create_tag.add_css_class("primary-btn")
        self.btn_create_tag.connect("clicked", self._on_create_tag)
        btn_row.append(self.btn_create_tag)

        content.append(btn_row)

        self._populate_draft()

    def _suggest_next_tag(self, latest_tag, has_features=False):
        if not latest_tag:
            return "v1.0.0"
        m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", latest_tag)
        if m:
            major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if has_features:
                minor += 1
                patch = 0
            else:
                patch += 1
            return f"v{major}.{minor}.{patch}"
        return f"{latest_tag}-next"

    def _populate_draft(self):
        data = self.git.get_changelog_data()
        cats = data.get("categories", {})
        latest_tag = data.get("latest_tag")

        has_features = len(cats.get("feat", [])) > 0
        suggested_tag = self._suggest_next_tag(latest_tag, has_features)
        self.tag_entry.set_text(suggested_tag)
        self.title_entry.set_text(f"Release {suggested_tag}")

        # Build clean Markdown changelog
        md_lines = [f"# {suggested_tag}\n"]

        category_labels = [
            ("feat", "🚀 New Features"),
            ("fix", "🐛 Bug Fixes"),
            ("perf", "⚡ Performance Improvements"),
            ("docs", "📝 Documentation"),
            ("refactor", "🔧 Refactoring & Code Style"),
            ("chore", "⚙️ Maintenance & Dependencies"),
            ("other", "📌 Other Changes")
        ]

        total_items = 0
        for cat_key, header in category_labels:
            items = cats.get(cat_key, [])
            if items:
                md_lines.append(f"## {header}")
                for item in items:
                    msg = item["message"]
                    # Strip conventional prefix for cleaner changelog line
                    clean_msg = re.sub(r"^(feat|fix|docs|perf|refactor|chore)(\([^)]+\))?!?:", "", msg).strip()
                    md_lines.append(f"- {clean_msg} (`{item['hash']}`)")
                    total_items += 1
                md_lines.append("")

        if total_items == 0:
            md_lines.append("- Maintenance updates and optimizations.")

        markdown_text = "\n".join(md_lines).strip()
        self.text_buffer.set_text(markdown_text)

    def _on_copy_markdown(self, btn):
        bounds = self.text_buffer.get_bounds()
        text = self.text_buffer.get_text(bounds[0], bounds[1], False)
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)
        self.sound.play("commit")
        btn.set_label(f"✓ {t('markdown_copied')}")

    def _on_create_tag(self, btn):
        tag_name = self.tag_entry.get_text().strip()
        if not tag_name:
            self.sound.play("error")
            return

        bounds = self.text_buffer.get_bounds()
        message = self.text_buffer.get_text(bounds[0], bounds[1], False)

        ok, out = self.git.create_tag(tag_name, message)
        if ok:
            self.sound.play("commit")
            if self.on_tag_created:
                self.on_tag_created(tag_name)
            self.close()
        else:
            self.sound.play("error")
