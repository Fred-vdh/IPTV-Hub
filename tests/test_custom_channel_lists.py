"""
Tests unitaires pour les listes de chaînes personnalisées (ex: Salon HD, Van SD),
leur gestion en base de données, l'affichage dans les catégories et la synchronisation multi-machines.
"""

import unittest
import tempfile
from pathlib import Path

from core.database import Database
from core.models import Channel, Playlist
from core.sync_manager import export_sync_data, merge_sync_data


class TestCustomChannelLists(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_iptv.db")
        self.db = Database(self.db_path)

        # Création d'une playlist et de quelques chaînes
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
            name="TF1 SD",
            stream_url="http://example.com/live/tf1_sd.m3u8",
            stream_id="102",
            group_title="FR | TNT SD",
            stream_type="live"
        )
        self.ch3 = Channel(
            playlist_id=self.pl_id,
            name="France 2 HD",
            stream_url="http://example.com/live/fr2_hd.m3u8",
            stream_id="201",
            group_title="FR | TNT",
            stream_type="live"
        )
        self.db.save_channels_batch(self.pl_id, [self.ch1, self.ch2, self.ch3])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_get_custom_lists(self):
        """Vérifie la création et la récupération des listes personnalisées."""
        list_salon_id = self.db.create_custom_channel_list("Salon HD")
        list_van_id = self.db.create_custom_channel_list("Van SD")
        self.assertIsNotNone(list_van_id)

        lists = self.db.get_custom_channel_lists()
        self.assertEqual(len(lists), 2)
        names = [cl["name"] for cl in lists]
        self.assertIn("Salon HD", names)
        self.assertIn("Van SD", names)

        # Créer à nouveau une liste avec le même nom retourne l'id existant
        same_id = self.db.create_custom_channel_list("Salon HD")
        self.assertEqual(list_salon_id, same_id)

    def test_add_and_remove_channels(self):
        """Vérifie l'ajout, le statut d'appartenance et le retrait de chaînes dans une liste."""
        list_id = self.db.create_custom_channel_list("Salon HD")

        # Ajout de TF1 HD et France 2 HD
        self.assertTrue(self.db.add_channel_to_custom_list(list_id, self.ch1))
        self.assertTrue(self.db.add_channel_to_custom_list(list_id, self.ch3))

        # Vérification d'appartenance
        self.assertTrue(self.db.is_channel_in_custom_list(list_id, self.ch1))
        self.assertTrue(self.db.is_channel_in_custom_list(list_id, self.ch3))
        self.assertFalse(self.db.is_channel_in_custom_list(list_id, self.ch2))

        # Récupération des IDs de listes pour une chaîne
        ids = self.db.get_channel_custom_list_ids(self.ch1)
        self.assertIn(list_id, ids)

        # Récupération des chaînes de la liste
        channels = self.db.get_channels_for_custom_list(list_id)
        self.assertEqual(len(channels), 2)
        channel_names = [c.name for c in channels]
        self.assertIn("TF1 HD", channel_names)
        self.assertIn("France 2 HD", channel_names)

        # Compteurs de chaînes
        counts = self.db.get_custom_channel_lists_with_counts()
        self.assertEqual(len(counts), 1)
        self.assertEqual(counts[0][1], "Salon HD")
        self.assertEqual(counts[0][2], 2)

        # Retrait d'une chaîne
        self.assertTrue(self.db.remove_channel_from_custom_list(list_id, self.ch1))
        self.assertFalse(self.db.is_channel_in_custom_list(list_id, self.ch1))
        channels_after = self.db.get_channels_for_custom_list(list_id)
        self.assertEqual(len(channels_after), 1)
        self.assertEqual(channels_after[0].name, "France 2 HD")

    def test_rename_and_delete_custom_list(self):
        """Vérifie le renommage et la suppression d'une liste personnalisée."""
        list_id = self.db.create_custom_channel_list("Mes Favoris Perso")
        self.db.add_channel_to_custom_list(list_id, self.ch1)

        # Renommer
        success = self.db.rename_custom_channel_list(list_id, "Salon HD VIP")
        self.assertTrue(success)

        info = self.db.get_custom_channel_list_by_id(list_id)
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "Salon HD VIP")

        # Supprimer
        self.assertTrue(self.db.delete_custom_channel_list(list_id))
        self.assertIsNone(self.db.get_custom_channel_list_by_id(list_id))
        self.assertEqual(len(self.db.get_custom_channel_lists()), 0)

    def test_sync_custom_lists_between_devices(self):
        """
        Simule la synchronisation entre l'appareil Salon (créateur de Salon HD)
        et l'appareil Van (créateur de Van SD), pour s'assurer que les deux listes fusionnent sans conflit.
        """
        # Machine A (Salon)
        salon_list_id = self.db.create_custom_channel_list("Salon HD")
        self.db.add_channel_to_custom_list(salon_list_id, self.ch1)
        self.db.add_channel_to_custom_list(salon_list_id, self.ch3)

        # Export depuis Salon
        salon_payload = export_sync_data(self.db)
        self.assertIn("custom_channel_lists", salon_payload)
        self.assertEqual(len(salon_payload["custom_channel_lists"]), 1)
        self.assertEqual(salon_payload["custom_channel_lists"][0]["name"], "Salon HD")
        self.assertEqual(len(salon_payload["custom_channel_lists"][0]["items"]), 2)

        # Machine B (Van) dans une autre base
        van_db_path = str(Path(self.temp_dir.name) / "van_iptv.db")
        van_db = Database(van_db_path)
        van_pl_id = van_db.add_playlist(Playlist(name="Van Playlist", url_or_path="http://example.com/playlist.m3u"))
        van_db.save_channels_batch(van_pl_id, [self.ch1, self.ch2, self.ch3])

        van_list_id = van_db.create_custom_channel_list("Van SD")
        van_db.add_channel_to_custom_list(van_list_id, self.ch2)

        # Synchronisation : import du payload Salon sur la machine Van
        stats = merge_sync_data(van_db, salon_payload)
        self.assertGreaterEqual(stats["custom_lists_added"], 1)

        # Vérification sur Machine B (Van) : elle possède maintenant TOUTES les deux listes !
        van_lists = van_db.get_custom_channel_lists()
        self.assertEqual(len(van_lists), 2)
        van_list_names = {cl["name"] for cl in van_lists}
        self.assertIn("Salon HD", van_list_names)
        self.assertIn("Van SD", van_list_names)

        # Vérifier que les chaînes de "Salon HD" sont bien accessibles sur Van
        salon_list_on_van = next(cl for cl in van_lists if cl["name"] == "Salon HD")
        salon_channels_on_van = van_db.get_channels_for_custom_list(salon_list_on_van["id"])
        self.assertEqual(len(salon_channels_on_van), 2)
        ch_names = {c.name for c in salon_channels_on_van}
        self.assertIn("TF1 HD", ch_names)
        self.assertIn("France 2 HD", ch_names)

        # Vérifier que "Van SD" a conservé sa chaîne "TF1 SD"
        van_list_local = next(cl for cl in van_lists if cl["name"] == "Van SD")
        van_channels = van_db.get_channels_for_custom_list(van_list_local["id"])
        self.assertEqual(len(van_channels), 1)
        self.assertEqual(van_channels[0].name, "TF1 SD")

    def test_stream_id_collision_across_stream_types(self):
        """Vérifie qu'un stream_id identique entre un canal live et une série/VOD n'écrase pas le canal."""
        # Ajouter une série avec le même stream_id que self.ch1 ("101")
        series_ch = Channel(
            playlist_id=self.pl_id,
            name="Orange Is the New Black",
            stream_url="http://example.com/series/orange.m3u8",
            stream_id="101",
            group_title="Series | Drama",
            stream_type="series"
        )
        self.db.save_channels_batch(self.pl_id, [series_ch])

        # Créer une liste personnalisée contenant self.ch1 (TF1 HD, stream_type="live", stream_id="101")
        list_id = self.db.create_custom_channel_list("Test Collision")
        self.db.add_channel_to_custom_list(list_id, self.ch1)

        # Récupération des chaînes de la liste
        channels = self.db.get_channels_for_custom_list(list_id)
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0].name, "TF1 HD")
        self.assertEqual(channels[0].stream_type, "live")
        self.assertNotEqual(channels[0].name, "Orange Is the New Black")


if __name__ == "__main__":
    unittest.main()

