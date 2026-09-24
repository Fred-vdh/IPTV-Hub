import os
import sys
import unittest
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.widgets.skip_intro_overlay import SkipIntroOverlay


class TestSkipIntroOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.overlay = SkipIntroOverlay()

    def tearDown(self):
        self.overlay.close()

    def test_initial_state(self):
        self.assertFalse(self.overlay.isVisible())
        self.assertIsNotNone(self.overlay.btn_skip)
        self.assertIsNotNone(self.overlay.btn_close)

    def test_skip_and_cancel_signals(self):
        skip_req = []
        cancelled = []
        self.overlay.skip_intro_requested.connect(lambda: skip_req.append(True))
        self.overlay.cancelled.connect(lambda: cancelled.append(True))

        self.overlay.show()
        self.assertTrue(self.overlay.isVisible())

        # Test clic sur le bouton "Passer le générique"
        self.overlay.btn_skip.click()
        self.assertEqual(len(skip_req), 1)
        self.assertEqual(len(cancelled), 0)

        # Test clic sur la croix [ ✕ ]
        self.overlay.btn_close.click()
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(len(cancelled), 1)

    def test_multilingual_retranslate(self):
        from core.i18n import set_language

        # En Français
        set_language('fr')
        self.overlay.retranslate_ui()
        self.assertEqual(self.overlay.btn_skip.text(), "Passer le générique")

        # En Anglais
        set_language('en')
        self.overlay.retranslate_ui()
        self.assertEqual(self.overlay.btn_skip.text(), "Skip Intro")

        # En Espagnol
        set_language('es')
        self.overlay.retranslate_ui()
        self.assertEqual(self.overlay.btn_skip.text(), "Saltar introducción")

        # En Allemand
        set_language('de')
        self.overlay.retranslate_ui()
        self.assertEqual(self.overlay.btn_skip.text(), "Intro überspringen")

        # Restaurer français
        set_language('fr')

    def test_zero_perturbation_and_integration(self):
        """Vérifie la règle de non-perturbation et le comportement dans MainWindow :
        - Aucun affichage sans segments certifiés IntroDB.
        - Affichage uniquement dans la plage [intro_start, intro_end].
        - Masquage automatique à la fin de l'intro.
        - Seek vers intro_end lors du clic.
        - Mémorisation de l'annulation via le bouton [ ✕ ].
        - Respect du paramètre utilisateur introdb_intro_skip.
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
        win._current_intro_start_sec = None
        win._current_intro_end_sec = None
        win._intro_overlay_cancelled = False
        win._current_outro_start_sec = None
        win._outro_overlay_cancelled = False
        win.current_channel = Channel(id=1, name="S01E01", stream_type="series", stream_url="http://test/1.mp4")
        win._series_episodes = [
            Channel(id=1, name="S01E01", stream_type="series", stream_url="http://test/1.mp4"),
            Channel(id=2, name="S01E02", stream_type="series", stream_url="http://test/2.mp4")
        ]
        win._current_series_idx = 0
        win.settings = MagicMock(
            introdb_intro_skip=True,
            auto_play_next_episode=True,
            introdb_outro_skip=True
        )
        win.db = MagicMock()
        win.player_controller = MagicMock()
        win.video_widget = MagicMock()
        win.video_widget.skip_intro_overlay = self.overlay

        # 1. Pas d'intro IntroDB -> zéro perturbation, overlay reste masqué
        win._on_player_time_pos_changed(60.0)
        self.assertFalse(self.overlay.isVisible())

        # 2. Intro définie de 120s à 180s. Avant 120s -> masqué
        win._current_intro_start_sec = 120.0
        win._current_intro_end_sec = 180.0
        win._on_player_time_pos_changed(50.0)
        self.assertFalse(self.overlay.isVisible())

        # 3. Position dans l'intervalle intro [120s, 180s[ -> l'overlay apparaît
        win._on_player_time_pos_changed(125.0)
        self.assertTrue(self.overlay.isVisible())

        # 4. Clic "Passer le générique" -> Seek instantané vers intro_end (180.0) et masquage
        win._on_skip_intro_requested()
        self.assertFalse(self.overlay.isVisible())
        win.player_controller.seek.assert_called_with(180.0, relative=False)

        # 5. Position dépasse la fin du générique (pos >= 180.0) -> masquage automatique
        self.overlay.show()
        win._on_player_time_pos_changed(180.5)
        self.assertFalse(self.overlay.isVisible())

        # 6. Annulation par l'utilisateur via [ ✕ ] -> ne doit plus réapparaître pendant cet épisode
        win._on_player_time_pos_changed(130.0)
        self.assertTrue(self.overlay.isVisible())
        win._on_skip_intro_cancelled()
        self.assertFalse(self.overlay.isVisible())
        self.assertTrue(win._intro_overlay_cancelled)

        win._on_player_time_pos_changed(140.0)
        self.assertFalse(self.overlay.isVisible())

        # 7. Si le paramètre introdb_intro_skip est désactivé -> zéro perturbation
        win._intro_overlay_cancelled = False
        win.settings.introdb_intro_skip = False
        win._on_player_time_pos_changed(135.0)
        self.assertFalse(self.overlay.isVisible())

    def test_overlay_positioning_and_event_filter(self):
        """Vérifie que l'overlay est positionné bien au-dessus de la barre OSD
        et que l'eventFilter de MPVVideoWidget ne bloque pas les clics et survols sur l'overlay.
        """
        from PyQt6.QtCore import Qt, QEvent, QPointF
        from PyQt6.QtGui import QMouseEvent
        from unittest.mock import MagicMock
        from ui.widgets.mpv_widget import MPVVideoWidget

        video_widget = MPVVideoWidget()
        video_widget.player = MagicMock()
        video_widget.resize(1280, 720)
        video_widget.show()
        video_widget.controls.has_active_media = True
        video_widget.skip_intro_overlay.show()
        video_widget._sync_geometry()

        # 1. Positionnement vertical : le bas de skip_intro_overlay doit être au moins à 130px du bas
        geom = video_widget.skip_intro_overlay.geometry()
        bottom_distance = video_widget.height() - (geom.y() + geom.height())
        self.assertGreaterEqual(bottom_distance, 130)

        # 2. Ordre Z : l'overlay doit être au-dessus des contrôles
        video_widget._show_osd()
        self.assertTrue(video_widget.skip_intro_overlay.isVisible())

        # 3. eventFilter : un événement sur skip_intro_overlay ou btn_skip ne doit PAS être intercepté (return False)
        press_ev = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        handled = video_widget.eventFilter(video_widget.skip_intro_overlay.btn_skip, press_ev)
        self.assertFalse(handled)

        video_widget.close()


if __name__ == '__main__':
    unittest.main()
