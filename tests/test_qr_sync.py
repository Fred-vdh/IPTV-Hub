"""
Tests unitaires pour le serveur et la passerelle de synchronisation QR.
"""

import unittest
import tempfile
import urllib.request
import urllib.error
import json
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from core.database import Database
from core.models import Playlist
from core.qr_sync_server import (
    get_local_ip_addresses,
    generate_qr_pixmap,
    QRSyncServer,
)

# Initialisation minimale de Qt pour les tests graphiques headless
app = QApplication.instance() or QApplication(["--platform", "offscreen"])


class TestQRSyncServer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_qr.db"
        self.db = Database(str(self.db_path))

        # Ajouter une playlist de test
        p = Playlist(name="Playlist QR Test", server_url="http://iptv.example.com", username="user1", password="pwd")
        self.db.add_playlist(p)

        self.server = QRSyncServer(self.db)

    def tearDown(self):
        if self.server:
            self.server.stop()
        self.temp_dir.cleanup()

    def test_ip_detection(self):
        ips = get_local_ip_addresses()
        self.assertIsInstance(ips, list)
        self.assertGreater(len(ips), 0)
        # Aucune IP loopback en tête si d'autres IPs existent
        if len(ips) > 1:
            self.assertFalse(ips[0].startswith("127."))
            self.assertFalse(ips[0].startswith("169.254."))

    def test_qr_pixmap_generation(self):
        url = "http://192.168.1.50:8989/?token=abcdef0123456789"
        pm = generate_qr_pixmap(url, size=200)
        self.assertFalse(pm.isNull())
        self.assertEqual(pm.width(), 200)
        self.assertEqual(pm.height(), 200)

    def test_server_lifecycle_and_http_endpoints(self):
        success, url = self.server.start(preferred_ip="127.0.0.1", base_port=9100)
        self.assertTrue(success)
        self.assertIn("token=", url)
        token = self.server.token

        base_url = f"http://127.0.0.1:{self.server.port}"

        # 1. Requête sans token -> 403 Forbidden
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{base_url}/")
        self.assertEqual(ctx.exception.code, 403)

        # 2. Requête avec mauvais token -> 403 Forbidden
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{base_url}/?token=badtoken")
        self.assertEqual(ctx.exception.code, 403)

        # 3. Requête GET / avec token valide -> 200 OK & HTML mobile
        req = urllib.request.Request(f"{base_url}/?token={token}")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode("utf-8")
            self.assertIn("Passerelle de synchronisation", html)
            self.assertIn("btnDownload", html)
            self.assertIn("btnUpload", html)

        # 4. Requête GET /api/export -> 200 OK & JSON
        req_export = urllib.request.Request(f"{base_url}/api/export?token={token}")
        with urllib.request.urlopen(req_export) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("playlists", data)
            self.assertEqual(len(data["playlists"]), 1)
            self.assertEqual(data["playlists"][0]["name"], "Playlist QR Test")

        # 5. Requête POST /api/import avec nouveau favori
        import_payload = {
            "metadata": {"device_name": "Mobile Test"},
            "persistent_favorites": [
                {
                    "name": "Canal+ Cinema",
                    "stream_url": "http://stream.cinema.ts",
                    "stream_id": "123",
                    "stream_type": "live",
                }
            ],
            "playback_progress": [
                {
                    "stream_url": "http://stream.cinema.ts",
                    "channel_name": "Canal+ Cinema",
                    "playback_position": 600.0,
                    "duration": 7200.0,
                    "updated_at": "2026-09-21T21:00:00",
                }
            ],
        }

        req_import = urllib.request.Request(
            f"{base_url}/api/import?token={token}",
            data=json.dumps(import_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req_import) as resp:
            self.assertEqual(resp.status, 200)
            res_data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res_data["success"])
            self.assertGreaterEqual(res_data["stats"]["favorites_added"], 1)

        # Vérification en base SQLite
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM persistent_favorites WHERE name = 'Canal+ Cinema'")
            row = cur.fetchone()
            self.assertIsNotNone(row)

        # 6. Arrêt propre du serveur
        self.server.stop()
        self.assertIsNone(self.server.server)

    def test_dialog_lifecycle_and_signals(self):
        from ui.dialogs.qr_sync_dialog import QRSyncDialog

        dlg = QRSyncDialog(self.db)
        self.assertIsNotNone(dlg.server.server)
        self.assertTrue(dlg.url_edit.text().startswith("http://"))
        self.assertFalse(dlg.qr_image_label.pixmap().isNull())

        # Test émission signal sync_completed
        received_stats = []
        dlg.sync_completed.connect(lambda s: received_stats.append(s))
        dlg.server.import_completed.emit({"favorites_added": 3})
        self.assertEqual(len(received_stats), 1)
        self.assertEqual(received_stats[0]["favorites_added"], 3)

        # Fermeture de la boîte de dialogue -> le serveur doit être éteint
        dlg.close()
        self.assertIsNone(dlg.server.server)

    def test_multilingual_support(self):
        from core.qr_sync_server import get_mobile_html
        from core.i18n import I18nManager, tr
        from ui.dialogs.qr_sync_dialog import QRSyncDialog

        # 1. Vérification HTML mobile en français et en anglais
        html_fr = get_mobile_html("PC-Test", "token123", lang="fr")
        self.assertIn("Passerelle de synchronisation", html_fr)
        self.assertIn("Sauvegarder cet appareil", html_fr)

        html_en = get_mobile_html("PC-Test", "token123", lang="en")
        self.assertIn("Sync Gateway", html_en)
        self.assertIn("Backup this device", html_en)

        # 2. Vérification du basculement dynamique de langue dans QRSyncDialog
        i18n = I18nManager.instance()
        old_lang = i18n.current_language

        try:
            i18n.set_language("en")
            dlg = QRSyncDialog(self.db)
            self.assertEqual(dlg.windowTitle(), "Sync Gateway")
            self.assertEqual(dlg.close_btn.text(), "Close")
            self.assertEqual(dlg.copy_btn.text(), "Copy")
            dlg.close()

            i18n.set_language("fr")
            self.assertEqual(tr("Passerelle de synchronisation"), "Passerelle de synchronisation")
            self.assertEqual(tr("Serveur actif"), "Serveur actif")
        finally:
            i18n.set_language(old_lang)


if __name__ == "__main__":
    unittest.main()
