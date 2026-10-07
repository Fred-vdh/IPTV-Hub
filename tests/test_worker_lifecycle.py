"""
Tests de non-régression : cycle de vie des workers QThread.

Bug corrigé (crash natif 0xc0000409 dans Qt6Core.dll) :
    RuntimeError: wrapped C/C++ object of type SeriesInfoWorker has been deleted

Déclenché par le clic sur le bouton "Retour" de l'OSD pendant la lecture d'un
épisode d'une série :
    MainWindow._return_to_vod_grid -> _stop_series_details_playback
    -> SeriesDetailsView.detach_video_widget -> stop_active_workers
    -> self._worker.isRunning()   # objet C++ déjà détruit par deleteLater()

PyQt transforme cette exception non gérée dans un slot en qFatal()/abort() :
l'application disparaît sans trace. Les helpers de core.qt_worker_utils doivent
rendre tous ces accès inoffensifs.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6 import sip  # noqa: E402
from PyQt6.QtCore import QEvent, QThread  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from core.qt_worker_utils import (  # noqa: E402
    is_worker_alive,
    is_worker_running,
    stop_tracked_worker,
    stop_worker,
    track_worker,
)
from core.database import Database  # noqa: E402
from core.player_controller import PlayerController  # noqa: E402
from core.xtream_client import XtreamClient  # noqa: E402
from ui.widgets.movie_details_view import MovieDetailsView  # noqa: E402
from ui.widgets.series_details_view import SeriesDetailsView  # noqa: E402


# Référence IMPÉRATIVE au niveau module : sans référence Python forte, le
# QApplication créé ici serait collecté par le GC puis détruit ; tout QWidget
# construit ensuite déclencherait alors
#     "QWidget: Must construct a QApplication before a QWidget"
# -> qFatal() -> abort() (0xc0000409), ce qui ferait passer un bug du test pour
# un bug du code testé.
_APP = QApplication.instance() or QApplication(sys.argv)


def _app():
    return _APP


class _DummyWorker(QThread):
    """Worker minimal : aucun accès réseau, durée très courte."""

    def run(self):
        self.msleep(20)


class TestWorkerLifecycleUtils(unittest.TestCase):
    """Le socle : plus aucun accès à un worker détruit ne doit lever."""

    def test_is_worker_running_survives_cpp_deletion(self):
        _app()
        worker = _DummyWorker()
        self.assertTrue(is_worker_alive(worker), "objet C++ bien vivant")
        self.assertFalse(is_worker_running(worker), "thread pas encore démarré")

        sip.delete(worker)  # équivalent d'un deleteLater() déjà exécuté

        # Avant correction : RuntimeError -> qFatal/abort de toute l'application.
        self.assertFalse(is_worker_alive(worker))
        self.assertFalse(is_worker_running(worker))
        stop_worker(worker, 50)  # ne doit rien lever

    def test_stop_tracked_worker_with_deleted_object(self):
        _app()
        owner = QWidget()
        stop_tracked_worker(owner, "_worker", 50)  # attribut absent -> inoffensif

        worker = _DummyWorker(owner)
        owner._worker = worker
        sip.delete(worker)
        stop_tracked_worker(owner, "_worker", 50)
        self.assertIsNone(owner._worker, "la référence morte doit être purgée")

    def test_track_worker_purges_reference_after_thread_end(self):
        app = _app()
        owner = QWidget()
        worker = _DummyWorker()
        track_worker(owner, "_worker", worker)
        self.assertIs(owner._worker, worker)

        worker.start()
        self.assertTrue(worker.wait(3000))
        for _ in range(20):
            app.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()

        self.assertIsNone(
            owner._worker,
            "la référence Python doit être oubliée quand l'objet C++ est détruit",
        )


class TestDetailsViewsSurviveDeletedWorkers(unittest.TestCase):
    """Scénario réel : arrêt de la lecture alors que les workers sont détruits."""

    def _db(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Database(Path(tmp.name) / "test.db")

    def test_series_details_stop_active_workers(self):
        _app()
        view = SeriesDetailsView(self._db())

        info_worker = _DummyWorker(view)
        trailer_worker = _DummyWorker(view)
        view._worker = info_worker
        view._trailer_worker = trailer_worker
        sip.delete(info_worker)
        sip.delete(trailer_worker)

        view.stop_active_workers()  # c'est exactement l'appel qui plantait

        self.assertIsNone(view._worker)
        self.assertIsNone(view._trailer_worker)

    def test_series_details_stop_workers_with_dead_worker(self):
        _app()
        view = SeriesDetailsView(self._db())
        worker = _DummyWorker(view)
        view._worker = worker
        sip.delete(worker)

        view.stop_workers()  # ne doit jamais lever

        self.assertIsNone(view._worker)

    def test_movie_details_stop_active_workers(self):
        _app()
        view = MovieDetailsView(self._db())

        dead = [_DummyWorker(view) for _ in range(3)]
        view._worker, view._trailer_worker, view._tmdb_worker = dead
        for worker in dead:
            sip.delete(worker)

        view.stop_active_workers()  # ne doit jamais lever

        self.assertIsNone(view._worker)
        self.assertIsNone(view._trailer_worker)
        self.assertIsNone(view._tmdb_worker)


class TestReturnFromOsdIntegration(unittest.TestCase):
    """Reparcours du geste utilisateur : fiche série -> lecture -> retour OSD."""

    def test_return_to_series_sheet_after_playback(self):
        from core.models import Channel as SeriesChannel
        from core.models import Playlist as SeriesPlaylist
        from ui.main_window import MainWindow

        app = _app()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Database(Path(tmp.name) / "test.db")
        pl_id = db.add_playlist(SeriesPlaylist(
            name="PL", url_or_path="http://x", playlist_type="xtream",
            server_url="http://x", username="u", password="p",
        ))
        series_ch = SeriesChannel(
            playlist_id=pl_id, name="|FR| Good Omens", stream_type="series",
            stream_id="1057", stream_url="xtream_series://1057",
        )

        with patch.object(XtreamClient, "get_series_info", return_value={"info": {}, "episodes": {}}), \
                patch("core.tmdb_client.find_best_trailer", return_value={}), \
                patch.object(PlayerController, "play"):
            window = MainWindow(db=db)
            self.addCleanup(window.close)

            window._open_series_details(series_ch)
            app.processEvents()

            # Le worker d'information se termine : son objet C++ est détruit par
            # deleteLater() alors que la fiche garde sa référence Python. C'est
            # cette référence morte qui faisait planter le clic sur "Retour".
            worker = getattr(window.series_details_view, "_worker", None)
            if worker is not None:
                worker.wait(3000)
                for _ in range(20):
                    app.processEvents()
                QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()

            window._is_playing_series_in_details = True
            window._return_to_vod_grid()  # clic sur le bouton Retour de l'OSD
            app.processEvents()

            self.assertFalse(getattr(window, "_is_playing_series_in_details", False))
            self.assertIsNone(getattr(window.series_details_view, "_worker", None))

