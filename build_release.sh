#!/usr/bin/env bash
# GitPulse HUD — Release Artifacts Builder
# Builds .deb package, portable .tar.gz archive, .zip, and SHA256SUMS.txt
set -e

VERSION="1.0.0"
APP_NAME="git-pulse-hud"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build_artifacts"

echo "================================================================"
echo " ⚡ Building Release Artifacts for $APP_NAME v$VERSION"
echo "================================================================"

# Clean up previous builds
rm -rf "$DIST_DIR" "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

# 1. Build .deb package
echo "==> 1. Building Debian / Ubuntu (.deb) package..."
DEB_ROOT="$BUILD_DIR/deb_root"
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/$APP_NAME"
mkdir -p "$DEB_ROOT/usr/share/$APP_NAME/assets"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps"

# Control file
cat << CONTROL > "$DEB_ROOT/DEBIAN/control"
Package: $APP_NAME
Version: $VERSION
Section: devel
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-adw-1, python3-cairo, git
Maintainer: Xronni <xronnimail@gmail.com>
Homepage: https://github.com/Xronni/$APP_NAME
Description: Tactical Git staging, conventional commits & repo pulse companion
 GitPulse HUD is a sleek, lightweight, semi-transparent Git micro-staging,
 Conventional Commits assistant, visual branch graph, and real-time repository
 pulse analytics companion for Linux developers. Built with GTK4 & Libadwaita.
CONTROL

# Post-install & Post-remove hooks
cat << 'POSTINST' > "$DEB_ROOT/DEBIAN/postinst"
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi
exit 0
POSTINST
chmod 755 "$DEB_ROOT/DEBIAN/postinst"

cat << 'POSTRM' > "$DEB_ROOT/DEBIAN/postrm"
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi
exit 0
POSTRM
chmod 755 "$DEB_ROOT/DEBIAN/postrm"

# Copy application files
cp "$SCRIPT_DIR"/*.py "$DEB_ROOT/usr/share/$APP_NAME/"
cp "$SCRIPT_DIR/style.css" "$DEB_ROOT/usr/share/$APP_NAME/"
cp "$SCRIPT_DIR/assets/icon.png" "$DEB_ROOT/usr/share/$APP_NAME/assets/"
cp "$SCRIPT_DIR/assets/icon.png" "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"

# Executable launcher in /usr/bin
cat << LAUNCHER > "$DEB_ROOT/usr/bin/$APP_NAME"
#!/bin/sh
exec python3 /usr/share/$APP_NAME/main.py "\$@"
LAUNCHER
chmod 755 "$DEB_ROOT/usr/bin/$APP_NAME"

# Desktop entry
cat << DESKTOP > "$DEB_ROOT/usr/share/applications/$APP_NAME.desktop"
[Desktop Entry]
Name=GitPulse HUD
GenericName=Git HUD & Telemetry Companion
Comment=Modern GTK4 / Libadwaita Git micro-staging, conventional commits, and repo pulse analytics companion
Exec=/usr/bin/$APP_NAME
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=Development;RevisionControl;GTK;
StartupNotify=true
StartupWMClass=io.github.xronni.gitpulse
DESKTOP
chmod 644 "$DEB_ROOT/usr/share/applications/$APP_NAME.desktop"

# Fix permissions
find "$DEB_ROOT" -type d -exec chmod 755 {} +
find "$DEB_ROOT/usr/share/$APP_NAME" -type f -exec chmod 644 {} +
chmod 755 "$DEB_ROOT/usr/share/$APP_NAME/main.py"

# Build deb
DEB_FILE="$DIST_DIR/${APP_NAME}_${VERSION}_all.deb"
dpkg-deb --build "$DEB_ROOT" "$DEB_FILE"
echo "   ✓ Built: $(basename "$DEB_FILE") ($(du -h "$DEB_FILE" | cut -f1))"

# 2. Build Portable .tar.gz archive
echo "==> 2. Building Standalone Portable (.tar.gz) archive..."
TAR_DIR="$BUILD_DIR/${APP_NAME}-${VERSION}"
mkdir -p "$TAR_DIR/assets"

cp "$SCRIPT_DIR"/*.py "$TAR_DIR/"
cp "$SCRIPT_DIR/style.css" "$TAR_DIR/"
cp "$SCRIPT_DIR/run.sh" "$TAR_DIR/"
cp "$SCRIPT_DIR/install.sh" "$TAR_DIR/"
cp "$SCRIPT_DIR/uninstall.sh" "$TAR_DIR/"
cp "$SCRIPT_DIR/test.sh" "$TAR_DIR/"
cp "$SCRIPT_DIR/README.md" "$TAR_DIR/"
cp "$SCRIPT_DIR/LICENSE" "$TAR_DIR/"
cp "$SCRIPT_DIR/assets/icon.png" "$TAR_DIR/assets/"

chmod +x "$TAR_DIR"/*.sh "$TAR_DIR/main.py"

TAR_FILE="$DIST_DIR/${APP_NAME}-v${VERSION}-linux-x86_64.tar.gz"
tar -czf "$TAR_FILE" -C "$BUILD_DIR" "${APP_NAME}-${VERSION}"
echo "   ✓ Built: $(basename "$TAR_FILE") ($(du -h "$TAR_FILE" | cut -f1))"

# 3. Build .zip archive
echo "==> 3. Building Universal Zip (.zip) archive..."
ZIP_FILE="$DIST_DIR/${APP_NAME}-v${VERSION}-portable.zip"
(cd "$BUILD_DIR" && zip -q -r "$ZIP_FILE" "${APP_NAME}-${VERSION}")
echo "   ✓ Built: $(basename "$ZIP_FILE") ($(du -h "$ZIP_FILE" | cut -f1))"

# 4. Generate SHA256 checksums
echo "==> 4. Generating SHA256 Checksums..."
(cd "$DIST_DIR" && sha256sum * > SHA256SUMS.txt)
echo "   ✓ Generated SHA256SUMS.txt"

# Clean temporary build directory
rm -rf "$BUILD_DIR"

echo "================================================================"
echo " 🎉 All release files successfully built in: dist/"
ls -lh "$DIST_DIR"
echo "================================================================"
