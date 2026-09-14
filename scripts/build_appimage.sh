#!/usr/bin/env bash
# ==============================================================================
# Script de création d'un paquet autonome AppImage pour IPTV Hub
# À exécuter sur une machine Linux (Ubuntu 20.04/22.04 recommandée pour compatibilité maximale)
# ==============================================================================

set -e

APP_NAME="IPTV_Hub"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$SRC_DIR/build_appimage"
APP_DIR="$BUILD_DIR/AppDir"
OUT_DIR="$SRC_DIR/dist_installer"

echo "=== Création du paquet AppImage IPTV Hub ==="

mkdir -p "$BUILD_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/share/applications"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$OUT_DIR"

# 1. Vérification et installation de PyInstaller si absent
echo "1. Vérification des outils de compilation..."
if command -v pyinstaller &>/dev/null; then
    PYINSTALLER="pyinstaller"
elif [ -f "$SRC_DIR/venv/bin/pyinstaller" ]; then
    PYINSTALLER="$SRC_DIR/venv/bin/pyinstaller"
elif [ -f "$HOME/.local/share/iptv-hub/venv/bin/pyinstaller" ]; then
    PYINSTALLER="$HOME/.local/share/iptv-hub/venv/bin/pyinstaller"
else
    echo "Installation de PyInstaller..."
    python3 -m pip install pyinstaller --quiet || pip install pyinstaller --quiet
    PYINSTALLER="pyinstaller"
fi

echo "Compilation de l'exécutable Linux avec PyInstaller..."
cd "$SRC_DIR"
"$PYINSTALLER" build.spec --noconfirm --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/build"

# Copie de l'arborescence PyInstaller dans AppDir/usr/bin
cp -rf "$BUILD_DIR/dist/IPTV_Hub/"* "$APP_DIR/usr/bin/"

# 2. Métadonnées du bureau et icônes
cp "$SRC_DIR/scripts/iptv-hub.desktop" "$APP_DIR/iptv-hub.desktop"
cp "$SRC_DIR/scripts/iptv-hub.desktop" "$APP_DIR/usr/share/applications/iptv-hub.desktop"
cp "$SRC_DIR/assets/logo.png" "$APP_DIR/iptv-hub.png"
cp "$SRC_DIR/assets/logo.png" "$APP_DIR/usr/share/icons/hicolor/256x256/apps/iptv-hub.png"

# 3. AppRun (Point d'entrée de l'AppImage)
cat << 'EOF' > "$APP_DIR/AppRun"
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export LC_NUMERIC="C"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${HERE}/usr/bin/lib:${LD_LIBRARY_PATH}"
export PYTHONHOME="${HERE}/usr/bin"
exec "${HERE}/usr/bin/IPTV_Hub" "$@"
EOF
chmod +x "$APP_DIR/AppRun"

# 4. Téléchargement d'appimagetool si absent (avec extraction pour contourner le besoin de FUSE sous Ubuntu 22.04+)
if ! command -v appimagetool &>/dev/null; then
    if [ ! -f "$BUILD_DIR/appimagetool" ]; then
        echo "Téléchargement d'appimagetool..."
        wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O "$BUILD_DIR/appimagetool"
        chmod +x "$BUILD_DIR/appimagetool"
    fi

    # Extraction pour fonctionner même sans libfuse2 (courant sur Ubuntu 22.04/24.04/Zorin OS 17)
    if [ ! -d "$BUILD_DIR/squashfs-root" ]; then
        echo "Préparation d'appimagetool..."
        cd "$BUILD_DIR"
        ./appimagetool --appimage-extract >/dev/null 2>&1 || true
        cd "$SRC_DIR"
    fi

    if [ -f "$BUILD_DIR/squashfs-root/AppRun" ]; then
        APPIMAGETOOL="$BUILD_DIR/squashfs-root/AppRun"
    else
        APPIMAGETOOL="$BUILD_DIR/appimagetool"
    fi
else
    APPIMAGETOOL="appimagetool"
fi

# 5. Génération du paquet .AppImage final
echo "Génération de l'AppImage finale..."
ARCH=x86_64 "$APPIMAGETOOL" "$APP_DIR" "$OUT_DIR/IPTV_Hub-x86_64.AppImage"
chmod +x "$OUT_DIR/IPTV_Hub-x86_64.AppImage"

echo "=== AppImage créée avec succès : $OUT_DIR/IPTV_Hub-x86_64.AppImage ==="
