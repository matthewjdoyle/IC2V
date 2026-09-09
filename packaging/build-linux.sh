#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure clean build
rm -rf dist/ build/

# Build using PyInstaller
python3 -m PyInstaller --noconfirm packaging/ic2v-gui.spec
python3 -m pip freeze > dist/IC2V/BUILD_INFO.txt

echo "Packaging tarball..."
cd dist
tar -czvf IC2V-linux-x86_64.tar.gz IC2V
cd ..

echo "Packaging AppImage..."
# Create AppDir structure
APPDIR="dist/IC2V.AppDir"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"

# Copy binary and dependencies
cp -r dist/IC2V/* "$APPDIR/usr/bin/"

# Copy icon
cp src/ic2v/assets/ic2v.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
cp src/ic2v/assets/ic2v.svg "$APPDIR/ic2v.svg"

# Create .desktop file
cat <<EOF > "$APPDIR/usr/share/applications/ic2v.desktop"
[Desktop Entry]
Name=IC2V
Exec=IC2V
Icon=ic2v
Type=Application
Categories=Utility;
EOF
cp "$APPDIR/usr/share/applications/ic2v.desktop" "$APPDIR/"

# Create AppRun script
cat <<'EOF' > "$APPDIR/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/IC2V" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Download appimagetool if we don't have it locally
if ! command -v appimagetool &> /dev/null; then
    wget -qO appimagetool "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool
    APPIMAGETOOL="./appimagetool"
else
    APPIMAGETOOL="appimagetool"
fi

# Build AppImage (requires FUSE, but in CI we usually extract it)
if [ -n "$CI" ]; then
    $APPIMAGETOOL --appimage-extract-and-run "$APPDIR"
else
    $APPIMAGETOOL "$APPDIR"
fi

mv IC2V*.AppImage dist/
echo "Done! Linux artifacts are in dist/"
