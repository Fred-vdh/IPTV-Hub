#!/usr/bin/env python3
"""
Orchestrateur de packaging et de préparation de release pour IPTV Hub.
Génère les 3 artefacts de distribution dans dist_installer/ :
  1. IPTV_Hub_Setup.exe (Inno Setup)
  2. IPTV_Hub_Portable_Win64.zip (Archive portable autonome)
  3. IPTV_Hub_Linux.tar.gz (Archive distribuable Linux avec script d'installation XDG)
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist" / "IPTV_Hub"
DIST_INSTALLER_DIR = ROOT_DIR / "dist_installer"


def copy_runtime_dlls():
    print("[1/5] Copie des DLLs runtime requises dans dist/IPTV_Hub...")
    dlls = ["vulkan-1.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll"]
    for dll in dlls:
        src = ROOT_DIR / "lib" / dll
        if src.exists():
            shutil.copy2(src, DIST_DIR / dll)
            print(f"  -> {dll} copié.")


def compile_pyinstaller():
    print("[2/5] Compilation de l'exécutable via PyInstaller...")
    cmd = ["pyinstaller", "build.spec", "--noconfirm"]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        raise RuntimeError("Échec de la compilation PyInstaller.")
    copy_runtime_dlls()
    print("  -> Exécutable IPTV_Hub.exe et dossier standalone prêts.")


def build_inno_setup_installer():
    print("[3/5] Génération de l'installateur Windows (Inno Setup)...")
    iscc_path = None
    candidates = [
        shutil.which("iscc"),
        shutil.which("ISCC"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 7" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            iscc_path = str(c)
            break

    if not iscc_path:
        raise RuntimeError("Compilateur Inno Setup (ISCC.exe) introuvable.")

    iss_file = ROOT_DIR / "installer.iss"
    cmd = [iscc_path, str(iss_file)]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        raise RuntimeError("Échec de la génération Inno Setup.")
    setup_file = DIST_INSTALLER_DIR / "IPTV_Hub_Setup.exe"
    if not setup_file.exists():
        raise FileNotFoundError(f"{setup_file} n'a pas été généré.")
    size_mb = setup_file.stat().st_size / (1024 * 1024)
    print(f"  -> Installateur créé : {setup_file.name} ({size_mb:.2f} Mo)")


def build_portable_zip():
    print("[4/5] Création de la version Portable Windows (ZIP)...")
    DIST_INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_INSTALLER_DIR / "IPTV_Hub_Portable_Win64.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(DIST_DIR):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(ROOT_DIR / "dist")
                zf.write(full_path, rel_path.as_posix())

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  -> Version portable créée : {zip_path.name} ({size_mb:.2f} Mo)")


def build_linux_package():
    print("[5/5] Création du paquet distribuable Linux (tar.gz)...")
    sys.path.insert(0, str(ROOT_DIR))
    from build_linux_package import create_linux_package
    create_linux_package()
    tar_path = DIST_INSTALLER_DIR / "IPTV_Hub_Linux.tar.gz"
    if not tar_path.exists():
        raise FileNotFoundError(f"{tar_path} introuvable.")
    size_mb = tar_path.stat().st_size / (1024 * 1024)
    print(f"  -> Paquet Linux créé : {tar_path.name} ({size_mb:.2f} Mo)")


def main():
    print("=" * 60)
    print("   Création de l'ensemble des packages de release IPTV Hub")
    print("=" * 60)
    compile_pyinstaller()
    build_inno_setup_installer()
    build_portable_zip()
    build_linux_package()
    print("=" * 60)
    print("Tous les packages ont été générés avec succès dans dist_installer/ !")
    print("=" * 60)


if __name__ == "__main__":
    main()
