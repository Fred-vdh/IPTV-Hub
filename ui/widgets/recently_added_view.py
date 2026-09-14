"""
Vue dédiée aux éléments Récemment Ajoutés avec carrousels horizontaux fluides pour Films, Séries et TV en direct.
Intègre des badges de note (★ 7.5), de qualité/langue, LIVE pour le direct, et des boutons de navigation par section.
"""

from datetime import datetime
from typing import Optional, List, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPropertyAnimation, QEasingCurve, QTimer, QSize
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QMouseEvent,
    QPen, QPainterPath
)

from core.models import Channel, parse_movie_metadata
from core.database import Database
from core.image_loader import ImageLoader
from ui.icons import get_icon
from ui.widgets.poster_utils import draw_added_date_badge
from core.i18n import tr, get_locale_month


def format_recent_date(dt_input: Any) -> str:
    """Formate une date en chaîne conviviale localisée (ex: '2 sept., 14:00' ou '13 avr. 2018')."""
    if not dt_input:
        return ""
    try:
        if isinstance(dt_input, (int, float)):
            dt = datetime.fromtimestamp(dt_input)
        elif isinstance(dt_input, str):
            clean_str = dt_input.strip()
            if not clean_str:
                return ""
            if clean_str.isdigit():
                dt = datetime.fromtimestamp(int(clean_str))
            else:
                clean_str = clean_str.replace(" ", "T")
                dt = datetime.fromisoformat(clean_str)
        elif isinstance(dt_input, datetime):
            dt = dt_input
        else:
            return ""

        month_name = get_locale_month(dt.month, short=True)
        now = datetime.now()
        if dt.year == now.year:
            return f"{dt.day} {month_name}, {dt.hour:02d}:{dt.minute:02d}"
        else:
            return f"{dt.day} {month_name} {dt.year}"
    except Exception:
        return ""


class RecentPosterWidget(QWidget):
    """Vignette d'affiche 2:3 avec coins arrondis, badge de type, badge qualité et effet hover."""

    def __init__(self, channel: Channel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.meta = parse_movie_metadata(channel.name, channel.rating, channel.year)
        self.pixmap: Optional[QPixmap] = None
        self.is_hovered = False

        self.setFixedSize(155, 230)
        self.setMouseTracking(True)
        ImageLoader.instance().image_loaded.connect(self._on_image_loaded)
        self._load_image()

    def _load_image(self):
        if not self.channel or not self.channel.logo_url:
            return

        loader = ImageLoader.instance()
        cached = loader.get_cached_image(self.channel.logo_url)
        if cached:
            self.pixmap = cached
            self.update()
        else:
            loader.request_image(self.channel.logo_url)

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        if self.channel and self.channel.logo_url and url == self.channel.logo_url:
            self.pixmap = pixmap
            self.update()
            if self.parentWidget():
                self.parentWidget().update()

    def set_hovered(self, hovered: bool):
        self.is_hovered = hovered
        self.update()

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
                target_size = QSize(rect.width() - 24, rect.height() - 44)
                scaled = self.pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                sx = (rect.width() - scaled.width()) // 2
                sy = (rect.height() - scaled.height()) // 2 + 6
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
            icon_name = "movie" if self.channel.stream_type == "movie" else ("tv" if self.channel.stream_type == "series" else "live_tv")
            icon_pix = get_icon(icon_name, color="#475569").pixmap(44, 44)
            painter.drawPixmap((rect.width() - 44) // 2, (rect.height() - 44) // 2, icon_pix)

        # 2. Overlay sombre et bouton Play au survol
        if self.is_hovered:
            painter.fillRect(rect, QColor(0, 0, 0, 95))
            play_pix = get_icon("play_arrow", color="#ffffff").pixmap(44, 44)
            painter.drawPixmap((rect.width() - 44) // 2, (rect.height() - 44) // 2, play_pix)

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

        # 4. Badges supérieurs : Type à gauche + Qualité/Langue à droite
        self._draw_header_badges(painter)

        # 5. Badge date d'ajout (Films et Séries)
        if self.channel and self.channel.stream_type in ("movie", "series"):
            draw_added_date_badge(painter, self.channel.added_at, rect.width(), rect.height(), bottom_offset=6)

    def _draw_header_badges(self, painter: QPainter):
        painter.save()
        st = self.channel.stream_type if self.channel else ""
        t_h = 16
        by = 6
        bx = 6

        # 1. Badge Live (uniquement pour les flux TV en direct)
        if st == "live":
            font_live = QFont()
            font_live.setPointSize(7)
            font_live.setBold(True)
            painter.setFont(font_live)

            type_text = "LIVE"
            t_w = painter.fontMetrics().horizontalAdvance(type_text) + 8
            painter.setBrush(QColor("#ef4444"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRect(bx, by, t_w, t_h), 3, 3)

            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRect(bx, by, t_w, t_h), Qt.AlignmentFlag.AlignCenter, type_text)
            bx += t_w + 4

        # 2. Badge Qualité / Format si présent (ex: 4K, FHD, MULTI...)
        q_tag = self.meta.get("quality_tag", "")
        if q_tag:
            font_q = QFont()
            font_q.setPointSize(7)
            font_q.setBold(True)
            painter.setFont(font_q)

            q_metrics = painter.fontMetrics()
            q_w = q_metrics.horizontalAdvance(q_tag) + 10

            if bx + q_w <= self.width() - 50:
                painter.setBrush(QColor(255, 255, 255, 235))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRect(bx, by, q_w, t_h), 3, 3)

                painter.setPen(QColor("#0f172a"))
                painter.drawText(QRect(bx, by, q_w, t_h), Qt.AlignmentFlag.AlignCenter, q_tag)

        # 3. Badge Note (★ 7.5) en haut à droite pour films et séries
        if st in ("movie", "series"):
            raw_rating = self.meta.get("rating", "") or (str(self.channel.rating).strip() if self.channel and self.channel.rating else "")
            rating_str = ""
            if raw_rating:
                try:
                    r_val = float(str(raw_rating).replace(",", "."))
                    if r_val > 10.0 and r_val <= 100.0:
                        r_val = r_val / 10.0
                    if r_val > 0.0:
                        rating_str = f"{r_val:.1f}"
                except (ValueError, TypeError):
                    pass

            if rating_str:
                self._draw_rating_badge(painter, rating_str)

        painter.restore()

    def _draw_rating_badge(self, painter: QPainter, rating: str):
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


class RecentCardWidget(QWidget):
    """Carte complète avec affiche, titre cliquable et date d'ajout."""
    clicked = pyqtSignal(Channel)

    CARD_WIDTH = 155
    TOTAL_HEIGHT = 300

    def __init__(self, channel: Channel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.setFixedSize(self.CARD_WIDTH, self.TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 1. Poster
        self.poster_widget = RecentPosterWidget(channel, parent=self)
        layout.addWidget(self.poster_widget)

        # 2. Titre
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
        self.title_label.setFixedHeight(30)
        layout.addWidget(self.title_label)

        # 3. Horodatage en français
        date_str = format_recent_date(self.channel.added_at)
        self.date_label = QLabel(date_str)
        self.date_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
        self.date_label.setFixedHeight(16)
        if not date_str:
            self.date_label.hide()
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
            self.clicked.emit(self.channel)
        super().mousePressEvent(event)


class CarouselRowWidget(QWidget):
    """Rangée carrousel horizontale avec en-tête, badge de compteur, lien 'Parcourir...' et boutons de défilement < >."""
    card_clicked = pyqtSignal(Channel)
    browse_clicked = pyqtSignal(str)

    def __init__(self, title: str, section_key: str, browse_text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title = title
        self.section_key = section_key
        self.browse_text = browse_text
        self._cards: List[RecentCardWidget] = []

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 10)
        main_layout.setSpacing(12)

        # 1. En-tête de la rangée
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Titre
        self.title_lbl = QLabel(tr(self.title))
        self.title_lbl.setStyleSheet("color: #f8fafc; font-size: 16px; font-weight: 700;")
        header_layout.addWidget(self.title_lbl)

        # Badge compteur (ex: '30')
        self.count_badge = QLabel("0")
        self.count_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 10px;
        """)
        header_layout.addWidget(self.count_badge)

        header_layout.addStretch(1)

        # Lien 'Parcourir tous les films >'
        self.browse_btn = QPushButton(tr(self.browse_text))
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 500;
                border: none;
                padding: 4px 8px;
            }
            QPushButton:hover {
                color: #60a5fa;
            }
        """)
        self.browse_btn.clicked.connect(lambda: self.browse_clicked.emit(self.section_key))
        header_layout.addWidget(self.browse_btn)

        main_layout.addLayout(header_layout)

        # 2. Zone de défilement horizontal avec conteneur et boutons
        scroll_container = QWidget()
        scroll_container_layout = QHBoxLayout(scroll_container)
        scroll_container_layout.setContentsMargins(0, 0, 0, 0)
        scroll_container_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFixedHeight(305)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.inner_widget = QWidget()
        self.inner_widget.setStyleSheet("background: transparent;")
        self.inner_layout = QHBoxLayout(self.inner_widget)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.inner_layout.setSpacing(14)
        self.inner_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.inner_widget)
        scroll_container_layout.addWidget(self.scroll_area)

        # Bouton défilement droit '>'
        self.btn_scroll_right = QPushButton("›", self.scroll_area)
        self.btn_scroll_right.setFixedSize(36, 36)
        self.btn_scroll_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scroll_right.setStyleSheet("""
            QPushButton {
                background-color: rgba(15, 23, 42, 0.85);
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                border: 1px solid #475569;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
        """)
        self.btn_scroll_right.clicked.connect(self._scroll_right)

        # Bouton défilement gauche '<'
        self.btn_scroll_left = QPushButton("‹", self.scroll_area)
        self.btn_scroll_left.setFixedSize(36, 36)
        self.btn_scroll_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scroll_left.setStyleSheet("""
            QPushButton {
                background-color: rgba(15, 23, 42, 0.85);
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                border: 1px solid #475569;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
        """)
        self.btn_scroll_left.clicked.connect(self._scroll_left)
        self.btn_scroll_left.hide()

        main_layout.addWidget(scroll_container)

    def set_channels(self, channels: List[Channel]):
        # Nettoyage
        while self.inner_layout.count():
            item = self.inner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._cards.clear()

        self.count_badge.setText(str(len(channels)))

        if not channels:
            empty_lbl = QLabel(tr("Aucun élément récent dans {category}.", category=tr(self.title).lower()))
            empty_lbl.setStyleSheet("color: #64748b; font-size: 12px; margin: 10px 0;")
            self.inner_layout.addWidget(empty_lbl)
            self.btn_scroll_right.hide()
            self.btn_scroll_left.hide()
            return

        for ch in channels:
            card = RecentCardWidget(ch, parent=self.inner_widget)
            card.clicked.connect(self.card_clicked.emit)
            self.inner_layout.addWidget(card)
            self._cards.append(card)

        self._update_scroll_buttons()
        QTimer.singleShot(30, self._update_scroll_buttons)
        QTimer.singleShot(150, self._update_scroll_buttons)

    def _animate_scroll(self, delta: int):
        """Anime le glissement fluide des cartes vers la gauche ou vers la droite."""
        bar = self.scroll_area.horizontalScrollBar()
        current = bar.value()
        target = max(0, min(bar.maximum(), current + delta))
        if current == target:
            return

        if hasattr(self, "_scroll_anim") and self._scroll_anim.state() == QPropertyAnimation.State.Running:
            self._scroll_anim.stop()

        self._scroll_anim = QPropertyAnimation(bar, b"value", self)
        self._scroll_anim.setDuration(380)
        self._scroll_anim.setStartValue(current)
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.valueChanged.connect(lambda _: self._update_scroll_buttons())
        self._scroll_anim.finished.connect(self._update_scroll_buttons)
        self._scroll_anim.start()

    def _scroll_right(self):
        step = (RecentCardWidget.CARD_WIDTH + 14) * 3
        self._animate_scroll(step)

    def _scroll_left(self):
        step = (RecentCardWidget.CARD_WIDTH + 14) * 3
        self._animate_scroll(-step)

    def _update_scroll_buttons(self):
        bar = self.scroll_area.horizontalScrollBar()
        has_many = len(self._cards) > 3
        max_val = bar.maximum()
        val = bar.value()

        self.btn_scroll_left.setVisible(val > 0)
        can_scroll_right = (val < max_val) if max_val > 0 else has_many
        self.btn_scroll_right.setVisible(has_many and can_scroll_right)

        # Repositionnement des boutons flottants
        vp = self.scroll_area.viewport()
        w = vp.width() if vp and vp.width() > 100 else self.scroll_area.width()
        h = vp.height() if vp and vp.height() > 100 else self.scroll_area.height()
        if w <= 100:
            w = self.width() if self.width() > 100 else 800
        if h <= 100:
            h = 305

        self.btn_scroll_right.move(max(10, w - 46), (h - 36) // 2 - 20)
        self.btn_scroll_left.move(10, (h - 36) // 2 - 20)

    def retranslate_ui(self):
        if hasattr(self, "title_lbl"):
            self.title_lbl.setText(tr(self.title))
        if hasattr(self, "browse_btn"):
            self.browse_btn.setText(tr(self.browse_text))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._update_scroll_buttons)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scroll_buttons()
        QTimer.singleShot(50, self._update_scroll_buttons)


class RecentlyAddedView(QWidget):
    """Vue complète pour les récents ajouts avec 3 carrousels (Films, Séries, TV en direct)."""
    movie_selected = pyqtSignal(Channel)
    series_selected = pyqtSignal(Channel)
    channel_selected = pyqtSignal(Channel)
    browse_section_requested = pyqtSignal(str)

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.current_playlist_id: Optional[int] = None
        self.search_query: str = ""

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("background-color: #111622;")
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 20, 28, 20)
        root_layout.setSpacing(16)

        # 1. Titre principal en haut
        self.title_label = QLabel(tr("Récemment ajoutés"))
        self.title_label.setStyleSheet("color: #f8fafc; font-size: 20px; font-weight: 700;")
        root_layout.addWidget(self.title_label)

        # 2. Zone défilante verticale globale
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
        self.content_layout = QVBoxLayout(self.container_widget)
        self.content_layout.setContentsMargins(0, 4, 0, 30)
        self.content_layout.setSpacing(24)

        # 2.1 Carrousel Films
        self.movies_carousel = CarouselRowWidget("Films", "vod", "Parcourir tous les films >", parent=self.container_widget)
        self.movies_carousel.card_clicked.connect(self.movie_selected.emit)
        self.movies_carousel.browse_clicked.connect(self.browse_section_requested.emit)
        self.content_layout.addWidget(self.movies_carousel)

        # 2.2 Carrousel Séries
        self.series_carousel = CarouselRowWidget("Séries", "series", "Parcourir toutes les séries >", parent=self.container_widget)
        self.series_carousel.card_clicked.connect(self.series_selected.emit)
        self.series_carousel.browse_clicked.connect(self.browse_section_requested.emit)
        self.content_layout.addWidget(self.series_carousel)

        # 2.3 Carrousel TV en direct
        self.live_carousel = CarouselRowWidget("TV en direct", "live", "Parcourir toute la TV en direct >", parent=self.container_widget)
        self.live_carousel.card_clicked.connect(self.channel_selected.emit)
        self.live_carousel.browse_clicked.connect(self.browse_section_requested.emit)
        self.content_layout.addWidget(self.live_carousel)

        self.scroll_area.setWidget(self.container_widget)
        root_layout.addWidget(self.scroll_area, stretch=1)

    def set_playlist_id(self, playlist_id: Optional[int]):
        self.current_playlist_id = playlist_id
        self.refresh_view()

    def set_search_query(self, query: str):
        self.search_query = query.strip()
        self.refresh_view()

    def refresh_view(self):
        # 1. Récupérer les films récents appartenant aux catégories activées
        movies = self.db.get_recently_added(
            playlist_id=self.current_playlist_id,
            stream_type="movie",
            search_query=self.search_query if self.search_query else None,
            limit=30
        )
        self.movies_carousel.set_channels(movies)

        # 2. Récupérer les séries récentes appartenant aux catégories activées
        series = self.db.get_recently_added(
            playlist_id=self.current_playlist_id,
            stream_type="series",
            search_query=self.search_query if self.search_query else None,
            limit=30
        )
        self.series_carousel.set_channels(series)

        # 3. Récupérer la TV en direct récente appartenant aux catégories activées
        live = self.db.get_recently_added(
            playlist_id=self.current_playlist_id,
            stream_type="live",
            search_query=self.search_query if self.search_query else None,
            limit=30
        )
        self.live_carousel.set_channels(live)

    def retranslate_ui(self):
        """Met à jour les textes des carrousels de RecentlyAddedView."""
        if hasattr(self, "title_label"):
            self.title_label.setText(tr("Récemment ajoutés"))
        if hasattr(self, "movies_carousel") and hasattr(self.movies_carousel, "retranslate_ui"):
            self.movies_carousel.retranslate_ui()
        if hasattr(self, "series_carousel") and hasattr(self.series_carousel, "retranslate_ui"):
            self.series_carousel.retranslate_ui()
        if hasattr(self, "live_carousel") and hasattr(self.live_carousel, "retranslate_ui"):
            self.live_carousel.retranslate_ui()
        self.refresh_view()
