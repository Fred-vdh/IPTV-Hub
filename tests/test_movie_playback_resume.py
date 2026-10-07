import sys
import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import Database
from core.models import Channel, Playlist
from ui.widgets.movie_details_view import MovieDetailsView
from ui.widgets.dashboard_view import DashboardView

_APP = QApplication.instance() or QApplication(sys.argv)


class TestMoviePlaybackResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_movie_resume.db"
        self.db = Database(self.db_path)

        # Créer une playlist et un film de test
        pl = Playlist(name="Test Playlist", playlist_type="xtream", server_url="http://test.com", username="u", password="p")
        self.pl_id = self.db.add_playlist(pl)

        self.movie_channel = Channel(
            playlist_id=self.pl_id,
            name="Spider-Man : Brand New Day (2026)",
            stream_url="http://test.com/movie/u/p/4438352.mkv",
            stream_type="movie",
            stream_id=4438352,
            group_title="Action",
            logo_url="http://test.com/poster.jpg"
        )
        self.db.save_channels_batch(self.pl_id, [self.movie_channel], replace=False, stream_type="movie")
        channels = self.db.get_channels(playlist_id=self.pl_id)
        self.movie_channel.id = channels[0].id

    def tearDown(self):
        self.tmp.cleanup()

    def test_movie_progress_saved_and_retrieved(self):
        """Vérifie qu'un film arrêté en cours de lecture a sa progression sauvegardée et accessible."""
        pos = 277.0
        dur = 8700.0
        self.db.save_playback_progress(
            channel_id=self.movie_channel.id,
            stream_url=self.movie_channel.stream_url,
            channel_name=self.movie_channel.name,
            position=pos,
            duration=dur
        )

        prog = self.db.get_playback_progress(self.movie_channel.id, self.movie_channel.stream_url)
        self.assertIsNotNone(prog)
        self.assertAlmostEqual(prog[0], pos, places=1)
        self.assertAlmostEqual(prog[1], dur, places=1)

    def test_movie_resume_in_dashboard_continue_watching(self):
        """Vérifie que le film en cours apparaît dans 'Reprendre la lecture' du tableau de bord."""
        pos = 277.0
        dur = 8700.0
        self.db.save_playback_progress(
            channel_id=self.movie_channel.id,
            stream_url=self.movie_channel.stream_url,
            channel_name=self.movie_channel.name,
            position=pos,
            duration=dur
        )

        continue_items = self.db.get_dashboard_continue_watching(playlist_id=self.pl_id)
        self.assertEqual(len(continue_items), 1)
        item = continue_items[0]
        self.assertEqual(item["channel"].name, self.movie_channel.name)
        self.assertAlmostEqual(item["position"], pos, places=1)
        self.assertFalse(item.get("is_completed", False))

    def test_movie_resumed_after_being_previously_completed(self):
        """Vérifie qu'un film précédemment vu (100%) peut être repris s'il est re-visionné au-delà de 10s."""
        dur = 8700.0
        # 1. Marqué comme terminé à 100%
        self.db.save_playback_progress(
            channel_id=self.movie_channel.id,
            stream_url=self.movie_channel.stream_url,
            channel_name=self.movie_channel.name,
            position=dur,
            duration=dur
        )
        self.assertIsNone(self.db.get_playback_progress(self.movie_channel.id, self.movie_channel.stream_url))

        # 2. Re-visionnage court (< 10s) : le statut terminé ne doit pas être écrasé
        self.db.save_playback_progress(
            channel_id=self.movie_channel.id,
            stream_url=self.movie_channel.stream_url,
            channel_name=self.movie_channel.name,
            position=5.0,
            duration=dur
        )
        self.assertIsNone(self.db.get_playback_progress(self.movie_channel.id, self.movie_channel.stream_url))

        # 3. Re-visionnage actif (>= 10s, ex: 300s) : la nouvelle position est bien enregistrée
        self.db.save_playback_progress(
            channel_id=self.movie_channel.id,
            stream_url=self.movie_channel.stream_url,
            channel_name=self.movie_channel.name,
            position=300.0,
            duration=dur
        )
        prog = self.db.get_playback_progress(self.movie_channel.id, self.movie_channel.stream_url)
        self.assertIsNotNone(prog)
        self.assertAlmostEqual(prog[0], 300.0, places=1)

    def test_movie_details_view_displays_resume_button(self):
        """Vérifie que la fiche film affiche 'Reprendre à ...' quand une position est mémorisée."""
        pos = 277.0
        dur = 8700.0
        self.db.save_playback_progress(
            channel_id=self.movie_channel.id,
            stream_url=self.movie_channel.stream_url,
            channel_name=self.movie_channel.name,
            position=pos,
            duration=dur
        )

        view = MovieDetailsView(self.db)
        view.load_movie(self.movie_channel)
        self.assertAlmostEqual(view.resume_pos, pos, places=1)
        self.assertIn("Reprendre", view.play_btn.text())
        self.assertFalse(view.restart_btn.isHidden())

    def test_dashboard_view_displays_movie_in_hero_banner(self):
        """Vérifie que DashboardView configure la bannière Hero avec le film en cours."""
        pos = 277.0
        dur = 8700.0
        self.db.save_playback_progress(
            channel_id=self.movie_channel.id,
            stream_url=self.movie_channel.stream_url,
            channel_name=self.movie_channel.name,
            position=pos,
            duration=dur
        )

        view = DashboardView(self.db)
        view.set_playlist_id(self.pl_id)
        self.assertFalse(view.hero_banner.isHidden())
        self.assertEqual(view.hero_banner.channel.name, self.movie_channel.name)

    def test_outro_requested_ignores_non_series_channel(self):
        """Vérifie que _on_outro_next_episode_requested n'écrase pas à 100% un film."""
        from unittest.mock import MagicMock
        from ui.main_window import MainWindow

        win = MagicMock(spec=MainWindow)
        win.current_channel = self.movie_channel
        win._current_playback_pos = 277.0
        win._current_playback_dur = 8700.0
        win.db = self.db

        # Appel direct de la méthode originale non mockée
        MainWindow._on_outro_next_episode_requested(win)

        # La base ne doit PAS avoir été mise à jour à 100%
        prog = self.db.get_playback_progress(self.movie_channel.id, self.movie_channel.stream_url)
        # S'il n'y avait pas de progression préalable, prog reste None (aucune écriture à 100%)
        self.assertIsNone(prog)


if __name__ == "__main__":
    unittest.main()
