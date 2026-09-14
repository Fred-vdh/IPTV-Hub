"""
Module de détection et d'initialisation de libmpv pour Windows/Linux/macOS.
Télécharge automatiquement mpv-2.dll si nécessaire sous Windows.
"""

import os
import sys
import json
import urllib.request
import subprocess
import shutil
from pathlib import Path


def get_lib_dir() -> Path:
    """Retourne le chemin vers le dossier lib local au projet ou bundle."""
    if getattr(sys, "frozen", False):
        # 1. Vérifier si les DLLs sont dans _MEIPASS / lib ou _MEIPASS
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_lib = Path(meipass) / "lib"
            if meipass_lib.exists():
                return meipass_lib
            if (Path(meipass) / "libmpv-2.dll").exists() or (Path(meipass) / "mpv-2.dll").exists():
                return Path(meipass)

        # 2. Vérifier à côté de l'exécutable
        exe_dir = Path(sys.executable).parent
        exe_lib = exe_dir / "lib"
        if exe_lib.exists():
            return exe_lib
        return exe_dir
    else:
        base_dir = Path(__file__).resolve().parent.parent
        lib_dir = base_dir / "lib"
        lib_dir.mkdir(exist_ok=True)
        return lib_dir


def is_mpv_available() -> bool:
    """Vérifie si libmpv est disponible dans le système, le bundle ou ./lib."""
    if sys.platform != "win32":
        import ctypes.util
        if ctypes.util.find_library("mpv"):
            return True
        lib_dir = get_lib_dir()
        for name in ["libmpv.so.2", "libmpv.so.1", "libmpv.so", "libmpv.dylib"]:
            if (lib_dir / name).exists():
                return True
            try:
                import ctypes
                ctypes.CDLL(name)
                return True
            except OSError:
                pass
        return False

    lib_dir = get_lib_dir()
    for dll_name in ["mpv-2.dll", "mpv-1.dll", "libmpv-2.dll"]:
        if (lib_dir / dll_name).exists():
            return True

    # Vérification à côté du .exe si mode gelé
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for dll_name in ["mpv-2.dll", "mpv-1.dll", "libmpv-2.dll"]:
            if (exe_dir / dll_name).exists() or (exe_dir / "lib" / dll_name).exists():
                return True

    # Vérification dans PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for p in path_dirs:
        for dll_name in ["mpv-2.dll", "mpv-1.dll", "libmpv-2.dll"]:
            if (Path(p) / dll_name).exists():
                return True
    return False


def download_mpv_windows(callback=None) -> bool:
    """Télécharge la version x86_64 de libmpv pour Windows depuis GitHub."""
    lib_dir = get_lib_dir()
    temp_archive = lib_dir / "mpv-dev.7z"

    api_url = "https://api.github.com/repos/zhongfly/mpv-winbuild/releases/latest"
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    try:
        if callback:
            callback("Recherche de la dernière version de libmpv...")
        with urllib.request.urlopen(req, timeout=15) as response:
            release_data = json.loads(response.read().decode("utf-8"))

        download_url = None
        for asset in release_data.get("assets", []):
            name = asset.get("name", "")
            # On cherche mpv-dev-x86_64-...7z (mais pas v3 ni lgpl ni aarch64 pour compatibilité standard)
            if name.startswith("mpv-dev-x86_64-") and not name.startswith("mpv-dev-x86_64-v3-") and name.endswith(".7z"):
                download_url = asset.get("browser_download_url")
                break

        if not download_url:
            # Fallback
            for asset in release_data.get("assets", []):
                name = asset.get("name", "")
                if "mpv-dev-x86_64" in name and name.endswith(".7z"):
                    download_url = asset.get("browser_download_url")
                    break

        if not download_url:
            raise RuntimeError("Impossible de trouver l'archive libmpv Windows x86_64 sur GitHub.")

        if callback:
            callback(f"Téléchargement de libmpv depuis {download_url}...")

        # Téléchargement
        dl_req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(dl_req, timeout=60) as resp, open(temp_archive, "wb") as out_file:
            shutil.copyfileobj(resp, out_file)

        if callback:
            callback("Extraction de mpv-2.dll...")

        # Extraction avec tar.exe de Windows
        extract_cmd = ["tar.exe", "-xf", str(temp_archive), "-C", str(lib_dir)]
        res = subprocess.run(extract_cmd, capture_output=True, text=True)

        if temp_archive.exists():
            temp_archive.unlink()

        if res.returncode != 0:
            raise RuntimeError(f"Erreur lors de l'extraction tar: {res.stderr}")

        if callback:
            callback("libmpv installé avec succès !")
        return True

    except Exception as e:
        print(f"Erreur lors du téléchargement de libmpv: {e}", file=sys.stderr)
        if temp_archive.exists():
            try:
                temp_archive.unlink()
            except Exception:
                pass
        return False


def is_ytdlp_available() -> bool:
    """Vérifie si yt-dlp est disponible dans le système, le bundle ou ./lib."""
    lib_dir = get_lib_dir()
    for name in ["yt-dlp.exe", "yt-dlp"]:
        if (lib_dir / name).exists():
            return True

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        for name in ["yt-dlp.exe", "yt-dlp"]:
            if (exe_dir / name).exists() or (exe_dir / "lib" / name).exists():
                return True

    scripts_dir = Path(sys.prefix) / "Scripts"
    if (scripts_dir / "yt-dlp.exe").exists() or (scripts_dir / "yt-dlp").exists():
        return True

    if shutil.which("yt-dlp"):
        return True

    return False


def download_ytdlp_windows(callback=None) -> bool:
    """Télécharge l'exécutable autonome yt-dlp.exe pour Windows."""
    lib_dir = get_lib_dir()
    dest_exe = lib_dir / "yt-dlp.exe"
    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

    try:
        if callback:
            callback("Téléchargement de yt-dlp pour les bandes-annonces YouTube...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest_exe, "wb") as out_file:
            shutil.copyfileobj(resp, out_file)
        if callback:
            callback("yt-dlp installé avec succès !")
        return True
    except Exception as e:
        print(f"Erreur lors du téléchargement de yt-dlp: {e}", file=sys.stderr)
        return False


def setup_mpv_environment():
    """Configure l'environnement d'exécution pour que python-mpv trouve la DLL et yt-dlp."""
    if sys.platform == "win32":
        lib_dir = get_lib_dir()
        if not is_mpv_available():
            print("libmpv n'a pas été trouvé. Téléchargement automatique en cours...")
            success = download_mpv_windows(callback=print)
            if not success:
                print("ATTENTION: Échec du téléchargement automatique de libmpv.", file=sys.stderr)

        if not is_ytdlp_available():
            print("yt-dlp n'a pas été trouvé. Téléchargement automatique en cours...")
            download_ytdlp_windows(callback=print)

        # Ajout du dossier lib, du dossier _internal et du dossier exécutable au PATH
        lib_str = str(lib_dir.resolve())
        scripts_dir = Path(sys.prefix) / "Scripts"
        scripts_str = str(scripts_dir.resolve()) if scripts_dir.exists() else ""

        path_elements = [lib_str]
        parent_dir = str(lib_dir.parent.resolve())
        if parent_dir not in path_elements:
            path_elements.append(parent_dir)

        if getattr(sys, "frozen", False):
            exe_dir = str(Path(sys.executable).parent.resolve())
            if exe_dir not in path_elements:
                path_elements.append(exe_dir)

        if scripts_str:
            path_elements.append(scripts_str)
        path_elements.append(os.environ.get("PATH", ""))

        os.environ["PATH"] = os.pathsep.join(path_elements)

        if hasattr(os, "add_dll_directory"):
            for d in [lib_str, parent_dir]:
                try:
                    os.add_dll_directory(d)
                except Exception as e:
                    print(f"Avertissement add_dll_directory({d}): {e}")
            if getattr(sys, "frozen", False):
                try:
                    os.add_dll_directory(str(Path(sys.executable).parent.resolve()))
                except Exception as e:
                    print(f"Avertissement add_dll_directory(exe_dir): {e}")
    else:
        # Configuration pour Linux / macOS
        path_elements = []
        local_bin = str(Path.home() / ".local" / "bin")
        if local_bin not in os.environ.get("PATH", "").split(os.pathsep):
            path_elements.append(local_bin)

        lib_dir = get_lib_dir()
        lib_str = str(lib_dir.resolve()) if lib_dir.exists() else ""
        if lib_str:
            path_elements.append(lib_str)
            # Enrichir LD_LIBRARY_PATH pour que ctypes et python-mpv trouvent la bibliothèque
            ld_path = os.environ.get("LD_LIBRARY_PATH", "")
            if lib_str not in ld_path.split(os.pathsep):
                os.environ["LD_LIBRARY_PATH"] = f"{lib_str}{os.pathsep}{ld_path}" if ld_path else lib_str

        if path_elements:
            path_elements.append(os.environ.get("PATH", ""))
            os.environ["PATH"] = os.pathsep.join(path_elements)

    # Requis par libmpv sous tous les systèmes pour éviter l'erreur "Non-C locale detected"
    try:
        import locale
        locale.setlocale(locale.LC_NUMERIC, "C")
    except Exception:
        pass



