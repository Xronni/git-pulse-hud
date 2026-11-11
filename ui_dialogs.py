#!/usr/bin/env python3
"""
GitPulse HUD — modal dialogs shared across views.

Built on Adw.AlertDialog: with an Adw.ApplicationWindow parent they are drawn
inside the main window (centered, dimming it) instead of as separate windows.
"""

import os

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Pango

from i18n import t

_APPEARANCE = {
    "primary": Adw.ResponseAppearance.SUGGESTED,
    "destructive": Adw.ResponseAppearance.DESTRUCTIVE,
}

AUTH_ERROR_HINTS = ("auth", "token", "permission", "denied", "credential", "403", "401")


def show_choice_dialog(parent, title, message, choices, on_choice=None,
                       entry_text=None, entry_validator=None, extra_child=None):
    """
    Shows a modal dialog with buttons.

    choices:   [(choice_id, label, style)] where style is 'subtle' | 'primary' | 'destructive'.
               The first choice is Cancel (also triggered by Escape / closing).
    on_choice: callback(choice_id, entry_value_or_None); never called for Cancel.
    entry_text: when not None, shows a text entry prefilled with this value.
    entry_validator: callable(text) -> bool; non-cancel buttons are disabled while it returns False.
    extra_child: optional widget shown under the message (ignored when entry_text is set).
    """
    dlg = Adw.AlertDialog(heading=title, body=message or "")
    cancel_id = choices[0][0]
    action_ids = [cid for cid, _, _ in choices[1:]]
    has_destructive = any(style == "destructive" for _, _, style in choices)

    for cid, label, style in choices:
        dlg.add_response(cid, label)
        if style in _APPEARANCE:
            dlg.set_response_appearance(cid, _APPEARANCE[style])
    dlg.set_close_response(cancel_id)
    # Never let a stray Enter confirm a destructive action
    dlg.set_default_response(cancel_id if (has_destructive or not action_ids) else action_ids[-1])

    entry = None
    if entry_text is not None:
        entry = Gtk.Entry(text=entry_text)
        dlg.set_extra_child(entry)
    elif extra_child is not None:
        dlg.set_extra_child(extra_child)

    def _valid():
        return entry_validator(entry.get_text().strip()) if (entry and entry_validator) else True

    def _on_response(_dlg, response):
        if response != cancel_id and on_choice:
            on_choice(response, entry.get_text().strip() if entry else None)

    dlg.connect("response", _on_response)

    if entry:
        def _on_changed(_e):
            ok = _valid()
            for cid in action_ids:
                dlg.set_response_enabled(cid, ok)
        entry.connect("changed", _on_changed)

        def _on_activate(_e):
            if action_ids and _valid():
                dlg.force_close()
                if on_choice:
                    on_choice(action_ids[-1], entry.get_text().strip())
        entry.connect("activate", _on_activate)
        _on_changed(entry)

    dlg.present(parent)
    if entry:
        entry.grab_focus()
        entry.select_region(0, -1)
    return dlg


def _scrolled_text(text, max_height=260, monospace=True):
    lbl = Gtk.Label(label=text, xalign=0, yalign=0, wrap=True, selectable=True)
    lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if monospace:
        lbl.add_css_class("monospace")
    lbl.add_css_class("dialog-detail-text")
    scrolled = Gtk.ScrolledWindow(max_content_height=max_height, propagate_natural_height=True)
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_child(lbl)
    return scrolled


def show_error_dialog(parent, title, message, on_open_token_guide=None):
    """Error with selectable details; offers the token guide for auth-looking errors."""
    message = (message or "").strip()
    choices = [("ok", "OK", "primary")]
    if on_open_token_guide and any(w in message.lower() for w in AUTH_ERROR_HINTS):
        choices.append(("token", f"🔑 {t('token_guide_title')}", "subtle"))

    dlg = Adw.AlertDialog(heading=title)
    for cid, label, style in choices:
        dlg.add_response(cid, label)
        if style in _APPEARANCE:
            dlg.set_response_appearance(cid, _APPEARANCE[style])
    dlg.set_close_response("ok")
    dlg.set_default_response("ok")
    if message:
        dlg.set_extra_child(_scrolled_text(message))

    def _on_response(_dlg, response):
        if response == "token" and on_open_token_guide:
            on_open_token_guide()
    dlg.connect("response", _on_response)
    dlg.present(parent)
    return dlg


def show_secret_findings_dialog(parent, findings, on_confirm=None):
    """Lists secrets found in staged files; optionally lets the user commit anyway."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    for finding in findings:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("file-item-row")
        row.append(Gtk.Label(label=finding.get("rule", "Secret"), css_classes=["status-tag", "status-del"]))
        location = f"{os.path.basename(finding.get('file', ''))}:{finding.get('line', 0)}"
        row.append(Gtk.Label(label=location, css_classes=["stat-label"]))
        row.append(Gtk.Label(label=finding.get("preview", ""), xalign=0, hexpand=True,
                             ellipsize=Pango.EllipsizeMode.END))
        box.append(row)
    scrolled = Gtk.ScrolledWindow(max_content_height=260, propagate_natural_height=True)
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_child(box)

    choices = [("cancel", t("cancel"), "subtle")]
    if on_confirm:
        choices.append(("commit", t("commit_anyway"), "destructive"))
    return show_choice_dialog(parent, t("secrets_dialog_title"), t("secrets_dialog_desc"), choices,
                              lambda choice, _v: on_confirm() if choice == "commit" else None,
                              extra_child=scrolled)
