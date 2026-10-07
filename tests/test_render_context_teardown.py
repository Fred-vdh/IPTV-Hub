"""
Tests de non-régression : ordre de destruction entre libmpv et le contexte de
rendu OpenGL.

libmpv impose (render.h) :
    "You must free the context with mpv_render_context_free() before the mpv
     core is destroyed. If this doesn't happen, undefined behavior will result."

Or l'application faisait exactement l'inverse : mpv_terminate_destroy() AVANT la
libération du mpv_render_context. Résultat : access violations natives aléatoires
(0xC0000005) à la fermeture de la fenêtre de lecture (et à la sortie des tests).
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication  # noqa: E402

# Référence IMPÉRATIVE : un QApplication collecté par le GC ferait ensuite
# échouer tout QWidget ("Must construct a QApplication before a QWidget").
_APP = QApplication.instance() or QApplication(sys.argv)

from ui.main_window import MainWindow  # noqa: E402
from ui.widgets.multiview_widget import MultiViewSlotWidget  # noqa: E402


class TestRenderContextTeardown(unittest.TestCase):
    def test_multiview_slot_frees_render_context_before_mpv_core(self):
        order = []
        player = MagicMock()
        surface = MagicMock()
        player.stop.side_effect = lambda: order.append("lecture_arretee")
        player.cleanup.side_effect = lambda: order.append("coeur_mpv_detruit")
        surface.cleanup_render_context.side_effect = lambda: order.append("contexte_rendu_libere")

        slot = MultiViewSlotWidget.__new__(MultiViewSlotWidget)
        slot.player = player
        slot.surface = surface

        slot.cleanup()

        self.assertEqual(
            order,
            ["lecture_arretee", "contexte_rendu_libere", "coeur_mpv_detruit"],
            "mpv_render_context_free() doit précéder la destruction du coeur mpv",
        )
        self.assertIsNone(slot.player)

    def test_multiview_slot_cleanup_tolerates_missing_player_and_surface(self):
        slot = MultiViewSlotWidget.__new__(MultiViewSlotWidget)
        slot.player = None
        slot.surface = None
        slot.cleanup()  # ne doit lever aucune exception

    def test_main_window_releases_video_surface_render_context(self):
        win = MainWindow.__new__(MainWindow)
        win.video_widget = MagicMock()

        win._release_video_render_contexts()

        win.video_widget.video_surface.cleanup_render_context.assert_called_once_with()

    def test_main_window_release_is_noop_without_video_surface(self):
        win = MainWindow.__new__(MainWindow)
        win.video_widget = None

        win._release_video_render_contexts()  # ne doit lever aucune exception


if __name__ == "__main__":
    unittest.main()
