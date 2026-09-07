#!/usr/bin/env bash
# GitPulse HUD — Desktop Application Installer
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/git-pulse-hud.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

echo "==> Installing GitPulse HUD for user $(whoami)..."

# Create directories if needed
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$ICON_DIR"

# Install icon
cp "$APP_DIR/assets/icon.png" "$ICON_DIR/git-pulse-hud.png"

# Generate desktop file with absolute paths
cat << DESKTOP > "$DESKTOP_FILE"
[Desktop Entry]
Name=GitPulse HUD
GenericName=Git HUD & Telemetry Companion
Comment=Modern GTK4 / Libadwaita Git micro-staging, conventional commits, and repo pulse analytics companion
Exec=python3 "$APP_DIR/main.py"
Icon=git-pulse-hud
Terminal=false
Type=Application
Categories=Development;RevisionControl;GTK;
StartupNotify=true
StartupWMClass=io.github.xronni.gitpulse
DESKTOP

chmod +x "$DESKTOP_FILE"

# Update desktop and icon databases
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" || true
fi

echo "✨ GitPulse HUD installed successfully!"
echo "You can now launch GitPulse HUD from your application menu or run './run.sh'"
