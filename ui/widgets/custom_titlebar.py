"""
Barre de titre moderne personnalisée (Custom Title Bar) avec sélecteur de listes,
barre de recherche contextuelle dynamique, et contrôles de fenêtre stylisés.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QMouseEvent

from ui.icons import get_icon, get_app_logo_pixmap, DEFAULT_ICON_COLOR


class CustomTitleBar(QWidget):
    playlist_changed = pyqtSignal(int)
    refresh_clicked = pyqtSignal()
    add_playlist_clicked = pyqtSignal()
    search_text_changed = pyqtSignal(str)
    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    close_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("customTitleBar")
        self.setFixedHeight(48)
        self._drag_pos: Optional[QPoint] = None

        self._init_ui()
        from core.i18n import I18nManager
        I18nManager.instance().language_changed.connect(lambda _: self.retranslate_ui())

    def _init_ui(self):
        from core.i18n import tr
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(10)

        # ------------------ 1. GAUCHE : LOGO & SÉLECTEUR DE LISTE ------------------
        logo_row = QHBoxLayout()
        logo_row.setSpacing(8)

        self.logo_icon = QLabel()
        self.logo_icon.setPixmap(get_app_logo_pixmap(24))
        self.logo_icon.setFixedSize(24, 24)
        self.logo_icon.setScaledContents(True)
        logo_row.addWidget(self.logo_icon)

        self.app_title = QLabel("IPTV Hub")
        self.app_title.setObjectName("appLogoTitle")
        logo_row.addWidget(self.app_title)

        layout.addLayout(logo_row)

        # Séparateur vertical
        sep_v = QFrame()
        sep_v.setFrameShape(QFrame.Shape.VLine)
        sep_v.setStyleSheet("background-color: #334155; margin: 10px 4px;")
        layout.addWidget(sep_v)

        # Menu déroulant des listes de lecture
        self.pl_label = QLabel(tr("Liste :"))
        self.pl_label.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.pl_label)

        self.playlist_combo = QComboBox()
        self.playlist_combo.setMinimumWidth(200)
        self.playlist_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.playlist_combo.currentIndexChanged.connect(self._on_playlist_combo_changed)
        layout.addWidget(self.playlist_combo)

        # Bouton Rafraîchir
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(get_icon("sync", color=DEFAULT_ICON_COLOR))
        self.refresh_btn.setIconSize(QSize(18, 18))
        self.refresh_btn.setProperty("class", "top-btn")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setToolTip("Rafraîchir les chaînes de la liste active")
        self.refresh_btn.clicked.connect(self.refresh_clicked.emit)
        layout.addWidget(self.refresh_btn)

        # Bouton Ajouter une liste
        self.add_btn = QPushButton()
        self.add_btn.setIcon(get_icon("add", color="#818cf8"))
        self.add_btn.setIconSize(QSize(18, 18))
        self.add_btn.setProperty("class", "top-btn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setToolTip("Ajouter une liste de lecture")
        self.add_btn.clicked.connect(self.add_playlist_clicked.emit)
        layout.addWidget(self.add_btn)

        # ------------------ 2. CENTRE : RECHERCHE CONTEXTUELLE ------------------
        layout.addStretch(1)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("topSearchBox")
        self.search_box.setPlaceholderText("Rechercher sur le tableau de bord...")
        self.search_box.setClearButtonEnabled(True)

        search_icon = get_icon("search", color="#94a3b8")
        self.search_box.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.search_box.textChanged.connect(self.search_text_changed.emit)
        layout.addWidget(self.search_box, stretch=2)

        layout.addStretch(1)

        # ------------------ 3. DROITE : STATUT & BOUTONS DE FENÊTRE ------------------
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #818cf8; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(90, 4)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Boutons de contrôle de la fenêtre (Minimize, Maximize, Close)
        win_ctrls = QHBoxLayout()
        win_ctrls.setSpacing(0)
        win_ctrls.setContentsMargins(0, 0, 0, 0)

        # Réduire
        self.min_btn = QPushButton()
        self.min_btn.setIcon(get_icon("remove", color="#cbd5e1"))
        self.min_btn.setIconSize(QSize(16, 16))
        self.min_btn.setProperty("class", "win-ctrl-btn")
        self.min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.min_btn.setToolTip("Réduire")
        self.min_btn.clicked.connect(self.minimize_clicked.emit)
        win_ctrls.addWidget(self.min_btn)

        # Agrandir / Restaurer
        self.max_btn = QPushButton()
        self.max_btn.setIcon(get_icon("crop_square", color="#cbd5e1"))
        self.max_btn.setIconSize(QSize(15, 15))
        self.max_btn.setProperty("class", "win-ctrl-btn")
        self.max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.max_btn.setToolTip("Agrandir / Restaurer")
        self.max_btn.clicked.connect(self.maximize_clicked.emit)
        win_ctrls.addWidget(self.max_btn)

        # Fermer
        self.close_btn = QPushButton()
        self.close_btn.setIcon(get_icon("close", color="#cbd5e1"))
        self.close_btn.setIconSize(QSize(18, 18))
        self.close_btn.setProperty("class", "win-close-btn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Fermer")
        self.close_btn.clicked.connect(self.close_clicked.emit)
        win_ctrls.addWidget(self.close_btn)

        layout.addLayout(win_ctrls)

    def set_category_placeholder(self, section_id: str):
        """Adapte le placeholder de recherche selon la catégorie active."""
        from core.i18n import tr
        self._current_section_id = section_id
        placeholders = {
            "dashboard": tr("Rechercher sur le tableau de bord..."),
            "favorites": tr("Favoris | Filtrer cette section..."),
            "history": tr("Rechercher dans l'historique..."),
            "live": tr("Rechercher une chaîne en direct..."),
            "vod": tr("Rechercher un film (VOD)..."),
            "series": tr("Rechercher une série..."),
            "recently_added": tr("Rechercher parmi les récents ajouts..."),
            "epg": tr("Rechercher dans le guide TV..."),
            "replay": tr("Rechercher dans le Replay..."),
            "settings": tr("Rechercher..."),
        }
        text = placeholders.get(section_id, tr("Rechercher..."))
        self.search_box.setPlaceholderText(text)

    def retranslate_ui(self):
        """Met à jour les libellés, infobulles et placeholder de la barre de titre."""
        from core.i18n import tr
        if hasattr(self, "pl_label"):
            self.pl_label.setText(tr("Liste :"))
        self.refresh_btn.setToolTip(tr("Rafraîchir les chaînes de la liste active"))
        self.add_btn.setToolTip(tr("Ajouter une liste de lecture"))
        self.min_btn.setToolTip(tr("Réduire"))
        self.max_btn.setToolTip(tr("Agrandir / Restaurer"))
        self.close_btn.setToolTip(tr("Fermer"))
        current_sec = getattr(self, "_current_section_id", "dashboard")
        self.set_category_placeholder(current_sec)

    def set_maximized_icon(self, is_max: bool):
        """Change l'icône du bouton agrandir/restaurer."""
        icon_name = "filter_none" if is_max else "crop_square"
        self.max_btn.setIcon(get_icon(icon_name, color="#cbd5e1"))

    def _on_playlist_combo_changed(self, index: int):
        playlist_id = self.playlist_combo.itemData(index)
        if playlist_id:
            self.playlist_changed.emit(playlist_id)

    # ------------------ DÉPLACEMENT DE LA FENÊTRE (DRAG & MOVE) ------------------

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            if win:
                self._drag_pos = event.globalPosition().toPoint() - win.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            win = self.window()
            if win and not getattr(win, "is_fullscreen", False):
                if win.isMaximized() or getattr(getattr(win, "settings", None), "window_maximized", False):
                    if hasattr(win, "_toggle_maximize"):
                        win._toggle_maximize()
                        self._drag_pos = QPoint(win.width() // 2, 20)
                win.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        win = self.window()
        if win and hasattr(win, "settings") and hasattr(win, "db"):
            if not win.isMaximized() and not getattr(win, "is_fullscreen", False) and not win.isMinimized():
                x, y = win.x(), win.y()
                if x > -10000 and y > -10000:
                    win.settings.window_x = x
                    win.settings.window_y = y
                    try:
                        win.db.save_settings(win.settings)
                    except Exception:
                        pass
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()
        super().mouseDoubleClickEvent(event)
