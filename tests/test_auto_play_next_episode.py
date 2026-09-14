import sys
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication, QMainWindow

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import Database
from core.models import AppSettings, Channel
from ui.widgets.player_controls import PlayerControls


class TestAutoPlayNextEpisode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / 'test.db')
        self.db = Database(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_settings_default_and_persistence(self):
        settings = self.db.get_settings()
        self.assertTrue(settings.auto_play_next_episode)

        settings.auto_play_next_episode = False
        self.db.save_settings(settings)

        reloaded = self.db.get_settings()
        self.assertFalse(reloaded.auto_play_next_episode)

        settings.auto_play_next_episode = True
        self.db.save_settings(settings)
        self.assertTrue(self.db.get_settings().auto_play_next_episode)

    def test_player_controls_button_state_and_toggle(self):
        controls = PlayerControls()
        self.assertTrue(hasattr(controls, 'auto_next_btn'))
        self.assertTrue(controls.auto_next_btn.isCheckable())

        controls.set_auto_next_state(True)
        self.assertTrue(controls.auto_next_btn.isChecked())
        self.assertIn('Activée', controls.auto_next_btn.toolTip())

        controls.set_auto_next_state(False)
        self.assertFalse(controls.auto_next_btn.isChecked())
        self.assertIn('Bloquée', controls.auto_next_btn.toolTip())

        toggled_events = []
        controls.auto_next_toggled.connect(lambda val: toggled_events.append(val))

        controls.auto_next_btn.click()
        self.assertEqual(len(toggled_events), 1)
        self.assertTrue(toggled_events[0])
        self.assertTrue(controls.auto_next_btn.isChecked())

        controls.auto_next_btn.click()
        self.assertEqual(len(toggled_events), 2)
        self.assertFalse(toggled_events[1])
        self.assertFalse(controls.auto_next_btn.isChecked())

        controls.close()

    def test_player_controls_visibility_by_stream_type(self):
        controls = PlayerControls()

        ch_series = Channel(id=1, name='S01E01', stream_type='series', stream_url='http://test/ep1.mp4')
        controls.update_channel_info(ch_series)
        self.assertFalse(controls.auto_next_btn.isHidden())

        ch_live = Channel(id=2, name='TF1', stream_type='live', stream_url='http://test/live.m3u8')
        controls.update_channel_info(ch_live)
        self.assertTrue(controls.auto_next_btn.isHidden())

        ch_movie = Channel(id=3, name='Inception', stream_type='movie', stream_url='http://test/movie.mp4')
        controls.update_channel_info(ch_movie)
        self.assertTrue(controls.auto_next_btn.isHidden())

        ch_replay = Channel(id=4, name='Journal', stream_type='replay', stream_url='http://test/replay.mp4')
        controls.update_channel_info(ch_replay)
        self.assertTrue(controls.auto_next_btn.isHidden())

        controls.close()

    def test_main_window_playback_finished_respects_setting(self):
        from ui.main_window import MainWindow

        win = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(win)
        win.db = self.db
        win.settings = AppSettings(auto_play_next_episode=False)
        win.current_channel = Channel(id=10, name='Ep 1', stream_type='series', stream_url='http://test/ep1.mp4')
        win._current_playback_pos = 1800.0
        win._current_playback_dur = 1800.0
        win._series_episodes = [
            Channel(id=10, name='Ep 1', stream_type='series', stream_url='http://test/ep1.mp4'),
            Channel(id=11, name='Ep 2', stream_type='series', stream_url='http://test/ep2.mp4')
        ]
        win._current_series_idx = 0
        win._play_series_episode_in_details = MagicMock()
        win.play_channel = MagicMock()
        win.series_details_view = MagicMock()
        win.video_widget = MagicMock()

        MainWindow._on_playback_finished(win)

        prog_map = self.db.get_all_playback_progress_map()
        self.assertIn('http://test/ep1.mp4', prog_map)
        pos, dur = prog_map['http://test/ep1.mp4']
        self.assertAlmostEqual(pos, 1800.0)
        self.assertAlmostEqual(dur, 1800.0)

        win._play_series_episode_in_details.assert_not_called()
        win.play_channel.assert_not_called()
        win.video_widget.controls.show_bars.assert_called_once()
        win.video_widget.controls.set_playing_state.assert_called_once_with('stopped')

        win.settings.auto_play_next_episode = True
        win.current_channel = Channel(id=10, name='Ep 1', stream_type='series', stream_url='http://test/ep1.mp4')
        win._is_playing_series_in_details = True

        MainWindow._on_playback_finished(win)
        win._play_series_episode_in_details.assert_called_once_with(win._series_episodes[1], start_pos=0.0)

    def test_reactivation_after_episode_stopped_launches_next_episode(self):
        """Vérifie que réactiver la lecture automatique alors qu'un épisode s'est arrêté à sa fin

        déclenche immédiatement la lecture de l'épisode suivant.
        """
        from ui.main_window import MainWindow

        win = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(win)
        win.db = self.db
        win.settings = AppSettings(auto_play_next_episode=False)
        win.current_channel = Channel(id=10, name='Ep 1', stream_type='series', stream_url='http://test/ep1.mp4')
        win._current_playback_pos = 1800.0
        win._current_playback_dur = 1800.0
        win._series_episodes = [
            Channel(id=10, name='Ep 1', stream_type='series', stream_url='http://test/ep1.mp4'),
            Channel(id=11, name='Ep 2', stream_type='series', stream_url='http://test/ep2.mp4')
        ]
        win._current_series_idx = 0
        win._stopped_at_episode_end = False
        win._play_series_episode_in_details = MagicMock()
        win.play_channel = MagicMock()
        win.series_details_view = MagicMock()
        win.video_widget = MagicMock()
        win._is_playing_series_in_details = True

        # 1. Fin de l'épisode avec autoplay=False -> arrêt et mémorisation de l'état
        MainWindow._on_playback_finished(win)
        self.assertTrue(win._stopped_at_episode_end)
        win._play_series_episode_in_details.assert_not_called()

        # 2. Réactivation de la lecture automatique -> l'épisode 2 doit être lancé immédiatement !
        MainWindow._on_auto_next_toggled(win, True)
        self.assertFalse(win._stopped_at_episode_end)
        win._play_series_episode_in_details.assert_called_once_with(win._series_episodes[1], start_pos=0.0)
        self.assertEqual(win._current_series_idx, 1)

    def test_play_pause_at_episode_end(self):
        """Vérifie le comportement de Play/Pause à la fin d'un épisode."""
        from ui.main_window import MainWindow

        win = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(win)
        win.db = self.db
        win.settings = AppSettings(auto_play_next_episode=False)
        win.current_channel = Channel(id=10, name='Ep 1', stream_type='series', stream_url='http://test/ep1.mp4')
        win._series_episodes = [
            Channel(id=10, name='Ep 1', stream_type='series', stream_url='http://test/ep1.mp4'),
            Channel(id=11, name='Ep 2', stream_type='series', stream_url='http://test/ep2.mp4')
        ]
        win._current_series_idx = 0
        win._stopped_at_episode_end = True
        win._is_playing_series_in_details = True
        win._play_series_episode_in_details = MagicMock()
        win.player_controller = MagicMock()
        win.series_details_view = MagicMock()

        # Cas 1 : autoplay=False -> relance le même épisode à 0.0
        MainWindow._on_play_pause_requested(win)
        self.assertFalse(win._stopped_at_episode_end)
        win._play_series_episode_in_details.assert_called_once_with(win._series_episodes[0], start_pos=0.0)

        # Cas 2 : autoplay=True -> enchaîne sur l'épisode suivant
        win.settings.auto_play_next_episode = True
        win._stopped_at_episode_end = True
        win._play_series_episode_in_details.reset_mock()
        MainWindow._on_play_pause_requested(win)
        self.assertFalse(win._stopped_at_episode_end)
        win._play_series_episode_in_details.assert_called_once_with(win._series_episodes[1], start_pos=0.0)

    def test_player_controller_eof_reported_reset(self):
        """Vérifie que _eof_reported est correctement réarmé sur seek et quand eof-reached repasse à False."""
        from core.player_controller import PlayerController

        ctrl = PlayerController.__new__(PlayerController)
        ctrl._eof_reported = True
        ctrl._is_vod = True
        ctrl._current_url = "http://test/video.mp4"
        ctrl.playback_finished = MagicMock()

        # Quand eof-reached repasse à False (par ex. déplacement dans le temps)
        ctrl._on_eof_reached(None, False)
        self.assertFalse(ctrl._eof_reported)

        # Quand eof-reached repasse à True -> émet playback_finished
        ctrl._on_eof_reached(None, True)
        self.assertTrue(ctrl._eof_reported)
        ctrl.playback_finished.emit.assert_called_once()

        # Quand on seek -> _eof_reported doit être réinitialisé à False
        ctrl._player = None
        ctrl.seek(10.0)
        self.assertFalse(ctrl._eof_reported)


if __name__ == '__main__':
    unittest.main()
