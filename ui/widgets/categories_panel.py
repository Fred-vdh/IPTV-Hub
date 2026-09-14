"""
Panneau des catégories de chaînes IPTV (colonne gauche style IPTVnator).
Affiche la liste des catégories avec compteurs, recherche, tri et filtres.
"""

from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QMenu, QFrame,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QCursor

from ui.icons import get_icon, DEFAULT_ICON_COLOR
from core.models import clean_category_display_name


class CategoryItemWidget(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, name: str, count: int, is_selected: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.name = name
        self.count = count
        self.is_selected = is_selected
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.name)
        super().mousePressEvent(event)

    def _init_ui(self):
        self.setObjectName("categoryCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 10, 4)
        layout.setSpacing(8)

        display_name = clean_category_display_name(self.name)
        self.name_label = QLabel(display_name)
        layout.addWidget(self.name_label, stretch=1)

        self.count_badge = QLabel(str(self.count))
        layout.addWidget(self.count_badge)

        self.set_selected(self.is_selected)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                QFrame#categoryCard {
                    background-color: rgba(37, 99, 235, 0.18);
                    border: 1.5px solid #3b82f6;
                    border-radius: 10px;
                }
            """)
            self.name_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #93c5fd;")
            self.count_badge.setStyleSheet("""
                background-color: rgba(37, 99, 235, 0.4);
                color: #93c5fd;
                font-size: 11px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 8px;
            """)
        else:
            self.setStyleSheet("""
                QFrame#categoryCard {
                    background-color: transparent;
                    border: 1.5px solid transparent;
                    border-radius: 10px;
                }
                QFrame#categoryCard:hover {
                    background-color: rgba(30, 41, 59, 0.6);
                }
            """)
            self.name_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #e2e8f0;")
            self.count_badge.setStyleSheet("""
                background-color: rgba(30, 41, 59, 0.7);
                color: #64748b;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 8px;
            """)


class CategoriesPanel(QFrame):
    category_selected = pyqtSignal(str)
    manage_categories_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("categoriesPanel")
        self.setMinimumWidth(160)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            #categoriesPanel {
                background-color: #161c2a;
                border: none;
            }
        """)

        self._all_categories: List[Tuple[str, int]] = []
        self._current_selected_cat = "Toutes les chaînes"
        self._active_category_widget: Optional[CategoryItemWidget] = None
        self._sort_mode = "default"  # "default", "name_asc", "name_desc", "count"

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        # 1. En-tête : Titre + Boutons d'action (Recherche, Tri, Filtre)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(4, 0, 4, 0)
        header_row.setSpacing(4)

        self.title_label = QLabel("Catégories en direct")
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        header_row.addWidget(self.title_label)
        header_row.addStretch()

        # Bouton Rechercher
        self.search_btn = QPushButton()
        self.search_btn.setIcon(get_icon("search", color=DEFAULT_ICON_COLOR))
        self.search_btn.setIconSize(QSize(18, 18))
        self.search_btn.setFixedSize(28, 28)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setToolTip("Rechercher une catégorie")
        self.search_btn.setStyleSheet("background: transparent; border: none; border-radius: 4px;")
        self.search_btn.clicked.connect(self._toggle_search_box)
        header_row.addWidget(self.search_btn)

        # Bouton Trier
        self.sort_btn = QPushButton()
        self.sort_btn.setIcon(get_icon("sort_by_alpha", color=DEFAULT_ICON_COLOR))
        self.sort_btn.setIconSize(QSize(18, 18))
        self.sort_btn.setFixedSize(28, 28)
        self.sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_btn.setToolTip("Trier les catégories")
        self.sort_btn.setStyleSheet("background: transparent; border: none; border-radius: 4px;")
        self.sort_btn.clicked.connect(self._show_sort_menu)
        header_row.addWidget(self.sort_btn)

        # Bouton Filtrer / Gérer les catégories
        self.filter_btn = QPushButton()
        self.filter_btn.setIcon(get_icon("filter_list", color=DEFAULT_ICON_COLOR))
        self.filter_btn.setIconSize(QSize(18, 18))
        self.filter_btn.setFixedSize(28, 28)
        self.filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_btn.setToolTip("Gérer et filtrer les catégories / chaînes")
        self.filter_btn.setStyleSheet("background: transparent; border: none; border-radius: 4px;")
        self.filter_btn.clicked.connect(self.manage_categories_requested.emit)
        header_row.addWidget(self.filter_btn)

        layout.addLayout(header_row)

        # 2. Barre de recherche (escamotable)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filtrer les catégories...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setStyleSheet("""
            background-color: #20293a;
            border: 1px solid #303d57;
            border-radius: 6px;
            padding: 5px 8px;
            color: #f8fafc;
            font-size: 12px;
        """)
        self.search_edit.textChanged.connect(self._filter_list)
        self.search_edit.setVisible(False)
        layout.addWidget(self.search_edit)

        # 3. Liste des catégories (QListWidget)
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setSpacing(4)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                padding: 0px;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
            QListWidget::item:selected, QListWidget::item:focus {
                background-color: transparent;
                border: none;
                outline: none;
            }
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

    def set_title(self, title: str):
        self.title_label.setText(title)

    def set_categories(self, categories: List[Tuple[str, int]], default_selected: Optional[str] = None):
        self._all_categories = categories
        if default_selected:
            self._current_selected_cat = default_selected
        self._render_categories()

    def _render_categories(self):
        self.list_widget.clear()
        search_txt = self.search_edit.text().strip().lower()

        cats = list(self._all_categories)

        if self._sort_mode == "name_asc":
            cats.sort(key=lambda x: x[0].lower())
        elif self._sort_mode == "name_desc":
            cats.sort(key=lambda x: x[0].lower(), reverse=True)
        elif self._sort_mode == "count":
            cats.sort(key=lambda x: x[1], reverse=True)
        # "default" conserve l'ordre exact transmis par le serveur

        for name, count in cats:
            display_name = clean_category_display_name(name)
            if search_txt and (search_txt not in name.lower() and search_txt not in display_name.lower()):
                continue

            item = QListWidgetItem(self.list_widget)
            is_sel = (name.strip().lower() == self._current_selected_cat.strip().lower())
            widget = CategoryItemWidget(name, count, is_selected=is_sel)
            widget.clicked.connect(self._select_category_by_name)
            if is_sel:
                self._active_category_widget = widget
            item.setSizeHint(QSize(0, 38))
            self.list_widget.setItemWidget(item, widget)
            if is_sel:
                self.list_widget.setCurrentItem(item)
                QTimer.singleShot(0, lambda it=item: self.list_widget.scrollToItem(it))

    def select_category(self, name: str, emit_signal: bool = False):
        """Sélectionne visuellement une catégorie par son nom dans la liste."""
        self._current_selected_cat = name
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            w = self.list_widget.itemWidget(it)
            if isinstance(w, CategoryItemWidget):
                is_sel = (w.name.strip().lower() == name.strip().lower())
                w.set_selected(is_sel)
                if is_sel:
                    self._active_category_widget = w
                    self.list_widget.setCurrentItem(it)
                    QTimer.singleShot(0, lambda item=it: self.list_widget.scrollToItem(item))
        if emit_signal:
            self.category_selected.emit(name)

    def _select_category_by_name(self, name: str):
        self.select_category(name, emit_signal=True)

    def _on_item_clicked(self, item: QListWidgetItem):
        widget = self.list_widget.itemWidget(item)
        if isinstance(widget, CategoryItemWidget):
            self._select_category_by_name(widget.name)

    def _toggle_search_box(self):
        self.search_edit.setVisible(not self.search_edit.isVisible())
        if self.search_edit.isVisible():
            self.search_edit.setFocus()
        else:
            self.search_edit.clear()

    def _filter_list(self, _text: str):
        self._render_categories()

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
        a_count = menu.addAction("📊 Nombre de chaînes (décroissant)")

        a_default.setCheckable(True)
        a_az.setCheckable(True)
        a_za.setCheckable(True)
        a_count.setCheckable(True)

        a_default.setChecked(self._sort_mode == "default")
        a_az.setChecked(self._sort_mode == "name_asc")
        a_za.setChecked(self._sort_mode == "name_desc")
        a_count.setChecked(self._sort_mode == "count")

        a_default.triggered.connect(lambda: self._set_sort_mode("default"))
        a_az.triggered.connect(lambda: self._set_sort_mode("name_asc"))
        a_za.triggered.connect(lambda: self._set_sort_mode("name_desc"))
        a_count.triggered.connect(lambda: self._set_sort_mode("count"))

        menu.exec(QCursor.pos())

    def _set_sort_mode(self, mode: str):
        self._sort_mode = mode
        self._render_categories()

    def _show_filter_menu(self):
        menu = QMenu(self)
        a_all = menu.addAction("Toutes les catégories")
        a_non_empty = menu.addAction("Uniquement catégories avec chaînes")

        a_all.triggered.connect(lambda: self._render_categories())
        a_non_empty.triggered.connect(self._filter_non_empty)
        menu.exec(QCursor.pos())

    def _filter_non_empty(self):
        self._all_categories = [(n, c) for n, c in self._all_categories if c > 0]
        self._render_categories()
