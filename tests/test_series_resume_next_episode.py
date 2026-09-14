import sys
import os
import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.models import Channel, Playlist
from ui.widgets.series_details_view import SeriesDetailsView


class TestSeriesResumeNextEpisode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.db = Database(self.db_path)
        self.pl = Playlist(
            id=1,
            name="Test Playlist",
            playlist_type="xtream",
            server_url="http://test.server:8080",
            username="user",
            password="pass"
        )
        self.db.add_playlist(self.pl)
        self.series_ch = Channel(
            id=10,
            playlist_id=1,
            name="Breaking Bad",
            stream_url="xtream_series://100",
            stream_type="series"
        )
        self.db.save_channels_batch(1, [self.series_ch])

        self.view = SeriesDetailsView(self.db)
        self.view.playlist = self.pl
        self.view.channel = self.series_ch

        # Mock data with Season 1 (3 eps) and Season 2 (2 eps)
        self.mock_data = {
            "info": {"name": "Breaking Bad", "plot": "A chemistry teacher..."},
            "episodes": {
                "1": [
                    {"id": "101", "season": "1", "episode_num": "1", "title": "Pilot", "container_extension": "mp4"},
                    {"id": "102", "season": "1", "episode_num": "2", "title": "Cat's in the Bag", "container_extension": "mp4"},
                    {"id": "103", "season": "1", "episode_num": "3", "title": "...And the Bag's in the River", "container_extension": "mp4"},
                ],
                "2": [
                    {"id": "201", "season": "2", "episode_num": "1", "title": "Seven Thirty-Seven", "container_extension": "mp4"},
                    {"id": "202", "season": "2", "episode_num": "2", "title": "Grilled", "container_extension": "mp4"},
                ]
            }
        }
        self.view._on_series_data_loaded(self.mock_data)

    def tearDown(self):
        self.view.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_initial_state_lancer_lecture(self):
        """Sans visionnage préalable, le bouton doit proposer de lancer la lecture."""
        self.view._update_resume_button_text()
        self.assertIn("Lancer la lecture", self.view.resume_btn.text())
        ep, action = self.view._get_resume_or_next_episode({})
        self.assertEqual(action, "start")
        self.assertEqual(ep["id"], "101")

    def test_partially_watched_proposes_resume_current_episode(self):
        """Un épisode commencé à 30% doit être repris."""
        progress_map = {
            "http://test.server:8080/series/user/pass/101.mp4": (300.0, 1000.0)
        }
        self.db.save_playback_progress(
            channel_id=10,
            stream_url="http://test.server:8080/series/user/pass/101.mp4",
            channel_name="Breaking Bad S01E01",
            position=300.0,
            duration=1000.0
        )
        self.view._update_resume_button_text()
        self.assertIn("Reprendre : S01E01", self.view.resume_btn.text())
        ep, action = self.view._get_resume_or_next_episode(progress_map)
        self.assertEqual(action, "resume")
        self.assertEqual(ep["id"], "101")

    def test_validated_episodes_proposes_next_unwatched_episode(self):
        """Quand des épisodes ont été validés comme lus (100%), le bouton propose l'épisode suivant."""
        self.db.save_playback_progress(
            channel_id=10,
            stream_url="http://test.server:8080/series/user/pass/101.mp4",
            channel_name="Breaking Bad S01E01",
            position=1000.0,
            duration=1000.0
        )
        self.view._update_resume_button_text()
        self.assertIn("Reprendre : S01E02", self.view.resume_btn.text())
        self.assertIn("Cat's in the Bag", self.view.resume_btn.text())

        self.db.save_playback_progress(
            channel_id=10,
            stream_url="http://test.server:8080/series/user/pass/102.mp4",
            channel_name="Breaking Bad S01E02",
            position=1000.0,
            duration=1000.0
        )
        self.view._update_resume_button_text()
        self.assertIn("Reprendre : S01E03", self.view.resume_btn.text())

    def test_season_completed_continues_to_next_season(self):
        """Quand toute la saison 1 est validée, le bouton propose la saison 2 épisode 1."""
        for ep_id in ("101", "102", "103"):
            self.db.save_playback_progress(
                channel_id=10,
                stream_url=f"http://test.server:8080/series/user/pass/{ep_id}.mp4",
                channel_name=f"Breaking Bad ep {ep_id}",
                position=1000.0,
                duration=1000.0
            )
        self.view._update_resume_button_text()
        self.assertIn("Reprendre : S02E01", self.view.resume_btn.text())

    def test_all_seasons_completed_proposes_restart(self):
        """Quand tous les épisodes de la série sont vus, le bouton propose de recommencer."""
        for ep_id in ("101", "102", "103", "201", "202"):
            self.db.save_playback_progress(
                channel_id=10,
                stream_url=f"http://test.server:8080/series/user/pass/{ep_id}.mp4",
                channel_name=f"Breaking Bad ep {ep_id}",
                position=1000.0,
                duration=1000.0
            )
        self.view._update_resume_button_text()
        self.assertIn("Recommencer la série", self.view.resume_btn.text())

    def test_click_resume_switches_season_tab_if_needed(self):
        """Cliquer sur reprendre alors que la cible est dans une autre saison bascule l'onglet."""
        for ep_id in ("101", "102", "103"):
            self.db.save_playback_progress(
                channel_id=10,
                stream_url=f"http://test.server:8080/series/user/pass/{ep_id}.mp4",
                channel_name=f"Breaking Bad ep {ep_id}",
                position=1000.0,
                duration=1000.0
            )
        self.view.current_season = "1"

        played_requests = []
        self.view.play_episode_requested.connect(lambda ch, all_eps, idx, pos: played_requests.append((ch, idx, pos)))

        self.view._on_resume_clicked()
        self.assertEqual(self.view.current_season, "2")
        self.assertEqual(len(played_requests), 1)
        self.assertIn("S02E01", played_requests[0][0].name)

    def test_auto_selects_active_season_when_loading_series(self):
        """À l'ouverture d'une série dont la saison 1 est vue, l'onglet saison 2 est sélectionné d'office."""
        for ep_id in ("101", "102", "103"):
            self.db.save_playback_progress(
                channel_id=10,
                stream_url=f"http://test.server:8080/series/user/pass/{ep_id}.mp4",
                channel_name=f"Breaking Bad ep {ep_id}",
                position=1000.0,
                duration=1000.0
            )
        self.view.current_season = ""
        self.view._populate_season_tabs()
        self.assertEqual(self.view.current_season, "2")

    def test_save_playback_progress_zero_duration_not_marked_100_percent(self):
        """Une sauvegarde de position avec duration=0 (ex: fermeture de lecteur) ne doit pas forcer 100% de complétion."""
        url = "http://test.server:8080/series/user/pass/test_dur.mp4"
        # 1. Première sauvegarde avec durée connue
        self.db.save_playback_progress(
            channel_id=10,
            stream_url=url,
            channel_name="Test Ep",
            position=500.0,
            duration=3000.0
        )
        prog = self.db.get_playback_progress(stream_url=url)
        self.assertIsNotNone(prog)
        self.assertEqual(prog[0], 500.0)
        self.assertEqual(prog[1], 3000.0)

        # 2. Sauvegarde intermédiaire en cours d'épisode avec duration=0
        self.db.save_playback_progress(
            channel_id=10,
            stream_url=url,
            channel_name="Test Ep",
            position=1506.6,
            duration=0.0
        )
        prog = self.db.get_playback_progress(stream_url=url)
        self.assertIsNotNone(prog)
        # La durée doit rester 3000.0 et la position 1506.6 (pas 100% complété !)
        self.assertEqual(prog[0], 1506.6)
        self.assertEqual(prog[1], 3000.0)
    def test_auto_select_season_tab_on_episode_change(self):
        """Vérifie que la lecture d'un épisode d'une autre saison sélectionne automatiquement son onglet."""
        # Initialement sur la saison 1
        self.view.select_season("1")
        self.assertEqual(self.view.current_season, "1")

        # L'épisode 201 appartient à la saison 2
        season_found = self.view.get_season_for_episode("201")
        self.assertEqual(season_found, "2")

        # Lancement de l'épisode 201 (passage S1 -> S2)
        self.view.set_active_playing_episode("201")

        # L'onglet saison 2 doit être sélectionné automatiquement
        self.assertEqual(self.view.current_season, "2")
        self.assertEqual(self.view._current_playing_episode_id, "201")

        # Lancement d'un épisode de la saison 1 (retour S2 -> S1)
        self.view.set_active_playing_episode("102")
        self.assertEqual(self.view.current_season, "1")
        self.assertEqual(self.view._current_playing_episode_id, "102")

    def test_update_playback_progress_at_95_percent_does_not_recreate_cards(self):
        """Vérifie que le passage à 95% ne recrée pas les cartes d'épisodes (évite le clignotement)."""
        self.view.select_season("1")
        initial_card_count = self.view.episodes_grid.count()
        self.assertGreater(initial_card_count, 0)

        # Récupérer les identifiants Python des widgets cartes initiaux
        initial_card_ids = [
            id(self.view.episodes_grid.itemAt(i).widget())
            for i in range(initial_card_count)
            if self.view.episodes_grid.itemAt(i) and self.view.episodes_grid.itemAt(i).widget()
        ]

        # Progression à 95% (marqué comme vu)
        self.view.update_playback_progress("101", position=950.0, duration=1000.0)

        # Progression une seconde plus tard (toujours à >95%)
        self.view.update_playback_progress("101", position=951.0, duration=1000.0)

        # Les cartes doivent être STRICTEMENT les mêmes instances (aucun widget détruit ni recréé)
        current_card_ids = [
            id(self.view.episodes_grid.itemAt(i).widget())
            for i in range(self.view.episodes_grid.count())
            if self.view.episodes_grid.itemAt(i) and self.view.episodes_grid.itemAt(i).widget()
        ]
        self.assertEqual(initial_card_ids, current_card_ids)

        # La carte de l'épisode 101 doit être marquée comme vue
        card_101 = self.view.episodes_grid.itemAt(0).widget()
        self.assertTrue(card_101.is_watched)


if __name__ == "__main__":
    unittest.main()
