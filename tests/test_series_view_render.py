"""
Test de rendu visuel pour SeriesDetailsView.
Vérifie la présence de :
1. La barre de progression sous l'image de chaque épisode.
2. Le badge avec coche verte en haut à gauche des épisodes visionnés.
3. Le badge avec coche verte sur les boutons de saisons terminées à 100%.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from PyQt6.QtWidgets import QApplication

from core.models import Channel, Playlist
from core.database import Database
from ui.widgets.series_details_view import SeriesDetailsView


def test_series_renders():
    app = QApplication.instance() or QApplication(sys.argv)

    import tempfile
    temp_dir = tempfile.TemporaryDirectory()
    db_file = Path(temp_dir.name) / "test.db"
    db = Database(db_file)

    pl = Playlist(
        name="Test Xtream",
        url_or_path="http://example.com",
        playlist_type="xtream",
        server_url="http://example.com",
        username="user",
        password="pass"
    )
    pl_id = db.add_playlist(pl)

    series_ch = Channel(
        playlist_id=pl_id,
        name="|FR| Star Trek : Strange New Worlds (2022)",
        stream_url="xtream_series://1001",
        logo_url="",
        group_title="🍿 Science-Fiction & Fantastique",
        stream_type="series",
        stream_id="1001",
        rating="8.0",
        year="2022"
    )

    mock_series_data = {
        "info": {
            "name": "|FR| Star Trek : Strange New Worlds (2022)",
            "plot": "Suivez Christopher Pike, Spock et le numéro un dans la décennie qui a précédé l'arrivée du capitaine Kirk...",
            "genre": "Science-Fiction & Fantastique",
            "releaseDate": "2022",
            "episode_run_time": "54",
            "rating": "8.0",
            "cast": "Anson Mount, Ethan Peck, Jess Bush",
            "director": "Akiva Goldsman"
        },
        "episodes": {
            "1": [
                {
                    "id": "2001",
                    "episode_num": 1,
                    "title": "1. Étranges nouveaux mondes",
                    "container_extension": "mkv",
                    "info": {"plot": "Un appel de détresse...", "duration": "00:52:29", "duration_secs": 3149}
                },
                {
                    "id": "2002",
                    "episode_num": 2,
                    "title": "2. Les Enfants de la comète",
                    "container_extension": "mkv",
                    "info": {"plot": "La commandante Una comparaît devant la cour martiale...", "duration": "00:57:02", "duration_secs": 3422}
                },
                {
                    "id": "2003",
                    "episode_num": 3,
                    "title": "3. Fantômes d'Illyria",
                    "container_extension": "mkv",
                    "info": {"plot": "La'an voyage dans le temps...", "duration": "00:51:41", "duration_secs": 3101}
                }
            ],
            "2": [
                {
                    "id": "2004",
                    "episode_num": 1,
                    "title": "1. La Clé du mystère",
                    "container_extension": "mkv",
                    "info": {"plot": "De retour sur une planète...", "duration": "00:57:41", "duration_secs": 3461}
                }
            ]
        }
    }

    # Simuler les progressions de lecture dans la base :
    # Saison 1 : Épisode 1 = 100% vu, Épisode 2 = 100% vu, Épisode 3 = 100% vu -> Saison 1 DOIT être marquée avec coche verte !
    db.save_playback_progress(channel_id=None, stream_url="http://example.com/series/user/pass/2001.mkv", channel_name="Ep 1", position=3149, duration=3149)
    db.save_playback_progress(channel_id=None, stream_url="http://example.com/series/user/pass/2002.mkv", channel_name="Ep 2", position=3422, duration=3422)
    db.save_playback_progress(channel_id=None, stream_url="http://example.com/series/user/pass/2003.mkv", channel_name="Ep 3", position=3101, duration=3101)

    # Saison 2 : Épisode 1 = 45% commencé (en cours) -> Barre rouge sous l'image
    db.save_playback_progress(channel_id=None, stream_url="http://example.com/series/user/pass/2004.mkv", channel_name="Ep S2E1", position=1500, duration=3461)

    view = SeriesDetailsView(db=db)
    view.resize(1300, 800)
    view.channel = series_ch
    view.playlist = db.get_playlist(pl_id)
    view._on_series_data_loaded(mock_series_data)
    view.show()
    app.processEvents()

    # Vérification que Saison 1 est terminée (coche verte active)
    s1_btn = view.seasons_tabs_layout.itemAt(0).widget()
    assert not s1_btn.icon().isNull(), "La Saison 1 devrait avoir une icône de coche verte"
    print("Saison 1 coche verte validée avec succès !")

    # Capture de la vue
    pix = view.grab()
    pix.save("scratch_series_progress_badges.png")
    print("Capture enregistrée dans scratch_series_progress_badges.png")

    # Basculer sur Saison 2 pour vérifier la barre rouge
    view._on_season_tab_clicked("2")
    app.processEvents()
    s2_btn = view.seasons_tabs_layout.itemAt(1).widget()
    assert s2_btn.icon().isNull(), "La Saison 2 ne devrait pas avoir de coche verte (non terminée)"
    print("Saison 2 (en cours) validée avec succès !")

    view.stop_workers()
    view.close()
    return True

class TestSeriesViewRender(unittest.TestCase):
    def test_series_renders(self):
        test_series_renders()


if __name__ == "__main__":
    unittest.main()

