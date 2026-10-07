"""
Point d'entrée principal de l'application IPTV Hub (Qt6 + libmpv).
Configure l'AppUserModelID Windows pour un épinglage parfait dans la barre des tâches.
"""

import sys
import ctypes
import locale
from pathlib import Path

# Fix impératif pour libmpv sous Linux :
# libmpv exige que LC_NUMERIC soit en "C" pour parser les nombres flottants.
# Sans cela, une erreur "Non-C locale detected... Erreur de segmentation" survient.
try:
    locale.setlocale(locale.LC_NUMERIC, "C")
except Exception:
    pass

# Fix pour la barre des tâches Windows : enregistre l'AppUserModelID
if sys.platform == "win32":
    try:
        app_id = "iptvhub.player.desktop.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

# Ajout du dossier racine au PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.mpv_setup import setup_mpv_environment  # noqa: E402

# Initialisation précoce de l'environnement libmpv (PATH et add_dll_directory)
# AVANT l'import de MainWindow (qui importe core.player_controller -> mpv)
setup_mpv_environment()

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402

from ui.theme import apply_theme  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.icons import get_app_logo_icon, prewarm_pixmap_cache  # noqa: E402


def _install_crash_guard():
    """Filet de sécurité contre les fermetures brutales sans trace.

    PyQt transforme toute exception Python non gérée dans un slot en appel à
    Qt's qFatal() -> abort() : l'application se ferme alors d'un coup avec un
    code natif 0xc0000409 (Qt6Core.dll), sans aucun message (console désactivée
    en production). Un hook d'exception installé par l'application est prioritaire
    sur ce comportement : on journalise donc la trace complète sur disque (et sur
    stderr si présent) au lieu de laisser l'application mourir silencieusement.

    Les fautes NATIVES sont confiées à ``core.native_crash_log`` : c'est un
    gestionnaire d'exceptions vectorisé qui journalise sans jamais parcourir les
    trames Python. ``faulthandler.enable()`` est volontairement proscrit (voir le
    module) : sur Windows il vidait les piles de tous les threads à chaque
    exception SEH levée par libmpv, ce qui finissait par faire planter
    l'interpréteur lui-même.
    """
    import os
    import threading
    import traceback
    from datetime import datetime

    from core.native_crash_log import install_native_crash_log

    base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    log_dir = os.path.join(base_dir, "IPTV_Hub")
    log_path = os.path.join(log_dir, "iptv_errors.log")

    stream = None
    try:
        os.makedirs(log_dir, exist_ok=True)
        stream = open(log_path, "a", encoding="utf-8", buffering=1)
        # Fautes natives : VEH minimaliste (voir core/native_crash_log.py).
        # Ne JAMAIS utiliser faulthandler.enable() ici : sur Windows il vide les
        # piles Python de tous les threads à chaque exception SEH, or libmpv en
        # lève en permanence (0xE24C4A02) pendant ses appels d'API ; ce vidage
        # finissait par violer l'accès dans python313.dll, au cœur du code
        # d'affichage des traces de CPython (crashs 19h33, 19h34, 19h47, 19h48).
        install_native_crash_log(log_path, stream=stream)
    except Exception:
        stream = None

    def _write(text: str):
        if stream is not None:
            try:
                stream.write(text)
                stream.flush()
            except Exception:
                pass
        try:
            sys.stderr.write(text)
        except Exception:
            pass

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        _write(
            "\n===== " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            + " : exception non gérée (évitée : aurait tué l'application) =====\n"
            + "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        )

    sys.excepthook = _hook

    def _thread_hook(args):
        _hook(args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = _thread_hook


def main():

    # Journalisation des erreurs fatales (évite les crashs muets 0xc0000409)
    _install_crash_guard()

    # Configuration Qt pour le rendu haute densité (HiDPI)
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("IPTV Hub")
    app.setOrganizationName("IPTVHub")

    # Définition de l'icône globale de l'application pour la barre des tâches Windows
    app.setWindowIcon(get_app_logo_icon())

    # Application du thème sombre moderne (style IPTVnator)
    apply_theme(app)

    # Pré-chauffage du cache d'icônes -----------------------------------------
    # QSvgRenderer.render() exécuté PENDANT un paintEvent corrompt la mémoire
    # (crash aléatoire au premier affichage de la grille VOD). On pré-rend donc
    # toutes les combinaisons icône × couleur ici, hors de tout paintEvent.
    prewarm_pixmap_cache()

    # Lancement de la fenêtre principale
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
