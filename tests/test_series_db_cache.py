import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from core.database import Database
from core.models import Channel, Playlist
from ui.widgets.series_details_view import SeriesDetailsView, _SERIES_INFO_CACHE


class TestSeriesDBCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_iptv.db"
        self.db = Database(str(self.db_path))

        # Création d'une playlist de test
        p = Playlist(
            name="Test Xtream",
            url_or_path="http://example.com",
            playlist_type="xtream",
            server_url="http://example.com",
            username="user",
            password="pass"
        )
        self.playlist_id = self.db.add_playlist(p)

        # Création d'une série de test
        self.channel = Channel(
            id=1,
            playlist_id=self.playlist_id,
            name="Breaking Bad",
            stream_url="xtream_series://100",
            logo_url="http://example.com/poster.jpg",
            group_title="Drame",
            stream_type="series",
            stream_id="100",
            rating="9.5",
            year="2008"
        )

        _SERIES_INFO_CACHE.clear()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        _SERIES_INFO_CACHE.clear()

    def test_database_save_and_get_series_info(self):
        """Vérifie l'enregistrement et la restitution des informations d'une série en SQLite."""
        series_data = {
            "info": {
                "name": "Breaking Bad",
                "plot": "Un professeur de chimie...",
                "genre": "Crime, Drama",
                "releaseDate": "2008-01-20"
            },
            "seasons": [
                {"season_number": 1, "name": "Saison 1"}
            ],
            "episodes": {
                "1": [
                    {"id": "1001", "episode_num": 1, "title": "Chute libre", "container_extension": "mkv"},
                    {"id": "1002", "episode_num": 2, "title": "Le Choix", "container_extension": "mkv"}
                ]
            }
        }

        # Au départ, aucun cache
        self.assertIsNone(self.db.get_series_info(self.playlist_id, "100"))

        # Sauvegarde
        self.db.save_series_info(self.playlist_id, "100", series_data)

        # Récupération
        cached = self.db.get_series_info(self.playlist_id, "100")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["info"]["name"], "Breaking Bad")
        self.assertEqual(len(cached["episodes"]["1"]), 2)
        self.assertEqual(cached["episodes"]["1"][0]["title"], "Chute libre")

    @patch("ui.widgets.series_details_view._SeriesTrailerLookupWorker")
    @patch("ui.widgets.series_details_view.SeriesInfoWorker")
    def test_load_series_displays_from_db_immediately(self, mock_worker_cls, mock_trailer_cls):
        """Vérifie que load_series charge et affiche immédiatement les épisodes depuis SQLite sans attendre le réseau."""
        # Pré-remplir la base avec des épisodes
        series_data = {
            "info": {
                "name": "Breaking Bad",
                "plot": "Un professeur de chimie...",
                "genre": "Drame"
            },
            "seasons": [
                {"season_number": 1, "name": "Saison 1"}
            ],
            "episodes": {
                "1": [
                    {"id": "1001", "episode_num": 1, "title": "Épisode 1", "container_extension": "mkv"}
                ]
            }
        }
        self.db.save_series_info(self.playlist_id, "100", series_data)

        view = SeriesDetailsView(self.db)

        # Mock du worker pour qu'il ne se lance pas réellement
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker
        mock_trailer = MagicMock()
        mock_trailer_cls.return_value = mock_trailer

        view.load_series(self.channel)

        # Vérifier que les épisodes sont chargés en mémoire immédiatement
        self.assertEqual(len(view.all_episodes_flat), 1)
        self.assertEqual(view.all_episodes_flat[0]["id"], "1001")
        self.assertEqual(view.all_episodes_flat[0]["title"], "Épisode 1")

        # Vérifier que le worker d'arrière-plan a bien été initié pour chercher d'éventuels nouveaux épisodes
        mock_worker_cls.assert_called_once()
        mock_worker.start.assert_called_once()

        view.stop_workers()
        view.close()

    @patch("ui.widgets.series_details_view._SeriesTrailerLookupWorker")
    @patch("ui.widgets.series_details_view.SeriesInfoWorker")
    def test_async_update_saves_to_db_and_updates_view(self, mock_worker_cls, mock_trailer_cls):
        """Vérifie que la réponse du worker met à jour la base de données SQLite et la vue."""
        view = SeriesDetailsView(self.db)
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker
        mock_trailer = MagicMock()
        mock_trailer_cls.return_value = mock_trailer

        view.load_series(self.channel)

        # Nouvelles données retournées par Xtream (2 épisodes)
        fresh_data = {
            "info": {
                "name": "Breaking Bad",
                "plot": "Nouveau synopsis mis à jour"
            },
            "seasons": [
                {"season_number": 1}
            ],
            "episodes": {
                "1": [
                    {"id": "1001", "episode_num": 1, "title": "Épisode 1"},
                    {"id": "1002", "episode_num": 2, "title": "Épisode 2"}
                ]
            }
        }

        # Simuler le signal de fin du worker
        cache_key = (self.playlist_id, "100")
        view._handle_series_data_loaded(cache_key, fresh_data)

        # Vérifier que la BDD SQLite a bien reçu les données fraîches
        cached_in_db = self.db.get_series_info(self.playlist_id, "100")
        self.assertIsNotNone(cached_in_db)
        self.assertEqual(len(cached_in_db["episodes"]["1"]), 2)

        # Vérifier que la vue a été mise à jour
        self.assertEqual(len(view.all_episodes_flat), 2)
        self.assertEqual(view.plot_label.text(), "Nouveau synopsis mis à jour")

        view.stop_workers()
        view.close()


if __name__ == "__main__":
    unittest.main()
