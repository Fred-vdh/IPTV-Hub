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

    def test_category_auto_selection_and_partial_channel_filtering(self):
        import sys
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from ui.dialogs.manage_categories_dialog import ManageCategoriesDialog

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # 1. Créer une catégorie de radios désactivée par défaut
        r1 = Channel(playlist_id=self.pl_id, name="France Inter", stream_url="http://radio/inter", stream_id="r1", group_title="RADIOS", stream_type="live", is_enabled=0)
        r2 = Channel(playlist_id=self.pl_id, name="Fun Radio", stream_url="http://radio/fun", stream_id="r2", group_title="RADIOS", stream_type="live", is_enabled=0)
        r3 = Channel(playlist_id=self.pl_id, name="Skyrock", stream_url="http://radio/sky", stream_id="r3", group_title="RADIOS", stream_type="live", is_enabled=0)
        self.db.save_channels_batch(self.pl_id, [r1, r2, r3])
        self.db.save_groups_enabled_status(self.pl_id, "live", disabled_groups=["RADIOS"], enabled_groups=[])

        # 2. Ouvrir le dialogue
        dlg = ManageCategoriesDialog(self.db, playlist_id=self.pl_id, stream_type="live")

        # Trouver la catégorie RADIOS
        tree = dlg.tree_widget
        cat_item = None
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if "RADIOS" in item.text(0):
                cat_item = item
                break

        self.assertIsNotNone(cat_item)
        # Initialement non cochée
        self.assertEqual(cat_item.checkState(0), Qt.CheckState.Unchecked)
        self.assertEqual(cat_item.childCount(), 3)

        # 3. Cocher UNIQUEMENT "France Inter"
        ch0 = cat_item.child(0)
        self.assertEqual(ch0.text(0), "France Inter")
        ch0.setCheckState(0, Qt.CheckState.Checked)

        # La catégorie doit devenir automatiquement COCHÉE (Checked), avec le compteur (1/3)
        self.assertEqual(cat_item.checkState(0), Qt.CheckState.Checked)
        self.assertIn("1/3", cat_item.text(0))

        # Les autres chaînes doivent rester NON cochées
        self.assertEqual(cat_item.child(1).checkState(0), Qt.CheckState.Unchecked)
        self.assertEqual(cat_item.child(2).checkState(0), Qt.CheckState.Unchecked)

        # 4. Sauvegarder
        dlg._save_and_accept()

        # 5. Vérifier en base :
        # - "RADIOS" n'est plus dans persistent_disabled_groups
        dis_groups = self.db.get_disabled_groups(self.pl_id, "live")
        self.assertNotIn("RADIOS", dis_groups)

        # - Seule France Inter est is_enabled=1
        enabled_channels = self.db.get_channels(self.pl_id, group_title="RADIOS", only_enabled=True)
        self.assertEqual(len(enabled_channels), 1)
        self.assertEqual(enabled_channels[0].name, "France Inter")

        # - Les 2 autres sont bien désactivées
        all_channels = self.db.get_channels(self.pl_id, group_title="RADIOS", only_enabled=False)
        self.assertEqual(len(all_channels), 3)
        ch_map = {c.name: c.is_enabled for c in all_channels}
        self.assertTrue(ch_map["France Inter"])
        self.assertFalse(ch_map["Fun Radio"])
        self.assertFalse(ch_map["Skyrock"])

        # - get_groups retourne bien RADIOS
        groups = self.db.get_groups(self.pl_id, stream_type="live", only_enabled=True)
        group_names = [g[0] for g in groups]
        self.assertIn("RADIOS", group_names)

        # 6. Rouvrir le dialogue pour tester la désélection
        dlg2 = ManageCategoriesDialog(self.db, playlist_id=self.pl_id, stream_type="live")
        tree2 = dlg2.tree_widget
        cat_item2 = next(tree2.topLevelItem(i) for i in range(tree2.topLevelItemCount()) if "RADIOS" in tree2.topLevelItem(i).text(0))
        self.assertEqual(cat_item2.checkState(0), Qt.CheckState.Checked)
        self.assertIn("1/3", cat_item2.text(0))

        # Décocher France Inter -> la catégorie doit repasser en Unchecked
        cat_item2.child(0).setCheckState(0, Qt.CheckState.Unchecked)
        self.assertEqual(cat_item2.checkState(0), Qt.CheckState.Unchecked)
        self.assertIn("(3)", cat_item2.text(0))

        # Cocher la catégorie directement -> toutes les chaînes passent à Checked
        cat_item2.setCheckState(0, Qt.CheckState.Checked)
        self.assertEqual(cat_item2.child(0).checkState(0), Qt.CheckState.Checked)
        self.assertEqual(cat_item2.child(1).checkState(0), Qt.CheckState.Checked)
        self.assertEqual(cat_item2.child(2).checkState(0), Qt.CheckState.Checked)

        # Décocher la catégorie directement -> toutes les chaînes passent à Unchecked
        cat_item2.setCheckState(0, Qt.CheckState.Unchecked)
        self.assertEqual(cat_item2.child(0).checkState(0), Qt.CheckState.Unchecked)
        self.assertEqual(cat_item2.child(1).checkState(0), Qt.CheckState.Unchecked)
        self.assertEqual(cat_item2.child(2).checkState(0), Qt.CheckState.Unchecked)

        dlg.deleteLater()
        dlg2.deleteLater()


if __name__ == "__main__":
    unittest.main()
