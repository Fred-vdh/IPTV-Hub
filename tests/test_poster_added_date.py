import sys
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter
from core.models import Channel
from ui.widgets.poster_utils import format_poster_added_date, draw_added_date_badge
import ui.widgets.poster_utils as poster_utils
from ui.widgets.rounded_poster import RoundedPosterLabel
from ui.widgets.vod_grid import PosterWidget


class TestPosterAddedDate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_format_poster_added_date_iso(self):
        self.assertEqual(format_poster_added_date('2024-12-08T19:59:24'), '08/12/2024')
        self.assertEqual(format_poster_added_date('2021-04-20 16:07:39'), '20/04/2021')
        self.assertEqual(format_poster_added_date('2019-10-15'), '15/10/2019')

    def test_format_poster_added_date_timestamp(self):
        # 1600000000 = 2020-09-13
        formatted = format_poster_added_date(1600000000)
        self.assertIn('/2020', formatted)

    def test_format_poster_added_date_empty_or_invalid(self):
        self.assertEqual(format_poster_added_date(''), '')
        self.assertEqual(format_poster_added_date(None), '')
        self.assertEqual(format_poster_added_date('invalid-date'), '')

    def test_draw_added_date_badge(self):
        pix = QPixmap(160, 240)
        painter = QPainter(pix)
        drawn = draw_added_date_badge(painter, '2024-12-08T19:59:24', 160, 240)
        self.assertTrue(drawn)
        
        # Non dessiné si date vide
        drawn_empty = draw_added_date_badge(painter, '', 160, 240)
        self.assertFalse(drawn_empty)
        painter.end()

    def test_toggle_show_poster_added_date(self):
        pix = QPixmap(160, 240)
        painter = QPainter(pix)
        poster_utils.SHOW_POSTER_ADDED_DATE = False
        try:
            drawn = draw_added_date_badge(painter, '2024-12-08T19:59:24', 160, 240)
            self.assertFalse(drawn)
        finally:
            poster_utils.SHOW_POSTER_ADDED_DATE = True
        painter.end()

    def test_rounded_poster_label_with_added_at(self):
        lbl = RoundedPosterLabel()
        lbl.resize(160, 240)
        lbl.set_added_at('2024-12-08T19:59:24', 'movie')
        self.assertEqual(lbl.added_at, '2024-12-08T19:59:24')
        self.assertEqual(lbl.stream_type, 'movie')
        # Déclencher le rendu
        pix = QPixmap(160, 240)
        lbl.render(pix)
        lbl.close()

    def test_vod_grid_poster_widget_with_added_at(self):
        ch = Channel(name='Test Movie (2024)', stream_type='movie', added_at='2024-12-08T19:59:24')
        widget = PosterWidget(ch)
        widget.resize(160, 240)
        pix = QPixmap(160, 240)
        widget.render(pix)
        widget.close()


if __name__ == '__main__':
    unittest.main()
