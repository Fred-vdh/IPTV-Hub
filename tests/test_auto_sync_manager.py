"""
Tests unitaires pour le gestionnaire de synchronisation automatique et sélective.
"""

import unittest
import tempfile
import os
import shutil
from datetime import datetime, timedelta

from core.models import Playlist, Channel
from core.database import Database
from core.auto_sync_manager import is_sync_due, format_last_sync
from core.i18n import tr, I18nManager


class TestAutoSyncManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_sync.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_format_last_sync(self):
        self.assertEqual(format_last_sync(None), tr("Jamais"))
        self.assertEqual(format_last_sync(""), tr("Jamais"))

        now_iso = datetime.now().isoformat()
        self.assertEqual(format_last_sync(now_iso), tr("À l'instant"))

        two_hours_ago = (datetime.now() - timedelta(hours=2, minutes=5)).isoformat()
        self.assertIn("2", format_last_sync(two_hours_ago))

        three_days_ago = (datetime.now() - timedelta(days=3)).isoformat()
        self.assertIn("3", format_last_sync(three_days_ago))

    def test_is_sync_due(self):
        # Intervalle nul ou négatif : jamais échu
        self.assertFalse(is_sync_due(None, 0))

        # Pas de date disponible : échu
        self.assertTrue(is_sync_due(None, 1))

        # Synchronisé il y a 5 heures, intervalle de 1 jour : non échu
        five_hours_ago = (datetime.now() - timedelta(hours=5)).isoformat()
        self.assertFalse(is_sync_due(five_hours_ago, 1))

        # Synchronisé il y a 25 heures, intervalle de 1 jour : échu
        twenty_five_hours_ago = (datetime.now() - timedelta(hours=25)).isoformat()
        self.assertTrue(is_sync_due(twenty_five_hours_ago, 1))

        # Synchronisé il y a 2 jours, intervalle de 3 jours : non échu
        two_days_ago = (datetime.now() - timedelta(days=2)).isoformat()
        self.assertFalse(is_sync_due(two_days_ago, 3))

        # Synchronisé il y a 4 jours, intervalle de 3 jours : échu
        four_days_ago = (datetime.now() - timedelta(days=4)).isoformat()
        self.assertTrue(is_sync_due(four_days_ago, 3))

        # Fallback date (ex: created_at)
        self.assertFalse(is_sync_due(None, 1, fallback_date_iso=five_hours_ago))
        self.assertTrue(is_sync_due(None, 1, fallback_date_iso=twenty_five_hours_ago))

    def test_database_sync_timestamps(self):
        pl = Playlist(name="Test Playlist", url_or_path="http://test.com/m3u", playlist_type="m3u")
        pl_id = self.db.add_playlist(pl)

        # Initialement, timestamps à None
        ts = self.db.get_playlist_sync_timestamps(pl_id)
        self.assertIsNone(ts["live"])
        self.assertIsNone(ts["vod"])
        self.assertIsNone(ts["series"])
        self.assertIsNone(ts["epg"])

        # Mettre à jour live
        now_str = datetime.now().isoformat()
        self.db.update_playlist_sync_timestamp(pl_id, "live", now_str)

        ts_after = self.db.get_playlist_sync_timestamps(pl_id)
        self.assertEqual(ts_after["live"], now_str)
        self.assertIsNone(ts_after["vod"])

        # Mettre à jour epg
        self.db.update_playlist_sync_timestamp(pl_id, "epg", now_str)
        ts_epg = self.db.get_playlist_sync_timestamps(pl_id)
        self.assertEqual(ts_epg["epg"], now_str)

    def test_save_channels_selective_replace(self):
        pl = Playlist(name="Test Selective", url_or_path="http://test.com", playlist_type="xtream")
        pl_id = self.db.add_playlist(pl)

        # Insérer 2 chaînes live, 2 films VOD, 2 séries
        live_ch1 = Channel(playlist_id=pl_id, name="TF1", stream_url="http://tf1.ts", stream_type="live")
        live_ch2 = Channel(playlist_id=pl_id, name="FR2", stream_url="http://fr2.ts", stream_type="live")
        movie_ch1 = Channel(playlist_id=pl_id, name="Film 1", stream_url="http://f1.mp4", stream_type="movie")
        movie_ch2 = Channel(playlist_id=pl_id, name="Film 2", stream_url="http://f2.mp4", stream_type="movie")
        series_ch1 = Channel(playlist_id=pl_id, name="Série 1", stream_url="http://s1", stream_type="series")

        all_channels = [live_ch1, live_ch2, movie_ch1, movie_ch2, series_ch1]
        self.db.save_channels_batch(pl_id, all_channels, replace=True)

        counts = self.db.get_playlist_stream_counts(pl_id)
        self.assertEqual(counts["live"], 2)
        self.assertEqual(counts["movie"], 2)
        self.assertEqual(counts["series"], 1)

        # Remplacement sélectif des films uniquement
        new_movie = Channel(playlist_id=pl_id, name="Film Nouveau", stream_url="http://fn.mp4", stream_type="movie")
        self.db.save_channels_batch(pl_id, [new_movie], replace=True, stream_type="movie")

        counts_after = self.db.get_playlist_stream_counts(pl_id)
        # Les chaînes live et les séries doivent être restées strictement intactes !
        self.assertEqual(counts_after["live"], 2)
        self.assertEqual(counts_after["series"], 1)
        # Seuls les films ont été remplacés par le nouveau
        self.assertEqual(counts_after["movie"], 1)

    def test_settings_persistence(self):
        s = self.db.get_settings()
        self.assertTrue(s.auto_sync_live)
        self.assertEqual(s.sync_interval_live_days, 1)

        # Modification des paramètres
        s.auto_sync_live = False
        s.sync_interval_live_days = 2
        s.auto_sync_vod = True
        s.sync_interval_vod_days = 7
        s.auto_sync_series = False
        s.sync_interval_series_days = 5
        s.sync_on_startup = False
        self.db.save_settings(s)

        loaded = self.db.get_settings()
        self.assertFalse(loaded.auto_sync_live)
        self.assertEqual(loaded.sync_interval_live_days, 2)
        self.assertTrue(loaded.auto_sync_vod)
        self.assertEqual(loaded.sync_interval_vod_days, 7)
        self.assertFalse(loaded.auto_sync_series)
        self.assertEqual(loaded.sync_interval_series_days, 5)
        self.assertFalse(loaded.sync_on_startup)

    def test_translations(self):
        i18n = I18nManager.instance()
        for lang in ("fr", "en", "es", "de"):
            i18n.set_language(lang)
            text_sync = tr("Synchronisation & EPG")
            text_live = tr("Chaînes en direct (Live TV)")
            self.assertTrue(len(text_sync) > 0)
            self.assertTrue(len(text_live) > 0)
        i18n.set_language("fr")


if __name__ == "__main__":
    unittest.main()
