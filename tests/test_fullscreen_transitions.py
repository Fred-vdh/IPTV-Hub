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



if __name__ == "__main__":
    unittest.main()
