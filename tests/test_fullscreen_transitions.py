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
        if hasattr(main_win, "player_controller") and main_win.player_controller:
            main_win.player_controller.cleanup()
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

    def test_fullscreen_no_unnecessary_stylesheet_cascades(self):
        """Vérifie que toggle_fullscreen ne force pas de récursion CSS sur les conteneurs ancêtres."""
        from ui.main_window import MainWindow
        main_win = MainWindow()
        if main_win._startup_fs_timer:
            main_win._startup_fs_timer.stop()
            main_win._startup_fs_timer = None

        orig_cs_style = main_win.content_stack.styleSheet()
        orig_mcs_style = main_win.main_content_stack.styleSheet()
        orig_rc_style = main_win.right_container.styleSheet()

        main_win.show()
        QApplication.processEvents()

        # Bascule en plein écran
        main_win.toggle_fullscreen()
        QApplication.processEvents()

        # Les conteneurs ancêtres ne doivent PAS avoir reçu de setStyleSheet récursif
        self.assertEqual(main_win.content_stack.styleSheet(), orig_cs_style)
        self.assertEqual(main_win.main_content_stack.styleSheet(), orig_mcs_style)
        self.assertEqual(main_win.right_container.styleSheet(), orig_rc_style)

        # Sortie du plein écran
        import time
        time.sleep(0.55)
        main_win.toggle_fullscreen()
        QApplication.processEvents()

        self.assertEqual(main_win.content_stack.styleSheet(), orig_cs_style)
        self.assertEqual(main_win.main_content_stack.styleSheet(), orig_mcs_style)
        self.assertEqual(main_win.right_container.styleSheet(), orig_rc_style)

        if hasattr(main_win, "player_controller") and main_win.player_controller:
            main_win.player_controller.cleanup()
        main_win.close()

    def test_series_details_no_reposition_during_fullscreen(self):
        """Vérifie que SeriesDetailsView court-circuite tout repositionnement de cartes pendant le plein écran."""
        from ui.widgets.series_details_view import SeriesDetailsView
        from core.database import Database
        import tempfile
        from pathlib import Path

        tmp_dir = Path(tempfile.mkdtemp())
        db = Database(tmp_dir / "test.db")
        view = SeriesDetailsView(db=db)

        # 1. En mode plein écran, _reposition_episode_cards doit court-circuiter
        view._is_fullscreen = True
        view._current_col_count = 3
        view._reposition_episode_cards()
        self.assertEqual(view._current_col_count, 3)

        # 2. Quand details_container est masqué, il doit également court-circuiter
        view._is_fullscreen = False
        view.details_container.hide()
        view._current_col_count = 5
        view._reposition_episode_cards()
        self.assertEqual(view._current_col_count, 5)

        view.close()

    def test_video_widget_single_click_works_on_first_try(self):
        """Vérifie qu'un simple clic met en pause dès le premier clic, y compris après un basculement plein écran."""
        from ui.widgets.mpv_widget import MPVVideoWidget
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF, QEvent
        import time

        widget = MPVVideoWidget()
        widget.resize(800, 600)
        widget.controls.has_active_media = True
        widget.show()
        QApplication.processEvents()

        pp_events = []
        widget.play_pause_requested.connect(lambda: pp_events.append(True))

        center = widget.rect().center()
        global_center = widget.mapToGlobal(center)
        p_pt = QPointF(float(center.x()), float(center.y()))
        p_global = QPointF(float(global_center.x()), float(global_center.y()))

        # 1. Clic unique direct
        press = QMouseEvent(QEvent.Type.MouseButtonPress, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, press)
        release = QMouseEvent(QEvent.Type.MouseButtonRelease, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, release)

        self.assertTrue(widget._click_timer.isActive())
        time.sleep(0.35)
        QApplication.processEvents()
        self.assertEqual(len(pp_events), 1, "Le premier clic doit déclencher play/pause")

        # 2. Clic unique après suppress_clicks (ex: transition plein écran ou fenêtre)
        widget.suppress_clicks(0.35)
        # Attendre la fin du verrou de 0.35s
        time.sleep(0.4)
        QApplication.processEvents()

        press2 = QMouseEvent(QEvent.Type.MouseButtonPress, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, press2)
        release2 = QMouseEvent(QEvent.Type.MouseButtonRelease, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, release2)

        self.assertTrue(widget._click_timer.isActive(), "Le timer doit être actif dès le premier clic")
        time.sleep(0.35)
        QApplication.processEvents()
        self.assertEqual(len(pp_events), 2, "Le premier clic après transition doit déclencher play/pause sans nécessiter de second clic")

        # 3. Clic d'activation de fenêtre (où MouseButtonPress n'a pas été reçu ou a été consommé)
        widget._mouse_pressed_on_video = False
        release3 = QMouseEvent(QEvent.Type.MouseButtonRelease, p_pt, p_global, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        widget.eventFilter(widget.video_surface, release3)

        self.assertTrue(widget._click_timer.isActive(), "Le clic de réactivation doit activer le timer")
        time.sleep(0.35)
        QApplication.processEvents()
        self.assertEqual(len(pp_events), 3, "Le clic d'activation doit déclencher play/pause du premier coup")

        widget.close()


if __name__ == "__main__":
    unittest.main()

