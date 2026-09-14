import sys
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QMouseEvent

from unittest.mock import MagicMock
from ui.widgets.mpv_widget import MPVVideoWidget


class TestOSDMouseAndResize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.widget = MPVVideoWidget()
        self.widget.player = MagicMock()
        self.widget.player.mpv_handle = None
        self.widget.controls.has_active_media = True
        self.widget.controls.hide()
        self.widget._osd_suspended = False

    def tearDown(self):
        self.widget.close()

    def test_resize_does_not_show_osd(self):
        """Le redimensionnement de la fenêtre vidéo ne doit pas afficher l'OSD s'il était masqué."""
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))
        self.widget.resize(900, 600)
        self.widget._sync_geometry()
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))

    def test_single_click_does_not_show_osd(self):
        """Un simple clic ne doit pas réafficher l'OSD."""
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))
        self.widget._handle_single_click()
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))

    def test_mouse_press_release_does_not_show_osd(self):
        """Les événements de pression/relâchement de souris sans déplacement ne doivent pas afficher l'OSD."""
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100, 100),
            QPointF(100, 100),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        self.widget.eventFilter(self.widget.video_surface, press_event)
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))

    def test_mouse_move_shows_osd(self):
        """Le déplacement de la souris (plus de 4 pixels) doit afficher l'OSD."""
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))
        # Déplacement initial
        self.widget._last_mouse_pos = QPoint(100, 100)
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(150, 150),
            QPointF(150, 150),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        self.widget.eventFilter(self.widget.video_surface, move_event)
        self.assertTrue(self.widget.controls.isVisibleTo(self.widget))
        self.assertEqual(self.widget.cursor().shape(), Qt.CursorShape.ArrowCursor)

    def test_set_fullscreen_masks_cursor_automatically(self):
        """Le passage en plein écran avec média actif doit masquer automatiquement le curseur."""
        self.widget.set_fullscreen(True)
        self.assertEqual(self.widget.cursor().shape(), Qt.CursorShape.BlankCursor)
        self.assertEqual(self.widget.video_surface.cursor().shape(), Qt.CursorShape.BlankCursor)
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))

    def test_exit_fullscreen_restores_cursor(self):
        """La sortie du mode plein écran doit restaurer le curseur standard."""
        self.widget.set_fullscreen(True)
        self.assertEqual(self.widget.cursor().shape(), Qt.CursorShape.BlankCursor)
        self.widget.set_fullscreen(False)
        self.assertEqual(self.widget.cursor().shape(), Qt.CursorShape.ArrowCursor)
        self.assertEqual(self.widget.video_surface.cursor().shape(), Qt.CursorShape.ArrowCursor)

    def test_mouse_move_in_fullscreen_restores_cursor(self):
        """En plein écran avec curseur masqué, bouger la souris réaffiche l'OSD et le curseur."""
        self.widget.set_fullscreen(True)
        self.assertEqual(self.widget.cursor().shape(), Qt.CursorShape.BlankCursor)
        self.widget._last_mouse_pos = QPoint(100, 100)
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(150, 150),
            QPointF(150, 150),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        self.widget.eventFilter(self.widget.video_surface, move_event)
        self.assertTrue(self.widget.controls.isVisibleTo(self.widget))
        self.assertEqual(self.widget.cursor().shape(), Qt.CursorShape.ArrowCursor)

    def test_hide_osd_masks_cursor(self):
        """Le masquage après timeout d'inactivité masque l'OSD et le curseur."""
        self.widget._show_osd()
        self.assertTrue(self.widget.controls.isVisibleTo(self.widget))
        self.widget._hide_osd()
        self.assertFalse(self.widget.controls.isVisibleTo(self.widget))
        self.assertEqual(self.widget.cursor().shape(), Qt.CursorShape.BlankCursor)


if __name__ == "__main__":
    unittest.main()
