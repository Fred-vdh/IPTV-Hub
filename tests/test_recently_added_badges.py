"""
Tests unitaires pour les badges d'affiches dans RecentlyAddedView :
- Absence des badges redondants 'MOVIE' et 'SERIES'
- Présence du badge de note '★ {rating}' en haut à droite
- Préservation du badge 'LIVE' pour les flux en direct
- Support des tags de qualité (4K, etc.)
"""

import sys
import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

from core.models import Channel
from ui.widgets.recently_added_view import RecentPosterWidget


class TestRecentlyAddedBadges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_movie_has_rating_and_no_movie_badge(self):
        ch = Channel(name="Inception (2010) [4K]", stream_type="movie", rating="8.8")
        widget = RecentPosterWidget(ch)
        widget.resize(155, 230)

        mock_painter = MagicMock()
        mock_painter.fontMetrics.return_value.horizontalAdvance.return_value = 20
        widget._draw_header_badges(mock_painter)

        text_calls = [call.args[2] for call in mock_painter.drawText.call_args_list if len(call.args) >= 3]

        # 1. Vérifier qu'aucun badge MOVIE n'est présent
        self.assertNotIn("MOVIE", text_calls)

        # 2. Vérifier que la note 8.8 est bien présente avec l'étoile
        self.assertTrue(any("8.8" in t for t in text_calls), f"Note non trouvée dans {text_calls}")
        self.assertTrue(any("★" in t for t in text_calls), f"Étoile non trouvée dans {text_calls}")

        # 3. Vérifier que le tag 4K est bien présent
        self.assertIn("4K", text_calls)

        widget.close()

    def test_series_has_rating_and_no_series_badge(self):
        ch = Channel(name="Breaking Bad S01E01", stream_type="series", rating="9.5")
        widget = RecentPosterWidget(ch)
        widget.resize(155, 230)

        mock_painter = MagicMock()
        mock_painter.fontMetrics.return_value.horizontalAdvance.return_value = 20
        widget._draw_header_badges(mock_painter)

        text_calls = [call.args[2] for call in mock_painter.drawText.call_args_list if len(call.args) >= 3]

        # 1. Vérifier qu'aucun badge SERIES n'est présent
        self.assertNotIn("SERIES", text_calls)

        # 2. Vérifier que la note 9.5 est bien présente
        self.assertTrue(any("9.5" in t for t in text_calls), f"Note non trouvée dans {text_calls}")

        widget.close()

    def test_live_stream_retains_live_badge_and_no_rating(self):
        ch = Channel(name="TF1 HD", stream_type="live", rating="0.0")
        widget = RecentPosterWidget(ch)
        widget.resize(155, 230)

        mock_painter = MagicMock()
        mock_painter.fontMetrics.return_value.horizontalAdvance.return_value = 20
        widget._draw_header_badges(mock_painter)

        text_calls = [call.args[2] for call in mock_painter.drawText.call_args_list if len(call.args) >= 3]

        # 1. Vérifier que le badge LIVE est bien présent
        self.assertIn("LIVE", text_calls)

        # 2. Vérifier qu'aucune note n'est affichée
        self.assertFalse(any("★" in t for t in text_calls))

        widget.close()

    def test_movie_without_rating(self):
        ch = Channel(name="Unknown Movie (2024)", stream_type="movie", rating="")
        widget = RecentPosterWidget(ch)
        widget.resize(155, 230)

        mock_painter = MagicMock()
        mock_painter.fontMetrics.return_value.horizontalAdvance.return_value = 20
        widget._draw_header_badges(mock_painter)

        text_calls = [call.args[2] for call in mock_painter.drawText.call_args_list if len(call.args) >= 3]

        # Aucun badge texte si pas de qualité ni de note
        self.assertNotIn("MOVIE", text_calls)
        self.assertFalse(any("★" in t for t in text_calls))

        widget.close()


if __name__ == "__main__":
    unittest.main()
