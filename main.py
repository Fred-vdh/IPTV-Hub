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
from ui.icons import get_app_logo_icon  # noqa: E402


def main():

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

    # Lancement de la fenêtre principale
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
