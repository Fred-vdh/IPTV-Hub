#!/usr/bin/env bash
# ==============================================================================
# Script d'installation automatique pour IPTV Hub sous Linux
# Compatible avec Ubuntu, Debian, Linux Mint, Fedora, Arch Linux, Manjaro, etc.
# ==============================================================================

set -e

# Couleurs pour le terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}"
echo "======================================================================"
echo "              Installation de IPTV Hub pour Linux                    "
echo "======================================================================"
echo -e "${NC}"

# Répertoire source contenant ce script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Détection intelligente du dossier racine du paquet ou du dépôt :
# 1. Si requirements.txt est dans le même dossier que ce script (archive extraite IPTV_Hub_Linux/install.sh)
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    SRC_DIR="$SCRIPT_DIR"
# 2. Si requirements.txt est dans le dossier parent (exécution directe depuis scripts/install_linux.sh)
elif [ -f "$SCRIPT_DIR/../requirements.txt" ]; then
    SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    SRC_DIR="$SCRIPT_DIR"
fi

# Détection de l'utilisateur réel si le script a été exécuté avec sudo
if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    REAL_USER="$SUDO_USER"
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    IS_SUDO=true
else
    REAL_USER="$(whoami)"
    REAL_HOME="$HOME"
    IS_SUDO=false
fi

# Répertoires cibles utilisateur (conforme aux normes XDG)
INSTALL_DIR="${REAL_HOME}/.local/share/iptv-hub"
BIN_DIR="${REAL_HOME}/.local/bin"
DESKTOP_DIR="${REAL_HOME}/.local/share/applications"
ICON_DIR="${REAL_HOME}/.local/share/icons/hicolor/256x256/apps"
PIXMAP_DIR="${REAL_HOME}/.local/share/pixmaps"

# Détection du dossier Bureau de l'utilisateur (français ou anglais)
DESKTOP_USER_DIR=""
if [ -d "$REAL_HOME/Bureau" ]; then
    DESKTOP_USER_DIR="$REAL_HOME/Bureau"
elif [ -d "$REAL_HOME/Desktop" ]; then
    DESKTOP_USER_DIR="$REAL_HOME/Desktop"
elif command -v xdg-user-dir &>/dev/null; then
    if [ "$IS_SUDO" = true ]; then
        DESKTOP_USER_DIR="$(su - "$REAL_USER" -c "xdg-user-dir DESKTOP 2>/dev/null" || true)"
    else
        DESKTOP_USER_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    fi
fi

echo -e "Utilisateur cible          : ${BOLD}${REAL_USER}${NC}"
echo -e "Répertoire d'installation  : ${BOLD}${INSTALL_DIR}${NC}"
echo -e "Raccourci exécutable        : ${BOLD}${BIN_DIR}/iptv-hub${NC}"
if [ -n "$DESKTOP_USER_DIR" ]; then
    echo -e "Dossier du Bureau          : ${BOLD}${DESKTOP_USER_DIR}${NC}"
fi
echo ""

# ------------------------------------------------------------------------------
# 1. Vérification et aide à l'installation des dépendances système (libmpv, etc.)
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[1/5] Vérification des prérequis système...${NC}"

MISSING_PKGS=()

# Vérification de Python 3
if ! command -v python3 &>/dev/null; then
    MISSING_PKGS+=("python3")
fi

# Vérification de python3-venv et ensurepip
# Note : Sous Debian/Ubuntu, `python3 -m venv --help` réussit même si ensurepip/python3-venv est absent !
HAS_VENV=true
if ! python3 -c "import venv, ensurepip" &>/dev/null; then
    HAS_VENV=false
    MISSING_PKGS+=("python3-venv")
fi

# Vérification de pip
if ! python3 -m pip --version &>/dev/null && ! command -v pip3 &>/dev/null; then
    MISSING_PKGS+=("python3-pip")
fi

# Vérification de libmpv
HAS_LIBMPV=false
if ldconfig -p 2>/dev/null | grep -E "libmpv\.so" &>/dev/null; then
    HAS_LIBMPV=true
elif [ -f "/usr/lib/libmpv.so" ] || [ -f "/usr/lib64/libmpv.so" ] || [ -f "/usr/lib/x86_64-linux-gnu/libmpv.so.2" ] || [ -f "/usr/lib/x86_64-linux-gnu/libmpv.so.1" ]; then
    HAS_LIBMPV=true
fi

if [ "$HAS_LIBMPV" = false ]; then
    MISSING_PKGS+=("libmpv")
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Certaines dépendances système sont recommandées : ${MISSING_PKGS[*]}${NC}"
    
    # Détection du gestionnaire de paquets
    if command -v apt-get &>/dev/null; then
        PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "")
        EXTRA_VENV=""
        [ -n "$PY_VER" ] && EXTRA_VENV="python${PY_VER}-venv"
        CMD_INSTALL="sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip $EXTRA_VENV libmpv-dev libmpv2 yt-dlp"
    elif command -v dnf &>/dev/null; then
        CMD_INSTALL="sudo dnf install -y python3 python3-pip mpv-libs-devel yt-dlp"
    elif command -v pacman &>/dev/null; then
        CMD_INSTALL="sudo pacman -S --needed python python-pip mpv yt-dlp"
    elif command -v zypper &>/dev/null; then
        CMD_INSTALL="sudo zypper install -y python3 python3-pip mpv-devel yt-dlp"
    else
        CMD_INSTALL=""
    fi

    if [ -n "$CMD_INSTALL" ]; then
        echo -e "Voulez-vous que le script installe les paquets manquants maintenant ? (nécessite sudo) [O/n]"
        read -r -t 15 CONFIRM || CONFIRM="o"
        if [[ "$CONFIRM" =~ ^[oOyY]|^$ ]]; then
            echo -e "${BLUE}Exécution : $CMD_INSTALL${NC}"
            eval "$CMD_INSTALL" || echo -e "${RED}Avertissement : installation automatique incomplète. Poursuite de l'installation...${NC}"
        else
            echo -e "${YELLOW}Assurez-vous que libmpv et python3-venv sont bien installés manuellement.${NC}"
        fi
    fi
else
    echo -e "${GREEN}✓ Tous les prérequis système sont présents.${NC}"
fi

# ------------------------------------------------------------------------------
# 2. Déploiement des fichiers de l'application
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/5] Déploiement des fichiers de l'application...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DIR"

# Vérification que la source est valide
if [ ! -f "$SRC_DIR/requirements.txt" ] || [ ! -f "$SRC_DIR/main.py" ]; then
    echo -e "${RED}Erreur : Les fichiers d'installation d'IPTV Hub (requirements.txt, main.py) sont introuvables.${NC}"
    echo -e "${YELLOW}Dossier source examiné : $SRC_DIR${NC}"
    exit 1
fi

# Copie propre des dossiers nécessaires
for item in core ui assets scripts main.py requirements.txt; do
    if [ -e "$SRC_DIR/$item" ]; then
        cp -rf "$SRC_DIR/$item" "$INSTALL_DIR/"
    fi
done

if [ ! -f "$INSTALL_DIR/requirements.txt" ]; then
    echo -e "${RED}Erreur : Échec lors de la copie de requirements.txt vers $INSTALL_DIR.${NC}"
    exit 1
fi

# Nettoyage des dossiers caches Python éventuels
find "$INSTALL_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$INSTALL_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

echo -e "${GREEN}✓ Fichiers copiés dans $INSTALL_DIR${NC}"

# ------------------------------------------------------------------------------
# 3. Création de l'environnement virtuel Python isolé
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/5] Configuration de l'environnement virtuel Python...${NC}"
VENV_DIR="$INSTALL_DIR/venv"

# Si un dossier venv existe mais est incomplet ou sans pip fonctionnel, on le réinitialise
if [ -d "$VENV_DIR" ]; then
    if [ ! -f "$VENV_DIR/bin/python" ] || ! "$VENV_DIR/bin/python" -m pip --version &>/dev/null; then
        echo -e "${YELLOW}Environnement virtuel incomplet ou sans pip détecté, réinitialisation...${NC}"
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo -e "Création de l'environnement virtuel..."
    # 1. Tentative standard avec python3 -m venv
    if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
        echo -e "${YELLOW}Création standard venv échouée (ensurepip absent). Tentative avec --without-pip...${NC}"
        python3 -m venv --without-pip "$VENV_DIR" || {
            echo -e "${RED}Erreur : Impossible de créer l'environnement virtuel avec python3.${NC}"
            echo -e "${RED}Veuillez installer le paquet python3-venv :${NC}"
            echo -e "  Ubuntu/Debian : sudo apt install -y python3-venv python3-pip"
            echo -e "  Fedora :        sudo dnf install -y python3-pip"
            echo -e "  Arch Linux :    sudo pacman -S python-pip"
            exit 1
        }
    fi
fi

# Vérification et amorçage automatique de pip dans le venv si absent
if ! "$VENV_DIR/bin/python" -m pip --version &>/dev/null; then
    echo -e "${YELLOW}Module pip absent du venv. Tentative d'amorçage via ensurepip...${NC}"
    "$VENV_DIR/bin/python" -m ensurepip --upgrade --default-pip 2>/dev/null || true
fi

# Si pip est toujours absent (ex: Debian/Ubuntu sans paquet ensurepip), téléchargement automatique de get-pip.py
if ! "$VENV_DIR/bin/python" -m pip --version &>/dev/null; then
    echo -e "${BLUE}Téléchargement de get-pip.py officiel pour initialiser pip...${NC}"
    TMP_GET_PIP="/tmp/iptv_hub_get_pip_$$.py"
    if command -v curl &>/dev/null; then
        curl -sSL https://bootstrap.pypa.io/get-pip.py -o "$TMP_GET_PIP" 2>/dev/null || true
    elif command -v wget &>/dev/null; then
        wget -qO "$TMP_GET_PIP" https://bootstrap.pypa.io/get-pip.py 2>/dev/null || true
    fi

    if [ -f "$TMP_GET_PIP" ]; then
        "$VENV_DIR/bin/python" "$TMP_GET_PIP" --no-warn-script-location --quiet 2>/dev/null || true
        rm -f "$TMP_GET_PIP"
    fi
fi

# Ultime vérification : pip est-il disponible dans le venv ?
if ! "$VENV_DIR/bin/python" -m pip --version &>/dev/null; then
    echo -e "\n${RED}${BOLD}======================================================================${NC}"
    echo -e "${RED}${BOLD}  ERREUR : Le module 'pip' n'a pas pu être installé dans le venv.     ${NC}"
    echo -e "${RED}${BOLD}======================================================================${NC}"
    echo -e "${YELLOW}Sur Ubuntu / Debian / Linux Mint, installez les paquets requis :${NC}"
    echo -e "  ${BOLD}sudo apt update && sudo apt install -y python3-venv python3-pip${NC}\n"
    echo -e "Puis relancez simplement : ${BOLD}./install.sh${NC}\n"
    exit 1
fi

echo -e "Mise à jour de pip..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet 2>/dev/null || true

echo -e "Installation des dépendances Python requises (PyQt6, aiohttp, etc.)..."
if ! "$VENV_DIR/bin/python" -m pip install -r "$INSTALL_DIR/requirements.txt"; then
    echo -e "\n${RED}${BOLD}Erreur : Échec lors de l'installation des paquets Python avec pip.${NC}"
    echo -e "${YELLOW}Vérifiez votre connexion Internet et relancez ./install.sh.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environnement virtuel et dépendances Python configurés avec succès.${NC}"

# ------------------------------------------------------------------------------
# 4. Création du lanceur exécutable
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/5] Création du lanceur exécutable...${NC}"
mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/iptv-hub"

cat << EOF > "$LAUNCHER"
#!/usr/bin/env bash
APP_DIR="$INSTALL_DIR"

# Correction impérative de la locale pour libmpv (évite l'erreur "Non-C locale detected")
export LC_NUMERIC="C"

# Inclusion du dossier lib local si présent
if [ -d "\$APP_DIR/lib" ]; then
    export LD_LIBRARY_PATH="\$APP_DIR/lib:\$LD_LIBRARY_PATH"
fi

# Exécution de l'application via son venv dédié
exec "\$APP_DIR/venv/bin/python" "\$APP_DIR/main.py" "\$@"
EOF

chmod +x "$LAUNCHER"
echo -e "${GREEN}✓ Lanceur créé : $LAUNCHER${NC}"

# ------------------------------------------------------------------------------
# 5. Intégration dans le menu des applications et sur le Bureau
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/5] Intégration dans le menu des applications et sur le Bureau...${NC}"

# A. Déploiement des icônes dans tous les dossiers standards
mkdir -p "$ICON_DIR"
mkdir -p "$PIXMAP_DIR"
mkdir -p "${REAL_HOME}/.icons"

LOGO_SOURCE="$INSTALL_DIR/assets/logo.png"
if [ -f "$LOGO_SOURCE" ]; then
    cp "$LOGO_SOURCE" "$ICON_DIR/iptv-hub.png"
    cp "$LOGO_SOURCE" "$PIXMAP_DIR/iptv-hub.png"
    cp "$LOGO_SOURCE" "${REAL_HOME}/.icons/iptv-hub.png"
    if [ "$IS_SUDO" = true ]; then
        mkdir -p /usr/share/pixmaps
        cp "$LOGO_SOURCE" /usr/share/pixmaps/iptv-hub.png 2>/dev/null || true
    fi
fi

# B. Création du fichier .desktop conforme aux spécifications XDG & GNOME / Zorin OS
mkdir -p "$DESKTOP_DIR"
DESKTOP_FILE="$DESKTOP_DIR/iptv-hub.desktop"

# Nettoyage préalable de l'ancien nom pour éviter le doublon d'affichage dans le menu
rm -f "$DESKTOP_DIR/io.github.iptvhub.desktop" 2>/dev/null || true
if [ "$IS_SUDO" = true ]; then
    rm -f /usr/share/applications/io.github.iptvhub.desktop 2>/dev/null || true
fi

cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=IPTV Hub
GenericName=Lecteur IPTV
GenericName[fr]=Lecteur IPTV
Comment=Lecteur moderne de télévision en direct, films et séries IPTV (Qt6 + libmpv)
Comment[fr]=Lecteur moderne de télévision en direct, films et séries IPTV (Qt6 + libmpv)
Exec="$LAUNCHER"
Icon=$LOGO_SOURCE
Terminal=false
Categories=AudioVideo;Video;Player;TV;
Keywords=iptv;tv;m3u;stream;player;series;movies;xtream;television;tele;video;
Keywords[fr]=iptv;tv;m3u;stream;lecteur;series;films;xtream;television;tele;video;
StartupWMClass=IPTV Hub
MimeType=x-scheme-handler/iptv;
EOF

chmod +x "$DESKTOP_FILE"

# Si exécuté avec sudo, installer aussi au niveau système pour tous les utilisateurs
if [ "$IS_SUDO" = true ]; then
    mkdir -p /usr/share/applications
    cp "$DESKTOP_FILE" /usr/share/applications/iptv-hub.desktop 2>/dev/null || true
    ln -sf "$LAUNCHER" /usr/local/bin/iptv-hub 2>/dev/null || true
fi

# C. Création du raccourci sur le Bureau (Desktop / Bureau)
if [ -n "$DESKTOP_USER_DIR" ] && [ -d "$DESKTOP_USER_DIR" ]; then
    DESKTOP_SHORTCUT="$DESKTOP_USER_DIR/iptv-hub.desktop"
    cp "$DESKTOP_FILE" "$DESKTOP_SHORTCUT"
    chmod +x "$DESKTOP_SHORTCUT"

    if [ "$IS_SUDO" = true ]; then
        chown "$REAL_USER:$REAL_USER" "$DESKTOP_SHORTCUT" 2>/dev/null || true
        su - "$REAL_USER" -c "gio set \"$DESKTOP_SHORTCUT\" metadata::trusted true 2>/dev/null" || true
    else
        gio set "$DESKTOP_SHORTCUT" metadata::trusted true 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ Raccourci créé sur le Bureau : $DESKTOP_SHORTCUT${NC}"
fi

# Rétablir les permissions utilisateur si sudo a été utilisé
if [ "$IS_SUDO" = true ]; then
    chown -R "$REAL_USER:$REAL_USER" "$INSTALL_DIR" "$BIN_DIR/iptv-hub" "$DESKTOP_DIR" "$ICON_DIR" "$PIXMAP_DIR" "${REAL_HOME}/.icons" 2>/dev/null || true
fi

# D. Rafraîchissement des bases de données desktop et icônes
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    if [ "$IS_SUDO" = true ]; then
        update-desktop-database /usr/share/applications 2>/dev/null || true
    fi
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "${REAL_HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

# Forcer le rafraîchissement d'horodatage pour GLib / GNOME Shell / Zorin Menu
touch "$DESKTOP_DIR"
touch "$DESKTOP_FILE"

echo -e "${GREEN}✓ Entrées de menu créées dans $DESKTOP_DIR${NC}"

# Vérifier si ~/.local/bin est dans le PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\n${YELLOW}Note : Pour lancer 'iptv-hub' directement dans votre terminal, assurez-vous que $BIN_DIR est dans votre PATH :${NC}"
    echo -e "  echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.bashrc"
fi

echo -e "\n${GREEN}${BOLD}======================================================================${NC}"
echo -e "${GREEN}${BOLD}             IPTV Hub a été installé avec succès !                   ${NC}"
echo -e "${GREEN}${BOLD}======================================================================${NC}"
echo -e "Vous pouvez maintenant le lancer depuis le menu de vos applications"
echo -e "ou en tapant directement : ${BOLD}iptv-hub${NC}\n"
