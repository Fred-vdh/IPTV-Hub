"""
Tests unitaires pour le gestionnaire de synchronisation multi-machines.
"""

import unittest
import tempfile
from pathlib import Path

from core.database import Database
from core.models import Playlist
from core.sync_manager import (
    export_sync_data,
    merge_sync_data,
    sync_push_to_file,
    sync_pull_from_file,
    EXCLUDED_SETTINGS_KEYS,
)


class TestSyncManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sync.db"
        self.db = Database(str(self.db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_excludes_raw_channels_and_window_geometry(self):
        p = Playlist(name="Test Playlist", server_url="http://test.com", username="user1", password="pwd")
        p_id = self.db.add_playlist(p)

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO channels (name, stream_url, stream_type, playlist_id)
                VALUES ('TF1 HD', 'http://stream.ts', 'live', ?)
            """, (p_id,))
            cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('window_width', '1920')")
            cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('preferred_audio_lang', 'fr-FR')")
            cur.execute("INSERT OR REPLACE INTO persistent_favorites (name, stream_url, stream_type) VALUES ('TF1 HD', 'http://stream.ts', 'live')")
            conn.commit()
        self.db.save_playback_progress(1, "http://stream.ts", "TF1 HD", 120.0, 3600.0)

        data = export_sync_data(self.db)

        self.assertNotIn("channels", data)
        self.assertNotIn("epg_programs", data)
        self.assertEqual(len(data["playback_progress"]), 1)
        self.assertEqual(len(data["persistent_favorites"]), 1)
        self.assertEqual(data["settings"].get("preferred_audio_lang"), "fr-FR")
        for key in EXCLUDED_SETTINGS_KEYS:
            self.assertNotIn(key, data["settings"])

    def test_smart_merge_progress_keeps_newer_timestamp(self):
        s_url = "http://movie1.mp4"
        self.db.save_playback_progress(None, s_url, "Film 1", 100.0, 1000.0)

        remote_data = {
            "playback_progress": [
                {
                    "stream_url": s_url,
                    "channel_name": "Film 1",
                    "playback_position": 450.0,
                    "duration": 1000.0,
                    "updated_at": "2099-01-01T00:00:00Z"
                }
            ]
        }

        stats = merge_sync_data(self.db, remote_data)
        self.assertEqual(stats["progress_updated"], 1)

        pos, dur = self.db.get_playback_progress(stream_url=s_url)
        self.assertEqual(pos, 450.0)

    def test_smart_merge_progress_rejects_older_timestamp(self):
        s_url = "http://movie2.mp4"
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO playback_progress (stream_url, channel_name, playback_position, duration, updated_at) VALUES (?, ?, ?, ?, ?)",
                (s_url, "Film 2", 800.0, 1000.0, "2099-01-01T00:00:00Z")
            )
            conn.commit()

        remote_data = {
            "playback_progress": [
                {
                    "stream_url": s_url,
                    "channel_name": "Film 2",
                    "playback_position": 200.0,
                    "duration": 1000.0,
                    "updated_at": "2020-01-01T00:00:00Z"
                }
            ]
        }

        stats = merge_sync_data(self.db, remote_data)
        self.assertEqual(stats["progress_updated"], 0)

        pos, dur = self.db.get_playback_progress(stream_url=s_url)
        self.assertEqual(pos, 800.0)

    def test_sync_push_and_pull_files(self):
        sync_file = Path(self.temp_dir.name) / "test_iptv_sync.json"
        self.db.save_playback_progress(None, "http://episode1.mkv", "Episode 1", 350.0, 2400.0)

        ok_push, msg_push = sync_push_to_file(self.db, sync_file)
        self.assertTrue(ok_push)
        self.assertTrue(sync_file.exists())

        db2_path = Path(self.temp_dir.name) / "test_pc2.db"
        db2 = Database(str(db2_path))

        ok_pull, msg_pull, stats = sync_pull_from_file(db2, sync_file)
        self.assertTrue(ok_pull)
        self.assertEqual(stats["progress_updated"], 1)

        pos2, dur2 = db2.get_playback_progress(stream_url="http://episode1.mkv")
        self.assertEqual(pos2, 350.0)

    def test_export_and_import_config_file(self):
        from core.sync_manager import export_config_to_file, import_config_from_file

        cfg_file = Path(self.temp_dir.name) / "my_custom_backup.json"
        self.db.save_playback_progress(None, "http://android_tv_stream.mkv", "Film Android", 1250.0, 7200.0)

        ok_exp, msg_exp = export_config_to_file(self.db, cfg_file)
        self.assertTrue(ok_exp)
        self.assertTrue(cfg_file.exists())

        # Créer une seconde base (simulant l'Android TV ou un autre PC)
        db_remote = Database(str(Path(self.temp_dir.name) / "android_tv.db"))
        ok_imp, msg_imp, stats = import_config_from_file(db_remote, cfg_file)
        self.assertTrue(ok_imp)
        self.assertEqual(stats["progress"], 1)
        self.assertEqual(stats["progress_updated"], 1)

        pos, dur = db_remote.get_playback_progress(stream_url="http://android_tv_stream.mkv")
        self.assertEqual(pos, 1250.0)
        self.assertEqual(dur, 7200.0)

    def test_settings_view_backup_page(self):
        import sys
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)

        from ui.widgets.settings_view import SettingsView
        sv = SettingsView(self.db)

        # Vérifier que le bouton Sauvegarde & Fichiers et la page existent
        self.assertIsNotNone(sv.btn_backup)
        self.assertIsNotNone(sv.page_backup)
        self.assertEqual(sv.stack.indexOf(sv.page_backup), 5)
        self.assertIsNotNone(sv.btn_export_config)
        self.assertIsNotNone(sv.btn_import_config)


if __name__ == "__main__":
    unittest.main()

