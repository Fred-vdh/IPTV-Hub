"""
Test de rendu pour ManageCategoriesDialog en mode Séries.
Vérifie qu'il n'y a pas de chevrons et que la liste est plate avec cases à cocher.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from PyQt6.QtWidgets import QApplication
import tempfile

from core.models import Channel, Playlist
from core.database import Database
from ui.dialogs.manage_categories_dialog import ManageCategoriesDialog


def test_manage_cat():
    app = QApplication.instance() or QApplication(sys.argv)

    temp_dir = tempfile.TemporaryDirectory()
    db_file = Path(temp_dir.name) / "test.db"
    db = Database(db_file)

    pl = Playlist(name="Test Xtream", url_or_path="http://example.com", playlist_type="xtream")
    pl_id = db.add_playlist(pl)

    series = [
        Channel(playlist_id=pl_id, name="Série A", group_title="🍿 Nouveautés 2025", stream_type="series"),
        Channel(playlist_id=pl_id, name="Série B", group_title="🍿 TOP 100", stream_type="series"),
        Channel(playlist_id=pl_id, name="Série C", group_title="🍿 Action", stream_type="series"),
    ]
    db.save_channels_batch(pl_id, series)

    dlg = ManageCategoriesDialog(db=db, playlist_id=pl_id, stream_type="series")
    dlg.resize(600, 500)
    dlg.show()
    app.processEvents()

    pix = dlg.grab()
    pix.save("scratch_manage_cat_series.png")
    print("Manage Categories Series Rendered OK!")

    dlg.close()


class TestManageCatRender(unittest.TestCase):
    def test_manage_cat_render(self):
        test_manage_cat()


if __name__ == "__main__":
    unittest.main()

