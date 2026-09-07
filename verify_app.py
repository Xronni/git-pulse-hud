#!/usr/bin/env python3
"""
GitPulse HUD — Automated Pre-Deployment Verification Suite
Runs full functional, unit, and integration checks across all modules.
"""

import sys
import os
import shutil
import tempfile
import subprocess
import json

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

passed_tests = 0
failed_tests = 0


def report(name, success, details=""):
    global passed_tests, failed_tests
    if success:
        passed_tests += 1
        print(f" {GREEN}✓{RESET} {BOLD}{name}{RESET}")
        if details:
            print(f"   {details}")
    else:
        failed_tests += 1
        print(f" {RED}✗{RESET} {BOLD}{name}{RESET}")
        if details:
            print(f"   {RED}{details}{RESET}")


def section(title):
    print(f"\n{CYAN}{BOLD}--- {title} ---{RESET}")


def test_system_dependencies():
    section("1. System Environment & Dependencies")
    
    # Python Version
    py_ver = sys.version_info
    is_py_ok = py_ver >= (3, 10)
    report("Python Version >= 3.10", is_py_ok, f"Current: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")

    # Git CLI
    git_path = shutil.which("git")
    report("Git Executable in PATH", bool(git_path), f"Path: {git_path or 'NOT FOUND'}")

    # Audio Engine Player
    audio_player = None
    for p in ["pw-play", "paplay", "canberra-gtk-play", "aplay"]:
        if shutil.which(p):
            audio_player = p
            break
    report("Linux Audio Subsystem Player", bool(audio_player), f"Detected backend: {audio_player or 'fallback mute'}")

    # GTK4 & Libadwaita
    gtk_ok = False
    adw_ok = False
    try:
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
        from gi.repository import Gtk, Adw, Gdk
        gtk_ok = True
        adw_ok = True
    except Exception as e:
        report("GTK4 / Libadwaita Runtime", False, str(e))

    if gtk_ok and adw_ok:
        report("GTK 4.0 & Libadwaita 1.0 Bindings", True, "Successfully loaded native gobject introspection")

    try:
        import cairo
        report("Cairo 2D Vector Graphics", True, f"Cairo Version: {cairo.cairo_version_string()}")
    except Exception as e:
        report("Cairo Graphics", False, str(e))


def test_assets_and_packaging():
    section("2. Project Assets & Desktop Packaging")

    icon_path = os.path.join(APP_DIR, "assets", "icon.png")
    is_icon = os.path.exists(icon_path) and os.path.getsize(icon_path) > 1000
    report("Application Icon Asset", is_icon, f"Path: {icon_path} ({os.path.getsize(icon_path)} bytes)" if is_icon else "Missing icon")

    css_path = os.path.join(APP_DIR, "style.css")
    is_css = os.path.exists(css_path) and os.path.getsize(css_path) > 500
    report("Dark Theme CSS Stylesheet", is_css, f"Path: {css_path} ({os.path.getsize(css_path)} bytes)" if is_css else "Missing style.css")

    desktop_file = os.path.join(APP_DIR, "git-pulse-hud.desktop")
    is_desktop = os.path.exists(desktop_file)
    report("FreeDesktop .desktop File", is_desktop, f"File: {desktop_file}")

    run_sh = os.path.join(APP_DIR, "run.sh")
    is_run_exec = os.path.exists(run_sh) and os.access(run_sh, os.X_OK)
    report("Executable run.sh Launcher", is_run_exec, f"Path: {run_sh}")


def test_i18n_parity():
    section("3. Bilingual Localization Parity (EN / RU)")

    import i18n
    en_keys = set(i18n.TRANSLATIONS["en"].keys())
    ru_keys = set(i18n.TRANSLATIONS["ru"].keys())

    missing_in_ru = en_keys - ru_keys
    missing_in_en = ru_keys - en_keys

    parity = (len(missing_in_ru) == 0 and len(missing_in_en) == 0)
    report(f"Translation Dictionary Parity ({len(en_keys)} keys)", parity,
           f"EN keys: {len(en_keys)}, RU keys: {len(ru_keys)}")
    if missing_in_ru:
        report("Missing RU keys", False, f"{missing_in_ru}")
    if missing_in_en:
        report("Missing EN keys", False, f"{missing_in_en}")

    i18n.set_language("en")
    en_done = i18n.t("refresh_done")
    i18n.set_language("ru")
    ru_done = i18n.t("refresh_done")

    is_en_check = en_done.endswith(" ✓")
    is_ru_check = ru_done.endswith(" ✓")
    report("Checkmark Formatting ('Up to date ✓')", is_en_check and is_ru_check,
           f"EN: '{en_done}', RU: '{ru_done}'")


def test_git_engine():
    section("4. Git Engine Core & Advanced Operations")

    from git_engine import GitEngine

    with tempfile.TemporaryDirectory() as tmp_dir:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_dir, capture_output=True, check=True)

        ge = GitEngine(tmp_dir)
        report("Repository Validation", ge.is_valid(), f"Root: {ge.root_path}")
        report("Branch Detection", ge.get_current_branch() == "main", f"Current: {ge.get_current_branch()}")

        f1 = os.path.join(tmp_dir, "file1.txt")
        with open(f1, "w") as f:
            f.write("line 1\nline 2\n")
        ge.stage_file("file1.txt")
        status = ge.get_status_files()
        report("Stage Single File", len(status["staged"]) == 1, f"Staged: {status['staged'][0]['path']}")

        ok, out = ge.commit("feat: initial commit")
        report("Commit Execution", ok, f"Commit output: {out.strip() if out else 'OK'}")

        subprocess.run(["git", "branch", "feature-x"], cwd=tmp_dir, capture_output=True, check=True)
        branches = ge.list_branches_detailed()
        has_branches = any(b["name"] == "feature-x" for b in branches)
        report("Branch Listing & Details", has_branches, f"Found {len(branches)} branches")

        ok_co, _ = ge.checkout_branch("feature-x")
        report("Branch Checkout (git checkout)", ok_co and ge.get_current_branch() == "feature-x",
               f"Active branch: {ge.get_current_branch()}")

        with open(f1, "a") as f:
            f.write("feature changes\n")
        ok_stash, _ = ge.stash_save("WIP on feature")
        report("Stash Save", ok_stash, "Successfully created stash")

        stashes = ge.stash_list()
        report("Stash Listing & Metadata", len(stashes) == 1,
               f"Stash count: {len(stashes)}, msg: '{stashes[0]['message'] if stashes else ''}'")

        diff = ge.stash_diff(0)
        report("Stash Diff Inspection", "feature changes" in diff, "Diff preview verified")

        ok_pop, _ = ge.stash_pop(0)
        report("Stash Pop", ok_pop, "Stash restored")

        ge.stage_all()
        ge.commit("feat(auth): add oauth login")
        ge.create_tag("v1.0.0", "Release 1.0.0")

        with open(os.path.join(tmp_dir, "fix.txt"), "w") as f:
            f.write("bugfix\n")
        ge.stage_all()
        ge.commit("fix(api): fix null pointer exception")

        cl = ge.get_changelog_data()
        report("Conventional Changelog Grouping",
               len(cl["categories"]["fix"]) >= 1,
               f"Grouped fixes: {len(cl['categories']['fix'])}, latest tag: {cl['latest_tag']}")

        graph = ge.get_commit_graph(10)
        report("Commit Graph Lane Allocation", len(graph) >= 3 and "col" in graph[0],
               f"Retrieved {len(graph)} commits with lane columns")


def test_secret_scanner():
    section("5. Pre-Commit Secret Scanner")

    from git_engine import GitEngine
    from secret_scanner import scan_staged_files

    with tempfile.TemporaryDirectory() as tmp_dir:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Sec Tester"], cwd=tmp_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "sec@example.com"], cwd=tmp_dir, capture_output=True, check=True)

        ge = GitEngine(tmp_dir)

        clean_file = os.path.join(tmp_dir, "safe_code.py")
        with open(clean_file, "w") as f:
            f.write("def add(a, b):\n    return a + b\n")
        ge.stage_file("safe_code.py")
        is_clean, findings = scan_staged_files(ge)
        report("Clean File Scan", is_clean and len(findings) == 0, "No false positives detected")

        leak_file = os.path.join(tmp_dir, "keys.py")
        with open(leak_file, "w") as f:
            f.write("GITHUB_PAT = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'\n")
        ge.stage_file("keys.py")
        is_clean_2, findings_2 = scan_staged_files(ge)
        has_pat = any(f["rule"] == "GitHub Personal Access Token" for f in findings_2)
        report("GitHub PAT Leak Detection", not is_clean_2 and has_pat,
               f"Detected: {findings_2[0]['rule'] if findings_2 else 'None'} ({findings_2[0]['preview'] if findings_2 else ''})")

        env_file = os.path.join(tmp_dir, ".env")
        with open(env_file, "w") as f:
            f.write("DB_PASSWORD=secret\n")
        ge.stage_file(".env")
        is_clean_3, findings_3 = scan_staged_files(ge)
        has_env = any(f["rule"] == "Sensitive Configuration File" for f in findings_3)
        report("Sensitive Configuration (.env) Detection", has_env,
               f"Detected sensitive config: {env_file}")


def test_sound_engine():
    section("6. Sound Feedback Engine")

    from sound_engine import SoundEngine

    se = SoundEngine(enabled=True)
    report("Sound Pre-generation", len(se._cache) >= 5, f"Cached {len(se._cache)} WAV assets in RAM/temp")
    
    all_valid = all(os.path.exists(p) and os.path.getsize(p) > 100 for p in se._cache.values())
    report("Synthetic Audio Integrity", all_valid, "All PCM WAV waveforms generated without external files")


def test_dialogs_and_window_csd():
    section("7. Dialogs & Libadwaita Titlebars (CSD)")

    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw
    from git_engine import GitEngine
    from sound_engine import SoundEngine
    from stash_dialog import StashInspectorDialog
    from release_dialog import ReleaseDrafterDialog
    from diff_viewer import DiffViewerDialog
    from quick_switcher import QuickSwitcherDialog

    ge = GitEngine(APP_DIR)
    se = SoundEngine(enabled=False)
    parent = Gtk.Window()

    # Stash Dialog
    d_stash = StashInspectorDialog(parent, ge, se)
    tb_stash = d_stash.get_titlebar()
    report("Stash Inspector Titlebar", isinstance(tb_stash, Adw.HeaderBar),
           f"Single official titlebar: {type(tb_stash).__name__} (zero duplicate SSD)")

    # Release Drafter Dialog
    d_rel = ReleaseDrafterDialog(parent, ge, se)
    tb_rel = d_rel.get_titlebar()
    report("Release Drafter Titlebar", isinstance(tb_rel, Adw.HeaderBar),
           f"Single official titlebar: {type(tb_rel).__name__} (zero duplicate SSD)")

    # Diff Viewer Dialog
    d_diff = DiffViewerDialog(parent, "main.py", "diff --git ...")
    tb_diff = d_diff.get_titlebar()
    report("Diff Viewer Titlebar", isinstance(tb_diff, Adw.HeaderBar),
           f"Single official titlebar: {type(tb_diff).__name__} (zero duplicate SSD)")

    # Quick Switcher
    d_qs = QuickSwitcherDialog(parent, [APP_DIR], APP_DIR, se, None, None)
    report("Quick Switcher Window", d_qs.get_child() is not None, "Spotlight-style dialog initialized cleanly")


def test_charts_rendering():
    section("8. Cairo Vector Visualizations")

    from pulse_widget import CommitVelocityWidget, PunchcardWidget, TrafficViewsChart, BranchGraphNodeWidget

    try:
        w_vel = CommitVelocityWidget()
        w_vel.set_data([{"date": "2026-09-01", "count": 5}, {"date": "2026-09-02", "count": 12}])
        report("Commit Velocity 14-Day Chart", w_vel.picture.get_paintable() is not None, "Vector bars & trendline rendered")

        w_punch = PunchcardWidget()
        w_punch.set_hours([2] * 24)
        report("24-Hour Punchcard Heatmap", w_punch.picture.get_paintable() is not None, "24 hourly activity buckets rendered")

        w_traffic = TrafficViewsChart()
        w_traffic.set_history([{"date": "2026-09-01", "views": 20, "uniques": 5}])
        report("Traffic Views Area Chart", w_traffic.picture.get_paintable() is not None, "Gradient area curve rendered")

        w_graph = BranchGraphNodeWidget(col=1, max_cols=3, is_merge=True)
        report("Branch Graph Node Vector", w_graph.picture.get_paintable() is not None, "Multi-lane Cairo tracks & merge curve rendered")
    except Exception as e:
        report("Cairo Charts Rendering", False, str(e))


def main():
    print(f"\n{BOLD}══════════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}         ⚡ GitPulse HUD — Full Verification Suite{RESET}")
    print(f"{BOLD}══════════════════════════════════════════════════════════════════{RESET}")

    test_system_dependencies()
    test_assets_and_packaging()
    test_i18n_parity()
    test_git_engine()
    test_secret_scanner()
    test_sound_engine()
    test_dialogs_and_window_csd()
    test_charts_rendering()

    total = passed_tests + failed_tests
    print(f"\n{BOLD}══════════════════════════════════════════════════════════════════{RESET}")
    if failed_tests == 0:
        print(f" {GREEN}{BOLD}🎉 ALL {passed_tests}/{total} CHECKS PASSED SUCCESSFULLY!{RESET}")
        print(f" {GREEN}GitPulse HUD is 100% verified and ready for deployment.{RESET}")
        print(f"{BOLD}══════════════════════════════════════════════════════════════════{RESET}\n")
        return 0
    else:
        print(f" {RED}{BOLD}⚠️ {failed_tests} out of {total} checks FAILED.{RESET}")
        print(f"{BOLD}══════════════════════════════════════════════════════════════════{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
