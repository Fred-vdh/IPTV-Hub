import unittest
from unittest.mock import patch
from core.download_manager import (
    DownloadManager, DownloadItem, DownloadStatus, StorageStats, sanitize_filename
)


class TestDownloadManager(unittest.TestCase):
    def test_sanitize_filename(self):
        clean = sanitize_filename('Film: "L\'aventure" / Action <2024>? *')
        self.assertNotIn(":", clean)
        self.assertNotIn('"', clean)
        self.assertNotIn("/", clean)
        self.assertNotIn("<", clean)
        self.assertNotIn(">", clean)
        self.assertNotIn("?", clean)
        self.assertNotIn("*", clean)

    def test_download_item_formatting(self):
        item = DownloadItem(
            id="movie_10",
            stream_id="10",
            title="Film Test",
            total_bytes=1500 * 1024 * 1024,  # ~1.46 Go
            downloaded_bytes=750 * 1024 * 1024,
            progress_percent=50,
            speed_bytes_per_sec=2 * 1024 * 1024  # 2.0 Mo/s
        )
        self.assertIn("Go", item.get_formatted_size())
        self.assertIn("50%", item.get_formatted_progress())
        self.assertEqual(item.get_formatted_speed(), "2.0 Mo/s")

    def test_download_item_serialization(self):
        item = DownloadItem(
            id="movie_42",
            stream_id="42",
            title="Inception",
            sub_title="1080p",
            poster_url="http://example.com/poster.jpg",
            stream_url="http://example.com/movie.mp4",
            stream_type="movie",
            container_extension="mp4"
        )
        d = item.to_dict()
        self.assertEqual(d["id"], "movie_42")
        self.assertEqual(d["title"], "Inception")

        restored = DownloadItem.from_dict(d)
        self.assertEqual(restored.id, item.id)
        self.assertEqual(restored.title, item.title)
        self.assertEqual(restored.stream_url, item.stream_url)

    def test_storage_stats_formatting(self):
        stats = StorageStats(
            total_bytes=100 * 1024 * 1024 * 1024,
            available_bytes=45 * 1024 * 1024 * 1024,
            downloads_occupied_bytes=1500 * 1024 * 1024
        )
        self.assertIn("45.0 Go libres", stats.get_formatted_available())
        self.assertIn("1.46 Go utilisés par IPTV Hub", stats.get_formatted_occupied())

    @patch.object(DownloadManager, "_start_worker")
    def test_fifo_queue_iptv_single_active_stream(self, mock_start):
        mgr = DownloadManager.instance()
        mgr._downloads_list.clear()
        mgr._active_workers.clear()

        item1 = DownloadItem(id="dl_1", stream_id="1", title="Item 1", added_date=100.0)
        item2 = DownloadItem(id="dl_2", stream_id="2", title="Item 2", added_date=200.0)

        mgr.enqueue_download(item1)
        mock_start.assert_called_once_with(item1)

        # Simuler item1 en cours
        item1.status = DownloadStatus.DOWNLOADING
        mgr._active_workers[item1.id] = None

        mock_start.reset_mock()
        mgr.enqueue_download(item2)
        # item2 doit être mis en attente QUEUED et ne pas démarrer immédiatement (règle IPTV 1 flux max)
        self.assertEqual(item2.status, DownloadStatus.QUEUED)
        mock_start.assert_not_called()

        # Libérer item1
        del mgr._active_workers[item1.id]
        item1.status = DownloadStatus.COMPLETED

        # Traiter la file : item2 doit maintenant démarrer
        mgr.process_queue()
        mock_start.assert_called_once_with(item2)

    def test_pause_and_resume_all_for_playback(self):
        mgr = DownloadManager.instance()
        mgr._downloads_list.clear()
        mgr._active_workers.clear()

        item1 = DownloadItem(id="dl_10", stream_id="10", title="Film 10", status=DownloadStatus.DOWNLOADING)
        item2 = DownloadItem(id="dl_20", stream_id="20", title="Film 20", status=DownloadStatus.QUEUED)
        mgr._downloads_list.extend([item1, item2])

        # Visionnage lancé -> pause de tous les téléchargements actifs pour libérer la bande passante IPTV
        mgr.pause_all_for_playback()
        self.assertEqual(item1.status, DownloadStatus.PAUSED)
        self.assertIn("Visionnage en cours", item1.error_message or "")
        self.assertEqual(item2.status, DownloadStatus.PAUSED)

        # Fin du visionnage -> reprise automatique dans l'ordre FIFO
        with patch.object(mgr, "_start_worker") as mock_start:
            mgr.resume_all_after_playback()
            self.assertEqual(item1.status, DownloadStatus.QUEUED)
            self.assertEqual(item2.status, DownloadStatus.QUEUED)
            mock_start.assert_called_once()

    def test_speed_limit_and_throttling_configuration(self):
        mgr = DownloadManager.instance()
        mgr.set_speed_limit(1500 * 1024)
        self.assertEqual(mgr.get_speed_limit(), 1500 * 1024)

        # Test application aux workers actifs
        from core.download_manager import DownloadWorkerThread
        item = DownloadItem(id="dl_spd", stream_id="spd", title="Spd Test")
        worker = DownloadWorkerThread(item, speed_limit_bytes_per_sec=mgr.get_speed_limit())
        self.assertEqual(worker.speed_limit_bytes_per_sec, 1500 * 1024)

        # Modification dynamique
        mgr._active_workers[item.id] = worker
        mgr.set_speed_limit(3000 * 1024)
        self.assertEqual(mgr.get_speed_limit(), 3000 * 1024)
        self.assertEqual(worker.speed_limit_bytes_per_sec, 3000 * 1024)
        del mgr._active_workers[item.id]

    def test_custom_download_directory_lookup(self):
        mgr = DownloadManager.instance()
        with patch("core.database.Database.get_settings") as mock_settings:
            from core.models import AppSettings
            s = AppSettings()
            s.download_dir = "C:/TestDownloads/IPTV"
            mock_settings.return_value = s
            with patch("os.path.isdir", return_value=True):
                self.assertEqual(mgr.get_download_directory(), "C:/TestDownloads/IPTV")


if __name__ == "__main__":
    unittest.main()
