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
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QModelIndex, QSize, QEvent, QPoint
from PyQt6.QtGui import QCursor

from core.models import Channel, clean_category_display_name
from core.database import Database
from core.image_loader import ImageLoader
from ui.widgets.channel_model import ChannelListModel
from ui.widgets.channel_delegate import ChannelItemDelegate
from ui.icons import get_icon, DEFAULT_ICON_COLOR
from core.i18n import tr, I18nManager
from ui.dialogs.themed_input_dialog import ThemedInputDialog


class ChannelListPanel(QFrame):
    channel_selected = pyqtSignal(Channel)
    favorite_toggled = pyqtSignal(int, bool)
    view_epg_requested = pyqtSignal(Channel)
    toggle_categories_requested = pyqtSignal()
    custom_lists_changed = pyqtSignal()

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
        self.current_custom_list_id: Optional[int] = None
        self.current_custom_list_name: Optional[str] = None

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
        I18nManager.instance().language_changed.connect(lambda _: self.retranslate_ui())

    def _init_ui(self):
        channels_layout = QVBoxLayout(self)
        channels_layout.setContentsMargins(10, 10, 10, 10)
        channels_layout.setSpacing(8)

        # 1. En-tête : Titre de la catégorie courante & Contrôles
        cat_header_row = QHBoxLayout()
        cat_header_row.setSpacing(6)

        self.cat_title_label = QLabel(tr("Toutes les catégories"))
        self.cat_title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
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

        # Bouton Tri A-Z
        self.sort_az_btn = QPushButton()
        self.sort_az_btn.setIcon(get_icon("sort_by_alpha", color=DEFAULT_ICON_COLOR))
        self.sort_az_btn.setIconSize(QSize(16, 16))
        self.sort_az_btn.setFixedSize(28, 28)
        self.sort_az_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_az_btn.setToolTip(tr("Trier par :"))
        self.sort_az_btn.setStyleSheet("background: transparent; border: none; border-radius: 4px;")
        self.sort_az_btn.clicked.connect(self._show_sort_menu)
        cat_header_row.addWidget(self.sort_az_btn)

        # Chevron pour replier/afficher le panneau des catégories
        self.toggle_cat_btn = QPushButton()
        self.toggle_cat_btn.setIcon(get_icon("chevron_left", color=DEFAULT_ICON_COLOR))
        self.toggle_cat_btn.setIconSize(QSize(20, 20))
        self.toggle_cat_btn.setFixedSize(28, 28)
        self.toggle_cat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_cat_btn.setToolTip(tr("Masquer / Afficher les catégories"))
        self.toggle_cat_btn.setStyleSheet("background: transparent; border: none; border-radius: 4px;")
        self.toggle_cat_btn.clicked.connect(self.toggle_categories_requested.emit)
        cat_header_row.addWidget(self.toggle_cat_btn)

        channels_layout.addLayout(cat_header_row)

        # 2. Barre de recherche interne
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchBox")
        self.search_input.setPlaceholderText(tr("Rechercher dans cette catégorie..."))
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
        self.list_view.installEventFilter(self)
        channels_layout.addWidget(self.list_view)

    def set_categories_collapsed(self, collapsed: bool):
        self.toggle_cat_btn.setIcon(get_icon("chevron_right" if collapsed else "chevron_left", color=DEFAULT_ICON_COLOR))
        self.toggle_cat_btn.setToolTip(tr("Afficher les catégories") if collapsed else tr("Masquer les catégories"))

    # ------------------ GESTION DES CHAÎNES & FILTRES ------------------

    def set_playlist(self, playlist_id: Optional[int], stream_type: Optional[str] = "live", favorites_only: bool = False):
        self.current_playlist_id = playlist_id
        self.current_stream_type = stream_type
        self.favorites_only = favorites_only
        self.current_custom_list_id = None
        self.current_custom_list_name = None
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.current_selected_category = ""
        self._apply_channel_filter()

    def set_category(self, category_name: str):
        self.current_custom_list_id = None
        self.current_custom_list_name = None
        self.current_selected_category = category_name
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self._apply_channel_filter()
        self.list_view.scrollToTop()

    def set_custom_list(self, list_id: int, list_name: str):
        """Affiche les chaînes appartenant à une liste de chaînes personnalisée (ex: Salon HD, Van SD)."""
        self.current_custom_list_id = list_id
        self.current_custom_list_name = list_name
        self.current_selected_category = list_name
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self._apply_channel_filter()
        self.list_view.scrollToTop()

    def set_search_query(self, query: str):
        self.search_input.blockSignals(True)
        self.search_input.setText(query)
        self.search_input.blockSignals(False)
        self._apply_channel_filter()

    def _apply_channel_filter(self):
        search_query = self.search_input.text().strip()
        is_series = (self.current_stream_type == "series")

        if self.current_custom_list_id is not None:
            # Affichage d'une liste de chaînes personnalisée
            channels = self.db.get_channels_for_custom_list(
                list_id=self.current_custom_list_id,
                playlist_id=self.current_playlist_id,
                search_query=search_query if search_query else None,
                order_by=self._sort_mode,
                limit=50000
            )
            title_text = f"📋 {self.current_custom_list_name}"
        elif is_series or self.current_stream_type in ("movie", "vod"):
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
                self.list_view.scrollTo(index, hint)

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

        a_default = menu.addAction("📌 " + tr("Ordre original"))
        a_az = menu.addAction("🔤 " + tr("Nom (A-Z)"))
        a_za = menu.addAction("🔤 " + tr("Nom (Z-A)"))

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
            self.list_view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtTop)
            self.channel_selected.emit(channel)

    def _on_fav_toggled(self, channel_id: int, is_fav: bool):
        self.db.set_favorite(channel_id, is_fav)
        self.favorite_toggled.emit(channel_id, is_fav)

    def _on_image_loaded(self, url: str):
        self.model.update_for_logo(url)

    def eventFilter(self, watched, event):
        if watched == self.list_view and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Menu, Qt.Key.Key_M, Qt.Key.Key_Context1):
                idx = self.list_view.currentIndex()
                if idx.isValid():
                    rect = self.list_view.visualRect(idx)
                    self._show_context_menu_at_index(idx, rect.center())
                    return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Menu, Qt.Key.Key_M, Qt.Key.Key_Context1):
            idx = self.list_view.currentIndex()
            if idx.isValid():
                rect = self.list_view.visualRect(idx)
                self._show_context_menu_at_index(idx, rect.center())
                event.accept()
                return
        super().keyPressEvent(event)

    def _show_context_menu(self, pos):
        index = self.list_view.indexAt(pos)
        if not index.isValid():
            return
        self._show_context_menu_at_index(index, pos)

    def _show_context_menu_at_index(self, index: QModelIndex, pos: QPoint):
        channel = self.model.get_channel(index.row())
        if not channel:
            return

        menu = QMenu(self)

        # Si on est dans une liste personnalisée : option directe pour retirer
        if self.current_custom_list_id is not None:
            act_rem = menu.addAction(
                get_icon("delete", color="#f87171"),
                f"{tr('Retirer de')} \"{self.current_custom_list_name}\""
            )
            act_rem.triggered.connect(lambda: self._remove_channel_from_current_custom_list(channel))
            menu.addSeparator()

        # Sous-menu des listes personnalisées
        custom_menu = menu.addMenu(get_icon("playlist_play", color="#38bdf8"), tr("Listes personnalisées"))
        custom_lists = self.db.get_custom_channel_lists()
        channel_list_ids = self.db.get_channel_custom_list_ids(channel)

        for cl in custom_lists:
            act_l = custom_menu.addAction(cl["name"])
            act_l.setCheckable(True)
            is_in = (cl["id"] in channel_list_ids)
            act_l.setChecked(is_in)
            act_l.triggered.connect(lambda checked, lid=cl["id"]: self._toggle_channel_in_custom_list(lid, channel, checked))

        if custom_lists:
            custom_menu.addSeparator()

        act_new_list = custom_menu.addAction(get_icon("add", color="#38bdf8"), tr("➕ Nouvelle liste..."))
        act_new_list.triggered.connect(lambda: self._create_custom_list_with_channel(channel))

        menu.addSeparator()

        fav_text = tr("Retirer des favoris") if channel.is_favorite else tr("Ajouter aux favoris")
        fav_icon = get_icon("favorite_border" if channel.is_favorite else "favorite", color="#f43f5e")
        act_fav = menu.addAction(fav_icon, fav_text)
        act_fav.triggered.connect(lambda: self.model.toggle_favorite(index.row()))

        act_epg = menu.addAction(get_icon("calendar_today", color="#818cf8"), tr("Guide des programmes (EPG)"))
        act_epg.triggered.connect(lambda: self.view_epg_requested.emit(channel))

        global_pos = self.list_view.viewport().mapToGlobal(pos)
        menu.exec(global_pos)

    def _remove_channel_from_current_custom_list(self, channel: Channel):
        if self.current_custom_list_id is not None:
            self.db.remove_channel_from_custom_list(self.current_custom_list_id, channel)
            self._apply_channel_filter()
            self.custom_lists_changed.emit()

    def _toggle_channel_in_custom_list(self, list_id: int, channel: Channel, checked: bool):
        if checked:
            self.db.add_channel_to_custom_list(list_id, channel)
        else:
            self.db.remove_channel_from_custom_list(list_id, channel)
        if self.current_custom_list_id == list_id:
            self._apply_channel_filter()
        self.custom_lists_changed.emit()

    def _create_custom_list_with_channel(self, channel: Channel):
        name, ok = ThemedInputDialog.get_text(
            self,
            title=tr("Nouvelle liste personnalisée"),
            label=tr("Nom de la liste (ex: Salon HD, Van SD) :"),
            placeholder=tr("ex: Salon HD"),
            icon_name="playlist_add"
        )
        if ok and name and name.strip():
            list_id = self.db.create_custom_channel_list(name.strip())
            self.db.add_channel_to_custom_list(list_id, channel)
            self.custom_lists_changed.emit()

    def retranslate_ui(self, *args):
        """Met à jour les infobulles, placeholders et titres de ChannelListPanel."""
        if hasattr(self, "sort_az_btn"):
            self.sort_az_btn.setToolTip(tr("Trier par :"))
        if hasattr(self, "search_input"):
            self.search_input.setPlaceholderText(tr("Rechercher dans cette catégorie..."))
        if hasattr(self, "cat_title_label"):
            if self.current_selected_category in ("Toutes les chaînes", "All channels", ""):
                self.cat_title_label.setText(tr("Toutes les chaînes"))

