import sys
import os
import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.models import Playlist
from ui.dialogs.manage_playlists_dialog import PlaylistItemWidget


class TestPlaylistCardConnections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.db = Database(self.db_path)
        PlaylistItemWidget._check_account_info = lambda self: None

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_xtream_card_displays_screens_and_authorized_connections(self):
        pl = Playlist(
            id=1,
            name="Test Xtream",
            playlist_type="xtream",
            server_url="http://example.com",
            username="user",
            password="pass",
            max_connections="2",
            active_cons="0",
            account_status="Active"
        )
        self.db.add_playlist(pl)

        card = PlaylistItemWidget(pl, db=self.db, is_currently_playing=False)
        self.assertTrue(hasattr(card, "screens_badge"))
        self.assertTrue(hasattr(card, "conn_badge"))

        self.assertIn("2", card.screens_badge.text())
        self.assertIn("Écrans", card.screens_badge.text())

        self.assertIn("2", card.conn_badge.text())
        self.assertIn("Connexions autorisées", card.conn_badge.text())


if __name__ == "__main__":
    unittest.main()
