import unittest
import os
import tempfile
from core.database import Database
from core.models import Playlist, Channel


class TestCategoryFiltering(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_filter.db")
        self.db = Database(self.db_path)

        # Creer une fausse playlist
        self.pl = Playlist(name="Test Playlist", url_or_path="http://example.com/playlist.m3u")
        self.pl_id = self.db.add_playlist(self.pl)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_disabled_groups_persistence_and_filtering(self):
        # 1. Inserer un lot initial avec 2 groupes : FR et IT
        ch1 = Channel(playlist_id=self.pl_id, name="Film FR 1", stream_url="http://url/fr1", group_title="Films FR", stream_type="movie", added_at="2026-09-01T10:00:00")
        ch2 = Channel(playlist_id=self.pl_id, name="Film IT 1", stream_url="http://url/it1", group_title="Films IT", stream_type="movie", added_at="2026-09-01T11:00:00")
        self.db.save_channels_batch(self.pl_id, [ch1, ch2])

        # Verifier que les 2 apparaissent
        movies = self.db.get_recently_added(playlist_id=self.pl_id, stream_type="movie")
        self.assertEqual(len(movies), 2)

        # 2. Desactiver le groupe "Films IT"
        self.db.save_groups_enabled_status(self.pl_id, "movie", disabled_groups=["Films IT"], enabled_groups=["Films FR"])
        dis = self.db.get_disabled_groups(self.pl_id, "movie")
        self.assertIn("Films IT", dis)

        # 3. get_recently_added doit maintenant ignorer "Films IT"
        movies = self.db.get_recently_added(playlist_id=self.pl_id, stream_type="movie")
        self.assertEqual(len(movies), 1)
        self.assertEqual(movies[0].name, "Film FR 1")

        # 4. Synchronisation / reimport : insertion d'un NOUVEAU film dans "Films IT"
        ch3 = Channel(playlist_id=self.pl_id, name="Nouveau Film IT 2", stream_url="http://url/it2", group_title="Films IT", stream_type="movie", added_at="2026-09-05T12:00:00")
        ch4 = Channel(playlist_id=self.pl_id, name="Nouveau Film FR 2", stream_url="http://url/fr2", group_title="Films FR", stream_type="movie", added_at="2026-09-05T12:30:00")
        self.db.save_channels_batch(self.pl_id, [ch1, ch2, ch3, ch4], replace=True)

        # Verifier que ch3 a ete automatiquement insere avec is_enabled = 0 !
        ch3_in_db = self.db.get_channels(playlist_id=self.pl_id, only_enabled=False)
        ch3_item = next(c for c in ch3_in_db if c.name == "Nouveau Film IT 2")
        self.assertFalse(ch3_item.is_enabled)

        # get_recently_added ne doit toujours renvoyer QUE les films FR
        recent_movies = self.db.get_recently_added(playlist_id=self.pl_id, stream_type="movie")
        self.assertEqual(len(recent_movies), 2)
        names = [m.name for m in recent_movies]
        self.assertIn("Nouveau Film FR 2", names)
        self.assertIn("Film FR 1", names)
        self.assertNotIn("Nouveau Film IT 2", names)

        # 5. get_groups avec only_enabled=True doit exclure "Films IT"
        groups = self.db.get_groups(playlist_id=self.pl_id, stream_type="movie", only_enabled=True)
        group_names = [g[0] for g in groups]
        self.assertIn("Films FR", group_names)
        self.assertNotIn("Films IT", group_names)


if __name__ == "__main__":
    unittest.main()
