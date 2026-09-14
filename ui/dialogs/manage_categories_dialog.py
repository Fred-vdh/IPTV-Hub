"""
Boîte de dialogue moderne de gestion et de filtrage hiérarchique des catégories et des chaînes IPTV.
Permet d'activer/désactiver des catégories entières ou des chaînes spécifiques avec accordéon et cases à cocher.
"""

from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTreeWidget, QTreeWidgetItem, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from core.database import Database
from core.models import Channel, clean_category_display_name
from core.image_loader import ImageLoader
from ui.icons import get_icon, get_pixmap

def _get_chevron_icons():
    from core.database import get_cache_dir
    cache_dir = get_cache_dir()
    right_svg = cache_dir / "chevron_right.svg"
    down_svg = cache_dir / "chevron_down.svg"
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
    return right_svg.as_posix(), down_svg.as_posix()


class ManageCategoriesDialog(QDialog):
    categories_updated = pyqtSignal()

    def __init__(self, db: Database, playlist_id: Optional[int] = None, stream_type: Optional[str] = "live", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.playlist_id = playlist_id
        self.stream_type = stream_type

        self.setWindowTitle("Gérer et filtrer les catégories")
        self.resize(680, 720)
        self.setMinimumSize(540, 500)
        self.setModal(True)
        self.setObjectName("manageCategoriesDialog")

        chevron_right_path, chevron_down_path = _get_chevron_icons()

        self.setStyleSheet(f"""
            QDialog#manageCategoriesDialog {{
                background-color: #161c2a;
                border: 1px solid #28354d;
                border-radius: 12px;
            }}
            QTreeWidget {{
                background-color: #1a2233;
                border: 1px solid #29364f;
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
                background-color: #242f44;
            }}
            QTreeWidget::item:selected {{
                background-color: #2b3952;
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
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1.5px solid #475569;
                border-radius: 4px;
                background-color: #1a2233;
            }}
            QCheckBox::indicator:checked {{
                background-color: #3b82f6;
                border-color: #3b82f6;
            }}
            QCheckBox::indicator:indeterminate {{
                background-color: #6366f1;
                border-color: #6366f1;
            }}
        """)

        self._channels_by_category: Dict[str, List[Channel]] = {}
        self._block_signals = False

        self._init_ui()
        self._load_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. En-tête : Titre + Sous-titre avec compteur en temps réel
        header_box = QVBoxLayout()
        header_box.setSpacing(4)

        title_label = QLabel("Gérer les catégories")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff;")
        header_box.addWidget(title_label)

        self.counter_label = QLabel("Sélectionnées: 0 / 0 (0 / 0 groupes)")
        self.counter_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 500;")
        header_box.addWidget(self.counter_label)

        main_layout.addLayout(header_box)

        # 2. Barre d'actions globales (Tout sélectionner / Tout désélectionner)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.select_all_btn = QPushButton(" Tout sélectionner")
        self.select_all_btn.setIcon(get_icon("check_circle", color="#818cf8"))
        self.select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #20293d;
                border: 1px solid #303e5c;
                border-radius: 7px;
                padding: 6px 14px;
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #29354d;
                border-color: #818cf8;
            }
        """)
        self.select_all_btn.clicked.connect(self._select_all)
        actions_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton(" Tout désélectionner")
        self.deselect_all_btn.setIcon(get_icon("crop_square", color="#94a3b8"))
        self.deselect_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #20293d;
                border: 1px solid #303e5c;
                border-radius: 7px;
                padding: 6px 14px;
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #29354d;
                border-color: #94a3b8;
            }
        """)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        actions_row.addWidget(self.deselect_all_btn)

        actions_row.addStretch()
        main_layout.addLayout(actions_row)

        # 3. Barre de recherche de catégories
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Rechercher des catégories ou des chaînes...")
        self.search_edit.setClearButtonEnabled(True)
        search_icon = get_icon("search", color="#94a3b8")
        self.search_edit.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1f283b;
                border: 1px solid #313f5c;
                border-radius: 8px;
                padding: 7px 10px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        self.search_edit.textChanged.connect(self._filter_tree)
        main_layout.addWidget(self.search_edit)

        # 4. Arbre hiérarchique (QTreeWidget) - plat en mode VOD, accordéon en mode Live
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        if self.stream_type in ("movie", "vod", "series"):
            self.tree_widget.setRootIsDecorated(False)
            self.tree_widget.setIndentation(8)
        else:
            self.tree_widget.setRootIsDecorated(True)
            self.tree_widget.setIndentation(22)
        self.tree_widget.itemChanged.connect(self._on_item_changed)
        main_layout.addWidget(self.tree_widget, stretch=1)

        # 5. Barre inférieure : Boutons Fermer & Enregistrer
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        bottom_row.addStretch()

        self.close_btn = QPushButton("Fermer")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #20293d;
                border: 1px solid #303e5c;
                border-radius: 8px;
                padding: 8px 20px;
                color: #e2e8f0;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #29354d;
            }
        """)
        self.close_btn.clicked.connect(self.reject)
        bottom_row.addWidget(self.close_btn)

        self.save_btn = QPushButton("Enregistrer")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
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

    def _load_data(self):
        self._block_signals = True
        self.tree_widget.setUpdatesEnabled(False)
        self.tree_widget.clear()

        # Récupération de toutes les catégories et chaînes (activées ou non)
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
            cat_item.setText(0, f"{clean_category_display_name(category_name)}  ({len(channels)})")
            cat_item.setData(0, Qt.ItemDataRole.UserRole, ("category", category_name))
            cat_item.setData(0, Qt.ItemDataRole.UserRole + 1, channels)
            cat_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.DemiBold))

            # Case à cocher pour la catégorie
            cat_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled |
                Qt.ItemFlag.ItemIsUserCheckable
            )

            total_in_cat = len(channels)
            group_disabled = (category_name in disabled_groups)
            checked_in_cat = 0 if group_disabled else sum(1 for ch in channels if ch.is_enabled)
            self._total_channels += total_in_cat

            if is_vod:
                # Mode VOD : liste plate de catégories sans arborescence d'enfants
                # Une catégorie est décochée si elle est dans disabled_groups ou si aucune chaîne n'est activée
                if group_disabled or checked_in_cat == 0:
                    cat_item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    cat_item.setCheckState(0, Qt.CheckState.Checked)
                    self._selected_channels += total_in_cat
            else:
                # Mode TV Direct : ajout des chaînes enfants avec logo
                for ch in channels:
                    ch_item = QTreeWidgetItem(cat_item)
                    ch_item.setText(0, ch.name)
                    ch_enabled = bool(ch.is_enabled and not group_disabled)
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

                if real_checked == total_in_cat and total_in_cat > 0:
                    cat_item.setCheckState(0, Qt.CheckState.Checked)
                elif real_checked == 0 or total_in_cat == 0:
                    cat_item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    cat_item.setCheckState(0, Qt.CheckState.PartiallyChecked)

        self._block_signals = False
        self.tree_widget.setUpdatesEnabled(True)
        self._refresh_counter_label()

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
                else:
                    # Mode VOD (sans enfants)
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

                    if checked_count == total_in_cat and total_in_cat > 0:
                        parent.setCheckState(0, Qt.CheckState.Checked)
                    elif checked_count == 0:
                        parent.setCheckState(0, Qt.CheckState.Unchecked)
                    else:
                        parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
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
                cat_matches = query in cat_item.text(0).lower()

                if cat_item.childCount() == 0:
                    # Mode VOD : filtrage direct sur les catégories
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
            if cat_item.checkState(0) in (Qt.CheckState.Checked, Qt.CheckState.PartiallyChecked):
                selected_groups += 1

        self.counter_label.setText(
            f"Sélectionnées: <b style='color:#38bdf8;'>{self._selected_channels}</b> / {self._total_channels}  ({selected_groups} / {total_groups} groupes)"
        )

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
                    cat_state = cat_item.checkState(0)
                    if cat_state == Qt.CheckState.Checked:
                        if category_name:
                            enabled_groups.append(category_name)
                    elif cat_state == Qt.CheckState.Unchecked:
                        if category_name:
                            disabled_groups.append(category_name)

                    for j in range(cat_item.childCount()):
                        ch_item = cat_item.child(j)
                        ch_data = ch_item.data(0, Qt.ItemDataRole.UserRole)
                        if ch_data and ch_data[0] == "channel":
                            channel_id = ch_data[1]
                            initial_enabled = ch_data[2] if len(ch_data) > 2 else None
                            is_checked = (ch_item.checkState(0) == Qt.CheckState.Checked)
                            if initial_enabled is None or is_checked != initial_enabled:
                                if is_checked:
                                    enabled_ids.append(channel_id)
                                else:
                                    disabled_ids.append(channel_id)
                else:
                    # Mode VOD / Séries (catégorie complète) : gestion propre par groupe
                    is_checked = (cat_item.checkState(0) == Qt.CheckState.Checked)
                    if is_checked:
                        if category_name:
                            enabled_groups.append(category_name)
                    else:
                        if category_name:
                            disabled_groups.append(category_name)

            # Enregistrement en base de données si des modifications ont eu lieu
            if enabled_groups or disabled_groups:
                self.db.save_groups_enabled_status(self.playlist_id, self.stream_type, disabled_groups, enabled_groups)

            if enabled_ids or disabled_ids:
                self.db.save_channels_enabled_status(enabled_ids, disabled_ids)

            if enabled_groups or disabled_groups or enabled_ids or disabled_ids:
                self.categories_updated.emit()
            self.accept()
        finally:
            QApplication.restoreOverrideCursor()

