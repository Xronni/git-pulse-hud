#!/usr/bin/env python3
"""
GitPulse HUD — remote sync & auto-refresh (mixin for GitPulseWindow).

- Sidebar sync row: Fetch / Pull (↓N) / Push (↑N), always visible when 'origin' exists
- Background fetch every `auto_fetch_minutes` (config, 0 disables)
- Auto-refresh: while the window is active, polls a cheap repo fingerprint and
  rebuilds the views only when something changed (terminal commits, editor saves, …)
"""

import threading
import time

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

from i18n import t

POLL_INTERVAL_MS = 3000
AUTO_FETCH_TICK_S = 60
DEFAULT_AUTO_FETCH_MINUTES = 5


class SyncMixin:
    """Expects: self.git, self.sound, self.telemetry, self.config, self._load_repo_data(),
    self._show_error_dialog(), self._toast(), self._on_publish_dialog()."""

    # --- UI ---

    def _build_sync_row(self, parent):
        self._sync_busy = False
        self._last_fetch_time = 0.0
        self._last_fetch_error = ""

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, homogeneous=True)
        row.add_css_class("sync-row")

        self.btn_sync_fetch = Gtk.Button(css_classes=["sync-btn"])
        self.sync_fetch_stack = Gtk.Stack()
        self.sync_fetch_stack.add_named(Gtk.Image.new_from_icon_name("emblem-synchronizing-symbolic"), "icon")
        self.sync_fetch_spinner = Gtk.Spinner()
        self.sync_fetch_stack.add_named(self.sync_fetch_spinner, "spinner")
        self.btn_sync_fetch.set_child(self.sync_fetch_stack)
        self.btn_sync_fetch.connect("clicked", lambda b: self._do_fetch(silent=False))
        row.append(self.btn_sync_fetch)

        self.btn_sync_pull = Gtk.Button(label="↓ 0", css_classes=["sync-btn"])
        self.btn_sync_pull.connect("clicked", lambda b: self._do_pull())
        row.append(self.btn_sync_pull)

        self.btn_sync_push = Gtk.Button(label="↑ 0", css_classes=["sync-btn"])
        self.btn_sync_push.connect("clicked", lambda b: self._do_push())
        row.append(self.btn_sync_push)

        self.sidebar_sync_row = row
        parent.append(row)

    def _set_sync_busy(self, busy):
        self._sync_busy = busy
        self.sync_fetch_stack.set_visible_child_name("spinner" if busy else "icon")
        if busy:
            self.sync_fetch_spinner.start()
        else:
            self.sync_fetch_spinner.stop()
        for b in (self.btn_sync_fetch, self.btn_sync_pull, self.btn_sync_push):
            b.set_sensitive(not busy)
        if hasattr(self, "btn_push_only"):
            self.btn_push_only.set_sensitive(not busy)

    def _format_last_fetch(self):
        if not self._last_fetch_time:
            return t("sync_never")
        minutes = int((time.time() - self._last_fetch_time) // 60)
        if minutes < 1:
            return t("time_just_now")
        return t("time_min_ago").format(n=minutes)

    def _refresh_sync_status(self, ahead=None, behind=None):
        """Updates the sidebar counters; ahead/behind may be passed in to avoid recomputing."""
        if not self.git.is_valid():
            self.sidebar_sync_row.set_visible(False)
            return
        has_origin = self.git.has_remote("origin")
        self.sidebar_sync_row.set_visible(has_origin)
        self.sidebar_ahead.set_visible(not has_origin)
        if not has_origin:
            return
        if ahead is None or behind is None:
            ahead, behind = self.git.get_ahead_behind()
        upstream = self.git.get_upstream() or "origin"

        self.btn_sync_pull.set_label(f"↓ {behind}")
        self.btn_sync_push.set_label(f"↑ {ahead}")
        for btn, attn in ((self.btn_sync_pull, behind > 0), (self.btn_sync_push, ahead > 0)):
            if attn:
                btn.add_css_class("sync-attn")
            else:
                btn.remove_css_class("sync-attn")

        fetch_tip = t("sync_fetch_tooltip").format(when=self._format_last_fetch())
        if self._last_fetch_error:
            fetch_tip += "\n" + t("sync_fetch_error").format(err=self._last_fetch_error.splitlines()[-1])
        self.btn_sync_fetch.set_tooltip_text(fetch_tip)
        self.btn_sync_pull.set_tooltip_text(t("sync_pull_tooltip").format(n=behind, upstream=upstream))
        self.btn_sync_push.set_tooltip_text(t("sync_push_tooltip").format(n=ahead, upstream=upstream))

    # --- Remote operations ---

    def _run_remote_op(self, op, on_ok, error_title, silent=False):
        """Runs a network git op on a worker thread with the sync row in busy state."""
        if self._sync_busy:
            return
        self._set_sync_busy(True)
        repo = self.git.root_path

        def _bg():
            ok, out = op()

            def _done():
                self._set_sync_busy(False)
                if repo != self.git.root_path:
                    return False  # user switched repositories meanwhile
                if ok:
                    on_ok(out)
                elif not silent:
                    self.sound.play("error")
                    self._show_error_dialog(error_title, (out or "").strip() or "Unknown error")
                self._refresh_sync_status()
                return False
            GLib.idle_add(_done)
        threading.Thread(target=_bg, daemon=True).start()

    def _do_fetch(self, silent=False):
        if not self.git.is_valid() or not self.git.has_remote("origin"):
            return
        tok = self.telemetry.token

        def op():
            ok, out = self.git.fetch(token=tok)
            self._last_fetch_time = time.time()
            self._last_fetch_error = "" if ok else (out or "")
            return ok, out

        def on_ok(_out):
            if not silent:
                self.sound.play("pop")
                self._toast(t("fetch_done"))
            self._load_repo_data()

        self._run_remote_op(op, on_ok, t("fetch_failed"), silent=silent)

    def _do_push(self):
        if not self.git.is_valid():
            return
        if not self.git.has_remote("origin"):
            self._on_publish_dialog()
            return
        if self.git.is_detached():
            self.sound.play("error")
            self._show_error_dialog(t("push_failed"), t("push_detached"))
            return
        tok = self.telemetry.token

        def on_ok(_out):
            self.sound.play("push")
            self._toast(t("push_done"))
            self._load_repo_data()

        self._run_remote_op(lambda: self.git.push(token=tok), on_ok, t("push_failed"))

    def _do_pull(self):
        if not self.git.is_valid() or not self.git.has_remote("origin"):
            return
        if self.git.is_detached():
            self.sound.play("error")
            self._show_error_dialog(t("pull_failed"), t("push_detached"))
            return
        tok = self.telemetry.token

        def on_ok(_out):
            self.sound.play("pop")
            self._toast(t("pull_done"))
            self._load_repo_data()

        def on_fail_refresh():
            # A pull that stops on conflicts leaves a merge in progress: show it
            self._load_repo_data()

        def op():
            res = self.git.pull(token=tok)
            if not res[0]:
                GLib.idle_add(lambda: (on_fail_refresh(), False)[1])
            return res

        self._run_remote_op(op, on_ok, t("pull_failed"))

    # --- Background timers ---

    def _start_sync_timers(self):
        self._poll_running = False
        self._last_state_sig = None
        GLib.timeout_add(POLL_INTERVAL_MS, self._poll_tick)
        GLib.timeout_add_seconds(AUTO_FETCH_TICK_S, self._auto_fetch_tick)
        self.connect("notify::is-active", self._on_active_changed)
        # First fetch shortly after startup, then every auto_fetch_minutes
        GLib.timeout_add_seconds(3, lambda: (self._auto_fetch_tick(force=True), False)[1])

    def _reset_sync_state(self):
        """Call after switching repositories."""
        self._last_fetch_time = 0.0
        self._last_fetch_error = ""
        self._last_state_sig = None
        # Fetch the new repository shortly instead of waiting a full interval
        GLib.timeout_add_seconds(3, lambda: (self._auto_fetch_tick(force=True), False)[1])

    def _mark_state_fresh(self):
        """The UI was just rebuilt: the next poll should only record the fingerprint."""
        self._last_state_sig = None

    def _on_active_changed(self, *_):
        if self.is_active():
            self._poll_tick()

    def _poll_tick(self):
        if self._poll_running or not self.is_active() or not self.git.is_valid():
            return True
        self._poll_running = True
        repo = self.git.root_path

        def _bg():
            sig = self.git.state_signature()

            def _done():
                self._poll_running = False
                if sig is None or repo != self.git.root_path:
                    return False
                previous = self._last_state_sig
                self._last_state_sig = sig
                if previous is not None and previous != sig:
                    self._on_repo_changed_externally()
                return False
            GLib.idle_add(_done)
        threading.Thread(target=_bg, daemon=True).start()
        return True

    def _on_repo_changed_externally(self):
        sig = self._last_state_sig
        self._load_repo_data()
        self._last_state_sig = sig  # keep: _load_repo_data reflects exactly this state
        if self.active_view == "history":
            self._refresh_history_view()
        elif self.active_view == "pulse":
            self._refresh_pulse_view()

    def _auto_fetch_tick(self, force=False):
        try:
            minutes = float(self.config.get("auto_fetch_minutes", DEFAULT_AUTO_FETCH_MINUTES))
        except (TypeError, ValueError):
            minutes = DEFAULT_AUTO_FETCH_MINUTES
        if minutes <= 0 and not force:
            return True
        due = force or (time.time() - self._last_fetch_time) >= minutes * 60
        if due and not self._sync_busy and self.git.is_valid() and self.git.has_remote("origin"):
            self._do_fetch(silent=True)
        return True
