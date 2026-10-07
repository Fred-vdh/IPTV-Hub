"""
Module de synchronisation automatique et sélective des contenus IPTV (Direct, VOD, Séries, EPG).
Gère l'ordonnancement asynchrone, la file d'attente (queue) et la vérification des échéances
sans jamais bloquer l'interface ni perturber la lecture en cours.
"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

from core.models import Playlist
from core.database import Database
from core.xtream_client import XtreamClient
from core.m3u_parser import M3UParser
from core.epg_manager import EPGManager
from core.i18n import tr
from core.qt_worker_utils import is_worker_running

logger = logging.getLogger(__name__)


def format_last_sync(iso_str: Optional[str]) -> str:
    """Formate une date ISO de dernière synchronisation en texte lisible et localisé."""
    if not iso_str:
        return tr("Jamais")
    try:
        dt = datetime.fromisoformat(str(iso_str))
        now = datetime.now()
        diff = (now - dt).total_seconds()
        if diff < 60:
            return tr("À l'instant")
        hours = int(diff // 3600)
        if hours < 1:
            minutes = max(1, int(diff // 60))
            return f"{minutes} min"
        if hours < 24:
            return tr("Il y a {} h").format(hours)
        days = int(diff // 86400)
        if days == 1:
            return tr("Hier")
        if days < 7:
            return tr("Il y a {} jours").format(days)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(iso_str)[:16]


def is_sync_due(last_sync_iso: Optional[str], interval_days: int, fallback_date_iso: Optional[str] = None) -> bool:
    """
    Détermine si une synchronisation est échue d'après l'intervalle configuré en jours.
    Si last_sync_iso est absent, se base sur fallback_date_iso (ex: updated_at ou created_at de la playlist).
    """
    if interval_days <= 0:
        return False

    ref_str = last_sync_iso or fallback_date_iso
    if not ref_str:
        return True

    try:
        ref_dt = datetime.fromisoformat(str(ref_str))
        elapsed_days = (datetime.now() - ref_dt).total_seconds() / 86400.0
        return elapsed_days >= interval_days
    except Exception:
        return True


class ContentSyncWorker(QThread):
    """
    Worker asynchrone pour la synchronisation ciblée d'un type de contenu
    ('live', 'vod', 'series', 'epg' ou 'all') pour une playlist donnée.
    """
    progress = pyqtSignal(str)
    finished = pyqtSignal(str, int, bool, str)  # sync_type, playlist_id, success, message

    def __init__(self, db: Database, playlist_id: int, sync_type: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.playlist_id = playlist_id
        self.sync_type = sync_type

    def run(self):
        try:
            playlist = self.db.get_playlist(self.playlist_id)
            if not playlist:
                self.finished.emit(self.sync_type, self.playlist_id, False, tr("Liste de lecture introuvable"))
                return

            if self.sync_type == "epg":
                self._sync_epg(playlist)
            elif playlist.playlist_type == "xtream":
                self._sync_xtream(playlist)
            else:
                self._sync_m3u(playlist)

            self.finished.emit(self.sync_type, self.playlist_id, True, tr("Synchronisation terminée avec succès !"))

        except Exception as e:
            logger.error(f"Erreur durant la synchronisation ({self.sync_type}) de la playlist {self.playlist_id}: {e}", exc_info=True)
            self.finished.emit(self.sync_type, self.playlist_id, False, str(e))

    def _sync_epg(self, playlist: Playlist):
        epg_url = playlist.epg_url
        if not epg_url and playlist.playlist_type == "xtream":
            client = XtreamClient(
                server_url=playlist.server_url,
                username=playlist.username,
                password=playlist.password
            )
            epg_url = client.get_epg_url()
            if epg_url:
                playlist.epg_url = epg_url
                self.db.update_playlist(playlist)

        if not epg_url:
            self.progress.emit(tr("Aucune URL EPG configurée pour cette liste"))
            return

        self.progress.emit(tr("Téléchargement du guide des programmes (EPG)..."))
        epg_mgr = EPGManager(self.db)
        if epg_url.startswith("http://") or epg_url.startswith("https://"):
            epg_mgr.load_from_url(
                epg_url,
                progress_callback=lambda count: self.progress.emit(f"Parsing EPG : {count} programmes...")
            )
        else:
            epg_mgr.load_from_file(
                epg_url,
                progress_callback=lambda count: self.progress.emit(f"Parsing EPG : {count} programmes...")
            )
        self.db.update_playlist_sync_timestamp(self.playlist_id, "epg")

    def _sync_xtream(self, playlist: Playlist):
        client = XtreamClient(
            server_url=playlist.server_url,
            username=playlist.username,
            password=playlist.password
        )
        auth_data = client.authenticate()
        u_info = auth_data.get("user_info", {})
        if u_info:
            try:
                self.db.update_playlist_account_info(
                    self.playlist_id,
                    account_status=u_info.get("status"),
                    exp_date=str(u_info.get("exp_date", "")),
                    max_connections=str(u_info.get("max_connections", "1")),
                    active_cons=str(u_info.get("active_cons", "0"))
                )
            except Exception:
                pass

        # Direct
        if self.sync_type in ("live", "all"):
            self.progress.emit(tr("Récupération des chaînes en direct..."))
            live_channels = client.get_live_streams(playlist_id=self.playlist_id)
            self.progress.emit(f"Enregistrement de {len(live_channels)} chaînes en direct...")
            self.db.save_channels_batch(self.playlist_id, live_channels, replace=True, stream_type="live")
            self.db.update_playlist_sync_timestamp(self.playlist_id, "live")

        # VOD / Films
        if self.sync_type in ("vod", "all"):
            self.progress.emit(tr("Récupération des films VOD..."))
            vod_channels = client.get_vod_streams(playlist_id=self.playlist_id)
            self.progress.emit(f"Enregistrement de {len(vod_channels)} films VOD...")
            self.db.save_channels_batch(self.playlist_id, vod_channels, replace=True, stream_type="movie")
            self.db.update_playlist_sync_timestamp(self.playlist_id, "vod")

        # Séries
        if self.sync_type in ("series", "all"):
            self.progress.emit(tr("Récupération des séries..."))
            series_channels = client.get_series(playlist_id=self.playlist_id)
            self.progress.emit(f"Enregistrement de {len(series_channels)} séries...")
            self.db.save_channels_batch(self.playlist_id, series_channels, replace=True, stream_type="series")
            self.db.update_playlist_sync_timestamp(self.playlist_id, "series")

        # EPG pour 'all'
        if self.sync_type == "all":
            try:
                self._sync_epg(playlist)
            except Exception as epg_err:
                logger.warning(f"EPG sync error in 'all': {epg_err}")

    def _sync_m3u(self, playlist: Playlist):
        self.progress.emit(tr("Téléchargement du fichier M3U..."))
        if playlist.url_or_path.startswith("http://") or playlist.url_or_path.startswith("https://"):
            channels = M3UParser.parse_url(
                playlist.url_or_path,
                playlist_id=self.playlist_id,
                progress_callback=lambda c: self.progress.emit(f"Parsing M3U : {c} entrées...")
            )
        else:
            channels = M3UParser.parse_file(
                playlist.url_or_path,
                playlist_id=self.playlist_id,
                progress_callback=lambda c: self.progress.emit(f"Parsing M3U : {c} entrées...")
            )

        if self.sync_type == "all":
            self.progress.emit(f"Enregistrement de {len(channels)} entrées...")
            self.db.save_channels_batch(self.playlist_id, channels, replace=True)
            self.db.update_playlist_sync_timestamp(self.playlist_id, "live")
            self.db.update_playlist_sync_timestamp(self.playlist_id, "vod")
            self.db.update_playlist_sync_timestamp(self.playlist_id, "series")
            try:
                self._sync_epg(playlist)
            except Exception as epg_err:
                logger.warning(f"EPG sync error in M3U: {epg_err}")
        else:
            stream_type_filter = "movie" if self.sync_type == "vod" else self.sync_type
            filtered = [c for c in channels if (c.stream_type or "live") == stream_type_filter]
            self.progress.emit(f"Enregistrement de {len(filtered)} éléments ({self.sync_type})...")
            self.db.save_channels_batch(self.playlist_id, filtered, replace=True, stream_type=stream_type_filter)
            self.db.update_playlist_sync_timestamp(self.playlist_id, self.sync_type)


class AutoSyncManager(QObject):
    """
    Gestionnaire global orchestrant les synchronisations automatiques et manuelles.
    Maintient une file d'attente pour n'exécuter qu'une seule opération à la fois
    afin de protéger les ressources réseau, la base de données et le CPU.
    """
    sync_started = pyqtSignal(str, str)             # sync_type, playlist_name
    sync_progress = pyqtSignal(str, str)            # sync_type, message
    sync_finished = pyqtSignal(str, int, bool, str) # sync_type, playlist_id, success, message
    queue_empty = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._queue: List[Tuple[int, str]] = []  # [(playlist_id, sync_type), ...]
        self._current_worker: Optional[ContentSyncWorker] = None
        self._current_task: Optional[Tuple[int, str]] = None

        # Timer périodique de vérification en arrière-plan (toutes les 15 minutes)
        self._check_timer = QTimer(self)
        self._check_timer.setInterval(15 * 60 * 1000)
        self._check_timer.timeout.connect(self._on_periodic_check)
        self._check_timer.start()

        # Identifiant de la playlist active suivie
        self._active_playlist_id: Optional[int] = None

    def set_active_playlist_id(self, playlist_id: Optional[int]):
        """Définit la playlist active à surveiller en priorité."""
        self._active_playlist_id = playlist_id

    def is_running(self) -> bool:
        """Indique si une synchronisation est actuellement en cours."""
        # is_worker_running ne lève jamais, même si l'objet C++ du worker a déjà
        # été détruit par deleteLater() (sinon RuntimeError -> qFatal/abort).
        return is_worker_running(self._current_worker)

    def get_due_sync_types(self, playlist_id: int) -> List[str]:
        """
        Détermine la liste des synchronisations échues ('live', 'vod', 'series', 'epg')
        pour la playlist indiquée d'après les paramètres de l'application.
        """
        playlist = self.db.get_playlist(playlist_id)
        if not playlist:
            return []

        settings = self.db.get_settings()
        ts_map = self.db.get_playlist_sync_timestamps(playlist_id)
        fallback = playlist.updated_at or playlist.created_at

        due: List[str] = []

        # Direct (Live)
        if getattr(settings, "auto_sync_live", True):
            interval = getattr(settings, "sync_interval_live_days", 1)
            if is_sync_due(ts_map.get("live"), interval, fallback):
                due.append("live")

        # Films (VOD)
        if getattr(settings, "auto_sync_vod", True):
            interval = getattr(settings, "sync_interval_vod_days", 3)
            if is_sync_due(ts_map.get("vod"), interval, fallback):
                due.append("vod")

        # Séries
        if getattr(settings, "auto_sync_series", True):
            interval = getattr(settings, "sync_interval_series_days", 2)
            if is_sync_due(ts_map.get("series"), interval, fallback):
                due.append("series")

        # EPG
        if getattr(settings, "auto_refresh_epg", True):
            interval = getattr(settings, "epg_refresh_days", 1)
            if is_sync_due(ts_map.get("epg"), interval, fallback):
                due.append("epg")

        return due

    def check_and_run_due_syncs(self, playlist_id: Optional[int] = None):
        """Vérifie si des synchronisations sont échues et les enfile pour exécution."""
        target_id = playlist_id or self._active_playlist_id
        if not target_id:
            return

        due_types = self.get_due_sync_types(target_id)
        for st in due_types:
            self.enqueue_sync(target_id, st)

    def trigger_sync(self, playlist_id: int, sync_type: str):
        """Déclenche immédiatement une synchronisation (manuelle ou programmée)."""
        self.enqueue_sync(playlist_id, sync_type, priority=True)

    def enqueue_sync(self, playlist_id: int, sync_type: str, priority: bool = False):
        """Ajoute une tâche à la file d'attente et démarre si le worker est inactif."""
        task = (playlist_id, sync_type)

        # Éviter les doublons dans la file
        if task in self._queue or (self._current_task == task and self.is_running()):
            return

        if priority:
            self._queue.insert(0, task)
        else:
            self._queue.append(task)

        if not self.is_running():
            self._process_next()

    def _process_next(self):
        """Traite la prochaine tâche dans la file d'attente."""
        if not self._queue:
            self._current_task = None
            self.queue_empty.emit()
            return

        task = self._queue.pop(0)
        self._current_task = task
        playlist_id, sync_type = task

        playlist = self.db.get_playlist(playlist_id)
        pl_name = playlist.name if playlist else f"Playlist #{playlist_id}"

        self.sync_started.emit(sync_type, pl_name)

        self._current_worker = ContentSyncWorker(self.db, playlist_id, sync_type, parent=self)
        self._current_worker.progress.connect(lambda msg: self.sync_progress.emit(sync_type, msg))
        self._current_worker.finished.connect(self._on_worker_finished)
        self._current_worker.start()

    def _on_worker_finished(self, sync_type: str, playlist_id: int, success: bool, message: str):
        """Réception de la fin du worker en cours, notification et transition vers la tâche suivante."""
        self.sync_finished.emit(sync_type, playlist_id, success, message)
        # ATTENTION : `finished` est ici un signal personnalisé émis depuis run().
        # Le thread peut donc encore tourner : on attend sa fin réelle avant libération.
        worker = self._current_worker
        if worker is not None:
            worker.wait(5000)
            worker.deleteLater()
        self._current_worker = None
        self._current_task = None

        # Traiter immédiatement la tâche suivante dans la queue
        QTimer.singleShot(500, self._process_next)

    def _on_periodic_check(self):
        """Déclencheur automatique périodique du timer interne."""
        if self._active_playlist_id:
            self.check_and_run_due_syncs(self._active_playlist_id)
