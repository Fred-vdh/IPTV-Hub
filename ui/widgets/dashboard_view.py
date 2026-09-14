"""
Vue du Tableau de Bord (Dashboard) ultra-moderne et élégante, fidèle aux captures d'écran.
Comprend :
1. Bannière Hero grand style "En cours de lecture" avec bouton direct "▶ Reprendre la lecture".
2. Carrousel horizontal "Reprendre la lecture" (VOD & Séries entamées avec jauge).
3. Carrousel horizontal "Favorite movies & series" (Films et séries favoris avec note).
4. Carrousel horizontal "Récemment ajoutés" sur la playlist active.

Les affiches sont affichées à 100% sans coupure ni scroll vertical interne.
Le défilement molette sur les carrousels transmet naturellement le scroll vertical à la page.
"""

import re
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QRectF, QThread, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPixmap, QMouseEvent, QPen, QWheelEvent,
    QLinearGradient, QRadialGradient, QPainterPath
)

from core.database import Database
from core.models import Channel, Playlist, parse_movie_metadata
from core.image_loader import ImageLoader
from ui.icons import get_icon
from ui.widgets.poster_utils import draw_added_date_badge
from core.i18n import tr


class BackdropFetchThread(QThread):
    """Thread léger d'arrière-plan pour récupérer le backdrop 16:9 d'un média Xtream."""
    backdrop_ready = pyqtSignal(str)

    def __init__(self, server_url: str, username: str, password: str, stream_id: str, stream_type: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.server_url = server_url
        self.username = username
        self.password = password
        self.stream_id = stream_id
        self.stream_type = stream_type

    def run(self):
        try:
            from core.xtream_client import XtreamClient
            client = XtreamClient(self.server_url, self.username, self.password)
            backdrop_url = ""
            if self.stream_type == "series":
                info = client.get_series_info(self.stream_id)
                bd = info.get("info", {}).get("backdrop_path")
                if isinstance(bd, list) and bd:
                    backdrop_url = bd[0]
                elif isinstance(bd, str):
                    backdrop_url = bd
            else:
                info = client.get_vod_info(self.stream_id)
                bd = info.get("info", {}).get("backdrop_path")
                if isinstance(bd, list) and bd:
                    backdrop_url = bd[0]
                elif isinstance(bd, str):
                    backdrop_url = bd

            if backdrop_url and isinstance(backdrop_url, str) and backdrop_url.strip():
                self.backdrop_ready.emit(backdrop_url.strip())
        except Exception:
            pass


# =========================================================================
# 1. AFFICHE AVEC BADGE PINNÉ POUR LA BANNIÈRE HERO
# =========================================================================

class HeroPosterWidget(QWidget):
    """Affiche grand format stylée avec coins arrondis et badge qualité pinné en haut au centre."""
    clicked = pyqtSignal()

    WIDTH = 140
    HEIGHT = 210

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pixmap: Optional[QPixmap] = None
        self.quality_tag: str = ""
        self.image_url: str = ""
        self.added_at: Optional[str] = None
        self.stream_type: str = ""

    def set_data(self, image_url: str, quality_tag: str, added_at: Optional[str] = None, stream_type: str = ""):
        self.image_url = image_url
        self.quality_tag = quality_tag
        self.added_at = added_at
        self.stream_type = stream_type
        self.pixmap = None
        self.update()

        if image_url:
            loader = ImageLoader.instance()
            cached = loader.get_cached_image(image_url)
            if cached:
                self.pixmap = cached
                self.update()
            else:
                loader.image_loaded.connect(self._on_image_loaded)
                loader.request_image_priority(image_url)

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        if url == self.image_url:
            self.pixmap = pixmap
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = self.rect()

        # 1. Découpe arrondie avec antialiasing parfait (QPainterPath)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 10.0, 10.0)
        painter.setClipPath(path)

        # Fond sombre
        painter.fillRect(rect, QColor("#0e1422"))

        # 2. Rendu de l'affiche
        if self.pixmap and not self.pixmap.isNull():
            is_wide_logo = (self.quality_tag == "REPLAY") or (self.pixmap.width() > self.pixmap.height() * 1.1)
            if is_wide_logo:
                scaled = self.pixmap.scaled(
                    self.WIDTH - 16, self.HEIGHT - 40,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                draw_x = (self.WIDTH - scaled.width()) // 2
                draw_y = (self.HEIGHT - scaled.height()) // 2
                painter.drawPixmap(draw_x, draw_y, scaled)
            else:
                scaled = self.pixmap.scaled(
                    self.WIDTH, self.HEIGHT,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                crop_x = (scaled.width() - self.WIDTH) // 2
                crop_y = (scaled.height() - self.HEIGHT) // 2
                painter.drawPixmap(0, 0, scaled, crop_x, crop_y, self.WIDTH, self.HEIGHT)
        else:
            painter.setPen(QColor("#334155"))
            font = QFont("Segoe UI", 9)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Affiche")

        # 3. Désactivation du clip pour la bordure nette sans coupure
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), 10.0, 10.0)

        # 4. Badge qualité pinné en haut au centre (style Netflix / Apple TV)
        if self.quality_tag:
            painter.save()
            font = QFont("Segoe UI", 7, QFont.Weight.ExtraBold)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(self.quality_tag)
            bw = text_w + 14
            bh = 17
            bx = (self.WIDTH - bw) // 2
            by = 6

            if self.quality_tag == "REPLAY":
                painter.setBrush(QColor("#312e81"))
                painter.setPen(QPen(QColor("#6366f1"), 1))
                painter.drawRoundedRect(QRect(bx, by, bw, bh), 4, 4)
                painter.setPen(QColor("#e0e7ff"))
                painter.drawText(QRect(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, self.quality_tag)
            else:
                # Fond pilule blanc cassé crème
                painter.setBrush(QColor(255, 255, 255, 245))
                painter.setPen(QPen(QColor(0, 0, 0, 30), 1))
                painter.drawRoundedRect(QRect(bx, by, bw, bh), 4, 4)
                painter.setPen(QColor("#0f172a"))
                painter.drawText(QRect(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, self.quality_tag)
            painter.restore()

        # 5. Badge date d'ajout (Films et Séries)
        if self.added_at and self.stream_type in ("movie", "series"):
            draw_added_date_badge(painter, self.added_at, self.WIDTH, self.HEIGHT, bottom_offset=6)


# =========================================================================
# 2. BANNIÈRE HERO DU DERNIER MÉDIA EN COURS
# =========================================================================

class HeroBannerWidget(QFrame):
    resume_clicked = pyqtSignal(Channel, float)  # channel, position

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item_data: Optional[Dict[str, Any]] = None
        self.channel: Optional[Channel] = None
        self.position: float = 0.0
        self.duration: float = 0.0
        self.backdrop_pixmap: Optional[QPixmap] = None
        self.backdrop_url: str = ""
        self._backdrop_thread: Optional[BackdropFetchThread] = None

        self.setFixedHeight(240)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 24, 18)
        layout.setSpacing(0)

        # 1. Affiche stylée à gauche
        self.poster_widget = HeroPosterWidget(self)
        self.poster_widget.clicked.connect(self._on_resume)
        layout.addWidget(self.poster_widget)

        layout.addSpacing(22)

        # 2. Zone d'informations à droite (justifiée à gauche)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 2, 0, 2)
        info_layout.setSpacing(0)

        # Titre en grand (blanc éclatant)
        self.title_label = QLabel("Aucun média en cours")
        self.title_label.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 700; margin: 0; background: transparent;")
        self.title_label.setWordWrap(False)
        info_layout.addWidget(self.title_label)

        info_layout.addSpacing(5)

        # Métadonnées (Playlist · Source · Type)
        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 500; background: transparent;")
        info_layout.addWidget(self.meta_label)

        info_layout.addSpacing(14)

        # Barre de progression fine (260 px)
        self.progress_bar_bg = QFrame()
        self.progress_bar_bg.setFixedHeight(4)
        self.progress_bar_bg.setFixedWidth(260)
        self.progress_bar_bg.setStyleSheet("background-color: #1e293b; border-radius: 2px;")
        self.progress_bar_fill = QFrame(self.progress_bar_bg)
        self.progress_bar_fill.setFixedHeight(4)
        self.progress_bar_fill.setStyleSheet("background-color: #38bdf8; border-radius: 2px;")
        info_layout.addWidget(self.progress_bar_bg)

        info_layout.addSpacing(6)

        # Statut temps restant & pourcentage
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500; background: transparent;")
        info_layout.addWidget(self.status_label)

        info_layout.addSpacing(14)

        # Bouton pilule "▶  Reprendre la lecture" (bleu ciel vif, texte noir marine)
        self.btn_resume = QPushButton("  Reprendre la lecture")
        self.btn_resume.setIcon(get_icon("play_arrow", color="#0a1628"))
        self.btn_resume.setIconSize(QSize(16, 16))
        self.btn_resume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_resume.setFixedHeight(36)
        self.btn_resume.setMinimumWidth(185)
        self.btn_resume.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_resume.setStyleSheet("""
            QPushButton {
                background-color: #38bdf8;
                color: #0a1628;
                font-size: 12px;
                font-weight: 700;
                border: none;
                border-radius: 18px;
                padding: 0px 16px;
            }
            QPushButton:hover {
                background-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #2563eb;
                color: #ffffff;
            }
        """)
        self.btn_resume.clicked.connect(self._on_resume)
        info_layout.addWidget(self.btn_resume)

        info_layout.addStretch(1)

        # Ancrage justifié à gauche près de l'affiche
        layout.addLayout(info_layout, stretch=0)
        layout.addStretch(1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 16.0, 16.0)
        painter.setClipPath(path)

        # 1. Fond sombre de base
        painter.fillRect(rect, QColor("#090d16"))

        # 2. Dessin du backdrop cinématique s'il est chargé
        if self.backdrop_pixmap and not self.backdrop_pixmap.isNull():
            bw = int(rect.width() * 0.75)
            scaled = self.backdrop_pixmap.scaled(
                bw, rect.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            draw_x = rect.width() - scaled.width()
            draw_y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(draw_x, draw_y, scaled)

            # Dégradé horizontal profond : 100% opaque à gauche pour lisibilité, dégradé vers transparent à droite
            fade_grad = QLinearGradient(0, 0, rect.width(), 0)
            fade_grad.setColorAt(0.0, QColor("#090d16"))
            fade_grad.setColorAt(0.38, QColor("#090d16"))
            fade_grad.setColorAt(0.56, QColor(9, 13, 22, 235))
            fade_grad.setColorAt(0.78, QColor(9, 13, 22, 130))
            fade_grad.setColorAt(1.0, QColor(9, 13, 22, 35))
            painter.fillRect(rect, fade_grad)

            # Vignette verticale haut/bas
            v_grad = QLinearGradient(0, 0, 0, rect.height())
            v_grad.setColorAt(0.0, QColor(9, 13, 22, 90))
            v_grad.setColorAt(0.5, QColor(0, 0, 0, 0))
            v_grad.setColorAt(1.0, QColor(9, 13, 22, 190))
            painter.fillRect(rect, v_grad)
        else:
            # Dégradé élégant riche de secours
            bg_grad = QLinearGradient(0, 0, rect.width(), rect.height() * 0.75)
            bg_grad.setColorAt(0.0, QColor("#141b2c"))
            bg_grad.setColorAt(0.28, QColor("#101625"))
            bg_grad.setColorAt(0.65, QColor("#0c101c"))
            bg_grad.setColorAt(1.0, QColor("#080b14"))
            painter.fillRect(rect, bg_grad)

            glow_grad = QRadialGradient(rect.width() * 0.2, 0, rect.width() * 0.45)
            glow_grad.setColorAt(0.0, QColor(78, 142, 247, 22))
            glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(rect, glow_grad)

        # 3. Contour & liseré lumineux
        painter.setClipping(False)
        border_grad = QLinearGradient(0, 0, rect.width(), rect.height())
        border_grad.setColorAt(0.0, QColor(80, 130, 220, 85))
        border_grad.setColorAt(0.35, QColor(45, 60, 90, 70))
        border_grad.setColorAt(0.7, QColor(30, 41, 59, 80))
        border_grad.setColorAt(1.0, QColor(20, 28, 44, 60))

        painter.setPen(QPen(border_grad, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 16, 16)

    def set_data(self, item: Optional[Dict[str, Any]]):
        self.item_data = item
        if not item:
            self.setVisible(False)
            return

        self.setVisible(True)
        ch: Channel = item["channel"]
        self.channel = ch
        self.position = float(item.get("position", 0.0))
        self.duration = float(item.get("duration", 1.0))

        # Titre
        display_title = item.get("series_name") or ch.name
        self.title_label.setText(display_title)

        # Métadonnées
        meta = parse_movie_metadata(ch.name, ch.rating, ch.year)
        q_tag = meta.get("quality_tag", "")

        is_replay = ch.stream_type == "replay" or "/timeshift/" in (ch.stream_url or "").lower()
        if ch.stream_type == "series":
            media_type = "Série"
        elif is_replay:
            media_type = "Replay"
            if not q_tag:
                q_tag = "REPLAY"
        else:
            media_type = "Film"

        pl_name = item.get("playlist_name", "Playlist")
        pl_type = item.get("playlist_type", "Xtream")
        self.meta_label.setText(f"{pl_name} · {pl_type} · {media_type}")

        # Temps & pourcentage
        rem_str = item.get("remaining_str", "")
        pct = item.get("percentage", 0)
        ep_text = item.get("episode_text", "")
        is_completed = item.get("is_completed", False)

        if ch.stream_type == "series":
            if is_completed:
                if ep_text:
                    self.status_label.setText(f"{ep_text}  ·  Épisode suivant disponible")
                    self.btn_resume.setText("  Lancer l'épisode suivant")
                else:
                    self.status_label.setText("Série à reprendre")
                    self.btn_resume.setText("  Voir la série")
            else:
                self.status_label.setText(f"{ep_text}  ·  {rem_str}  ({pct}% regardé)")
                self.btn_resume.setText("  Reprendre l'épisode")
        elif is_replay:
            self.status_label.setText(f"{rem_str}  ·  {pct}% regardé")
            self.btn_resume.setText("  Reprendre le Replay")
        else:
            self.status_label.setText(f"{rem_str}  ·  {pct}% regardé")
            self.btn_resume.setText("  Reprendre la lecture")

        # Mise à jour barre de progression
        if is_completed:
            self.progress_bar_fill.setFixedWidth(0)
        else:
            pct_ratio = max(0.01, min(1.0, self.position / max(1.0, self.duration)))
            self.progress_bar_fill.setFixedWidth(int(260 * pct_ratio))

        # Affiche avec badge
        self.poster_widget.set_data(ch.logo_url, q_tag, added_at=ch.added_at, stream_type=ch.stream_type)

        # Chargement du backdrop cinématique
        self._load_backdrop(ch)

    def _load_backdrop(self, ch: Channel):
        # 1. Utiliser le poster déjà en cache comme première ambiance
        if ch.logo_url:
            cached_logo = ImageLoader.instance().get_cached_image(ch.logo_url)
            if cached_logo and not self.backdrop_pixmap:
                self.backdrop_pixmap = cached_logo
                self.update()

        # 2. Chercher le vrai backdrop HD 16:9 si playlist Xtream
        if ch.playlist_id and ch.stream_id:
            try:
                db = Database()
                pl = db.get_playlist(ch.playlist_id)
                if pl and pl.server_url and pl.username and pl.password:
                    if self._backdrop_thread and self._backdrop_thread.isRunning():
                        self._backdrop_thread.terminate()
                    self._backdrop_thread = BackdropFetchThread(
                        pl.server_url, pl.username, pl.password,
                        str(ch.stream_id), ch.stream_type, self
                    )
                    self._backdrop_thread.backdrop_ready.connect(self._on_backdrop_url_resolved)
                    self._backdrop_thread.start()
            except Exception:
                pass

    def _on_backdrop_url_resolved(self, url: str):
        if not url:
            return
        self.backdrop_url = url
        loader = ImageLoader.instance()
        cached = loader.get_cached_image(url)
        if cached:
            self.backdrop_pixmap = cached
            self.update()
        else:
            loader.image_loaded.connect(self._on_image_loaded)
            loader.request_image_priority(url)

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        if url == self.backdrop_url and not pixmap.isNull():
            self.backdrop_pixmap = pixmap
            self.update()
        elif url == (self.channel.logo_url if self.channel else "") and not self.backdrop_pixmap and not pixmap.isNull():
            self.backdrop_pixmap = pixmap
            self.update()

    def _on_resume(self):
        if self.channel:
            self.resume_clicked.emit(self.channel, self.position)


# =========================================================================
# 3. MINI-CARTE POUR CHAÎNE TV EN DIRECT ("RECENTLY WATCHED LIVE TV")
# =========================================================================

class LiveTvMiniCard(QFrame):
    """Mini-carte horizontale 220x56 px pour une chaîne TV en direct récemment regardée."""
    clicked = pyqtSignal(Channel)

    CARD_WIDTH = 220
    CARD_HEIGHT = 56

    def __init__(self, item: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self.channel: Channel = item["channel"]
        self.pixmap: Optional[QPixmap] = None

        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()
        self._load_logo()

    def _init_ui(self):
        self.setObjectName("LiveTvMiniCard")
        self.setStyleSheet("""
            QFrame#LiveTvMiniCard {
                background-color: #111726;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QFrame#LiveTvMiniCard:hover {
                background-color: #162035;
                border: 1px solid #3b82f6;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 7, 10, 7)
        layout.setSpacing(10)

        # 1. Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(40, 40)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("background-color: #0b101d; border-radius: 6px; border: 1px solid #1e293b;")
        layout.addWidget(self.logo_label)

        # 2. Textes (Nom & Groupe)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        self.name_label = QLabel(self.channel.name)
        self.name_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        self.name_label.setWordWrap(False)
        info_layout.addWidget(self.name_label)

        grp = self.channel.group_title or self.item.get("playlist_name") or "Direct"
        self.group_label = QLabel(grp)
        self.group_label.setStyleSheet("color: #8c9bb3; font-size: 10px; font-weight: 500; background: transparent; border: none;")
        self.group_label.setWordWrap(False)
        info_layout.addWidget(self.group_label)

        layout.addLayout(info_layout, stretch=1)

        # 3. Badge LIVE
        badge_live = QLabel("• LIVE")
        badge_live.setFixedSize(48, 20)
        badge_live.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_live.setStyleSheet("""
            background-color: #2e1014;
            color: #f87171;
            font-size: 9px;
            font-weight: 800;
            border-radius: 4px;
            border: 1px solid #ef444450;
        """)
        layout.addWidget(badge_live)

    def _load_logo(self):
        if not self.channel.logo_url:
            self._set_fallback_icon()
            return
        loader = ImageLoader.instance()
        cached = loader.get_cached_image(self.channel.logo_url)
        if cached:
            self._set_pixmap(cached)
        else:
            loader.image_loaded.connect(self._on_image_loaded)
            loader.request_image(self.channel.logo_url)
            self._set_fallback_icon()

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        if url == self.channel.logo_url and not pixmap.isNull():
            self._set_pixmap(pixmap)

    def _set_pixmap(self, pixmap: QPixmap):
        scaled = pixmap.scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.logo_label.setPixmap(scaled)

    def _set_fallback_icon(self):
        self.logo_label.setPixmap(get_icon("live_tv", color="#64748b").pixmap(20, 20))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.channel)
        super().mousePressEvent(event)


# =========================================================================
# 4. CARTE POSTER DE CARROUSEL (NON TRONQUÉE)
# =========================================================================

class DashboardPosterCard(QWidget):
    """Carte poster verticale 140x258 px entièrement visible sans coupure."""
    clicked = pyqtSignal(Channel)

    CARD_WIDTH = 140
    POSTER_HEIGHT = 210
    TOTAL_HEIGHT = 258

    def __init__(self, channel: Channel, progress_info: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.progress_info = progress_info
        self.meta = parse_movie_metadata(channel.name, channel.rating, channel.year)
        self.pixmap: Optional[QPixmap] = None
        self.is_hovered = False

        self.setFixedSize(self.CARD_WIDTH, self.TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_image()

    def _load_image(self):
        if not self.channel.logo_url:
            return
        loader = ImageLoader.instance()
        cached = loader.get_cached_image(self.channel.logo_url)
        if cached:
            self.pixmap = cached
            self.update()
        else:
            loader.image_loaded.connect(self._on_image_loaded)
            loader.request_image(self.channel.logo_url)

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        if url == self.channel.logo_url:
            self.pixmap = pixmap
            self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.channel)
        super().mousePressEvent(event)

    def _get_badge_palette(self, tag: str):
        tag_u = tag.upper()
        if "REPLAY" in tag_u:
            return QColor("#312e81"), QColor("#e0e7ff"), QColor("#6366f1")
        elif "4K" in tag_u or "UHD" in tag_u or "DOLBY" in tag_u:
            return QColor("#090d16"), QColor("#f8fafc"), QColor("#334155")
        elif "VFQ" in tag_u or tag_u == "MULTI":
            return QColor("#fef3c7"), QColor("#78350f"), QColor("#fde68a")
        elif "VFF" in tag_u:
            return QColor("#fce7f3"), QColor("#9d174d"), QColor("#fbcfe8")
        else:
            return QColor(255, 255, 255, 245), QColor("#0f172a"), QColor("#cbd5e1")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 1. Rendu de l'affiche (Poster) avec découpe arrondie parfaite (QPainterPath)
        p_rect = QRectF(0.0, 0.0, float(self.CARD_WIDTH), float(self.POSTER_HEIGHT))
        path = QPainterPath()
        path.addRoundedRect(p_rect, 10.0, 10.0)

        painter.save()
        painter.setClipPath(path)
        painter.fillRect(p_rect.toRect(), QColor("#131b2e"))

        is_replay = self.channel.stream_type == "replay" or "/timeshift/" in (self.channel.stream_url or "").lower()

        if self.pixmap and not self.pixmap.isNull():
            is_wide_logo = is_replay or (self.pixmap.width() > self.pixmap.height() * 1.1 and self.channel.stream_type != "series")
            if is_wide_logo:
                scaled = self.pixmap.scaled(
                    self.CARD_WIDTH - 20, self.POSTER_HEIGHT - 40,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                draw_x = (self.CARD_WIDTH - scaled.width()) // 2
                draw_y = (self.POSTER_HEIGHT - scaled.height()) // 2
                painter.drawPixmap(draw_x, draw_y, scaled)
            else:
                scaled = self.pixmap.scaled(
                    self.CARD_WIDTH, self.POSTER_HEIGHT,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                crop_x = (scaled.width() - self.CARD_WIDTH) // 2
                crop_y = (scaled.height() - self.POSTER_HEIGHT) // 2
                painter.drawPixmap(0, 0, scaled, crop_x, crop_y, self.CARD_WIDTH, self.POSTER_HEIGHT)
        else:
            painter.setPen(QColor("#334155"))
            font = QFont("Segoe UI", 9)
            painter.setFont(font)
            painter.drawText(p_rect.toRect(), Qt.AlignmentFlag.AlignCenter, "Affiche")

        # 2. Barre de progression fine au bas du poster (également masquée par l'arrondi)
        if self.progress_info:
            pct = self.progress_info.get("percentage", 0)
            is_completed = self.progress_info.get("is_completed", False)
            if pct > 0 and not is_completed:
                bar_h = 4
                bar_y = self.POSTER_HEIGHT - bar_h
                painter.fillRect(QRect(0, bar_y, self.CARD_WIDTH, bar_h), QColor("#0f172a"))
                fill_w = max(4, int(self.CARD_WIDTH * (pct / 100.0)))
                painter.fillRect(QRect(0, bar_y, fill_w, bar_h), QColor("#38bdf8"))

        painter.restore()

        # 3. Bordure et survol
        painter.save()
        border_color = QColor("#3b82f6") if self.is_hovered else QColor(255, 255, 255, 30)
        border_w = 2 if self.is_hovered else 1
        painter.setPen(QPen(border_color, border_w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(p_rect.adjusted(0.5, 0.5, -0.5, -0.5), 10.0, 10.0)
        painter.restore()

        # 4. Badge qualité en haut (MULTI VFF, 4K, VFQ, REPLAY, etc.)
        q_tag = "REPLAY" if is_replay else self.meta.get("quality_tag", "")
        if q_tag:
            painter.save()
            font = QFont("Segoe UI", 7, QFont.Weight.Bold)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            bw = metrics.horizontalAdvance(q_tag) + 12
            bh = 16
            bx = (self.CARD_WIDTH - bw) // 2
            by = 6

            bg_col, txt_col, brd_col = self._get_badge_palette(q_tag)
            painter.setBrush(bg_col)
            painter.setPen(QPen(brd_col, 1))
            painter.drawRoundedRect(QRect(bx, by, bw, bh), 3, 3)
            painter.setPen(txt_col)
            painter.drawText(QRect(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, q_tag)
            painter.restore()

        # 4.bis Badge date d'ajout (Films et Séries)
        if self.channel and self.channel.stream_type in ("movie", "series"):
            has_prog = bool(self.progress_info and self.progress_info.get("percentage", 0) > 0 and not self.progress_info.get("is_completed", False))
            bottom_off = 10 if has_prog else 6
            draw_added_date_badge(painter, self.channel.added_at, self.CARD_WIDTH, self.POSTER_HEIGHT, bottom_offset=bottom_off)

        # 5. Titre du film / série / replay sous l'affiche
        painter.save()
        t_rect = QRect(0, self.POSTER_HEIGHT + 6, self.CARD_WIDTH, 18)
        font = QFont("Segoe UI", 8, QFont.Weight.DemiBold if not self.is_hovered else QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff" if self.is_hovered else "#cbd5e1"))

        # Nettoyage du titre si c'est une série
        display_title = self.channel.name
        if self.progress_info and self.progress_info.get("series_name"):
            display_title = self.progress_info["series_name"]
        elif self.channel.stream_type == "series":
            split_title = re.split(r"[\s\u2013\u2014\-]+S\d{1,2}E\d{1,2}", display_title, flags=re.IGNORECASE)
            if split_title:
                display_title = split_title[0].strip()

        elided = painter.fontMetrics().elidedText(display_title, Qt.TextElideMode.ElideRight, self.CARD_WIDTH)
        painter.drawText(t_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        # 6. Sous-titre avec badge épisode (séries) ou badge Replay
        sub_rect = QRect(0, self.POSTER_HEIGHT + 26, self.CARD_WIDTH, 16)
        sub_font = QFont("Segoe UI", 7)
        painter.setFont(sub_font)

        pl_type = (self.progress_info.get("playlist_type") if self.progress_info else "Xtream") or "Xtream"

        if self.channel.stream_type == "series":
            ep_text = self.progress_info.get("episode_text", "") if self.progress_info else ""
            if not ep_text:
                m_ep = re.search(r"\bS(\d{1,2})[\s\.:-]*E(\d{1,2})\b", self.channel.name, re.IGNORECASE)
                if m_ep:
                    ep_text = f"S{int(m_ep.group(1))}:E{int(m_ep.group(2))}"

            if ep_text:
                ep_w = painter.fontMetrics().horizontalAdvance(ep_text) + 8
                # Pilule bleue de l'épisode
                painter.setBrush(QColor("#1e3a8a"))
                painter.setPen(QPen(QColor("#3b82f6"), 1))
                painter.drawRoundedRect(QRect(0, self.POSTER_HEIGHT + 27, ep_w, 14), 3, 3)
                painter.setPen(QColor("#bfdbfe"))
                painter.drawText(QRect(0, self.POSTER_HEIGHT + 27, ep_w, 14), Qt.AlignmentFlag.AlignCenter, ep_text)

                # Texte après la pilule
                painter.setPen(QColor("#64748b"))
                painter.drawText(
                    QRect(ep_w + 5, self.POSTER_HEIGHT + 26, self.CARD_WIDTH - ep_w - 5, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"· {pl_type} · Série"
                )
            else:
                painter.setPen(QColor("#64748b"))
                painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{pl_type} · Série")
        elif is_replay:
            badge_text = "REPLAY"
            bw = painter.fontMetrics().horizontalAdvance(badge_text) + 10
            painter.setBrush(QColor("#312e81"))
            painter.setPen(QPen(QColor("#818cf8"), 1))
            painter.drawRoundedRect(QRect(0, self.POSTER_HEIGHT + 27, bw, 14), 3, 3)
            painter.setPen(QColor("#c7d2fe"))
            painter.drawText(QRect(0, self.POSTER_HEIGHT + 27, bw, 14), Qt.AlignmentFlag.AlignCenter, badge_text)

            painter.setPen(QColor("#64748b"))
            painter.drawText(
                QRect(bw + 6, self.POSTER_HEIGHT + 26, self.CARD_WIDTH - bw - 6, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"· {pl_type} · TV"
            )
        else:
            painter.setPen(QColor("#64748b"))
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{pl_type} · Film")

        painter.restore()


# =========================================================================
# 4. SCROLLAREA HORIZONTALE FLUIDE SANS CAPTURE DE LA MOLETTE VERTICALE
# =========================================================================

class HorizontalCarouselScrollArea(QScrollArea):
    """
    ScrollArea horizontale qui transmet les défilements verticaux de la molette
    à la page parente, garantissant un défilement vertical continu et sans blocage.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 4px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #1e293b;
                min-width: 24px;
                border-radius: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #334155;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    def wheelEvent(self, event: QWheelEvent):
        # Si défilement vertical classique (sans Shift) : transmettre au parent vertical
        if event.angleDelta().y() != 0 and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            parent = self.parent()
            while parent and not isinstance(parent, QScrollArea):
                parent = parent.parent()
            if parent:
                parent.wheelEvent(event)
            else:
                event.ignore()
        else:
            super().wheelEvent(event)


# =========================================================================
# 5. CONTENEUR DE CARROUSEL HORIZONTAL AVEC EN-TÊTE
# =========================================================================

class DashboardSection(QWidget):
    see_all_clicked = pyqtSignal(str)  # section_key

    def __init__(self, title: str, section_key: str, see_all_text: str = "Voir tout >", content_height: int = 262, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.section_key = section_key
        self.content_height = content_height
        self.setFixedHeight(content_height + 46)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # En-tête
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #f8fafc; font-size: 16px; font-weight: 700;")
        header_row.addWidget(self.title_label)

        self.badge_label = QLabel("0")
        self.badge_label.setStyleSheet("""
            background-color: #1e293b;
            color: #818cf8;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 9px;
            border: 1px solid #334155;
        """)
        header_row.addWidget(self.badge_label)

        header_row.addStretch()

        self.see_all_btn = QPushButton(see_all_text)
        self.see_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.see_all_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                font-size: 12px;
                font-weight: 500;
                border: none;
            }
            QPushButton:hover {
                color: #f8fafc;
            }
        """)
        self.see_all_btn.clicked.connect(lambda: self.see_all_clicked.emit(self.section_key))
        header_row.addWidget(self.see_all_btn)

        layout.addLayout(header_row)

        # Scroll Area horizontale
        self.scroll_area = HorizontalCarouselScrollArea(self)
        self.scroll_area.setFixedHeight(content_height + 14)

        self.items_container = QWidget()
        self.items_container.setStyleSheet("background: transparent;")
        self.items_container.setFixedHeight(content_height)

        self.items_layout = QHBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(14)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.items_container)
        layout.addWidget(self.scroll_area)

        # Flèches de défilement gauche et droite pour naviguer dans le carrousel
        btn_style = """
            QPushButton {
                background-color: rgba(15, 23, 42, 0.90);
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
                border: 1px solid #475569;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
            QPushButton:pressed {
                background-color: #2563eb;
            }
        """

        self.btn_scroll_right = QPushButton("›", self.scroll_area)
        self.btn_scroll_right.setFixedSize(32, 32)
        self.btn_scroll_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scroll_right.setStyleSheet(btn_style)
        self.btn_scroll_right.clicked.connect(self._scroll_right)
        self.btn_scroll_right.hide()

        self.btn_scroll_left = QPushButton("‹", self.scroll_area)
        self.btn_scroll_left.setFixedSize(32, 32)
        self.btn_scroll_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scroll_left.setStyleSheet(btn_style)
        self.btn_scroll_left.clicked.connect(self._scroll_left)
        self.btn_scroll_left.hide()

        bar = self.scroll_area.horizontalScrollBar()
        bar.valueChanged.connect(lambda _: self._update_scroll_buttons())
        bar.rangeChanged.connect(lambda _min, _max: self._update_scroll_buttons())

    def _animate_scroll(self, delta: int):
        """Anime le glissement fluide des éléments vers la gauche ou vers la droite."""
        bar = self.scroll_area.horizontalScrollBar()
        current = bar.value()
        target = max(0, min(bar.maximum(), current + delta))
        if current == target:
            return

        if hasattr(self, "_scroll_anim") and self._scroll_anim.state() == QPropertyAnimation.State.Running:
            self._scroll_anim.stop()

        self._scroll_anim = QPropertyAnimation(bar, b"value", self)
        self._scroll_anim.setDuration(350)
        self._scroll_anim.setStartValue(current)
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.valueChanged.connect(lambda _: self._update_scroll_buttons())
        self._scroll_anim.finished.connect(self._update_scroll_buttons)
        self._scroll_anim.start()

    def _scroll_right(self):
        vp = self.scroll_area.viewport()
        vp_width = vp.width() if vp else self.width()
        step = max(300, int(vp_width * 0.75))
        self._animate_scroll(step)

    def _scroll_left(self):
        vp = self.scroll_area.viewport()
        vp_width = vp.width() if vp else self.width()
        step = max(300, int(vp_width * 0.75))
        self._animate_scroll(-step)

    def _update_scroll_buttons(self):
        bar = self.scroll_area.horizontalScrollBar()
        max_val = bar.maximum()
        val = bar.value()

        self.btn_scroll_left.setVisible(val > 0)
        self.btn_scroll_right.setVisible(max_val > 0 and val < max_val)

        vp = self.scroll_area.viewport()
        w = vp.width() if vp and vp.width() > 50 else self.scroll_area.width()
        h = vp.height() if vp and vp.height() > 30 else self.scroll_area.height()
        if w <= 50:
            w = self.width() if self.width() > 50 else 800

        btn_size = 32
        btn_y = (min(h, self.content_height) - btn_size) // 2
        self.btn_scroll_right.move(max(10, w - btn_size - 8), max(0, btn_y))
        self.btn_scroll_left.move(8, max(0, btn_y))
        self.btn_scroll_right.raise_()
        self.btn_scroll_left.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scroll_buttons()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._update_scroll_buttons)

    def set_badge_count(self, count: int):
        self.badge_label.setText(str(count))

    def set_see_all_text(self, text: str):
        self.see_all_btn.setText(text)

    def clear_items(self):
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        QTimer.singleShot(30, self._update_scroll_buttons)

    def add_item(self, widget: QWidget):
        self.items_layout.addWidget(widget)
        QTimer.singleShot(30, self._update_scroll_buttons)

    def filter_items(self, query: str) -> int:
        """Filtre les éléments affichés selon la requête. Retourne le nombre d'éléments correspondants."""
        q = query.lower().strip()
        visible_count = 0
        total_items = self.items_layout.count()
        for i in range(total_items):
            item = self.items_layout.itemAt(i)
            if not item:
                continue
            widget = item.widget()
            if not widget:
                continue
            if not q:
                widget.setVisible(True)
                visible_count += 1
            else:
                name = ""
                if hasattr(widget, "channel") and widget.channel:
                    name = widget.channel.name or ""
                elif hasattr(widget, "item_data") and isinstance(widget.item_data, dict):
                    ch = widget.item_data.get("channel")
                    name = ch.name if ch else ""
                matches = q in name.lower()
                widget.setVisible(matches)
                if matches:
                    visible_count += 1

        self.set_badge_count(visible_count)
        if q:
            self.setVisible(visible_count > 0)
        else:
            self.setVisible(total_items > 0)
        QTimer.singleShot(30, self._update_scroll_buttons)
        return visible_count


# =========================================================================
# 6. VUE GLOBALE DU TABLEAU DE BORD (DASHBOARDVIEW)
# =========================================================================

class DashboardView(QWidget):
    movie_selected = pyqtSignal(Channel)
    series_selected = pyqtSignal(Channel)
    channel_selected = pyqtSignal(Channel)
    resume_playback_requested = pyqtSignal(Channel, float)  # channel, position
    navigate_section_requested = pyqtSignal(str)           # "live", "vod", "series", "favorites", "recently_added"
    playlist_switched = pyqtSignal(Playlist)

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.current_playlist_id: Optional[int] = None
        self.setObjectName("dashboardView")

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("background-color: #0b0f19;")
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll vertical global
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.main_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #0b0f19;
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #1e293b;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #334155;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.container_widget = QWidget()
        self.container_widget.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout(self.container_widget)
        self.container_layout.setContentsMargins(24, 16, 24, 30)
        self.container_layout.setSpacing(16)

        # 1. Bannière Hero "En cours de lecture"
        self.hero_banner = HeroBannerWidget(self.container_widget)
        self.hero_banner.resume_clicked.connect(self.resume_playback_requested.emit)
        self.container_layout.addWidget(self.hero_banner)

        # 2. Section "Reprendre la lecture"
        self.sec_continue = DashboardSection("Reprendre la lecture", "continue", "Voir tout >", content_height=262, parent=self.container_widget)
        self.sec_continue.see_all_clicked.connect(lambda: self.navigate_section_requested.emit("favorites"))
        self.container_layout.addWidget(self.sec_continue)

        # 3. Section "Recently watched live TV"
        self.sec_recent_live = DashboardSection("Recently watched live TV", "live", "Voir tout >", content_height=58, parent=self.container_widget)
        self.sec_recent_live.see_all_clicked.connect(self.navigate_section_requested.emit)
        self.container_layout.addWidget(self.sec_recent_live)

        # 4. Section "Favorite movies & series"
        self.sec_favs = DashboardSection("Favorite movies & series", "favorites", "Voir tout >", content_height=262, parent=self.container_widget)
        self.sec_favs.see_all_clicked.connect(self.navigate_section_requested.emit)
        self.container_layout.addWidget(self.sec_favs)

        # 5. Section "Récemment ajoutés"
        self.sec_recents = DashboardSection("Récemment ajoutés", "recently_added", "Voir tout >", content_height=262, parent=self.container_widget)
        self.sec_recents.see_all_clicked.connect(self.navigate_section_requested.emit)
        self.container_layout.addWidget(self.sec_recents)

        self.main_scroll.setWidget(self.container_widget)
        root_layout.addWidget(self.main_scroll)

    def set_playlist_id(self, playlist_id: Optional[int]):
        self.current_playlist_id = playlist_id
        self.refresh_view()

    def refresh_view(self):
        pl_id = self.current_playlist_id

        # 1. Bannière Hero & Reprendre la lecture
        continue_items = self.db.get_dashboard_continue_watching(playlist_id=pl_id, limit=20)
        if continue_items:
            self.hero_banner.set_data(continue_items[0])
            self.hero_banner.setVisible(True)
        else:
            self.hero_banner.setVisible(False)

        self.sec_continue.clear_items()
        self.sec_continue.set_badge_count(len(continue_items))
        if continue_items:
            self.sec_continue.setVisible(True)
            for item in continue_items:
                ch = item["channel"]
                card = DashboardPosterCard(ch, progress_info=item, parent=self.sec_continue.items_container)
                pos = float(item.get("position", 0.0))
                card.clicked.connect(lambda c, p=pos: self.resume_playback_requested.emit(c, p))
                self.sec_continue.add_item(card)
        else:
            self.sec_continue.setVisible(False)

        # 2. Recently watched live TV
        live_items = self.db.get_dashboard_recent_live(playlist_id=pl_id, limit=15)
        self.sec_recent_live.clear_items()
        self.sec_recent_live.set_badge_count(len(live_items))
        if live_items:
            self.sec_recent_live.setVisible(True)
            for l_item in live_items:
                ch = l_item["channel"]
                card = LiveTvMiniCard(l_item, parent=self.sec_recent_live.items_container)
                card.clicked.connect(self.channel_selected.emit)
                self.sec_recent_live.add_item(card)
        else:
            self.sec_recent_live.setVisible(False)

        # 3. Favorite movies & series
        fav_channels = self.db.get_channels(
            playlist_id=pl_id,
            favorites_only=True,
            order_by="favorite_date_desc",
            limit=30
        )
        fav_vod_series = [c for c in fav_channels if c.stream_type in ("movie", "series")]
        self.sec_favs.clear_items()
        self.sec_favs.set_badge_count(len(fav_vod_series))
        self.sec_favs.set_see_all_text(f"Voir les {len(fav_vod_series)} >" if fav_vod_series else "Voir tout >")
        if fav_vod_series:
            self.sec_favs.setVisible(True)
            for ch in fav_vod_series:
                card = DashboardPosterCard(ch, parent=self.sec_favs.items_container)
                card.clicked.connect(self._on_channel_clicked)
                self.sec_favs.add_item(card)
        else:
            self.sec_favs.setVisible(False)

        # 4. Récemment ajoutés sur [Playlist]
        playlists = self.db.get_playlists()
        active_pl_name = tr("la liste")
        if pl_id:
            for pl in playlists:
                if pl.id == pl_id:
                    active_pl_name = pl.name
                    break
        self.sec_recents.title_label.setText(tr("Récemment ajoutés sur {name}", name=active_pl_name))

        recents = self.db.get_recently_added_channels(playlist_id=pl_id, limit=20)
        recent_vod = [c for c in recents if c.stream_type in ("movie", "series")]
        self.sec_recents.clear_items()
        self.sec_recents.set_badge_count(len(recent_vod))
        if recent_vod:
            self.sec_recents.setVisible(True)
            for ch in recent_vod:
                card = DashboardPosterCard(ch, parent=self.sec_recents.items_container)
                card.clicked.connect(self._on_channel_clicked)
                self.sec_recents.add_item(card)
        else:
            self.sec_recents.setVisible(False)

    def _on_channel_clicked(self, channel: Channel):
        if channel.stream_type in ("movie", "vod"):
            self.movie_selected.emit(channel)
        elif channel.stream_type == "series":
            self.series_selected.emit(channel)
        elif channel.stream_type == "replay" or "/timeshift/" in (channel.stream_url or "").lower():
            self.resume_playback_requested.emit(channel, 0.0)
        else:
            self.channel_selected.emit(channel)

    def set_search_query(self, query: str):
        """Filtre les sections et bannières du tableau de bord selon le texte de recherche."""
        q = query.lower().strip()
        self.sec_continue.filter_items(q)
        self.sec_recent_live.filter_items(q)
        self.sec_favs.filter_items(q)
        self.sec_recents.filter_items(q)

        if hasattr(self, "hero_banner") and hasattr(self.hero_banner, "channel"):
            hero_ch = self.hero_banner.channel
            if hero_ch and hero_ch.name:
                if not q:
                    self.hero_banner.setVisible(True)
                else:
                    self.hero_banner.setVisible(q in hero_ch.name.lower())

    def retranslate_ui(self):
        """Met à jour les textes et en-têtes du tableau de bord."""
        if hasattr(self, "hero_banner"):
            if hasattr(self.hero_banner, "btn_resume"):
                self.hero_banner.btn_resume.setText("  " + tr("Reprendre la lecture"))
            if not getattr(self.hero_banner, "channel", None):
                self.hero_banner.title_label.setText(tr("Aucun média en cours") if hasattr(tr, "__call__") else "Aucun média en cours")

        see_all_str = tr("Voir tout") + " >"
        if hasattr(self, "sec_continue"):
            self.sec_continue.title_label.setText(tr("Reprendre la lecture"))
            self.sec_continue.set_see_all_text(see_all_str)

        if hasattr(self, "sec_recent_live"):
            self.sec_recent_live.title_label.setText(tr("TV en direct"))
            self.sec_recent_live.set_see_all_text(see_all_str)

        if hasattr(self, "sec_favs"):
            self.sec_favs.title_label.setText(tr("Vos Favoris"))
            self.sec_favs.set_see_all_text(see_all_str)

        if hasattr(self, "sec_recents"):
            self.sec_recents.set_see_all_text(see_all_str)

        self.refresh_content()


