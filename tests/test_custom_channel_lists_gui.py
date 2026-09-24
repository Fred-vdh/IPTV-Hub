"""
Tests unitaires GUI pour l'intégration des listes de chaînes personnalisées dans CategoriesPanel et ChannelListPanel.
"""

import sys
import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication

from core.database import Database
from core.models import Channel, Playlist
from ui.widgets.categories_panel import CategoriesPanel
from ui.widgets.channel_list import ChannelListPanel
from ui.dialogs.manage_custom_lists_dialog import ManageCustomListsDialog

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestCustomChannelListsGUI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_gui_iptv.db")
        self.db = Database(self.db_path)

        p = Playlist(name="Test Playlist", url_or_path="http://example.com/playlist.m3u")
        self.pl_id = self.db.add_playlist(p)

        self.ch1 = Channel(
            playlist_id=self.pl_id,
            name="TF1 HD",
            stream_url="http://example.com/live/tf1_hd.m3u8",
            stream_id="101",
            group_title="FR | TNT",
            stream_type="live"
        )
        self.ch2 = Channel(
            playlist_id=self.pl_id,
            name="France 2 HD",
            stream_url="http://example.com/live/fr2_hd.m3u8",
            stream_id="201",
            group_title="FR | TNT",
            stream_type="live"
        )
        self.db.save_channels_batch(self.pl_id, [self.ch1, self.ch2])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_categories_panel_custom_lists_rendering_and_selection(self):
        """Vérifie l'affichage et la sélection d'une liste personnalisée dans CategoriesPanel."""
        panel = CategoriesPanel()
        categories = [("FR | TNT", 2), ("FR | CINEMA", 0)]
        custom_lists = [(1, "Salon HD", 2), (2, "Van SD", 0)]

        panel.set_categories(categories, default_selected="FR | TNT")
        panel.set_custom_lists(custom_lists)

        # Vérifier que le panneau contient les items personnalisés
        self.assertEqual(panel.list_widget.count(), 4)

        # Tester la sélection d'une liste personnalisée
        selected_events = []
        panel.custom_list_selected.connect(lambda lid, name: selected_events.append((lid, name)))

        panel.select_custom_list(1, emit_signal=True)
        self.assertEqual(len(selected_events), 1)
        self.assertEqual(selected_events[0], (1, "Salon HD"))

    def test_channel_list_panel_with_custom_list(self):
        """Vérifie que ChannelListPanel filtre et affiche correctement une liste personnalisée."""
        list_id = self.db.create_custom_channel_list("Salon HD")
        self.db.add_channel_to_custom_list(list_id, self.ch1)

        channel_panel = ChannelListPanel(self.db)
        channel_panel.set_playlist(self.pl_id, stream_type="live")
        channel_panel.set_custom_list(list_id, "Salon HD")

        channels = channel_panel.get_channels()
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0].name, "TF1 HD")
        self.assertIn("Salon HD", channel_panel.cat_title_label.text())

    def test_manage_custom_lists_dialog_instantiation(self):
        """Vérifie que la boîte de dialogue ManageCustomListsDialog s'instancie sans erreur."""
        self.db.create_custom_channel_list("Salon HD")
        dlg = ManageCustomListsDialog(self.db)
        self.assertEqual(dlg.list_widget.count(), 1)
        dlg.close()

    def test_manage_categories_dialog_custom_lists_tab(self):
        """Vérifie que ManageCategoriesDialog intègre les onglets de filtrage et de listes personnalisées."""
        from ui.dialogs.manage_categories_dialog import ManageCategoriesDialog
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent

        list_id = self.db.create_custom_channel_list("Salon HD")
        dlg = ManageCategoriesDialog(self.db, self.pl_id, "live", initial_tab=1)

        # Vérifier les onglets
        self.assertEqual(dlg.tabs.count(), 2)
        self.assertEqual(dlg.tabs.currentIndex(), 1)

        # Vérifier que la liste apparaît dans le combo
        self.assertGreaterEqual(dlg.custom_list_combo.count(), 1)
        self.assertEqual(dlg.custom_list_combo.currentData(), list_id)

        # Vérifier l'arbre des chaînes
        self.assertGreater(dlg.custom_tree_widget.topLevelItemCount(), 0)
        cat_item = dlg.custom_tree_widget.topLevelItem(0)
        self.assertGreater(cat_item.childCount(), 0)

        ch_item = cat_item.child(0)
        self.assertEqual(ch_item.checkState(0), Qt.CheckState.Unchecked)

        # Simuler touche Entrée (télécommande) pour cocher la chaîne
        dlg.custom_tree_widget.setCurrentItem(ch_item)
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        dlg.custom_tree_widget.keyPressEvent(event)

        self.assertEqual(ch_item.checkState(0), Qt.CheckState.Checked)

        # Vérifier que la chaîne a été ajoutée en base
        in_list = self.db.is_channel_in_custom_list(list_id, self.ch1)
        self.assertTrue(in_list)

        dlg.close()

    def test_custom_list_retention_on_categories_reload(self):
        """Vérifie que la sélection d'une liste personnalisée est conservée lors du rechargement des catégories."""
        list_van_id = self.db.create_custom_channel_list("Van SD")
        self.db.add_channel_to_custom_list(list_van_id, self.ch2)

        # Simuler CategoriesPanel et ChannelListPanel
        cat_panel = CategoriesPanel()
        ch_panel = ChannelListPanel(self.db)
        ch_panel.set_playlist(self.pl_id, stream_type="live")

        custom_lists = self.db.get_custom_channel_lists_with_counts(playlist_id=self.pl_id)
        cat_panel.set_custom_lists(custom_lists)
        cat_panel.select_custom_list(list_van_id, emit_signal=False)
        ch_panel.set_custom_list(list_van_id, "Van SD")

        # Vérifier l'état initial
        self.assertEqual(cat_panel._current_selected_custom_list_id, list_van_id)
        self.assertEqual(ch_panel.current_custom_list_id, list_van_id)
        self.assertEqual(len(ch_panel.get_channels()), 1)
        self.assertEqual(ch_panel.get_channels()[0].name, "France 2 HD")

        # Simuler un rechargement (comme fait par _load_categories_and_channels)
        prev_custom_list_id = ch_panel.current_custom_list_id
        matching_custom = next((cl for cl in custom_lists if cl[0] == prev_custom_list_id), None)
        self.assertIsNotNone(matching_custom)

        # Appliquer la logique de préservation
        cat_panel.set_custom_lists(custom_lists)
        cat_panel.set_categories([("FR | TNT", 2)])
        cat_panel.select_custom_list(matching_custom[0], emit_signal=False)
        ch_panel.set_custom_list(matching_custom[0], matching_custom[1])

        # Vérifier que Van SD est TOUJOURS sélectionné et affiche bien sa chaîne
        self.assertEqual(cat_panel._current_selected_custom_list_id, list_van_id)
        self.assertEqual(ch_panel.current_custom_list_id, list_van_id)
        self.assertEqual(len(ch_panel.get_channels()), 1)
        self.assertEqual(ch_panel.get_channels()[0].name, "France 2 HD")

    def test_manage_categories_dialog_movie_series_excludes_custom_tab(self):
        """Vérifie que l'onglet des listes personnalisées n'apparaît que pour le direct."""
        from ui.dialogs.manage_categories_dialog import ManageCategoriesDialog

        # Test mode films (movie)
        dlg_movie = ManageCategoriesDialog(self.db, self.pl_id, "movie")
        self.assertFalse(dlg_movie.has_custom_lists)
        self.assertEqual(dlg_movie.tabs.count(), 1)
        self.assertTrue(dlg_movie.tabs.tabBar().isHidden())
        self.assertFalse(hasattr(dlg_movie, "custom_tree_widget"))
        dlg_movie.close()

        # Test mode séries (series)
        dlg_series = ManageCategoriesDialog(self.db, self.pl_id, "series")
        self.assertFalse(dlg_series.has_custom_lists)
        self.assertEqual(dlg_series.tabs.count(), 1)
        self.assertTrue(dlg_series.tabs.tabBar().isHidden())
        self.assertFalse(hasattr(dlg_series, "custom_tree_widget"))
        dlg_series.close()

        # Test mode direct (live)
        dlg_live = ManageCategoriesDialog(self.db, self.pl_id, "live")
        self.assertTrue(dlg_live.has_custom_lists)
        self.assertEqual(dlg_live.tabs.count(), 2)
        self.assertFalse(dlg_live.tabs.tabBar().isHidden())
        self.assertTrue(hasattr(dlg_live, "custom_tree_widget"))
        dlg_live.close()

    def test_categories_panel_never_shows_custom_lists_for_movies_or_series(self):
        """Vérifie que CategoriesPanel ne contient jamais de listes perso en mode films ou séries."""
        cat_panel = CategoriesPanel()
        custom_lists = [(1, "Salon HD", 10), (2, "Van SD", 5)]

        # En mode live: les listes sont affichées
        cat_panel.set_stream_type("live")
        cat_panel.set_custom_lists(custom_lists)
        cat_panel.set_categories([("FR | TNT", 20)])
        self.assertEqual(len(cat_panel._custom_lists), 2)
        # Vérifier que les items personnalisés sont dans le QListWidget
        has_custom_items = any(
            getattr(cat_panel.list_widget.itemWidget(cat_panel.list_widget.item(i)), "is_custom", False)
            for i in range(cat_panel.list_widget.count())
        )
        self.assertTrue(has_custom_items)

        # Bascule en mode films via set_stream_type
        cat_panel.set_stream_type("movie")
        self.assertEqual(len(cat_panel._custom_lists), 0)
        # Même si set_custom_lists est appelé par erreur en mode films :
        cat_panel.set_custom_lists(custom_lists)
        self.assertEqual(len(cat_panel._custom_lists), 0)
        cat_panel.set_categories([("Action", 50)])
        has_custom_items = any(
            getattr(cat_panel.list_widget.itemWidget(cat_panel.list_widget.item(i)), "is_custom", False)
            for i in range(cat_panel.list_widget.count())
        )
        self.assertFalse(has_custom_items)

        # Bascule en mode séries via set_title
        cat_panel.set_title("Catégories Séries")
        self.assertEqual(cat_panel.stream_type, "series")
        self.assertEqual(len(cat_panel._custom_lists), 0)
        cat_panel.set_custom_lists(custom_lists)
        self.assertEqual(len(cat_panel._custom_lists), 0)
        cat_panel.set_categories([("Comédie", 30)])
        has_custom_items = any(
            getattr(cat_panel.list_widget.itemWidget(cat_panel.list_widget.item(i)), "is_custom", False)
            for i in range(cat_panel.list_widget.count())
        )
        self.assertFalse(has_custom_items)


if __name__ == "__main__":
    unittest.main()

