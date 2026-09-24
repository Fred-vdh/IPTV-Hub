import sys
import unittest
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class TestFullscreenTransitions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.win = QMainWindow()
        self.win.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.win.resize(1000, 600)
        central = QWidget()
        self.win.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.label = QLabel("Test")
        layout.addWidget(self.label)
        self.win.show()
        QApplication.processEvents()

    def tearDown(self):
        self.win.close()
        del self.win

    def test_fullscreen_from_maximized_and_return(self):
        # 1. Maximiser la fenêtre
        self.win.showMaximized()
        QApplication.processEvents()
        self.assertTrue(self.win.isMaximized())

        # 2. Passer en plein écran
        self.win.showFullScreen()
        QApplication.processEvents()
        self.assertTrue(self.win.isFullScreen())

        # 3. Revenir directement en maximisé
        self.win.showMaximized()
        QApplication.processEvents()
        self.assertTrue(self.win.isMaximized())
        self.assertFalse(self.win.isFullScreen())

    def test_fullscreen_from_normal_and_return(self):
        # 1. Fenêtre normale
        self.win.showNormal()
        QApplication.processEvents()
        self.assertFalse(self.win.isFullScreen())
        self.assertFalse(self.win.isMaximized())

        # 2. Plein écran
        self.win.showFullScreen()
        QApplication.processEvents()
        self.assertTrue(self.win.isFullScreen())

        # 3. Retour en normal
        self.win.showNormal()
        QApplication.processEvents()
        self.assertFalse(self.win.isFullScreen())
        self.assertFalse(self.win.isMaximized())

    def test_mainwindow_fullscreen_debounce(self):
        from ui.main_window import MainWindow
        import time
        main_win = MainWindow()
        if main_win._startup_fs_timer:
            main_win._startup_fs_timer.stop()
            main_win._startup_fs_timer = None
        main_win.is_fullscreen = False
        main_win.settings.window_fullscreen = False
        main_win.showNormal()
        main_win.show()
        QApplication.processEvents()
        self.assertTrue(main_win.isVisible())
        self.assertFalse(main_win.is_fullscreen)
        self.assertFalse(main_win.isFullScreen())

        # 1er appel : bascule en plein écran
        main_win.toggle_fullscreen()
        QApplication.processEvents()
        self.assertTrue(main_win.is_fullscreen)
        self.assertTrue(main_win.isVisible())

        # 2ème appel immédiat (< 400ms) : ignoré par le debounce pour éviter tout masquage/conflit
        main_win.toggle_fullscreen()
        QApplication.processEvents()
        self.assertTrue(main_win.is_fullscreen)  # Reste plein écran sans disparaître
        self.assertTrue(main_win.isVisible())

        # Attendre la fin du délai debounce
        time.sleep(0.55)

        # 3ème appel après debounce : retour propre en mode fenêtré
        main_win.toggle_fullscreen()
        QApplication.processEvents()
        self.assertFalse(main_win.is_fullscreen)
        self.assertTrue(main_win.isVisible())
        self.assertTrue(main_win.geometry().isValid())
        main_win.close()

    def test_video_widget_double_click_suppresses_single_click_and_bounces(self):
        """Vérifie qu'un double-clic sur la vidéo déclenche le plein écran sans jamais émettre de play/pause intempestif."""
        from ui.widgets.mpv_widget import MPVVideoWidget
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF, QEvent
        import time

        widget = MPVVideoWidget()
        widget.resize(800, 600)
        widget.controls.has_active_media = True
        widget.show()
        QApplication.processEvents()

        fs_events = []
        pp_events = []
        widget.fullscreen_requested.connect(lambda: fs_events.append(True))
        widget.play_pause_requested.connect(lambda: pp_events.append(True))

        center = widget.rect().center()
        global_center = widget.mapToGlobal(center)
        p_pt = QPointF(float(center.x()), float(center.y()))
        p_global = QPointF(float(global_center.x()), float(global_center.y()))

        # 1. Premier clic : Press puis Release
        press1 = QMouseEvent(QEvent.Type.MouseButtonPress, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, press1)

        release1 = QMouseEvent(QEvent.Type.MouseButtonRelease, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, release1)

        self.assertTrue(widget._click_timer.isActive())

        # 2. Deuxième clic rapide (cadence normale de double-clic, ex. 150ms)
        time.sleep(0.15)
        dbl = QMouseEvent(QEvent.Type.MouseButtonDblClick, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, dbl)

        # Vérifier que le timer de simple clic a été immédiatement annulé
        self.assertFalse(widget._click_timer.isActive())
        self.assertEqual(len(fs_events), 1)
        self.assertEqual(len(pp_events), 0)

        # 3. Deuxième release du double-clic (rebond potentiel)
        release2 = QMouseEvent(QEvent.Type.MouseButtonRelease, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, release2)

        # Le deuxième release ne doit pas avoir réactivé le timer
        self.assertFalse(widget._click_timer.isActive())

        # 4. Attendre au-delà de l'intervalle de timer pour s'assurer qu'aucun play/pause retardé ne part
        time.sleep(0.6)
        QApplication.processEvents()

        self.assertEqual(len(fs_events), 1)
        self.assertEqual(len(pp_events), 0, "Un simple clic (play/pause) a été émis lors d'un double-clic !")

        widget.close()


if __name__ == "__main__":
    unittest.main()
