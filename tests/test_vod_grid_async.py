import sys
import unittest
import tempfile
import os
import gc
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from core.database import Database
from core.models import Channel, Playlist
from core.image_loader import ImageLoader
from ui.widgets.vod_grid import VODGridView, VODQueryWorker, PosterWidget


class TestVODGridAsync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_vod_async.db")
        self.db = Database(self.db_path)

        pl = Playlist(name="Test Playlist", url_or_path="http://example.com/playlist.m3u")
        self.pl_id = self.db.add_playlist(pl)

        # Insérer 120 films de test
        channels = [
            Channel(
                playlist_id=self.pl_id,
                stream_id=f"movie_{i}",
                name=f"Film Test {i}",
                stream_type="movie",
                stream_url=f"http://example.com/movie_{i}.mp4",
                group_title="Action",
                logo_url=f"http://example.com/poster_{i}.jpg",
                rating=7.5,
                year=2023,
                is_enabled=True,
            )
            for i in range(1, 121)
        ]
        self.db.save_channels_batch(self.pl_id, channels)

    def tearDown(self):
        del self.db
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_vod_query_worker_execution(self):
        """Vérifie que VODQueryWorker exécute la requête dans un thread et émet results_ready."""
        worker = VODQueryWorker(
            db=self.db,
            playlist_id=self.pl_id,
            group_title="Action",
            search_query=None,
            stream_type="movie",
            only_enabled=True,
            order_by="default",
            limit=20,
            offset=0,
            batch_id=42,
        )

        received_results = []
        received_batch_id = []

        def on_results(movies, batch_id):
            received_results.extend(movies)
            received_batch_id.append(batch_id)

        worker.results_ready.connect(on_results)
        worker.start()
        worker.wait(2000)
        QApplication.processEvents()

        self.assertEqual(received_batch_id, [42])
        self.assertEqual(len(received_results), 20)
        self.assertEqual(received_results[0].name, "Film Test 1")

    def test_vod_query_worker_interruption(self):
        """Vérifie que l'interruption empêche l'émission des résultats."""
        worker = VODQueryWorker(
            db=self.db,
            playlist_id=self.pl_id,
            group_title="Action",
            search_query=None,
            stream_type="movie",
            only_enabled=True,
            order_by="default",
            limit=50,
            offset=0,
            batch_id=99,
        )
        worker.requestInterruption()

        received_results = []
        worker.results_ready.connect(lambda movies, b_id: received_results.extend(movies))
        worker.start()
        worker.wait(1000)

        self.assertEqual(len(received_results), 0)

    def test_vod_grid_async_population(self):
        """Vérifie le cycle complet de chargement asynchrone et d'insertion par lots."""
        view = VODGridView(self.db, stream_type="movie")
        view.resize(800, 600)
        view.set_playlist_and_category(self.pl_id, "Action")

        self.assertEqual(view.total_items, 120)
        # Les 60 premières cartes doivent être présentes IMMÉDIATEMENT dès l'ouverture
        self.assertEqual(view.loaded_count, 60)
        self.assertEqual(view.grid_layout.count(), 60)
        for _ in range(50):
            QApplication.processEvents()
            if view.loaded_count >= 80:
                break
            QApplication.processEvents()
            if view._current_worker:
                view._current_worker.wait(50)

        self.assertGreaterEqual(view.loaded_count, 80)
        self.assertGreater(view.grid_layout.count(), 0)

        # Arrêt propre
        view.stop_workers()
        QApplication.processEvents()

    def test_poster_widget_disconnects_image_loader(self):
        """Vérifie que PosterWidget se déconnecte d'ImageLoader dès réception de son image."""
        ch = Channel(name="Test Poster", logo_url="http://test.com/logo.png")
        pw = PosterWidget(ch)
        loader = ImageLoader.instance()
        self.assertTrue(pw._is_connected_to_loader)

        # Émission d'une image pour un autre poster -> ne doit pas se déconnecter
        pix = QPixmap(10, 10)
        loader.image_loaded.emit("http://other.com/logo.png", pix)
        self.assertTrue(pw._is_connected_to_loader)
        self.assertIsNone(pw.pixmap)

        # Émission de son image -> déconnexion immédiate et pixmap assigné
        loader.image_loaded.emit("http://test.com/logo.png", pix)
        self.assertFalse(pw._is_connected_to_loader)
        self.assertIsNotNone(pw.pixmap)

    def test_sort_order_persists_across_categories(self):
        """Vérifie que l'ordre de tri choisi par l'utilisateur est conservé par catégorie."""
        view = VODGridView(self.db, stream_type="movie")
        view.set_playlist_and_category(self.pl_id, "Action")

        # Par défaut, le tri est default (index 0)
        self.assertEqual(view.current_order, "default")
        self.assertEqual(view.sort_combo.currentIndex(), 0)

        # L'utilisateur choisit le tri par note (index 4: rating_desc)
        view.sort_combo.setCurrentIndex(4)
        self.assertEqual(view.current_order, "rating_desc")

        # L'utilisateur change de catégorie (va sur Comédie, non configurée) -> default
        view.set_playlist_and_category(self.pl_id, "Comédie")
        self.assertEqual(view.current_order, "default")

        # L'utilisateur revient sur Action -> retrouve rating_desc
        view.set_playlist_and_category(self.pl_id, "Action")
        self.assertEqual(view.current_order, "rating_desc")
        self.assertEqual(view.sort_combo.currentIndex(), 4)

        # Vérifier aussi la persistance dans SQLite
        saved = self.db.get_category_sort_order(self.pl_id, "movie", "Action")
        self.assertEqual(saved, "rating_desc")

        view.stop_workers()


if __name__ == "__main__":
    unittest.main()
