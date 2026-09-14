"""
Panneau de liste des chaînes pour la catégorie active (style IPTVnator).
Lancement immédiat des chaînes au simple clic, barre de recherche, tri et chevron de masquage des catégories.
"""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListView, QLabel, QPushButton, QMenu, QAbstractItemView,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QModelIndex, QSize
from PyQt6.QtGui import QCursor

from core.models import Channel, clean_category_display_name
from core.database import Database
from core.image_loader import ImageLoader
from ui.widgets.channel_model import ChannelListModel
from ui.widgets.channel_delegate import ChannelItemDelegate
from ui.icons import get_icon, DEFAULT_ICON_COLOR


class ChannelListPanel(QFrame):
    channel_selected = pyqtSignal(Channel)
    favorite_toggled = pyqtSignal(int, bool)
    view_epg_requested = pyqtSignal(Channel)
    toggle_categories_requested = pyqtSignal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("channelsContainer")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("#channelsContainer { background-color: #181f2d; }")
        self.setMinimumWidth(200)

        self.current_playlist_id: Optional[int] = None
        self.current_stream_type: Optional[str] = "live"
        self.favorites_only: bool = False
        self.all_channels: List[Channel] = []
        self._sort_mode = "default"  # "default", "name_asc", "name_desc"
        self.current_selected_category = "Toutes les chaînes"

        # Modèle & Délégué
        self.model = ChannelListModel(self)
        self.model.favorite_toggled.connect(self._on_fav_toggled)
        self.delegate = ChannelItemDelegate(self)

        ImageLoader.instance().image_loaded.connect(self._on_image_loaded)

        # Timer pour le debouncing de recherche
        self.search_timer = QTimer(self)
        self.search_timer.setInterval(180)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)

        self._init_ui()

    def _init_ui(self):
        channels_layout = QVBoxLayout(self)
        channels_layout.setContentsMargins(10, 12, 10, 10)
        channels_layout.setSpacing(8)

        # 1. En-tête de catégorie active (style IPTVnator)
        cat_header_row = QHBoxLayout()
        cat_header_row.setContentsMargins(4, 0, 4, 0)
        cat_header_row.setSpacing(8)

        self.cat_title_label = QLabel("Toutes les chaînes")
        self.cat_title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff;")
        cat_header_row.addWidget(self.cat_title_label, stretch=1)

        self.cat_count_badge = QLabel("0")
        self.cat_count_badge.setStyleSheet("""
            background-color: #242f44;
            color: #818cf8;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 9px;
            border: 1px solid #33415c;
        """)
        cat_header_row.addWidget(self.cat_count_badge)

        # Bouton Tri (Serveur / A-Z / Z-A)
        self.sort_az_btn = QPushButton()
        self.sort_az_btn.setIcon(get_icon("sort_by_alpha", color=DEFAULT_ICON_COLOR))
        self.sort_az_btn.setIconSize(QSize(18, 18))
        self.sort_az_btn.setFixedSize(28, 28)
        self.sort_az_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_az_btn.setToolTip("Trier les chaînes (Serveur / A-Z / Z-A)")
        self.sort_az_btn.setStyleSheet("background: transparent; border: none; border-radius: 4px;")
        self.sort_az_btn.clicked.connect(self._show_sort_menu)
        cat_header_row.addWidget(self.sort_az_btn)

        # Bouton Replier / Déplier catégories
        self.toggle_cat_btn = QPushButton()
        self.toggle_cat_btn.setIcon(get_icon("chevron_left", color=DEFAULT_ICON_COLOR))
        self.toggle_cat_btn.setIconSize(QSize(20, 20))
        self.toggle_cat_btn.setFixedSize(28, 28)
        self.toggle_cat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_cat_btn.setToolTip("Masquer / Afficher les catégories")
        self.toggle_cat_btn.setStyleSheet("background: transparent; border: none; border-radius: 4px;")
        self.toggle_cat_btn.clicked.connect(self.toggle_categories_requested.emit)
        cat_header_row.addWidget(self.toggle_cat_btn)

        channels_layout.addLayout(cat_header_row)

        # 2. Barre de recherche interne
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchBox")
        self.search_input.setPlaceholderText("Rechercher dans cette catégorie...")
        self.search_input.setClearButtonEnabled(True)
        search_icon = get_icon("search", color="#94a3b8")
        self.search_input.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(lambda: self.search_timer.start())
        channels_layout.addWidget(self.search_input)

        # 3. Vue des chaînes (QListView avec clic simple immédiat)
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.list_view.setMouseTracking(True)
        self.list_view.clicked.connect(self._on_single_clicked)
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self._show_context_menu)
        channels_layout.addWidget(self.list_view)

    def set_categories_collapsed(self, collapsed: bool):
        self.toggle_cat_btn.setIcon(get_icon("chevron_right" if collapsed else "chevron_left", color=DEFAULT_ICON_COLOR))
        self.toggle_cat_btn.setToolTip("Afficher les catégories" if collapsed else "Masquer les catégories")

    # ------------------ GESTION DES CHAÎNES & FILTRES ------------------

    def set_playlist(self, playlist_id: Optional[int], stream_type: Optional[str] = "live", favorites_only: bool = False):
        self.current_playlist_id = playlist_id
        self.current_stream_type = stream_type
        self.favorites_only = favorites_only
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.current_selected_category = ""
        self._apply_channel_filter()

    def set_category(self, category_name: str):
        self.current_selected_category = category_name
        self._apply_channel_filter()

    def set_search_query(self, query: str):
        self.search_input.blockSignals(True)
        self.search_input.setText(query)
        self.search_input.blockSignals(False)
        self._apply_channel_filter()

    def _apply_channel_filter(self):
        search_query = self.search_input.text().strip()
        is_series = (self.current_stream_type == "series")

        if is_series or self.current_stream_type in ("movie", "vod"):
            # Pour les séries et films : recherche globale sur tout le catalogue dès 3 caractères, limitée à 40
            if len(search_query) >= 3:
                group = None
                query_to_use = search_query
                limit_val = 40
                title_text = f'Recherche : "{search_query}"'
            else:
                group = self.current_selected_category if self.current_selected_category else None
                query_to_use = None
                limit_val = 50000
                title_text = self.current_selected_category or ("Séries" if is_series else "Films")
        else:
            group = self.current_selected_category if self.current_selected_category else None
            query_to_use = search_query if search_query else None
            limit_val = 50000
            title_text = self.current_selected_category or ("Favoris" if self.favorites_only else "Chaînes")

        channels = self.db.get_channels(
            playlist_id=self.current_playlist_id,
            group_title=group,
            search_query=query_to_use,
            favorites_only=self.favorites_only,
            stream_type=self.current_stream_type,
            only_enabled=True,
            order_by=self._sort_mode,
            limit=limit_val
        )

        epg_map = self.db.get_current_programs_map()

        self.all_channels = channels
        self.model.set_channels(channels, epg_map=epg_map)
        self.cat_title_label.setText(clean_category_display_name(title_text))
        if len(search_query) >= 3 and (is_series or self.current_stream_type in ("movie", "vod")):
            total_found = len(channels)
            self.cat_count_badge.setText(f"{total_found} (max 40)" if total_found >= 40 else str(total_found))
        else:
            self.cat_count_badge.setText(str(len(channels)))

    def get_channels(self) -> List[Channel]:
        return self.all_channels or self.model._channels

    def select_channel(self, channel: Channel, scroll_to_top: bool = False):
        """Sélectionne visuellement la chaîne et la fait défiler dans la vue."""
        channels = self.get_channels()
        if not channels:
            return

        target_row = -1
        for i, c in enumerate(channels):
            if (c.id and channel.id and c.id == channel.id) or c.stream_url == channel.stream_url:
                target_row = i
                break

        if target_row != -1:
            index = self.model.index(target_row, 0)
            if index.isValid():
                self.list_view.setCurrentIndex(index)
                hint = QAbstractItemView.ScrollHint.PositionAtTop if scroll_to_top else QAbstractItemView.ScrollHint.PositionAtCenter
                QTimer.singleShot(0, lambda idx=index, h=hint: self.list_view.scrollTo(idx, h))

    def _perform_search(self):
        self._apply_channel_filter()

    def _show_sort_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1f283b;
                border: 1px solid #313f5c;
                border-radius: 8px;
                padding: 4px;
                color: #f1f5f9;
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

        a_default = menu.addAction("📌 Ordre du serveur (Original)")
        a_az = menu.addAction("🔤 Nom (A → Z)")
        a_za = menu.addAction("🔤 Nom (Z → A)")

        a_default.setCheckable(True)
        a_az.setCheckable(True)
        a_za.setCheckable(True)

        a_default.setChecked(self._sort_mode == "default")
        a_az.setChecked(self._sort_mode == "name_asc")
        a_za.setChecked(self._sort_mode == "name_desc")

        a_default.triggered.connect(lambda: self._set_sort_mode("default"))
        a_az.triggered.connect(lambda: self._set_sort_mode("name_asc"))
        a_za.triggered.connect(lambda: self._set_sort_mode("name_desc"))

        menu.exec(QCursor.pos())

    def _set_sort_mode(self, mode: str):
        self._sort_mode = mode
        self._apply_channel_filter()

    # ------------------ ÉVÉNEMENTS CLIC SIMPLE (1-CLIC) ------------------

    def _on_single_clicked(self, index: QModelIndex):
        channel = self.model.get_channel(index.row())
        if channel:
            QTimer.singleShot(0, lambda idx=index: self.list_view.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtTop))
            self.channel_selected.emit(channel)

    def _on_fav_toggled(self, channel_id: int, is_fav: bool):
        self.db.set_favorite(channel_id, is_fav)
        self.favorite_toggled.emit(channel_id, is_fav)

    def _on_image_loaded(self, url: str):
        self.model.update_for_logo(url)

    def _show_context_menu(self, pos):
        index = self.list_view.indexAt(pos)
        if not index.isValid():
            return

        channel = self.model.get_channel(index.row())
        if not channel:
            return

        menu = QMenu(self)
        fav_text = "Retirer des favoris" if channel.is_favorite else "Ajouter aux favoris"
        fav_icon = get_icon("favorite_border" if channel.is_favorite else "favorite", color="#f43f5e")
        act_fav = menu.addAction(fav_icon, fav_text)
        act_fav.triggered.connect(lambda: self.model.toggle_favorite(index.row()))

        act_epg = menu.addAction(get_icon("calendar_today", color="#818cf8"), "Voir le guide TV (EPG)")
        act_epg.triggered.connect(lambda: self.view_epg_requested.emit(channel))

        menu.exec(QCursor.pos())
