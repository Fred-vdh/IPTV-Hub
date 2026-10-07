"""
Dialogue de sélection rapide de chaîne pour le mode Multiview.

Deux colonnes :
  * à gauche, les sources de chaînes dans l'ordre demandé : les listes
    personnalisées d'abord, puis les catégories (filtrées : seules les catégories
    contenant réellement des chaînes activées apparaissent) ;
  * à droite, les chaînes de la source sélectionnée, filtrables par recherche.
"""

from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QBrush, QColor

from core.database import Database
from core.models import Channel, clean_category_display_name
from core.i18n import tr
from ui.icons import get_icon


class ChannelPickerDialog(QDialog):
    """Sélecteur de chaîne d'un écran Multiview.

    La colonne des sources affiche les listes personnalisées EN PREMIER, puis les
    catégories filtrées. Toutes les sources proviennent de la TV en direct
    (chaînes activées uniquement), comme le reste de l'application.
    """

    SCOPE_ALL = "__all__"
    CUSTOM_PREFIX = "custom:"
    CATEGORY_PREFIX = "category:"
    MAX_ITEMS = 300

    def __init__(self, db: Database, playlist_id: Optional[int] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.playlist_id = playlist_id
        self.selected_channel: Optional[Channel] = None

        self._all_channels: List[Channel] = []
        self._custom_lists: List[Tuple[int, str, int]] = []
        self._categories: List[Tuple[str, int]] = []
        self._scope_channels: Dict[str, List[Channel]] = {}
        self._scope_labels: Dict[str, str] = {}
        self.current_scope: str = self.SCOPE_ALL

        self.setWindowTitle(tr("Choisir une chaîne (Multiview)"))
        self.resize(760, 580)
        self.setMinimumSize(620, 460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._init_ui()
        self._load_sources()
        self._populate_scopes()
        self._select_default_scope()

    # ------------------------------------------------------------------- UI

    def _init_ui(self):
        """Construit la double colonne : sources (listes perso + catégories) puis chaînes."""
        self.setStyleSheet("""
            QDialog {
                background-color: #171d2b;
                color: #f8fafc;
            }
            QLineEdit {
                background-color: #222c40;
                border: 1px solid #334360;
                border-radius: 8px;
                padding: 10px 14px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
            QListWidget {
                background-color: #1a2234;
                border: 1px solid #28354f;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                background-color: transparent;
                border-radius: 6px;
                padding: 8px 12px;
                margin: 2px 0px;
                color: #e2e8f0;
                font-size: 13px;
                font-weight: 500;
            }
            QListWidget::item:hover {
                background-color: #26334d;
                color: #38bdf8;
            }
            QListWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 600;
            }
            QListWidget#scopeList {
                background-color: #141b28;
            }
            QListWidget#scopeList::item {
                padding: 6px 10px;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # En-tête
        header = QLabel(tr("Sélectionner une chaîne pour cet écran"))
        header.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(12)

        # Colonne gauche : listes personnalisées EN PREMIER, catégories ensuite
        self.scope_list = QListWidget()
        self.scope_list.setObjectName("scopeList")
        self.scope_list.setMinimumWidth(210)
        self.scope_list.setMaximumWidth(300)
        self.scope_list.currentItemChanged.connect(self._on_scope_changed)
        body.addWidget(self.scope_list)

        # Colonne droite : source courante + recherche + chaînes
        right = QVBoxLayout()
        right.setSpacing(8)

        self.scope_label = QLabel()
        self.scope_label.setObjectName("scopeLabel")
        self.scope_label.setStyleSheet("color: #93c5fd; font-size: 12px; font-weight: 700;")
        right.addWidget(self.scope_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("Rechercher une chaîne..."))
        self.search_edit.textChanged.connect(self._filter_channels)
        right.addWidget(self.search_edit)

        self.channel_list = QListWidget()
        self.channel_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        right.addWidget(self.channel_list, stretch=1)

        body.addLayout(right, stretch=1)
        layout.addLayout(body, stretch=1)

        # Boutons d'action
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = QPushButton(tr("Annuler"))
        cancel_btn.setProperty("class", "secondary-btn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.select_btn = QPushButton(tr("Sélectionner"))
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.select_btn.setDefault(True)
        self.select_btn.clicked.connect(self._on_select_clicked)
        btn_row.addWidget(self.select_btn)

        layout.addLayout(btn_row)

    # --------------------------------------------------------------- sources

    def _load_sources(self):
        """Charge les chaînes en direct, les listes personnalisées puis les catégories."""
        # 1. Chaînes TV en direct activées (base commune de toutes les sources)
        try:
            self._all_channels = self.db.get_channels(
                playlist_id=self.playlist_id,
                stream_type="live",
                only_enabled=True
            ) or []
        except Exception as e:
            print(f"[ChannelPicker] erreur de chargement des chaînes : {e}")
            self._all_channels = []

        # 2. Catégories « après filtrage » : déduites des chaînes réellement
        #    disponibles, les groupes vides ou désactivés sont donc exclus.
        counts: Dict[str, int] = {}
        for ch in self._all_channels:
            key = self._category_key(ch)
            counts[key] = counts.get(key, 0) + 1
        self._categories = list(counts.items())

        # 3. Listes personnalisées (affichées EN PREMIER)
        try:
            self._custom_lists = self.db.get_custom_channel_lists_with_counts(
                playlist_id=self.playlist_id
            ) or []
        except Exception as e:
            print(f"[ChannelPicker] erreur de chargement des listes personnalisées : {e}")
            self._custom_lists = []

        # 4. Cache des chaînes par source (rempli à la demande)
        self._scope_channels = {self.SCOPE_ALL: list(self._all_channels)}

    @staticmethod
    def _category_key(channel: Channel) -> str:
        """Nom de catégorie brut d'une chaîne (clé de regroupement des catégories)."""
        return (channel.group_title or "Général").strip() or "Général"

    def _populate_scopes(self):
        """Remplit la colonne des sources : listes personnalisées puis catégories."""
        self.scope_list.blockSignals(True)
        self.scope_list.clear()
        self._scope_labels = {}

        # 1. Accès direct à l'intégralité de la TV en direct
        self._add_scope_item(tr("Toutes les chaînes"), self.SCOPE_ALL, icon="live_tv")

        # 2. Listes personnalisées EN PREMIER
        if self._custom_lists:
            self._add_header(tr("Listes personnalisées"))
            for list_id, name, count in self._custom_lists:
                self._add_scope_item(
                    f"{name}  ({count})",
                    f"{self.CUSTOM_PREFIX}{list_id}",
                    icon="playlist_play"
                )

        # 3. Catégories (filtrées) ensuite
        if self._categories:
            self._add_header(tr("CATÉGORIES"))
            for cat_name, count in self._categories:
                display = tr(clean_category_display_name(cat_name))
                self._add_scope_item(
                    f"{display}  ({count})",
                    f"{self.CATEGORY_PREFIX}{cat_name}",
                    icon="folder"
                )

        self.scope_list.blockSignals(False)

    def _add_scope_item(self, label: str, scope: str, icon: Optional[str] = None) -> QListWidgetItem:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, scope)
        if icon:
            item.setIcon(get_icon(icon, color="#38bdf8"))
        item.setSizeHint(QSize(0, 30))
        self.scope_list.addItem(item)
        self._scope_labels[scope] = label
        return item

    def _add_header(self, text: str) -> QListWidgetItem:
        """Ajoute un intitulé de section, non sélectionnable."""
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setData(Qt.ItemDataRole.UserRole, None)
        item.setForeground(QBrush(QColor("#64748b")))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setSizeHint(QSize(0, 24))
        self.scope_list.addItem(item)
        return item

    def _select_default_scope(self):
        """Sélectionne la source par défaut : première liste personnalisée, sinon tout.

        En mode Multiview, l'usage courant est d'aller chercher une chaîne dans une
        liste personnalisée : c'est donc elle qui est présélectionnée dès qu'il en
        existe une (les listes personnalisées sont également affichées en premier).
        """
        target_row = None
        for row in range(self.scope_list.count()):
            scope = self.scope_list.item(row).data(Qt.ItemDataRole.UserRole)
            if not scope:
                continue
            if target_row is None:
                target_row = row   # repli : « Toutes les chaînes »
            if str(scope).startswith(self.CUSTOM_PREFIX):
                target_row = row
                break
        if target_row is not None:
            self.scope_list.setCurrentRow(target_row)
        # setCurrentRow n'émet rien si la ligne est déjà courante : on rafraîchit ici.
        self._refresh_channels()

    def _channels_for_scope(self, scope: str) -> List[Channel]:
        """Chaînes d'une source, avec mise en cache (lecture à la demande en base)."""
        if scope in self._scope_channels:
            return self._scope_channels[scope]

        channels: List[Channel] = []
        if scope.startswith(self.CUSTOM_PREFIX):
            try:
                list_id = int(scope[len(self.CUSTOM_PREFIX):])
            except ValueError:
                list_id = -1
            try:
                channels = self.db.get_channels_for_custom_list(
                    list_id, playlist_id=self.playlist_id
                ) or []
            except Exception as e:
                print(f"[ChannelPicker] erreur de chargement de la liste personnalisée : {e}")
                channels = []
        elif scope.startswith(self.CATEGORY_PREFIX):
            wanted = scope[len(self.CATEGORY_PREFIX):].strip().lower()
            channels = [
                ch for ch in self._all_channels
                if self._category_key(ch).strip().lower() == wanted
            ]

        self._scope_channels[scope] = channels
        return channels

    # ------------------------------------------------------------- affichage

    def _on_scope_changed(self, current: Optional[QListWidgetItem], _previous):
        if current is None:
            return
        scope = current.data(Qt.ItemDataRole.UserRole)
        if not scope:
            # Intitulé de section : purement décoratif, aucune sélection possible.
            return
        self.current_scope = scope
        self._refresh_channels()

    def _refresh_channels(self):
        """Met à jour l'entête de la source puis la liste des chaînes associée."""
        channels = self._channels_for_scope(self.current_scope)
        label = self._scope_labels.get(self.current_scope, tr("Toutes les chaînes"))
        self.scope_label.setText(f"{label} — {len(channels)}")
        self._filter_channels(self.search_edit.text())

    def _filter_channels(self, query: str):
        self.channel_list.clear()
        q = (query or "").strip().lower()

        count = 0
        for ch in self._channels_for_scope(self.current_scope):
            if q and q not in (ch.name or "").lower():
                continue
            item = QListWidgetItem(f"  {ch.name}")
            item.setIcon(get_icon("live_tv", color="#38bdf8"))
            item.setData(Qt.ItemDataRole.UserRole, ch)
            self.channel_list.addItem(item)
            count += 1
            if count >= self.MAX_ITEMS:
                break

        if self.channel_list.count() > 0:
            self.channel_list.setCurrentRow(0)
        else:
            empty = QListWidgetItem(tr("Aucune chaîne"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.channel_list.addItem(empty)

    # ----------------------------------------------------------------- action

    def _current_channel(self) -> Optional[Channel]:
        item = self.channel_list.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, Channel) else None

    def _on_item_double_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, Channel):
            self.selected_channel = data
            self.accept()

    def _on_select_clicked(self):
        channel = self._current_channel()
        if channel is not None:
            self.selected_channel = channel
            self.accept()

