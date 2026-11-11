#!/usr/bin/env python3
"""
GitPulse HUD — Branch Manager popover.

Search / switch / create local branches, check out remote branches,
rename, merge into current and delete — plus fetch from the remote.
Slow git operations run on a worker thread; the UI is updated via GLib.idle_add.
"""

import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Pango

from i18n import t
from ui_dialogs import show_choice_dialog


def run_in_background(fn, on_done):
    """Runs fn() on a worker thread and calls on_done(result) on the GTK main loop."""
    def _worker():
        result = fn()
        GLib.idle_add(lambda: (on_done(result), False)[1])
    threading.Thread(target=_worker, daemon=True).start()


class BranchSwitcherPopover(Gtk.Popover):
    def __init__(self, window, git_engine, sound_engine, get_token, on_changed, on_error):
        """
        window:     parent window for modal dialogs
        get_token:  callable returning the GitHub token (or '')
        on_changed: callable invoked after anything that changes branches / HEAD
        on_error:   callable(title, message) for error dialogs
        """
        super().__init__()
        self.window = window
        self.git = git_engine
        self.sound = sound_engine
        self.get_token = get_token
        self.on_changed = on_changed
        self.on_error = on_error
        self._branches = []
        self._actions = []   # ordered callables; Enter in search runs the first one
        self._busy = False

        self.set_has_arrow(True)
        self.set_autohide(True)
        self.add_css_class("branch-popover")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(10)
        root.set_margin_bottom(10)
        root.set_margin_start(10)
        root.set_margin_end(10)
        root.set_size_request(340, -1)
        self.set_child(root)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.lbl_title = Gtk.Label(label=t("branches_title"), css_classes=["hud-card-header"], xalign=0, hexpand=True)
        hdr.append(self.lbl_title)
        self.spinner = Gtk.Spinner()
        hdr.append(self.spinner)
        self.lbl_busy = Gtk.Label(css_classes=["stat-label"])
        hdr.append(self.lbl_busy)
        self.btn_fetch = Gtk.Button(icon_name="emblem-synchronizing-symbolic", css_classes=["subtle-icon-btn"])
        self.btn_fetch.set_tooltip_text(t("branch_fetch"))
        self.btn_fetch.connect("clicked", lambda b: self._on_fetch())
        hdr.append(self.btn_fetch)
        root.append(hdr)

        # Two pages: the branch list, and per-branch actions (no nested popovers)
        self.pages = Gtk.Stack()
        self.pages.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.pages.set_transition_duration(160)
        self.pages.set_vhomogeneous(False)
        self.pages.set_interpolate_size(True)
        root.append(self.pages)

        list_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text(t("branch_search_placeholder"))
        self.search.connect("search-changed", lambda e: self._populate())
        self.search.connect("activate", lambda e: self._activate_first())
        list_page.append(self.search)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_max_content_height(380)
        self.scrolled.set_propagate_natural_height(True)
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.scrolled.set_child(self.list_box)
        list_page.append(self.scrolled)
        self.pages.add_named(list_page, "list")

        self.actions_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.pages.add_named(self.actions_page, "actions")

        key_ctl = Gtk.EventControllerKey()
        key_ctl.connect("key-pressed", self._on_key)
        self.add_controller(key_ctl)

    # --- Public ---

    def open(self):
        """Reloads branches and shows the popover with the search focused."""
        if not self.git.is_valid():
            return
        self.lbl_title.set_text(t("branches_title"))
        self.search.set_placeholder_text(t("branch_search_placeholder"))
        self.btn_fetch.set_tooltip_text(t("branch_fetch"))
        self.search.set_text("")
        self.pages.set_visible_child_name("list")
        self._reload()
        self.popup()
        self.search.grab_focus()

    # --- Data ---

    def _reload(self):
        self._branches = self.git.list_branches_detailed()
        self.btn_fetch.set_visible(self.git.has_remote("origin"))
        self._populate()

    def _current_name(self):
        return self.git.get_branch_name()

    # --- Rendering ---

    def _populate(self):
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)
        self._actions = []

        query = self.search.get_text().strip()
        q = query.lower()
        local = [b for b in self._branches if b["kind"] == "local" and q in b["name"].lower()]
        remote = [b for b in self._branches
                  if b["kind"] == "remote" and not b["has_local"] and q in b["name"].lower()]

        # Exact match first so Enter switches to it
        local.sort(key=lambda b: (b["name"].lower() != q, not b["current"]))

        exact = any(b["name"] == query for b in self._branches if b["kind"] == "local")
        if query and not exact and self.git.is_valid_branch_name(query):
            self._append_create_row(query)

        if local:
            self._append_section(t("branch_local"))
            for b in local:
                self._append_local_row(b)
        if remote:
            self._append_section(t("branch_remote"))
            for b in remote:
                self._append_remote_row(b)

        if not self._actions:
            self.list_box.append(Gtk.Label(label=t("branch_none_found"), css_classes=["stat-label"], margin_top=10, margin_bottom=10))

    def _append_section(self, title):
        lbl = Gtk.Label(label=title.upper(), css_classes=["stat-label"], xalign=0)
        lbl.set_margin_top(6)
        lbl.set_margin_start(6)
        self.list_box.append(lbl)

    def _row_button(self, icon_name, name, detail=None, detail_css="stat-label", dim_icon=False):
        btn = Gtk.Button(css_classes=["flat", "branch-row-btn"], hexpand=True)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(14)
        if dim_icon:
            icon.set_opacity(0.35)
        row.append(icon)
        lbl = Gtk.Label(label=name, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        row.append(lbl)
        if detail:
            row.append(Gtk.Label(label=detail, css_classes=[detail_css]))
        btn.set_child(row)
        return btn, lbl

    def _append_create_row(self, name):
        btn, lbl = self._row_button("list-add-symbolic", t("branch_create").format(name=name))
        lbl.add_css_class("branch-create-label")
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        btn.set_tooltip_text(t("branch_create_hint"))
        action = lambda: self._create(name)
        btn.connect("clicked", lambda b: action())
        self._actions.append(action)
        self.list_box.append(btn)

    def _append_local_row(self, b):
        detail_parts = []
        if b["ahead"]:
            detail_parts.append(f"↑{b['ahead']}")
        if b["behind"]:
            detail_parts.append(f"↓{b['behind']}")
        if b["gone"]:
            detail_parts.append(t("branch_upstream_gone"))
        detail = " ".join(detail_parts) or None

        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        btn, lbl = self._row_button(
            "emblem-ok-symbolic" if b["current"] else "media-record-symbolic",
            b["name"], detail, "ahead-badge", dim_icon=not b["current"])
        if b["current"]:
            lbl.add_css_class("branch-current-label")
        if b.get("subject"):
            btn.set_tooltip_text(f"{b['subject']}\n{b.get('date', '')}".strip())
        action = lambda name=b["name"]: self._switch(name, remote=False)
        btn.connect("clicked", lambda _b: action())
        self._actions.append(action)
        line.append(btn)
        line.append(self._make_menu_button(b))
        self.list_box.append(line)

    def _append_remote_row(self, b):
        btn, _ = self._row_button("network-server-symbolic", b["name"], dim_icon=True)
        if b.get("subject"):
            btn.set_tooltip_text(f"{b['subject']}\n{b.get('date', '')}".strip())
        action = lambda name=b["name"]: self._switch(name, remote=True)
        btn.connect("clicked", lambda _b: action())
        self._actions.append(action)
        self.list_box.append(btn)

    def _make_menu_button(self, b):
        btn = Gtk.Button(icon_name="view-more-symbolic", css_classes=["flat", "subtle-icon-btn"])
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda _b, br=b: self._show_actions(br))
        return btn

    def _show_actions(self, b):
        while child := self.actions_page.get_first_child():
            self.actions_page.remove(child)

        back = Gtk.Button(css_classes=["flat", "branch-row-btn"])
        back_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        back_row.append(Gtk.Image.new_from_icon_name("go-previous-symbolic"))
        back_row.append(Gtk.Label(label=b["name"], xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE,
                                  css_classes=["branch-current-label"] if b["current"] else []))
        back.set_child(back_row)
        back.connect("clicked", lambda _b: self._back_to_list())
        self.actions_page.append(back)
        self.actions_page.append(Gtk.Separator(margin_top=4, margin_bottom=4))

        def _item(icon, label, callback, css=None):
            item = Gtk.Button(css_classes=["flat", "branch-row-btn"])
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(14)
            row.append(img)
            row.append(Gtk.Label(label=label, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END))
            item.set_child(row)
            if css:
                item.add_css_class(css)

            def _clicked(_btn):
                self.popdown()
                callback()
            item.connect("clicked", _clicked)
            self.actions_page.append(item)

        name = b["name"]
        current = self._current_name()
        if not b["current"]:
            _item("object-select-symbolic", t("switch_branch"), lambda: self._switch(name, remote=False))
        _item("document-edit-symbolic", t("branch_rename"), lambda: self._rename(name))
        if not b["current"] and current:
            _item("media-playlist-consecutive-symbolic", t("branch_merge_into").format(name=current),
                  lambda: self._merge(name))
        if not b["current"]:
            _item("user-trash-symbolic", t("branch_delete"), lambda: self._delete(name), "danger-text")

        self.pages.set_visible_child_name("actions")

    def _back_to_list(self):
        self.pages.set_visible_child_name("list")
        self.search.grab_focus()

    # --- Busy state ---

    def _set_busy(self, text):
        self._busy = bool(text)
        self.lbl_busy.set_text(text or "")
        self.spinner.set_spinning(self._busy)
        self.search.set_sensitive(not self._busy)
        self.scrolled.set_sensitive(not self._busy)
        self.btn_fetch.set_sensitive(not self._busy)

    def _run(self, busy_text, fn, on_done):
        if self._busy:
            return
        self._set_busy(busy_text)

        def _done(result):
            self._set_busy(None)
            on_done(*result)
        run_in_background(fn, _done)

    # --- Actions ---

    def _activate_first(self):
        if self._actions and not self._busy:
            self._actions[0]()

    def _on_key(self, _ctl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            if self.pages.get_visible_child_name() == "actions":
                self._back_to_list()
            else:
                self.popdown()
            return True
        return False

    def _changed(self, sound="click"):
        self.sound.play(sound)
        self.on_changed()

    def _fail(self, title, msg):
        self.sound.play("error")
        self.on_error(title, msg)

    def _switch(self, name, remote):
        if not remote and name == self._current_name():
            self.popdown()
            return

        def op():
            return self.git.checkout_remote_branch(name) if remote else self.git.checkout_branch(name)

        def done(ok, msg):
            if ok:
                self.popdown()
                self._changed()
                return
            self.popdown()
            if self.git.has_changes():
                self._offer_stash_and_switch(name, op)
            else:
                self._fail(t("checkout_failed"), msg)

        self._run(t("branch_switching").format(name=name), op, done)

    def _offer_stash_and_switch(self, name, switch_op):
        current = self.git.get_current_branch()

        def on_choice(choice, _value):
            if choice != "stash":
                return

            def op():
                ok, msg = self.git.stash_save(
                    f"GitPulse: auto-stash on {current} before switching to {name}", include_untracked=True)
                if not ok:
                    return False, msg
                return switch_op()

            def done(result):
                ok, msg = result
                self.on_changed()
                if ok:
                    self.sound.play("click")
                else:
                    self._fail(t("checkout_failed"), msg)
            run_in_background(op, done)

        show_choice_dialog(
            self.window, t("branch_dirty_title"), t("branch_dirty_desc").format(name=name),
            [("cancel", t("cancel"), "subtle"), ("stash", t("branch_stash_switch"), "primary")],
            on_choice)

    def _create(self, name):
        def done(ok, msg):
            if ok:
                self.popdown()
                self._changed("commit")
            else:
                self._fail(t("branch_op_failed"), msg)
        self._run(t("branch_working"), lambda: self.git.create_branch(name), done)

    def _rename(self, old_name):
        def on_choice(_choice, new_name):
            if not new_name or new_name == old_name:
                return
            ok, msg = self.git.rename_branch(old_name, new_name)
            if ok:
                self._changed()
            else:
                self._fail(t("branch_op_failed"), msg)

        show_choice_dialog(
            self.window, t("branch_rename_title"), t("branch_rename_desc").format(name=old_name),
            [("cancel", t("cancel"), "subtle"), ("rename", t("branch_rename_btn"), "primary")],
            on_choice, entry_text=old_name,
            entry_validator=lambda s: s == old_name or (self.git.is_valid_branch_name(s) and not self.git.branch_exists(s)))

    def _merge(self, name):
        current = self._current_name()

        def on_choice(choice, _value):
            if choice != "merge":
                return

            def done(result):
                ok, msg = result
                self.on_changed()
                if ok:
                    self.sound.play("commit")
                elif self.git.is_merging():
                    self._fail(t("merge_failed"), t("merge_conflicts_desc"))
                else:
                    self._fail(t("merge_failed"), msg)
            run_in_background(lambda: self.git.merge_branch(name), done)

        show_choice_dialog(
            self.window, t("branch_merge_title"), t("branch_merge_desc").format(src=name, dst=current),
            [("cancel", t("cancel"), "subtle"), ("merge", t("branch_merge_btn"), "primary")],
            on_choice)

    def _delete(self, name):
        unmerged = self.git.unmerged_commit_count(name)
        if unmerged:
            desc = t("branch_delete_unmerged").format(name=name, count=unmerged)
        else:
            desc = t("branch_delete_desc").format(name=name)

        def on_choice(choice, _value):
            if choice != "delete":
                return
            # Confirmed by the user (and nothing is lost when unmerged == 0), so force is safe here
            ok, msg = self.git.delete_branch(name, force=True)
            if ok:
                self._changed("pop")
            else:
                self._fail(t("branch_op_failed"), msg)

        show_choice_dialog(
            self.window, t("branch_delete_title"), desc,
            [("cancel", t("cancel"), "subtle"), ("delete", t("branch_delete_btn"), "destructive")],
            on_choice)

    def _on_fetch(self):
        token = self.get_token() or None

        def done(ok, msg):
            if ok:
                self._reload()
                self.on_changed()
            else:
                self.popdown()
                self._fail(t("fetch_failed"), msg)
        self._run(t("branch_fetching"), lambda: self.git.fetch(token=token), done)
