#!/usr/bin/env python3
"""
Script de packaging pour la distribution Linux d'IPTV Hub.
Génère l'archive distribuable 'dist_installer/IPTV_Hub_Linux.tar.gz' prête à l'emploi.
"""

import os
import tarfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DIST_INSTALLER = ROOT_DIR / "dist_installer"
DIST_INSTALLER.mkdir(parents=True, exist_ok=True)
ARCHIVE_PATH = DIST_INSTALLER / "IPTV_Hub_Linux.tar.gz"

README_CONTENT = """# IPTV Hub pour Linux

IPTV Hub est compatible avec toutes les distributions Linux modernes (Ubuntu, Debian, Linux Mint, Fedora, Arch Linux, Manjaro, openSUSE, etc.).

## Prérequis (selon votre distribution)

Sous **Ubuntu / Debian / Linux Mint** :
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip libmpv-dev libmpv2
```

Sous **Fedora** :
```bash
sudo dnf install -y python3 python3-pip mpv-libs-devel
```

Sous **Arch Linux / Manjaro** :
```bash
sudo pacman -S python python-pip mpv
```

## Installation rapide

Ouvrez un terminal dans ce dossier décompressé et exécutez simplement :

```bash
chmod +x install.sh
./install.sh
```

Ce script d'installation automatique va :
1. Vérifier et installer les prérequis système nécessaires (`libmpv`, `yt-dlp`, `python3-venv`).
2. Déployer l'application dans votre dossier utilisateur standard `~/.local/share/iptv-hub`.
3. Créer un environnement virtuel Python sécurisé et isolé.
4. Créer la commande terminal `iptv-hub` dans `~/.local/bin`.
5. Ajouter automatiquement le raccourci et le logo officiel dans le **menu des applications** de votre bureau (GNOME, KDE, Cinnamon, XFCE, etc.).

## Lancement

Après l'installation, vous pouvez lancer l'application :
- Directement depuis le menu de vos applications (catégorie *Audio & Vidéo*).
- Ou dans un terminal via la commande : `iptv-hub`

## Désinstallation

Pour désinstaller proprement l'application :
```bash
./uninstall.sh
```
(ou exécutez `~/.local/share/iptv-hub/scripts/uninstall_linux.sh`).
"""


def should_include_file(path: Path) -> bool:
    """Filtre les fichiers inutiles pour la distribution Linux."""
    parts = path.parts
    # Exclure dossiers de build Windows / caches / git
    excluded_names = {
        "__pycache__",
        ".git",
        ".gemini",
        "dist",
        "dist_installer",
        "build",
        "build_appimage",
        "tests",
        ".vscode",
        ".idea",
    }
    for p in parts:
        if p in excluded_names:
            return False

    # Exclure fichiers spécifiques Windows ou temporaires
    if path.suffix in (".exe", ".dll", ".spec", ".bak", ".log", ".iss"):
        return False
    if "CASSE" in path.name or "Copie" in path.name:
        return False
    return True


def create_linux_package():
    print("Création du paquet Linux distribuable...")

    # Dossiers et fichiers requis
    include_dirs = ["core", "ui", "assets", "scripts"]
    include_files = ["main.py", "requirements.txt"]

    # Fichiers d'installation copiés à la racine du paquet
    install_script = ROOT_DIR / "scripts" / "install_linux.sh"
    uninstall_script = ROOT_DIR / "scripts" / "uninstall_linux.sh"

    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()

    with tarfile.open(ARCHIVE_PATH, "w:gz") as tar:
        # 1. install.sh à la racine
        if install_script.exists():
            ti = tar.gettarinfo(str(install_script), arcname="IPTV_Hub_Linux/install.sh")
            ti.mode = 0o755
            with open(install_script, "rb") as f:
                tar.addfile(ti, f)

        # 2. uninstall.sh à la racine
        if uninstall_script.exists():
            ti = tar.gettarinfo(str(uninstall_script), arcname="IPTV_Hub_Linux/uninstall.sh")
            ti.mode = 0o755
            with open(uninstall_script, "rb") as f:
                tar.addfile(ti, f)

        # 3. README_LINUX.md à la racine
        readme_bytes = README_CONTENT.encode("utf-8")
        ti = tarfile.TarInfo(name="IPTV_Hub_Linux/README_LINUX.md")
        ti.size = len(readme_bytes)
        ti.mode = 0o644
        import io
        tar.addfile(ti, io.BytesIO(readme_bytes))

        # 4. Fichiers racine
        for f_name in include_files:
            f_path = ROOT_DIR / f_name
            if f_path.exists():
                ti = tar.gettarinfo(str(f_path), arcname=f"IPTV_Hub_Linux/{f_name}")
                ti.mode = 0o644
                with open(f_path, "rb") as f:
                    tar.addfile(ti, f)

        # 5. Dossiers de code et ressources
        for d_name in include_dirs:
            d_path = ROOT_DIR / d_name
            if not d_path.exists():
                continue
            for root, _, files in os.walk(d_path):
                for f in files:
                    file_path = Path(root) / f
                    if should_include_file(file_path):
                        rel = file_path.relative_to(ROOT_DIR)
                        arcname = f"IPTV_Hub_Linux/{rel.as_posix()}"
                        ti = tar.gettarinfo(str(file_path), arcname=arcname)
                        if file_path.suffix == ".sh":
                            ti.mode = 0o755
                        else:
                            ti.mode = 0o644
                        with open(file_path, "rb") as f:
                            tar.addfile(ti, f)

    size_mb = ARCHIVE_PATH.stat().st_size / (1024 * 1024)
    print(f"Archive Linux générée avec succès : {ARCHIVE_PATH} ({size_mb:.2f} Mo)")


if __name__ == "__main__":
    create_linux_package()
