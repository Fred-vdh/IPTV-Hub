#!/usr/bin/env bash
# ==============================================================================
# Script de désinstallation propre pour IPTV Hub sous Linux
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}"
echo "======================================================================"
echo "            Désinstallation de IPTV Hub pour Linux                   "
echo "======================================================================"
echo -e "${NC}"

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/iptv-hub"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/applications/io.github.iptvhub.desktop"
ICON_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps/iptv-hub.png"
PIXMAP_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/pixmaps/iptv-hub.png"

echo "Suppression des composants du programme..."

# 1. Raccourcis exécutables
rm -f "$BIN_DIR/iptv-hub" /usr/local/bin/iptv-hub 2>/dev/null || true

# 2. Raccourcis .desktop (Menu et Bureau)
rm -f "${REAL_HOME:-$HOME}/.local/share/applications/iptv-hub.desktop" 2>/dev/null || true
rm -f "${REAL_HOME:-$HOME}/.local/share/applications/io.github.iptvhub.desktop" 2>/dev/null || true
rm -f "${REAL_HOME:-$HOME}/Bureau/iptv-hub.desktop" 2>/dev/null || true
rm -f "${REAL_HOME:-$HOME}/Desktop/iptv-hub.desktop" 2>/dev/null || true
rm -f /usr/share/applications/iptv-hub.desktop 2>/dev/null || true

# 3. Icônes
rm -f "$ICON_FILE" "$PIXMAP_FILE" "${REAL_HOME:-$HOME}/.icons/iptv-hub.png" /usr/share/pixmaps/iptv-hub.png 2>/dev/null || true

# 4. Fichiers du programme
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "✓ Dossier du programme $INSTALL_DIR supprimé."
fi

# Mise à jour des caches système
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null || true
fi

# 5. Question facultative pour les données utilisateur
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/IPTV_Hub"
LEGACY_DIR="$HOME/.iptv_hub"

if [ -d "$DATA_DIR" ] || [ -d "$LEGACY_DIR" ]; then
    echo ""
    echo -e "${YELLOW}Voulez-vous également supprimer vos données utilisateur (playlists, favoris, historique) ? [o/N]${NC}"
    read -r CONFIRM || CONFIRM="n"
    if [[ "$CONFIRM" =~ ^[oOyY] ]]; then
        rm -rf "$DATA_DIR" "$LEGACY_DIR"
        echo -e "${GREEN}✓ Données utilisateur supprimées.${NC}"
    else
        echo -e "Vos données ont été conservées."
    fi
fi

echo -e "\n${GREEN}Désinstallation terminée avec succès.${NC}\n"
