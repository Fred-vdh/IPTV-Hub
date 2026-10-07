import sys
import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import Database
from core.models import Channel, WatchHistory
from ui.widgets.dashboard_view import DashboardView
from ui.widgets.recently_watched_view import RecentlyWatchedView

_APP = QApplication.instance() or QApplication(sys.argv)


class TestRecentlyWatchedExcludesLiveTV(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_no_live.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dashboard_does_not_have_recent_live_section(self):
        """Vérifie que la section 'TV en direct récemment regardée' n'est plus présente sur le tableau de bord."""
        view = DashboardView(self.db)
        self.assertFalse(hasattr(view, "sec_recent_live"))
        # Le refresh ne doit pas planter
        view.refresh_view()

    def test_recently_watched_view_does_not_have_live_button(self):
        """Vérifie que le bouton de filtre 'TV en direct' est supprimé de RecentlyWatchedView."""
        view = RecentlyWatchedView(self.db)
        self.assertFalse(hasattr(view, "btn_live"))
        self.assertTrue(hasattr(view, "btn_all"))
        self.assertTrue(hasattr(view, "btn_movies"))
        self.assertTrue(hasattr(view, "btn_series"))

    def test_get_recently_watched_items_excludes_live_by_default(self):
        """Vérifie que les chaînes de TV en direct sont exclues par défaut de l'historique."""
        # 1. Ajouter un film, une série et une chaîne de TV live
        movie_h = WatchHistory(channel_name="Inception (2010)", stream_url="http://x/movie.mp4", duration=7200, playback_position=1000)
        series_h = WatchHistory(channel_name="Breaking Bad S01E01", stream_url="http://x/series/1.mkv", duration=3000, playback_position=500)
        live_h = WatchHistory(channel_name="TF1 HD", stream_url="http://x/live/tf1.ts", duration=0, playback_position=0)

        self.db.add_watch_history(movie_h)
        self.db.add_watch_history(series_h)
        self.db.add_watch_history(live_h)

        # 2. Récupérer avec include_live=False (défaut)
        items = self.db.get_recently_watched_items(include_live=False)
        stream_types = [item["channel"].stream_type for item in items]

        self.assertIn("movie", stream_types)
        self.assertIn("series", stream_types)
        self.assertNotIn("live", stream_types)

        # 3. Vérifier que RecentlyWatchedView ne contient aucune carte live
        view = RecentlyWatchedView(self.db)
        view.refresh_view()
        for card in view._cards:
            self.assertNotEqual(card.channel.stream_type, "live")

    def test_play_channel_does_not_record_live_in_history(self):
        """Vérifie que la lecture d'une chaîne TV ne génère pas d'entrée dans watch_history."""
        from ui.main_window import MainWindow
        from unittest.mock import patch
        from core.player_controller import PlayerController
        from core.xtream_client import XtreamClient

        live_ch = Channel(
            id=1,
            name="France 2 HD",
            stream_url="http://x/live/fr2.ts",
            stream_type="live"
        )
        vod_ch = Channel(
            id=2,
            name="Gladiator",
            stream_url="http://x/movie/glad.mp4",
            stream_type="movie"
        )

        with patch.object(XtreamClient, "get_series_info", return_value={"info": {}, "seasons": [], "episodes": {}}), \
             patch("core.tmdb_client.find_best_trailer", return_value={}), \
             patch("core.introdb_client.get_imdb_id_for_series", return_value=None), \
             patch.object(PlayerController, "play"):
            window = MainWindow(db=self.db)
            try:
                # Lecture chaîne TV
                window.play_channel(live_ch)
                # Lecture VOD
                window.play_channel(vod_ch)

                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT channel_name, stream_url FROM watch_history")
                    rows = cursor.fetchall()
                    names = [r[0] for r in rows]

                    # Gladiator doit être présent, France 2 HD doit être absent
                    self.assertIn("Gladiator", names)
                    self.assertNotIn("France 2 HD", names)
            finally:
                window.close()
                if hasattr(window, "player_controller"):
                    window.player_controller.cleanup()


if __name__ == "__main__":
    unittest.main()
