import sys
import unittest
from PyQt6.QtWidgets import QApplication

from core.database import Database
from core.models import Channel
from ui.widgets.dashboard_view import (
    DashboardView, HeroBannerWidget, LiveTvMiniCard, DashboardPosterCard, DashboardSection
)

app = QApplication.instance() or QApplication(sys.argv)


class TestDashboardEnhancements(unittest.TestCase):
    def setUp(self):
        self.db = Database()

    def test_continue_watching_series_resolution(self):
        items = self.db.get_dashboard_continue_watching()
        self.assertIsInstance(items, list)
        for item in items:
            ch = item['channel']
            self.assertIsInstance(ch, Channel)
            if 'S01E' in item.get('raw_title', ''):
                self.assertEqual(ch.stream_type, 'series')
                self.assertTrue(len(item['episode_text']) > 0)
                if 'Stuart Fails' in ch.name or 'Ted Lasso' in ch.name:
                    self.assertTrue(bool(ch.logo_url))

    def test_dashboard_components_instantiation(self):
        view = DashboardView(self.db)
        self.assertIsInstance(view.hero_banner, HeroBannerWidget)
        self.assertIsInstance(view.sec_continue, DashboardSection)
        self.assertIsInstance(view.sec_recent_live, DashboardSection)
        self.assertIsInstance(view.sec_favs, DashboardSection)
        self.assertIsInstance(view.sec_recents, DashboardSection)

        view.refresh_view()

        live_items = self.db.get_dashboard_recent_live(limit=5)
        if live_items:
            mini_card = LiveTvMiniCard(live_items[0])
            self.assertEqual(mini_card.CARD_WIDTH, 220)
            self.assertEqual(mini_card.CARD_HEIGHT, 56)

    def test_dashboard_poster_card_episode_badge(self):
        ch = Channel(
            id=123,
            playlist_id=1,
            name='|FR| Ted Lasso (2020)',
            stream_url='http://example.com/ep.mkv',
            logo_url='http://example.com/poster.jpg',
            stream_type='series'
        )
        prog = {
            'channel': ch,
            'raw_title': '|FR| Ted Lasso (2020) — S01E03 : Biscuits',
            'series_name': '|FR| Ted Lasso (2020)',
            'episode_text': 'S1:E3',
            'percentage': 45,
            'playlist_type': 'XTREAM'
        }
        card = DashboardPosterCard(ch, progress_info=prog)
        self.assertEqual(card.channel.stream_type, 'series')
        self.assertEqual(card.progress_info.get('episode_text'), 'S1:E3')

    def test_dashboard_poster_card_replay_badge(self):
        ch = Channel(
            id=456,
            playlist_id=1,
            name='|FR| TF1 HD : Qui sera le plus nul ?',
            stream_url='http://example.com/timeshift/user/pass/95/2026-09-05:00-50/366.ts',
            logo_url='http://example.com/tf1.png',
            stream_type='replay'
        )
        prog = {
            'channel': ch,
            'raw_title': '|FR| TF1 HD : Qui sera le plus nul ?',
            'percentage': 20,
            'playlist_type': 'XTREAM'
        }
        card = DashboardPosterCard(ch, progress_info=prog)
        self.assertEqual(card.channel.stream_type, 'replay')
        self.assertEqual(card._get_badge_palette('REPLAY')[1].name(), '#e0e7ff')

    def test_continue_watching_completed_series_episode(self):
        try:
            # Enregistrer un épisode de série terminé à 100%
            self.db.save_playback_progress(
                channel_id=999999,
                stream_url="http://example.com/series/user/pass/9999.mkv",
                channel_name="|FR| Test Series (2024) — S02E05 : Le grand final",
                position=3000.0,
                duration=3000.0
            )
            items = self.db.get_dashboard_continue_watching(limit=10)
            found = next((i for i in items if "Test Series" in (i["series_name"] or i["raw_title"])), None)
            self.assertIsNotNone(found, "La série avec épisode terminé doit figurer dans Continuer la lecture")
            self.assertTrue(found["is_completed"])
            self.assertEqual(found["episode_text"], "S2:E6")
            self.assertEqual(found["position"], 0.0)
            self.assertEqual(found["percentage"], 0)
        finally:
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM playback_progress WHERE channel_name LIKE '%Test Series%'")
                conn.commit()

    def test_hero_banner_completed_series_episode(self):
        banner = HeroBannerWidget()
        ch = Channel(
            id=999999,
            playlist_id=1,
            name="|FR| Test Series (2024)",
            stream_url="http://example.com/series/user/pass/9999.mkv",
            stream_type="series"
        )
        item = {
            "channel": ch,
            "raw_title": "|FR| Test Series (2024) — S02E05",
            "series_name": "|FR| Test Series (2024)",
            "episode_text": "S2:E6",
            "position": 0.0,
            "duration": 3000.0,
            "remaining_str": "Épisode suivant disponible",
            "percentage": 0,
            "is_completed": True,
            "playlist_name": "Test",
            "playlist_type": "XTREAM"
        }
        banner.set_data(item)
        self.assertIn("Lancer l'épisode suivant", banner.btn_resume.text())
        self.assertIn("Épisode suivant disponible", banner.status_label.text())
        self.assertEqual(banner.progress_bar_fill.width(), 0)


if __name__ == '__main__':
    unittest.main()

