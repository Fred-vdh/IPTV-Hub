import unittest
import os
import tempfile
from core.database import Database
from core.models import Channel, Playlist
from core.i18n import tr, set_language, get_language


class TestFavoriteSeriesNewEpisodes(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, 'test_iptv.db')
        self.db = Database(db_path=self.db_path)

        pl = Playlist(name='Test Xtream', url_or_path='http://example.com', playlist_type='xtream')
        self.playlist_id = self.db.add_playlist(pl)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_i18n_new_episode_translations(self):
        original_lang = get_language()
        try:
            for lang in ['fr', 'en', 'es', 'de']:
                set_language(lang)
                t_sec = tr('Nouveaux épisodes de vos séries favorites')
                t_badge = tr('✨ NOUVEAU')
                t_pill = tr('NOUVEAU')
                t_item = tr('Nouvel épisode')

                self.assertTrue(bool(t_sec), f'Missing section title for lang {lang}')
                self.assertTrue(bool(t_badge), f'Missing badge for lang {lang}')
                self.assertTrue(bool(t_pill), f'Missing pill for lang {lang}')
                self.assertTrue(bool(t_item), f'Missing item for lang {lang}')
        finally:
            set_language(original_lang)

    def test_detection_on_playlist_sync(self):
        ch1 = Channel(
            playlist_id=self.playlist_id,
            name='Breaking Bad',
            stream_type='series',
            stream_id='501',
            added_at=1000,
            is_favorite=True
        )
        self.db.save_channels_batch(self.playlist_id, [ch1])

        active_series = self.db.get_active_new_episodes_series(self.playlist_id)
        self.assertEqual(len(active_series), 0)

        # Deuxième passe : added_at passe à 2000
        ch1_updated = Channel(
            playlist_id=self.playlist_id,
            name='Breaking Bad',
            stream_type='series',
            stream_id='501',
            added_at=2000,
            is_favorite=True
        )
        self.db.save_channels_batch(self.playlist_id, [ch1_updated])

        active_series = self.db.get_active_new_episodes_series(self.playlist_id)
        self.assertEqual(len(active_series), 1)
        self.assertEqual(active_series[0].stream_id, '501')

        active_ids = self.db.get_active_new_episodes_series_ids(self.playlist_id)
        self.assertIn('501', active_ids)

    def test_episodes_flagging_and_dismissal(self):
        ch = Channel(
            playlist_id=self.playlist_id,
            name='Severance',
            stream_type='series',
            stream_id='702',
            added_at=1000,
            is_favorite=True
        )
        self.db.save_channels_batch(self.playlist_id, [ch])

        ch_new = Channel(
            playlist_id=self.playlist_id,
            name='Severance',
            stream_type='series',
            stream_id='702',
            added_at=3000,
            is_favorite=True
        )
        self.db.save_channels_batch(self.playlist_id, [ch_new])

        series_info = {
            'info': {'name': 'Severance'},
            'episodes': {
                '1': [
                    {'id': '1001', 'episode_num': 1, 'added': '1000', 'title': 'Good News About Hell'},
                    {'id': '1002', 'episode_num': 2, 'added': '3000', 'title': 'Half Loop'}
                ]
            }
        }
        self.db.save_series_info(self.playlist_id, '702', series_info)

        new_ep_ids = self.db.get_new_episode_ids_for_series(self.playlist_id, '702')
        self.assertIn('1002', new_ep_ids)
        self.assertNotIn('1001', new_ep_ids)

        self.db.dismiss_new_episode(
            playlist_id=self.playlist_id,
            series_id='702',
            episode_id='1002'
        )

        new_ep_ids_after = self.db.get_new_episode_ids_for_series(self.playlist_id, '702')
        self.assertNotIn('1002', new_ep_ids_after)

        active_series = self.db.get_active_new_episodes_series(self.playlist_id)
        self.assertEqual(len(active_series), 0)

    def test_dismiss_on_playback_progress(self):
        ch = Channel(
            playlist_id=self.playlist_id,
            name='Stranger Things',
            stream_type='series',
            stream_id='803',
            added_at=1000,
            is_favorite=True
        )
        self.db.save_channels_batch(self.playlist_id, [ch])

        ch_new = Channel(
            playlist_id=self.playlist_id,
            name='Stranger Things',
            stream_type='series',
            stream_id='803',
            added_at=5000,
            is_favorite=True
        )
        self.db.save_channels_batch(self.playlist_id, [ch_new])

        stream_url = 'http://example.com/series/user/pass/9001.mp4'
        series_info = {
            'info': {'name': 'Stranger Things'},
            'episodes': {
                '4': [
                    {'id': '9001', 'episode_num': 1, 'added': '5000', 'title': 'The Hellfire Club'}
                ]
            }
        }
        self.db.save_series_info(self.playlist_id, '803', series_info)

        self.assertIn('9001', self.db.get_new_episode_ids_for_series(self.playlist_id, '803'))

        channels = self.db.get_channels(playlist_id=self.playlist_id, stream_type='series')
        self.assertTrue(len(channels) > 0)
        ch_id = channels[0].id

        self.db.save_playback_progress(
            channel_id=ch_id,
            stream_url=stream_url,
            channel_name='Stranger Things S04E01',
            position=120.0,
            duration=3600.0
        )

        self.db.dismiss_new_episode(stream_url=stream_url)
        self.assertNotIn('9001', self.db.get_new_episode_ids_for_series(self.playlist_id, '803'))

    def test_unfavorite_deactivates_updates(self):
        ch = Channel(
            playlist_id=self.playlist_id,
            name='Loki',
            stream_type='series',
            stream_id='999',
            added_at=1000,
            is_favorite=True
        )
        self.db.save_channels_batch(self.playlist_id, [ch])

        ch_up = Channel(
            playlist_id=self.playlist_id,
            name='Loki',
            stream_type='series',
            stream_id='999',
            added_at=4000,
            is_favorite=True
        )
        self.db.save_channels_batch(self.playlist_id, [ch_up])
        self.assertIn('999', self.db.get_active_new_episodes_series_ids(self.playlist_id))

        channels = self.db.get_channels(playlist_id=self.playlist_id, stream_type='series')
        self.assertTrue(len(channels) > 0)
        self.db.set_favorite(channels[0].id, False)
        self.assertNotIn('999', self.db.get_active_new_episodes_series_ids(self.playlist_id))

if __name__ == '__main__':
    unittest.main()
