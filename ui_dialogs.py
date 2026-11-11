#!/usr/bin/env python3
"""
GitPulse HUD — small modal dialogs shared across views (confirm / choice / text prompt).
Styled like the other GitPulse modals (token-modal-window).
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk

_STYLE_CLASSES = {
    "subtle": ["subtle-btn"],
    "primary": ["primary-btn"],
    "destructive": ["primary-btn", "danger-btn"],
}


def show_choice_dialog(parent, title, message, choices, on_choice=None,
                       entry_text=None, entry_validator=None):
    """
    Shows a modal dialog with buttons.

    choices:   [(choice_id, label, style)] where style is 'subtle' | 'primary' | 'destructive'.
               The first choice is treated as Cancel (also triggered by Escape).
    on_choice: callback(choice_id, entry_value_or_None); not called on Escape/close.
    entry_text: when not None, shows a text entry prefilled with this value.
    entry_validator: callable(text) -> bool; non-cancel buttons are disabled while it returns False.
    """
    dlg = Gtk.Window(transient_for=parent, modal=True)
    dlg.set_title(title)
    dlg.set_default_size(460, -1)
    dlg.set_resizable(False)
    dlg.add_css_class("token-modal-window")

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_margin_top(20)
    box.set_margin_bottom(20)
    box.set_margin_start(20)
    box.set_margin_end(20)
    dlg.set_child(box)

    box.append(Gtk.Label(label=title, css_classes=["view-title"], xalign=0, wrap=True))
    if message:
        box.append(Gtk.Label(label=message, css_classes=["view-subtitle"], xalign=0, wrap=True, max_width_chars=60))

    entry = None
    if entry_text is not None:
        entry = Gtk.Entry(text=entry_text)
        entry.add_css_class("token-entry")
        box.append(entry)

    btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    btn_row.set_margin_top(4)
    btn_row.append(Gtk.Box(hexpand=True))
    box.append(btn_row)

    action_buttons = []
    cancel_button = None
    has_destructive = any(style == "destructive" for _, _, style in choices)

    def _finish(choice_id):
        value = entry.get_text().strip() if entry else None
        dlg.close()
        if on_choice:
            on_choice(choice_id, value)

    for idx, (choice_id, label, style) in enumerate(choices):
        btn = Gtk.Button(label=label, css_classes=list(_STYLE_CLASSES.get(style, ["subtle-btn"])))
        if idx == 0:
            btn.connect("clicked", lambda b: dlg.close())
            cancel_button = btn
        else:
            btn.connect("clicked", lambda b, cid=choice_id: _finish(cid))
            action_buttons.append((choice_id, btn))
        btn_row.append(btn)

    def _validate(*_):
        valid = entry_validator(entry.get_text().strip()) if (entry and entry_validator) else True
        for _, b in action_buttons:
            b.set_sensitive(valid)
        return valid

    if entry:
        entry.connect("changed", _validate)

        def _on_activate(_e):
            if action_buttons and _validate():
                _finish(action_buttons[-1][0])
        entry.connect("activate", _on_activate)
        _validate()

    key_ctl = Gtk.EventControllerKey()

    def _on_key(_ctl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            dlg.close()
            return True
        return False
    key_ctl.connect("key-pressed", _on_key)
    dlg.add_controller(key_ctl)

    dlg.present()
    if entry:
        entry.grab_focus()
        entry.select_region(0, -1)
    elif has_destructive and cancel_button:
        # Never let a stray Enter confirm a destructive action
        cancel_button.grab_focus()
    elif action_buttons:
        action_buttons[-1][1].grab_focus()
    return dlg
