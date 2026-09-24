"""
Boîte de dialogue moderne de gestion des listes de chaînes personnalisées.
Permet de créer, renommer et supprimer des listes personnalisées (ex: Salon HD, Van SD).
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QWidget, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from core.database import Database
from ui.icons import get_icon
from core.i18n import tr
from ui.dialogs.themed_input_dialog import ThemedInputDialog


class CustomListItemWidget(QFrame):
    def __init__(self, list_id: int, name: str, count: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.list_id = list_id
        self.list_name = name
        self.count = count
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("customListItemCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Icône liste
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("playlist_play", color="#38bdf8").pixmap(20, 20))
        layout.addWidget(icon_lbl)

        # Nom
        self.name_label = QLabel(self.list_name)
        self.name_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #f1f5f9;")
        layout.addWidget(self.name_label, stretch=1)

        # Compteur
        count_lbl = QLabel(f"{self.count} {tr('chaîne(s)')}")
        count_lbl.setStyleSheet("""
            background-color: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        layout.addWidget(count_lbl)

        self.setStyleSheet("""
            QFrame#customListItemCard {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)


class ManageCustomListsDialog(QDialog):
    lists_changed = pyqtSignal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db

        self.setWindowTitle(tr("Gérer les listes personnalisées"))
        self.resize(520, 480)
        self.setMinimumSize(420, 360)
        self.setModal(True)
        self.setObjectName("manageCustomListsDialog")

        self.setStyleSheet("""
            QDialog#manageCustomListsDialog {
                background-color: #161c2a;
                border: 1px solid #28354d;
                border-radius: 12px;
            }
            QLabel {
                color: #f1f5f9;
            }
            QListWidget {
                background-color: #1a2233;
                border: 1px solid #29364f;
                border-radius: 8px;
                padding: 6px;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 2px 0px;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
            QPushButton {
                font-size: 12px;
                font-weight: 600;
                padding: 7px 14px;
                border-radius: 6px;
            }
        """)

        self._init_ui()
        self._load_lists()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # En-tête
        header_layout = QHBoxLayout()
        title_lbl = QLabel(tr("Listes de chaînes personnalisées"))
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        subtitle_lbl = QLabel(tr("Créez vos listes personnalisées (ex: Salon HD, Van SD) adaptées à vos différents écrans ou connexions."))
        subtitle_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        subtitle_lbl.setWordWrap(True)
        layout.addWidget(subtitle_lbl)

        # Liste des listes personnalisées
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget, stretch=1)

        # Rangée de boutons d'action
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_new = QPushButton(tr("➕ Nouvelle liste"))
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.btn_new.clicked.connect(self._create_new_list)
        btn_row.addWidget(self.btn_new)

        self.btn_rename = QPushButton(tr("✏️ Renommer"))
        self.btn_rename.setEnabled(False)
        self.btn_rename.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rename.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #e2e8f0;
                border: none;
            }
            QPushButton:hover:enabled {
                background-color: #475569;
            }
            QPushButton:disabled {
                color: #64748b;
                background-color: #1e293b;
            }
        """)
        self.btn_rename.clicked.connect(self._rename_selected_list)
        btn_row.addWidget(self.btn_rename)

        self.btn_delete = QPushButton(tr("🗑️ Supprimer"))
        self.btn_delete.setEnabled(False)
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.3);
            }
            QPushButton:hover:enabled {
                background-color: rgba(239, 68, 68, 0.3);
            }
            QPushButton:disabled {
                color: #64748b;
                border-color: transparent;
                background-color: #1e293b;
            }
        """)
        self.btn_delete.clicked.connect(self._delete_selected_list)
        btn_row.addWidget(self.btn_delete)

        btn_row.addStretch()

        self.btn_close = QPushButton(tr("Fermer"))
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #cbd5e1;
                border: none;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

    def _load_lists(self):
        self.list_widget.clear()
        lists = self.db.get_custom_channel_lists()
        for cl in lists:
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 48))
            widget = CustomListItemWidget(cl["id"], cl["name"], cl["item_count"])
            item.setData(Qt.ItemDataRole.UserRole, cl)
            self.list_widget.setItemWidget(item, widget)

        self._on_selection_changed()

    def _get_selected_list_data(self) -> Optional[dict]:
        current_item = self.list_widget.currentItem()
        if not current_item:
            return None
        return current_item.data(Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self):
        has_sel = self.list_widget.currentItem() is not None
        self.btn_rename.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)

    def _create_new_list(self):
        name, ok = ThemedInputDialog.get_text(
            self,
            title=tr("Nouvelle liste personnalisée"),
            label=tr("Nom de la liste (ex: Salon HD, Van SD) :"),
            placeholder=tr("ex: Salon HD"),
            icon_name="playlist_add"
        )
        if ok and name and name.strip():
            clean_name = name.strip()
            try:
                self.db.create_custom_channel_list(clean_name)
                self._load_lists()
                self.lists_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, tr("Erreur"), str(e))

    def _rename_selected_list(self):
        data = self._get_selected_list_data()
        if not data:
            return
        old_name = data["name"]
        new_name, ok = ThemedInputDialog.get_text(
            self,
            title=tr("Renommer la liste"),
            label=tr("Nouveau nom :"),
            text=old_name,
            icon_name="edit"
        )
        if ok and new_name and new_name.strip() and new_name.strip() != old_name:
            success = self.db.rename_custom_channel_list(data["id"], new_name.strip())
            if success:
                self._load_lists()
                self.lists_changed.emit()
            else:
                QMessageBox.warning(self, tr("Erreur"), tr("Ce nom de liste existe déjà."))

    def _delete_selected_list(self):
        data = self._get_selected_list_data()
        if not data:
            return
        confirm = QMessageBox.question(
            self,
            tr("Supprimer la liste"),
            tr("Êtes-vous sûr de vouloir supprimer la liste '{name}' ?\nLes chaînes associées ne seront pas effacées de votre playlist.").format(name=data['name']),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.delete_custom_channel_list(data["id"])
            self._load_lists()
            self.lists_changed.emit()
