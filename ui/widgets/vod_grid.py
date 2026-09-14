"""
Vue galerie continue VOD Films avec défilement fluide ("ascenseur" infini / chargement par lots),
affiches cinéma 2:3 avec coins arrondis, badges qualité/audio/note, barre d'outils et tri instantané.
"""

from typing import Optional, Set, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QGridLayout, QMenu, QFrame, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QTimer, QThread, QObject
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QCursor, QMouseEvent, QPen, QPainterPath

from core.models import Channel, parse_movie_metadata, clean_category_display_name
from core.database import Database
from core.image_loader import ImageLoader
from ui.icons import get_icon
from ui.widgets.poster_utils import draw_added_date_badge
from core.i18n import tr, I18nManager

# ==============================================================================
# FONCTIONNALITÉ EXPÉRIMENTALE : RECHERCHE PAR ACTEUR / RÉALISATEUR (OPTION 3)
# Pour désactiver ou supprimer cette fonctionnalité, passez ce drapeau à False :
EXPERIMENTAL_ARTIST_SEARCH = True
# ==============================================================================



class VODQueryWorker(QThread):
    """Worker asynchrone pour exécuter les requêtes SQLite de pagination VOD/Séries hors du thread GUI."""
    results_ready = pyqtSignal(list, int)  # (movies: List[Channel], batch_id: int)

    def __init__(
        self,
        db: Database,
        playlist_id: Optional[int],
        group_title: Optional[str],
        search_query: Optional[str],
        stream_type: str,
        only_enabled: bool,
        order_by: str,
        limit: int,
        offset: int,
        batch_id: int,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.playlist_id = playlist_id
        self.group_title = group_title
        self.search_query = search_query
        self.stream_type = stream_type
        self.only_enabled = only_enabled
        self.order_by = order_by
        self.limit = limit
        self.offset = offset
        self.batch_id = batch_id

    def run(self):
        if self.isInterruptionRequested():
            return
        try:
            movies = self.db.get_channels(
                playlist_id=self.playlist_id,
                group_title=self.group_title,
                search_query=self.search_query,
                stream_type=self.stream_type,
                only_enabled=self.only_enabled,
                order_by=self.order_by,
                limit=self.limit,
                offset=self.offset,
            )
            if not self.isInterruptionRequested():
                self.results_ready.emit(movies, self.batch_id)
        except Exception:
            pass


class PosterWidget(QWidget):
    """Widget dédié à l'affiche du film avec coins arrondis, badges et barre de progression."""
    def __init__(self, channel: Channel, is_watched: bool = False, progress_ratio: float = 0.0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.is_watched = is_watched
        self.progress_ratio = progress_ratio
        self.meta = parse_movie_metadata(channel.name, channel.rating, channel.year)
        self.pixmap: Optional[QPixmap] = None
        self.is_hovered = False
        self._is_connected_to_loader = False

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
            self._is_connected_to_loader = True
            loader.image_loaded.connect(self._on_image_loaded)
            loader.request_image(self.channel.logo_url)

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        if url == self.channel.logo_url:
            self.pixmap = pixmap
            self._disconnect_loader()
            self.update()

    def _disconnect_loader(self):
        if getattr(self, "_is_connected_to_loader", False):
            try:
                ImageLoader.instance().image_loaded.disconnect(self._on_image_loaded)
            except Exception:
                pass
            self._is_connected_to_loader = False

    def closeEvent(self, event):
        self._disconnect_loader()
        super().closeEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        event.ignore()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        event.ignore()

    def set_hovered(self, hovered: bool):
        self.is_hovered = hovered
        self.update()

    def set_progress_ratio(self, ratio: float):
        if abs(self.progress_ratio - ratio) > 0.001:
            self.progress_ratio = ratio
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
            scaled = self.pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            sx = (rect.width() - scaled.width()) // 2
            sy = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(sx, sy, scaled)
        else:
            # Fond sombre et icône placeholder si pas d'image
            painter.fillRect(rect, QColor("#1e293b"))
            icon_pix = get_icon("movie", color="#475569").pixmap(48, 48)
            painter.drawPixmap((rect.width() - 48) // 2, (rect.height() - 48) // 2, icon_pix)

        # 2. Overlay sombre et bouton Play au survol
        if self.is_hovered:
            painter.fillRect(rect, QColor(0, 0, 0, 95))
            play_pix = get_icon("play_arrow", color="#ffffff").pixmap(46, 46)
            painter.drawPixmap((rect.width() - 46) // 2, (rect.height() - 46) // 2, play_pix)

        # Fin du clip pour les badges
        painter.setClipping(False)

        # 3. Bordure de l'affiche
        painter.save()
        if self.is_hovered:
            painter.setPen(QPen(QColor("#3b82f6"), 2))
        else:
            painter.setPen(QPen(QColor("#334155"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, rect.width() - 2, rect.height() - 2, 8, 8)
        painter.restore()

        # 4. Badge supérieur droit : Note (ex: ★ 7.3)
        rating_str = self.meta.get("rating", "")
        if rating_str:
            self._draw_rating_badge(painter, rating_str)

        # 5. Pastille verte de visionnage
        if self.is_watched:
            self._draw_watched_badge(painter)

        # 6. Barre de progression rouge de reprise au bas de l'affiche
        if self.progress_ratio > 0.0:
            self._draw_progress_bar(painter, self.progress_ratio)

        # 7. Badge date d'ajout (Films et Séries)
        if self.channel and self.channel.stream_type in ("movie", "series"):
            bottom_off = 10 if self.progress_ratio > 0.0 else 6
            draw_added_date_badge(painter, self.channel.added_at, rect.width(), rect.height(), bottom_offset=bottom_off)

    def _draw_progress_bar(self, painter: QPainter, ratio: float):
        painter.save()
        rect = self.rect()
        bar_h = 4
        by = rect.height() - bar_h - 2
        bx = 4
        bw = rect.width() - 8

        # Fond sombre de la barre
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 230))
        painter.drawRoundedRect(bx, by, bw, bar_h, 2, 2)

        # Remplissage rouge vif (style cinéma / Netflix)
        fill_w = max(4, int(bw * min(1.0, max(0.02, ratio))))
        painter.setBrush(QColor("#ef4444"))
        painter.drawRoundedRect(bx, by, fill_w, bar_h, 2, 2)
        painter.restore()

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

    def _draw_watched_badge(self, painter: QPainter):
        painter.save()
        bx = 6
        by = 6

        painter.setBrush(QColor(16, 185, 129, 230))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(bx, by, 16, 16)

        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawLine(bx + 4, by + 8, bx + 7, by + 12)
        painter.drawLine(bx + 7, by + 12, bx + 12, by + 5)
        painter.restore()


class MovieCardWidget(QWidget):
    """Carte complète de film avec affiche et titre cliquable."""
    clicked = pyqtSignal(Channel)
    details_requested = pyqtSignal(Channel)
    favorite_toggled = pyqtSignal(Channel)

    CARD_WIDTH = 160
    TOTAL_HEIGHT = 285

    def __init__(self, channel: Channel, is_watched: bool = False, progress_ratio: float = 0.0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.is_watched = is_watched
        self.progress_ratio = progress_ratio

        self.setFixedSize(self.CARD_WIDTH, self.TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 1. Affiche
        self.poster_widget = PosterWidget(channel, is_watched=is_watched, progress_ratio=progress_ratio, parent=self)
        layout.addWidget(self.poster_widget)

        # 2. Titre du film
        self.title_label = QLabel(self.channel.name)
        self.title_label.setToolTip(f"{self.channel.name}\nCatégorie: {self.channel.group_title}")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setStyleSheet("""
            color: #cbd5e1;
            font-size: 11px;
            font-weight: 500;
            line-height: 1.2;
        """)
        self.title_label.setFixedHeight(34)
        layout.addWidget(self.title_label)

    def enterEvent(self, event):
        self.poster_widget.set_hovered(True)
        self.title_label.setStyleSheet("""
            color: #ffffff;
            font-size: 11px;
            font-weight: 600;
        """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.poster_widget.set_hovered(False)
        self.title_label.setStyleSheet("""
            color: #cbd5e1;
            font-size: 11px;
            font-weight: 500;
        """)
        super().leaveEvent(event)

    def set_progress_ratio(self, ratio: float):
        self.progress_ratio = ratio
        self.poster_widget.set_progress_ratio(ratio)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.details_requested.emit(self.channel)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.channel)
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)

        play_act = menu.addAction("▶  Lire le film")
        fav_text = "★  Retirer des favoris" if self.channel.is_favorite else "☆  Ajouter aux favoris"
        fav_act = menu.addAction(fav_text)
        info_act = menu.addAction("ℹ  Fiche détaillée du film")

        action = menu.exec(global_pos)
        if action == play_act:
            self.clicked.emit(self.channel)
        elif action == fav_act:
            self.favorite_toggled.emit(self.channel)
        elif action == info_act:
            self.details_requested.emit(self.channel)


class VODGridView(QWidget):
    """
    Vue galerie continue pour les films VOD avec défilement infini ("ascenseur"),
    chargement progressif par lots fluide, tri et filtres.
    """
    movie_selected = pyqtSignal(Channel)
    movie_details_requested = pyqtSignal(Channel)
    favorite_toggled = pyqtSignal(Channel)
    artist_search_requested = pyqtSignal(str, object)

    INITIAL_BATCH_SIZE = 60  # Affichage immédiat des 60 premières affiches à l'ouverture
    BATCH_SIZE = 60          # Lots chargés de manière asynchrone lors du défilement
    CHUNK_SIZE = 20          # Micro-lots insérés par tick GUI lors du défilement pour maintenir 60 FPS

    def __init__(self, db: Database, stream_type: str = "movie", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.stream_type = stream_type
        self.current_playlist_id: Optional[int] = None
        self.current_category: str = "Toutes les séries" if stream_type == "series" else "Tous les films"
        self.search_query: str = ""
        self.current_order: Optional[str] = None

        self.total_items: int = 0
        self.loaded_count: int = 0
        self.is_loading: bool = False
        self.watched_ids: Set[int] = set()
        self.progress_map: dict = {}

        self._current_batch_id: int = 0
        self._current_worker: Optional[VODQueryWorker] = None
        self._pending_cards_queue: List[Channel] = []
        self._last_col_count: Optional[int] = None

        self._search_timer = QTimer(self)
        self._search_timer.setInterval(180)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)

        self._init_ui()

        from core.i18n import I18nManager
        I18nManager.instance().language_changed.connect(lambda _: self.retranslate_ui())

    def _populate_sort_combo(self):
        curr_idx = self.sort_combo.currentIndex() if self.sort_combo.count() > 0 else 0
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        self.sort_combo.addItems([
            tr("Trier : Ordre du serveur (Original)"),
            tr("Trier : Date d'ajout (plus récents...)"),
            tr("Trier : Titre (A à Z)"),
            tr("Trier : Titre (Z à A)"),
            tr("Trier : Note (plus haute)"),
            tr("Trier : Année (plus récente)")
        ])
        if 0 <= curr_idx < self.sort_combo.count():
            self.sort_combo.setCurrentIndex(curr_idx)
        self.sort_combo.blockSignals(False)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(12)
        self.setStyleSheet("background-color: #131926;")

        # ------------------ 1. BARRE D'OUTILS SUPÉRIEURE ------------------
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: transparent;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(12)

        # 1.1 Gauche : Titre de catégorie & Compteur
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        default_cat_title = tr("TOUTES LES SÉRIES") if self.stream_type == "series" else tr("TOUS LES FILMS")
        self.category_title_label = QLabel(default_cat_title)
        self.category_title_label.setStyleSheet("color: #ffffff; font-size: 17px; font-weight: 700;")
        title_box.addWidget(self.category_title_label)

        default_count = "0 " + (tr("séries") if self.stream_type == "series" else tr("films"))
        self.items_count_label = QLabel(default_count)
        self.items_count_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
        title_box.addWidget(self.items_count_label)

        top_layout.addLayout(title_box)
        top_layout.addStretch()

        # 1.2 Droite : Tri & Bouton Refine
        right_box = QHBoxLayout()
        right_box.setSpacing(10)

        sort_icon_lbl = QLabel()
        sort_icon_lbl.setPixmap(get_icon("sort_by_alpha", color="#94a3b8").pixmap(16, 16))
        right_box.addWidget(sort_icon_lbl)

        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #e2e8f0;
                selection-background-color: #3b82f6;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        self._populate_sort_combo()
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        right_box.addWidget(self.sort_combo)

        # Bouton Refine / Filtre rapide
        self.refine_btn = QPushButton(" " + tr("Refine"))
        self.refine_btn.setIcon(get_icon("filter_list", color="#e2e8f0"))
        self.refine_btn.setIconSize(QSize(14, 14))
        self.refine_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refine_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #475569;
            }
        """)
        self.refine_btn.clicked.connect(self._on_refine_clicked)
        right_box.addWidget(self.refine_btn)

        # Bouton expérimental : Recherche par Artiste (Acteur / Réalisateur)
        if EXPERIMENTAL_ARTIST_SEARCH:
            self.artist_btn = QPushButton(" " + tr("Artiste"))
            self.artist_btn.setIcon(get_icon("person", color="#38bdf8"))
            self.artist_btn.setIconSize(QSize(14, 14))
            self.artist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.artist_btn.setToolTip(tr("Rechercher un acteur ou réalisateur (expérimental)"))
            self.artist_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #38bdf8;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 5px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #0f172a;
                    border-color: #38bdf8;
                    color: #ffffff;
                }
            """)
            self.artist_btn.clicked.connect(self._prompt_artist_search)
            right_box.addWidget(self.artist_btn)

        top_layout.addLayout(right_box)
        root_layout.addWidget(top_bar)

        # Bandeau expérimental de suggestion contextuelle lors d'une recherche (100% souris)
        if EXPERIMENTAL_ARTIST_SEARCH:
            self.artist_banner = QFrame()
            self.artist_banner.setObjectName("artistSearchBanner")
            self.artist_banner.setStyleSheet("""
                QFrame#artistSearchBanner {
                    background-color: #162238;
                    border: 1px solid #2563eb;
                    border-radius: 8px;
                }
            """)
            banner_layout = QHBoxLayout(self.artist_banner)
            banner_layout.setContentsMargins(14, 8, 14, 8)
            banner_layout.setSpacing(12)

            banner_icon = QLabel()
            banner_icon.setPixmap(get_icon("person", color="#38bdf8").pixmap(20, 20))
            banner_layout.addWidget(banner_icon)

            self.artist_banner_label = QLabel()
            self.artist_banner_label.setStyleSheet("color: #f1f5f9; font-size: 12.5px; font-weight: 500;")
            banner_layout.addWidget(self.artist_banner_label, stretch=1)

            self.artist_banner_btn = QPushButton(" Voir la filmographie")
            self.artist_banner_btn.setIcon(get_icon("chevron_right", color="#ffffff"))
            self.artist_banner_btn.setIconSize(QSize(16, 16))
            self.artist_banner_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.artist_banner_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.artist_banner_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #3b82f6;
                }
            """)
            self.artist_banner_btn.clicked.connect(self._on_banner_artist_clicked)
            banner_layout.addWidget(self.artist_banner_btn)

            self.artist_banner.hide()
            root_layout.addWidget(self.artist_banner)

        # ------------------ 2. ZONE DE DÉFILEMENT CONTINUE ("ASCENSEUR") ------------------
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #111827;
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

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 4, 0, 24)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.grid_container)

        # Détection du défilement pour le chargement progressif infini
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)

        root_layout.addWidget(self.scroll_area)

    def set_playlist_and_category(self, playlist_id: Optional[int], category_name: str = ""):
        self.current_playlist_id = playlist_id
        default_cat = "Toutes les séries" if self.stream_type == "series" else "Tous les films"
        self.current_category = category_name or default_cat

        cat_display = clean_category_display_name(self.current_category).upper()
        if cat_display in ("TOUTES LES CHAÎNES", "TOUS LES GROUPES", "TOUS LES FILMS", "TOUTES LES SÉRIES", "TOUTES LES SERIES"):
            cat_display = "TOUTES LES SÉRIES" if self.stream_type == "series" else "TOUS LES FILMS"
        self.category_title_label.setText(cat_display)

        # Maintien du tri actif lors du parcours des catégories
        order_to_index = {
            "default": 0,
            "date_desc": 1,
            "name_asc": 2,
            "name_desc": 3,
            "rating_desc": 4,
            "year_desc": 5,
        }

        saved_order = None
        if hasattr(self, "db") and self.db:
            try:
                if self.current_category:
                    saved_order = self.db.get_category_sort_order(
                        self.current_playlist_id or 0,
                        self.stream_type,
                        self.current_category,
                    )
            except Exception:
                pass
        self.current_order = saved_order if (saved_order and saved_order in order_to_index) else "default"

        target_idx = order_to_index.get(self.current_order, 0)
        self.sort_combo.blockSignals(True)
        self.sort_combo.setCurrentIndex(target_idx)
        self.sort_combo.blockSignals(False)

        self.refresh()

    def set_search_query(self, query: str):
        self._pending_query = query.strip()
        self._search_timer.start()

    def _apply_search(self):
        query = getattr(self, "_pending_query", "")
        if query == self.search_query:
            return
        self.search_query = query
        self.refresh()

    def _prompt_artist_search(self):
        """Ouvre le dialogue 100% pilotable à la souris pour rechercher un artiste avec suggestions temps réel."""
        if not EXPERIMENTAL_ARTIST_SEARCH:
            return
        from ui.dialogs.artist_filmography_dialog import ArtistSearchPromptDialog
        dlg = ArtistSearchPromptDialog(parent=self.window(), initial_text=self.search_query.strip())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            artist_name = dlg.get_artist_name()
            person_id = dlg.get_person_id()
            if artist_name:
                self.artist_search_requested.emit(artist_name, person_id)

    def _on_banner_artist_clicked(self):
        """Déclenche la recherche de l'artiste correspondant au texte recherché (100% souris)."""
        if not EXPERIMENTAL_ARTIST_SEARCH:
            return
        # Ouvre la boîte de dialogue pré-remplie pour afficher les suggestions et choisir facilement
        self._prompt_artist_search()

    def _get_column_count(self) -> int:
        """Calcule le nombre de colonnes de façon stable à partir de la largeur utile."""
        vw = self.scroll_area.viewport().width() if hasattr(self, "scroll_area") else 0
        if vw > 100:
            available_w = vw
        else:
            win = self.window()
            if win and win.width() > 400:
                # Largeur estimée : largeur de la fenêtre moins panneau latéral (~64px) et catégories (~260px)
                available_w = max(400, win.width() - 340)
            else:
                available_w = max(400, self.width())
        return max(2, available_w // (MovieCardWidget.CARD_WIDTH + 14))

    def _create_card(self, movie: Channel) -> MovieCardWidget:
        """Instancie et configure une carte de film ou série."""
        is_w = bool(movie.id and movie.id in self.watched_ids)
        prog_ratio = 0.0
        if movie.id and movie.id in self.progress_map:
            pos, dur = self.progress_map[movie.id]
            prog_ratio = (pos / dur) if dur > 0 else 0.0
        elif movie.stream_url and movie.stream_url in self.progress_map:
            pos, dur = self.progress_map[movie.stream_url]
            prog_ratio = (pos / dur) if dur > 0 else 0.0

        prog_ratio = min(0.95, max(0.0, prog_ratio))
        card = MovieCardWidget(movie, is_watched=is_w, progress_ratio=prog_ratio, parent=self.grid_container)
        card.clicked.connect(self.movie_selected.emit)
        card.details_requested.connect(self.movie_details_requested.emit)
        card.favorite_toggled.connect(self._on_favorite_toggled)
        return card

    def refresh(self):
        """Réinitialise la galerie et charge les films ou séries de manière asynchrone et fluide."""
        self._is_stopped = False
        # 1. Annulation de toute requête en cours et invalidation des lots précédents
        self._current_batch_id += 1
        self._pending_cards_queue.clear()
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.requestInterruption()
        self.is_loading = False

        # 2. Nettoyage de la file d'attente d'images
        ImageLoader.instance().clear_queue()
        self.watched_ids = self.db.get_watched_channel_ids()
        self.progress_map = self.db.get_all_playback_progress_map()

        is_global_search = len(self.search_query) >= 3
        item_singular = tr("série") if self.stream_type == "series" else tr("film")
        item_plural = tr("séries") if self.stream_type == "series" else tr("films")

        # Gestion du bandeau d'artiste contextuel (100% souris)
        if EXPERIMENTAL_ARTIST_SEARCH and hasattr(self, "artist_banner"):
            if is_global_search:
                q_disp = self.search_query.strip()
                self.artist_banner_label.setText(
                    f'Rechercher "<b>{q_disp}</b>" en tant qu\'<b>acteur ou réalisateur</b>'
                )
                self.artist_banner.show()
            else:
                self.artist_banner.hide()

        all_groups = (
            "Toutes les chaînes", "Tous les groupes", "Tous les films", "Toutes les séries", "Toutes les series",
            "All channels", "All groups", "All movies", "All series"
        )
        grp = None if is_global_search else (self.current_category if self.current_category not in all_groups else None)
        query_to_use = self.search_query if is_global_search else None

        if is_global_search:
            # Recherche globale sur TOUT le catalogue, max 40
            self.total_items = self.db.get_channel_count(
                playlist_id=self.current_playlist_id,
                group_title=None,
                search_query=query_to_use,
                stream_type=self.stream_type,
                only_enabled=True
            )
            self.category_title_label.setText(f'{tr("RECHERCHE :")} "{self.search_query.upper()}"')
            if self.total_items > 40:
                tot_str = f"{self.total_items:,}".replace(",", " ")
                self.items_count_label.setText(tr("40 premiers résultats sur {total}", total=tot_str))
            else:
                self.items_count_label.setText(f"{self.total_items} {item_singular if self.total_items <= 1 else item_plural}")
        else:
            # Catégorie normale sélectionnée
            grp = self.current_category if self.current_category not in all_groups else None
            self.total_items = self.db.get_channel_count(
                playlist_id=self.current_playlist_id,
                group_title=grp,
                search_query=None,
                stream_type=self.stream_type,
                only_enabled=True
            )
            if not self.current_category or self.current_category in all_groups:
                cat_display = tr("TOUTES LES SÉRIES") if self.stream_type == "series" else tr("TOUS LES FILMS")
            else:
                cat_display = clean_category_display_name(self.current_category).upper()
            self.category_title_label.setText(cat_display)
            formatted_total = f"{self.total_items:,}".replace(",", " ")
            is_singular = (self.total_items <= 1) if I18nManager.instance().current_language == "fr" else (self.total_items == 1)
            count_word = item_singular if is_singular else item_plural
            self.items_count_label.setText(f"{formatted_total} {count_word}")

        # Nettoyage ultra-rapide de la grille sans saccade
        self.grid_container.setUpdatesEnabled(False)
        try:
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        finally:
            self.grid_container.setUpdatesEnabled(True)

        self.loaded_count = 0
        self.scroll_area.verticalScrollBar().setValue(0)

        if self.total_items == 0:
            if is_global_search and EXPERIMENTAL_ARTIST_SEARCH:
                empty_box = QWidget()
                empty_vbox = QVBoxLayout(empty_box)
                empty_vbox.setSpacing(14)
                empty_vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

                msg_lbl = QLabel(f'Aucun titre de {item_singular} ne correspond à "{self.search_query}".')
                msg_lbl.setStyleSheet("color: #94a3b8; font-size: 14px; font-weight: 500;")
                msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_vbox.addWidget(msg_lbl)

                btn_find_artist = QPushButton(f' Rechercher "{self.search_query.strip()}" parmi les artistes')
                btn_find_artist.setIcon(get_icon("person", color="#ffffff"))
                btn_find_artist.setIconSize(QSize(16, 16))
                btn_find_artist.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_find_artist.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        color: #ffffff;
                        border: none;
                        border-radius: 8px;
                        padding: 10px 20px;
                        font-size: 13px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #3b82f6;
                    }
                """)
                btn_find_artist.clicked.connect(self._on_banner_artist_clicked)
                empty_vbox.addWidget(btn_find_artist, alignment=Qt.AlignmentFlag.AlignCenter)

                self.grid_layout.addWidget(empty_box, 0, 0, 1, 4, Qt.AlignmentFlag.AlignCenter)
            else:
                msg = f'Aucune {item_singular} trouvée pour "{self.search_query}".' if is_global_search else f"Aucune {item_singular} trouvée dans cette catégorie."
                empty_lbl = QLabel(msg)
                empty_lbl.setStyleSheet("color: #64748b; font-size: 14px; font-weight: 500; margin-top: 40px;")
                empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid_layout.addWidget(empty_lbl, 0, 0, 1, 4, Qt.AlignmentFlag.AlignCenter)
            return

        # Chargement et affichage IMMÉDIAT des premières affiches (synchrone SQLite ultra-rapide)
        max_loadable = 40 if is_global_search else self.total_items
        first_limit = min(self.INITIAL_BATCH_SIZE, max_loadable)
        first_movies = []
        if first_limit > 0:
            try:
                first_movies = self.db.get_channels(
                    playlist_id=self.current_playlist_id,
                    group_title=grp,
                    search_query=query_to_use,
                    stream_type=self.stream_type,
                    only_enabled=True,
                    order_by=self.current_order,
                    limit=first_limit,
                    offset=0,
                )
            except Exception:
                first_movies = []

        if first_movies:
            col_count = self._get_column_count()
            self._last_col_count = col_count
            self.grid_container.setUpdatesEnabled(False)
            try:
                for movie in first_movies:
                    card = self._create_card(movie)
                    global_idx = self.loaded_count
                    row = global_idx // col_count
                    col = global_idx % col_count
                    self.grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                    self.loaded_count += 1
            finally:
                self.grid_container.setUpdatesEnabled(True)

        # Préparation éventuelle pour les écrans sans barre de défilement initiale
        self._check_prefetch()

    def _load_next_batch(self):
        """Lance une requête asynchrone en arrière-plan sans bloquer le thread GUI."""
        is_global_search = len(self.search_query) >= 3
        max_loadable = 40 if is_global_search else self.total_items
        offset = self.loaded_count + len(self._pending_cards_queue)

        if self.is_loading or offset >= max_loadable:
            return

        self.is_loading = True
        all_groups = ("Toutes les chaînes", "Tous les groupes", "Tous les films", "Toutes les séries", "Toutes les series")
        grp = None if is_global_search else (self.current_category if self.current_category not in all_groups else None)
        query_to_use = self.search_query if is_global_search else None
        batch_limit = min(self.BATCH_SIZE, max_loadable - offset)

        worker = VODQueryWorker(
            db=self.db,
            playlist_id=self.current_playlist_id,
            group_title=grp,
            search_query=query_to_use,
            stream_type=self.stream_type,
            only_enabled=True,
            order_by=self.current_order,
            limit=batch_limit,
            offset=offset,
            batch_id=self._current_batch_id,
            parent=self,
        )
        worker.results_ready.connect(self._on_worker_results)
        worker.finished.connect(self._on_worker_finished)
        self._current_worker = worker
        worker.start()

    def _on_worker_results(self, movies: list, batch_id: int):
        if batch_id != self._current_batch_id:
            return

        if not movies:
            self.is_loading = False
            return

        self._pending_cards_queue.extend(movies)
        self._insert_next_card_chunk()

    def _on_worker_finished(self):
        if self.sender() == self._current_worker:
            self._current_worker = None

    def _insert_next_card_chunk(self):
        """Insère un micro-lot de cartes en rendant immédiatement la main au thread GUI lors du défilement."""
        if getattr(self, "_is_stopped", False) or not self._pending_cards_queue:
            self.is_loading = False
            return

        self.grid_container.setUpdatesEnabled(False)
        try:
            col_count = self._get_column_count()
            count_to_insert = min(self.CHUNK_SIZE, len(self._pending_cards_queue))

            for _ in range(count_to_insert):
                movie = self._pending_cards_queue.pop(0)
                card = self._create_card(movie)
                global_idx = self.loaded_count
                row = global_idx // col_count
                col = global_idx % col_count
                self.grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                self.loaded_count += 1
        finally:
            self.grid_container.setUpdatesEnabled(True)

        if self._pending_cards_queue:
            QTimer.singleShot(0, self._insert_next_card_chunk)
        else:
            self.is_loading = False
            self._check_prefetch()

    def update_all_progress_bars(self):
        """Met à jour instantanément les barres de progression de toutes les cartes affichées."""
        self.progress_map = self.db.get_all_playback_progress_map()
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, MovieCardWidget) and widget.channel:
                ch = widget.channel
                ratio = 0.0
                if ch.id and ch.id in self.progress_map:
                    pos, dur = self.progress_map[ch.id]
                    ratio = (pos / dur) if dur > 0 else 0.0
                elif ch.stream_url and ch.stream_url in self.progress_map:
                    pos, dur = self.progress_map[ch.stream_url]
                    ratio = (pos / dur) if dur > 0 else 0.0
                ratio = min(0.95, max(0.0, ratio))
                widget.set_progress_ratio(ratio)

    def _check_prefetch(self):
        """Vérifie si un pré-chargement asynchrone du lot suivant doit être anticipé lors du défilement."""
        is_global_search = len(self.search_query) >= 3
        max_loadable = 40 if is_global_search else self.total_items
        total_in_flight = self.loaded_count + len(self._pending_cards_queue)
        if total_in_flight >= max_loadable:
            return

        if self.is_loading:
            return

        max_scroll = self.scroll_area.verticalScrollBar().maximum()
        curr_scroll = self.scroll_area.verticalScrollBar().value()
        distance_to_bottom = max_scroll - curr_scroll

        # On précharge la suite si la marge avant le bas est inférieure à 1500px,
        # ou dès l'ouverture si le nombre total d'éléments dépasse ce qui est déjà chargé.
        if (max_scroll == 0) or distance_to_bottom <= 1500:
            self._load_next_batch()

    def _on_scroll(self, value: int):
        """Détecte l'approche du bas de la liste pour charger le lot suivant automatiquement."""
        self._check_prefetch()

    def _on_favorite_toggled(self, channel: Channel):
        new_fav = not channel.is_favorite
        channel.is_favorite = new_fav
        if channel.id:
            self.db.toggle_favorite(channel.id, new_fav)
        self.favorite_toggled.emit(channel)

    def _on_sort_changed(self, index: int):
        sort_map = {
            0: "default",
            1: "date_desc",
            2: "name_asc",
            3: "name_desc",
            4: "rating_desc",
            5: "year_desc"
        }
        self.current_order = sort_map.get(index, "default")
        if hasattr(self, "db") and self.db and not self.search_query:
            try:
                # Mémorisation globale pour ce type de média (films ou séries)
                self.db.set_category_sort_order(
                    self.current_playlist_id or 0,
                    self.stream_type,
                    "__global__",
                    self.current_order
                )
                if self.current_category:
                    self.db.set_category_sort_order(
                        self.current_playlist_id or 0,
                        self.stream_type,
                        self.current_category,
                        self.current_order
                    )
            except Exception:
                pass
        self.refresh()

    def _on_refine_clicked(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)

        all_act = menu.addAction("Tous les films")
        act_4k = menu.addAction("4K / UHD uniquement")
        act_multi = menu.addAction("MULTI / VFF uniquement")
        act_fav = menu.addAction("Favoris uniquement")

        action = menu.exec(QCursor.pos())
        if action == act_4k:
            self.set_search_query("4K")
        elif action == act_multi:
            self.set_search_query("MULTI")
        elif action == act_fav:
            self.set_search_query("")
            self.refresh()
        elif action == all_act:
            self.set_search_query("")

    def stop_workers(self):
        """Arrête proprement les workers asynchrones."""
        self._is_stopped = True
        self._current_batch_id += 1
        self._pending_cards_queue.clear()
        worker = getattr(self, "_current_worker", None)
        if worker and worker.isRunning():
            worker.requestInterruption()
            worker.wait(2000)
        self._current_worker = None

    def closeEvent(self, event):
        self.stop_workers()
        super().closeEvent(event)

    def __del__(self):
        try:
            self.stop_workers()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._reorganize_grid()
        QTimer.singleShot(50, self._reorganize_grid)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reorganize_grid()

    def _reorganize_grid(self):
        """Réorganise réactivement les colonnes pour exploiter toute la largeur utile de l'écran."""
        if not self.isVisible():
            return
        col_count = self._get_column_count()

        if getattr(self, "_last_col_count", None) == col_count:
            return
        self._last_col_count = col_count

        widgets = []
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if w and isinstance(w, MovieCardWidget):
                widgets.append(w)

        if widgets:
            self.grid_container.setUpdatesEnabled(False)
            try:
                for w in widgets:
                    self.grid_layout.removeWidget(w)
                for i, w in enumerate(widgets):
                    row = i // col_count
                    col = i % col_count
                    self.grid_layout.addWidget(w, row, col, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            finally:
                self.grid_container.setUpdatesEnabled(True)

    def retranslate_ui(self, *args):
        """Met à jour les libellés de la barre d'outils, du combo de tri et du bouton artiste."""
        item_singular = tr("série") if self.stream_type == "series" else tr("film")
        item_plural = tr("séries") if self.stream_type == "series" else tr("films")

        all_groups = (
            "Toutes les chaînes", "Tous les groupes", "Tous les films", "Toutes les séries", "Toutes les series",
            "All channels", "All groups", "All movies", "All series"
        )
        if not self.current_category or self.current_category in all_groups:
            self.category_title_label.setText(tr("TOUTES LES SÉRIES") if self.stream_type == "series" else tr("TOUS LES FILMS"))
        else:
            self.category_title_label.setText(clean_category_display_name(self.current_category).upper())

        formatted_total = f"{self.total_items:,}".replace(",", " ")
        is_singular = (self.total_items <= 1) if I18nManager.instance().current_language == "fr" else (self.total_items == 1)
        count_word = item_singular if is_singular else item_plural
        self.items_count_label.setText(f"{formatted_total} {count_word}")

        self._populate_sort_combo()

        if hasattr(self, "refine_btn"):
            self.refine_btn.setText(" " + tr("Refine"))
        if hasattr(self, "artist_btn"):
            self.artist_btn.setText(" " + tr("Artiste"))
            self.artist_btn.setToolTip(tr("Rechercher un acteur ou réalisateur (expérimental)"))

