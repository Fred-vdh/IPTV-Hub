"""
Vue dédiée aux Favoris avec affiches cinéma modernes, filtres interactifs (Films / Séries, Cette liste / Toutes les listes),
suppression rapide en un clic (bouton ×) et horodatage en français.
"""

from datetime import datetime
from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QMouseEvent,
    QPen, QPainterPath
)

from core.models import Channel, parse_movie_metadata
from core.database import Database
from core.image_loader import ImageLoader
from ui.icons import get_icon
from ui.widgets.poster_utils import draw_added_date_badge
from core.i18n import tr


FRENCH_MONTHS = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc."
]


def format_favorite_date(iso_str: Optional[str]) -> str:
    """Formate une date ISO en chaîne conviviale en français (ex: '2 sept., 01:20')."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        month_name = FRENCH_MONTHS[dt.month - 1]
        return f"{dt.day} {month_name}, {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return ""


class FavoritePosterWidget(QWidget):
    """Widget d'affiche avec badge qualité, bouton de suppression × et effet hover."""
    remove_clicked = pyqtSignal(Channel)

    def __init__(self, channel: Channel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.meta = parse_movie_metadata(channel.name, channel.rating, channel.year)
        self.pixmap: Optional[QPixmap] = None
        self.is_hovered = False
        self._cross_hovered = False

        self.setFixedSize(160, 240)
        self.setMouseTracking(True)
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

    def set_hovered(self, hovered: bool):
        self.is_hovered = hovered
        self.update()

    def _get_cross_rect(self) -> QRect:
        return QRect(6, 6, 20, 20)

    def mouseMoveEvent(self, event: QMouseEvent):
        was_cross = self._cross_hovered
        self._cross_hovered = self._get_cross_rect().contains(event.pos())
        if was_cross != self._cross_hovered:
            self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._get_cross_rect().contains(event.pos()):
            self.remove_clicked.emit(self.channel)
            event.accept()
            return
        event.ignore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect()

        # 1. Découpe arrondie pour le poster
        path = QPainterPath()
        path.addRoundedRect(0, 0, rect.width(), rect.height(), 8, 8)
        painter.setClipPath(path)

        if self.pixmap and not self.pixmap.isNull():
            if self.channel.stream_type == "live":
                painter.fillRect(rect, QColor("#131b2e"))
                target_size = QSize(rect.width() - 24, rect.height() - 40)
                scaled = self.pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                sx = (rect.width() - scaled.width()) // 2
                sy = (rect.height() - scaled.height()) // 2
                painter.drawPixmap(sx, sy, scaled)
            else:
                scaled = self.pixmap.scaled(
                    rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                sx = (rect.width() - scaled.width()) // 2
                sy = (rect.height() - scaled.height()) // 2
                painter.drawPixmap(sx, sy, scaled)
        else:
            painter.fillRect(rect, QColor("#1e293b"))
            icon_name = "movie" if self.channel.stream_type == "movie" else "tv"
            icon_pix = get_icon(icon_name, color="#475569").pixmap(48, 48)
            painter.drawPixmap((rect.width() - 48) // 2, (rect.height() - 48) // 2, icon_pix)

        # 2. Overlay sombre et bouton Play au survol
        if self.is_hovered and not self._cross_hovered:
            painter.fillRect(rect, QColor(0, 0, 0, 95))
            play_pix = get_icon("play_arrow", color="#ffffff").pixmap(46, 46)
            painter.drawPixmap((rect.width() - 46) // 2, (rect.height() - 46) // 2, play_pix)

        painter.setClipping(False)

        # 3. Bordure
        painter.save()
        if self.is_hovered:
            painter.setPen(QPen(QColor("#3b82f6"), 2))
        else:
            painter.setPen(QPen(QColor("#334155"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, rect.width() - 2, rect.height() - 2, 8, 8)
        painter.restore()

        # 4. Badges supérieurs droits : Note (ex: ★ 7.3) / Direct / Qualité
        if self.channel.stream_type == "live":
            self._draw_live_badge(painter)
        else:
            rating_str = self.meta.get("rating", "") or (self.channel.rating if self.channel and self.channel.rating else "")
            if rating_str:
                self._draw_rating_badge(painter, rating_str)
            else:
                q_tag = self.meta.get("quality_tag", "")
                if q_tag:
                    self._draw_quality_badge(painter, q_tag)

        # 5. Bouton croix × de suppression rapide en haut à gauche
        self._draw_cross_button(painter)

        # 6. Badge date d'ajout (Films et Séries)
        if self.channel and self.channel.stream_type in ("movie", "series"):
            draw_added_date_badge(painter, self.channel.added_at, rect.width(), rect.height(), bottom_offset=6)

    def _draw_rating_badge(self, painter: QPainter, rating: str):
        painter.save()
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        text = f"★ {rating}"
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        badge_w = text_w + 10
        badge_h = 16
        bx = self.width() - badge_w - 6
        by = 6

        painter.setBrush(QColor(15, 23, 42, 220))
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRoundedRect(QRect(bx, by, badge_w, badge_h), 4, 4)

        painter.setPen(QColor("#4ade80"))
        painter.drawText(QRect(bx, by, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _draw_live_badge(self, painter: QPainter):
        painter.save()
        font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(font)
        badge_w = 46
        badge_rect = QRect(self.width() - badge_w - 6, 6, badge_w, 16)
        painter.setBrush(QColor("#ef4444"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect, 3, 3)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "DIRECT")
        painter.restore()

    def _draw_quality_badge(self, painter: QPainter, tag: str):
        painter.save()
        font = QFont()
        font.setPointSize(7)
        font.setBold(True)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(tag)
        badge_w = text_w + 12
        badge_h = 16
        bx = self.width() - badge_w - 6
        by = 6

        # Fond badge blanc / crème comme sur la capture
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRect(bx, by, badge_w, badge_h), 3, 3)

        painter.setPen(QColor("#0f172a"))
        painter.drawText(QRect(bx, by, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, tag)
        painter.restore()

    def _draw_cross_button(self, painter: QPainter):
        painter.save()
        r = self._get_cross_rect()

        if self._cross_hovered:
            painter.setBrush(QColor(239, 68, 68, 230))  # Rouge vif au survol
            painter.setPen(QPen(QColor("#ffffff"), 1))
        else:
            painter.setBrush(QColor(15, 23, 42, 190))  # Fond sombre semi-transparent
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1))

        painter.drawRoundedRect(r, 4, 4)

        # Dessiner le symbole "×"
        painter.setPen(QPen(QColor("#ffffff"), 1.8))
        cx = r.center().x()
        cy = r.center().y()
        offset = 4
        painter.drawLine(cx - offset, cy - offset, cx + offset, cy + offset)
        painter.drawLine(cx - offset, cy + offset, cx + offset, cy - offset)
        painter.restore()


class FavoriteCardWidget(QWidget):
    """Carte complète de favori avec affiche, titre et date d'ajout."""
    clicked = pyqtSignal(Channel)
    remove_requested = pyqtSignal(Channel)

    CARD_WIDTH = 160
    TOTAL_HEIGHT = 300

    def __init__(self, channel: Channel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.setFixedSize(self.CARD_WIDTH, self.TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 1. Poster avec badge et bouton croix
        self.poster_widget = FavoritePosterWidget(channel, parent=self)
        self.poster_widget.remove_clicked.connect(self.remove_requested.emit)
        layout.addWidget(self.poster_widget)

        # 2. Titre du film / série
        self.title_label = QLabel(self.channel.name)
        self.title_label.setToolTip(self.channel.name)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.title_label.setStyleSheet("""
            color: #cbd5e1;
            font-size: 11px;
            font-weight: 500;
            line-height: 1.2;
        """)
        self.title_label.setFixedHeight(32)
        layout.addWidget(self.title_label)

        # 3. Horodatage d'ajout en français
        date_str = format_favorite_date(self.channel.favorite_added_at)
        self.date_label = QLabel(date_str)
        self.date_label.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 400;")
        self.date_label.setFixedHeight(14)
        layout.addWidget(self.date_label)

    def enterEvent(self, event):
        self.poster_widget.set_hovered(True)
        self.title_label.setStyleSheet("""
            color: #ffffff;
            font-size: 11px;
            font-weight: 600;
            line-height: 1.2;
        """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.poster_widget.set_hovered(False)
        self.title_label.setStyleSheet("""
            color: #cbd5e1;
            font-size: 11px;
            font-weight: 500;
            line-height: 1.2;
        """)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Vérifier que le clic n'était pas sur la croix (déjà intercepté par le poster)
            self.clicked.emit(self.channel)
        super().mousePressEvent(event)


class FavoritesView(QWidget):
    """Vue complète pour la gestion des Favoris avec grille de cartes et barre d'outils."""
    movie_selected = pyqtSignal(Channel)
    series_selected = pyqtSignal(Channel)
    channel_selected = pyqtSignal(Channel)

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.current_playlist_id: Optional[int] = None
        self.active_stream_type: str = "movie"  # "movie", "series", "live"
        self.scope_all_playlists: bool = False  # False = Cette liste, True = Toutes les listes
        self.search_query: str = ""

        self._cards: List[FavoriteCardWidget] = []
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("background-color: #111622;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 20)
        main_layout.setSpacing(18)

        # 1. En-tête (Top Bar)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(12)

        title_label = QLabel("Favoris")
        title_label.setStyleSheet("color: #f8fafc; font-size: 20px; font-weight: 700;")
        top_bar.addWidget(title_label)

        top_bar.addStretch(1)

        # 1.1 Groupe Type de média (Films | Séries | TV en direct)
        self.media_group = QFrame()
        self.media_group.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        media_layout = QHBoxLayout(self.media_group)
        media_layout.setContentsMargins(2, 2, 2, 2)
        media_layout.setSpacing(2)

        self.btn_movies = QPushButton("Films")
        self.btn_movies.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_movies.setFixedHeight(28)
        self.btn_movies.clicked.connect(lambda: self._set_stream_type("movie"))
        media_layout.addWidget(self.btn_movies)

        self.btn_series = QPushButton("Séries")
        self.btn_series.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_series.setFixedHeight(28)
        self.btn_series.clicked.connect(lambda: self._set_stream_type("series"))
        media_layout.addWidget(self.btn_series)

        self.btn_live = QPushButton("TV en direct")
        self.btn_live.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_live.setFixedHeight(28)
        self.btn_live.clicked.connect(lambda: self._set_stream_type("live"))
        media_layout.addWidget(self.btn_live)

        top_bar.addWidget(self.media_group)

        # 1.2 Groupe Portée (Cette liste | Toutes les listes)
        self.scope_group = QFrame()
        self.scope_group.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        scope_layout = QHBoxLayout(self.scope_group)
        scope_layout.setContentsMargins(2, 2, 2, 2)
        scope_layout.setSpacing(2)

        self.btn_this_playlist = QPushButton("  " + tr("Cette liste de lecture"))
        self.btn_this_playlist.setIcon(get_icon("playlist_play", color="#94a3b8"))
        self.btn_this_playlist.setIconSize(QSize(16, 16))
        self.btn_this_playlist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_this_playlist.setFixedHeight(28)
        self.btn_this_playlist.clicked.connect(lambda: self._set_scope(False))
        scope_layout.addWidget(self.btn_this_playlist)

        self.btn_all_playlists = QPushButton("  " + tr("Toutes les listes de lecture"))
        self.btn_all_playlists.setIcon(get_icon("language", color="#94a3b8"))
        self.btn_all_playlists.setIconSize(QSize(16, 16))
        self.btn_all_playlists.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_all_playlists.setFixedHeight(28)
        self.btn_all_playlists.clicked.connect(lambda: self._set_scope(True))
        scope_layout.addWidget(self.btn_all_playlists)

        top_bar.addWidget(self.scope_group)

        # 1.3 Bouton Corbeille (Vider les favoris)
        self.btn_clear_all = QPushButton()
        self.btn_clear_all.setIcon(get_icon("delete_outline", color="#94a3b8"))
        self.btn_clear_all.setIconSize(QSize(18, 18))
        self.btn_clear_all.setToolTip(tr("Vider tous les favoris affichés"))
        self.btn_clear_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_all.setFixedSize(32, 32)
        self.btn_clear_all.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                border-color: #dc2626;
            }
        """)
        self.btn_clear_all.clicked.connect(self._on_clear_all_clicked)
        top_bar.addWidget(self.btn_clear_all)

        main_layout.addLayout(top_bar)

        # 2. Zone défilante avec Grille
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #0f131d;
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.container_widget = QWidget()
        self.container_widget.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.container_widget)
        self.grid_layout.setContentsMargins(0, 4, 0, 20)
        self.grid_layout.setHorizontalSpacing(18)
        self.grid_layout.setVerticalSpacing(22)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.container_widget)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # 3. Label message vide
        self.empty_label = QLabel("Aucun favori enregistré dans cette section.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #64748b; font-size: 14px; font-weight: 500; margin-top: 60px;")
        self.empty_label.setVisible(False)
        main_layout.addWidget(self.empty_label)

        self._update_button_styles()

    def _update_button_styles(self):
        active_style = """
            QPushButton {
                background-color: #334155;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 500;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                color: #f1f5f9;
                background-color: rgba(255, 255, 255, 0.05);
            }
        """
        self.btn_movies.setStyleSheet(active_style if self.active_stream_type == "movie" else inactive_style)
        self.btn_series.setStyleSheet(active_style if self.active_stream_type == "series" else inactive_style)
        self.btn_live.setStyleSheet(active_style if self.active_stream_type == "live" else inactive_style)

        self.btn_this_playlist.setStyleSheet(active_style if not self.scope_all_playlists else inactive_style)
        self.btn_all_playlists.setStyleSheet(active_style if self.scope_all_playlists else inactive_style)

    def _set_stream_type(self, stream_type: str):
        if self.active_stream_type != stream_type:
            self.active_stream_type = stream_type
            self._update_button_styles()
            self.refresh_view()

    def _set_scope(self, all_playlists: bool):
        if self.scope_all_playlists != all_playlists:
            self.scope_all_playlists = all_playlists
            self._update_button_styles()
            self.refresh_view()

    def set_playlist_id(self, playlist_id: Optional[int]):
        self.current_playlist_id = playlist_id
        self.refresh_view()

    def set_search_query(self, query: str):
        self.search_query = query.strip()
        self.refresh_view()

    def refresh_view(self):
        # 1. Nettoyer la grille actuelle
        for card in self._cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        # 2. Récupérer les favoris depuis la base de données
        target_pl_id = None if self.scope_all_playlists else self.current_playlist_id
        channels = self.db.get_channels(
            playlist_id=target_pl_id,
            favorites_only=True,
            stream_type=self.active_stream_type,
            search_query=self.search_query if self.search_query else None,
            order_by="favorite_date_desc"
        )

        if not channels:
            self.empty_label.setVisible(True)
            self.scroll_area.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.scroll_area.setVisible(True)

        # 3. Calculer le nombre de colonnes selon la largeur disponible
        available_w = max(400, self.scroll_area.width() - 40)
        card_w = FavoriteCardWidget.CARD_WIDTH + 18
        cols = max(2, available_w // card_w)

        # 4. Peupler la grille
        for i, ch in enumerate(channels):
            card = FavoriteCardWidget(ch, parent=self.container_widget)
            card.clicked.connect(self._on_card_clicked)
            card.remove_requested.connect(self._on_remove_requested)
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)
            self._cards.append(card)

    def _on_card_clicked(self, channel: Channel):
        if channel.stream_type in ("movie", "vod"):
            self.movie_selected.emit(channel)
        elif channel.stream_type == "series":
            self.series_selected.emit(channel)
        else:
            self.channel_selected.emit(channel)

    def _on_remove_requested(self, channel: Channel):
        """Retire l'élément des favoris et rafraîchit la vue."""
        if channel.id:
            self.db.set_favorite(channel.id, False)
            self.refresh_view()

    def _on_clear_all_clicked(self):
        if self.active_stream_type == "live":
            sec_name = "de TV en direct"
        elif self.active_stream_type == "movie":
            sec_name = "de films"
        else:
            sec_name = "de séries"
        scope_name = "de toutes les listes" if self.scope_all_playlists else "de la liste active"
        msg = f"Voulez-vous vraiment retirer tous les favoris {sec_name} ({scope_name}) ?"

        reply = QMessageBox.question(
            self,
            "Vider les favoris",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            target_pl_id = None if self.scope_all_playlists else self.current_playlist_id
            self.db.clear_all_favorites(playlist_id=target_pl_id, stream_type=self.active_stream_type)
            self.refresh_view()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Réorganiser les colonnes lors du redimensionnement de la fenêtre
        if self._cards:
            available_w = max(400, self.scroll_area.width() - 40)
            card_w = FavoriteCardWidget.CARD_WIDTH + 18
            cols = max(2, available_w // card_w)

            for i, card in enumerate(self._cards):
                row = i // cols
                col = i % cols
                self.grid_layout.removeWidget(card)
                self.grid_layout.addWidget(card, row, col)

    def retranslate_ui(self):
        """Met à jour les textes des onglets et boutons de FavoritesView."""
        if hasattr(self, "header_title"):
            self.header_title.setText(tr("Vos Favoris"))
        if hasattr(self, "btn_all"):
            self.btn_all.setText(tr("Tous"))
        if hasattr(self, "btn_live"):
            self.btn_live.setText(tr("Chaînes TV"))
        if hasattr(self, "btn_movies"):
            self.btn_movies.setText(tr("Films"))
        if hasattr(self, "btn_series"):
            self.btn_series.setText(tr("Séries"))
        if hasattr(self, "btn_this_playlist"):
            self.btn_this_playlist.setText("  " + tr("Cette liste de lecture"))
        if hasattr(self, "btn_all_playlists"):
            self.btn_all_playlists.setText("  " + tr("Toutes les listes de lecture"))
        if hasattr(self, "btn_clear_all"):
            self.btn_clear_all.setToolTip(tr("Vider tous les favoris affichés"))
        self.refresh_view()
