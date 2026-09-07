#!/usr/bin/env bash
# GitPulse HUD — Uninstaller
set -e

DESKTOP_FILE="$HOME/.local/share/applications/git-pulse-hud.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/256x256/apps/git-pulse-hud.png"

echo "==> Removing GitPulse HUD desktop entries..."
rm -f "$DESKTOP_FILE"
rm -f "$ICON_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" || true
fi

echo "✨ GitPulse HUD uninstalled successfully."
