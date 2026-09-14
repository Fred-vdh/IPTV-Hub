"""
Barre latérale de navigation compacte ultra-moderne avec icônes Google Material Symbols.
Affichage compact (icônes seules avec info-bulles au survol) :
1. Tableau de bord
2. Favoris globaux (icône Cœur)
--- Séparateur ---
3. TV en direct
4. Films (VOD)
5. Séries
6. Récemment ajoutés (TV, VOD, Séries)
--- En bas : Listes de lecture, Paramètres
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFrame, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter

from core.database import Database
from ui.icons import get_pixmap, DEFAULT_ICON_COLOR


class SidebarButton(QPushButton):
    """Bouton d'action latéral avec rendu direct garanti par QPainter."""
    def __init__(self, icon_name: str, tooltip: str, is_checkable: bool = True, checked: bool = False, icon_size: int = 22, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.icon_size = icon_size
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(40, 40)
        self.setCheckable(is_checkable)
        self.setChecked(checked)
        self.setProperty("class", "sidebar-icon-btn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self._pixmap_normal = get_pixmap(icon_name, color=DEFAULT_ICON_COLOR, size=icon_size)
        self._pixmap_active = get_pixmap(icon_name, color="#ffffff", size=icon_size)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        is_active = self.isChecked() or self.isDown()
        pm = self._pixmap_active if is_active else self._pixmap_normal
        if pm and not pm.isNull():
            x = (self.width() - self.icon_size) // 2
            y = (self.height() - self.icon_size) // 2
            p.drawPixmap(x, y, pm)
        p.end()

    def showEvent(self, event):
        super().showEvent(event)
        self.update()


class Sidebar(QFrame):
    # 'dashboard', 'favorites', 'history', 'live', 'vod', 'series', 'recently_added'
    section_changed = pyqtSignal(str)
    manage_playlists_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("sidebar")
        self.setFixedWidth(56)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 12)
        layout.setSpacing(6)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        # 1. Tableau de bord (actif par défaut)
        self.btn_dashboard = self._create_icon_btn("dashboard", "dashboard", "Tableau de bord", checked=True)
        layout.addWidget(self.btn_dashboard, 0, Qt.AlignmentFlag.AlignHCenter)

        # 2. Favoris globaux (Icône cœur)
        self.btn_favorites = self._create_icon_btn("favorite", "favorites", "Favoris globaux")
        layout.addWidget(self.btn_favorites, 0, Qt.AlignmentFlag.AlignHCenter)

        # 3. Récemment regardé (Icône historique)
        self.btn_history = self._create_icon_btn("history", "history", "Récemment regardé")
        layout.addWidget(self.btn_history, 0, Qt.AlignmentFlag.AlignHCenter)

        # --- Séparateur supérieur ---
        sep_mid = QFrame()
        sep_mid.setFrameShape(QFrame.Shape.HLine)
        sep_mid.setFixedSize(36, 2)
        sep_mid.setStyleSheet("background-color: #334155; border-radius: 1px; border: none;")
        layout.addWidget(sep_mid, 0, Qt.AlignmentFlag.AlignHCenter)

        # 4. Guide des programmes (EPG) - Au-dessus des chaînes de TV en direct
        self.btn_epg = self._create_icon_btn("calendar_month", "epg", "Guide des programmes (EPG)")
        layout.addWidget(self.btn_epg, 0, Qt.AlignmentFlag.AlignHCenter)

        # 5. TV Replay (Rattrapage) - Entre l'EPG et les chaînes de TV
        self.btn_replay = self._create_icon_btn("replay", "replay", "TV Replay (Rattrapage)")
        layout.addWidget(self.btn_replay, 0, Qt.AlignmentFlag.AlignHCenter)

        # 6. TV en direct
        self.btn_live = self._create_icon_btn("live_tv", "live", "TV en direct", checked=False)
        layout.addWidget(self.btn_live, 0, Qt.AlignmentFlag.AlignHCenter)

        # 7. Films (VOD)
        self.btn_vod = self._create_icon_btn("movie", "vod", "Films (VOD)")
        layout.addWidget(self.btn_vod, 0, Qt.AlignmentFlag.AlignHCenter)

        # 8. Séries
        self.btn_series = self._create_icon_btn("video_library", "series", "Séries")
        layout.addWidget(self.btn_series, 0, Qt.AlignmentFlag.AlignHCenter)

        # 9. Récemment ajoutés (TV, Films, Séries)
        self.btn_recent_added = self._create_icon_btn("new_releases", "recently_added", "Récemment ajoutés (TV, VOD, Séries)")
        layout.addWidget(self.btn_recent_added, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

        # --- Bas de page : Gestion des listes & Paramètres ---
        sep_bottom = QFrame()
        sep_bottom.setFrameShape(QFrame.Shape.HLine)
        sep_bottom.setFixedSize(36, 2)
        sep_bottom.setStyleSheet("background-color: #334155; border-radius: 1px; border: none;")
        layout.addWidget(sep_bottom, 0, Qt.AlignmentFlag.AlignHCenter)

        self.btn_manage_pl = SidebarButton("playlist_play", "Gérer les listes de lecture", is_checkable=False, icon_size=22)
        self.btn_manage_pl.clicked.connect(self.manage_playlists_clicked.emit)
        layout.addWidget(self.btn_manage_pl, 0, Qt.AlignmentFlag.AlignHCenter)

        self.btn_settings = SidebarButton("settings", "Paramètres de l'application", is_checkable=True, icon_size=20)
        self.btn_group.addButton(self.btn_settings)
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.btn_settings, 0, Qt.AlignmentFlag.AlignHCenter)

    def _create_icon_btn(self, icon_name: str, section_id: str, tooltip: str, checked: bool = False) -> SidebarButton:
        btn = SidebarButton(icon_name, tooltip, is_checkable=True, checked=checked, icon_size=22)
        self.btn_group.addButton(btn)
        btn.clicked.connect(lambda: self.section_changed.emit(section_id))
        return btn

    def select_section(self, section_id: str):
        """Sélectionne programmatiquement une section et émet le signal correspondant."""
        mapping = {
            "dashboard": self.btn_dashboard,
            "favorites": self.btn_favorites,
            "history": self.btn_history,
            "live": self.btn_live,
            "replay": self.btn_replay,
            "vod": self.btn_vod,
            "series": self.btn_series,
            "epg": self.btn_epg,
            "recently_added": self.btn_recent_added,
        }
        btn = mapping.get(section_id)
        if btn:
            btn.setChecked(True)
            self.section_changed.emit(section_id)

    def set_active_section(self, section_id: str):
        """Met à jour visuellement le bouton actif dans la barre latérale sans émettre section_changed."""
        mapping = {
            "dashboard": self.btn_dashboard,
            "favorites": self.btn_favorites,
            "history": self.btn_history,
            "live": self.btn_live,
            "replay": self.btn_replay,
            "vod": self.btn_vod,
            "series": self.btn_series,
            "epg": self.btn_epg,
            "recently_added": self.btn_recent_added,
        }
        btn = mapping.get(section_id)
        if btn:
            self.btn_group.blockSignals(True)
            btn.setChecked(True)
            self.btn_group.blockSignals(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_buttons()

    def refresh_buttons(self):
        """Force le rafraîchissement et le redessin immédiat de tous les boutons et icônes."""
        self.update()
        for btn in self.findChildren(QPushButton):
            btn.update()
            btn.repaint()
        self.repaint()

