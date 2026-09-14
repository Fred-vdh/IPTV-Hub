import sys
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.models import AppSettings, Channel, Playlist
from ui.main_window import MainWindow


class TestRefreshPlaylistNoScreenChange(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.db = Database(self.db_path)
        self.pl = Playlist(id=1, name="Test PL", playlist_type="xtream", server_url="http://s", username="u", password="p")
        self.db.add_playlist(self.pl)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_refresh_during_series_details_playback_does_not_change_screen(self):
        """Vérifie que rafraîchir la liste pendant la lecture d'une série dans sa fiche ne change pas d'écran."""
        win = MainWindow.__new__(MainWindow)
        win.db = self.db
        win.settings = AppSettings()
        win.current_section = "series"

        # Simuler un épisode en cours de lecture dans la fiche série (index 3)
        win.content_stack = MagicMock()
        win.content_stack.currentIndex.return_value = 0

        win.main_content_stack = MagicMock()
        win.main_content_stack.currentIndex.return_value = 3  # Fiche série détaillée

        win.current_channel = Channel(id=10, name="Ep 1", stream_type="series")
        win._is_playing_series_in_details = True
        win.player_controller = MagicMock()
        win.player_controller._current_state = "playing"

        win.categories_panel = MagicMock()
        win.categories_panel._current_selected_cat = "Toutes les séries"
        win.series_grid_view = MagicMock()

        # Appel du rafraîchissement
        win._refresh_active_views_data(1)

        # Vérification formelle : setCurrentIndex ne doit JAMAIS avoir été appelé pour changer d'écran
        win.content_stack.setCurrentIndex.assert_not_called()
        win.main_content_stack.setCurrentIndex.assert_not_called()
        win.series_grid_view.set_playlist_and_category.assert_not_called()


if __name__ == "__main__":
    unittest.main()
