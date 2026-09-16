"""
Tests unitaires pour l'animation de chargement/buffering et la détection
de ralentissement/gel de flux avec transition vers le message d'erreur.
"""

import sys
import time
import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter

from core.models import Channel
from core.player_controller import PlayerController
from ui.widgets.stream_buffering_indicator import StreamBufferingIndicator, OrbitalPulseGraphic
from ui.widgets.player_controls import PlayerControls
from ui.widgets.mpv_widget import MPVVideoWidget


class TestStreamBufferingAndError(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_buffering_indicator_lifecycle(self):
        """Vérifie le cycle de vie, le timer de délai et la visibilité de StreamBufferingIndicator."""
        indicator = StreamBufferingIndicator()
        self.assertFalse(indicator.isVisible())
        self.assertFalse(indicator._timer.isActive())
        self.assertFalse(indicator._delay_timer.isActive())

        # Démarrage avec délai de grâce par défaut (1.5s)
        indicator.start(delay_ms=1500)
        self.assertTrue(indicator._delay_timer.isActive())
        self.assertFalse(indicator.isVisible())  # Reste masqué pendant le délai

        # Si le chargement réussit vite et s'arrête avant 1.5s
        indicator.stop()
        self.assertFalse(indicator._delay_timer.isActive())
        self.assertFalse(indicator.isVisible())
        self.assertFalse(indicator._timer.isActive())

        # Démarrage immédiat (ou expiration du délai)
        indicator.start(delay_ms=0)
        self.assertTrue(indicator.isVisible())
        self.assertTrue(indicator._timer.isActive())

        # Arrêt
        indicator.stop()
        self.assertFalse(indicator.isVisible())
        self.assertFalse(indicator._timer.isActive())

    def test_orbital_pulse_graphic_rendering(self):
        """Vérifie que le rendu vectoriel QPainter ne provoque aucune exception."""
        graphic = OrbitalPulseGraphic()
        graphic.update_animation(16.0)

        pixmap = QPixmap(74, 74)
        painter = QPainter(pixmap)
        try:
            graphic.render(painter)
        finally:
            painter.end()

        self.assertFalse(pixmap.isNull())

    def test_player_controls_buffering_and_error_states(self):
        """Vérifie l'affichage exclusif entre l'animation de chargement et la bannière d'erreur."""
        controls = PlayerControls()
        controls.show()
        live_channel = Channel(id=1, name="Canal Live 1", stream_type="live")
        controls.update_channel_info(live_channel)

        # 1. État buffering (déclenchement avec délai)
        controls.set_playing_state("buffering")
        self.assertTrue(controls.is_buffering)
        self.assertFalse(controls.is_error)
        self.assertTrue(controls.buffering_indicator._delay_timer.isActive())
        # Simulation de l'expiration du délai de chargement
        controls.buffering_indicator._show_and_run()
        self.assertFalse(controls.buffering_indicator.isHidden())
        self.assertTrue(controls.buffering_indicator._timer.isActive())
        self.assertTrue(controls.error_banner.isHidden())
        self.assertEqual(controls.badge_live.text(), "DIRECT")

        # 2. État playing (reprise normale)
        controls.set_playing_state("playing")
        self.assertFalse(controls.is_buffering)
        self.assertTrue(controls.is_playing)
        self.assertTrue(controls.buffering_indicator.isHidden())
        self.assertFalse(controls.buffering_indicator._timer.isActive())
        self.assertTrue(controls.error_banner.isHidden())
        self.assertEqual(controls.badge_live.text(), "DIRECT")

        # 3. État error (flux mort)
        controls.set_playing_state("error")
        self.assertFalse(controls.is_buffering)
        self.assertTrue(controls.is_error)
        self.assertTrue(controls.buffering_indicator.isHidden())
        self.assertFalse(controls.buffering_indicator._timer.isActive())
        self.assertFalse(controls.error_banner.isHidden())
        self.assertEqual(controls.badge_live.text(), "INDISPONIBLE")

        # 4. État VOD en buffering
        vod_channel = Channel(id=2, name="Film Test", stream_type="movie")
        controls.update_channel_info(vod_channel)
        controls.set_playing_state("buffering")
        self.assertEqual(controls.badge_live.text(), "FILM")
        controls.buffering_indicator._show_and_run()
        self.assertFalse(controls.buffering_indicator.isHidden())

    def test_player_controller_stall_detection_and_recovery(self):
        """Vérifie la détection de gel dans PlayerController, la reprise et le timeout d'erreur."""
        controller = PlayerController(render_mode=True)
        controller._player = MagicMock()
        controller._current_url = "http://fake-stream/live.ts"
        controller._stream_has_started = True
        controller._set_state("playing")

        emitted_states = []
        controller.state_changed.connect(lambda s: emitted_states.append(s))

        emitted_errors = []
        controller.error_occurred.connect(lambda e: emitted_errors.append(e))

        # Simulation de lecture normale
        controller._last_progress_monotonic = time.monotonic()
        controller._on_stall_monitor_tick()
        self.assertEqual(controller._current_state, "playing")

        # Simulation d'un gel (aucune progression depuis 3.5s)
        controller._last_progress_monotonic = time.monotonic() - 3.5
        controller._on_stall_monitor_tick()
        self.assertEqual(controller._current_state, "buffering")
        self.assertIn("buffering", emitted_states)

        # Reprise du flux (nouvelle frame reçue via _on_time_pos)
        controller._on_time_pos("time-pos", 12.5)
        self.assertEqual(controller._current_state, "playing")
        self.assertIsNone(controller._stall_start_monotonic)

        # Nouveau gel qui persiste plus de 12 secondes
        controller._last_progress_monotonic = time.monotonic() - 3.5
        controller._on_stall_monitor_tick()
        self.assertEqual(controller._current_state, "buffering")

        # Simuler un gel continu de 12.5 secondes
        controller._stall_start_monotonic = time.monotonic() - 12.5
        controller._on_stall_monitor_tick()
        self.assertEqual(controller._current_state, "error")
        self.assertIn("Flux indisponible", emitted_errors)

        controller.cleanup()

    def test_player_controller_paused_for_cache(self):
        """Vérifie que la notification paused-for-cache de MPV bascule l'état correctement."""
        controller = PlayerController(render_mode=True)
        controller._player = MagicMock()
        controller._current_url = "http://fake-stream/vod.mp4"
        controller._stream_has_started = True
        controller._set_state("playing")

        # MPV signale le besoin de mise en cache
        controller._on_paused_for_cache("paused-for-cache", True)
        self.assertEqual(controller._current_state, "buffering")

        # MPV signale que le cache est reconstitué
        controller._on_paused_for_cache("paused-for-cache", False)
        self.assertEqual(controller._current_state, "playing")

        controller.cleanup()

    def test_mpv_widget_buffering_coordination(self):
        """Vérifie la coordination dans MPVVideoWidget lors de l'état buffering."""
        controller = PlayerController(render_mode=True)
        widget = MPVVideoWidget(player_controller=controller)
        widget.show()

        channel = Channel(id=10, name="Chaîne Test", stream_type="live")
        widget.controls.update_channel_info(channel)

        # Passage en buffering
        controller._set_state("buffering")
        self.assertEqual(widget.stack.currentIndex(), 1)
        self.assertFalse(widget.controls.isHidden())
        widget.controls.buffering_indicator._show_and_run()
        self.assertFalse(widget.controls.buffering_indicator.isHidden())

        # Passage en error
        controller._set_state("error")
        self.assertFalse(widget.controls.error_banner.isHidden())
        self.assertTrue(widget.controls.buffering_indicator.isHidden())

        widget.close()
        controller.cleanup()


if __name__ == "__main__":
    unittest.main()
