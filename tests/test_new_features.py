"""
Tests unitaires pour les nouvelles fonctionnalités :
- Titre et affichage des comptes dans ManagePlaylistsDialog (sans 'SQLite')
- Bouton TV Replay dans la Sidebar
- Génération d'URL timeshift et vue ReplayView
- Intégration TMDB avis spectateurs
- Sections trailer YouTube dans MovieDetailsView et SeriesDetailsView
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from PyQt6.QtWidgets import QApplication

from core.database import Database
from core.models import Playlist, Channel
from core.xtream_client import XtreamClient
from core.tmdb_client import get_movie_reviews
from ui.widgets.sidebar import Sidebar
from ui.widgets.replay_view import ReplayView
from ui.dialogs.manage_playlists_dialog import ManagePlaylistsDialog, PlaylistItemWidget

app = QApplication.instance() or QApplication(sys.argv)


class TestNewFeatures(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_features.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        try:
            del self.db
            import gc
            gc.collect()
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_manage_playlists_dialog_title_and_badges(self):
        # 1. Vérifier le titre de la fenêtre sans "SQLite"
        dlg = ManagePlaylistsDialog(self.db)
        self.assertNotIn("SQLite", dlg.windowTitle())
        self.assertEqual(dlg.windowTitle(), "Gestion des listes de lecture")

        # 2. Vérifier les badges de compte
        p = Playlist(
            name="Test Xtream",
            url_or_path="",
            playlist_type="xtream",
            server_url="http://test.com",
            account_status="Active",
            exp_date="1767225600",
            max_connections="2",
            active_cons="1"
        )
        widget = PlaylistItemWidget(p, db=self.db)
        self.assertIn("Actif", widget.status_badge.text())
        self.assertIn("01/01/2026", widget.exp_badge.text())
        self.assertIn("1 / 2", widget.conn_badge.text())

    def test_sidebar_has_replay_button(self):
        sidebar = Sidebar(self.db)
        self.assertTrue(hasattr(sidebar, "btn_replay"))
        self.assertIn("replay", sidebar.btn_replay.toolTip().lower())

        received = []
        sidebar.section_changed.connect(lambda s: received.append(s))
        sidebar.select_section("replay")
        self.assertIn("replay", received)

        # Vérifier l'ordre des boutons : EPG au-dessus de TV en direct, et Replay entre EPG et TV
        widgets = [sidebar.layout().itemAt(i).widget() for i in range(sidebar.layout().count()) if sidebar.layout().itemAt(i).widget()]
        idx_epg = widgets.index(sidebar.btn_epg)
        idx_replay = widgets.index(sidebar.btn_replay)
        idx_live = widgets.index(sidebar.btn_live)
        self.assertLess(idx_epg, idx_replay)
        self.assertLess(idx_replay, idx_live)
        self.assertEqual(idx_replay, idx_epg + 1)
        self.assertEqual(idx_live, idx_replay + 1)

    def test_timeshift_url_generation(self):
        client = XtreamClient("http://server.example:8080", "user123", "pass456")
        dt = datetime(2026, 9, 5, 14, 30)
        url = client.get_timeshift_stream_url("9999", dt, 90)
        expected = "http://server.example:8080/timeshift/user123/pass456/90/2026-09-05:14-30/9999.ts"
        self.assertEqual(url, expected)

    def test_replay_view_initialization(self):
        # Ajouter une chaîne avec archive
        pl_id = self.db.add_playlist(Playlist(name="PL1", url_or_path="", playlist_type="xtream"))
        ch = Channel(
            playlist_id=pl_id,
            name="TF1 Replay",
            stream_url="http://example.com/tf1.ts",
            stream_type="live",
            stream_id="101",
            tv_archive=1,
            tv_archive_duration=7
        )
        self.db.save_channels_batch(pl_id, [ch])

        replay_view = ReplayView(self.db)
        replay_view.set_playlist_id(pl_id)
        replay_view.refresh_view()

        self.assertEqual(replay_view.channel_list_widget.count(), 1)
        self.assertIn("TF1 Replay", replay_view.channel_list_widget.item(0).text())
        replay_view.stop_workers()
        replay_view.close()

    def test_tmdb_client_structure(self):
        # Test avec un ID invalide ou vide
        empty_res = get_movie_reviews("")
        self.assertEqual(empty_res, [])

    def test_player_controls_replay_mode(self):
        from ui.widgets.player_controls import PlayerControls
        controls = PlayerControls()
        ch = Channel(
            id=42,
            name="France 2 : Journal 20h",
            stream_url="http://example.com/timeshift.ts",
            stream_type="replay"
        )
        controls.update_channel_info(ch)
        self.assertEqual(controls.badge_live.text(), "REPLAY")
        self.assertEqual(controls.back_btn.text(), "‹  Retour au Replay")
        self.assertFalse(controls.back_btn.isHidden())
        self.assertFalse(controls.timeline_row.isHidden())
        self.assertTrue(controls.prev_btn.isHidden())
        self.assertTrue(controls.next_btn.isHidden())

        controls.set_playing_state("playing")
        self.assertEqual(controls.badge_live.text(), "REPLAY")

    def test_player_controls_all_categories(self):
        from ui.widgets.player_controls import PlayerControls
        controls = PlayerControls()

        # 1. LIVE (Option 3 : timeline affichée, figée au début si pas d'EPG)
        ch_live = Channel(name="TF1", stream_url="http://x/live.ts", stream_type="live")
        controls.update_channel_info(ch_live)
        self.assertEqual(controls.badge_live.text(), "DIRECT")
        self.assertTrue(controls.back_btn.isHidden())
        self.assertFalse(controls.timeline_row.isHidden())
        self.assertEqual(controls.timeline_slider.value(), 0)
        self.assertEqual(controls.curr_time_label.text(), "00:00")
        self.assertEqual(controls.total_time_label.text(), "--:--")
        self.assertFalse(controls.prev_btn.isHidden())

        # 2. MOVIE
        ch_movie = Channel(name="Inception", stream_url="http://x/movie.mp4", stream_type="movie")
        controls.update_channel_info(ch_movie)
        self.assertEqual(controls.badge_live.text(), "FILM")
        self.assertEqual(controls.back_btn.text(), "‹  Retour aux films")
        self.assertFalse(controls.back_btn.isHidden())
        self.assertFalse(controls.timeline_row.isHidden())
        self.assertTrue(controls.prev_btn.isHidden())

        # 3. VOD
        ch_vod = Channel(name="Interstellar", stream_url="http://x/vod.mkv", stream_type="vod")
        controls.update_channel_info(ch_vod)
        self.assertEqual(controls.badge_live.text(), "FILM")
        self.assertEqual(controls.back_btn.text(), "‹  Retour aux films")

        # 4. SERIES
        ch_series = Channel(name="Breaking Bad S01E01", stream_url="http://x/s.mp4", stream_type="series")
        controls.update_channel_info(ch_series)
        self.assertEqual(controls.badge_live.text(), "SÉRIE")
        self.assertEqual(controls.back_btn.text(), "‹  Retour à la fiche série")
        self.assertFalse(controls.prev_btn.isHidden())

        # 5. REPLAY
        ch_replay = Channel(name="JT 20H", stream_url="http://x/timeshift/1.ts", stream_type="replay")
        controls.update_channel_info(ch_replay)
        self.assertEqual(controls.badge_live.text(), "REPLAY")
        self.assertEqual(controls.back_btn.text(), "‹  Retour au Replay")

    def test_contextual_back_button_preservation(self):
        from ui.widgets.player_controls import PlayerControls
        controls = PlayerControls()
        ch = Channel(name="Docu", stream_url="http://x/doc.mp4", stream_type="movie")
        controls.update_channel_info(ch)
        controls.set_back_button_text("‹  Retour à l'historique")
        self.assertEqual(controls.back_btn.text(), "‹  Retour à l'historique")

        # Vérifier que le changement d'état (ex: en cours de lecture) n'écrase pas le libellé
        controls.set_playing_state("playing")
        self.assertEqual(controls.back_btn.text(), "‹  Retour à l'historique")

    def test_watch_history_replay_detection(self):
        from core.models import WatchHistory
        h = WatchHistory(
            channel_id=1,
            channel_name="France 2 : Envoyé Spécial",
            stream_url="http://server.example:8080/timeshift/user/pass/90/2026-09-05:14-30/101.ts",
            group_title="TV Replay"
        )
        self.db.add_watch_history(h)
        items = self.db.get_recently_watched_items()
        self.assertTrue(len(items) >= 1)
        self.assertEqual(items[0]["channel"].stream_type, "replay")

    def test_player_controls_live_epg_and_frozen_slider(self):
        from ui.widgets.player_controls import PlayerControls
        from core.models import Channel, EPGProgram
        from datetime import datetime, timedelta

        controls = PlayerControls()
        ch_live = Channel(name="TF1 HD", stream_url="http://x/live.ts", stream_type="live", tvg_id="tf1.fr")

        # 1. Sans EPG : curseur figé au début (0), labels 00:00 et --:--
        controls.update_channel_info(ch_live, epg=None)
        self.assertFalse(controls.timeline_row.isHidden())
        self.assertEqual(controls.timeline_slider.value(), 0)
        self.assertEqual(controls.curr_time_label.text(), "00:00")
        self.assertEqual(controls.total_time_label.text(), "--:--")

        # set_position ne doit pas modifier la position ni les labels en direct sans EPG
        controls.set_position(120.0, 3600.0)
        self.assertEqual(controls.timeline_slider.value(), 0)
        self.assertEqual(controls.curr_time_label.text(), "00:00")

        # 2. Avec EPG en cours : début il y a 30m, fin dans 30m (~50%)
        now = datetime.now()
        st = now - timedelta(minutes=30)
        et = now + timedelta(minutes=30)
        epg = EPGProgram(
            tvg_id="tf1.fr",
            title="Journal de 20 Heures",
            start_time=st.isoformat(),
            end_time=et.isoformat()
        )
        controls.update_channel_info(ch_live, epg=epg)
        self.assertFalse(controls.timeline_row.isHidden())
        # Le slider doit être proche de 500 (50%)
        self.assertAlmostEqual(controls.timeline_slider.value(), 500, delta=20)
        self.assertEqual(controls.curr_time_label.text(), st.strftime("%H:%M"))
        self.assertEqual(controls.total_time_label.text(), et.strftime("%H:%M"))

        # set_position ne doit PAS écraser avec les valeurs de MPV
        controls.set_position(5.0, 10.0)
        self.assertAlmostEqual(controls.timeline_slider.value(), 500, delta=20)

        # 3. Le seek doit être bloqué en direct
        seek_emitted = []
        controls.seek_requested.connect(lambda target: seek_emitted.append(target))
        controls._on_slider_moved(800)
        controls._on_slider_released()
        self.assertEqual(len(seek_emitted), 0)

    def test_epg_timeline_midnight_rollover(self):
        from ui.widgets.epg_timeline import EPGTimelinePanel
        from core.models import Channel
        from datetime import date, timedelta

        panel = EPGTimelinePanel(self.db)
        canvas = panel.canvas

        # 1. Vérifier que get_now_x_position() ne renvoie pas None pour la date d'aujourd'hui
        now_pos = canvas.get_now_x_position()
        self.assertIsNotNone(now_pos)
        self.assertGreater(now_pos, 0)

        # 2. Vérifier que même si target_date était hier (ex: passage minuit à 00h15),
        # l'heure reste dans la plage 40h (-8h à +32h) et get_now_x_position() renvoie une coordonnée valide
        yesterday = date.today() - timedelta(days=1)
        canvas.target_date = yesterday
        from unittest.mock import patch
        midnight_time = datetime.combine(date.today(), datetime.min.time()) + timedelta(minutes=15)
        with patch("ui.widgets.epg_timeline.datetime") as mock_dt:
            mock_dt.now.return_value = midnight_time
            mock_dt.combine = datetime.combine
            mock_dt.min = datetime.min
            pos_yesterday = canvas.get_now_x_position()
            self.assertIsNotNone(pos_yesterday)

        # 3. Simuler le panel restant sur 'hier' lors du passage de minuit :
        # _on_live_tick doit détecter que date.today() a changé et basculer sur aujourd'hui
        ch = Channel(name="France 2", stream_url="http://x/f2.ts", stream_type="live", tvg_id="f2.fr")
        panel.current_channel = ch
        panel.current_date = yesterday
        panel.auto_scroll_to_now = True

        panel._on_live_tick()
        self.assertEqual(panel.current_date, date.today())
        self.assertEqual(panel.canvas.target_date, date.today())
        self.assertEqual(panel.date_label.text(), "Aujourd'hui")

        # 4. set_channel doit également réinitialiser sur date.today() si panel était sur un jour antérieur
        panel.current_date = yesterday
        ch2 = Channel(name="TF1", stream_url="http://x/tf1.ts", stream_type="live", tvg_id="tf1.fr")
        panel.set_channel(ch2)
        self.assertEqual(panel.current_date, date.today())
        self.assertEqual(panel.canvas.target_date, date.today())

    def test_search_text_changed_dashboard_and_settings(self):
        """Vérifie que la saisie ou le vidage de la recherche sur le dashboard ou les paramètres ne plante pas."""
        from ui.main_window import MainWindow
        from unittest.mock import MagicMock

        # On peut mocker ou tester directement la méthode sur une instance MainWindow légère
        win = MainWindow.__new__(MainWindow)
        win.current_section = "dashboard"
        win.channel_panel = MagicMock()
        # Ne doit pas lever d'AttributeError ni appeler channel_panel
        win._on_search_text_changed("")
        win._on_search_text_changed("batwoman")
        win.channel_panel.set_search_query.assert_not_called()

        win.current_section = "settings"
        win._on_search_text_changed("")
        win.channel_panel.set_search_query.assert_not_called()

        # En mode live, doit appeler set_search_query
        win.current_section = "live"
        win._on_search_text_changed("tf1")
        win.channel_panel.set_search_query.assert_called_once_with("tf1")

    def test_category_disabled_isolation_and_batwoman_search(self):
        """Vérifie que désactiver une catégorie (ex: V.O.) ne désactive pas les chaînes/séries de même nom dans une autre catégorie."""
        from core.models import Playlist, Channel

        p = Playlist(name="TestPL", url_or_path="http://test.m3u")
        p_id = self.db.add_playlist(p)

        c_vo = Channel(
            playlist_id=p_id,
            name="FR| Batwoman (2019)",
            stream_url="http://x/s1.mp4",
            stream_id="631599",
            stream_type="series",
            group_title="FR| V.O SOUS TITRÉS"
        )
        c_sf = Channel(
            playlist_id=p_id,
            name="FR| Batwoman (2019)",
            stream_url="http://x/s2.mp4",
            stream_id="632931",
            stream_type="series",
            group_title="FR| SCIENCE-FICTION | FANTASTIQUE"
        )
        self.db.save_channels_batch(p_id, [c_vo, c_sf])

        # Désactiver uniquement la catégorie "FR| V.O SOUS TITRÉS"
        self.db.save_groups_enabled_status(
            playlist_id=p_id,
            stream_type="series",
            enabled_groups=["FR| SCIENCE-FICTION | FANTASTIQUE"],
            disabled_groups=["FR| V.O SOUS TITRÉS"]
        )

        # Réimporter les chaînes en batch (comme lors d'une synchro)
        self.db.save_channels_batch(p_id, [c_vo, c_sf])

        # Vérifier que c_sf est toujours actif et trouvé dans la recherche
        res = self.db.get_channels(playlist_id=p_id, stream_type="series", search_query="Batwoman")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].stream_id, "632931")
        self.assertEqual(res[0].group_title, "FR| SCIENCE-FICTION | FANTASTIQUE")
        self.assertEqual(res[0].is_enabled, 1)

    def test_series_season_buttons_square_and_dropdown_over_10(self):
        """Vérifie que les boutons de saison ont un aspect carré (border-radius: 4px) et se changent en QComboBox si > 10 saisons."""
        from ui.widgets.series_details_view import SeriesDetailsView
        from PyQt6.QtWidgets import QPushButton, QComboBox

        view = SeriesDetailsView(self.db)

        # 1. Cas <= 10 saisons (ex: 3 saisons) -> boutons QPushButton avec border-radius: 4px
        view.episodes_by_season = {
            "1": [{"id": "1", "title": "Ep 1", "info": {}}],
            "2": [{"id": "2", "title": "Ep 2", "info": {}}],
            "3": [{"id": "3", "title": "Ep 3", "info": {}}]
        }
        view._populate_season_tabs()

        btn1 = view.seasons_tabs_layout.itemAt(0).widget()
        self.assertIsInstance(btn1, QPushButton)
        # Vérifier que la bordure arrondie (16px) a bien été remplacée par un aspect carré (4px)
        self.assertIn("border-radius: 4px;", btn1.styleSheet())
        self.assertNotIn("border-radius: 16px;", btn1.styleSheet())

        # Vérifier aussi le bouton inactif
        btn2 = view.seasons_tabs_layout.itemAt(1).widget()
        self.assertIsInstance(btn2, QPushButton)
        self.assertIn("border-radius: 4px;", btn2.styleSheet())
        self.assertNotIn("border-radius: 16px;", btn2.styleSheet())

        # Vérifier aussi quand la saison est complétée
        view._style_season_button(btn1, is_active=True, is_completed=True)
        self.assertIn("border-radius: 4px;", btn1.styleSheet())
        self.assertNotIn("border-radius: 16px;", btn1.styleSheet())

        # 2. Cas > 10 saisons (ex: 12 saisons) -> transformation en menu déroulant QComboBox
        view.episodes_by_season = {str(i): [{"id": str(i), "title": f"Ep {i}", "info": {}}] for i in range(1, 13)}
        view._populate_season_tabs()

        combo = view.seasons_tabs_layout.itemAt(0).widget()
        self.assertIsInstance(combo, QComboBox)
        self.assertEqual(combo.count(), 12)
        self.assertEqual(combo.itemData(0), "1")
        self.assertEqual(combo.itemData(11), "12")

        # Sélectionner la saison 5 dans le combo
        combo.setCurrentIndex(4)
        self.assertEqual(view.current_season, "5")

        view.stop_workers()
        view.close()

    def test_series_episodes_watched_isolation_and_no_wipe(self):
        """Vérifie que dévalider ou réinitialiser un épisode ne supprime pas les autres épisodes de la même série."""
        series_ch_id = 999
        url_ep1 = "http://server/series/u/p/101.mp4"
        url_ep2 = "http://server/series/u/p/102.mp4"
        url_ep3 = "http://server/series/u/p/103.mp4"

        # 1. Marquer 3 épisodes comme terminés (durée 3600s, position 3600s)
        self.db.save_playback_progress(channel_id=series_ch_id, stream_url=url_ep1, channel_name="Series - S01E01", position=3600.0, duration=3600.0)
        self.db.save_playback_progress(channel_id=series_ch_id, stream_url=url_ep2, channel_name="Series - S01E02", position=3600.0, duration=3600.0)
        self.db.save_playback_progress(channel_id=series_ch_id, stream_url=url_ep3, channel_name="Series - S01E03", position=3600.0, duration=3600.0)

        prog_map = self.db.get_all_playback_progress_map()
        self.assertIn(url_ep1, prog_map)
        self.assertIn(url_ep2, prog_map)
        self.assertIn(url_ep3, prog_map)

        # 2. Dévalider l'épisode 2 en appelant clear_playback_progress avec stream_url ET channel_id
        # (comme le faisait auparavant _on_episode_toggle_watched ou _play_next_channel)
        self.db.clear_playback_progress(channel_id=series_ch_id, stream_url=url_ep2)

        prog_map_after = self.db.get_all_playback_progress_map()
        # Épisode 2 doit être supprimé
        self.assertNotIn(url_ep2, prog_map_after)
        # CRUCIAL : Épisodes 1 et 3 NE DOIVENT PAS être supprimés !
        self.assertIn(url_ep1, prog_map_after)
        self.assertIn(url_ep3, prog_map_after)

        # 3. Vérifier qu'une lecture fugitive (ex: 15 secondes) ne dévalide pas un épisode déjà complété à 100%
        self.db.save_playback_progress(channel_id=series_ch_id, stream_url=url_ep1, channel_name="Series - S01E01", position=15.0, duration=3600.0)
        prog_ep1 = self.db.get_all_playback_progress_map()[url_ep1]
        self.assertEqual(prog_ep1[0], 3600.0)  # La position 3600s (100%) est restée préservée !

    def test_series_switch_clears_old_view_and_uses_cache(self):
        """Vérifie qu'en changeant de série, l'ancienne vue (onglets, cartes d'épisodes, boutons)
        est immédiatement purgée pour éviter les artefacts fantômes, et que le cache mémoire permet un chargement instantané."""
        from ui.widgets.series_details_view import SeriesDetailsView, _SERIES_INFO_CACHE
        from ui.widgets.series_details_view import EpisodeCardWidget
        from PyQt6.QtWidgets import QLabel

        p_id = self.db.add_playlist(Playlist(name="PL_Test", url_or_path="", playlist_type="xtream"))
        ch1 = Channel(playlist_id=p_id, stream_id="101", name="Series One", stream_type="series")
        ch2 = Channel(playlist_id=p_id, stream_id="202", name="Series Two", stream_type="series")

        view = SeriesDetailsView(self.db)

        # 1. Simuler des données chargées pour Series 1
        data_s1 = {
            "info": {"name": "Series One", "plot": "Plot 1"},
            "seasons": [{"season_number": "1"}],
            "episodes": {
                "1": [
                    {"id": "1001", "episode_num": 1, "title": "S01E01", "info": {}},
                    {"id": "1002", "episode_num": 2, "title": "S01E02", "info": {}},
                ]
            }
        }
        view.channel = ch1
        view.playlist = self.db.get_playlist(p_id)
        view._on_series_data_loaded(data_s1)

        # Vérifier que les onglets et épisodes de Series 1 sont bien présents
        self.assertEqual(view.seasons_tabs_layout.count(), 2)  # Button + stretch
        cards_s1 = [view.episodes_grid.itemAt(i).widget() for i in range(view.episodes_grid.count()) if isinstance(view.episodes_grid.itemAt(i).widget(), EpisodeCardWidget)]
        self.assertEqual(len(cards_s1), 2)

        # 2. Maintenant, basculer sur Series 2 (non encore dans le cache)
        # load_series() doit IMMÉDIATEMENT purger les onglets et les cartes de Series 1
        from unittest.mock import patch
        with patch.object(XtreamClient, "get_series_info", return_value={"info": {}, "seasons": [], "episodes": {}}):
            view.load_series(ch2)

            # Les anciennes cartes de Series 1 ne doivent PLUS être dans la grille
            remaining_cards = [view.episodes_grid.itemAt(i).widget() for i in range(view.episodes_grid.count()) if isinstance(view.episodes_grid.itemAt(i).widget(), EpisodeCardWidget)]
            self.assertEqual(len(remaining_cards), 0)

            # Il doit y avoir un placeholder de chargement propre
            placeholder = view.episodes_grid.itemAt(0).widget()
            self.assertIsInstance(placeholder, QLabel)
            self.assertIn("Chargement", placeholder.text())

            # Les onglets de saisons doivent être vides
            self.assertEqual(view.seasons_tabs_layout.count(), 0)

            if view._worker:
                view._worker.wait(1000)

        # 3. Mettre des données de Series 2 dans le cache mémoire
        data_s2 = {
            "info": {"name": "Series Two", "plot": "Plot 2"},
            "seasons": [{"season_number": "1"}],
            "episodes": {
                "1": [
                    {"id": "2001", "episode_num": 1, "title": "S02E01", "info": {}},
                ]
            }
        }
        _SERIES_INFO_CACHE[(p_id, "202")] = data_s2

        # 4. Recharger Series 2 : le rendu doit être instantané (0ms) depuis le cache
        with patch.object(XtreamClient, "get_series_info", return_value=data_s2):
            view.load_series(ch2)
            cards_s2 = [view.episodes_grid.itemAt(i).widget() for i in range(view.episodes_grid.count()) if isinstance(view.episodes_grid.itemAt(i).widget(), EpisodeCardWidget)]
            self.assertEqual(len(cards_s2), 1)
            if view._worker:
                view._worker.wait(2000)
            view.stop_workers()
        view.close()

    def test_series_with_season_zero_and_nested_list_episodes(self):
        """Vérifie que les séries dont les épisodes sont renvoyés sous forme de liste de listes
        (ex: Euphoria avec saisons 0, 1, 2, 3) sont correctement extraites, que la saison 0 est bien présente,
        et que la saison 1 est sélectionnée par défaut avec tous ses épisodes."""
        from ui.widgets.series_details_view import SeriesDetailsView, EpisodeCardWidget
        from PyQt6.QtWidgets import QPushButton

        p_id = self.db.add_playlist(Playlist(name="PL_Test", url_or_path="", playlist_type="xtream"))
        ch = Channel(playlist_id=p_id, stream_id="1094", name="Euphoria", stream_type="series")

        # Données représentatives de la réponse Xtream d'Euphoria (liste de listes avec saison 0)
        euphoria_data = {
            "info": {"name": "Euphoria", "plot": "Plot Euphoria"},
            "seasons": [{"season_number": 1}],
            "episodes": [
                # Index 0 = Saison 0 (2 épisodes spéciaux)
                [
                    {"id": "5001", "episode_num": 1, "season": 0, "title": "Trouble Don't Last Always", "info": {}},
                    {"id": "5002", "episode_num": 2, "season": 0, "title": "Fuck Anyone Who's Not a Sea Blob", "info": {}},
                ],
                # Index 1 = Saison 1 (8 épisodes)
                [
                    {"id": f"600{i}", "episode_num": i, "season": 1, "title": f"S01E{i}", "info": {}}
                    for i in range(1, 9)
                ],
                # Index 2 = Saison 2 (8 épisodes)
                [
                    {"id": f"700{i}", "episode_num": i, "season": 2, "title": f"S02E{i}", "info": {}}
                    for i in range(1, 9)
                ],
                # Index 3 = Saison 3 (8 épisodes)
                [
                    {"id": f"800{i}", "episode_num": i, "season": 3, "title": f"S03E{i}", "info": {}}
                    for i in range(1, 9)
                ],
            ]
        }

        # 1. Test dans SeriesDetailsView
        with patch("core.tmdb_client.find_best_trailer", return_value={}):
            view = SeriesDetailsView(self.db)
            view.channel = ch
            view.playlist = self.db.get_playlist(p_id)
            view._on_series_data_loaded(euphoria_data)

            # Vérifier que toutes les 4 saisons sont bien identifiées
            self.assertEqual(sorted(view.episodes_by_season.keys()), ["0", "1", "2", "3"])
            self.assertEqual(len(view.episodes_by_season["0"]), 2)
            self.assertEqual(len(view.episodes_by_season["1"]), 8)
            self.assertEqual(len(view.episodes_by_season["2"]), 8)
            self.assertEqual(len(view.episodes_by_season["3"]), 8)
            self.assertEqual(len(view.all_episodes_flat), 26)

            # Vérifier que la saison 1 est sélectionnée par défaut
            self.assertEqual(view.current_season, "1")

            # Vérifier que 8 cartes d'épisodes sont affichées pour la saison 1
            cards_s1 = [view.episodes_grid.itemAt(i).widget() for i in range(view.episodes_grid.count()) if isinstance(view.episodes_grid.itemAt(i).widget(), EpisodeCardWidget)]
            self.assertEqual(len(cards_s1), 8)

            # Vérifier les boutons d'onglets de saisons : Saison 0, 1, 2, 3
            season_buttons = [view.seasons_tabs_layout.itemAt(i).widget() for i in range(view.seasons_tabs_layout.count()) if isinstance(view.seasons_tabs_layout.itemAt(i).widget(), QPushButton)]
            self.assertEqual(len(season_buttons), 4)
            self.assertEqual(season_buttons[0].text(), "Saison 0")
            self.assertEqual(season_buttons[1].text(), "Saison 1")

            # Basculer sur la Saison 0
            view._on_season_tab_clicked("0")
            self.assertEqual(view.current_season, "0")
            cards_s0 = [view.episodes_grid.itemAt(i).widget() for i in range(view.episodes_grid.count()) if isinstance(view.episodes_grid.itemAt(i).widget(), EpisodeCardWidget)]
            self.assertEqual(len(cards_s0), 2)
            self.assertEqual(cards_s0[0].episode["title"], "Trouble Don't Last Always")

            view.stop_workers()
            view.close()

        # 2. Test dans SeriesEpisodesDialog
        from ui.dialogs.series_dialog import SeriesEpisodesDialog
        with patch.object(SeriesEpisodesDialog, "_load_series_info"):
            dlg = SeriesEpisodesDialog(ch, self.db)
            dlg._on_series_data_loaded(euphoria_data)
            self.assertEqual(sorted(dlg.episodes_by_season.keys()), ["0", "1", "2", "3"])
            self.assertEqual(dlg.season_combo.count(), 4)
            self.assertIn("Saison 0", dlg.season_combo.itemText(0))
            self.assertIn("Saison 1", dlg.season_combo.itemText(1))
            # Sélection par défaut : Saison 1
            self.assertEqual(dlg.season_combo.currentData(), "1")
            dlg.close()

    def test_channel_level_filtering_persistence_no_reset(self):
        """Vérifie que les chaînes désactivées individuellement dans une catégorie active
        ne sont JAMAIS réactivées lors de la réouverture de la base, de la réinitialisation des tables
        ou de la synchronisation des chaînes."""
        p_id = self.db.add_playlist(Playlist(name="PL_Test", url_or_path="", playlist_type="xtream"))

        # Créer 3 chaînes dans une même catégorie active "France HD"
        c1 = Channel(playlist_id=p_id, name="TF1 HD", stream_type="live", stream_id="101", group_title="France HD")
        c2 = Channel(playlist_id=p_id, name="TF1 SD", stream_type="live", stream_id="102", group_title="France HD")
        c3 = Channel(playlist_id=p_id, name="FRANCE 2 SD", stream_type="live", stream_id="103", group_title="France HD")
        self.db.save_channels_batch(p_id, [c1, c2, c3])

        # Récupérer les IDs générés
        channels = self.db.get_channels(playlist_id=p_id, stream_type="live")
        self.assertEqual(len(channels), 3)
        id_c2 = next(c.id for c in channels if c.name == "TF1 SD")
        id_c3 = next(c.id for c in channels if c.name == "FRANCE 2 SD")

        # 1. L'utilisateur désactive TF1 SD et FRANCE 2 SD (dans la catégorie France HD qui reste active)
        self.db.save_channels_enabled_status(enabled_ids=[], disabled_ids=[id_c2, id_c3])

        # Vérifier que seules 1 chaîne est visible (TF1 HD)
        active_channels = self.db.get_channels(playlist_id=p_id, stream_type="live")
        self.assertEqual(len(active_channels), 1)
        self.assertEqual(active_channels[0].name, "TF1 HD")

        # 2. Simuler un redémarrage de l'application (nouvelle instance Database pointant sur le même fichier)
        db2 = Database(self.db_path)

        # Vérifier que les chaînes désactivées sont toujours masquées et n'ont PAS été réinitialisées à is_enabled=1
        active_after_restart = db2.get_channels(playlist_id=p_id, stream_type="live")
        self.assertEqual(len(active_after_restart), 1)
        self.assertEqual(active_after_restart[0].name, "TF1 HD")

        # 3. Simuler une synchronisation / rechargement de la playlist (save_channels_batch avec replace=True)
        db2.save_channels_batch(p_id, [c1, c2, c3], replace=True)

        active_after_sync = db2.get_channels(playlist_id=p_id, stream_type="live")
        self.assertEqual(len(active_after_sync), 1)
        self.assertEqual(active_after_sync[0].name, "TF1 HD")

        # 4. Vérifier qu'activer la catégorie France HD ne réactive pas les chaînes individuellement filtrées
        db2.save_groups_enabled_status(playlist_id=p_id, stream_type="live", disabled_groups=[], enabled_groups=["France HD"])
        active_after_grp_enable = db2.get_channels(playlist_id=p_id, stream_type="live")
        self.assertEqual(len(active_after_grp_enable), 1)
        self.assertEqual(active_after_grp_enable[0].name, "TF1 HD")


if __name__ == "__main__":
    unittest.main()


