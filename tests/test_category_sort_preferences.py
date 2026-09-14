import sys
import unittest
import tempfile
import os
import gc
from PyQt6.QtWidgets import QApplication
from core.database import Database
from ui.widgets.vod_grid import VODGridView


class TestCategorySortPreferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_sort.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        del self.db
        gc.collect()
        self.temp_dir.cleanup()

    def test_database_get_set_sort_order(self):
        # Par defaut aucun tri enregistre
        order = self.db.get_category_sort_order(1, "series", "Nouveautes")
        self.assertIsNone(order)

        # Enregistrement
        self.db.set_category_sort_order(1, "series", "Nouveautes", "date_desc")
        self.assertEqual(self.db.get_category_sort_order(1, "series", "Nouveautes"), "date_desc")

        # Mise a jour (UPSERT)
        self.db.set_category_sort_order(1, "series", "Nouveautes", "rating_desc")
        self.assertEqual(self.db.get_category_sort_order(1, "series", "Nouveautes"), "rating_desc")

        # Isolation par stream_type
        self.assertIsNone(self.db.get_category_sort_order(1, "movie", "Nouveautes"))

        # Isolation par playlist_id
        self.assertIsNone(self.db.get_category_sort_order(2, "series", "Nouveautes"))

        # Isolation par categorie
        self.assertIsNone(self.db.get_category_sort_order(1, "series", "Action"))

    def test_vod_grid_restores_and_persists_sort(self):
        # Pre-enregistrer un tri pour une categorie
        self.db.set_category_sort_order(1, "series", "Nouveautes", "date_desc")

        view = VODGridView(self.db, stream_type="series")
        # Selectionner la categorie "Nouveautes"
        view.set_playlist_and_category(1, "Nouveautes")

        self.assertEqual(view.current_order, "date_desc")
        self.assertEqual(view.sort_combo.currentIndex(), 1)  # 1 = "Trier : Date d'ajout (plus recents...)"

        # Changer le tri via l'IHM vers "Trier : Note (plus haute)" (index 4)
        view.sort_combo.setCurrentIndex(4)
        self.assertEqual(view.current_order, "rating_desc")

        # Verifier que la preference a bien ete persistee dans la DB
        saved_order = self.db.get_category_sort_order(1, "series", "Nouveautes")
        self.assertEqual(saved_order, "rating_desc")

        # Passer a une autre categorie non enregistree
        view.set_playlist_and_category(1, "Comedie")
        self.assertEqual(view.current_order, "default")
        self.assertEqual(view.sort_combo.currentIndex(), 0)

        # Revenir sur "Nouveautes" -> retrouve bien "rating_desc"
        view.set_playlist_and_category(1, "Nouveautes")
        self.assertEqual(view.current_order, "rating_desc")
        self.assertEqual(view.sort_combo.currentIndex(), 4)

        view.stop_workers()
        view.deleteLater()
        QApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
