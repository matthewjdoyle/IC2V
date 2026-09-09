#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure clean build
rm -rf dist/ build/

# Build using PyInstaller
python3 -m PyInstaller --noconfirm packaging/ic2v-gui.spec
python3 -m pip freeze > dist/IC2V/BUILD_INFO.txt

echo "Packaging macOS App Bundle and DMG..."
cd dist

# The .app bundle is created in dist/IC2V.app by PyInstaller
if [ -d "IC2V.app" ]; then
    # Create DMG
    if command -v hdiutil &> /dev/null; then
        echo "Creating DMG..."
        hdiutil create -volname "IC2V" -srcfolder "IC2V.app" -ov -format UDZO "IC2V-macos.dmg"
    else
        echo "hdiutil not found, skipping DMG creation (are you on macOS?)"
    fi
else
    echo "Error: IC2V.app not found in dist/"
    exit 1
fi

echo "Done! macOS artifacts are in dist/"
