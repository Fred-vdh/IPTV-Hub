"""
Chargeur asynchrone d'images (logos de chaînes) haute performance avec file d'attente et cache.
"""

import hashlib
from collections import OrderedDict, deque
from pathlib import Path
from typing import Optional, Dict, Set
from PyQt6.QtCore import QObject, pyqtSignal, QUrl, Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from core.database import get_cache_dir


class ImageLoader(QObject):
    image_loaded = pyqtSignal(str, QPixmap)  # url, pixmap
    image_failed = pyqtSignal(str)           # url (échec de chargement pour fallback)

    _instance: Optional["ImageLoader"] = None

    @classmethod
    def instance(cls) -> "ImageLoader":
        if cls._instance is not None:
            try:
                _ = cls._instance.parent()
            except RuntimeError:
                cls._instance = None
        if cls._instance is None:
            cls._instance = ImageLoader()
        return cls._instance

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.nam = QNetworkAccessManager(self)
        self.nam.finished.connect(self._on_reply_finished)
        self.memory_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self.max_memory_cache_size = 200  # Limite mémoire stricte pour éviter toute saturation RAM
        self.pending_replies: Dict[QNetworkReply, str] = {}
        self.priority_queue: deque[str] = deque()
        self.queued_urls: deque[str] = deque()
        self.queued_set: Set[str] = set()
        self.active_downloads = 0
        self.max_concurrent = 8  # 8 téléchargements max en parallèle (évite la saturation réseau et du serveur)

        self.disk_cache_dir = get_cache_dir() / "logos"
        self.disk_cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def normalize_url(url: str) -> str:
        if not url:
            return ""
        u = str(url).strip()
        if u.startswith("//"):
            u = "https:" + u
        if " " in u:
            u = u.replace(" ", "%20")
        return u

    def _get_cache_path(self, url: str) -> Path:
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        return self.disk_cache_dir / f"{url_hash}.png"

    def _put_memory_cache(self, url: str, pix: QPixmap):
        """Ajoute une image au cache mémoire avec politique d'éviction LRU."""
        if not url or pix.isNull():
            return
        if url in self.memory_cache:
            self.memory_cache.move_to_end(url)
        self.memory_cache[url] = pix
        if len(self.memory_cache) > self.max_memory_cache_size:
            self.memory_cache.popitem(last=False)

    def get_cached_image(self, url: str) -> Optional[QPixmap]:
        """Retourne immédiatement l'image si elle est en cache mémoire ou disque."""
        url = self.normalize_url(url)
        if not url:
            return None

        # Cache mémoire (LRU)
        if url in self.memory_cache:
            self.memory_cache.move_to_end(url)
            return self.memory_cache[url]

        # Cache disque
        disk_path = self._get_cache_path(url)
        if disk_path.exists():
            pix = QPixmap(str(disk_path))
            if not pix.isNull():
                self._put_memory_cache(url, pix)
                return pix
        return None

    def request_image(self, url: str):
        """Met en file d'attente le téléchargement de l'affiche de manière non-bloquante."""
        url = self.normalize_url(url)
        if not url or not url.startswith("http"):
            return

        if url in self.memory_cache:
            self.memory_cache.move_to_end(url)
            self.image_loaded.emit(url, self.memory_cache[url])
            return

        # Vérification rapide sur disque avant de mettre en file d'attente
        disk_path = self._get_cache_path(url)
        if disk_path.exists():
            pix = QPixmap(str(disk_path))
            if not pix.isNull():
                self._put_memory_cache(url, pix)
                self.image_loaded.emit(url, pix)
                return

        if url in self.queued_set or url in self.pending_replies.values():
            return

        self.queued_set.add(url)
        self.queued_urls.append(url)
        self._process_queue()

    def request_image_priority(self, url: str):
        """Place l'URL en file prioritaire pour téléchargement immédiat avant les autres requêtes."""
        url = self.normalize_url(url)
        if not url or not url.startswith("http"):
            return

        if url in self.memory_cache:
            self.memory_cache.move_to_end(url)
            self.image_loaded.emit(url, self.memory_cache[url])
            return

        disk_path = self._get_cache_path(url)
        if disk_path.exists():
            pix = QPixmap(str(disk_path))
            if not pix.isNull():
                self._put_memory_cache(url, pix)
                self.image_loaded.emit(url, pix)
                return

        # Si l'URL était déjà en file normale, on la bascule en file prioritaire
        if url in self.queued_set:
            try:
                self.queued_urls.remove(url)
            except ValueError:
                pass
            if url not in self.priority_queue:
                self.priority_queue.append(url)
        elif url not in self.pending_replies.values():
            self.queued_set.add(url)
            self.priority_queue.append(url)

        self._process_queue()

    def clear_queue(self):
        """Vide la file d'attente des images non commencées pour privilégier la nouvelle catégorie."""
        self.priority_queue.clear()
        self.queued_urls.clear()
        self.queued_set.clear()

    def cancel_pending(self):
        """Annule immédiatement les téléchargements en cours et vide la file d'attente (ex: lancement vidéo)."""
        self.priority_queue.clear()
        self.queued_urls.clear()
        self.queued_set.clear()
        for reply in list(self.pending_replies.keys()):
            try:
                reply.abort()
                reply.deleteLater()
            except Exception:
                pass
        self.pending_replies.clear()
        self.active_downloads = 0

    def _process_queue(self):
        while self.active_downloads < self.max_concurrent and (self.priority_queue or self.queued_urls):
            if self.priority_queue:
                url = self.priority_queue.popleft()
            else:
                url = self.queued_urls.popleft()

            self.queued_set.discard(url)

            req = QNetworkRequest(QUrl(url))
            req.setRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.UserVerifiedRedirectPolicy)
            req.setTransferTimeout(7000)  # 7 secondes max par image pour éviter tout blocage réseau

            reply = self.nam.get(req)
            reply.sslErrors.connect(lambda errors, r=reply: r.ignoreSslErrors())
            self.pending_replies[reply] = url
            self.active_downloads += 1

    @staticmethod
    def _optimize_and_save_image(raw_bytes: bytes, disk_path: Path) -> Optional[QPixmap]:
        """
        Décode, redimensionne et compresse intelligemment l'image avant stockage sur disque :
        - Affiches portrait : max 600px de haut (JPEG 85%)
        - Bannières/Backdrops paysage : max 1920px de large (JPEG 85%)
        - Images avec transparence (logos) : max 320x320 (PNG)
        Retourne le QPixmap optimisé prêt pour l'affichage.
        """
        img = QImage()
        if not img.loadFromData(raw_bytes):
            return None

        w, h = img.width(), img.height()
        if w <= 0 or h <= 0:
            return None

        has_alpha = img.hasAlphaChannel()

        # 1. Calcul des dimensions cibles
        if has_alpha:
            max_w, max_h = 320, 320
        elif w > h:
            max_w, max_h = 1920, 1080
        else:
            max_w, max_h = 400, 600

        # Redimensionnement doux si l'image dépasse les dimensions cibles
        if w > max_w or h > max_h:
            img = img.scaled(
                max_w, max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

        # 2. Sauvegarde compressée sur disque
        try:
            if has_alpha:
                img.save(str(disk_path), "PNG")
            else:
                img.save(str(disk_path), "JPEG", 85)
        except Exception:
            try:
                disk_path.write_bytes(raw_bytes)
            except Exception:
                pass

        return QPixmap.fromImage(img)

    def _on_reply_finished(self, reply: QNetworkReply):
        url = self.pending_replies.pop(reply, None)
        self.active_downloads = max(0, self.active_downloads - 1)

        if url:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll()
                raw_bytes = bytes(data)
                disk_path = self._get_cache_path(url)
                pix = self._optimize_and_save_image(raw_bytes, disk_path)
                if pix and not pix.isNull():
                    self._put_memory_cache(url, pix)
                    self.image_loaded.emit(url, pix)
                else:
                    self.image_failed.emit(url)
            else:
                self.image_failed.emit(url)

        reply.deleteLater()
        self._process_queue()
