"""
Gestion du cycle de vie des workers QThread utilisés par les vues et dialogues Qt.

Pourquoi ce module existe
-------------------------
PyQt transforme toute exception Python non gérée dans un slot en appel à
``qFatal()`` -> ``abort()`` : l'application se ferme alors brutalement avec un
crash natif ``0xc0000409`` dans Qt6Core.dll, sans traceback ni message (la
console est désactivée en production).

Or un QThread détruit côté C++ par ``deleteLater()`` alors que la vue conserve
encore une référence Python déclenche exactement cette situation : le premier
accès ultérieur à une méthode du worker (``isRunning()``, ``wait()`` ...) lève

    RuntimeError: wrapped C/C++ object of type X has been deleted

et fait donc planter toute l'application (ex. crash au clic sur le bouton
"Retour" de l'OSD : detach_video_widget -> stop_active_workers -> _worker.isRunning()).

Les deux helpers ci-dessous suppriment ce piège :
  * :func:`track_worker` enregistre le worker et oublie automatiquement la
    référence Python au moment où l'objet C++ est détruit ;
  * :func:`is_worker_running` / :func:`stop_worker` ne lèvent jamais, même si
    l'objet C++ a déjà été libéré.
"""

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import QThread


def is_worker_alive(worker: Optional[Any]) -> bool:
    """Retourne True si le worker existe encore côté C++."""
    if worker is None:
        return False
    try:
        worker.isRunning()
    except RuntimeError:
        # L'objet C++ a été détruit (deleteLater) mais le wrapper Python survit.
        return False
    except Exception:
        return False
    return True


def is_worker_running(worker: Optional[Any]) -> bool:
    """Retourne True si le worker tourne encore ; False s'il est arrêté ou détruit."""
    if not is_worker_alive(worker):
        return False
    try:
        return bool(worker.isRunning())
    except Exception:
        return False


def forget_worker(owner: Any, attr_name: str, worker: Any) -> None:
    """Remet ``owner.<attr_name>`` à None si elle référence encore ce worker."""
    try:
        if getattr(owner, attr_name, None) is worker:
            setattr(owner, attr_name, None)
    except Exception:
        pass


def track_worker(owner: Any, attr_name: str, worker: QThread) -> QThread:
    """
    Enregistre ``worker`` sur ``owner.<attr_name>`` et branche sa destruction.

    Le signal natif ``QThread.finished`` est utilisé explicitement : plusieurs
    workers redéfinissent ``finished`` avec une signature métier (``dict``), ce
    qui masquerait le signal de QThread et empêcherait la connexion à
    ``deleteLater``.
    """
    setattr(owner, attr_name, worker)

    try:
        native_finished = QThread.finished.__get__(worker, QThread)
    except Exception:
        native_finished = None

    if native_finished is not None:
        # Oubli de la référence Python *et* suppression de l'objet C++.
        native_finished.connect(lambda _o=owner, _n=attr_name, _w=worker: forget_worker(_o, _n, _w))
        native_finished.connect(worker.deleteLater)

    return worker


def stop_worker(worker: Optional[Any], timeout_ms: int = 200) -> None:
    """Arrête coopérativement un worker sans jamais lever d'exception."""
    if not is_worker_alive(worker):
        return
    try:
        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(timeout_ms)
    except Exception:
        pass


def stop_tracked_worker(owner: Any, attr_name: str, timeout_ms: int = 200) -> None:
    """Arrête le worker référencé par ``owner.<attr_name>`` puis purge la référence."""
    worker = getattr(owner, attr_name, None)
    if worker is None:
        return
    stop_worker(worker, timeout_ms)
    setattr(owner, attr_name, None)
