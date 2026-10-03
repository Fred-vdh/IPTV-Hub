"""
Boîte de dialogue moderne de gestion et de filtrage hiérarchique des catégories et des chaînes IPTV.
Intègre le filtrage de visibilité des catégories et la gestion complète des listes personnalisées (ex: Salon HD, Van SD),
entièrement navigable à la souris et à la télécommande Android TV, reprenant fidèlement le thème Slate Blue-Grey de l'application.
"""

from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTreeWidget, QTreeWidgetItem, QWidget, QTabWidget,
    QComboBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from core.database import Database
from core.models import Channel, clean_category_display_name
from core.image_loader import ImageLoader
from ui.icons import get_icon, get_pixmap
from core.i18n import tr
from ui.dialogs.themed_input_dialog import ThemedInputDialog


def _get_ui_icons():
    from core.database import get_cache_dir
    cache_dir = get_cache_dir()
    right_svg = cache_dir / "chevron_right.svg"
    down_svg = cache_dir / "chevron_down.svg"
    check_svg = cache_dir / "check_white.svg"
    if not right_svg.exists():
        right_svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>',
            encoding="utf-8"
        )
    if not down_svg.exists():
        down_svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>',
            encoding="utf-8"
        )
    if not check_svg.exists():
        check_svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
            encoding="utf-8"
        )
    return right_svg.as_posix(), down_svg.as_posix(), check_svg.as_posix()


class KeyboardNavTreeWidget(QTreeWidget):
    """
    QTreeWidget optimisé pour la navigation à la télécommande (Android TV) et au clavier.
    Appuyer sur Entrée, Retour ou Espace bascule immédiatement l'état de la case à cocher.
    """
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            item = self.currentItem()
            if item and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                curr = item.checkState(0)
                new_state = Qt.CheckState.Unchecked if curr == Qt.CheckState.Checked else Qt.CheckState.Checked
                item.setCheckState(0, new_state)
                event.accept()
                return
        super().keyPressEvent(event)


class ManageCategoriesDialog(QDialog):
    categories_updated = pyqtSignal()

    def __init__(
        self,
        db: Database,
        playlist_id: Optional[int] = None,
        stream_type: Optional[str] = "live",
        parent: Optional[QWidget] = None,
        initial_tab: int = 0,
        initial_custom_list_id: Optional[int] = None
    ):
        super().__init__(parent)
        self.db = db
        self.playlist_id = playlist_id
        self.stream_type = stream_type
        self.has_custom_lists = (self.stream_type == "live")
        self.initial_tab = initial_tab if self.has_custom_lists else 0
        self.initial_custom_list_id = initial_custom_list_id if self.has_custom_lists else None

        if self.has_custom_lists:
            self.setWindowTitle(tr("Gestion des catégories & listes"))
        else:
            self.setWindowTitle(tr("Gérer et filtrer les catégories"))
        self.resize(740, 750)
        self.setMinimumSize(580, 520)
        self.setModal(True)
        self.setObjectName("manageCategoriesDialog")

        chevron_right_path, chevron_down_path, check_white_path = _get_ui_icons()

        # Palette Slate Blue-Grey cohérente avec l'application (pas de fond noir pur)
        self.setStyleSheet(f"""
            QDialog#manageCategoriesDialog {{
                background-color: #1b2232;
                border: 1px solid #33415c;
                border-radius: 12px;
            }}
            QTabWidget::pane {{
                border: 1px solid #33415c;
                background-color: #1e283d;
                border-radius: 10px;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: #222b3d;
                color: #94a3b8;
                padding: 9px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 13px;
                border: 1px solid #33415c;
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: #2c3952;
                color: #38bdf8;
                border-bottom: 2px solid #38bdf8;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #28354d;
                color: #e2e8f0;
            }}
            QTreeWidget {{
                background-color: #1e283d;
                border: 1px solid #33415c;
                border-radius: 8px;
                padding: 6px;
                color: #f1f5f9;
                font-size: 13px;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 4px 6px;
                border-radius: 6px;
                margin: 1px 0px;
            }}
            QTreeWidget::item:hover {{
                background-color: #28354d;
            }}
            QTreeWidget::item:selected {{
                background-color: #33466a;
                color: #ffffff;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: url("{chevron_right_path}");
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: url("{chevron_down_path}");
            }}
            QTreeWidget::indicator,
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1.5px solid #475569;
                border-radius: 4px;
                background-color: #222b3d;
            }}
            QTreeWidget::indicator:hover,
            QCheckBox::indicator:hover {{
                border-color: #38bdf8;
            }}
            QTreeWidget::indicator:checked,
            QCheckBox::indicator:checked {{
                background-color: #3b82f6;
                border-color: #3b82f6;
                image: url("{check_white_path}");
            }}
            QComboBox {{
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 7px;
                padding: 6px 12px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
            }}
            QComboBox:focus {{
                border: 1px solid #38bdf8;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 8px;
                selection-background-color: #2c3952;
                selection-color: #ffffff;
                color: #f1f5f9;
                padding: 4px;
                outline: none;
            }}
        """)

        self._channels_by_category: Dict[str, List[Channel]] = {}
        self._block_signals = False
        self._block_custom_signals = False
        self._custom_lists_modified = False

        self._init_ui()
        self._load_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        # Onglets principaux
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        # Tab 1: Filtrer les catégories (visibilité)
        tab_filter = QWidget()
        self._init_filter_tab(tab_filter)
        self.tabs.addTab(tab_filter, get_icon("filter_list", color="#38bdf8"), tr("Filtrer les catégories"))

        # Tab 2: Listes personnalisées (uniquement pour les chaînes en direct)
        if self.has_custom_lists:
            tab_custom = QWidget()
            self._init_custom_lists_tab(tab_custom)
            self.tabs.addTab(tab_custom, get_icon("playlist_play", color="#38bdf8"), tr("Listes personnalisées"))

            if 0 <= self.initial_tab < self.tabs.count():
                self.tabs.setCurrentIndex(self.initial_tab)
        else:
            self.tabs.tabBar().hide()

        # Barre inférieure : Boutons Fermer & Enregistrer
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        bottom_row.addStretch()

        self.close_btn = QPushButton(tr("Fermer"))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 8px;
                padding: 8px 22px;
                color: #e2e8f0;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2e3c56;
                border-color: #475569;
            }
        """)
        self.close_btn.clicked.connect(self._on_close_clicked)
        bottom_row.addWidget(self.close_btn)

        self.save_btn = QPushButton(tr("Enregistrer"))
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 8px;
                padding: 8px 26px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.save_btn.clicked.connect(self._save_and_accept)
        bottom_row.addWidget(self.save_btn)

        main_layout.addLayout(bottom_row)

    def _init_filter_tab(self, parent_widget: QWidget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # En-tête : Titre + Compteur
        header_box = QVBoxLayout()
        header_box.setSpacing(3)

        title_label = QLabel(tr("Activer ou masquer des catégories"))
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        header_box.addWidget(title_label)

        self.counter_label = QLabel(tr("Sélectionnées: 0 / 0 (0 / 0 groupes)"))
        self.counter_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")
        header_box.addWidget(self.counter_label)

        layout.addLayout(header_box)

        # Actions Tout sélectionner / Tout désélectionner
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.select_all_btn = QPushButton(" " + tr("Tout sélectionner"))
        self.select_all_btn.setIcon(get_icon("check_circle", color="#818cf8"))
        self.select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 7px;
                padding: 6px 14px;
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2e3c56;
                border-color: #818cf8;
            }
        """)
        self.select_all_btn.clicked.connect(self._select_all)
        actions_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton(" " + tr("Tout désélectionner"))
        self.deselect_all_btn.setIcon(get_icon("crop_square", color="#94a3b8"))
        self.deselect_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 7px;
                padding: 6px 14px;
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2e3c56;
                border-color: #94a3b8;
            }
        """)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        actions_row.addWidget(self.deselect_all_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        # Recherche
        self.search_edit = QLineEdit()
        if self.stream_type in ("movie", "vod", "series"):
            self.search_edit.setPlaceholderText(tr("Rechercher des catégories..."))
        else:
            self.search_edit.setPlaceholderText(tr("Rechercher des catégories ou des chaînes..."))
        self.search_edit.setClearButtonEnabled(True)
        search_icon = get_icon("search", color="#94a3b8")
        self.search_edit.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 8px;
                padding: 7px 10px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background-color: #273349;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_tree)
        layout.addWidget(self.search_edit)

        # Arbre des catégories
        self.tree_widget = KeyboardNavTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        if self.stream_type in ("movie", "vod", "series"):
            self.tree_widget.setRootIsDecorated(False)
            self.tree_widget.setIndentation(8)
        else:
            self.tree_widget.setRootIsDecorated(True)
            self.tree_widget.setIndentation(22)
        self.tree_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree_widget, stretch=1)

    def _init_custom_lists_tab(self, parent_widget: QWidget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Barre supérieure : Sélecteur de liste + Boutons d'action
        list_ctrl_row = QHBoxLayout()
        list_ctrl_row.setSpacing(8)

        lbl_active = QLabel(tr("Liste active :"))
        lbl_active.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600;")
        list_ctrl_row.addWidget(lbl_active)

        self.custom_list_combo = QComboBox()
        self.custom_list_combo.setMinimumWidth(220)
        self.custom_list_combo.currentIndexChanged.connect(self._on_custom_list_selected)
        list_ctrl_row.addWidget(self.custom_list_combo, stretch=1)

        # Bouton Nouvelle liste
        self.btn_new_custom_list = QPushButton(" " + tr("➕ Nouvelle liste"))
        self.btn_new_custom_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_custom_list.setStyleSheet("""
            QPushButton {
                background-color: #222b3d;
                border: 1px solid #38bdf8;
                border-radius: 7px;
                padding: 6px 12px;
                color: #38bdf8;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(56, 189, 248, 0.2);
            }
        """)
        self.btn_new_custom_list.clicked.connect(self._create_new_custom_list)
        list_ctrl_row.addWidget(self.btn_new_custom_list)

        # Bouton Renommer
        self.btn_rename_custom_list = QPushButton(tr("Renommer"))
        self.btn_rename_custom_list.setIcon(get_icon("edit", color="#94a3b8"))
        self.btn_rename_custom_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rename_custom_list.setStyleSheet("""
            QPushButton {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 7px;
                padding: 6px 12px;
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2e3c56;
                border-color: #475569;
            }
        """)
        self.btn_rename_custom_list.clicked.connect(self._rename_current_custom_list)
        list_ctrl_row.addWidget(self.btn_rename_custom_list)

        # Bouton Supprimer
        self.btn_delete_custom_list = QPushButton(tr("Supprimer"))
        self.btn_delete_custom_list.setIcon(get_icon("delete", color="#f87171"))
        self.btn_delete_custom_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete_custom_list.setStyleSheet("""
            QPushButton {
                background-color: #222b3d;
                border: 1px solid #5a2727;
                border-radius: 7px;
                padding: 6px 12px;
                color: #fca5a5;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #451a1a;
                border-color: #f87171;
            }
        """)
        self.btn_delete_custom_list.clicked.connect(self._delete_current_custom_list)
        list_ctrl_row.addWidget(self.btn_delete_custom_list)

        layout.addLayout(list_ctrl_row)

        # Sous-titre / instruction & compteur
        info_row = QHBoxLayout()
        self.custom_counter_label = QLabel(tr("Sélectionnez les chaînes à inclure dans cette liste personnalisée"))
        self.custom_counter_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")
        info_row.addWidget(self.custom_counter_label, stretch=1)
        layout.addLayout(info_row)

        # Recherche de chaînes dans la liste
        self.custom_search_edit = QLineEdit()
        self.custom_search_edit.setPlaceholderText(tr("Rechercher une chaîne..."))
        self.custom_search_edit.setClearButtonEnabled(True)
        search_icon = get_icon("search", color="#94a3b8")
        self.custom_search_edit.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.custom_search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 8px;
                padding: 7px 10px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background-color: #273349;
            }
        """)
        self.custom_search_edit.textChanged.connect(self._filter_custom_tree)
        layout.addWidget(self.custom_search_edit)

        # Arbre des chaînes pour la liste personnalisée
        self.custom_tree_widget = KeyboardNavTreeWidget()
        self.custom_tree_widget.setHeaderHidden(True)
        self.custom_tree_widget.setRootIsDecorated(True)
        self.custom_tree_widget.setIndentation(22)
        self.custom_tree_widget.itemChanged.connect(self._on_custom_tree_item_changed)
        layout.addWidget(self.custom_tree_widget, stretch=1)

        # Vue placeholder quand aucune liste personnalisée n'existe
        self.empty_lists_frame = QFrame()
        self.empty_lists_frame.setStyleSheet("""
            QFrame {
                background-color: #222b3d;
                border: 1px dashed #33415c;
                border-radius: 12px;
                padding: 24px;
            }
        """)
        empty_layout = QVBoxLayout(self.empty_lists_frame)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("playlist_play", color="#38bdf8").pixmap(48, 48))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon_lbl)

        title_empty = QLabel(tr("Aucune liste personnalisée créée"))
        title_empty.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f5f9;")
        title_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title_empty)

        desc_empty = QLabel(tr("Créez vos listes personnalisées (ex: Salon HD, Van SD) adaptées à vos différents écrans ou connexions."))
        desc_empty.setStyleSheet("font-size: 13px; color: #94a3b8;")
        desc_empty.setWordWrap(True)
        desc_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(desc_empty)

        btn_create_empty = QPushButton(" " + tr("Créer une liste personnalisée"))
        btn_create_empty.setIcon(get_icon("add", color="#ffffff"))
        btn_create_empty.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_create_empty.setStyleSheet("""
            QPushButton {
                background-color: #38bdf8;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                color: #0f172a;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #0ea5e9;
            }
        """)
        btn_create_empty.clicked.connect(self._create_new_custom_list)
        empty_layout.addWidget(btn_create_empty, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.empty_lists_frame)
        self.empty_lists_frame.hide()

    def _load_data(self):
        self._block_signals = True
        self.tree_widget.setUpdatesEnabled(False)
        self.tree_widget.clear()

        # Récupération de toutes les catégories et chaînes
        self._channels_by_category = self.db.get_all_categories_with_channels(
            playlist_id=self.playlist_id,
            stream_type=self.stream_type
        )
        disabled_groups = self.db.get_disabled_groups(
            playlist_id=self.playlist_id,
            stream_type=self.stream_type
        )

        image_loader = ImageLoader.instance()
        fallback_pix = get_pixmap("live_tv", color="#64748b", size=18)
        fallback_icon = QIcon(fallback_pix)

        self._total_channels = 0
        self._selected_channels = 0
        self._total_groups = len(self._channels_by_category)
        is_vod = self.stream_type in ("movie", "vod", "series")

        cat_items = list(self._channels_by_category.items())
        if is_vod:
            from core.models import prioritize_categories
            cat_items = prioritize_categories(cat_items)

        for category_name, channels in cat_items:
            cat_item = QTreeWidgetItem(self.tree_widget)
            cat_item.setData(0, Qt.ItemDataRole.UserRole, ("category", category_name))
            cat_item.setData(0, Qt.ItemDataRole.UserRole + 1, channels)
            cat_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            cat_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)

            total_in_cat = len(channels)
            group_disabled = (category_name in disabled_groups)
            checked_in_cat = sum(1 for ch in channels if ch.is_enabled)
            self._total_channels += total_in_cat
            cat_clean_name = clean_category_display_name(category_name)

            if is_vod:
                cat_item.setText(0, f"{cat_clean_name}  ({total_in_cat})")
                if group_disabled or checked_in_cat == 0:
                    cat_item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    cat_item.setCheckState(0, Qt.CheckState.Checked)
                    self._selected_channels += total_in_cat
            else:
                for ch in channels:
                    ch_item = QTreeWidgetItem(cat_item)
                    ch_item.setText(0, ch.name)
                    if group_disabled and checked_in_cat == 0:
                        ch_enabled = False
                    else:
                        ch_enabled = bool(ch.is_enabled)

                    ch_item.setData(0, Qt.ItemDataRole.UserRole, ("channel", ch.id, ch_enabled))
                    ch_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)

                    if ch.logo_url:
                        pix = image_loader.get_cached_image(ch.logo_url)
                        if pix and not pix.isNull():
                            ch_item.setIcon(0, QIcon(pix.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
                        else:
                            ch_item.setIcon(0, fallback_icon)
                    else:
                        ch_item.setIcon(0, fallback_icon)

                    if ch_enabled:
                        ch_item.setCheckState(0, Qt.CheckState.Checked)
                    else:
                        ch_item.setCheckState(0, Qt.CheckState.Unchecked)

                real_checked = sum(1 for j in range(cat_item.childCount()) if cat_item.child(j).checkState(0) == Qt.CheckState.Checked)
                self._selected_channels += real_checked
                cat_item.setData(0, Qt.ItemDataRole.UserRole + 2, total_in_cat)

                if real_checked > 0:
                    cat_item.setCheckState(0, Qt.CheckState.Checked)
                    if real_checked < total_in_cat:
                        cat_item.setText(0, f"{cat_clean_name}  ({real_checked}/{total_in_cat})")
                    else:
                        cat_item.setText(0, f"{cat_clean_name}  ({total_in_cat})")
                else:
                    cat_item.setCheckState(0, Qt.CheckState.Unchecked)
                    cat_item.setText(0, f"{cat_clean_name}  ({total_in_cat})")

        self._block_signals = False
        self.tree_widget.setUpdatesEnabled(True)
        self._refresh_counter_label()

        # Initialisation de l'onglet des listes personnalisées (uniquement en direct)
        if self.has_custom_lists:
            self._populate_custom_tree()
            self._reload_custom_lists_combo(select_list_id=self.initial_custom_list_id)

    def _populate_custom_tree(self):
        """Construit l'arborescence des catégories/chaînes pour l'onglet des listes personnalisées."""
        self._block_custom_signals = True
        self.custom_tree_widget.setUpdatesEnabled(False)
        self.custom_tree_widget.clear()

        image_loader = ImageLoader.instance()
        fallback_pix = get_pixmap("live_tv", color="#64748b", size=18)
        fallback_icon = QIcon(fallback_pix)

        for category_name, channels in self._channels_by_category.items():
            cat_item = QTreeWidgetItem(self.custom_tree_widget)
            cat_item.setText(0, f"{clean_category_display_name(category_name)}  ({len(channels)})")
            cat_item.setData(0, Qt.ItemDataRole.UserRole, ("custom_category", category_name))
            cat_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            cat_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            cat_item.setCheckState(0, Qt.CheckState.Unchecked)

            for ch in channels:
                ch_item = QTreeWidgetItem(cat_item)
                ch_item.setText(0, ch.name)
                ch_item.setData(0, Qt.ItemDataRole.UserRole, ("custom_channel", ch))
                ch_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                ch_item.setCheckState(0, Qt.CheckState.Unchecked)

                if ch.logo_url:
                    pix = image_loader.get_cached_image(ch.logo_url)
                    if pix and not pix.isNull():
                        ch_item.setIcon(0, QIcon(pix.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
                    else:
                        ch_item.setIcon(0, fallback_icon)
                else:
                    ch_item.setIcon(0, fallback_icon)

        self._block_custom_signals = False
        self.custom_tree_widget.setUpdatesEnabled(True)

    def _reload_custom_lists_combo(self, select_list_id: Optional[int] = None):
        """Charge la liste des listes personnalisées dans la liste déroulante."""
        self.custom_list_combo.blockSignals(True)
        self.custom_list_combo.clear()

        lists = self.db.get_custom_channel_lists_with_counts(playlist_id=self.playlist_id)

        if not lists:
            self.empty_lists_frame.show()
            self.custom_tree_widget.hide()
            self.custom_search_edit.hide()
            self.btn_rename_custom_list.setEnabled(False)
            self.btn_delete_custom_list.setEnabled(False)
            self.custom_counter_label.setText(tr("Aucune liste personnalisée"))
        else:
            self.empty_lists_frame.hide()
            self.custom_tree_widget.show()
            self.custom_search_edit.show()
            self.btn_rename_custom_list.setEnabled(True)
            self.btn_delete_custom_list.setEnabled(True)

            selected_idx = 0
            for idx, (lid, name, count) in enumerate(lists):
                display = f"📋 {name}  ({count})"
                self.custom_list_combo.addItem(display, userData=lid)
                if select_list_id is not None and lid == select_list_id:
                    selected_idx = idx

            self.custom_list_combo.setCurrentIndex(selected_idx)

        self.custom_list_combo.blockSignals(False)
        self._sync_custom_tree_checks()

    def get_current_custom_list_id(self) -> Optional[int]:
        """Retourne l'ID de la liste personnalisée actuellement affichée dans le dialogue."""
        if getattr(self, "has_custom_lists", False) and hasattr(self, "custom_list_combo") and self.custom_list_combo.count() > 0:
            return self.custom_list_combo.currentData()
        return None

    def _on_custom_list_selected(self, index: int):
        self._sync_custom_tree_checks()

    def _sync_custom_tree_checks(self):
        """Met à jour les cases à cocher de l'arborescence selon la liste personnalisée sélectionnée."""
        if self.custom_list_combo.count() == 0:
            return

        list_id = self.custom_list_combo.currentData()
        if not list_id:
            return

        self._block_custom_signals = True
        self.custom_tree_widget.setUpdatesEnabled(False)

        try:
            channels_in_list = self.db.get_channels_for_custom_list(list_id, playlist_id=self.playlist_id)
            ids_in_list = {c.id for c in channels_in_list if c.id}
            urls_in_list = {c.stream_url for c in channels_in_list if c.stream_url}
            names_in_list = {c.name for c in channels_in_list if c.name}

            total_checked = 0

            for i in range(self.custom_tree_widget.topLevelItemCount()):
                cat_item = self.custom_tree_widget.topLevelItem(i)
                cat_checked = 0
                child_count = cat_item.childCount()

                for j in range(child_count):
                    ch_item = cat_item.child(j)
                    data = ch_item.data(0, Qt.ItemDataRole.UserRole)
                    if data and data[0] == "custom_channel":
                        ch: Channel = data[1]
                        is_in = (ch.id in ids_in_list) or (ch.stream_url in urls_in_list) or (ch.name in names_in_list)
                        if is_in:
                            ch_item.setCheckState(0, Qt.CheckState.Checked)
                            cat_checked += 1
                        else:
                            ch_item.setCheckState(0, Qt.CheckState.Unchecked)

                total_checked += cat_checked
                cat_data = cat_item.data(0, Qt.ItemDataRole.UserRole)
                cat_clean_name = clean_category_display_name(cat_data[1]) if cat_data else ""
                if cat_checked > 0:
                    cat_item.setCheckState(0, Qt.CheckState.Checked)
                    if cat_checked < child_count:
                        cat_item.setText(0, f"{cat_clean_name}  ({cat_checked}/{child_count})")
                    else:
                        cat_item.setText(0, f"{cat_clean_name}  ({child_count})")
                else:
                    cat_item.setCheckState(0, Qt.CheckState.Unchecked)
                    cat_item.setText(0, f"{cat_clean_name}  ({child_count})")

            self.custom_counter_label.setText(
                tr("{count} chaîne(s) dans cette liste", count=total_checked)
            )
        finally:
            self._block_custom_signals = False
            self.custom_tree_widget.setUpdatesEnabled(True)

    def _on_custom_tree_item_changed(self, item: QTreeWidgetItem, column: int):
        if self._block_custom_signals:
            return

        list_id = self.custom_list_combo.currentData()
        if not list_id:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        item_type = data[0]
        state = item.checkState(0)

        self._block_custom_signals = True
        self.custom_tree_widget.setUpdatesEnabled(False)
        try:
            if item_type == "custom_category":
                target_state = Qt.CheckState.Checked if state == Qt.CheckState.Checked else Qt.CheckState.Unchecked
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(0, target_state)
                    ch_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if ch_data and ch_data[0] == "custom_channel":
                        ch: Channel = ch_data[1]
                        if target_state == Qt.CheckState.Checked:
                            self.db.add_channel_to_custom_list(list_id, ch)
                        else:
                            self.db.remove_channel_from_custom_list(list_id, ch)
                cat_name = clean_category_display_name(data[1])
                item.setText(0, f"{cat_name}  ({item.childCount()})")

            elif item_type == "custom_channel":
                ch: Channel = data[1]
                if state == Qt.CheckState.Checked:
                    self.db.add_channel_to_custom_list(list_id, ch)
                else:
                    self.db.remove_channel_from_custom_list(list_id, ch)

                parent = item.parent()
                if parent:
                    total_in_cat = parent.childCount()
                    checked_count = sum(1 for i in range(total_in_cat) if parent.child(i).checkState(0) == Qt.CheckState.Checked)
                    parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
                    cat_name = clean_category_display_name(parent_data[1]) if parent_data else ""
                    if checked_count > 0:
                        parent.setCheckState(0, Qt.CheckState.Checked)
                        if checked_count < total_in_cat:
                            parent.setText(0, f"{cat_name}  ({checked_count}/{total_in_cat})")
                        else:
                            parent.setText(0, f"{cat_name}  ({total_in_cat})")
                    else:
                        parent.setCheckState(0, Qt.CheckState.Unchecked)
                        parent.setText(0, f"{cat_name}  ({total_in_cat})")

            self._custom_lists_modified = True
            total_checked = 0
            for i in range(self.custom_tree_widget.topLevelItemCount()):
                cat_item = self.custom_tree_widget.topLevelItem(i)
                total_checked += sum(1 for j in range(cat_item.childCount()) if cat_item.child(j).checkState(0) == Qt.CheckState.Checked)

            self.custom_counter_label.setText(
                tr("{count} chaîne(s) dans cette liste", count=total_checked)
            )

            curr_idx = self.custom_list_combo.currentIndex()
            if curr_idx >= 0:
                list_info = self.db.get_custom_channel_list_by_id(list_id)
                list_name = list_info["name"] if list_info else ""
                self.custom_list_combo.setItemText(curr_idx, f"📋 {list_name}  ({total_checked})")

        finally:
            self._block_custom_signals = False
            self.custom_tree_widget.setUpdatesEnabled(True)

    def _create_new_custom_list(self):
        name, ok = ThemedInputDialog.get_text(
            self,
            title=tr("Nouvelle liste personnalisée"),
            label=tr("Nom de la liste (ex: Salon HD, Van SD) :"),
            placeholder=tr("ex: Salon HD"),
            icon_name="playlist_add"
        )
        if ok and name and name.strip():
            list_name = name.strip()
            list_id = self.db.create_custom_channel_list(list_name)
            if list_id:
                self._custom_lists_modified = True
                self._reload_custom_lists_combo(select_list_id=list_id)
            else:
                QMessageBox.warning(self, tr("Erreur"), tr("Ce nom de liste existe déjà."))

    def _rename_current_custom_list(self):
        list_id = self.custom_list_combo.currentData()
        if not list_id:
            return
        list_info = self.db.get_custom_channel_list_by_id(list_id)
        if not list_info:
            return
        old_name = list_info["name"]

        new_name, ok = ThemedInputDialog.get_text(
            self,
            title=tr("Renommer la liste"),
            label=tr("Nouveau nom :"),
            text=old_name,
            icon_name="edit"
        )
        if ok and new_name and new_name.strip() and new_name.strip() != old_name:
            success = self.db.rename_custom_channel_list(list_id, new_name.strip())
            if success:
                self._custom_lists_modified = True
                self._reload_custom_lists_combo(select_list_id=list_id)
            else:
                QMessageBox.warning(self, tr("Erreur"), tr("Ce nom de liste existe déjà."))

    def _delete_current_custom_list(self):
        list_id = self.custom_list_combo.currentData()
        if not list_id:
            return
        list_info = self.db.get_custom_channel_list_by_id(list_id)
        if not list_info:
            return
        name = list_info["name"]

        confirm = QMessageBox.question(
            self,
            tr("Supprimer la liste"),
            tr("Êtes-vous sûr de vouloir supprimer la liste '{name}' ?\nLes chaînes associées ne seront pas effacées de votre playlist.").format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.delete_custom_channel_list(list_id)
            self._custom_lists_modified = True
            self._reload_custom_lists_combo()

    def _filter_custom_tree(self, text: str):
        query = text.strip().lower()
        self.custom_tree_widget.setUpdatesEnabled(False)
        try:
            for i in range(self.custom_tree_widget.topLevelItemCount()):
                cat_item = self.custom_tree_widget.topLevelItem(i)
                cat_matches = query in cat_item.text(0).lower()

                child_matched_count = 0
                for j in range(cat_item.childCount()):
                    ch_item = cat_item.child(j)
                    ch_matches = query in ch_item.text(0).lower()
                    ch_item.setHidden(not (cat_matches or ch_matches))
                    if ch_matches:
                        child_matched_count += 1

                cat_item.setHidden(not (cat_matches or child_matched_count > 0))
                if query and (cat_matches or child_matched_count > 0):
                    cat_item.setExpanded(True)
        finally:
            self.custom_tree_widget.setUpdatesEnabled(True)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        if self._block_signals:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        item_type = data[0]
        state = item.checkState(0)

        self._block_signals = True
        self.tree_widget.setUpdatesEnabled(False)
        try:
            if item_type == "category":
                channels = item.data(0, Qt.ItemDataRole.UserRole + 1) or []
                total_in_cat = len(channels)

                if item.childCount() > 0:
                    target_state = Qt.CheckState.Checked if state == Qt.CheckState.Checked else Qt.CheckState.Unchecked
                    old_checked = sum(1 for i in range(item.childCount()) if item.child(i).checkState(0) == Qt.CheckState.Checked)
                    new_checked = item.childCount() if target_state == Qt.CheckState.Checked else 0

                    self._selected_channels += (new_checked - old_checked)
                    for i in range(item.childCount()):
                        item.child(i).setCheckState(0, target_state)

                    cat_name = clean_category_display_name(data[1])
                    item.setText(0, f"{cat_name}  ({item.childCount()})")
                else:
                    if state == Qt.CheckState.Checked:
                        self._selected_channels += total_in_cat
                    else:
                        self._selected_channels = max(0, self._selected_channels - total_in_cat)

            elif item_type == "channel":
                parent = item.parent()
                if parent:
                    total_in_cat = parent.childCount()
                    checked_count = sum(1 for i in range(total_in_cat) if parent.child(i).checkState(0) == Qt.CheckState.Checked)

                    if state == Qt.CheckState.Checked:
                        self._selected_channels += 1
                    else:
                        self._selected_channels = max(0, self._selected_channels - 1)

                    parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
                    cat_name = clean_category_display_name(parent_data[1]) if parent_data else ""

                    if checked_count > 0:
                        parent.setCheckState(0, Qt.CheckState.Checked)
                        if checked_count < total_in_cat:
                            parent.setText(0, f"{cat_name}  ({checked_count}/{total_in_cat})")
                        else:
                            parent.setText(0, f"{cat_name}  ({total_in_cat})")
                    else:
                        parent.setCheckState(0, Qt.CheckState.Unchecked)
                        parent.setText(0, f"{cat_name}  ({total_in_cat})")
        finally:
            self._block_signals = False
            self.tree_widget.setUpdatesEnabled(True)

        self._refresh_counter_label()

    def _select_all(self):
        self._block_signals = True
        self.tree_widget.setUpdatesEnabled(False)
        try:
            self._selected_channels = self._total_channels
            for i in range(self.tree_widget.topLevelItemCount()):
                cat_item = self.tree_widget.topLevelItem(i)
                cat_item.setCheckState(0, Qt.CheckState.Checked)
                cat_data = cat_item.data(0, Qt.ItemDataRole.UserRole)
                if cat_data and cat_data[0] == "category":
                    cat_name = clean_category_display_name(cat_data[1])
                    total = cat_item.childCount() if cat_item.childCount() > 0 else (len(cat_item.data(0, Qt.ItemDataRole.UserRole + 1) or []))
                    cat_item.setText(0, f"{cat_name}  ({total})")
                for j in range(cat_item.childCount()):
                    cat_item.child(j).setCheckState(0, Qt.CheckState.Checked)
        finally:
            self._block_signals = False
            self.tree_widget.setUpdatesEnabled(True)
        self._refresh_counter_label()

    def _deselect_all(self):
        self._block_signals = True
        self.tree_widget.setUpdatesEnabled(False)
        try:
            self._selected_channels = 0
            for i in range(self.tree_widget.topLevelItemCount()):
                cat_item = self.tree_widget.topLevelItem(i)
                cat_item.setCheckState(0, Qt.CheckState.Unchecked)
                cat_data = cat_item.data(0, Qt.ItemDataRole.UserRole)
                if cat_data and cat_data[0] == "category":
                    cat_name = clean_category_display_name(cat_data[1])
                    total = cat_item.childCount() if cat_item.childCount() > 0 else (len(cat_item.data(0, Qt.ItemDataRole.UserRole + 1) or []))
                    cat_item.setText(0, f"{cat_name}  ({total})")
                for j in range(cat_item.childCount()):
                    cat_item.child(j).setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            self._block_signals = False
            self.tree_widget.setUpdatesEnabled(True)
        self._refresh_counter_label()

    def _filter_tree(self, text: str):
        query = text.strip().lower()
        self.tree_widget.setUpdatesEnabled(False)
        try:
            for i in range(self.tree_widget.topLevelItemCount()):
                cat_item = self.tree_widget.topLevelItem(i)
                data = cat_item.data(0, Qt.ItemDataRole.UserRole)
                category_name = data[1] if (data and data[0] == "category") else ""
                cat_matches = (query in cat_item.text(0).lower()) or (query in category_name.lower())

                if cat_item.childCount() == 0:
                    cat_item.setHidden(not cat_matches)
                else:
                    child_matched_count = 0
                    for j in range(cat_item.childCount()):
                        ch_item = cat_item.child(j)
                        ch_matches = query in ch_item.text(0).lower()
                        ch_item.setHidden(not (cat_matches or ch_matches))
                        if ch_matches:
                            child_matched_count += 1

                    cat_item.setHidden(not (cat_matches or child_matched_count > 0))
                    if query and (cat_matches or child_matched_count > 0):
                        cat_item.setExpanded(True)
        finally:
            self.tree_widget.setUpdatesEnabled(True)

    def _refresh_counter_label(self):
        selected_groups = 0
        total_groups = self.tree_widget.topLevelItemCount()
        for i in range(total_groups):
            cat_item = self.tree_widget.topLevelItem(i)
            if cat_item.checkState(0) == Qt.CheckState.Checked:
                selected_groups += 1

        self.counter_label.setText(
            tr(
                "Sélectionnées: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} groupes)",
                selected=self._selected_channels,
                total=self._total_channels,
                sel_groups=selected_groups,
                tot_groups=total_groups
            )
        )

    def _on_close_clicked(self):
        if getattr(self, "has_custom_lists", False) and self._custom_lists_modified:
            self.categories_updated.emit()
        self.reject()

    def _save_and_accept(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            enabled_ids: List[int] = []
            disabled_ids: List[int] = []
            enabled_groups: List[str] = []
            disabled_groups: List[str] = []

            for i in range(self.tree_widget.topLevelItemCount()):
                cat_item = self.tree_widget.topLevelItem(i)
                data = cat_item.data(0, Qt.ItemDataRole.UserRole)
                category_name = data[1] if (data and data[0] == "category") else ""

                if cat_item.childCount() > 0:
                    checked_count = sum(1 for j in range(cat_item.childCount()) if cat_item.child(j).checkState(0) == Qt.CheckState.Checked)

                    if checked_count > 0:
                        if category_name:
                            enabled_groups.append(category_name)
                    else:
                        if category_name:
                            disabled_groups.append(category_name)

                    for j in range(cat_item.childCount()):
                        ch_item = cat_item.child(j)
                        ch_data = ch_item.data(0, Qt.ItemDataRole.UserRole)
                        if ch_data and ch_data[0] == "channel":
                            channel_id = ch_data[1]
                            is_checked = (ch_item.checkState(0) == Qt.CheckState.Checked)
                            if is_checked:
                                enabled_ids.append(channel_id)
                            else:
                                disabled_ids.append(channel_id)
                else:
                    is_checked = (cat_item.checkState(0) == Qt.CheckState.Checked)
                    if is_checked:
                        if category_name:
                            enabled_groups.append(category_name)
                    else:
                        if category_name:
                            disabled_groups.append(category_name)

            if enabled_ids or disabled_ids:
                self.db.save_channels_enabled_status(enabled_ids, disabled_ids)

            if enabled_groups or disabled_groups:
                self.db.save_groups_enabled_status(self.playlist_id, self.stream_type, disabled_groups, enabled_groups)

            if enabled_groups or disabled_groups or enabled_ids or disabled_ids or (getattr(self, "has_custom_lists", False) and self._custom_lists_modified):
                self.categories_updated.emit()
            self.accept()
        finally:
            QApplication.restoreOverrideCursor()
