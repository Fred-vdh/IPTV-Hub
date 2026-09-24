import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import Database
from core.introdb_client import (
    extract_series_title_and_year,
    fetch_introdb_segments,
    get_imdb_id_for_series,
    parse_episode_season_and_num,
)
from core.models import IntroDBSegments


class TestIntroDB(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / 'test_introdb.db')
        self.db = Database(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_extract_series_title_and_year(self):
        title, year = extract_series_title_and_year("Breaking Bad (2008)")
        self.assertEqual(title, "Breaking Bad")
        self.assertEqual(year, "2008")

        title, year = extract_series_title_and_year("Stranger Things")
        self.assertEqual(title, "Stranger Things")
        self.assertEqual(year, "")

        title, year = extract_series_title_and_year("Doctor Who (2005) [FR]")
        self.assertEqual(title, "Doctor Who")
        self.assertEqual(year, "2005")

    def test_parse_episode_season_and_num(self):
        s, ep = parse_episode_season_and_num("Stranger.Things.S02E05.FRENCH.1080p")
        self.assertEqual((s, ep), (2, 5))

        s, ep = parse_episode_season_and_num("Saison 1 Episode 3")
        self.assertEqual((s, ep), (1, 3))

        s, ep = parse_episode_season_and_num("Episode 12")
        self.assertEqual((s, ep), (1, 12))

        s, ep = parse_episode_season_and_num("1x04 Pilot")
        self.assertEqual((s, ep), (1, 4))

    def test_database_settings_introdb(self):
        settings = self.db.get_settings()
        self.assertTrue(settings.introdb_outro_skip)

        settings.introdb_outro_skip = False
        self.db.save_settings(settings)

        reloaded = self.db.get_settings()
        self.assertFalse(reloaded.introdb_outro_skip)

    def test_database_introdb_segments_caching(self):
        # Initialement aucun segment
        cached = self.db.get_introdb_segments("tt1234567", 1, 1)
        self.assertIsNone(cached)

        # Sauvegarde
        seg = IntroDBSegments(
            imdb_id="tt1234567",
            season=1,
            episode=1,
            intro_start=120.5,
            intro_end=150.0,
            outro_start=2800.0,
            outro_end=2890.0,
            confidence=0.98,
            submission_count=12,
        )
        self.db.save_introdb_segments(seg)

        # Lecture
        loaded = self.db.get_introdb_segments("tt1234567", 1, 1)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.imdb_id, "tt1234567")
        self.assertEqual(loaded.season, 1)
        self.assertEqual(loaded.episode, 1)
        self.assertEqual(loaded.intro_start, 120.5)
        self.assertEqual(loaded.intro_end, 150.0)
        self.assertEqual(loaded.outro_start, 2800.0)
        self.assertEqual(loaded.outro_end, 2890.0)
        self.assertEqual(loaded.confidence, 0.98)
        self.assertEqual(loaded.submission_count, 12)

    @patch("urllib.request.urlopen")
    def test_fetch_introdb_segments_api(self, mock_urlopen):
        # Simuler la réponse json de IntroDB avec status 200
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'''{
            "intro": {"start_sec": 45.0, "end_sec": 75.0, "confidence": 0.9},
            "outro": {"start_sec": 3100.5, "end_sec": 3160.0, "confidence": 0.95}
        }'''
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        segments = fetch_introdb_segments("tt9876543", 2, 4, db=self.db)
        self.assertIsNotNone(segments)
        self.assertEqual(segments.outro_start, 3100.5)
        self.assertEqual(segments.intro_start, 45.0)

        # Vérifier que le segment a été mis en cache SQLite
        cached = self.db.get_introdb_segments("tt9876543", 2, 4)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.outro_start, 3100.5)

    @patch("urllib.request.urlopen")
    def test_get_imdb_id_for_series(self, mock_urlopen):
        # 1er appel: recherche TMDB tv
        # 2ème appel: tv external_ids
        mock_resp1 = MagicMock()
        mock_resp1.read.return_value = b'{"results": [{"id": 1399, "name": "Game of Thrones"}]}'
        mock_resp1.__enter__.return_value = mock_resp1

        mock_resp2 = MagicMock()
        mock_resp2.read.return_value = b'{"imdb_id": "tt0944947"}'
        mock_resp2.__enter__.return_value = mock_resp2

        mock_urlopen.side_effect = [mock_resp1, mock_resp2]

        imdb_id = get_imdb_id_for_series("Game of Thrones")
        self.assertEqual(imdb_id, "tt0944947")


if __name__ == '__main__':
    unittest.main()
