"""
Tests de non-régression : thread d'exécution des observers libmpv.

Bug corrigé (crash natif 0xC0000005 : l'application disparaît sans aucune trace) :

    Le clic sur « Lire maintenant » de l'overlay de fin d'épisode
    (ui/widgets/next_episode_overlay._on_play_now_clicked
     -> ui/main_window._on_outro_next_episode_requested
     -> core/player_controller.stop) déclenche une rafale d'événements libmpv
    (track-list, aid, sid, paused-for-cache, eof...).

python-mpv exécute les handlers enregistrés via ``observe_property`` DEPUIS SON
THREAD INTERNE (``mpv.py`` -> ``_loop``). Or ces handlers manipulaient des
QTimer, émettaient des signaux Qt et lisaient/écrivaient des propriétés libmpv
de façon synchrone : la mémoire était alors corrompue entre le thread libmpv et
le thread GUI, et le crash survenait au hasard (ici pendant l'enchaînement vers
l'épisode suivant).

Correctif (``core.player_controller._mpv_callback_in_qt_thread``) : tout
observer reçu hors du thread Qt du contrôleur est replanifié dans une file
d'attente protégée par un verrou, vidée par un QTimer du thread Qt (l'ordre des
notifications est préservé). Aucune API Qt n'est touchée depuis le thread de
libmpv : ni signal inter-threads, ni ``QThread.currentThread()``.
"""

import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QObject, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.player_controller import PlayerController  # noqa: E402

# Référence IMPÉRATIVE au niveau module : sans référence forte, le QApplication
# créé ici serait collecté par le GC puis détruit ; tout QWidget construit
# ensuite déclencherait alors
#     "QWidget: Must construct a QApplication before a QWidget"
# -> qFatal() -> abort() (0xc0000409), ce qui ferait passer un bug du test pour
# un bug du code testé.
_APP = QApplication.instance() or QApplication(sys.argv)


def _controller_without_libmpv() -> PlayerController:
    """Contrôleur Qt minimal : aucun libmpv, seul le câblage thread/observers compte."""
    ctrl = PlayerController.__new__(PlayerController)
    QObject.__init__(ctrl)
    ctrl._init_gui_dispatch()
    ctrl._stream_watchdog = QTimer(ctrl)
    ctrl._stall_monitor = QTimer(ctrl)
    ctrl._player = None
    ctrl._current_state = "stopped"
    ctrl._stream_has_started = False
    ctrl._subtitles_enabled = False
    ctrl._preferred_subtitle_lang = "off"
    ctrl._preferred_audio_lang = "fre"
    return ctrl


def _drain(ctrl: PlayerController) -> None:
    """Vide la file de callbacks libmpv, comme le fait le QTimer en production."""
    ctrl._drain_gui_calls()
    QApplication.processEvents()


class TestObserverThreadMarshalling(unittest.TestCase):
    """Les observers libmpv ne doivent jamais s'exécuter dans le thread libmpv."""

    def test_observer_from_libmpv_thread_is_replayed_in_qt_thread(self):
        ctrl = _controller_without_libmpv()
        seen = []
        ctrl.chapters_changed.connect(
            lambda chapters: seen.append(threading.current_thread())
        )

        worker = threading.Thread(
            target=ctrl._on_chapter_list,
            args=("chapter-list", [{"title": "Générique", "time": 0.0}]),
        )
        worker.start()
        worker.join()

        # Avant correction : le corps s'exécutait dans le thread libmpv et
        # l'access violation suivait immédiatement.
        self.assertEqual(seen, [], "le corps ne doit pas s'exécuter dans le thread libmpv")

        _drain(ctrl)
        self.assertEqual(len(seen), 1, "le corps doit être rejoué dans le thread Qt")
        self.assertIs(seen[0], threading.main_thread())

    def test_observer_from_qt_thread_stays_synchronous(self):
        ctrl = _controller_without_libmpv()
        seen = []
        ctrl.volume_changed.connect(seen.append)

        ctrl._on_volume_changed("volume", 42)

        # Appelé depuis le thread Qt (tests, code UI) : comportement inchangé.
        self.assertEqual(seen, [42])

    def test_track_list_observer_is_marshalled_too(self):
        """_on_track_list est celui qui déclenchait le crash : il doit être déporté."""
        ctrl = _controller_without_libmpv()
        seen = []
        ctrl.tracks_changed.connect(
            lambda tracks: seen.append(threading.current_thread())
        )
        tracks = [{"type": "video", "id": 1}, {"type": "audio", "id": 2}]

        worker = threading.Thread(
            target=ctrl._on_track_list, args=("track-list", tracks)
        )
        worker.start()
        worker.join()

        self.assertEqual(seen, [])

        _drain(ctrl)
        self.assertEqual(len(seen), 1)
        self.assertIs(seen[0], threading.main_thread())

    def test_pending_observers_are_dropped_after_cleanup(self):
        """Après cleanup(), plus aucune notification libmpv ne doit être traitée."""
        ctrl = _controller_without_libmpv()
        seen = []
        ctrl.chapters_changed.connect(seen.append)

        worker = threading.Thread(
            target=ctrl._on_chapter_list,
            args=("chapter-list", [{"title": "Fin", "time": 10.0}]),
        )
        worker.start()
        worker.join()

        ctrl.cleanup()
        _drain(ctrl)

        self.assertEqual(seen, [], "un lecteur détruit ne doit plus notifier l'interface")

    def test_pending_calls_are_executed_in_order_within_qt_thread(self):
        """La file remplace le signal inter-threads : ordre et thread préservés."""
        ctrl = _controller_without_libmpv()
        order = []
        ctrl.chapters_changed.connect(lambda chapters: order.append(chapters))

        workers = [
            threading.Thread(
                target=ctrl._on_chapter_list,
                args=("chapter-list", [{"title": f"ch{i}", "time": float(i)}]),
            )
            for i in range(3)
        ]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

        self.assertEqual(order, [], "rien ne doit s'exécuter dans le thread libmpv")

        drained = ctrl._drain_gui_calls()
        self.assertEqual(drained, 3, "les trois notifications doivent être rejouées")
        self.assertEqual(
            [c[0]["title"] for c in order], ["ch0", "ch1", "ch2"],
            "l'ordre des notifications libmpv doit être conservé",
        )

    def test_queue_is_thread_safe_under_concurrent_notifications(self):
        """Des notifications simultanées ne doivent en perdre aucune."""
        ctrl = _controller_without_libmpv()
        seen = []
        ctrl.chapters_changed.connect(seen.append)
        count = 40

        workers = [
            threading.Thread(
                target=ctrl._on_chapter_list,
                args=("chapter-list", [{"title": str(i), "time": 0.0}]),
            )
            for i in range(count)
        ]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

        drained = 0
        while drained < count:
            step = ctrl._drain_gui_calls()
            if not step:
                break
            drained += step

        self.assertEqual(len(seen), count, "aucune notification ne doit être perdue")

    def test_gui_thread_flag_does_not_use_qt_thread_api(self):
        """is_in_gui_thread repose sur l'identifiant de thread Python."""
        ctrl = _controller_without_libmpv()
        self.assertTrue(ctrl.is_in_gui_thread)

        result = []
        worker = threading.Thread(target=lambda: result.append(ctrl.is_in_gui_thread))
        worker.start()
        worker.join()
        self.assertEqual(result, [False])


    def test_every_observed_property_handler_is_marshalled(self):
        """Aucun handler enregistré par observe_property ne doit rester brut.

        C'est ce contrôle générique qui couvre aussi la navigation dans la barre
        de timeline : un seek fait re-notifier une rafale de propriétés
        (time-pos, playback-time, track-list, aid, sid, chapter-list,
        paused-for-cache, eof-reached...). Si l'une d'elles restait exécutée
        dans le thread libmpv, le seek redevenait un crash natif possible.
        """
        ctrl = _controller_without_libmpv()
        ctrl._render_mode = False
        ctrl._wid = None
        ctrl._hwdec_mode = "auto"
        ctrl._initial_volume = 80

        class _StubPlayer:
            """Faux lecteur : enregistre les handlers au lieu de créer libmpv."""

            def __init__(self, **kwargs):
                self.observed = {}

            def observe_property(self, name, handler):
                self.observed[name] = handler

        with patch("core.player_controller.mpv.MPV", _StubPlayer):
            ctrl._init_mpv()

        observed = ctrl._player.observed
        self.assertEqual(
            len(observed), 15,
            "les 15 observe_property de _init_mpv doivent être enregistrés",
        )
        not_marshalled = [
            name for name, handler in observed.items()
            if not hasattr(handler, "__wrapped__")
        ]
        self.assertEqual(
            not_marshalled, [],
            f"handlers encore exécutés dans le thread libmpv : {not_marshalled}",
        )


if __name__ == "__main__":
    unittest.main()
