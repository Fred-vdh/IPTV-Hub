"""
Gestionnaire et threads de téléchargement en arrière-plan pour les flux VOD d'IPTV Hub.
Implémente la file FIFO (1 flux actif à la fois), reprise Range HTTP (.part),
persistance JSON, pause lors du visionnage, et statistiques de stockage.
"""

import json
import os
import re
import shutil
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
import requests
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.database import get_data_dir


def sanitize_filename(name: str) -> str:
    """Supprime les caractères interdits pour un nom de fichier Windows/OS."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean or "video"


def get_default_download_dir() -> str:
    """Retourne le dossier Téléchargements/IPTV Hub par défaut."""
    home_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.exists(home_downloads):
        home_downloads = os.path.join(os.path.expanduser("~"), "Téléchargements")
    if not os.path.exists(home_downloads):
        home_downloads = os.path.expanduser("~")

    hub_dir = os.path.join(home_downloads, "IPTV Hub")
    try:
        os.makedirs(hub_dir, exist_ok=True)
    except Exception:
        pass
    return hub_dir


class DownloadStatus:
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class DownloadItem:
    id: str  # ex: "movie_123" ou "series_456_s1_e789"
    stream_id: str
    title: str
    sub_title: str = ""
    poster_url: Optional[str] = None
    stream_url: str = ""
    local_file_path: str = ""
    stream_type: str = "movie"  # "movie" ou "series"
    season_number: int = 0
    episode_number: int = 0
    container_extension: str = "mp4"
    status: str = DownloadStatus.QUEUED
    total_bytes: int = 0
    downloaded_bytes: int = 0
    progress_percent: int = 0
    speed_bytes_per_sec: int = 0
    added_date: float = 0.0
    error_message: Optional[str] = None
    user_agent: Optional[str] = None
    custom_headers: Optional[Dict[str, str]] = None

    def __post_init__(self):
        if not self.added_date:
            self.added_date = time.time()
        if self.custom_headers is None:
            self.custom_headers = {}

    def get_formatted_size(self) -> str:
        bytes_val = self.total_bytes if self.total_bytes > 0 else self.downloaded_bytes
        if bytes_val <= 0:
            return "-- Mo"
        mb = bytes_val / (1024.0 * 1024.0)
        if mb >= 1024:
            return f"{mb / 1024.0:.2f} Go"
        return f"{mb:.1f} Mo"

    def get_formatted_progress(self) -> str:
        if self.total_bytes > 0:
            cur_mb = self.downloaded_bytes / (1024.0 * 1024.0)
            tot_mb = self.total_bytes / (1024.0 * 1024.0)
            if tot_mb >= 1024:
                return f"{cur_mb / 1024.0:.2f} / {tot_mb / 1024.0:.2f} Go ({self.progress_percent}%)"
            return f"{cur_mb:.1f} / {tot_mb:.1f} Mo ({self.progress_percent}%)"
        cur_mb = self.downloaded_bytes / (1024.0 * 1024.0)
        return f"{cur_mb:.1f} Mo"

    def get_formatted_speed(self) -> str:
        if self.speed_bytes_per_sec <= 0:
            return ""
        kb = self.speed_bytes_per_sec / 1024.0
        mb = kb / 1024.0
        if mb >= 1.0:
            return f"{mb:.1f} Mo/s"
        return f"{int(kb)} Ko/s"

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadItem":
        # Filtrer les clés inconnues
        known_keys = {
            "id", "stream_id", "title", "sub_title", "poster_url", "stream_url",
            "local_file_path", "stream_type", "season_number", "episode_number",
            "container_extension", "status", "total_bytes", "downloaded_bytes",
            "progress_percent", "speed_bytes_per_sec", "added_date", "error_message",
            "user_agent", "custom_headers"
        }
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


@dataclass
class StorageStats:
    total_bytes: int
    available_bytes: int
    downloads_occupied_bytes: int

    def get_formatted_available(self) -> str:
        gb = self.available_bytes / (1024.0 * 1024.0 * 1024.0)
        return f"{gb:.1f} Go libres"

    def get_formatted_occupied(self) -> str:
        mb = self.downloads_occupied_bytes / (1024.0 * 1024.0)
        if mb >= 1024:
            return f"{mb / 1024.0:.2f} Go utilisés par IPTV Hub"
        return f"{mb:.1f} Mo utilisés par IPTV Hub"


class DownloadWorkerThread(QThread):
    """Thread gérant un téléchargement individuel avec reprise HTTP Range, throttling et retries."""
    progress = pyqtSignal(int, int, str)       # (downloaded_bytes, total_bytes, speed_str)
    download_finished = pyqtSignal(str)        # output_path
    download_error = pyqtSignal(str)           # error_message

    def __init__(self, item: DownloadItem, speed_limit_bytes_per_sec: int = 0, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.item = item
        self.speed_limit_bytes_per_sec = max(0, speed_limit_bytes_per_sec)
        self._is_cancelled = False
        self._is_paused = False

    def set_speed_limit(self, limit: int):
        self.speed_limit_bytes_per_sec = max(0, limit)

    def cancel(self):
        self._is_cancelled = True

    def pause(self):
        self._is_paused = True

    def run(self):
        part_path = f"{self.item.local_file_path}.part"
        final_path = self.item.local_file_path
        max_retries = 3
        retry_count = 0

        dest_dir = os.path.dirname(final_path)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception:
            pass

        while not self._is_cancelled and not self._is_paused and retry_count <= max_retries:
            try:
                downloaded_so_far = os.path.getsize(part_path) if os.path.exists(part_path) else 0
                self.item.downloaded_bytes = downloaded_so_far
                self.item.status = DownloadStatus.DOWNLOADING
                if retry_count == 0:
                    self.item.error_message = None

                req_headers = {"User-Agent": self.item.user_agent or "Mozilla/5.0"}
                if self.item.custom_headers:
                    req_headers.update(self.item.custom_headers)

                if downloaded_so_far > 0:
                    req_headers["Range"] = f"bytes={downloaded_so_far}-"

                with requests.get(self.item.stream_url, headers=req_headers, stream=True, timeout=25) as r:
                    if r.status_code not in (200, 206):
                        raise RuntimeError(f"Erreur HTTP {r.status_code}: {r.reason}")

                    content_length = int(r.headers.get("content-length", 0))
                    if content_length > 0:
                        if r.status_code == 206:
                            self.item.total_bytes = content_length + downloaded_so_far
                        else:
                            self.item.total_bytes = content_length

                    file_mode = "ab" if (r.status_code == 206 and downloaded_so_far > 0) else "wb"
                    if file_mode == "wb":
                        downloaded_so_far = 0

                    retry_count = 0
                    self.item.error_message = None

                    start_time = time.time()
                    last_notify_time = start_time
                    bytes_since_last_notify = 0
                    smoothed_speed = 0

                    # Régulation de débit (Throttling / Rate limiter)
                    rate_limit_start_time = time.time()
                    bytes_in_rate_window = 0

                    with open(part_path, file_mode) as f:
                        for chunk in r.iter_content(chunk_size=128 * 1024):
                            if self._is_cancelled or self._is_paused:
                                f.flush()
                                break

                            if chunk:
                                f.write(chunk)
                                chunk_len = len(chunk)
                                downloaded_so_far += chunk_len
                                bytes_since_last_notify += chunk_len
                                bytes_in_rate_window += chunk_len
                                self.item.downloaded_bytes = downloaded_so_far

                                if self.item.total_bytes > 0:
                                    self.item.progress_percent = min(100, max(0, int((downloaded_so_far / self.item.total_bytes) * 100)))

                                # Régulation de débit pour ne pas saturer le serveur
                                limit = self.speed_limit_bytes_per_sec
                                if limit > 0:
                                    elapsed_in_window = time.time() - rate_limit_start_time
                                    expected_time = bytes_in_rate_window / float(limit)
                                    if expected_time > elapsed_in_window:
                                        wait_sec = min(1.0, expected_time - elapsed_in_window)
                                        if wait_sec > 0.010:
                                            time.sleep(wait_sec)
                                    if time.time() - rate_limit_start_time >= 1.0:
                                        rate_limit_start_time = time.time()
                                        bytes_in_rate_window = 0

                                now = time.time()
                                dt = now - last_notify_time
                                if dt >= 0.5:
                                    inst_speed = int(bytes_since_last_notify / dt) if dt > 0 else 0
                                    smoothed_speed = inst_speed if smoothed_speed == 0 else int(smoothed_speed * 0.7 + inst_speed * 0.3)
                                    self.item.speed_bytes_per_sec = smoothed_speed
                                    last_notify_time = now
                                    bytes_since_last_notify = 0

                                    speed_str = self.item.get_formatted_speed()
                                    self.progress.emit(downloaded_so_far, self.item.total_bytes, speed_str)

                    if self._is_cancelled:
                        self.item.status = DownloadStatus.PAUSED
                        self.item.speed_bytes_per_sec = 0
                        return

                    if self._is_paused:
                        self.item.status = DownloadStatus.PAUSED
                        self.item.speed_bytes_per_sec = 0
                        return

                    # Vérification si complété normalement
                    # Si total_bytes est connu et atteint, ou si fin de flux HTTP normale
                    if self.item.total_bytes <= 0 or downloaded_so_far >= self.item.total_bytes:
                        if os.path.exists(final_path):
                            try:
                                os.unlink(final_path)
                            except Exception:
                                pass
                        try:
                            os.rename(part_path, final_path)
                        except Exception:
                            shutil.copy2(part_path, final_path)
                            try:
                                os.unlink(part_path)
                            except Exception:
                                pass

                        self.item.status = DownloadStatus.COMPLETED
                        self.item.progress_percent = 100
                        self.item.speed_bytes_per_sec = 0
                        self.item.error_message = None
                        self.item.downloaded_bytes = os.path.getsize(final_path) if os.path.exists(final_path) else downloaded_so_far
                        if self.item.total_bytes <= 0:
                            self.item.total_bytes = self.item.downloaded_bytes
                        self.progress.emit(self.item.downloaded_bytes, self.item.total_bytes, "Terminé")
                        self.download_finished.emit(final_path)
                        return

            except Exception as e:
                if self._is_cancelled or self._is_paused:
                    return
                retry_count += 1
                if retry_count <= max_retries:
                    self.item.speed_bytes_per_sec = 0
                    self.item.error_message = f"Reconnexion ({retry_count}/{max_retries})..."
                    self.progress.emit(self.item.downloaded_bytes, self.item.total_bytes, self.item.error_message)
                    time.sleep(2 * retry_count)
                else:
                    self.item.status = DownloadStatus.ERROR
                    self.item.error_message = f"Erreur : {e}"
                    self.item.speed_bytes_per_sec = 0
                    self.download_error.emit(str(e))
                    return


# Rétrocompatibilité : DownloadTask enveloppe le worker ou est un alias
DownloadTask = DownloadWorkerThread


class DownloadManager(QObject):
    """
    Gestionnaire singleton de téléchargement pour IPTV Hub.
    Gère la file FIFO (1 flux à la fois), la persistance, la mise en pause/reprise,
    et les statistiques de stockage.
    """
    _instance: Optional["DownloadManager"] = None

    download_progress = pyqtSignal(object)       # émet DownloadItem
    download_status_changed = pyqtSignal(object) # émet DownloadItem
    downloads_changed = pyqtSignal()

    @classmethod
    def instance(cls) -> "DownloadManager":
        if cls._instance is None:
            cls._instance = DownloadManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._downloads_list: List[DownloadItem] = []
        self._active_workers: Dict[str, DownloadWorkerThread] = {}
        self._paused_for_playback_ids: List[str] = []
        self._speed_limit_bytes_per_sec: int = 0
        self._load_speed_limit_from_settings()
        self._json_file = os.path.join(get_data_dir(), "downloads.json")
        self._load_saved_downloads()

    def _load_speed_limit_from_settings(self):
        try:
            from core.database import Database
            self._speed_limit_bytes_per_sec = Database().get_settings().download_speed_limit
        except Exception:
            self._speed_limit_bytes_per_sec = 0

    def _load_saved_downloads(self):
        self._downloads_list.clear()
        if os.path.exists(self._json_file):
            try:
                with open(self._json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item_dict in data:
                            item = DownloadItem.from_dict(item_dict)
                            final_file = item.local_file_path
                            part_file = f"{item.local_file_path}.part"

                            # 1. Si terminé, vérifier que le fichier existe physiquement
                            if item.status == DownloadStatus.COMPLETED:
                                if not os.path.exists(final_file) or os.path.getsize(final_file) == 0:
                                    continue

                            # 2. Si erreur, vérifier s'il reste un .part ou un fichier
                            if item.status == DownloadStatus.ERROR:
                                has_part = os.path.exists(part_file) and os.path.getsize(part_file) > 0
                                has_final = os.path.exists(final_file) and os.path.getsize(final_file) > 0
                                if not has_part and not has_final:
                                    continue

                            # 0. Ignorer les entrées incomplètes ou factices sans URL ni fichier
                            if not item.stream_url and not item.local_file_path:
                                continue

                            # 3. Si l'application a été fermée en cours de téléchargement
                            if item.status in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED):
                                item.status = DownloadStatus.PAUSED
                                item.error_message = "En pause"
                                item.speed_bytes_per_sec = 0

                            self._downloads_list.append(item)
            except Exception:
                pass
        self._persist_downloads()

    def _persist_downloads(self):
        try:
            data = [item.to_dict() for item in self._downloads_list]
            with open(self._json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _notify_progress(self, item: DownloadItem):
        self.download_progress.emit(item)

    def _notify_status(self, item: DownloadItem):
        self._persist_downloads()
        self.download_status_changed.emit(item)
        self.downloads_changed.emit()

    def get_speed_limit(self) -> int:
        return self._speed_limit_bytes_per_sec

    def set_speed_limit(self, limit_bytes_per_sec: int):
        """Définit la vitesse maximale de téléchargement en octets/s (0 = illimité) et l'applique aux threads actifs."""
        self._speed_limit_bytes_per_sec = max(0, limit_bytes_per_sec)
        for worker in self._active_workers.values():
            worker.set_speed_limit(self._speed_limit_bytes_per_sec)

    def get_download_directory(self) -> str:
        """Retourne le dossier configuré par l'utilisateur ou le dossier par défaut."""
        try:
            from core.database import Database
            custom_dir = Database().get_settings().download_dir
            if custom_dir and os.path.isdir(custom_dir):
                return custom_dir
            elif custom_dir:
                try:
                    os.makedirs(custom_dir, exist_ok=True)
                    return custom_dir
                except Exception:
                    pass
        except Exception:
            pass
        return get_default_download_dir()

    def get_all_downloads(self) -> List[DownloadItem]:
        return list(self._downloads_list)

    def get_ongoing_downloads(self) -> List[DownloadItem]:
        return [
            item for item in self._downloads_list
            if item.status in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED, DownloadStatus.PAUSED, DownloadStatus.ERROR)
        ]

    def get_completed_downloads(self) -> List[DownloadItem]:
        return [
            item for item in self._downloads_list
            if item.status == DownloadStatus.COMPLETED and os.path.exists(item.local_file_path)
        ]

    def get_download(self, item_id: str) -> Optional[DownloadItem]:
        for item in self._downloads_list:
            if item.id == item_id:
                return item
        return None

    def get_download_by_stream_id(self, stream_id: str) -> Optional[DownloadItem]:
        for item in self._downloads_list:
            if str(item.stream_id) == str(stream_id):
                return item
        return None

    def is_downloaded(self, stream_id: str) -> bool:
        item = self.get_download_by_stream_id(stream_id)
        if not item:
            return False
        return item.status == DownloadStatus.COMPLETED and os.path.exists(item.local_file_path)

    def is_downloading(self, stream_id: str) -> bool:
        item = self.get_download_by_stream_id(stream_id)
        if not item:
            return False
        return item.status in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED, DownloadStatus.PAUSED, DownloadStatus.ERROR)

    def enqueue_download(self, item: DownloadItem):
        """Ajoute un téléchargement à la file FIFO."""
        existing = self.get_download(item.id)
        if existing:
            if existing.status == DownloadStatus.COMPLETED and os.path.exists(existing.local_file_path):
                return
            idx = self._downloads_list.index(existing)
            self._downloads_list[idx] = item
        else:
            self._downloads_list.append(item)

        # Détermination du chemin local
        if not item.local_file_path:
            dir_path = self.get_download_directory()
            safe_title = sanitize_filename(item.title)
            if item.sub_title:
                safe_sub = sanitize_filename(item.sub_title)
                filename = f"{safe_title} - {safe_sub}_{item.stream_id}.{item.container_extension}"
            else:
                filename = f"{safe_title}_{item.stream_id}.{item.container_extension}"
            item.local_file_path = os.path.join(dir_path, filename)

        item.status = DownloadStatus.QUEUED
        item.error_message = None
        self._notify_status(item)
        self.process_queue()

    def process_queue(self):
        """Lance le prochain élément en attente si aucun téléchargement n'est actif."""
        is_any_downloading = any(
            item.status == DownloadStatus.DOWNLOADING and item.id in self._active_workers
            for item in self._downloads_list
        )
        if is_any_downloading:
            return

        # Trouver le prochain en attente (QUEUED) par date d'ajout
        queued_items = [item for item in self._downloads_list if item.status == DownloadStatus.QUEUED]
        if not queued_items:
            return

        queued_items.sort(key=lambda x: x.added_date)
        next_item = queued_items[0]
        self._start_worker(next_item)

    def _start_worker(self, item: DownloadItem):
        if item.id in self._active_workers:
            old_w = self._active_workers.pop(item.id)
            old_w.cancel()
            old_w.wait(500)

        worker = DownloadWorkerThread(item, speed_limit_bytes_per_sec=self.get_speed_limit(), parent=self)
        self._active_workers[item.id] = worker

        def on_prog(downloaded, total, speed_str):
            self._notify_progress(item)

        def on_finished(output_path):
            if item.id in self._active_workers:
                del self._active_workers[item.id]
            self._notify_status(item)
            self.process_queue()

        def on_err(err_msg):
            if item.id in self._active_workers:
                del self._active_workers[item.id]
            self._notify_status(item)
            self.process_queue()

        worker.progress.connect(on_prog)
        worker.download_finished.connect(on_finished)
        worker.download_error.connect(on_err)
        worker.start()

        item.status = DownloadStatus.DOWNLOADING
        item.error_message = None
        self._notify_status(item)

    def pause_download(self, item_id: str):
        item = self.get_download(item_id)
        if not item:
            return
        if item.id in self._active_workers:
            worker = self._active_workers.pop(item.id)
            worker.pause()
            worker.wait(500)

        item.status = DownloadStatus.PAUSED
        item.speed_bytes_per_sec = 0
        item.error_message = "En pause"
        self._notify_status(item)
        self.process_queue()

    def resume_download(self, item_id: str):
        item = self.get_download(item_id)
        if not item:
            return
        if item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
            item.status = DownloadStatus.QUEUED
            item.error_message = None
            self._notify_status(item)
            self.process_queue()

    def cancel_download(self, item_id: str):
        item = self.get_download(item_id)
        if not item:
            return
        if item.id in self._active_workers:
            worker = self._active_workers.pop(item.id)
            worker.cancel()
            worker.wait(500)

        part_file = f"{item.local_file_path}.part"
        if os.path.exists(part_file):
            try:
                os.unlink(part_file)
            except Exception:
                pass

        if os.path.exists(item.local_file_path):
            try:
                os.unlink(item.local_file_path)
            except Exception:
                pass

        if item in self._downloads_list:
            self._downloads_list.remove(item)

        self._notify_status(item)
        self.process_queue()

    def delete_download(self, item_id: str):
        self.cancel_download(item_id)

    def clear_all_completed(self):
        completed = self.get_completed_downloads()
        for item in completed:
            self.delete_download(item.id)

    def pause_all_for_playback(self):
        """Met en pause les téléchargements actifs lors de la lecture pour éviter lag / ban IPTV."""
        self._paused_for_playback_ids.clear()
        for item in sorted(self._downloads_list, key=lambda x: x.added_date):
            if item.status in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED):
                self._paused_for_playback_ids.append(item.id)
                if item.id in self._active_workers:
                    worker = self._active_workers.pop(item.id)
                    worker.pause()
                    worker.wait(500)
                item.status = DownloadStatus.PAUSED
                item.error_message = "En pause (Visionnage en cours)"
                item.speed_bytes_per_sec = 0
                self._notify_status(item)

    def resume_all_after_playback(self):
        """Reprend séquentiellement les téléchargements mis en pause par la lecture."""
        if not self._paused_for_playback_ids:
            return
        for item_id in self._paused_for_playback_ids:
            item = self.get_download(item_id)
            if item and item.status == DownloadStatus.PAUSED:
                item.status = DownloadStatus.QUEUED
                item.error_message = None
                self._notify_status(item)
        self._paused_for_playback_ids.clear()
        self.process_queue()

    def get_disk_stats(self) -> StorageStats:
        """Retourne les statistiques de stockage du disque (en Mo/Go)."""
        try:
            download_dir = self.get_download_directory()
            total, used, free = shutil.disk_usage(download_dir)
            used_by_hub = sum(
                os.path.getsize(it.local_file_path)
                for it in self.get_completed_downloads()
                if os.path.exists(it.local_file_path)
            )
            return StorageStats(total_bytes=total, available_bytes=free, downloads_occupied_bytes=used_by_hub)
        except Exception:
            return StorageStats(total_bytes=0, available_bytes=0, downloads_occupied_bytes=0)

    # Compatibilité avec le code existant qui appelait start_download(...)
    def start_download(
        self,
        url: str,
        dest_dir: str,
        base_name: str,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> DownloadWorkerThread:
        # Extraire l'extension
        ext = "mp4"
        clean_url = url.split("?")[0].lower()
        for cand in [".mp4", ".mkv", ".avi", ".ts", ".m4v", ".mov"]:
            if clean_url.endswith(cand):
                ext = cand[1:]
                break

        stream_id = str(abs(hash(url)))
        item = DownloadItem(
            id=f"vod_{stream_id}",
            stream_id=stream_id,
            title=base_name,
            stream_url=url,
            container_extension=ext,
            user_agent=user_agent,
            custom_headers=headers or {}
        )
        safe_title = sanitize_filename(base_name)
        item.local_file_path = os.path.join(dest_dir, f"{safe_title}.{ext}")
        self.enqueue_download(item)

        # Retourne le worker créé ou un proxy worker
        if item.id in self._active_workers:
            return self._active_workers[item.id]
        # Si mis en attente, créer un worker temporaire non démarré pour brancher les signaux
        dummy = DownloadWorkerThread(item)
        return dummy
