"""
Tests d'intégration de la sortie du mode Multiview depuis la fenêtre principale.

Reproduit la demande :
  * « quand on quitte la TV en direct, tous les écrans Multiview doivent être
    désactivés ; il ne reste que l'écran de base » ;
  * le bouton « Quitter Multiview » doit toujours réagir.

Aucun lecteur libmpv réel n'est créé : les écrans sont alimentés par des chaînes
factices (sans lecteur) et play_channel() est neutralisé pour la reprise en solo.
"""

import os
import sys
import unittest

from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.mpv_setup import setup_mpv_environment

setup_mpv_environment()

from core.models import Channel  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


class TestMultiViewExitIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = MainWindow()
        self.mv = self.window.multiview_widget

    def tearDown(self):
        try:
            self.window.close()
        except Exception:
            pass

    @staticmethod
    def _fake_channel(name: str = "TF1 HD", sid: str = "101") -> Channel:
        return Channel(
            playlist_id=1,
            name=name,
            stream_url=f"http://example.com/live/{sid}.m3u8",
            stream_id=sid,
            group_title="FR | TNT",
            stream_type="live",
        )

    def test_leaving_multiview_restores_base_screen(self):
        """« Quitter Multiview » désactive tous les écrans et revient à l'écran de base."""
        self.window.activate_multiview()
        self.assertEqual(self.window.player_stack.currentIndex(), 1)
        self.assertTrue(self.mv.is_active)

        self.window._on_multiview_exit(None)

        self.assertEqual(self.window.player_stack.currentIndex(), 0)
        self.assertFalse(self.mv.is_active)
        self.assertFalse(self.mv.has_running_slots())

    def test_section_change_deactivates_every_multiview_screen(self):
        """Changer de section quitte la TV en direct : plus aucun écran Multiview actif."""
        self.window.activate_multiview()
        self.mv.slots[0].channel = self._fake_channel()

        self.window._on_section_changed("dashboard")

        self.assertEqual(self.window.player_stack.currentIndex(), 0)
        self.assertFalse(self.mv.is_active)
        self.assertIsNone(self.mv.slots[0].channel)
        self.assertFalse(self.mv.has_running_slots())

    def test_returning_to_live_resumes_focused_channel(self):
        """Revenir sur « TV en direct » reprend en solo la chaîne qui avait le focus."""
        self.window.activate_multiview()
        ch = self._fake_channel()
        self.mv.slots[0].channel = ch
        self.mv.active_slot_idx = 0

        played = []
        self.window.play_channel = lambda channel, start_time=None: played.append(channel)

        self.window._on_section_changed("live")

        self.assertEqual(played, [ch])
        self.assertFalse(self.mv.is_active)
        self.assertIsNone(self.mv.slots[0].channel)
        self.assertFalse(self.mv.has_running_slots())

    # ------------------------------------------------------------------ non-régression
    # Bug constaté : après une lecture dans une fiche (série/film/bande-annonce),
    # le lecteur était réinséré directement dans right_container.layout() au lieu
    # de player_stack. L'écran se retrouvait scindé (lecteur en haut à pleine
    # largeur + Multiview en bas) et le Multiview ne répondait plus.

    def test_video_widget_lives_in_player_stack_by_default(self):
        """État initial : le lecteur occupe la page 0 de player_stack, pas right_container."""
        self.assertEqual(self.window.player_stack.widget(0), self.window.video_widget)
        self.assertEqual(self.window.player_stack.widget(1), self.mv)
        self.assertEqual(self.window.right_container.layout().indexOf(self.window.video_widget), -1)

    def test_reattach_is_noop_while_playing_in_details(self):
        """Pendant la lecture en fiche, le lecteur reste détenu par la fiche."""
        self.window._is_playing_series_in_details = True
        self.window.player_stack.removeWidget(self.window.video_widget)

        self.window._reattach_video_widget()

        self.assertEqual(self.window.player_stack.indexOf(self.window.video_widget), -1)

    def test_video_widget_returns_to_player_stack_after_details(self):
        """Après la lecture en fiche, le lecteur revient dans player_stack (page 0)."""
        self.window._is_playing_series_in_details = True
        self.window.player_stack.removeWidget(self.window.video_widget)
        self.window._is_playing_series_in_details = False

        self.window._reattach_video_widget()

        self.assertEqual(self.window.player_stack.indexOf(self.window.video_widget), 0)
        self.assertEqual(self.window.player_stack.widget(1), self.mv)
        self.assertEqual(self.window.player_stack.currentWidget(), self.window.video_widget)
        # Le lecteur ne doit JAMAIS être inséré directement dans right_container.
        self.assertEqual(self.window.right_container.layout().indexOf(self.window.video_widget), -1)

    def test_multiview_still_closable_after_details_roundtrip(self):
        """Scénario signalé : fiche → TV en direct. Le Multiview doit rester fermable."""
        # Simule la fin d'une lecture en fiche (le lecteur avait été détaché).
        self.window._is_playing_series_in_details = True
        self.window.player_stack.removeWidget(self.window.video_widget)
        self.window._is_playing_series_in_details = False
        self.window._reattach_video_widget()

        # Le Multiview est activé puis quitté : le bouton doit toujours réagir.
        self.window.activate_multiview()
        self.assertEqual(self.window.player_stack.currentIndex(), 1)

        self.window._on_multiview_exit(None)

        self.assertEqual(self.window.player_stack.currentIndex(), 0)
        self.assertEqual(self.window.player_stack.currentWidget(), self.window.video_widget)
        self.assertFalse(self.mv.is_active)


if __name__ == "__main__":
    unittest.main()
