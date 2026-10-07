"""
Chargeur asynchrone d'images (logos de chaînes) haute performance avec file d'attente et cache.
"""

import hashlib
import weakref
from collections import OrderedDict, deque
from pathlib import Path
from typing import Optional, Dict, Set, List, Tuple, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QUrl, Qt
from PyQt6.QtGui import QPixmap, QImage, QPixmapCache
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
        self.max_memory_cache_size = 80  # Limite mémoire stricte (80 images LRU) pour éviter saturation RAM
        self.pending_replies: Dict[QNetworkReply, str] = {}
        self.priority_queue: deque[str] = deque()
        self.queued_urls: deque[str] = deque()
        self.queued_set: Set[str] = set()
        self.active_downloads = 0
        self.max_concurrent = 8  # 8 téléchargements max en parallèle (évite la saturation réseau et du serveur)

        # Abonnés ciblés par URL avec cycle de vie faible (évite toute fuite mémoire / slots fantômes)
        self._subscribers: Dict[str, List[Tuple[Optional[weakref.ref], Callable[[QPixmap], None]]]] = {}
        # Abonnés notifiés uniquement en cas d'échec (permet aux vues de tenter un repli)
        self._failed_subscribers: Dict[str, List[Tuple[Optional[weakref.ref], Callable[[str], None]]]] = {}
        self._target_urls: Dict[int, Set[str]] = {}

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
        while len(self.memory_cache) > self.max_memory_cache_size:
            self.memory_cache.popitem(last=False)

    def clear_memory_cache(self):
        """Vide le cache mémoire pour libérer la RAM immédiatement."""
        self.memory_cache.clear()
        try:
            QPixmapCache.clear()
        except Exception:
            pass

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

    def cancel_target(self, target: QObject):
        """Désabonne un widget de tous ses chargements d'images en attente."""
        target_id = id(target)
        self._on_target_destroyed(target_id)

    def _on_target_destroyed(self, target_id: int):
        """Nettoie instantanément les abonnements lorsqu'un widget cible est détruit."""
        urls = self._target_urls.pop(target_id, set())
        for u in urls:
            self._prune_subscribers(self._subscribers, u, target_id)
            self._prune_subscribers(self._failed_subscribers, u, target_id)

    def _prune_subscribers(self, store: Dict[str, List[Tuple[Optional[weakref.ref], Callable]]], url: str, target_id: int):
        """Retire d'un registre d'abonnés toutes les entrées appartenant à la cible donnée."""
        subs = store.get(url)
        if not subs:
            return
        remaining = [
            (ref, cb) for (ref, cb) in subs
            if ref is not None and ref() is not None and id(ref()) != target_id
        ]
        if remaining:
            store[url] = remaining
        else:
            store.pop(url, None)

    def _report_failure(self, url: str):
        """Signale qu'une image n'a pas pu être chargée : libère les abonnés et prévient les vues.

        Le signal `image_failed` est émis (compatibilité) et les callbacks d'échec enregistrés via
        `load_image(..., on_failed=...)` sont appelés pour permettre un repli immédiat.
        """
        self._subscribers.pop(url, None)
        subs = self._failed_subscribers.pop(url, [])
        for ref, cb in subs:
            if ref is None or ref() is not None:
                try:
                    cb(url)
                except Exception:
                    pass
        self.image_failed.emit(url)

    @staticmethod
    def alternate_host_urls(
        url: str,
        known_urls: Optional[List[str]] = None,
        limit: int = 2,
    ) -> List[str]:
        """URLs équivalentes servies par les autres domaines d'images connus du fournisseur.

        Plusieurs fournisseurs Xtream renvoient les visuels de certains épisodes sur un domaine
        hors service (HTTP 404) alors que le même fichier est bien servi, au même chemin, par le
        domaine qui héberge l'affiche de la série. On remplace donc l'autorité (hôte et port) de
        l'URL par celle des URLs connues, en conservant le chemin et les paramètres.
        """
        base = ImageLoader.normalize_url(url)
        scheme, sep, rest = str(base or "").partition("://")
        if not sep or not rest:
            return []
        authority, _, suffix = rest.partition("/")
        if not authority:
            return []
        suffix = "/" + suffix if suffix else ""

        variants: List[str] = []
        max_variants = max(1, int(limit))
        for known in (known_urls or []):
            k = ImageLoader.normalize_url(str(known or ""))
            k_scheme, k_sep, k_rest = k.partition("://")
            if not k_sep or not k_rest:
                continue
            k_authority = k_rest.partition("/")[0]
            if not k_authority or k_authority == authority:
                continue
            variant = f"{k_scheme}://{k_authority}{suffix}"
            if variant != base and variant not in variants:
                variants.append(variant)
            if len(variants) >= max_variants:
                break
        return variants

    def load_image(
        self,
        url: str,
        on_success: Optional[Callable[[QPixmap], None]] = None,
        target: Optional[QObject] = None,
        priority: bool = False,
        on_failed: Optional[Callable[[str], None]] = None
    ) -> Optional[QPixmap]:
        """
        Charge une image de manière asynchrone avec callback sans fuite mémoire.
        Détecte automatiquement le widget cible via callback.__self__ si target n'est pas fourni.
        `on_failed` (optionnel) est appelé si l'image ne peut pas être chargée : il permet à la vue
        de tenter un repli (autre domaine d'images, autre visuel) au lieu de rester sans image.
        """
        url = self.normalize_url(url)
        if not url:
            if on_failed:
                try:
                    on_failed("")
                except Exception:
                    pass
            return None

        cached = self.get_cached_image(url)
        if cached:
            if on_success:
                try:
                    on_success(cached)
                except Exception:
                    pass
            return cached

        # Enregistrement des abonnés ciblés (succès et/ou échec)
        if on_success or on_failed:
            if target is None:
                bound_obj = getattr(on_success or on_failed, "__self__", None)
                if isinstance(bound_obj, QObject):
                    target = bound_obj

            if target is not None:
                target_id = id(target)
                target_ref = weakref.ref(target)
                if target_id not in self._target_urls:
                    self._target_urls[target_id] = set()
                    try:
                        target.destroyed.connect(lambda _, tid=target_id: self._on_target_destroyed(tid))
                    except (RuntimeError, TypeError):
                        pass
                self._target_urls[target_id].add(url)
                if on_success:
                    self._subscribers.setdefault(url, []).append((target_ref, on_success))
                if on_failed:
                    self._failed_subscribers.setdefault(url, []).append((target_ref, on_failed))
            else:
                if on_success:
                    self._subscribers.setdefault(url, []).append((None, on_success))
                if on_failed:
                    self._failed_subscribers.setdefault(url, []).append((None, on_failed))

        if priority:
            self.request_image_priority(url)
        else:
            self.request_image(url)
        return None

    def request_image(self, url: str):
        """Met en file d'attente le téléchargement de l'affiche de manière non-bloquante."""
        url = self.normalize_url(url)
        if not url or not url.startswith("http"):
            return

        if url in self.memory_cache:
            self.memory_cache.move_to_end(url)
            self._notify_subscribers(url, self.memory_cache[url])
            self.image_loaded.emit(url, self.memory_cache[url])
            return

        # Vérification rapide sur disque avant de mettre en file d'attente
        disk_path = self._get_cache_path(url)
        if disk_path.exists():
            pix = QPixmap(str(disk_path))
            if not pix.isNull():
                self._put_memory_cache(url, pix)
                self._notify_subscribers(url, pix)
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

    def _notify_subscribers(self, url: str, pix: QPixmap):
        subs = self._subscribers.pop(url, [])
        for ref, cb in subs:
            if ref is None or ref() is not None:
                try:
                    cb(pix)
                except Exception:
                    pass

    @staticmethod
    def _optimize_and_save_image(raw_bytes: bytes, disk_path: Path) -> Optional[QPixmap]:
        """
        Décode, redimensionne et compresse intelligemment l'image avant stockage sur disque :
        - Affiches portrait : max 400x600 (JPEG 85%)
        - Bannières/Backdrops paysage : max 1280x720 (JPEG 85%, économique en RAM)
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
            max_w, max_h = 1280, 720
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
                    self._notify_subscribers(url, pix)
                    self.image_loaded.emit(url, pix)
                else:
                    self._report_failure(url)
            else:
                self._report_failure(url)

        reply.deleteLater()
        self._process_queue()
