"""
Gestionnaire et threads de téléchargement en arrière-plan pour les flux VOD d'IPTV Hub.
"""

import os
import re
import time
from typing import Optional, Dict
import requests
from PyQt6.QtCore import QObject, QThread, pyqtSignal


def sanitize_filename(name: str) -> str:
    """Supprime les caractères interdits pour un nom de fichier Windows."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean or "video"


def get_default_download_dir() -> str:
    """Retourne le dossier Téléchargements par défaut du système."""
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.exists(downloads):
        return downloads
    telechargements = os.path.join(os.path.expanduser("~"), "Téléchargements")
    if os.path.exists(telechargements):
        return telechargements
    return downloads


class DownloadTask(QThread):
    progress = pyqtSignal(int, int, str)  # (downloaded_bytes, total_bytes, speed_str)
    finished = pyqtSignal(str)  # output_path
    error = pyqtSignal(str)  # error_message

    def __init__(
        self,
        url: str,
        dest_dir: str,
        base_name: str,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.url = url
        self.dest_dir = dest_dir
        self.base_name = base_name
        self.user_agent = user_agent
        self.custom_headers = headers or {}
        self._is_cancelled = False
        self.output_path = ""
        self.is_downloading = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        self.is_downloading = True
        try:
            os.makedirs(self.dest_dir, exist_ok=True)

            # Détection de l'extension
            ext = ".mp4"
            clean_url = self.url.split("?")[0].lower()
            for candidate in [".mp4", ".mkv", ".avi", ".ts", ".m4v", ".mov"]:
                if clean_url.endswith(candidate):
                    ext = candidate
                    break

            clean_title = sanitize_filename(self.base_name)
            filename = f"{clean_title}{ext}"
            self.output_path = os.path.join(self.dest_dir, filename)

            # Éviter d'écraser si le fichier existe
            counter = 1
            while os.path.exists(self.output_path):
                self.output_path = os.path.join(self.dest_dir, f"{clean_title} ({counter}){ext}")
                counter += 1

            req_headers = {"User-Agent": self.user_agent or "Mozilla/5.0"}
            req_headers.update(self.custom_headers)

            with requests.get(self.url, headers=req_headers, stream=True, timeout=25) as r:
                r.raise_for_status()
                total_bytes = int(r.headers.get("content-length", 0))

                downloaded = 0
                start_time = time.time()
                last_time = start_time
                last_downloaded = 0

                with open(self.output_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=128 * 1024):
                        if self._is_cancelled:
                            f.close()
                            if os.path.exists(self.output_path):
                                os.unlink(self.output_path)
                            self.is_downloading = False
                            self.error.emit("Téléchargement annulé.")
                            return

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            now = time.time()
                            if now - last_time >= 0.5:
                                dt = now - last_time
                                speed_bps = (downloaded - last_downloaded) / dt if dt > 0 else 0
                                speed_mb = speed_bps / (1024 * 1024)
                                speed_str = f"{speed_mb:.1f} Mo/s"
                                self.progress.emit(downloaded, total_bytes, speed_str)
                                last_time = now
                                last_downloaded = downloaded

                if self._is_cancelled:
                    if os.path.exists(self.output_path):
                        os.unlink(self.output_path)
                    self.is_downloading = False
                    return

                self.is_downloading = False
                self.progress.emit(downloaded, total_bytes, "Terminé")
                self.finished.emit(self.output_path)

        except Exception as e:
            self.is_downloading = False
            if os.path.exists(self.output_path):
                try:
                    os.unlink(self.output_path)
                except Exception:
                    pass
            self.error.emit(str(e))


class DownloadManager(QObject):
    _instance: Optional["DownloadManager"] = None

    @classmethod
    def instance(cls) -> "DownloadManager":
        if cls._instance is None:
            cls._instance = DownloadManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.active_tasks: Dict[str, DownloadTask] = {}

    def start_download(
        self,
        url: str,
        dest_dir: str,
        base_name: str,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> DownloadTask:
        task = DownloadTask(
            url=url,
            dest_dir=dest_dir,
            base_name=base_name,
            user_agent=user_agent,
            headers=headers
        )
        task_id = f"{url}_{time.time()}"
        self.active_tasks[task_id] = task

        def cleanup():
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

        task.finished.connect(lambda _: cleanup())
        task.error.connect(lambda _: cleanup())
        task.start()
        return task
