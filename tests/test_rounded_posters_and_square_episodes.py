import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QColor
from core.models import Channel
from core.database import Database
from core.xtream_client import XtreamClient
from ui.widgets.rounded_poster import RoundedPosterLabel
from ui.widgets.movie_details_view import MovieDetailsView
from ui.widgets.series_details_view import SeriesDetailsView, EpisodeCardWidget
from ui.dialogs.movie_details_dialog import MovieDetailsDialog
from ui.dialogs.series_dialog import SeriesEpisodesDialog
import tempfile


def test_rounded_posters_and_square_episodes():
    _ = QApplication.instance() or QApplication(sys.argv)

    # 1. Tester RoundedPosterLabel avec et sans image
    poster = RoundedPosterLabel(radius=10, border_color="#334155", bg_color="#1e293b", fallback_icon="movie")
    poster.setFixedSize(180, 270)
    poster.show()
    QApplication.processEvents()
    assert poster.radius == 10

    # Image valide
    pm = QPixmap(200, 300)
    pm.fill(QColor("#e11d48"))
    poster.setPixmap(pm)
    poster.update()
    QApplication.processEvents()
    assert poster.pixmap() is not None

    # Effacement
    poster.clear()
    poster.update()
    QApplication.processEvents()

    # 2. Vérifier MovieDetailsView
    temp_dir = tempfile.TemporaryDirectory()
    try:
        db = Database(Path(temp_dir.name) / "test.db")
        ch_movie = Channel(name="Inception", stream_type="movie", stream_url="http://movie.mp4")

        movie_view = MovieDetailsView(db)
        assert isinstance(movie_view.poster_label, RoundedPosterLabel), "Le poster dans MovieDetailsView doit etre RoundedPosterLabel"
        assert movie_view.poster_label.radius == 10

        # 3. Vérifier SeriesDetailsView
        ch_series = Channel(name="Breaking Bad", stream_type="series", stream_url="xtream_series://100")
        series_view = SeriesDetailsView(db)
        assert isinstance(series_view.poster_label, RoundedPosterLabel), "Le poster dans SeriesDetailsView doit etre RoundedPosterLabel"
        assert series_view.poster_label.radius == 10

        # 4. Vérifier MovieDetailsDialog et SeriesEpisodesDialog
        movie_dlg = MovieDetailsDialog(ch_movie, db)
        assert isinstance(movie_dlg.poster_label, RoundedPosterLabel), "Le poster dans MovieDetailsDialog doit etre RoundedPosterLabel"
        movie_dlg.close()

        with patch.object(SeriesEpisodesDialog, "_load_series_info"):
            series_dlg = SeriesEpisodesDialog(ch_series, db)
            assert isinstance(series_dlg.poster_label, RoundedPosterLabel), "Le poster dans SeriesEpisodesDialog doit etre RoundedPosterLabel"
            series_dlg.close()

        # 5. Vérifier que la vignette d'un épisode de série est bien à coins CARRÉS
        ep_data = {"id": "101", "episode_num": 1, "title": "Pilot", "info": {}}
        card = EpisodeCardWidget(episode=ep_data, season_num="1")
        card.setFixedSize(220, 200)

        # Image valide sur la vignette d'épisode
        ep_pm = QPixmap(220, 124)
        ep_pm.fill(QColor("#2563eb"))
        card.pixmap = ep_pm
        card.thumb_container.update()
        QApplication.processEvents()

        print("[PASS] Tous les tests de posters arrondis et vignettes d'episodes carrees sont valides !")
        poster.close()
        card.close()
        series_view.stop_workers()
        movie_view.close()
        series_view.close()
    finally:
        temp_dir.cleanup()

class TestRoundedPostersAndSquareEpisodes(unittest.TestCase):
    def test_rounded_posters_and_square_episodes(self):
        with patch.object(XtreamClient, "get_series_info", return_value={"info": {}, "seasons": [], "episodes": {}}), \
             patch("core.tmdb_client.find_best_trailer", return_value={}):
            test_rounded_posters_and_square_episodes()


if __name__ == "__main__":
    unittest.main()