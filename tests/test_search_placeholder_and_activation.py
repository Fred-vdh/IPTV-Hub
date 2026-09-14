import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.mpv_setup import setup_mpv_environment
setup_mpv_environment()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication  # noqa: E402
from core.models import Channel, Playlist  # noqa: E402
from core.database import Database  # noqa: E402
from ui.widgets.custom_titlebar import CustomTitleBar  # noqa: E402
from ui.widgets.dashboard_view import DashboardView, DashboardPosterCard  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)


class TestSearchPlaceholderAndActivation(unittest.TestCase):
    def test_custom_titlebar_default_placeholder(self):
        titlebar = CustomTitleBar()
        self.assertEqual(titlebar.search_box.placeholderText(), 'Rechercher sur le tableau de bord...')

    def test_custom_titlebar_section_placeholders(self):
        titlebar = CustomTitleBar()
        expected = {
            'dashboard': 'Rechercher sur le tableau de bord...',
            'favorites': 'Favoris | Filtrer cette section...',
            'history': 'Rechercher dans l\'historique...',
            'live': 'Rechercher une chaîne en direct...',
            'vod': 'Rechercher un film (VOD)...',
            'series': 'Rechercher une série...',
            'recently_added': 'Rechercher parmi les récents ajouts...',
            'epg': 'Rechercher dans le guide TV...',
            'replay': 'Rechercher dans le Replay...',
            'settings': 'Rechercher...',
        }
        for section, text in expected.items():
            titlebar.set_category_placeholder(section)
            self.assertEqual(titlebar.search_box.placeholderText(), text, f'Échec pour la section {section}')

    @patch('ui.widgets.movie_details_view._TrailerLookupWorker')
    @patch('ui.widgets.series_details_view._SeriesTrailerLookupWorker')
    @patch('ui.widgets.series_details_view.SeriesInfoWorker')
    def test_mainwindow_search_placeholder_synchronization(self, mock_w1, mock_w2, mock_w3):
        from ui.main_window import MainWindow

        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / 'test_search.db'
        db = Database(str(db_path))

        pl = Playlist(name='TestPL', url_or_path='http://test.m3u')
        pl_id = db.add_playlist(pl)

        ch_series = Channel(playlist_id=pl_id, name='Stranger Things', stream_type='series')
        db.save_channels_batch(pl_id, [ch_series], replace=False)
        ch_movie = Channel(playlist_id=pl_id, name='Inception', stream_type='movie')
        db.save_channels_batch(pl_id, [ch_movie], replace=False)

        win = MainWindow(db=db)
        try:
            win.series_details_view.load_series = MagicMock()
            win.movie_details_view.load_movie = MagicMock()
            win.player_controller.play = MagicMock()

            # 1. Startup : la fenêtre commence sur le tableau de bord avec le placeholder approprié
            self.assertEqual(win.current_section, 'dashboard')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher sur le tableau de bord...')

            # 2. Ouverture d\'une série depuis le dashboard
            win._open_series_details(ch_series)
            self.assertEqual(win.current_section, 'series')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher une série...')
            self.assertEqual(win._details_origin_section, 'dashboard')

            # 3. Retour vers le dashboard depuis la fiche série
            win._back_to_series_grid()
            self.assertEqual(win.current_section, 'dashboard')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher sur le tableau de bord...')

            # 4. Ouverture d\'un film depuis le dashboard
            win._open_movie_details(ch_movie)
            self.assertEqual(win.current_section, 'vod')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher un film (VOD)...')
            self.assertEqual(win._details_origin_section, 'dashboard')

            # 5. Retour vers le dashboard depuis la fiche film
            win._back_to_vod_grid_from_details()
            self.assertEqual(win.current_section, 'dashboard')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher sur le tableau de bord...')

            # 6. Reprise de lecture d\'une série depuis le dashboard via _on_resume_playback
            win._on_resume_playback(ch_series, position=120.0)
            self.assertEqual(win.current_section, 'series')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher une série...')

            # Retour au dashboard
            win._back_to_series_grid()
            self.assertEqual(win.current_section, 'dashboard')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher sur le tableau de bord...')

            # 7. Navigation par sidebar
            win._on_section_changed('live')
            self.assertEqual(win.current_section, 'live')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher une chaîne en direct...')

            win._on_section_changed('epg')
            self.assertEqual(win.current_section, 'epg')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher dans le guide TV...')

            win._on_section_changed('replay')
            self.assertEqual(win.current_section, 'replay')
            self.assertEqual(win.title_bar.search_box.placeholderText(), 'Rechercher dans le Replay...')
        finally:
            pass

    def test_dashboard_view_search_filtering(self):
        db_mock = MagicMock()
        db_mock.get_dashboard_continue_watching.return_value = []
        db_mock.get_dashboard_recent_live.return_value = []
        db_mock.get_channels.return_value = []
        db_mock.get_playlists.return_value = []
        db_mock.get_recently_added_channels.return_value = []

        dash = DashboardView(db_mock)
        sec = dash.sec_continue

        c1 = Channel(id=1, name='Breaking Bad S01E01', stream_type='series')
        c2 = Channel(id=2, name='Better Call Saul S02E04', stream_type='series')
        card1 = DashboardPosterCard(c1)
        card2 = DashboardPosterCard(c2)
        sec.add_item(card1)
        sec.add_item(card2)

        sec.filter_items('breaking')
        self.assertFalse(card1.isHidden())
        self.assertTrue(card2.isHidden())
        self.assertEqual(sec.badge_label.text(), '1')

        sec.filter_items('')
        self.assertFalse(card1.isHidden())
        self.assertFalse(card2.isHidden())
        self.assertEqual(sec.badge_label.text(), '2')


if __name__ == '__main__':
    unittest.main()
