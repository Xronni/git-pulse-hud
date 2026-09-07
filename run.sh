#!/usr/bin/env bash
# GitPulse HUD — Intelligent Launcher with Clean OS Dependency Detection
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

CHECK_CODE="
import sys
missing = []
try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw
except Exception:
    missing.append('GTK 4.0 / Libadwaita 1.0 (PyGObject)')

try:
    import cairo
except Exception:
    missing.append('PyCairo (python3-cairo)')

if missing:
    print('MISSING: ' + ', '.join(missing))
    sys.exit(1)
"

if ! python3 -c "$CHECK_CODE" 2>/dev/null; then
    echo "================================================================"
    echo " ⚡ GitPulse HUD — System Dependencies Check"
    echo "================================================================"
    echo " Looks like some required Linux desktop libraries are missing:"
    python3 -c "$CHECK_CODE" || true
    echo ""
    echo " To run GitPulse HUD on your system, please install dependencies:"

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            ubuntu|debian|pop|linuxmint|elementary|zorin)
                CMD="sudo apt update && sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 git"
                ;;
            fedora|rhel|centos)
                CMD="sudo dnf install -y python3-gobject gtk4 libadwaita git python3-cairo"
                ;;
            arch|manjaro|endeavouros)
                CMD="sudo pacman -S --needed python-gobject gtk4 libadwaita git python-cairo"
                ;;
            opensuse*|suse)
                CMD="sudo zypper install -y python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 git python3-cairo"
                ;;
            *)
                CMD="sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 git"
                ;;
        esac
    else
        CMD="sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 git"
    fi

    echo " 👉 Run this command:"
    echo "    $CMD"
    echo "================================================================"
    
    if [ -t 0 ] && command -v sudo >/dev/null 2>&1; then
        read -r -p " Would you like to install these packages now? [y/N] " response
        case "$response" in
            [yY][eE][sS]|[yY])
                eval "$CMD"
                ;;
            *)
                echo " Installation cancelled. Run the command above when ready."
                exit 1
                ;;
        esac
    else
        exit 1
    fi
fi

exec python3 "$APP_DIR/main.py" "$@"
