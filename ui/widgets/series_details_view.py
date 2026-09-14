"""
Vue détaillée et immersive pour les séries IPTV (style Netflix / moderne).
Affiche la fiche série complète avec bannière backdrop, affiche 2:3, badges métadonnées,
synopsis, distribution, réalisateur, sélection de saisons et grille de cartes d'épisodes 16:9.
Intègre des barres de progression sous chaque vignette, des badges verts cochés sur les épisodes
vus ainsi que sur les boutons de saisons complétées à 100%.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QFrame, QSizePolicy, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread, QRect, QRectF, QEvent
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QMouseEvent,
    QPen, QPainterPath, QLinearGradient, QImage, QIcon
)

from core.models import Channel, Playlist, format_seconds, parse_movie_metadata
from core.database import Database
from core.xtream_client import XtreamClient
from core.image_loader import ImageLoader
from ui.icons import get_icon
from ui.widgets.rounded_poster import RoundedPosterLabel


# Cache mémoire des informations de séries pour un affichage instantané (0ms) lors de la navigation
_SERIES_INFO_CACHE: Dict[Tuple[int, str], Dict[str, Any]] = {}
_MAX_SERIES_INFO_CACHE: int = 60


class SeriesInfoWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, client: XtreamClient, series_id: str, parent=None):
        super().__init__(parent)
        self.client = client
        self.series_id = series_id

    def run(self):
        try:
            data = self.client.get_series_info(self.series_id)
            if not isinstance(data, dict):
                raise ValueError("Format de données de série invalide")
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class _SeriesTrailerLookupWorker(QThread):
    finished_trailer = pyqtSignal(dict)

    def __init__(self, tmdb_id: str, title: str, year: str, preferred_lang: str, orig_trailer: str, parent=None):
        super().__init__(None)
        self.tmdb_id = tmdb_id
        self.title = title
        self.year = year
        self.preferred_lang = preferred_lang
        self.orig_trailer = orig_trailer

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            from core.tmdb_client import find_best_trailer
            result = find_best_trailer(
                media_type="tv",
                tmdb_id=self.tmdb_id,
                title=self.title,
                year=self.year,
                preferred_audio_lang=self.preferred_lang,
                orig_trailer=self.orig_trailer,
            )
            if self.isInterruptionRequested():
                return
            self.finished_trailer.emit(result or {})
        except Exception:
            if not self.isInterruptionRequested():
                self.finished_trailer.emit({})



class EpisodeProgressBar(QWidget):
    """Barre de progression horizontale dédiée placée immédiatement sous la vignette 16:9."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self.setFixedWidth(220)
        self.ratio: float = 0.0
        self.is_watched: bool = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_progress(self, ratio: float, is_watched: bool):
        self.ratio = max(0.0, min(1.0, ratio))
        self.is_watched = is_watched
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # Fond de la piste
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1e293b"))
        painter.drawRoundedRect(0, 0, rect.width(), rect.height(), 2, 2)

        # Remplissage
        if self.is_watched or self.ratio >= 0.90:
            # 100% vert si épisode déjà vu
            painter.setBrush(QColor("#10b981"))
            painter.drawRoundedRect(0, 0, rect.width(), rect.height(), 2, 2)
        elif self.ratio > 0.0:
            # Rouge proportionnel si lecture en cours
            fill_w = max(4, int(rect.width() * self.ratio))
            painter.setBrush(QColor("#ef4444"))
            painter.drawRoundedRect(0, 0, fill_w, rect.height(), 2, 2)


class EpisodeCardWidget(QWidget):
    """Carte d'épisode avec vignette 16:9, bouton cliquable de validation 'Vu / Terminé', barre de progression et métadonnées."""
    clicked = pyqtSignal(dict, str)  # (episode_dict, season_num)
    toggle_watched_clicked = pyqtSignal(dict, str)  # (episode_dict, season_num)

    CARD_WIDTH = 220
    THUMB_HEIGHT = 124

    def __init__(
        self,
        episode: Dict[str, Any],
        season_num: str,
        is_watched: bool = False,
        progress_ratio: float = 0.0,
        is_current_playing: bool = False,
        fallback_urls: Optional[List[str]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.episode = episode
        self.season_num = season_num
        self.is_watched = is_watched
        self.progress_ratio = progress_ratio
        self.is_current_playing = is_current_playing
        self.fallback_urls = [u for u in (fallback_urls or []) if u]
        self._current_fallback_idx = 0
        self._active_loading_url = ""
        self.is_hovered = False
        self._check_hovered = False
        self.pixmap: Optional[QPixmap] = None

        self.setFixedWidth(self.CARD_WIDTH)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._init_ui()
        self._load_thumbnail()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)

        # 1. Vignette 16:9
        self.thumb_container = QWidget()
        self.thumb_container.setFixedSize(self.CARD_WIDTH, self.THUMB_HEIGHT)
        self.thumb_container.setCursor(Qt.CursorShape.PointingHandCursor)
        self.thumb_container.setMouseTracking(True)
        self.thumb_container.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.thumb_container.paintEvent = self._paint_thumbnail
        layout.addWidget(self.thumb_container)

        # 2. Barre de progression dédiée SOUS la vignette
        self.progress_bar = EpisodeProgressBar(self)
        self.progress_bar.set_progress(self.progress_ratio, self.is_watched)
        self.progress_bar.setCursor(Qt.CursorShape.ArrowCursor)
        self.progress_bar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.progress_bar)

        # 3. Titre de l'épisode
        ep_num = self.episode.get("episode_num", 1)
        raw_title = self.episode.get("title", f"Épisode {ep_num}")
        clean_title = raw_title.strip()
        if not clean_title.startswith(f"{ep_num}."):
            clean_title = f"{ep_num}. {clean_title}"

        self.title_label = QLabel(clean_title)
        self.title_label.setToolTip(clean_title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.title_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.title_label.setStyleSheet("""
            color: #ffffff;
            font-size: 12px;
            font-weight: 700;
            line-height: 1.2;
        """)
        self.title_label.setWordWrap(True)
        self.title_label.setFixedHeight(30)
        self.title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.title_label)

        # 4. Synopsis (aligné en haut, hauteur augmentée pour lignes supplémentaires et info-bulle complète)
        info = self.episode.get("info", {})
        plot = info.get("plot", "") or info.get("overview", "") or "Aucune description disponible."
        self.plot_label = QLabel(plot)
        self.plot_label.setToolTip(f"Synopsis :\n{plot}")
        self.plot_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.plot_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 11px;
            line-height: 1.25;
        """)
        self.plot_label.setWordWrap(True)
        self.plot_label.setFixedHeight(48)
        self.plot_label.setCursor(Qt.CursorShape.ArrowCursor)
        layout.addWidget(self.plot_label)

        # 5. Durée
        duration_str = info.get("duration", "")
        if not duration_str and info.get("duration_secs"):
            duration_str = format_seconds(float(info.get("duration_secs", 0)))
        if not duration_str:
            duration_str = "00:50:00"

        self.dur_label = QLabel(duration_str)
        self.dur_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.dur_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.dur_label.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 500;")
        self.dur_label.setFixedHeight(14)
        self.dur_label.setCursor(Qt.CursorShape.ArrowCursor)
        layout.addWidget(self.dur_label)

    def _get_thumb_url(self) -> str:
        info = self.episode.get("info", {}) if isinstance(self.episode.get("info"), dict) else {}
        url = (
            info.get("movie_image") or
            info.get("cover") or
            info.get("cover_big") or
            info.get("still_path") or
            info.get("backdrop_path") or
            self.episode.get("cover") or
            self.episode.get("stream_icon") or
            self.episode.get("movie_image") or
            ""
        )
        if isinstance(url, list) and url:
            url = url[0]
        return ImageLoader.normalize_url(str(url)) if url else ""

    def _load_thumbnail(self):
        thumb_url = self._get_thumb_url()
        loader = ImageLoader.instance()
        loader.image_loaded.connect(self._on_image_loaded)
        loader.image_failed.connect(self._on_image_failed)

        if thumb_url and thumb_url.startswith("http"):
            self._active_loading_url = thumb_url
            cached = loader.get_cached_image(thumb_url)
            if cached:
                self.pixmap = cached
                self.thumb_container.update()
                return
            loader.request_image_priority(thumb_url)
        else:
            self._try_next_fallback()

    def _try_next_fallback(self):
        loader = ImageLoader.instance()
        while self._current_fallback_idx < len(self.fallback_urls):
            fb_url = ImageLoader.normalize_url(self.fallback_urls[self._current_fallback_idx])
            self._current_fallback_idx += 1
            if fb_url and fb_url.startswith("http"):
                self._active_loading_url = fb_url
                cached = loader.get_cached_image(fb_url)
                if cached:
                    self.pixmap = cached
                    self.thumb_container.update()
                    return
                loader.request_image_priority(fb_url)
                return

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        if url and self._active_loading_url and url == self._active_loading_url:
            self.pixmap = pixmap
            self._scaled_pixmap = None
            self.thumb_container.update()
            self.update()

    def _on_image_failed(self, url: str):
        if url and self._active_loading_url and url == self._active_loading_url:
            self._try_next_fallback()

    def set_current_playing(self, is_playing: bool):
        if self.is_current_playing != is_playing:
            self.is_current_playing = is_playing
            self.thumb_container.update()

    def set_progress_ratio(self, ratio: float, is_watched: bool = False):
        # On ne redessine la vignette que si l'état de complétion (coche) change
        was_completed = (self.is_watched or self.progress_ratio >= 0.90)
        now_completed = (is_watched or ratio >= 0.90)
        self.progress_ratio = ratio
        self.is_watched = is_watched
        self.progress_bar.set_progress(ratio, is_watched)
        if was_completed != now_completed:
            self.thumb_container.update()

    def _get_check_rect(self) -> QRect:
        return QRect(8, 8, 24, 24)

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self._check_hovered = False
        self.thumb_container.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.pos()
        thumb_pos = self.thumb_container.mapFrom(self, pos)
        is_over_thumb = self.thumb_container.rect().contains(thumb_pos)
        is_over_title = self.title_label.rect().contains(self.title_label.mapFrom(self, pos))

        new_hovered = (is_over_thumb or is_over_title)
        new_check = is_over_thumb and self._get_check_rect().contains(thumb_pos)

        hover_changed = (self.is_hovered != new_hovered)
        check_changed = (self._check_hovered != new_check)

        self.is_hovered = new_hovered
        self._check_hovered = new_check

        if check_changed:
            if self._check_hovered:
                tip = "Marqué comme vu. Cliquer pour réinitialiser" if (self.is_watched or self.progress_ratio >= 0.90) else "Marquer comme vu et terminé"
                self.setToolTip(tip)
            else:
                self.setToolTip("")

        if hover_changed or check_changed:
            self.thumb_container.update()

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            thumb_pos = self.thumb_container.mapFrom(self, event.pos())
            if self.thumb_container.rect().contains(thumb_pos) and self._get_check_rect().contains(thumb_pos):
                self.toggle_watched_clicked.emit(self.episode, self.season_num)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            thumb_pos = self.thumb_container.mapFrom(self, event.pos())
            is_over_thumb = self.thumb_container.rect().contains(thumb_pos)
            is_over_title = self.title_label.rect().contains(self.title_label.mapFrom(self, event.pos()))
            if (is_over_thumb and not self._get_check_rect().contains(thumb_pos)) or is_over_title:
                self.clicked.emit(self.episode, self.season_num)
        super().mouseReleaseEvent(event)

    def _paint_thumbnail(self, event):
        painter = QPainter(self.thumb_container)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.thumb_container.rect()

        # 1. Découpe carrée 16:9 (les images des épisodes restent rectangulaires/carrées)
        path = QPainterPath()
        path.addRect(0, 0, rect.width(), rect.height())
        painter.setClipPath(path)

        if self.pixmap and not self.pixmap.isNull():
            if not getattr(self, "_scaled_pixmap", None) or getattr(self, "_scaled_pixmap_size", None) != rect.size():
                self._scaled_pixmap = self.pixmap.scaled(
                    rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._scaled_pixmap_size = rect.size()
            scaled = self._scaled_pixmap
            sx = (rect.width() - scaled.width()) // 2
            sy = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(sx, sy, scaled)
        else:
            painter.fillRect(rect, QColor("#1e293b"))
            icon_pix = get_icon("tv", color="#475569").pixmap(36, 36)
            painter.drawPixmap((rect.width() - 36) // 2, (rect.height() - 36) // 2, icon_pix)

        # 2. Overlay sombre et bouton Play au survol
        if (self.is_hovered and not self._check_hovered) or self.is_current_playing:
            painter.fillRect(rect, QColor(0, 0, 0, 110))
            play_pix = get_icon("play_arrow", color="#ffffff" if not self.is_current_playing else "#38bdf8").pixmap(38, 38)
            painter.drawPixmap((rect.width() - 38) // 2, (rect.height() - 38) // 2, play_pix)

        painter.setClipping(False)

        # 3. Bordure carrée
        painter.save()
        if self.is_current_playing:
            painter.setPen(QPen(QColor("#38bdf8"), 2.5))
        elif self.is_hovered:
            painter.setPen(QPen(QColor("#60a5fa"), 1.8))
        else:
            painter.setPen(QPen(QColor("#334155"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(1, 1, rect.width() - 2, rect.height() - 2)
        painter.restore()

        # 4. Bouton coche 'Vu / Terminé' en haut à gauche
        is_completed = (self.is_watched or self.progress_ratio >= 0.90)
        check_rect = self._get_check_rect()
        painter.save()

        if is_completed:
            # Épisode déjà vu : fond vert
            if self._check_hovered:
                painter.setBrush(QColor("#059669"))
                painter.setPen(QPen(QColor("#ffffff"), 1.5))
            else:
                painter.setBrush(QColor("#10b981"))
                painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(check_rect, 6, 6)

            # Coche blanche nette
            painter.setPen(QPen(QColor("#ffffff"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            cx = check_rect.x()
            cy = check_rect.y()
            painter.drawLine(cx + 5, cy + 12, cx + 9, cy + 17)
            painter.drawLine(cx + 9, cy + 17, cx + 18, cy + 7)
        else:
            # Épisode non vu : bouton avec coche discrète
            if self._check_hovered:
                painter.setBrush(QColor("#10b981"))
                painter.setPen(QPen(QColor("#ffffff"), 1.5))
                painter.drawRoundedRect(check_rect, 6, 6)
                painter.setPen(QPen(QColor("#ffffff"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                cx = check_rect.x()
                cy = check_rect.y()
                painter.drawLine(cx + 5, cy + 12, cx + 9, cy + 17)
                painter.drawLine(cx + 9, cy + 17, cx + 18, cy + 7)
            else:
                painter.setBrush(QColor(15, 23, 42, 190))
                painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
                painter.drawRoundedRect(check_rect, 6, 6)
                painter.setPen(QPen(QColor(255, 255, 255, 140), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                cx = check_rect.x()
                cy = check_rect.y()
                painter.drawLine(cx + 6, cy + 12, cx + 10, cy + 16)
                painter.drawLine(cx + 10, cy + 16, cx + 17, cy + 8)

        painter.restore()

        # 5. Badge numéro d'épisode en bas à droite
        ep_num_str = str(self.episode.get("episode_num", "1"))
        painter.save()
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        txt_w = fm.horizontalAdvance(ep_num_str)
        badge_w = max(18, txt_w + 10)
        badge_h = 18
        bx = rect.width() - badge_w - 6
        by = rect.height() - badge_h - 6
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 220))
        painter.drawRoundedRect(bx, by, badge_w, badge_h, 4, 4)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(bx, by, badge_w, badge_h, Qt.AlignmentFlag.AlignCenter, ep_num_str)
        painter.restore()


class SeriesDetailsView(QWidget):
    """
    Vue immersive complète pour les fiches de séries :
    - Hero banner avec backdrop fanart, affiche 2:3, badges, synopsis, casting, réalisateur
    - Bouton principal 'Lancer la lecture' ou 'Reprendre'
    - Bouton Favoris
    - Navigation par saisons avec coche verte sur saisons complétées et grille d'épisodes 16:9 interactive
    - Lecteur embarqué en haut de la fiche lors de la lecture d'un épisode (hors plein écran)
    """
    back_clicked = pyqtSignal()
    fullscreen_requested = pyqtSignal()
    favorite_toggled = pyqtSignal(Channel, bool)
    play_episode_requested = pyqtSignal(Channel, list, int, float)  # (channel, all_episodes, current_idx, start_pos)
    play_trailer_requested = pyqtSignal(str, str)  # (title, trailer_url)
    artist_clicked = pyqtSignal(str)

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.channel: Optional[Channel] = None
        self.playlist: Optional[Playlist] = None
        self.series_data: Dict[str, Any] = {}
        self.episodes_by_season: Dict[str, List[Dict[str, Any]]] = {}
        self.season_covers: Dict[str, str] = {}
        self.current_season: str = "1"
        self.all_episodes_flat: List[Dict[str, Any]] = []

        self._backdrop_pixmap: Optional[QPixmap] = None
        self._poster_pixmap: Optional[QPixmap] = None
        self._worker: Optional[SeriesInfoWorker] = None
        self._trailer_worker: Optional[_SeriesTrailerLookupWorker] = None
        self._video_widget = None
        self._is_fullscreen: bool = False
        self._current_playing_episode_id: str = ""
        self._marked_watched_episodes: set = set()
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("background-color: #0d111a;")
        self.setCursor(Qt.CursorShape.ArrowCursor)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Zone déroulante principale
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setCursor(Qt.CursorShape.ArrowCursor)
        self.scroll_area.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #0d111a;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.content_widget = QWidget()
        self.content_widget.setCursor(Qt.CursorShape.ArrowCursor)
        self.content_widget.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(28, 20, 28, 30)
        self.content_layout.setSpacing(14)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 1. Barre de navigation supérieure (Bouton retour + tag)
        self.nav_row_widget = QWidget()
        self.nav_row_widget.setCursor(Qt.CursorShape.ArrowCursor)
        nav_row = QHBoxLayout(self.nav_row_widget)
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(12)

        self.back_btn = QPushButton("‹")
        self.back_btn.setFixedSize(36, 36)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_btn.setToolTip("Retour à la galerie de séries")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 0.85);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 18px;
                font-size: 22px;
                font-weight: 700;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
        """)
        self.back_btn.clicked.connect(self.back_clicked.emit)
        nav_row.addWidget(self.back_btn)

        nav_tag = QLabel("FICHE DE LA SÉRIE")
        nav_tag.setCursor(Qt.CursorShape.ArrowCursor)
        nav_tag.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700; letter-spacing: 1.5px;")
        nav_row.addWidget(nav_tag)
        nav_row.addStretch()
        self.content_layout.addWidget(self.nav_row_widget)

        # 2. Conteneur principal de la fiche (Hero banner + Saisons + Épisodes)
        self.details_container = QWidget()
        self.details_container.setCursor(Qt.CursorShape.ArrowCursor)
        self.details_container.setStyleSheet("background: transparent;")
        self.details_layout = QVBoxLayout(self.details_container)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(14)
        self.details_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ------------------ 1. SECTION SAISONS ET ÉPISODES ------------------
        self.seasons_container = QWidget()
        self.seasons_container.setCursor(Qt.CursorShape.ArrowCursor)
        self.seasons_container.setStyleSheet("background: transparent;")
        self.seasons_container_layout = QVBoxLayout(self.seasons_container)
        self.seasons_container_layout.setContentsMargins(0, 0, 0, 0)
        self.seasons_container_layout.setSpacing(14)
        self.seasons_container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        seasons_header_box = QVBoxLayout()
        seasons_header_box.setSpacing(10)

        # Titre de la section
        seasons_title_row = QHBoxLayout()
        self.seasons_title_lbl = QLabel("Saisons et épisodes")
        self.seasons_title_lbl.setCursor(Qt.CursorShape.ArrowCursor)
        self.seasons_title_lbl.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 800;")
        seasons_title_row.addWidget(self.seasons_title_lbl)
        seasons_title_row.addStretch()
        seasons_header_box.addLayout(seasons_title_row)

        # Onglets de saisons (Pills)
        self.seasons_tabs_layout = QHBoxLayout()
        self.seasons_tabs_layout.setSpacing(8)
        self.seasons_tabs_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        seasons_header_box.addLayout(self.seasons_tabs_layout)

        self.seasons_container_layout.addLayout(seasons_header_box)

        # Grille des cartes d'épisodes
        self.episodes_grid = QGridLayout()
        self.episodes_grid.setSpacing(16)
        self.episodes_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.seasons_container_layout.addLayout(self.episodes_grid)

        # Section Bande-annonce YouTube (placée immédiatement sous les épisodes et vignettes)
        self._current_trailer_id = ""
        self.trailer_section = QFrame()
        self.trailer_section.setObjectName("seriesTrailerSection")
        self.trailer_section.setCursor(Qt.CursorShape.ArrowCursor)
        self.trailer_section.setStyleSheet("""
            QFrame#seriesTrailerSection {
                background-color: #151b27;
                border: 1px solid #232d3f;
                border-radius: 12px;
                margin-top: 10px;
            }
        """)
        trailer_layout = QVBoxLayout(self.trailer_section)
        trailer_layout.setContentsMargins(20, 16, 20, 16)
        trailer_layout.setSpacing(12)

        trailer_header = QHBoxLayout()
        trailer_title = QLabel("Bande-annonce de la série")
        trailer_title.setCursor(Qt.CursorShape.ArrowCursor)
        trailer_title.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 700;")
        trailer_header.addWidget(trailer_title)

        self.trailer_badge = QLabel("")
        self.trailer_badge.setStyleSheet("""
            background-color: rgba(220, 38, 38, 0.2);
            color: #f87171;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid rgba(220, 38, 38, 0.4);
        """)
        self.trailer_badge.hide()
        trailer_header.addWidget(self.trailer_badge)

        trailer_header.addStretch()
        trailer_layout.addLayout(trailer_header)

        trailer_content_row = QHBoxLayout()
        trailer_content_row.setSpacing(18)

        # Miniature 16:9
        self.trailer_thumb_label = QLabel()
        self.trailer_thumb_label.setFixedSize(220, 124)
        self.trailer_thumb_label.setScaledContents(True)
        self.trailer_thumb_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trailer_thumb_label.setToolTip("Cliquer pour regarder la bande-annonce dans l'application")
        self.trailer_thumb_label.mousePressEvent = lambda e: self._on_play_trailer_clicked()
        self.trailer_thumb_label.setStyleSheet("""
            QLabel {
                background-color: #0b0f17;
                border: 1px solid #2e3a50;
                border-radius: 8px;
            }
            QLabel:hover {
                border-color: #e11d48;
            }
        """)
        trailer_content_row.addWidget(self.trailer_thumb_label)

        # Actions trailer
        trailer_actions = QVBoxLayout()
        trailer_actions.setSpacing(10)
        trailer_actions.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.trailer_name_label = QLabel("")
        self.trailer_name_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.trailer_name_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 500;")
        self.trailer_name_label.setWordWrap(True)
        trailer_actions.addWidget(self.trailer_name_label)

        btns_row = QHBoxLayout()
        btns_row.setSpacing(10)

        # 1. Bouton lecture directe In-App
        self.play_trailer_btn = QPushButton("  Lire la bande-annonce")
        self.play_trailer_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
        self.play_trailer_btn.setIconSize(QSize(16, 16))
        self.play_trailer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_trailer_btn.setStyleSheet("""
            QPushButton {
                background-color: #cc0000;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #e60000;
            }
            QPushButton:pressed {
                background-color: #990000;
            }
        """)
        self.play_trailer_btn.clicked.connect(self._on_play_trailer_clicked)
        btns_row.addWidget(self.play_trailer_btn)

        # 2. Bouton secondaire : ouvrir dans le navigateur
        self.open_youtube_btn = QPushButton("  Ouvrir sur YouTube")
        self.open_youtube_btn.setIcon(get_icon("open_in_new", color="#cbd5e1"))
        self.open_youtube_btn.setIconSize(QSize(15, 15))
        self.open_youtube_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_youtube_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                font-size: 12px;
                font-weight: 600;
                padding: 10px 16px;
                border-radius: 6px;
                border: 1px solid #334155;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
                border-color: #475569;
            }
            QPushButton:pressed {
                background-color: #0f172a;
            }
        """)
        self.open_youtube_btn.clicked.connect(self._open_trailer_url)
        btns_row.addWidget(self.open_youtube_btn)
        btns_row.addStretch()

        trailer_actions.addLayout(btns_row)

        trailer_content_row.addLayout(trailer_actions)
        trailer_content_row.addStretch()
        trailer_layout.addLayout(trailer_content_row)

        self.trailer_section.hide()
        self.seasons_container_layout.addWidget(self.trailer_section)

        # ------------------ 2. SECTION DESCRIPTION DE LA SÉRIE (HERO BANNER) ------------------
        self.hero_banner = QFrame()
        self.hero_banner.setObjectName("seriesHeroBanner")
        self.hero_banner.setCursor(Qt.CursorShape.ArrowCursor)
        self.hero_banner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.hero_banner.setStyleSheet("background-color: transparent; border: none;")
        self.hero_banner.paintEvent = self._paint_hero_backdrop

        hero_main_layout = QVBoxLayout(self.hero_banner)
        hero_main_layout.setContentsMargins(0, 0, 0, 0)
        hero_main_layout.setSpacing(14)

        # Contenu Hero : Poster à gauche, Métadonnées à droite
        hero_content_row = QHBoxLayout()
        hero_content_row.setSpacing(28)
        hero_content_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Affiche de la série (160x240) avec coins arrondis
        self.poster_label = RoundedPosterLabel(radius=10, border_color="#334155", fallback_icon="tv", parent=self)
        self.poster_label.setFixedSize(160, 240)
        self.poster_label.setCursor(Qt.CursorShape.ArrowCursor)
        hero_content_row.addWidget(self.poster_label)

        # Bloc métadonnées
        meta_box = QVBoxLayout()
        meta_box.setSpacing(8)

        self.title_label = QLabel("Titre de la série")
        self.title_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.title_label.setStyleSheet("color: #ffffff; font-size: 24px; font-weight: 800;")
        self.title_label.setWordWrap(True)
        meta_box.addWidget(self.title_label)

        # Ligne de badges
        self.badges_row = QHBoxLayout()
        self.badges_row.setSpacing(8)

        self.badge_year = QLabel("2024")
        self.badge_year.setCursor(Qt.CursorShape.ArrowCursor)
        self.badge_year.setStyleSheet("background-color: #1e293b; color: #e2e8f0; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 5px; border: 1px solid #334155;")
        self.badges_row.addWidget(self.badge_year)

        self.badge_genre = QLabel("Genre")
        self.badge_genre.setCursor(Qt.CursorShape.ArrowCursor)
        self.badge_genre.setStyleSheet("background-color: #1e293b; color: #e2e8f0; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 5px; border: 1px solid #334155;")
        self.badges_row.addWidget(self.badge_genre)

        self.badge_duration = QLabel("50 min/ep")
        self.badge_duration.setCursor(Qt.CursorShape.ArrowCursor)
        self.badge_duration.setStyleSheet("background-color: #1e293b; color: #e2e8f0; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 5px; border: 1px solid #334155;")
        self.badges_row.addWidget(self.badge_duration)

        self.badge_rating = QLabel("★ 8.0")
        self.badge_rating.setCursor(Qt.CursorShape.ArrowCursor)
        self.badge_rating.setStyleSheet("background-color: rgba(245, 158, 11, 0.15); color: #fbbf24; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 5px; border: 1px solid rgba(245, 158, 11, 0.3);")
        self.badges_row.addWidget(self.badge_rating)

        self.badges_row.addStretch()
        meta_box.addLayout(self.badges_row)

        # Synopsis
        self.plot_label = QLabel("Chargement des informations...")
        self.plot_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.plot_label.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.4;")
        self.plot_label.setWordWrap(True)
        self.plot_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        meta_box.addWidget(self.plot_label)

        # Distribution & Réalisateur
        self.cast_label = QLabel("Distribution : —")
        self.cast_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.cast_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.cast_label.setWordWrap(True)
        self.cast_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.cast_label.linkActivated.connect(self._on_artist_link_clicked)
        meta_box.addWidget(self.cast_label)

        self.director_label = QLabel("Réalisateur : —")
        self.director_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.director_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.director_label.setWordWrap(True)
        self.director_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.director_label.linkActivated.connect(self._on_artist_link_clicked)
        meta_box.addWidget(self.director_label)

        # Boutons d'action
        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        self.resume_btn = QPushButton("  Lancer la lecture")
        self.resume_btn.setIcon(get_icon("play_arrow", color="#0f172a"))
        self.resume_btn.setIconSize(QSize(20, 20))
        self.resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resume_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #0f172a;
                border: none;
                border-radius: 8px;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
        """)
        self.resume_btn.clicked.connect(self._on_resume_clicked)
        actions_row.addWidget(self.resume_btn)

        self.fav_btn = QPushButton("  Ajouter aux favoris")
        self.fav_btn.setIcon(get_icon("favorite_border", color="#f43f5e"))
        self.fav_btn.setIconSize(QSize(18, 18))
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fav_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 0.85);
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #242f44;
                border-color: #f43f5e;
                color: #f43f5e;
            }
        """)
        self.fav_btn.clicked.connect(self._on_fav_clicked)
        actions_row.addWidget(self.fav_btn)

        actions_row.addStretch()
        meta_box.addLayout(actions_row)

        hero_content_row.addLayout(meta_box, stretch=1)
        hero_main_layout.addLayout(hero_content_row)

        # Disposition par défaut (hors lecture vidéo) : Description en haut, saisons/épisodes en bas
        self._update_sections_order(video_playing=False)

        self.content_layout.addWidget(self.details_container)

        self.scroll_area.setWidget(self.content_widget)
        self.scroll_area.viewport().installEventFilter(self)
        main_layout.addWidget(self.scroll_area)

    def _update_sections_order(self, video_playing: bool):
        """Réorganise dynamiquement l'ordre des sections de la fiche série :
        - En cours de diffusion vidéo : Saisons et épisodes immédiatement sous le lecteur, description tout en bas.
        - Hors diffusion vidéo : Description complète en haut de la fiche, saisons et épisodes en dessous.
        """
        if not hasattr(self, "hero_banner") or not hasattr(self, "seasons_container") or not hasattr(self, "details_layout"):
            return

        self._is_video_playing = video_playing

        self.details_layout.removeWidget(self.hero_banner)
        self.details_layout.removeWidget(self.seasons_container)

        if video_playing:
            self.hero_banner.setStyleSheet("background-color: transparent; border: none; margin-top: 20px;")
            self.seasons_container.setStyleSheet("background-color: transparent; border: none; margin-top: 0px;")
            self.details_layout.addWidget(self.seasons_container)
            self.details_layout.addWidget(self.hero_banner)
            if hasattr(self, "trailer_section"):
                self.trailer_section.hide()
        else:
            self.hero_banner.setStyleSheet("background-color: transparent; border: none; margin-top: 0px;")
            self.seasons_container.setStyleSheet("background-color: transparent; border: none; margin-top: 14px;")
            self.details_layout.addWidget(self.hero_banner)
            self.details_layout.addWidget(self.seasons_container)
            if hasattr(self, "trailer_section") and getattr(self, "_current_trailer_id", None):
                self.trailer_section.show()

        self.hero_banner.show()
        self.hero_banner.update()
        self.seasons_container.show()

    # ------------------ CHARGEMENT ET RENDU ------------------

    def load_series(self, channel: Channel):
        """Charge les informations détaillées et épisodes d'une série."""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if hasattr(self, "scroll_area") and self.scroll_area.viewport():
            self.scroll_area.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        # Résolution défensive de la série si stream_id est manquant
        if (not channel.stream_id or not str(channel.stream_id).strip() or not (channel.stream_url or "").startswith("xtream_series://")) and self.db:
            resolved = None
            if channel.id:
                resolved = self.db.get_channel_by_id(channel.id)
            if not resolved or not resolved.stream_id:
                matching = self.db.get_channels(
                    playlist_id=channel.playlist_id or None,
                    search_query=channel.name,
                    stream_type="series",
                    limit=10
                )
                for cand in matching:
                    if cand.stream_type == "series" and cand.stream_id:
                        if cand.name.lower().strip() == channel.name.lower().strip():
                            resolved = cand
                            break
            if resolved and resolved.stream_id:
                channel = resolved

        self.channel = channel
        self.playlist = self.db.get_playlist(channel.playlist_id)
        if not self.playlist and self.db:
            pls = self.db.get_playlists()
            if pls:
                self.playlist = pls[0]
        self.series_data = {}
        self.episodes_by_season = {}
        self.season_covers = {}
        self.current_season = ""
        self.all_episodes_flat = []
        self._marked_watched_episodes.clear()

        # Arrêt sécurisé du worker de données précédent s'il était en cours d'exécution
        if hasattr(self, "_worker") and self._worker and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except Exception:
                pass
            self._worker.requestInterruption()
            self._worker.wait(200)
            self._worker = None

        if hasattr(self, "_trailer_worker") and self._trailer_worker and self._trailer_worker.isRunning():
            try:
                self._trailer_worker.finished_trailer.disconnect()
            except Exception:
                pass
            self._trailer_worker.requestInterruption()
            self._trailer_worker.wait(200)
            self._trailer_worker = None

        self._current_trailer_id = ""
        self.trailer_badge.setText("")
        self.trailer_badge.hide()
        self.trailer_name_label.setText("")
        self.trailer_name_label.hide()
        self.trailer_section.hide()

        # Réinitialisation immédiate du fond hero pour éviter d'afficher le backdrop de la série précédente
        self._backdrop_pixmap = None
        self.hero_banner.update()

        # Réinitialisation du bouton de lecture
        self.resume_btn.setText("  Lancer la lecture")
        self.resume_btn.setEnabled(False)

        # Nettoyage immédiat des onglets de saisons et de la grille d'épisodes de la série précédente
        while self.seasons_tabs_layout.count():
            item = self.seasons_tabs_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        while self.episodes_grid.count():
            item = self.episodes_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._update_sections_order(video_playing=False)
        self.scroll_area.verticalScrollBar().setValue(0)

        # Métadonnées de base
        self.title_label.setText(channel.name)
        meta = parse_movie_metadata(channel.name, channel.rating, channel.year)

        year_str = meta.get("year", "") or channel.year or "2024"
        self.badge_year.setText(year_str)

        genre_str = channel.group_title.replace("🍿", "").strip() or "Série"
        self.badge_genre.setText(genre_str)

        self.badge_duration.setText("50 min/ep")
        rating_str = meta.get("rating", "") or channel.rating or "8.0"
        self.badge_rating.setText(f"★ {rating_str}")

        self.plot_label.setText("Chargement des informations de la série...")
        self.cast_label.setText("Distribution : —")
        self.director_label.setText("Réalisateur : —")

        self._update_favorite_button()

        # Poster
        self.poster_label.set_added_at(channel.added_at, "series")
        if channel.logo_url:
            cached = ImageLoader.instance().get_cached_image(channel.logo_url)
            if cached:
                self._poster_pixmap = cached
                self.poster_label.setPixmap(cached)
            else:
                self.poster_label.clear()
                ImageLoader.instance().image_loaded.connect(self._on_poster_loaded)
                ImageLoader.instance().request_image_priority(channel.logo_url)
        else:
            self.poster_label.clear()

        # Clé de cache (playlist_id, stream_id)
        cache_key = (channel.playlist_id, str(channel.stream_id))
        cached_data = _SERIES_INFO_CACHE.get(cache_key)
        if not cached_data and self.db:
            cached_data = self.db.get_series_info(channel.playlist_id, str(channel.stream_id))
            if cached_data:
                _SERIES_INFO_CACHE[cache_key] = cached_data

        if cached_data:
            # Rendu instantané (0 ms !) depuis le cache mémoire ou la base de données SQLite
            self._on_series_data_loaded(cached_data)
        else:
            # Affichage d'un placeholder de chargement si aucune donnée n'est encore enregistrée
            loading_lbl = QLabel("Chargement des saisons et épisodes...")
            loading_lbl.setStyleSheet("color: #64748b; font-size: 13px; margin: 20px 0;")
            self.episodes_grid.addWidget(loading_lbl, 0, 0)

        # Récupération asynchrone des données fraîches Xtream (toujours lancée en arrière-plan)
        if self.playlist and self.playlist.playlist_type == "xtream" and channel.stream_id:
            client = XtreamClient(
                server_url=self.playlist.server_url,
                username=self.playlist.username,
                password=self.playlist.password
            )
            self._worker = SeriesInfoWorker(client, channel.stream_id, self)
            self._worker.finished.connect(lambda data, ck=cache_key: self._handle_series_data_loaded(ck, data))
            self._worker.error.connect(self._on_series_data_error)
            self._worker.start()

    def _handle_series_data_loaded(self, cache_key: Tuple[int, str], data: Dict[str, Any]):
        """Met en cache SQLite et mémoire les données reçues et rafraîchit l'affichage si la série est toujours sélectionnée."""
        if not isinstance(data, dict):
            return

        # 1. Sauvegarde persistante en base SQLite
        if self.db and cache_key[0] and cache_key[1]:
            self.db.save_series_info(cache_key[0], cache_key[1], data)

        # 2. Mise à jour du cache RAM
        if len(_SERIES_INFO_CACHE) >= _MAX_SERIES_INFO_CACHE:
            first_key = next(iter(_SERIES_INFO_CACHE))
            _SERIES_INFO_CACHE.pop(first_key, None)
        _SERIES_INFO_CACHE[cache_key] = data

        # 3. Rafraîchissement de l'affichage si l'utilisateur est toujours sur cette série
        if self.channel and (self.channel.playlist_id, str(self.channel.stream_id)) == cache_key:
            # Éviter tout recalcul/reconstruction si les données n'ont pas changé (ex: série ancienne sans nouvel épisode)
            if hasattr(self, "series_data") and self.series_data == data:
                return

            prev_season = getattr(self, "current_season", "")
            self._on_series_data_loaded(data)
            if prev_season and prev_season in self.episodes_by_season:
                self._on_season_tab_clicked(prev_season)

    def _on_poster_loaded(self, url: str, pixmap: QPixmap):
        if self.channel and url == self.channel.logo_url:
            self._poster_pixmap = pixmap
            self.poster_label.setPixmap(pixmap)

    def _on_backdrop_loaded(self, url: str, pixmap: QPixmap):
        self._backdrop_pixmap = pixmap
        self.hero_banner.update()

    def _on_series_data_loaded(self, data: Dict[str, Any]):
        self.series_data = data
        info = data.get("info", {})

        if isinstance(info, dict):
            cover = info.get("cover", "") or info.get("movie_image", "") or info.get("cover_big", "")
            if cover and cover.startswith("http"):
                if not self.channel.logo_url or self._poster_pixmap is None or self._poster_pixmap.isNull():
                    self.channel.logo_url = cover
                    if self.channel.id:
                        self.db.update_channel_logo(self.channel.id, cover)
                    ImageLoader.instance().request_image_priority(cover)

            plot = info.get("plot", "") or info.get("description", "")
            if plot:
                self.plot_label.setText(plot)

            genre = info.get("genre", "")
            if genre:
                self.badge_genre.setText(genre)

            year = info.get("releaseDate", "") or info.get("year", "")
            if year:
                self.badge_year.setText(year[:4] if len(year) >= 4 else year)

            run_time = info.get("episode_run_time", "")
            if run_time:
                self.badge_duration.setText(f"{run_time} min/ep")

            rating = info.get("rating", "") or info.get("rating_5based", "")
            if rating:
                self.badge_rating.setText(f"★ {rating}")

            def _make_links(names_str: str) -> str:
                if not names_str:
                    return "—"
                parts = [p.strip() for p in re.split(r"[,;/]+", names_str) if p.strip()]
                return ", ".join(
                    f'<a href="artist:{p}" style="color: #38bdf8; text-decoration: none;">{p}</a>'
                    for p in parts
                )

            cast = info.get("cast", "") or info.get("actors", "")
            if cast:
                self.cast_label.setText(f"Distribution : {_make_links(cast)}")

            director = info.get("director", "") or info.get("creators", "")
            if director:
                self.director_label.setText(f"Réalisateur : {_make_links(director)}")

            # Image de fond backdrop
            backdrop_url = info.get("backdrop_path", "") or info.get("fanart", "")
            if isinstance(backdrop_url, list) and backdrop_url:
                backdrop_url = backdrop_url[0]
            if backdrop_url:
                cached = ImageLoader.instance().get_cached_image(backdrop_url)
                if cached:
                    self._backdrop_pixmap = cached
                    self.hero_banner.update()
                else:
                    ImageLoader.instance().image_loaded.connect(self._on_backdrop_loaded)
                    ImageLoader.instance().request_image(backdrop_url)

        # Extraction des affiches de saisons (cover / cover_big)
        self.season_covers = {}
        seasons_raw = data.get("seasons", [])
        if isinstance(seasons_raw, list):
            for s in seasons_raw:
                if isinstance(s, dict):
                    s_num = str(s.get("season_number", ""))
                    cov = s.get("cover_big") or s.get("cover") or ""
                    if cov:
                        self.season_covers[s_num] = str(cov).strip()
        elif isinstance(seasons_raw, dict):
            for s_k, s in seasons_raw.items():
                if isinstance(s, dict):
                    s_num = str(s.get("season_number", s_k))
                    cov = s.get("cover_big") or s.get("cover") or ""
                    if cov:
                        self.season_covers[s_num] = str(cov).strip()

        # Extraction des saisons
        episodes_raw = data.get("episodes", {})
        self.episodes_by_season = {}
        self.all_episodes_flat = []

        if isinstance(episodes_raw, dict):
            for season_key, ep_list in episodes_raw.items():
                items = ep_list if isinstance(ep_list, list) else (list(ep_list.values()) if isinstance(ep_list, dict) else [])
                s_str = str(season_key)
                if s_str not in self.episodes_by_season:
                    self.episodes_by_season[s_str] = []
                for ep in items:
                    if isinstance(ep, dict):
                        ep["_season"] = s_str
                        self.episodes_by_season[s_str].append(ep)
                        self.all_episodes_flat.append(ep)
        elif isinstance(episodes_raw, list):
            for idx, item in enumerate(episodes_raw):
                if isinstance(item, list):
                    # Format liste de listes (ex: Euphoria où les saisons démarrent à 0 et PHP produit un tableau JSON imbriqué)
                    for ep in item:
                        if isinstance(ep, dict):
                            s_val = ep.get("season")
                            s_str = str(s_val) if s_val is not None and str(s_val).strip() != "" else str(idx)
                            if s_str not in self.episodes_by_season:
                                self.episodes_by_season[s_str] = []
                            ep["_season"] = s_str
                            self.episodes_by_season[s_str].append(ep)
                            self.all_episodes_flat.append(ep)
                elif isinstance(item, dict):
                    # Format liste plate d'épisodes
                    s_val = item.get("season")
                    s_str = str(s_val) if s_val is not None and str(s_val).strip() != "" else "1"
                    if s_str not in self.episodes_by_season:
                        self.episodes_by_season[s_str] = []
                    item["_season"] = s_str
                    self.episodes_by_season[s_str].append(item)
                    self.all_episodes_flat.append(item)

        # Trier all_episodes_flat chronologiquement par saison et numéro d'épisode
        def _ep_sort_key(ep):
            s_val = ep.get("_season", 1)
            e_val = ep.get("episode_num", 1)
            try:
                s_int = int(s_val)
            except (ValueError, TypeError):
                s_int = 999
            try:
                e_int = int(e_val)
            except (ValueError, TypeError):
                e_int = 999
            return (s_int, e_int)

        self.all_episodes_flat.sort(key=_ep_sort_key)

        self._populate_season_tabs()
        self._update_resume_button_text()

        # Bande-annonce YouTube (avec recherche automatique dans la langue préférée)
        orig_trailer = str(info.get("youtube_trailer", "") or "").strip()
        tmdb_id = str(info.get("tmdb_id", "") or info.get("tmdb", "") or "").strip()
        year = str(self.channel.year or info.get("releaseDate", "") or info.get("year", "") or "") if self.channel else ""
        title = self.channel.name if self.channel else ""

        if orig_trailer:
            self._setup_trailer(orig_trailer, name="Bande-annonce d'origine", badge="VO")

        pref_lang = self.db.get_settings().preferred_audio_lang
        self._trailer_worker = _SeriesTrailerLookupWorker(
            tmdb_id=tmdb_id,
            title=title,
            year=year,
            preferred_lang=pref_lang,
            orig_trailer=orig_trailer,
            parent=None,
        )
        self._trailer_worker.finished_trailer.connect(self._on_trailer_resolved)
        self._trailer_worker.start()

    def _on_trailer_resolved(self, data: dict):
        if not data or not data.get("key"):
            if not getattr(self, "_current_trailer_id", None):
                self.trailer_section.hide()
            return

        key = str(data.get("key", "")).strip()
        name = str(data.get("name", "Bande-annonce")).strip()
        badge = str(data.get("badge", "")).strip()
        self._setup_trailer(key, name=name, badge=badge)

    def _setup_trailer(self, trailer_id: str, name: str = "", badge: str = ""):
        clean_id = str(trailer_id or "").strip()
        if "v=" in clean_id:
            clean_id = clean_id.split("v=")[1].split("&")[0]
        elif "youtu.be/" in clean_id:
            clean_id = clean_id.split("youtu.be/")[1].split("?")[0]
        elif clean_id.startswith("http://") or clean_id.startswith("https://"):
            clean_id = clean_id.rstrip("/").split("/")[-1]

        if not clean_id:
            self.trailer_section.hide()
            return

        self._current_trailer_id = clean_id

        if badge:
            self.trailer_badge.setText(badge)
            self.trailer_badge.show()
        else:
            self.trailer_badge.hide()

        if name:
            self.trailer_name_label.setText(name)
            self.trailer_name_label.show()
        else:
            self.trailer_name_label.hide()

        thumb_url = f"https://img.youtube.com/vi/{clean_id}/hqdefault.jpg"
        self.trailer_thumb_label.clear()
        cached = ImageLoader.instance().get_cached_image(thumb_url)
        if cached:
            self.trailer_thumb_label.setPixmap(cached)
        else:
            ImageLoader.instance().image_loaded.connect(self._on_trailer_thumb_loaded)
            ImageLoader.instance().request_image_priority(thumb_url)

        if not getattr(self, "_is_video_playing", False) and not getattr(self, "_video_widget", None):
            self.trailer_section.show()
        else:
            self.trailer_section.hide()

    def _on_trailer_thumb_loaded(self, url: str, pixmap: QPixmap):
        if hasattr(self, "_current_trailer_id") and self._current_trailer_id:
            expected = f"https://img.youtube.com/vi/{self._current_trailer_id}/hqdefault.jpg"
            if url == expected:
                self.trailer_thumb_label.setPixmap(pixmap)

    def _on_play_trailer_clicked(self):
        if hasattr(self, "_current_trailer_id") and self._current_trailer_id:
            title = self.channel.name if self.channel else "Série"
            url = f"https://www.youtube.com/watch?v={self._current_trailer_id}"
            self.play_trailer_requested.emit(title, url)

    def _open_trailer_url(self):
        if hasattr(self, "_current_trailer_id") and self._current_trailer_id:
            import webbrowser
            webbrowser.open(f"https://www.youtube.com/watch?v={self._current_trailer_id}")

    def _on_series_data_error(self, err: str):
        # Si des épisodes ont déjà été chargés depuis la base de données, conserver l'affichage existant
        if self.all_episodes_flat:
            print(f"[SeriesDetailsView] Erreur mise à jour arrière-plan ({err}), conservation des épisodes en cache.")
            return

        self.plot_label.setText("Impossible de charger les détails de cette série.")
        while self.episodes_grid.count():
            item = self.episodes_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        err_lbl = QLabel("Impossible de charger les épisodes de cette série.")
        err_lbl.setStyleSheet("color: #ef4444; font-size: 13px; margin: 20px 0;")
        self.episodes_grid.addWidget(err_lbl, 0, 0)

    def _paint_hero_backdrop(self, event):
        painter = QPainter(self.hero_banner)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.hero_banner.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Hauteur calculée pour ne pas être plus haut que la description / affiche + petite marge
        poster_h = self.poster_label.height() if hasattr(self, "poster_label") else 240
        default_content_h = poster_h + 36  # 240 + 36 = 276px
        if hasattr(self, "poster_label") and self.poster_label.isVisible():
            p_geom = self.poster_label.geometry()
            if p_geom.bottom() > 0:
                btn_b = self.resume_btn.geometry().bottom() if hasattr(self, "resume_btn") and self.resume_btn.isVisible() else 0
                default_content_h = max(p_geom.bottom() + 16, btn_b + 16, default_content_h)

        bg_height = min(rect.height(), default_content_h)
        if bg_height <= 0:
            return

        bg_rect = QRectF(0, 0, rect.width(), bg_height)

        # Buffer ARGB pour composer le fond avec dégradé de transparence verticale
        buffer = QImage(QSize(rect.width(), int(bg_height)), QImage.Format.Format_ARGB32_Premultiplied)
        buffer.fill(Qt.GlobalColor.transparent)

        b_painter = QPainter(buffer)
        b_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        b_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        clip_path = QPainterPath()
        clip_path.addRoundedRect(bg_rect, 14.0, 14.0)
        b_painter.setClipPath(clip_path)

        # Si une vidéo est en cours de diffusion, ne pas afficher l'image de fond sous la description
        if not getattr(self, "_is_video_playing", False) and self._backdrop_pixmap and not self._backdrop_pixmap.isNull():
            scaled = self._backdrop_pixmap.scaled(
                QSize(rect.width(), int(bg_height)),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            dx = (scaled.width() - rect.width()) // 2
            dy = (scaled.height() - int(bg_height)) // 2
            b_painter.drawPixmap(0, 0, scaled, dx, dy, rect.width(), int(bg_height))

            # Dégradé horizontal sombre à gauche pour assurer la lisibilité des textes
            h_grad = QLinearGradient(0, 0, rect.width(), 0)
            h_grad.setColorAt(0.0, QColor(13, 17, 26, 245))
            h_grad.setColorAt(0.40, QColor(13, 17, 26, 215))
            h_grad.setColorAt(0.70, QColor(13, 17, 26, 140))
            h_grad.setColorAt(1.0, QColor(13, 17, 26, 60))
            b_painter.fillRect(bg_rect, h_grad)

            # Voile d'ambiance bleuté
            b_painter.fillRect(bg_rect, QColor(13, 17, 26, 80))
        else:
            # Fond sobre sans image (pendant la vidéo ou par défaut)
            b_painter.fillRect(bg_rect, QColor(19, 25, 38, 230))

        # Masque de dégradé de transparence vertical : le bas est le plus transparent et rejoint la couleur du fond
        b_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        alpha_grad = QLinearGradient(0, 0, 0, bg_height)
        alpha_grad.setColorAt(0.0, QColor(0, 0, 0, 255))
        alpha_grad.setColorAt(0.35, QColor(0, 0, 0, 235))
        alpha_grad.setColorAt(0.70, QColor(0, 0, 0, 130))
        alpha_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        b_painter.fillRect(bg_rect, alpha_grad)
        b_painter.end()

        # Dessiner le résultat sur la bannière
        painter.drawImage(0, 0, buffer)

    # ------------------ SAISONS ET ÉPISODES ------------------

    def _get_episode_progress(self, ep: Dict[str, Any], progress_map: Dict[Any, Tuple[float, float]]) -> Tuple[float, bool]:
        """Retourne (prog_ratio, is_watched) pour un épisode donné de manière fiable."""
        ep_id = str(ep.get("id", ""))
        ep_url = str(ep.get("url", ""))

        for key, (pos, dur) in progress_map.items():
            if not isinstance(key, str):
                continue
            # Correspondance par URL contenant /{ep_id}. ou égale à ep_url
            if (ep_id and f"/{ep_id}." in key) or (ep_url and key == ep_url) or (ep_id and key.endswith(f"/{ep_id}")):
                if dur > 0:
                    ratio = min(1.0, max(0.0, pos / dur))
                    is_w = bool(ratio >= 0.90 or (dur - pos) <= 60)
                    return (1.0 if is_w else ratio, is_w)
                return (0.0, False)

        return (0.0, False)

    def _is_season_completed(self, season_num: str, progress_map: dict) -> bool:
        """Vérifie si tous les épisodes d'une saison ont été visionnés à >= 90%."""
        episodes = self.episodes_by_season.get(str(season_num), [])
        if not episodes:
            return False
        watched_set = getattr(self, "_marked_watched_episodes", set())
        for ep in episodes:
            ep_id = str(ep.get("id", ""))
            if ep_id and ep_id in watched_set:
                continue
            _, is_w = self._get_episode_progress(ep, progress_map)
            if not is_w:
                return False
        return True

    def _populate_season_tabs(self):
        # Nettoyage des onglets
        while self.seasons_tabs_layout.count():
            item = self.seasons_tabs_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        sorted_seasons = sorted(self.episodes_by_season.keys(), key=lambda k: int(k) if k.isdigit() else 999)
        if not sorted_seasons:
            sorted_seasons = ["1"]

        progress_map = self.db.get_all_playback_progress_map()

        if not self.current_season or self.current_season not in sorted_seasons:
            # Sélectionner intelligemment la saison de l'épisode en cours de visionnage ou à reprendre
            target_season = ""
            if getattr(self, "_current_playing_episode_id", ""):
                target_season = self.get_season_for_episode(self._current_playing_episode_id) or ""
            if not target_season:
                target_ep, _ = self._get_resume_or_next_episode(progress_map)
                target_season = str(target_ep.get("_season", "")) if target_ep else ""
            if target_season and target_season in sorted_seasons:
                self.current_season = target_season
            else:
                self.current_season = "1" if "1" in sorted_seasons else sorted_seasons[0]

        if len(sorted_seasons) > 10:
            combo = QComboBox()
            combo.setObjectName("seasonSelectorCombo")
            combo.setCursor(Qt.CursorShape.PointingHandCursor)
            combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            combo.setStyleSheet("""
                QComboBox#seasonSelectorCombo {
                    background-color: #1e293b;
                    color: #f1f5f9;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-size: 13px;
                    font-weight: 600;
                    min-width: 180px;
                }
                QComboBox#seasonSelectorCombo:hover {
                    background-color: #2a374d;
                    border-color: #475569;
                }
                QComboBox#seasonSelectorCombo::drop-down {
                    border: none;
                    width: 24px;
                }
                QComboBox#seasonSelectorCombo QAbstractItemView {
                    background-color: #1e293b;
                    color: #f1f5f9;
                    selection-background-color: #3b82f6;
                    selection-color: #ffffff;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
            selected_idx = 0
            for idx, s in enumerate(sorted_seasons):
                is_completed = self._is_season_completed(s, progress_map)
                if is_completed:
                    combo.addItem(get_icon("check_circle", color="#10b981"), f"Saison {s}  ✓", userData=s)
                else:
                    combo.addItem(f"Saison {s}", userData=s)
                if s == self.current_season:
                    selected_idx = idx

            combo.blockSignals(True)
            combo.setCurrentIndex(selected_idx)
            combo.blockSignals(False)

            combo.currentIndexChanged.connect(self._on_season_combo_changed)
            self.seasons_tabs_layout.addWidget(combo)
            self.seasons_tabs_layout.addStretch()
        else:
            for s in sorted_seasons:
                btn = QPushButton(f"Saison {s}")
                btn.setProperty("season_num", s)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

                is_completed = self._is_season_completed(s, progress_map)
                if is_completed:
                    btn.setIcon(get_icon("check_circle", color="#10b981"))
                    btn.setIconSize(QSize(16, 16))

                self._style_season_button(btn, is_active=(s == self.current_season), is_completed=is_completed)
                btn.clicked.connect(lambda checked, s_num=s: self._on_season_tab_clicked(s_num))
                self.seasons_tabs_layout.addWidget(btn)

            self.seasons_tabs_layout.addStretch()

        self._populate_episodes_grid()

    def _on_season_combo_changed(self, index: int):
        for i in range(self.seasons_tabs_layout.count()):
            item = self.seasons_tabs_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QComboBox):
                s_val = widget.itemData(index)
                if s_val:
                    self.current_season = str(s_val)
                    self._populate_episodes_grid()
                break

    def _style_season_button(self, btn: QPushButton, is_active: bool, is_completed: bool = False):
        if is_active:
            border = "border: 2px solid #10b981;" if is_completed else "border: none;"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #ffffff;
                    color: #0f172a;
                    {border}
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 700;
                }}
            """)
        else:
            border = "border: 1px solid #10b981; color: #f1f5f9;" if is_completed else "border: 1px solid #334155; color: #94a3b8;"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1e293b;
                    {border}
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #2a374d;
                    color: #ffffff;
                }}
            """)

    def get_season_for_episode(self, episode_id: str) -> Optional[str]:
        """Retourne le numéro de saison (str) auquel appartient l'épisode donné."""
        if not episode_id or not hasattr(self, "episodes_by_season"):
            return None
        ep_id_str = str(episode_id).strip()
        for s_key, ep_list in self.episodes_by_season.items():
            for ep in ep_list:
                if (
                    str(ep.get("id", "")).strip() == ep_id_str
                    or str(ep.get("stream_id", "")).strip() == ep_id_str
                ):
                    return str(s_key)
        return None

    def _update_season_tab_buttons(self):
        """Met à jour les icônes et styles des boutons d'onglets de saisons sans recréer les widgets."""
        if not hasattr(self, "seasons_tabs_layout"):
            return
        progress_map = self.db.get_all_playback_progress_map() if hasattr(self, "db") and self.db else {}
        for i in range(self.seasons_tabs_layout.count()):
            item = self.seasons_tabs_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QPushButton) and widget.property("season_num") is not None:
                s_val = str(widget.property("season_num"))
                is_comp = self._is_season_completed(s_val, progress_map)
                if is_comp:
                    widget.setIcon(get_icon("check_circle", color="#10b981"))
                    widget.setIconSize(QSize(16, 16))
                else:
                    widget.setIcon(QIcon())
                self._style_season_button(widget, is_active=(s_val == str(self.current_season)), is_completed=is_comp)
            elif isinstance(widget, QComboBox):
                widget.blockSignals(True)
                for idx in range(widget.count()):
                    s_val = str(widget.itemData(idx))
                    is_comp = self._is_season_completed(s_val, progress_map)
                    if is_comp:
                        widget.setItemIcon(idx, get_icon("check_circle", color="#10b981"))
                        widget.setItemText(idx, f"Saison {s_val}  ✓")
                    else:
                        widget.setItemIcon(idx, QIcon())
                        widget.setItemText(idx, f"Saison {s_val}")
                    if s_val == str(self.current_season):
                        widget.setCurrentIndex(idx)
                widget.blockSignals(False)

    def select_season(self, season_num: str):
        """Sélectionne l'onglet de la saison indiquée et met à jour l'affichage des épisodes."""
        season_str = str(season_num)
        if hasattr(self, "episodes_by_season") and season_str not in self.episodes_by_season:
            return

        self.current_season = season_str
        self._update_season_tab_buttons()
        self._populate_episodes_grid()
        if getattr(self, "_video_widget", None) and hasattr(self, "scroll_area"):
            self.scroll_area.verticalScrollBar().setValue(0)

    def _on_season_tab_clicked(self, season_num: str):
        self.select_season(season_num)

    def _populate_episodes_grid(self):
        # Nettoyage de la grille
        while self.episodes_grid.count():
            item = self.episodes_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        episodes = self.episodes_by_season.get(self.current_season, [])
        if not episodes:
            empty_lbl = QLabel("Aucun épisode disponible dans cette saison.")
            empty_lbl.setStyleSheet("color: #64748b; font-size: 13px; margin: 20px 0;")
            self.episodes_grid.addWidget(empty_lbl, 0, 0)
            return

        # Calcul réactif du nombre de colonnes selon la largeur réelle de la fenêtre
        viewport_w = self.scroll_area.viewport().width()
        available_w = max(EpisodeCardWidget.CARD_WIDTH, viewport_w - 56)
        card_total_w = EpisodeCardWidget.CARD_WIDTH + 16
        col_count = max(1, available_w // card_total_w)
        self._current_col_count = col_count

        progress_map = self.db.get_all_playback_progress_map()

        # Fallbacks ordonnés pour les vignettes :
        # 1. Backdrop 16:9 paysage de la série (même ratio panoramique 16:9 que les cartes d'épisodes)
        # 2. Affiche spécifique de la saison
        # 3. Affiche / logo principal de la série
        info = self.series_data.get("info", {}) if isinstance(self.series_data, dict) else {}
        backdrop = info.get("backdrop_path", "") or info.get("fanart", "")
        if isinstance(backdrop, list) and backdrop:
            backdrop = backdrop[0]
        season_cover = self.season_covers.get(str(self.current_season), "")
        series_cover = (self.channel.logo_url if self.channel else "") or info.get("cover", "") or info.get("movie_image", "")

        fallback_urls = []
        if backdrop:
            fallback_urls.append(str(backdrop).strip())
        if season_cover and season_cover not in fallback_urls:
            fallback_urls.append(str(season_cover).strip())
        if series_cover and series_cover not in fallback_urls:
            fallback_urls.append(str(series_cover).strip())

        for idx, ep in enumerate(episodes):
            row = idx // col_count
            col = idx % col_count

            ep_id = str(ep.get("id", ""))
            prog_ratio, is_w = self._get_episode_progress(ep, progress_map)

            is_cur_playing = bool(self._video_widget and str(ep_id) == str(getattr(self, "_current_playing_episode_id", "")))
            card = EpisodeCardWidget(
                episode=ep,
                season_num=self.current_season,
                is_watched=is_w,
                progress_ratio=prog_ratio,
                is_current_playing=is_cur_playing,
                fallback_urls=fallback_urls,
                parent=self.seasons_container
            )
            card.clicked.connect(self._on_episode_card_clicked)
            card.toggle_watched_clicked.connect(self._on_episode_toggle_watched)
            self.episodes_grid.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def _on_episode_toggle_watched(self, ep_dict: Dict[str, Any], season_num: str):
        """Bascule manuellement le statut d'un épisode entre 'lu / terminé (100%)' et 'non vu (0%)'."""
        if not self.playlist or not self.channel:
            return

        client = XtreamClient(
            server_url=self.playlist.server_url,
            username=self.playlist.username,
            password=self.playlist.password
        )

        ep_id = str(ep_dict.get("id", ""))
        curr_ext = str(ep_dict.get("container_extension", "mp4")).strip(".") or "mp4"
        stream_url = client.get_episode_stream_url(ep_id, container_extension=curr_ext) if self.playlist.playlist_type == "xtream" else str(ep_dict.get("url", ""))

        info = ep_dict.get("info", {})
        dur = float(info.get("duration_secs", 0)) if info.get("duration_secs") else 3600.0

        # Vérifier si l'épisode est déjà considéré comme vu
        progress_map = self.db.get_all_playback_progress_map()
        _, is_already_watched = self._get_episode_progress(ep_dict, progress_map)

        ch_id = self.channel.id or (int(ep_id) if ep_id.isdigit() else 0)
        if is_already_watched:
            # Réinitialiser : supprimer uniquement la progression de cet épisode spécifique
            self.db.clear_playback_progress(stream_url=stream_url)
            self._marked_watched_episodes.discard(str(ep_id))
        else:
            # Valider : forcer le statut terminé à 100%
            ep_num = ep_dict.get("episode_num", 1)
            raw_title = ep_dict.get("title", f"Épisode {ep_num}").strip()
            full_title = f"{self.channel.name} — S{int(season_num):02d}E{int(ep_num):02d} : {raw_title}"
            self.db.save_playback_progress(
                channel_id=ch_id,
                stream_url=stream_url,
                channel_name=full_title,
                position=dur,
                duration=dur
            )
            self._marked_watched_episodes.add(str(ep_id))

        # Mettre à jour l'interface instantanément (vignettes, coche sur l'onglet saison, bouton reprendre)
        self.refresh_progress()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_video_geometry()
        if self._video_widget and self._video_widget.isVisible():
            self._video_widget._sync_geometry()
        self._reposition_episode_cards()

    def eventFilter(self, watched, event: QEvent) -> bool:
        if hasattr(self, "scroll_area") and watched == self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            self._update_video_geometry()
            if self._video_widget and self._video_widget.isVisible():
                self._video_widget._sync_geometry()
            self._reposition_episode_cards()
        return super().eventFilter(watched, event)

    def _reposition_episode_cards(self):
        """Réorganise instantanément les cartes d'épisodes pour s'adapter à la largeur sans déborder à droite."""
        if not hasattr(self, "episodes_grid") or not hasattr(self, "scroll_area"):
            return

        cards = []
        for i in range(self.episodes_grid.count()):
            item = self.episodes_grid.itemAt(i)
            w = item.widget() if item else None
            if isinstance(w, EpisodeCardWidget):
                cards.append(w)

        if not cards:
            return

        viewport_w = self.scroll_area.viewport().width()
        available_w = max(EpisodeCardWidget.CARD_WIDTH, viewport_w - 56)
        card_total_w = EpisodeCardWidget.CARD_WIDTH + 16
        col_count = max(1, available_w // card_total_w)

        if getattr(self, "_current_col_count", 0) == col_count:
            return
        self._current_col_count = col_count

        for card in cards:
            self.episodes_grid.removeWidget(card)

        for idx, card in enumerate(cards):
            row = idx // col_count
            col = idx % col_count
            self.episodes_grid.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def refresh_progress(self):
        """Met à jour l'état de visionnage des onglets de saisons, des épisodes et du bouton Reprendre."""
        progress_map = self.db.get_all_playback_progress_map()
        if hasattr(self, "episodes_grid"):
            for i in range(self.episodes_grid.count()):
                item = self.episodes_grid.itemAt(i)
                w = item.widget() if item else None
                if isinstance(w, EpisodeCardWidget):
                    prog_ratio, is_w = self._get_episode_progress(w.episode, progress_map)
                    w.set_progress_ratio(prog_ratio, is_w)
        self._update_season_tab_buttons()
        self._update_resume_button_text()

    def update_playback_progress(self, episode_id: str, position: float, duration: float, stream_url: str = ""):
        """Met à jour en temps réel la barre de progression sous la vignette de l'épisode en cours."""
        if not hasattr(self, "episodes_grid") or duration <= 0:
            return
        ratio = max(0.0, min(1.0, position / duration))
        is_watched = bool(ratio >= 0.90 or (duration - position) <= 60)
        matched_card = None
        for i in range(self.episodes_grid.count()):
            item = self.episodes_grid.itemAt(i)
            w = item.widget() if item else None
            if isinstance(w, EpisodeCardWidget):
                w_id = str(w.episode.get("id", ""))
                w_url = str(w.episode.get("url", ""))
                if episode_id and (w_id == str(episode_id) or (stream_url and f"/{w_id}." in stream_url) or (stream_url and stream_url.endswith(f"/{w_id}"))):
                    matched_card = w
                    break
                elif stream_url and (w_url == stream_url or (w_id and f"/{w_id}." in stream_url)):
                    matched_card = w
                    break

        if matched_card:
            target_ratio = 1.0 if is_watched else ratio
            if abs(matched_card.progress_ratio - target_ratio) >= 0.002 or matched_card.is_watched != is_watched:
                matched_card.set_progress_ratio(target_ratio, is_watched)
            if is_watched:
                if not hasattr(self, "_marked_watched_episodes"):
                    self._marked_watched_episodes = set()
                ep_key = str(matched_card.episode.get("id", "") or episode_id)
                if ep_key and ep_key not in self._marked_watched_episodes:
                    self._marked_watched_episodes.add(ep_key)
                    self._update_season_tab_buttons()
                    self._update_resume_button_text()

    # ------------------ LECTURE ------------------

    def _get_first_episode(self) -> Optional[Dict[str, Any]]:
        """Retourne le premier épisode de la série (priorité Saison 1, sinon premier disponible)."""
        if not self.all_episodes_flat:
            return None
        for ep in self.all_episodes_flat:
            try:
                if int(ep.get("_season", 1)) == 1:
                    return ep
            except (ValueError, TypeError):
                pass
        return self.all_episodes_flat[0]

    def _get_resume_or_next_episode(self, progress_map: dict) -> Tuple[Optional[Dict[str, Any]], str]:
        """Détermine l'épisode cible et le type d'action pour le bouton principal de lecture.
        Retourne (target_ep, action_type) avec action_type parmi :
        - 'resume' : un épisode est en cours de lecture partielle (reprise)
        - 'continue' : des épisodes précédents sont terminés/validés (prochain épisode non vu)
        - 'restart' : tous les épisodes sont vus (recommencer la série)
        - 'start' : aucun épisode n'a encore été vu
        - 'none' : aucun épisode
        """
        if not self.all_episodes_flat:
            return None, "none"

        active_indices = []
        for idx, ep in enumerate(self.all_episodes_flat):
            prog_ratio, is_w = self._get_episode_progress(ep, progress_map)
            if is_w or prog_ratio > 0.0:
                active_indices.append(idx)

        if not active_indices:
            return self._get_first_episode(), "start"

        # Dernier épisode ayant eu une activité
        last_active_idx = max(active_indices)
        last_active_ep = self.all_episodes_flat[last_active_idx]
        prog_ratio, is_w = self._get_episode_progress(last_active_ep, progress_map)

        if 0.0 < prog_ratio < 0.90 and not is_w:
            # Épisode actuellement en cours de visionnage (reprise)
            return last_active_ep, "resume"

        # Le dernier épisode actif est terminé / validé comme vu
        # Trouver le premier épisode non vu suivant
        for idx in range(last_active_idx + 1, len(self.all_episodes_flat)):
            candidate_ep = self.all_episodes_flat[idx]
            c_ratio, c_w = self._get_episode_progress(candidate_ep, progress_map)
            if not c_w and c_ratio < 0.90:
                return candidate_ep, "continue"

        # Si tous les épisodes postérieurs sont vus, chercher s'il reste des épisodes non vus avant
        for idx in range(len(self.all_episodes_flat)):
            candidate_ep = self.all_episodes_flat[idx]
            c_ratio, c_w = self._get_episode_progress(candidate_ep, progress_map)
            if not c_w and c_ratio < 0.90:
                return candidate_ep, "continue"

        # Tous les épisodes de la série sont vus
        return self._get_first_episode(), "restart"

    def _update_resume_button_text(self):
        if self._video_widget:
            self.resume_btn.setText("  Lecture en cours...")
            self.resume_btn.setEnabled(False)
            return
        self.resume_btn.setEnabled(True)
        if not self.all_episodes_flat:
            self.resume_btn.setText("  Lancer la lecture")
            self.resume_btn.setIcon(get_icon("play_arrow", color="#0f172a"))
            return

        progress_map = self.db.get_all_playback_progress_map()
        target_ep, action_type = self._get_resume_or_next_episode(progress_map)

        if action_type in ("resume", "continue") and target_ep:
            s_num = target_ep.get("_season", "1")
            e_num = target_ep.get("episode_num", 1)
            raw_title = target_ep.get("title", f"Épisode {e_num}")
            short_title = raw_title[:28] + "..." if len(raw_title) > 28 else raw_title
            try:
                s_int = int(s_num)
            except (ValueError, TypeError):
                s_int = 1
            try:
                e_int = int(e_num)
            except (ValueError, TypeError):
                e_int = 1
            self.resume_btn.setText(f"  Reprendre : S{s_int:02d}E{e_int:02d} ({short_title})")
            self.resume_btn.setIcon(get_icon("play_arrow", color="#0f172a"))
            self.resume_btn.setToolTip("Reprendre la lecture" if action_type == "resume" else "Lancer l'épisode suivant")
        elif action_type == "restart":
            self.resume_btn.setText("  Recommencer la série")
            self.resume_btn.setIcon(get_icon("replay", color="#0f172a"))
            self.resume_btn.setToolTip("Recommencer la série depuis le premier épisode")
        else:
            self.resume_btn.setText("  Lancer la lecture")
            self.resume_btn.setIcon(get_icon("play_arrow", color="#0f172a"))
            self.resume_btn.setToolTip("Lancer le premier épisode")

    def _on_resume_clicked(self):
        if not self.all_episodes_flat:
            return
        progress_map = self.db.get_all_playback_progress_map()
        target_ep, _ = self._get_resume_or_next_episode(progress_map)
        if not target_ep:
            target_ep = self._get_first_episode() or self.all_episodes_flat[0]

        target_season = str(target_ep.get("_season", self.current_season))
        if target_season != self.current_season:
            self.current_season = target_season
            self._populate_season_tabs()

        self.play_episode(target_ep, target_season)

    def _on_episode_card_clicked(self, ep_dict: Dict[str, Any], season_num: str):
        self.play_episode(ep_dict, season_num)

    def play_episode(self, ep_dict: Dict[str, Any], season_num: str):
        """Lance la lecture d'un épisode.
        Émet play_episode_in_view_requested pour que main_window gère l'affichage embarqué."""
        if not self.playlist or not self.channel:
            return

        if season_num and str(season_num) != str(self.current_season):
            self.select_season(str(season_num))

        client = XtreamClient(
            server_url=self.playlist.server_url,
            username=self.playlist.username,
            password=self.playlist.password
        )

        all_series_episodes: List[Channel] = []
        current_ep_idx = 0
        sorted_seasons = sorted(self.episodes_by_season.keys(), key=lambda x: int(x) if x.isdigit() else 999)

        for s in sorted_seasons:
            for ep in self.episodes_by_season[s]:
                curr_ep_id = str(ep.get("id", ""))
                curr_ext = str(ep.get("container_extension", "mp4")).strip(".") or "mp4"
                curr_ep_num = ep.get("episode_num", 1)
                curr_ep_title = ep.get("title", f"Épisode {curr_ep_num}").strip()
                curr_stream_url = client.get_episode_stream_url(curr_ep_id, container_extension=curr_ext)

                ep_ch = Channel(
                    id=self.channel.id,
                    playlist_id=self.playlist.id or 0,
                    name=f"{self.channel.name} — S{int(s):02d}E{int(curr_ep_num):02d} : {curr_ep_title}",
                    stream_url=curr_stream_url,
                    logo_url=self.channel.logo_url,
                    group_title=self.channel.group_title,
                    stream_type="series",
                    stream_id=curr_ep_id,
                    container_extension=curr_ext
                )

                if str(s) == str(season_num) and str(curr_ep_id) == str(ep_dict.get("id", "")):
                    current_ep_idx = len(all_series_episodes)

                all_series_episodes.append(ep_ch)

        if all_series_episodes:
            selected_ep = all_series_episodes[current_ep_idx]
            prog = self.db.get_playback_progress(stream_url=selected_ep.stream_url)
            start_pos = prog[0] if prog else 0.0
            self.play_episode_requested.emit(selected_ep, all_series_episodes, current_ep_idx, start_pos)

    def attach_video_widget(self, video_widget):
        """Attache le lecteur vidéo au sommet de la vue scrollable."""
        self._video_widget = video_widget
        self.nav_row_widget.hide()
        self.content_layout.insertWidget(0, video_widget)
        video_widget.show()
        self._update_sections_order(video_playing=True)
        self.scroll_area.verticalScrollBar().setValue(0)
        self._update_video_geometry()
        try:
            self.scroll_area.verticalScrollBar().valueChanged.disconnect(self._on_scroll_sync)
        except Exception:
            pass
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_sync)
        self.resume_btn.setText("  Lecture en cours...")
        self.resume_btn.setEnabled(False)

    def detach_video_widget(self, video_widget=None):
        """Détache le lecteur vidéo et réactive la fiche standard."""
        try:
            self.scroll_area.verticalScrollBar().valueChanged.disconnect(self._on_scroll_sync)
        except Exception:
            pass
        vw = video_widget or self._video_widget
        if vw:
            self.content_layout.removeWidget(vw)
            vw.setMinimumHeight(0)
            vw.setMaximumHeight(16777215)
            vw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_widget = None
        self._current_playing_episode_id = ""
        self._update_sections_order(video_playing=False)
        self.nav_row_widget.show()
        self.resume_btn.setEnabled(True)
        self.refresh_progress()
        self.stop_active_workers()

    def stop_active_workers(self):
        """Arrête tous les threads d'arrière-plan actifs de la série."""
        if hasattr(self, "_worker") and self._worker and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except Exception:
                pass
            self._worker.requestInterruption()
            self._worker.wait(100)
            self._worker = None

        if hasattr(self, "_trailer_worker") and self._trailer_worker and self._trailer_worker.isRunning():
            try:
                self._trailer_worker.finished_trailer.disconnect()
            except Exception:
                pass
            self._trailer_worker.requestInterruption()
            self._trailer_worker.wait(100)
            self._trailer_worker = None

    def _on_scroll_sync(self, _=None):
        if self._video_widget and self._video_widget.isVisible():
            self._video_widget._sync_geometry()

    def _update_video_geometry(self):
        if not self._video_widget:
            return

        is_fs = bool(getattr(self, "_is_fullscreen", False))
        if is_fs:
            win = self.window()
            target_h = win.height() if win else self.height()
            if hasattr(self, "scroll_area") and self.scroll_area.viewport():
                target_h = max(target_h, self.scroll_area.viewport().height())
            target_h = max(100, target_h)
            if self._video_widget.height() != target_h:
                self._video_widget.setFixedHeight(target_h)
            if self._video_widget.isVisible():
                self._video_widget._sync_geometry()
            return

        # Largeur réelle disponible pour le contenu dans le viewport
        vp_w = self.scroll_area.viewport().width()
        if vp_w <= 100:
            sb_w = self.scroll_area.verticalScrollBar().width() if self.scroll_area.verticalScrollBar().isVisible() else 0
            vp_w = max(320, self.width() - sb_w)

        margins = self.content_layout.contentsMargins()
        content_w = max(320, vp_w - margins.left() - margins.right())
        h = int(content_w * 9 / 16)

        if self._video_widget.height() != h:
            self._video_widget.setFixedHeight(h)
        if self._video_widget.isVisible():
            self._video_widget._sync_geometry()

    def set_fullscreen(self, is_fs: bool):
        self._is_fullscreen = is_fs
        if is_fs:
            self.nav_row_widget.hide()
            self.details_container.hide()
            if hasattr(self, "hero_banner"):
                self.hero_banner.hide()
            if hasattr(self, "trailer_section"):
                self.trailer_section.hide()
            self.content_layout.setContentsMargins(0, 0, 0, 0)
            self.content_layout.setSpacing(0)
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._update_video_geometry()
        else:
            self.details_container.show()
            if hasattr(self, "hero_banner"):
                self.hero_banner.show()
            if hasattr(self, "_current_trailer_id") and self._current_trailer_id and not getattr(self, "_is_video_playing", False) and not getattr(self, "_video_widget", None):
                self.trailer_section.show()
            self.content_layout.setContentsMargins(28, 20, 28, 30)
            self.content_layout.setSpacing(20)
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._update_video_geometry()

    def set_active_playing_episode(self, episode_id: str):
        """Met en surbrillance l'épisode actuellement en cours de lecture et sélectionne automatiquement son onglet de saison."""
        self._current_playing_episode_id = str(episode_id)
        if not episode_id:
            return

        # Basculer automatiquement sur l'onglet de la saison de l'épisode en cours
        target_season = self.get_season_for_episode(episode_id)
        if target_season and str(target_season) != str(self.current_season):
            self.select_season(target_season)

        if hasattr(self, "episodes_grid"):
            for i in range(self.episodes_grid.count()):
                item = self.episodes_grid.itemAt(i)
                w = item.widget() if item else None
                if isinstance(w, EpisodeCardWidget):
                    is_this = str(w.episode.get("id", "")) == str(episode_id)
                    w.set_current_playing(is_this)

        # Si le lecteur vidéo est actif dans la fiche, s'assurer que la vue reste fermement ancrée en haut
        if getattr(self, "_video_widget", None) and hasattr(self, "scroll_area"):
            self.scroll_area.verticalScrollBar().setValue(0)

    def close_player(self):
        """Ferme et détache le lecteur vidéo."""
        self.detach_video_widget()


    def _on_fav_clicked(self):
        if self.channel:
            new_state = not self.channel.is_favorite
            self.channel.is_favorite = new_state
            self.db.set_favorite(self.channel.id, new_state)
            self._update_favorite_button()
            self.favorite_toggled.emit(self.channel, new_state)

    def _update_favorite_button(self):
        if not self.channel:
            return
        is_fav = bool(self.channel.is_favorite)
        if is_fav:
            self.fav_btn.setText("  Retirer des favoris")
            self.fav_btn.setIcon(get_icon("favorite", color="#f43f5e"))
            self.fav_btn.setIconSize(QSize(18, 18))
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(244, 63, 94, 0.15);
                    color: #f43f5e;
                    border: 1px solid rgba(244, 63, 94, 0.4);
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: rgba(244, 63, 94, 0.25);
                }
            """)
        else:
            self.fav_btn.setText("  Ajouter aux favoris")
            self.fav_btn.setIcon(get_icon("favorite_border", color="#f43f5e"))
            self.fav_btn.setIconSize(QSize(18, 18))
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(30, 41, 59, 0.85);
                    color: #f1f5f9;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #242f44;
                    border-color: #f43f5e;
                    color: #f43f5e;
                }
            """)

    def stop_workers(self):
        """Arrête proprement tous les threads de travail d'arrière-plan."""
        if hasattr(self, "_worker") and self._worker and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except Exception:
                pass
            self._worker.requestInterruption()
            self._worker.wait(200)
            self._worker = None
        if hasattr(self, "_trailer_worker") and self._trailer_worker and self._trailer_worker.isRunning():
            try:
                self._trailer_worker.finished_trailer.disconnect()
            except Exception:
                pass
            self._trailer_worker.requestInterruption()
            self._trailer_worker.wait(200)
            self._trailer_worker = None

    def closeEvent(self, event):
        self.stop_workers()
        super().closeEvent(event)

    def _on_artist_link_clicked(self, link: str):
        if link.startswith("artist:"):
            artist_name = link[len("artist:"):].strip()
            if artist_name:
                self.artist_clicked.emit(artist_name)

