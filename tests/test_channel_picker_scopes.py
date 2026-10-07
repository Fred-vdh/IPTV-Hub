"""
Tests du sélecteur de chaîne des écrans Multiview (ChannelPickerDialog).

Vérifie que la fenêtre propose les listes personnalisées EN PREMIER, puis les
catégories filtrées (chaînes TV en direct activées uniquement), et que la
sélection d'une source filtre bien la liste des chaînes.
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.models import Channel, Playlist
from ui.dialogs.channel_picker_dialog import ChannelPickerDialog


class TestChannelPickerScopes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp_dir.name) / "test_picker.db"))

        playlist = Playlist(name="Test Playlist", url_or_path="http://example.com/playlist.m3u")
        self.pl_id = self.db.add_playlist(playlist)

        self.tf1 = Channel(
            playlist_id=self.pl_id, name="TF1 HD", stream_url="http://x/tf1.m3u8",
            stream_id="101", group_title="FR | TNT", stream_type="live"
        )
        self.fr2 = Channel(
            playlist_id=self.pl_id, name="France 2 HD", stream_url="http://x/fr2.m3u8",
            stream_id="201", group_title="FR | TNT", stream_type="live"
        )
        self.cplus = Channel(
            playlist_id=self.pl_id, name="Canal+", stream_url="http://x/cplus.m3u8",
            stream_id="301", group_title="FR | CINE", stream_type="live"
        )
        self.movie = Channel(
            playlist_id=self.pl_id, name="Un film", stream_url="http://x/film.mp4",
            stream_id="901", group_title="VOD | Films", stream_type="movie"
        )
        self.db.save_channels_batch(self.pl_id, [self.tf1, self.fr2, self.cplus, self.movie])

        # Liste personnalisée « Salon HD » : TF1 HD + Canal+
        self.list_id = self.db.create_custom_channel_list("Salon HD")
        self.db.add_channel_to_custom_list(self.list_id, self.tf1)
        self.db.add_channel_to_custom_list(self.list_id, self.cplus)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # ---------------------------------------------------------- utilitaires

    def _labels(self, dialog):
        return [dialog.scope_list.item(i).text() for i in range(dialog.scope_list.count())]

    def _scope_keys(self, dialog):
        return [
            dialog.scope_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(dialog.scope_list.count())
        ]

    def _channel_names(self, dialog):
        names = []
        for i in range(dialog.channel_list.count()):
            item = dialog.channel_list.item(i)
            if isinstance(item.data(Qt.ItemDataRole.UserRole), Channel):
                names.append(item.text().strip())
        return names

    def _row_for_scope(self, dialog, scope):
        for row in range(dialog.scope_list.count()):
            if dialog.scope_list.item(row).data(Qt.ItemDataRole.UserRole) == scope:
                return row
        raise AssertionError(f"source introuvable : {scope}")

    def _select_scope(self, dialog, scope):
        dialog.scope_list.setCurrentRow(self._row_for_scope(dialog, scope))

    # --------------------------------------------------------------- tests
    def test_custom_lists_are_listed_before_categories(self):
        """Les listes personnalisées doivent précéder la liste des catégories."""
        dlg = ChannelPickerDialog(self.db, playlist_id=self.pl_id)
        labels = self._labels(dlg)

        idx_custom_header = labels.index("Listes personnalisées")
        idx_custom_item = next(i for i, t in enumerate(labels) if t.startswith("Salon HD"))
        idx_cat_header = labels.index("CATÉGORIES")

        self.assertLess(idx_custom_header, idx_custom_item)
        self.assertLess(idx_custom_item, idx_cat_header)

    def test_first_custom_list_is_selected_by_default(self):
        dlg = ChannelPickerDialog(self.db, playlist_id=self.pl_id)
        self.assertEqual(
            dlg.current_scope, f"{ChannelPickerDialog.CUSTOM_PREFIX}{self.list_id}"
        )
        self.assertEqual(sorted(self._channel_names(dlg)), ["Canal+", "TF1 HD"])

    def test_categories_only_contain_filtered_live_channels(self):
        """Les catégories sont filtrées : jamais de groupe VOD dans ce sélecteur."""
        dlg = ChannelPickerDialog(self.db, playlist_id=self.pl_id)
        scopes = self._scope_keys(dlg)

        self.assertIn(f"{ChannelPickerDialog.CATEGORY_PREFIX}FR | TNT", scopes)
        self.assertIn(f"{ChannelPickerDialog.CATEGORY_PREFIX}FR | CINE", scopes)
        self.assertNotIn(f"{ChannelPickerDialog.CATEGORY_PREFIX}VOD | Films", scopes)

    def test_category_scope_filters_channels(self):
        dlg = ChannelPickerDialog(self.db, playlist_id=self.pl_id)
        self._select_scope(dlg, f"{ChannelPickerDialog.CATEGORY_PREFIX}FR | CINE")
        self.assertEqual(self._channel_names(dlg), ["Canal+"])

    def test_all_channels_scope_lists_live_channels(self):
        dlg = ChannelPickerDialog(self.db, playlist_id=self.pl_id)
        self._select_scope(dlg, ChannelPickerDialog.SCOPE_ALL)
        self.assertEqual(
            sorted(self._channel_names(dlg)), ["Canal+", "France 2 HD", "TF1 HD"]
        )

    def test_search_filters_within_selected_scope(self):
        dlg = ChannelPickerDialog(self.db, playlist_id=self.pl_id)
        self._select_scope(dlg, f"{ChannelPickerDialog.CATEGORY_PREFIX}FR | TNT")
        self.assertEqual(sorted(self._channel_names(dlg)), ["France 2 HD", "TF1 HD"])

        dlg.search_edit.setText("france")
        self.assertEqual(self._channel_names(dlg), ["France 2 HD"])

        dlg.search_edit.setText("")
        self.assertEqual(len(self._channel_names(dlg)), 2)

    def test_select_button_returns_current_channel(self):
        dlg = ChannelPickerDialog(self.db, playlist_id=self.pl_id)
        self._select_scope(dlg, f"{ChannelPickerDialog.CATEGORY_PREFIX}FR | CINE")
        dlg._on_select_clicked()
        self.assertIsNotNone(dlg.selected_channel)
        self.assertEqual(dlg.selected_channel.name, "Canal+")


if __name__ == "__main__":
    unittest.main()
