"""
Test d'initialisation et d'intégration de l'interface graphique Qt6.
"""

import unittest
import sys
import tempfile
import os
from PyQt6.QtWidgets import QApplication

from core.mpv_setup import setup_mpv_environment

setup_mpv_environment()

from core.database import Database  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.dialogs.add_playlist import AddPlaylistDialog  # noqa: E402
from ui.dialogs.settings_dialog import SettingsDialog  # noqa: E402


class TestGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QApplication.instance() is None:
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_main_window_init(self):
        # Création et affichage de la fenêtre principale
        window = MainWindow()
        self.assertIsNotNone(window)
        self.assertEqual(window.windowTitle(), "IPTV Hub — Lecteur Moderne")

        # Vérification des composants
        self.assertIsNotNone(window.sidebar)
        self.assertIsNotNone(window.channel_panel)
        self.assertIsNotNone(window.video_widget)
        self.assertIsNotNone(window.player_controller)

        # Simulation bascule plein écran
        window.toggle_fullscreen()
        self.assertTrue(window.is_fullscreen)
        window._last_fullscreen_toggle_time = 0.0
        window.toggle_fullscreen()
        self.assertFalse(window.is_fullscreen)

        # Nettoyage
        window.close()

    def test_dialogs_init(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "dialog_test.db")
        db = Database(db_path)

        add_dlg = AddPlaylistDialog(db)
        self.assertIsNotNone(add_dlg)
        self.assertEqual(add_dlg.windowTitle(), "Ajouter une liste de lecture")

        settings_dlg = SettingsDialog(db)
        self.assertIsNotNone(settings_dlg)
        self.assertEqual(settings_dlg.windowTitle(), "Paramètres")

        temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
