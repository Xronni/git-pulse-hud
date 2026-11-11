#!/usr/bin/env python3
"""GitPulse HUD — tiny helper for running blocking work off the GTK main loop."""

import threading
import traceback

from gi.repository import GLib


def run_in_background(fn, on_done):
    """Runs fn() on a daemon thread, then on_done(result) on the GTK main loop.

    fn must not touch widgets. If fn raises, the traceback is printed and
    on_done is not called.
    """
    def _worker():
        try:
            result = fn()
        except Exception:
            traceback.print_exc()
            return

        def _deliver():
            on_done(result)
            return False
        GLib.idle_add(_deliver)
    threading.Thread(target=_worker, daemon=True).start()
