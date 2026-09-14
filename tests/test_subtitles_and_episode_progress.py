import sys
import os
import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.models import Channel, Playlist
from core.player_controller import PlayerController
from ui.widgets.series_details_view import SeriesDetailsView, EpisodeCardWidget


class MockMpv(dict):
    """Mock léger pour MPV basé sur un dictionnaire."""
    def get_property(self, key):
        return self.get(key)


class TestSubtitlesAndEpisodeProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_subtitles_disabled_persistence_and_auto_select(self):
        """Vérifie que la désactivation des sous-titres est persistante et force sid='no'."""
        controller = PlayerController(
            preferred_subtitle_lang="off",
            subtitles_enabled=False
        )
        mock_mpv = MockMpv()
        controller._player = mock_mpv

        # Pistes simulées avec une piste de sous-titres français
        tracks = [
            {"type": "video", "id": 1},
            {"type": "audio", "id": 1, "lang": "fra"},
            {"type": "sub", "id": 1, "lang": "fra", "title": "French"}
        ]

        # 1. Quand les sous-titres sont désactivés, _auto_select_preferred_subtitles force sid='no'
        mock_mpv["sid"] = 1  # simule que MPV a activé la piste 1 par défaut
        controller._auto_select_preferred_subtitles(tracks)
        self.assertEqual(mock_mpv["sid"], "no")

        # 2. Clic utilisateur pour activer les sous-titres sur la piste 1
        signal_received = []
        controller.subtitle_preference_changed.connect(lambda lang, enabled: signal_received.append((lang, enabled)))
        mock_mpv["track-list"] = tracks
        controller.set_subtitle_track(1)

        self.assertTrue(controller._subtitles_enabled)
        self.assertEqual(controller._preferred_subtitle_lang, "fra")
        self.assertEqual(signal_received, [("fra", True)])

        # 3. Nouveau fichier chargé avec sous-titres activés : la piste française doit être sélectionnée
        mock_mpv["sid"] = "no"
        controller._auto_select_preferred_subtitles(tracks)
        self.assertEqual(mock_mpv["sid"], 1)

        # 4. Clic utilisateur pour désactiver les sous-titres (piste 0)
        signal_received.clear()
        controller.set_subtitle_track(0)
        self.assertFalse(controller._subtitles_enabled)
        self.assertEqual(controller._preferred_subtitle_lang, "off")
        self.assertEqual(signal_received, [("off", False)])
        self.assertEqual(mock_mpv["sid"], "no")

        # 5. Nouveau fichier chargé après désactivation : doit rester à sid='no'
        mock_mpv["sid"] = 1
        controller._auto_select_preferred_subtitles(tracks)
        self.assertEqual(mock_mpv["sid"], "no")

    def test_series_episode_progress_realtime_and_refresh(self):
        """Vérifie la mise à jour en temps réel et le rafraîchissement des cartes d'épisodes."""
        pl = Playlist(id=1, name="Test PL", playlist_type="xtream", server_url="http://s", username="u", password="p")
        self.db.add_playlist(pl)
        ch = Channel(id=5, playlist_id=1, name="Test Series", stream_url="xtream_series://1", stream_type="series")
        self.db.save_channels_batch(1, [ch])

        view = SeriesDetailsView(self.db)
        view.playlist = pl
        view.channel = ch
        view.series_data = {
            "info": {"name": "Test Series"},
            "episodes": {
                "1": [
                    {"id": "501", "season": "1", "episode_num": "1", "title": "Ep 1", "container_extension": "mp4"},
                    {"id": "502", "season": "1", "episode_num": "2", "title": "Ep 2", "container_extension": "mp4"}
                ]
            }
        }
        view.episodes_by_season = view.series_data["episodes"]
        view.current_season = "1"
        view._populate_episodes_grid()

        # Vérifier que deux cartes d'épisodes sont créées
        self.assertEqual(view.episodes_grid.count(), 2)
        card1 = view.episodes_grid.itemAt(0).widget()
        card2 = view.episodes_grid.itemAt(1).widget()
        self.assertIsInstance(card1, EpisodeCardWidget)
        self.assertIsInstance(card2, EpisodeCardWidget)
        self.assertEqual(card1.progress_ratio, 0.0)

        # 1. Mise à jour en temps réel (50% sur l'épisode 501)
        view.update_playback_progress(episode_id="501", position=1500.0, duration=3000.0)
        self.assertAlmostEqual(card1.progress_ratio, 0.5, places=2)
        self.assertFalse(card1.is_watched)
        self.assertEqual(card2.progress_ratio, 0.0)

        # 2. Mise à jour en temps réel (95% -> marqué comme vu)
        view.update_playback_progress(episode_id="501", position=2900.0, duration=3000.0)
        self.assertAlmostEqual(card1.progress_ratio, 1.0, places=2)
        self.assertTrue(card1.is_watched)

        # 3. Enregistrement en base de données pour l'épisode 502 et refresh_progress()
        self.db.save_playback_progress(
            channel_id=0,
            stream_url="http://s/series/u/p/502.mp4",
            channel_name="Ep 2",
            position=600.0,
            duration=2000.0
        )
        view.refresh_progress()
        card2_updated = view.episodes_grid.itemAt(1).widget()
        self.assertAlmostEqual(card2_updated.progress_ratio, 0.3, places=2)


if __name__ == "__main__":
    unittest.main()
