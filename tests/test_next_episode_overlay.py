import os
import sys
import unittest
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.widgets.next_episode_overlay import NextEpisodeOverlay


class TestNextEpisodeOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.overlay = NextEpisodeOverlay()

    def tearDown(self):
        self.overlay.close()

    def test_initial_state(self):
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(self.overlay.total_seconds, 10)
        self.assertEqual(self.overlay.seconds_left, 10)

    def test_start_countdown_and_signals(self):
        next_req = []
        cancelled = []
        self.overlay.play_next_requested.connect(lambda: next_req.append(True))
        self.overlay.cancelled.connect(lambda: cancelled.append(True))

        self.overlay.setup_episode("S01E02 - Le commencement", duration_sec=5)
        self.overlay.start_countdown(5)
        self.assertTrue(self.overlay.isVisible())
        self.assertIn("S01E02 - Le commencement", self.overlay.title_lbl.text())

        # Test cancel button
        self.overlay.btn_cancel.click()
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(len(next_req), 0)

    def test_countdown_play_now(self):
        next_req = []
        self.overlay.play_next_requested.connect(lambda: next_req.append(True))

        self.overlay.setup_episode("S01E03", duration_sec=10)
        self.overlay.start_countdown(10)
        self.overlay.btn_play_now.click()

        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(len(next_req), 1)

    def test_countdown_timer_tick_and_auto_trigger(self):
        next_req = []
        self.overlay.play_next_requested.connect(lambda: next_req.append(True))

        self.overlay.setup_episode("S01E04", duration_sec=1)
        self.overlay.start_countdown(1)
        self.assertEqual(self.overlay.seconds_left, 1)

        # Simuler le tick du timer
        self.overlay._on_tick()
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(len(next_req), 1)

    def test_pause_and_resume_countdown(self):
        self.overlay.start_countdown(10)
        self.assertTrue(self.overlay.countdown_timer.isActive())

        self.overlay.pause_countdown()
        self.assertFalse(self.overlay.countdown_timer.isActive())
        self.assertTrue(self.overlay._is_paused)

        self.overlay.resume_countdown()
        self.assertTrue(self.overlay.countdown_timer.isActive())
        self.assertFalse(self.overlay._is_paused)

    def test_multilingual_retranslate(self):
        from core.i18n import set_language

        # En Français
        set_language('fr')
        self.overlay.retranslate_ui()
        self.assertIn("Épisode suivant", self.overlay.header_lbl.text())
        self.assertIn("Lire maintenant", self.overlay.btn_play_now.text())
        self.assertIn("Annuler", self.overlay.btn_cancel.text())

        # En Anglais
        set_language('en')
        self.overlay.retranslate_ui()
        self.assertIn("Next episode", self.overlay.header_lbl.text())
        self.assertIn("Play Now", self.overlay.btn_play_now.text())
        self.assertIn("Cancel", self.overlay.btn_cancel.text())

        # En Espagnol
        set_language('es')
        self.overlay.retranslate_ui()
        self.assertIn("Episodio siguiente", self.overlay.header_lbl.text())
        self.assertIn("Reproducir ahora", self.overlay.btn_play_now.text())
        self.assertIn("Cancelar", self.overlay.btn_cancel.text())

        # En Allemand
        set_language('de')
        self.overlay.retranslate_ui()
        self.assertIn("Nächste Folge", self.overlay.header_lbl.text())
        self.assertIn("Jetzt abspielen", self.overlay.btn_play_now.text())
        self.assertIn("Abbrechen", self.overlay.btn_cancel.text())

        # Restaurer français
        set_language('fr')

    def test_zero_perturbation_policy(self):
        """Vérifie la règle de non-perturbation :
        Aucune boîte de dialogue n'est affichée si IntroDB ne possède pas de marqueur précis.
        """
        from unittest.mock import MagicMock
        from PyQt6.QtWidgets import QMainWindow
        from core.models import Channel
        from ui.main_window import MainWindow

        win = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(win)
        win._current_playback_pos = 0.0
        win._current_playback_dur = 3600.0
        win._last_progress_saved_time = 0.0
        win._current_outro_start_sec = None
        win._outro_overlay_cancelled = False
        win.current_channel = Channel(id=1, name="S01E01", stream_type="series", stream_url="http://test/1.mp4")
        win._series_episodes = [
            Channel(id=1, name="S01E01", stream_type="series", stream_url="http://test/1.mp4"),
            Channel(id=2, name="S01E02", stream_type="series", stream_url="http://test/2.mp4")
        ]
        win._current_series_idx = 0
        win.settings = MagicMock(
            auto_play_next_episode=True,
            introdb_outro_skip=True
        )
        win.db = MagicMock()
        win.video_widget = MagicMock()
        win.video_widget.next_ep_overlay = self.overlay

        # 1. Pas d'outro IntroDB -> aucune perturbation, overlay reste masqué
        win._on_player_time_pos_changed(1800.0)
        self.assertFalse(self.overlay.isVisible())

        # 2. Outro présent à 2500s, position à 2400s -> pas encore le générique, overlay masqué
        win._current_outro_start_sec = 2500.0
        win._on_player_time_pos_changed(2400.0)
        self.assertFalse(self.overlay.isVisible())

        # 3. Position atteint 2500.5s -> début du générique détecté avec précision -> overlay affiché !
        win._on_player_time_pos_changed(2500.5)
        self.assertTrue(self.overlay.isVisible())
        self.assertEqual(self.overlay.seconds_left, 10)

        # 4. L'utilisateur annule -> ne doit plus réapparaître
        win._on_outro_next_episode_cancelled()
        self.assertFalse(self.overlay.isVisible())
        self.assertTrue(win._outro_overlay_cancelled)

        win._on_player_time_pos_changed(2510.0)
        self.assertFalse(self.overlay.isVisible())

        # 5. Si l'option introdb_outro_skip est désactivée dans les paramètres -> jamais d'overlay
        win._outro_overlay_cancelled = False
        win.settings.introdb_outro_skip = False
        win._on_player_time_pos_changed(2520.0)
        self.assertFalse(self.overlay.isVisible())


if __name__ == '__main__':
    unittest.main()
