"""
MovieDetailsView — Fiche détaillée et immersive pour un film VOD.
Design moderne et resserré : poster 2:3 à gauche, métadonnées & synopsis & boutons d'actions groupés à droite.
"""

import os
import re
from typing import Optional, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread, QEvent, QRectF
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QLinearGradient, QPen, QPainterPath, QImage
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from core.download_manager import DownloadManager, DownloadTask, get_default_download_dir
from core.image_loader import ImageLoader
from core.models import Channel, Playlist, parse_movie_metadata
from core.xtream_client import XtreamClient
from ui.icons import get_icon
from ui.widgets.rounded_poster import RoundedPosterLabel


def _fmt(seconds: float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m:02d}:{s:02d}"


class _MovieInfoWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, client: XtreamClient, stream_id: str, parent=None):
        super().__init__(parent)
        self.client = client
        self.stream_id = stream_id

    def run(self):
        try:
            data = self.client.get_vod_info(self.stream_id)
            if isinstance(data, dict):
                self.finished.emit(data)
        except Exception:
            pass


class _TMDBReviewsWorker(QThread):
    finished_reviews = pyqtSignal(list)

    def __init__(self, tmdb_id: str, parent=None):
        super().__init__(parent)
        self.tmdb_id = tmdb_id

    def run(self):
        try:
            from core.tmdb_client import get_movie_reviews
            reviews = get_movie_reviews(self.tmdb_id)
            self.finished_reviews.emit(reviews or [])
        except Exception:
            self.finished_reviews.emit([])


class _TrailerLookupWorker(QThread):
    finished_trailer = pyqtSignal(dict)

    def __init__(self, media_type: str, tmdb_id: str, title: str, year: str, preferred_lang: str, orig_trailer: str, parent=None):
        super().__init__(parent)
        self.media_type = media_type
        self.tmdb_id = tmdb_id
        self.title = title
        self.year = year
        self.preferred_lang = preferred_lang
        self.orig_trailer = orig_trailer

    def run(self):
        try:
            from core.tmdb_client import find_best_trailer
            result = find_best_trailer(
                media_type=self.media_type,
                tmdb_id=self.tmdb_id,
                title=self.title,
                year=self.year,
                preferred_audio_lang=self.preferred_lang,
                orig_trailer=self.orig_trailer,
            )
            self.finished_trailer.emit(result or {})
        except Exception:
            self.finished_trailer.emit({})


class MovieDetailsView(QWidget):
    """Fiche film VOD intégrée."""

    back_clicked = pyqtSignal()
    play_requested = pyqtSignal(Channel, float)
    play_trailer_requested = pyqtSignal(str, str)  # (title, trailer_url)
    progress_cleared = pyqtSignal(Channel)
    artist_clicked = pyqtSignal(str)

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.channel: Optional[Channel] = None
        self.playlist: Optional[Playlist] = None
        self.meta: Dict[str, Any] = {}
        self.resume_pos: float = 0.0
        self._worker: Optional[_MovieInfoWorker] = None
        self._download_task: Optional[DownloadTask] = None
        self._video_widget = None
        self._is_fullscreen: bool = False
        self._backdrop_pixmap: Optional[QPixmap] = None
        self._backdrop_url: str = ""
        self._is_video_playing: bool = False
        self._trailer_worker: Optional[_TrailerLookupWorker] = None

        self.setObjectName("movieDetailsView")
        self.setStyleSheet("QWidget#movieDetailsView { background-color: #0d111a; }")
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Zone scrollable
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setCursor(Qt.CursorShape.ArrowCursor)
        self.scroll.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #0d111a; width: 8px; margin: 0; }
            QScrollBar::handle:vertical { background: #334155; min-height: 30px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: #475569; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setCursor(Qt.CursorShape.ArrowCursor)
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(28, 20, 28, 28)
        self.scroll_layout.setSpacing(20)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 1. Navigation supérieure
        self.nav_row_widget = QWidget()
        self.nav_row_widget.setCursor(Qt.CursorShape.ArrowCursor)
        nav_row = QHBoxLayout(self.nav_row_widget)
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(12)

        self.back_btn = QPushButton("‹")
        self.back_btn.setFixedSize(36, 36)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setToolTip("Retour à la galerie de films")
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

        nav_tag = QLabel("FICHE DU FILM")
        nav_tag.setCursor(Qt.CursorShape.ArrowCursor)
        nav_tag.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700; letter-spacing: 1.5px;")
        nav_row.addWidget(nav_tag)
        nav_row.addStretch()
        self.scroll_layout.addWidget(self.nav_row_widget)

        # 2. Carte principale resserrée (Poster + Informations + Actions)
        self.card_frame = QFrame()
        self.card_frame.setObjectName("movieCardFrame")
        self.card_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.card_frame.setStyleSheet("background-color: transparent; border: none;")
        self.card_frame.setCursor(Qt.CursorShape.ArrowCursor)
        self.card_frame.paintEvent = self._paint_card_backdrop
        card_layout = QHBoxLayout(self.card_frame)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(24)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Affiche 2:3 (180x270) avec coins arrondis
        poster_box = QVBoxLayout()
        poster_box.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.poster_label = RoundedPosterLabel(radius=10, border_color="#334155", fallback_icon="movie", parent=self)
        self.poster_label.setFixedSize(180, 270)
        self.poster_label.setCursor(Qt.CursorShape.ArrowCursor)
        poster_box.addWidget(self.poster_label)
        poster_box.addStretch()
        card_layout.addLayout(poster_box)

        # Colonne de contenu
        info_col = QVBoxLayout()
        info_col.setSpacing(10)
        info_col.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Titre
        self.title_label = QLabel("Titre du film")
        self.title_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.title_label.setStyleSheet("color: #f8fafc; font-size: 22px; font-weight: 800; line-height: 1.2;")
        self.title_label.setWordWrap(True)
        info_col.addWidget(self.title_label)

        # Badges
        self.badges_row = QHBoxLayout()
        self.badges_row.setSpacing(8)
        info_col.addLayout(self.badges_row)

        # Détails (Genre, Durée, Réalisateur, Acteurs)
        self.details_label = QLabel()
        self.details_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.details_label.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.5;")
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.details_label.linkActivated.connect(self._on_artist_link_clicked)
        info_col.addWidget(self.details_label)

        # Synopsis
        self.synopsis_label = QLabel("Chargement des informations...")
        self.synopsis_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.synopsis_label.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.5;")
        self.synopsis_label.setWordWrap(True)
        self.synopsis_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        info_col.addWidget(self.synopsis_label)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #1e293b; max-height: 1px;")
        info_col.addWidget(sep)

        # Ligne de boutons d'actions groupés et resserrés
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        actions_row.setContentsMargins(0, 4, 0, 0)

        # Bouton Regarder
        self.play_btn = QPushButton("  Regarder le film")
        self.play_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
        self.play_btn.setIconSize(QSize(18, 18))
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.play_btn.clicked.connect(self._on_play)
        actions_row.addWidget(self.play_btn)

        # Bouton "Du début"
        self.restart_btn = QPushButton("  Du début")
        self.restart_btn.setIcon(get_icon("replay", color="#cbd5e1"))
        self.restart_btn.setIconSize(QSize(15, 15))
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.restart_btn.clicked.connect(self._on_restart)
        self.restart_btn.hide()
        actions_row.addWidget(self.restart_btn)

        # Bouton "Annuler reprise"
        self.clear_resume_btn = QPushButton("  Annuler reprise")
        self.clear_resume_btn.setIcon(get_icon("restart_alt", color="#f87171"))
        self.clear_resume_btn.setIconSize(QSize(15, 15))
        self.clear_resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_resume_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.12);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
            }
        """)
        self.clear_resume_btn.clicked.connect(self._on_clear_resume)
        self.clear_resume_btn.hide()
        actions_row.addWidget(self.clear_resume_btn)

        # Bouton Favoris
        self.fav_btn = QPushButton()
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.clicked.connect(self._toggle_favorite)
        actions_row.addWidget(self.fav_btn)

        # Bouton Télécharger
        self.download_btn = QPushButton("  Télécharger")
        self.download_btn.setIcon(get_icon("file_download", color="#38bdf8"))
        self.download_btn.setIconSize(QSize(16, 16))
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_download_btn()
        self.download_btn.clicked.connect(self._on_download)
        actions_row.addWidget(self.download_btn)

        actions_row.addStretch()
        info_col.addLayout(actions_row)

        card_layout.addLayout(info_col, stretch=1)
        self.scroll_layout.addWidget(self.card_frame)

        # 3. Section Bande-annonce YouTube
        self._current_trailer_id = ""
        self.trailer_section = QFrame()
        self.trailer_section.setObjectName("trailerSection")
        self.trailer_section.setCursor(Qt.CursorShape.ArrowCursor)
        self.trailer_section.setStyleSheet("""
            QFrame#trailerSection {
                background-color: #151b27;
                border: 1px solid #232d3f;
                border-radius: 12px;
            }
        """)
        trailer_layout = QVBoxLayout(self.trailer_section)
        trailer_layout.setContentsMargins(20, 16, 20, 16)
        trailer_layout.setSpacing(12)

        trailer_header = QHBoxLayout()
        trailer_title = QLabel("Bande-annonce")
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
        self.scroll_layout.addWidget(self.trailer_section)

        # 4. Section Avis des spectateurs TMDB (Module test)
        self._tmdb_worker: Optional[_TMDBReviewsWorker] = None
        self.reviews_section = QFrame()
        self.reviews_section.setObjectName("reviewsSection")
        self.reviews_section.setCursor(Qt.CursorShape.ArrowCursor)
        self.reviews_section.setStyleSheet("""
            QFrame#reviewsSection {
                background-color: #151b27;
                border: 1px solid #232d3f;
                border-radius: 12px;
            }
        """)
        self.reviews_layout = QVBoxLayout(self.reviews_section)
        self.reviews_layout.setContentsMargins(20, 16, 20, 16)
        self.reviews_layout.setSpacing(12)

        reviews_header = QHBoxLayout()
        reviews_title = QLabel("Avis des spectateurs (TMDB)")
        reviews_title.setCursor(Qt.CursorShape.ArrowCursor)
        reviews_title.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 700;")
        reviews_header.addWidget(reviews_title)
        reviews_header.addStretch()

        self.reviews_badge = QLabel("")
        self.reviews_badge.setStyleSheet("""
            background-color: rgba(99, 102, 241, 0.15);
            color: #818cf8;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid rgba(99, 102, 241, 0.3);
        """)
        reviews_header.addWidget(self.reviews_badge)
        self.reviews_layout.addLayout(reviews_header)

        self.reviews_list_layout = QVBoxLayout()
        self.reviews_list_layout.setSpacing(10)
        self.reviews_layout.addLayout(self.reviews_list_layout)

        self.reviews_section.hide()
        self.scroll_layout.addWidget(self.reviews_section)

        self.scroll_layout.addStretch()

        self.scroll.setWidget(self.scroll_content)
        self.scroll.viewport().installEventFilter(self)
        root.addWidget(self.scroll)

    def load_movie(self, channel: Channel):
        """Charge et affiche la fiche du film sélectionné."""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if hasattr(self, "scroll") and self.scroll.viewport():
            self.scroll.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.channel = channel
        self.playlist = self.db.get_playlist(channel.playlist_id)
        self.meta = parse_movie_metadata(channel.name, channel.rating, channel.year)

        self.refresh_progress()
        self.stop_active_workers()

        self._current_trailer_id = ""
        self.trailer_badge.setText("")
        self.trailer_badge.hide()
        self.trailer_name_label.setText("")
        self.trailer_name_label.hide()
        self.trailer_section.hide()
        self.reviews_section.hide()
        while self.reviews_list_layout.count():
            item = self.reviews_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._backdrop_pixmap = None
        self._backdrop_url = ""
        self._is_video_playing = False
        self.card_frame.update()

        self.title_label.setText(channel.name)
        self._populate_badges()
        self.details_label.setText("")
        self.synopsis_label.setText("Chargement des informations...")

        self._load_poster()
        self.poster_label.set_added_at(channel.added_at, "movie")
        self._update_fav_btn()

        # Image de fond par défaut (affiche) en attendant les métadonnées
        if channel.logo_url:
            cached = ImageLoader.instance().get_cached_image(channel.logo_url)
            if cached:
                self._backdrop_pixmap = cached
                self.card_frame.update()

        if self.playlist and self.playlist.playlist_type == "xtream" and channel.stream_id:
            client = XtreamClient(
                self.playlist.server_url,
                self.playlist.username,
                self.playlist.password,
                channel.user_agent or self.playlist.user_agent,
            )
            self._worker = _MovieInfoWorker(client, channel.stream_id, self)
            self._worker.finished.connect(self._on_extra_info_loaded)
            self._worker.start()
        else:
            self.synopsis_label.setText(
                f"Film : {channel.name}\nCatégorie : {channel.group_title}\n\n"
                "Prêt pour le streaming en haute définition."
            )
            pref_lang = self.db.get_settings().preferred_audio_lang
            self._trailer_worker = _TrailerLookupWorker(
                media_type="movie",
                tmdb_id="",
                title=channel.name,
                year=channel.year or "",
                preferred_lang=pref_lang,
                orig_trailer="",
                parent=self,
            )
            self._trailer_worker.finished_trailer.connect(self._on_trailer_resolved)
            self._trailer_worker.start()

    def refresh_progress(self):
        """Met à jour l'affichage des boutons de reprise selon la progression sauvegardée."""
        if not self.channel:
            return
        prog = self.db.get_playback_progress(self.channel.id, self.channel.stream_url)
        self.resume_pos = prog[0] if prog else 0.0
        self._refresh_action_buttons()

    def _load_poster(self):
        if not self.channel or not self.channel.logo_url:
            self.poster_label.clear()
            return
        loader = ImageLoader.instance()
        cached = loader.get_cached_image(self.channel.logo_url)
        if cached:
            self._set_poster(cached)
        else:
            self.poster_label.clear()
            loader.image_loaded.connect(self._on_poster_loaded)
            loader.request_image_priority(self.channel.logo_url)

    def _on_poster_loaded(self, url: str, pixmap: QPixmap):
        if self.channel and url == self.channel.logo_url:
            self._set_poster(pixmap)

    def _set_poster(self, pixmap: QPixmap):
        if not pixmap or pixmap.isNull():
            return
        self.poster_label.setPixmap(pixmap)

    def _populate_badges(self):
        while self.badges_row.count():
            item = self.badges_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        badge_style = (
            "background-color: #1e293b; color: #e2e8f0; border: 1px solid #334155;"
            "border-radius: 5px; padding: 3px 9px; font-size: 11px; font-weight: 600;"
        )

        if self.meta.get("year"):
            lbl = QLabel(self.meta["year"])
            lbl.setCursor(Qt.CursorShape.ArrowCursor)
            lbl.setStyleSheet(badge_style)
            self.badges_row.addWidget(lbl)

        q_tag = self.meta.get("quality_tag")
        if q_tag:
            lbl = QLabel(q_tag)
            lbl.setCursor(Qt.CursorShape.ArrowCursor)
            lbl.setStyleSheet(
                "background-color: #15803d; color: #ffffff; border-radius: 5px;"
                "padding: 3px 9px; font-size: 11px; font-weight: 700;"
            )
            self.badges_row.addWidget(lbl)

        if self.meta.get("rating"):
            lbl = QLabel(f"★ {self.meta['rating']} / 10")
            lbl.setCursor(Qt.CursorShape.ArrowCursor)
            lbl.setStyleSheet(
                "background-color: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3);"
                "border-radius: 5px; padding: 3px 9px; font-size: 11px; font-weight: 700;"
            )
            self.badges_row.addWidget(lbl)

        if self.channel and self.channel.group_title:
            lbl = QLabel(self.channel.group_title)
            lbl.setCursor(Qt.CursorShape.ArrowCursor)
            lbl.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 600; padding: 3px 0;")
            self.badges_row.addWidget(lbl)

        self.badges_row.addStretch()

    def _refresh_action_buttons(self):
        if self.resume_pos > 0:
            self.play_btn.setText(f"  Reprendre à {_fmt(self.resume_pos)}")
            self.clear_resume_btn.show()
            self.restart_btn.show()
        else:
            self.play_btn.setText("  Regarder le film")
            self.clear_resume_btn.hide()
            self.restart_btn.hide()

    def _update_fav_btn(self):
        if not self.channel:
            return
        is_fav = bool(self.channel.is_favorite)
        self.fav_btn.setText("  Retirer des favoris" if is_fav else "  Ajouter aux favoris")
        self.fav_btn.setIcon(get_icon("favorite" if is_fav else "favorite_border", color="#f43f5e"))
        self.fav_btn.setIconSize(QSize(16, 16))
        if is_fav:
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(244,63,94,0.15);
                    color: #f43f5e;
                    border: 1px solid rgba(244,63,94,0.35);
                    border-radius: 8px;
                    padding: 10px 18px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: rgba(244,63,94,0.25);
                }
            """)
        else:
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #cbd5e1;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 10px 18px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #242f44;
                    border-color: #f43f5e;
                    color: #f43f5e;
                }
            """)

    def _style_download_btn(self):
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: #ffffff;
            }
        """)

    def _on_play(self):
        if self.channel:
            self.play_requested.emit(self.channel, self.resume_pos)

    def _on_restart(self):
        if self.channel:
            self.db.clear_playback_progress(self.channel.id, self.channel.stream_url)
            self.resume_pos = 0.0
            self.play_requested.emit(self.channel, 0.0)

    def _on_clear_resume(self):
        if self.channel:
            self.db.clear_playback_progress(self.channel.id, self.channel.stream_url)
            self.resume_pos = 0.0
            self._refresh_action_buttons()
            self.progress_cleared.emit(self.channel)

    def _toggle_favorite(self):
        if self.channel:
            new_fav = not self.channel.is_favorite
            self.channel.is_favorite = new_fav
            if self.channel.id:
                self.db.toggle_favorite(self.channel.id, new_fav)
            self._update_fav_btn()

    def _on_download(self):
        if not self.channel:
            return
        settings = self.db.get_settings()
        dest_dir = settings.download_dir or get_default_download_dir()
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "Erreur de dossier", str(e))
            return

        self.download_btn.setEnabled(False)
        self.download_btn.setText("  Téléchargement...")

        headers = {}
        if self.channel.http_referrer:
            headers["Referer"] = self.channel.http_referrer
        if self.channel.extra_headers:
            headers.update(self.channel.extra_headers)

        ua = self.channel.user_agent or settings.user_agent
        self._download_task = DownloadManager.instance().start_download(
            url=self.channel.stream_url,
            dest_dir=dest_dir,
            base_name=self.channel.name,
            user_agent=ua,
            headers=headers,
        )
        self._download_task.progress.connect(self._on_dl_progress)
        self._download_task.finished.connect(self._on_dl_finished)
        self._download_task.error.connect(self._on_dl_error)

    def _on_dl_progress(self, downloaded: int, total: int, speed: str):
        if total > 0:
            pct = int(downloaded / total * 100)
            self.download_btn.setText(f"  {pct}% ({speed})")
        else:
            mb = downloaded / (1024 * 1024)
            self.download_btn.setText(f"  {mb:.1f} Mo ({speed})")

    def _on_dl_finished(self, output_path: str):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("  ✓ Téléchargé")
        self.download_btn.setIcon(get_icon("check_circle", color="#4ade80"))
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                color: #4ade80;
                border: 1px solid #059669;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #047857;
                color: #ffffff;
            }
        """)
        try:
            self.download_btn.clicked.disconnect()
        except Exception:
            pass
        self.download_btn.clicked.connect(lambda: os.startfile(os.path.dirname(output_path)))

    def _on_dl_error(self, _):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("  Télécharger")
        self.download_btn.setIcon(get_icon("file_download", color="#38bdf8"))
        self._style_download_btn()

    def _on_extra_info_loaded(self, data: dict):
        info = data.get("info", {}) or data.get("movie_data", {})

        cover = info.get("movie_image", "") or info.get("cover_big", "") or info.get("cover", "")
        if cover and cover.startswith("http") and self.channel:
            if not self.channel.logo_url or self.poster_label.pixmap() is None or self.poster_label.pixmap().isNull():
                self.channel.logo_url = cover
                if self.channel.id:
                    self.db.update_channel_logo(self.channel.id, cover)
                ImageLoader.instance().request_image_priority(cover)

        plot = info.get("plot") or info.get("description") or "Aucun résumé disponible pour ce film."
        genre = info.get("genre", "")
        duration = info.get("duration", "")
        director = info.get("director", "")
        cast = info.get("cast", "")

        def _make_links(names_str: str) -> str:
            if not names_str:
                return ""
            parts = [p.strip() for p in re.split(r"[,;/]+", names_str) if p.strip()]
            return ", ".join(
                f'<a href="artist:{p}" style="color: #38bdf8; text-decoration: none;">{p}</a>'
                for p in parts
            )

        details = []
        if genre:
            details.append(f"<b>Genre :</b> {genre}")
        if duration:
            details.append(f"<b>Durée :</b> {duration}")
        if director:
            details.append(f"<b>Réalisateur :</b> {_make_links(director)}")
        if cast:
            details.append(f"<b>Acteurs :</b> {_make_links(cast)}")

        self.details_label.setText("<br>".join(details) if details else "")
        self.synopsis_label.setText(plot)

        # Récupération de l'image de fond (fanart / backdrop)
        backdrop_url = info.get("backdrop_path") or info.get("fanart") or info.get("cover_big")
        if isinstance(backdrop_url, list) and backdrop_url:
            backdrop_url = backdrop_url[0]
        if backdrop_url and isinstance(backdrop_url, str) and backdrop_url.startswith("http"):
            self._backdrop_url = backdrop_url
            cached = ImageLoader.instance().get_cached_image(backdrop_url)
            if cached:
                self._backdrop_pixmap = cached
                self.card_frame.update()
            else:
                ImageLoader.instance().image_loaded.connect(self._on_backdrop_loaded)
                ImageLoader.instance().request_image_priority(backdrop_url)

        # 1. Bande-annonce YouTube (avec recherche automatique dans la langue préférée)
        orig_trailer = str(info.get("youtube_trailer", "") or "").strip()
        tmdb_id = str(info.get("tmdb_id", "") or "").strip()
        year = str(self.channel.year or info.get("year", "") or "") if self.channel else ""
        title = self.channel.name if self.channel else ""

        if orig_trailer:
            self._setup_trailer(orig_trailer, name="Bande-annonce d'origine", badge="VO")

        pref_lang = self.db.get_settings().preferred_audio_lang
        self._trailer_worker = _TrailerLookupWorker(
            media_type="movie",
            tmdb_id=tmdb_id,
            title=title,
            year=year,
            preferred_lang=pref_lang,
            orig_trailer=orig_trailer,
            parent=self,
        )
        self._trailer_worker.finished_trailer.connect(self._on_trailer_resolved)
        self._trailer_worker.start()

        # 2. Avis spectateurs TMDB (Module de test)
        if tmdb_id:
            self._load_tmdb_reviews(tmdb_id)
        else:
            self.reviews_section.hide()

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
            title = self.channel.name if self.channel else "Film"
            url = f"https://www.youtube.com/watch?v={self._current_trailer_id}"
            self.play_trailer_requested.emit(title, url)

    def _open_trailer_url(self):
        if hasattr(self, "_current_trailer_id") and self._current_trailer_id:
            import webbrowser
            webbrowser.open(f"https://www.youtube.com/watch?v={self._current_trailer_id}")

    def _load_tmdb_reviews(self, tmdb_id: str):
        if self._tmdb_worker and self._tmdb_worker.isRunning():
            self._tmdb_worker.terminate()
            self._tmdb_worker.wait()

        self._tmdb_worker = _TMDBReviewsWorker(tmdb_id, self)
        self._tmdb_worker.finished_reviews.connect(self._on_tmdb_reviews_loaded)
        self._tmdb_worker.start()

    def _on_tmdb_reviews_loaded(self, reviews: list):
        while self.reviews_list_layout.count():
            item = self.reviews_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not reviews:
            self.reviews_section.hide()
            return

        self.reviews_badge.setText(f"{len(reviews)} avis")
        for rev in reviews[:5]:  # Limiter aux 5 avis les plus pertinents
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #1a2232;
                    border: 1px solid #28354c;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(14, 12, 14, 12)
            c_layout.setSpacing(6)

            # En-tête de l'avis
            top_row = QHBoxLayout()
            author_name = rev.get("author", "Spectateur")
            author_lbl = QLabel(author_name)
            author_lbl.setStyleSheet("color: #f1f5f9; font-size: 13px; font-weight: 700;")
            top_row.addWidget(author_lbl)

            rating = rev.get("rating")
            if rating is not None:
                rate_lbl = QLabel(f"★ {rating} / 10")
                rate_lbl.setStyleSheet("""
                    background-color: rgba(245, 158, 11, 0.15);
                    color: #fbbf24;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 6px;
                    border-radius: 4px;
                """)
                top_row.addWidget(rate_lbl)

            top_row.addStretch()

            date_str = rev.get("created_at", "")
            if date_str:
                date_lbl = QLabel(date_str)
                date_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
                top_row.addWidget(date_lbl)

            c_layout.addLayout(top_row)

            # Texte de l'avis
            content = rev.get("content", "")
            if len(content) > 350:
                content = content[:347] + "..."
            text_lbl = QLabel(content)
            text_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.5;")
            text_lbl.setWordWrap(True)
            c_layout.addWidget(text_lbl)

            self.reviews_list_layout.addWidget(card)

        self.reviews_section.show()

    def _on_backdrop_loaded(self, url: str, pixmap: QPixmap):
        if hasattr(self, "_backdrop_url") and self._backdrop_url and url == self._backdrop_url:
            self._backdrop_pixmap = pixmap
            self.card_frame.update()

    def _paint_card_backdrop(self, event):
        """Dessine un fond avec dégradé de transparence vers le bas qui rejoint la couleur du fond de la fenêtre.
        La hauteur du fond est bornée à la hauteur de l'affiche / description plus une petite marge."""
        painter = QPainter(self.card_frame)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.card_frame.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Hauteur calculée pour ne pas dépasser la description / affiche + petite marge
        poster_h = self.poster_label.height() if hasattr(self, "poster_label") else 270
        default_content_h = poster_h + 48  # 270 + 48 = 318px
        if hasattr(self, "poster_label") and self.poster_label.isVisible():
            p_geom = self.poster_label.geometry()
            if p_geom.bottom() > 0:
                btn_b = self.play_btn.geometry().bottom() if hasattr(self, "play_btn") and self.play_btn.isVisible() else 0
                default_content_h = max(p_geom.bottom() + 20, btn_b + 20, default_content_h)

        bg_height = min(rect.height(), default_content_h)
        if bg_height <= 0:
            return

        bg_rect = QRectF(0, 0, rect.width(), bg_height)

        # Buffer ARGB pour composer l'arrière-plan avec dégradé de transparence verticale
        buffer = QImage(QSize(rect.width(), int(bg_height)), QImage.Format.Format_ARGB32_Premultiplied)
        buffer.fill(Qt.GlobalColor.transparent)

        b_painter = QPainter(buffer)
        b_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        b_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        clip_path = QPainterPath()
        clip_path.addRoundedRect(bg_rect, 14.0, 14.0)
        b_painter.setClipPath(clip_path)

        if not self._is_video_playing and self._backdrop_pixmap and not self._backdrop_pixmap.isNull():
            # Affiche l'image de fond fanart avec des dégradés sombres
            scaled = self._backdrop_pixmap.scaled(
                QSize(rect.width(), int(bg_height)),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            dx = (scaled.width() - rect.width()) // 2
            dy = (scaled.height() - int(bg_height)) // 2
            b_painter.drawPixmap(0, 0, scaled, dx, dy, rect.width(), int(bg_height))

            # Dégradé horizontal (sombre à gauche pour le texte, plus clair à droite)
            h_grad = QLinearGradient(0, 0, rect.width(), 0)
            h_grad.setColorAt(0.0, QColor(17, 24, 39, 252))
            h_grad.setColorAt(0.40, QColor(17, 24, 39, 235))
            h_grad.setColorAt(0.70, QColor(17, 24, 39, 175))
            h_grad.setColorAt(1.0, QColor(17, 24, 39, 100))
            b_painter.fillRect(bg_rect, h_grad)

            # Voile d'ambiance bleuté profond
            b_painter.fillRect(bg_rect, QColor(13, 17, 26, 80))
        else:
            # Fond sobre sans image (pendant la vidéo ou par défaut)
            b_painter.fillRect(bg_rect, QColor(19, 25, 38, 235))

        # Masque de transparence verticale : le bas est le plus transparent et rejoint le fond de la fenêtre
        b_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        alpha_grad = QLinearGradient(0, 0, 0, bg_height)
        alpha_grad.setColorAt(0.0, QColor(0, 0, 0, 255))
        alpha_grad.setColorAt(0.35, QColor(0, 0, 0, 235))
        alpha_grad.setColorAt(0.70, QColor(0, 0, 0, 130))
        alpha_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        b_painter.fillRect(bg_rect, alpha_grad)
        b_painter.end()

        # Rendu du buffer
        painter.drawImage(0, 0, buffer)

        # Bordure douce qui s'estompe également vers le bas pour ne pas créer de cassure
        border_grad = QLinearGradient(0, 0, 0, bg_height)
        border_grad.setColorAt(0.0, QColor(51, 65, 85, 200))
        border_grad.setColorAt(0.50, QColor(51, 65, 85, 110))
        border_grad.setColorAt(0.85, QColor(51, 65, 85, 25))
        border_grad.setColorAt(1.0, QColor(51, 65, 85, 0))
        pen = QPen(border_grad, 1)
        painter.setPen(pen)
        painter.drawRoundedRect(bg_rect.adjusted(0.5, 0.5, -0.5, -0.5), 14.0, 14.0)

    def attach_video_widget(self, video_widget):
        """Attache le lecteur vidéo au sommet de la vue scrollable."""
        self._video_widget = video_widget
        self._is_video_playing = True
        self.card_frame.update()
        self.nav_row_widget.hide()
        if hasattr(self, "trailer_section"):
            self.trailer_section.hide()
        self.scroll_layout.insertWidget(0, video_widget)
        video_widget.show()
        self.scroll.verticalScrollBar().setValue(0)
        self._update_video_geometry()
        try:
            self.scroll.verticalScrollBar().valueChanged.disconnect(self._on_scroll_sync)
        except Exception:
            pass
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_sync)
        self.play_btn.setText("  Lecture en cours...")
        self.play_btn.setEnabled(False)

    def detach_video_widget(self, video_widget=None):
        """Détache le lecteur vidéo et réactive la fiche standard."""
        try:
            self.scroll.verticalScrollBar().valueChanged.disconnect(self._on_scroll_sync)
        except Exception:
            pass
        vw = video_widget or self._video_widget
        if vw:
            self.scroll_layout.removeWidget(vw)
            vw.setMinimumHeight(0)
            vw.setMaximumHeight(16777215)
            vw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_widget = None
        self._is_video_playing = False
        self.card_frame.update()
        self.nav_row_widget.show()
        if hasattr(self, "trailer_section") and getattr(self, "_current_trailer_id", None):
            self.trailer_section.show()
        self.play_btn.setEnabled(True)
        self.refresh_progress()
        self.stop_active_workers()

    def stop_active_workers(self):
        """Arrête tous les threads d'arrière-plan actifs pour libérer le processeur et le réseau."""
        if hasattr(self, "_worker") and self._worker and self._worker.isRunning():
            try:
                self._worker.terminate()
                self._worker.wait()
            except Exception:
                pass
            self._worker = None

        if hasattr(self, "_trailer_worker") and self._trailer_worker and self._trailer_worker.isRunning():
            try:
                self._trailer_worker.terminate()
                self._trailer_worker.wait()
            except Exception:
                pass
            self._trailer_worker = None

        if hasattr(self, "_tmdb_worker") and self._tmdb_worker and self._tmdb_worker.isRunning():
            try:
                self._tmdb_worker.terminate()
                self._tmdb_worker.wait()
            except Exception:
                pass
            self._tmdb_worker = None

    def _on_scroll_sync(self, _=None):
        if self._video_widget and self._video_widget.isVisible():
            self._video_widget._sync_geometry()

    def _update_video_geometry(self):
        if not self._video_widget:
            return

        win = self.window()
        is_fs = getattr(self, "_is_fullscreen", False) or (win.isFullScreen() if win else False)
        if is_fs:
            target_h = win.height() if win else self.height()
            if hasattr(self, "scroll") and self.scroll.viewport():
                target_h = max(target_h, self.scroll.viewport().height())
            self._video_widget.setFixedHeight(max(100, target_h))
            return

        # Largeur réelle disponible pour le contenu dans le viewport
        vp_w = self.scroll.viewport().width()
        if vp_w <= 100:
            sb_w = self.scroll.verticalScrollBar().width() if self.scroll.verticalScrollBar().isVisible() else 0
            vp_w = max(320, self.width() - sb_w)

        margins = self.scroll_layout.contentsMargins()
        content_w = max(320, vp_w - margins.left() - margins.right())
        h = int(content_w * 9 / 16)

        self._video_widget.setFixedHeight(h)

    def set_fullscreen(self, is_fs: bool):
        self._is_fullscreen = is_fs
        if is_fs:
            self.nav_row_widget.hide()
            self.card_frame.hide()
            if hasattr(self, "trailer_section"):
                self.trailer_section.hide()
            if hasattr(self, "reviews_section"):
                self.reviews_section.hide()
            self.scroll_layout.setContentsMargins(0, 0, 0, 0)
            self.scroll_layout.setSpacing(0)
            self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._update_video_geometry()
        else:
            self.card_frame.show()
            if hasattr(self, "_current_trailer_id") and self._current_trailer_id and not getattr(self, "_is_video_playing", False) and not getattr(self, "_video_widget", None):
                self.trailer_section.show()
            self.reviews_section.show()
            self.scroll_layout.setContentsMargins(28, 20, 28, 28)
            self.scroll_layout.setSpacing(20)
            self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._update_video_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_video_geometry()
        if self._video_widget and self._video_widget.isVisible():
            self._video_widget._sync_geometry()

    def eventFilter(self, watched, event: QEvent) -> bool:
        if hasattr(self, "scroll") and watched == self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._update_video_geometry()
            if self._video_widget and self._video_widget.isVisible():
                self._video_widget._sync_geometry()
        return super().eventFilter(watched, event)

    def _on_artist_link_clicked(self, link: str):
        if link.startswith("artist:"):
            artist_name = link[len("artist:"):].strip()
            if artist_name:
                self.artist_clicked.emit(artist_name)
