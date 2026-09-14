import sys
import os
import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.models import Channel
from ui.widgets.movie_details_view import MovieDetailsView
from ui.widgets.series_details_view import SeriesDetailsView, EpisodeCardWidget


class TestDetailsCursors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from unittest.mock import patch
        self._patcher1 = patch("ui.widgets.movie_details_view._TrailerLookupWorker")
        self._patcher2 = patch("ui.widgets.series_details_view._SeriesTrailerLookupWorker")
        self._patcher3 = patch("ui.widgets.series_details_view.SeriesInfoWorker")
        self._patcher1.start()
        self._patcher2.start()
        self._patcher3.start()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self._patcher1.stop()
        self._patcher2.stop()
        self._patcher3.stop()
        self.temp_dir.cleanup()

    def test_movie_details_view_cursors(self):
        """Vérifie que MovieDetailsView n'a la main (PointingHandCursor) que sur les zones cliquables."""
        view = MovieDetailsView(self.db)
        ch = Channel(id=1, name="Film Test", stream_type="movie", stream_url="http://s/1.mkv")
        view.load_movie(ch)

        # 1. Zones non cliquables -> Flèche (ArrowCursor)
        self.assertEqual(view.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.scroll.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.scroll.viewport().cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.scroll_content.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.card_frame.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.poster_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.title_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.details_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.synopsis_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.trailer_section.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.trailer_name_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.reviews_section.cursor().shape(), Qt.CursorShape.ArrowCursor)

        # 2. Zones cliquables -> Main (PointingHandCursor)
        self.assertEqual(view.back_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.play_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.restart_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.clear_resume_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.fav_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.download_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.trailer_thumb_label.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.play_trailer_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.open_youtube_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)

    def test_series_details_view_cursors(self):
        """Vérifie que SeriesDetailsView n'a la main (PointingHandCursor) que sur les boutons interactifs."""
        view = SeriesDetailsView(self.db)
        ch = Channel(id=2, name="Série Test", stream_type="series", stream_url="http://s/series/2")
        view.load_series(ch)

        # 1. Zones non cliquables -> Flèche (ArrowCursor)
        self.assertEqual(view.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.scroll_area.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.scroll_area.viewport().cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.content_widget.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.hero_banner.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.poster_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.title_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.badge_year.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.badge_genre.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.badge_duration.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.badge_rating.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.plot_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.cast_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.director_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.seasons_container.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.trailer_section.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(view.trailer_name_label.cursor().shape(), Qt.CursorShape.ArrowCursor)

        # 2. Zones cliquables -> Main (PointingHandCursor)
        self.assertEqual(view.back_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.resume_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.fav_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.trailer_thumb_label.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.play_trailer_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.open_youtube_btn.cursor().shape(), Qt.CursorShape.PointingHandCursor)

    def test_episode_card_widget_cursors(self):
        """Vérifie que EpisodeCardWidget n'a le curseur main QUE sur la vignette et le titre."""
        ep = {
            "episode_num": 1,
            "title": "Épisode 1",
            "info": {"plot": "Description longue", "duration": "42m"}
        }
        card = EpisodeCardWidget(ep, season_num="1")

        # La carte globale doit avoir la flèche
        self.assertEqual(card.cursor().shape(), Qt.CursorShape.ArrowCursor)

        # Zones cliquables : vignette (pour lancer/cocher) et titre
        self.assertEqual(card.thumb_container.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(card.title_label.cursor().shape(), Qt.CursorShape.PointingHandCursor)

        # Zones non cliquables : synopsis, durée, barre de progression
        self.assertEqual(card.plot_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(card.dur_label.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(card.progress_bar.cursor().shape(), Qt.CursorShape.ArrowCursor)

    def test_movie_trailer_hidden_during_playback(self):
        """Vérifie que la section bande-annonce d'un film est masquée pendant la lecture et réaffichée après."""
        from PyQt6.QtWidgets import QWidget
        view = MovieDetailsView(self.db)
        ch = Channel(id=1, name="Film Test", stream_type="movie", stream_url="http://s/1.mkv")
        view.load_movie(ch)
        view._setup_trailer("abc123xyz")
        self.assertFalse(view.trailer_section.isHidden())

        dummy_player = QWidget()
        view.attach_video_widget(dummy_player)
        self.assertTrue(view.trailer_section.isHidden())

        view.detach_video_widget()
        self.assertFalse(view.trailer_section.isHidden())

    def test_series_trailer_hidden_during_playback(self):
        """Vérifie que la section bande-annonce d'une série est masquée pendant la lecture et réaffichée après."""
        from PyQt6.QtWidgets import QWidget
        view = SeriesDetailsView(self.db)
        ch = Channel(id=2, name="Série Test", stream_type="series", stream_url="http://s/series/2")
        view.load_series(ch)
        view._setup_trailer("series123xyz")
        self.assertFalse(view.trailer_section.isHidden())

        dummy_player = QWidget()
        view.attach_video_widget(dummy_player)
        self.assertTrue(view.trailer_section.isHidden())

        view.detach_video_widget()
        self.assertFalse(view.trailer_section.isHidden())


if __name__ == "__main__":
    unittest.main()
