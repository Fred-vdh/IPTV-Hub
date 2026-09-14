import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication

from core.models import Channel, Playlist
from core.database import Database
from core.player_controller import PlayerController
from core.xtream_client import XtreamClient
from ui.widgets.series_details_view import SeriesDetailsView
from ui.widgets.mpv_widget import MPVVideoWidget


def test_series_details_video_integration():
    _ = QApplication.instance() or QApplication(sys.argv)

    import tempfile
    temp_dir = tempfile.TemporaryDirectory()
    db_file = Path(temp_dir.name) / "test.db"
    db = Database(db_file)

    pl = Playlist(
        name="Test Series Playlist",
        url_or_path="http://example.com",
        playlist_type="xtream",
        server_url="http://example.com",
        username="user",
        password="pass"
    )
    pl_id = db.add_playlist(pl)

    series_ch = Channel(
        playlist_id=pl_id,
        name="Star Trek: Strange New Worlds",
        stream_url="xtream_series://1001",
        logo_url="",
        group_title="Science-Fiction",
        stream_type="series",
        stream_id="1001",
        rating="8.2",
        year="2022"
    )

    view = SeriesDetailsView(db)
    view.resize(1200, 800)
    view.show()
    QApplication.processEvents()

    assert hasattr(view, "nav_row_widget")
    assert hasattr(view, "details_container")
    assert hasattr(view, "scroll_area")
    assert view.nav_row_widget.isVisible()
    assert view.details_container.isVisible()

    mock_data = {
        "info": {
            "name": "Star Trek: Strange New Worlds",
            "plot": "Exploration spatiale...",
            "genre": "Science-Fiction",
            "releaseDate": "2022",
            "episode_run_time": "50",
            "rating": "8.2",
        },
        "episodes": {
            "1": [
                {
                    "id": "2001",
                    "episode_num": 1,
                    "title": "Episode 1",
                    "container_extension": "mkv",
                    "info": {"plot": "Plot 1", "duration_secs": 3000}
                }
            ]
        }
    }
    view.channel = series_ch
    view.playlist = pl
    view._on_series_data_loaded(mock_data)
    QApplication.processEvents()

    # Sans lecture : Description en haut, saisons/épisodes en bas
    assert view.details_layout.itemAt(0).widget() == view.hero_banner, "Hors vidéo, la description doit être en premier"
    assert view.details_layout.itemAt(1).widget() == view.seasons_container, "Hors vidéo, les saisons doivent être en dessous"

    player_controller = PlayerController()
    video_widget = MPVVideoWidget(player_controller)
    video_widget.resize(600, 400)

    view.attach_video_widget(video_widget)
    QApplication.processEvents()

    assert view.content_layout.itemAt(0).widget() == video_widget
    assert view.nav_row_widget.isHidden()
    assert "Lecture en cours" in view.resume_btn.text()
    assert not view.resume_btn.isEnabled()
    # Pendant la lecture : Saisons/épisodes en premier sous la vidéo, description en bas
    assert view.details_layout.itemAt(0).widget() == view.seasons_container, "Pendant la lecture, les saisons doivent être en premier"
    assert view.details_layout.itemAt(1).widget() == view.hero_banner, "Pendant la lecture, la description doit être tout en bas"

    test_widths = [1000, 1200, 1400, 1600]
    for w in test_widths:
        view.resize(w, 800)
        QApplication.processEvents()
        view._update_video_geometry()
        QApplication.processEvents()

        vp_w = view.scroll_area.viewport().width()
        margins = view.content_layout.contentsMargins()
        expected_content_w = max(320, vp_w - margins.left() - margins.right())
        expected_h = int(expected_content_w * 9 / 16)

        actual_h = video_widget.height()
        assert abs(actual_h - expected_h) <= 1, f"Largeur {w}: actual={actual_h} != expected={expected_h}"

    print("[PASS] Calcul geometrique 16:9 valide sur toutes les largeurs !")

    view.set_fullscreen(True)
    QApplication.processEvents()
    assert view.details_container.isHidden(), "details_container doit etre masque en plein ecran"
    assert view.nav_row_widget.isHidden(), "nav_row_widget doit etre masque en plein ecran"

    view.set_fullscreen(False)
    QApplication.processEvents()
    assert view.details_container.isVisible(), "details_container doit etre reaffiche hors plein ecran"

    view.detach_video_widget(video_widget)
    QApplication.processEvents()
    assert view.content_layout.indexOf(video_widget) == -1, "video_widget doit etre retire du layout"
    assert view.nav_row_widget.isVisible(), "nav_row_widget doit etre reaffiche"
    assert view.resume_btn.isEnabled(), "resume_btn doit etre reactive"
    # Après arrêt de la lecture : retour à la normale (description en haut, saisons en dessous)
    assert view.details_layout.itemAt(0).widget() == view.hero_banner, "Après arrêt, la description doit être revenue en premier"
    assert view.details_layout.itemAt(1).widget() == view.seasons_container, "Après arrêt, les saisons doivent être revenues en dessous"

    print("[PASS] Attachement, 16:9, plein ecran et detachement valides avec succes !")
    view.close()
    player_controller.cleanup()


def test_main_window_series_navigation():
    from ui.main_window import MainWindow

    _ = QApplication.instance() or QApplication(sys.argv)

    import tempfile
    temp_dir = tempfile.TemporaryDirectory()
    db_file = Path(temp_dir.name) / "test_mw.db"
    db = Database(db_file)

    pl = Playlist(
        name="Test Series Playlist",
        url_or_path="http://example.com",
        playlist_type="xtream",
        server_url="http://example.com",
        username="user",
        password="pass"
    )
    pl_id = db.add_playlist(pl)

    series_ch = Channel(
        playlist_id=pl_id,
        name="Star Trek: Strange New Worlds",
        stream_url="xtream_series://1001",
        logo_url="",
        group_title="Science-Fiction",
        stream_type="series",
        stream_id="1001",
        rating="8.2",
        year="2022"
    )
    db.save_channels_batch(pl_id, [series_ch])

    window = MainWindow(db)
    window.resize(1280, 720)
    window.show()
    QApplication.processEvents()

    # 1. Ouverture de la fiche série
    window._open_series_details(series_ch)
    QApplication.processEvents()

    assert window.current_section == "series", f"Section attendue 'series', obtenu {window.current_section}"
    assert window.main_content_stack.currentIndex() == 3, f"Index attendu 3, obtenu {window.main_content_stack.currentIndex()}"
    assert window.categories_panel.isVisible(), "Le panneau catégories Séries doit être affiché à gauche"
    assert "Séries" in window.categories_panel.title_label.text(), f"Titre des catégories inattendu: {window.categories_panel.title_label.text()}"
    assert window.series_details_view.details_layout.itemAt(0).widget() == window.series_details_view.hero_banner, "La description doit être en haut hors lecture"
    print("[PASS] _open_series_details affiche bien la fiche avec le panneau des catégories Séries et la description en haut !")

    # 2. Lancement d'un épisode
    window._on_series_play_episode_requested(series_ch, [series_ch], 0, 0.0)
    QApplication.processEvents()

    assert getattr(window, "_is_playing_series_in_details", False), "_is_playing_series_in_details doit être True"
    assert window.categories_panel.isVisible(), "Le panneau catégories Séries doit RESTER affiché pendant la lecture"
    assert window.main_content_stack.currentIndex() == 3, "Doit rester sur la vue SeriesDetailsView (index 3)"
    assert window.series_details_view.content_layout.itemAt(0).widget() == window.video_widget, "Le lecteur doit être attaché au sommet de la fiche série"
    assert "fiche série" in window.video_widget.controls.back_btn.text(), f"Texte bouton retour inattendu: {window.video_widget.controls.back_btn.text()}"
    assert window.series_details_view.details_layout.itemAt(0).widget() == window.series_details_view.seasons_container, "Les saisons doivent passer sous la vidéo pendant la lecture"
    assert window.series_details_view.details_layout.itemAt(1).widget() == window.series_details_view.hero_banner, "La description doit être tout en bas pendant la lecture"
    print("[PASS] _on_series_play_episode_requested attache le lecteur en 16:9 dans la fiche série, inverse les sections et garde les catégories !")

    # 3. Arrêt de la lecture de l'épisode (via retour OSD)
    window._return_to_vod_grid()
    QApplication.processEvents()

    assert not getattr(window, "_is_playing_series_in_details", False), "_is_playing_series_in_details doit être False après arrêt"
    assert window.main_content_stack.currentIndex() == 3, "Doit rester sur la fiche série"
    assert window.categories_panel.isVisible(), "Le panneau catégories Séries doit rester visible"
    assert window.series_details_view.content_layout.indexOf(window.video_widget) == -1, "video_widget doit être détaché de la fiche série"
    assert window.series_details_view.details_layout.itemAt(0).widget() == window.series_details_view.hero_banner, "La description doit revenir en haut après arrêt"
    print("[PASS] _return_to_vod_grid arrête la lecture et rétablit l'ordre standard (description en haut) !")

    window.close()
    print("[PASS] Tous les tests MainWindow Séries sont passés avec succès !")


class TestSeriesVideoIntegration(unittest.TestCase):
    def test_series_details_video_integration(self):
        with patch.object(XtreamClient, "get_series_info", return_value={"info": {}, "seasons": [], "episodes": {}}), \
             patch("core.tmdb_client.find_best_trailer", return_value={}):
            test_series_details_video_integration()

    def test_main_window_series_navigation(self):
        with patch.object(XtreamClient, "get_series_info", return_value={"info": {}, "seasons": [], "episodes": {}}), \
             patch("core.tmdb_client.find_best_trailer", return_value={}), \
             patch.object(PlayerController, "play"):
            test_main_window_series_navigation()


if __name__ == "__main__":
    unittest.main()


