"""
Widget OSD affichant un bouton moderne et discret pour passer le générique de début (Skip Intro).
Respecte strictement la politique de non-perturbation et disparaît automatiquement après le générique.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from core.i18n import tr, I18nManager
from ui.icons import get_icon


class SkipIntroOverlay(QFrame):
    """Overlay escamotable affiché en bas à droite lors du générique de début."""
    skip_intro_requested = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent: Optional[QFrame] = None):
        super().__init__(parent)
        self.setObjectName("skipIntroOverlay")
        self.setMouseTracking(True)

        self._init_ui()

        I18nManager.instance().language_changed.connect(lambda _: self.retranslate_ui())

        # Masqué par défaut
        self.hide()

    def _init_ui(self):
        self.setFixedHeight(44)
        self.setStyleSheet("""
            QFrame#skipIntroOverlay {
                background-color: rgba(15, 23, 42, 0.95);
                border: 1.5px solid #3b82f6;
                border-radius: 10px;
                padding: 2px 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # Bouton principal "Passer le générique"
        self.btn_skip = QPushButton(tr("Passer le générique"))
        self.btn_skip.setIcon(get_icon("skip_next", color="#ffffff"))
        self.btn_skip.setIconSize(QSize(16, 16))
        self.btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_skip.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        self.btn_skip.clicked.connect(self._on_skip_clicked)
        layout.addWidget(self.btn_skip)

        # Bouton de fermeture discret (✕) pour laisser tourner le générique
        self.btn_close = QPushButton()
        self.btn_close.setIcon(get_icon("close", color="#94a3b8"))
        self.btn_close.setIconSize(QSize(13, 13))
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 11px;
            }
            QPushButton:hover {
                background: #334155;
            }
        """)
        self.btn_close.setToolTip(tr("Annuler"))
        self.btn_close.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.btn_close)

        self.adjustSize()

    def _on_skip_clicked(self):
        self.hide()
        self.skip_intro_requested.emit()

    def _on_cancel_clicked(self):
        self.hide()
        self.cancelled.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()

    def retranslate_ui(self):
        """Réactualise dynamiquement les textes selon la langue sélectionnée."""
        if hasattr(self, "btn_skip"):
            self.btn_skip.setText(tr("Passer le générique"))
        if hasattr(self, "btn_close"):
            self.btn_close.setToolTip(tr("Annuler"))
        self.adjustSize()
