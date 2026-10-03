import sys
import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtGui import QMouseEvent

from core.player_controller import PlayerController
from ui.widgets.player_controls import ChapterTimelineSlider, PlayerControls

# Initialiser QApplication si non existante
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestChapterMarkers(unittest.TestCase):
    def setUp(self):
        self.slider = ChapterTimelineSlider()
        self.slider.resize(800, 30)

    def test_chapter_parsing_in_player_controller(self):
        pc = PlayerController()
        # Mock mpv
        mock_mpv = MagicMock()
        pc._player = mock_mpv

        # Simuler un retour chapter-list de libmpv
        mock_chapters = [
            {"title": "Générique", "time": 0.0},
            {"title": "Scène 1 - La rencontre", "time": 120.5},
            {"title": "Chapitre 3", "time": 450.0},
        ]
        mock_mpv.chapter_list = mock_chapters

        captured_chapters = []
        pc.chapters_changed.connect(lambda ch: captured_chapters.extend(ch))

        pc._on_chapter_list("chapter-list", mock_chapters)

        self.assertEqual(len(captured_chapters), 3)
        self.assertEqual(captured_chapters[1]["title"], "Scène 1 - La rencontre")
        self.assertEqual(captured_chapters[1]["time"], 120.5)
        self.assertEqual(pc.get_chapters(), mock_chapters)

    def test_slider_chapters_assignment(self):
        chapters = [
            {"title": "Intro", "time": 0.0},
            {"title": "Partie 1", "time": 300.0},
            {"title": "Fin", "time": 900.0},
        ]
        self.slider.set_chapters(chapters, total_duration=1200.0)
        self.assertEqual(len(self.slider._chapters), 3)
        self.assertEqual(self.slider._total_duration, 1200.0)

    def test_slider_magnetic_snap(self):
        chapters = [
            {"title": "Partie 1", "time": 600.0},
        ]
        self.slider.set_chapters(chapters, total_duration=1200.0)
        groove, handle, avail_w, start_x = self.slider._get_geometry_info()

        # Coordonnée x exacte du marqueur (600s / 1200s = 50%)
        exact_x = start_x + int(0.5 * avail_w)

        # Clic à 3px à gauche du marqueur (dans la tolérance de 6px)
        click_x = exact_x - 3
        seek_targets = []
        self.slider.seek_requested.connect(lambda t: seek_targets.append(t))

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(float(click_x), float(groove.center().y())),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        self.slider.mousePressEvent(event)

        # Doit snapper exactement à 600.0s et non pas à (click_x ratio)
        self.assertEqual(len(seek_targets), 1)
        self.assertEqual(seek_targets[0], 600.0)

    def test_player_controls_integration(self):
        controls = PlayerControls()
        controls.resize(1000, 200)

        chapters = [
            {"title": "Chapitre 1", "time": 0.0},
            {"title": "Chapitre 2", "time": 500.0},
        ]
        controls.set_position(0, 1000.0)
        controls.set_chapters(chapters)

        self.assertEqual(len(controls.chapters), 2)
        self.assertEqual(len(controls.timeline_slider._chapters), 2)
        self.assertEqual(controls.timeline_slider._total_duration, 1000.0)

    def test_in_process_tooltip(self):
        controls = PlayerControls()
        controls.resize(1000, 300)
        controls.show()

        # Vérifier que l'infobulle personnalisée est bien présente et cachée par défaut
        self.assertTrue(hasattr(controls, "osd_tooltip"))
        self.assertFalse(controls.osd_tooltip.isVisible())

        # Afficher l'infobulle pour le bouton lecture/pause
        controls.show_custom_tooltip(controls.play_btn, "Lecture / Pause (Espace)")
        self.assertTrue(controls.osd_tooltip.isVisible())
        self.assertEqual(controls.osd_tooltip.label.text(), "Lecture / Pause (Espace)")

        # L'infobulle doit être positionnée au-dessus du bouton
        btn_pt = controls.play_btn.mapTo(controls, QPoint(0, 0))
        self.assertLess(controls.osd_tooltip.y(), btn_pt.y())

        # Masquer l'infobulle
        controls.hide_custom_tooltip()
        self.assertFalse(controls.osd_tooltip.isVisible())


if __name__ == "__main__":
    unittest.main()
