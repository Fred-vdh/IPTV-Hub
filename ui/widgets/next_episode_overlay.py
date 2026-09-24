"""
Widget OSD affichant une boîte de dialogue élégante lors de l'apparition des génériques de fin.
Propose un compte à rebours de 10 secondes pour enchaîner sur l'épisode suivant avec bouton d'annulation.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize

from core.i18n import tr, I18nManager
from ui.icons import get_icon


class NextEpisodeOverlay(QFrame):
    """Overlay escamotable affiché en bas à droite du lecteur lors des génériques de fin."""
    play_next_requested = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent: Optional[QFrame] = None):
        super().__init__(parent)
        self.setObjectName("nextEpisodeOverlay")
        self.setMouseTracking(True)

        self.seconds_left: int = 10
        self.total_seconds: int = 10
        self._next_episode_title: str = ""
        self._is_paused: bool = False

        self._init_ui()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._on_tick)

        I18nManager.instance().language_changed.connect(lambda _: self.retranslate_ui())

        # Masqué par défaut
        self.hide()

    def _init_ui(self):
        self.setFixedWidth(340)
        self.setStyleSheet("""
            QFrame#nextEpisodeOverlay {
                background-color: rgba(15, 23, 42, 0.95);
                border: 1.5px solid #3b82f6;
                border-radius: 12px;
                padding: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # En-tête : Icône + Titre "Épisode suivant" + Bouton fermeture (✕)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(get_icon("skip_next", color="#60a5fa").pixmap(QSize(18, 18)))
        header_layout.addWidget(self.icon_lbl)

        self.header_lbl = QLabel(tr("Épisode suivant"))
        self.header_lbl.setStyleSheet("color: #60a5fa; font-weight: 700; font-size: 12px; letter-spacing: 0.5px;")
        header_layout.addWidget(self.header_lbl)
        header_layout.addStretch()

        self.btn_close = QPushButton()
        self.btn_close.setIcon(get_icon("close", color="#94a3b8"))
        self.btn_close.setIconSize(QSize(14, 14))
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
        self.btn_close.clicked.connect(self._on_cancel_clicked)
        header_layout.addWidget(self.btn_close)
        layout.addLayout(header_layout)

        # Titre de l'épisode suivant
        self.title_lbl = QLabel("S01E02 — ...")
        self.title_lbl.setStyleSheet("color: #f8fafc; font-weight: 600; font-size: 13px; line-height: 1.3;")
        self.title_lbl.setWordWrap(True)
        layout.addWidget(self.title_lbl)

        # Libellé du compte à rebours
        self.timer_lbl = QLabel(tr("Lecture automatique dans {seconds} s...", seconds=10))
        self.timer_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.timer_lbl)

        # Barre de progression discrète
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Ligne de boutons d'action
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_play_now = QPushButton(tr("Lire maintenant"))
        self.btn_play_now.setIcon(get_icon("play_arrow", color="#ffffff"))
        self.btn_play_now.setIconSize(QSize(16, 16))
        self.btn_play_now.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_now.setFixedHeight(30)
        self.btn_play_now.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        self.btn_play_now.clicked.connect(self._on_play_now_clicked)
        btn_layout.addWidget(self.btn_play_now)

        self.btn_cancel = QPushButton(tr("Annuler"))
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                font-weight: 500;
                font-size: 12px;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def setup_episode(self, next_episode_name: str, duration_sec: int = 10):
        """Configure le titre de l'épisode suivant et initialise le décompte."""
        self._next_episode_title = next_episode_name or tr("Épisode suivant")
        self.title_lbl.setText(self._next_episode_title)
        self.total_seconds = max(1, duration_sec)
        self.seconds_left = self.total_seconds
        self._update_countdown_display()

    def start_countdown(self, duration_sec: int = 10):
        """Démarre le compte à rebours et rend l'overlay visible."""
        self.total_seconds = max(1, duration_sec)
        self.seconds_left = self.total_seconds
        self._is_paused = False
        self._update_countdown_display()
        self.show()
        self.raise_()
        self.countdown_timer.start()

    def pause_countdown(self):
        """Suspend le compte à rebours (ex: mise en pause du lecteur)."""
        if self.countdown_timer.isActive():
            self.countdown_timer.stop()
            self._is_paused = True

    def resume_countdown(self):
        """Reprend le compte à rebours si le lecteur est relancé."""
        if self._is_paused and self.isVisible() and self.seconds_left > 0:
            self._is_paused = False
            self.countdown_timer.start()

    def reset(self):
        """Réinitialise et masque l'overlay."""
        self.countdown_timer.stop()
        self._is_paused = False
        self.hide()

    def _on_tick(self):
        self.seconds_left -= 1
        self._update_countdown_display()

        if self.seconds_left <= 0:
            self.countdown_timer.stop()
            self.hide()
            self.play_next_requested.emit()

    def _update_countdown_display(self):
        self.timer_lbl.setText(tr("Lecture automatique dans {seconds} s...", seconds=max(0, self.seconds_left)))
        percent = int((self.seconds_left / max(1, self.total_seconds)) * 100)
        self.progress_bar.setValue(percent)

    def _on_play_now_clicked(self):
        self.countdown_timer.stop()
        self.hide()
        self.play_next_requested.emit()

    def _on_cancel_clicked(self):
        self.countdown_timer.stop()
        self.hide()
        self.cancelled.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()

    def retranslate_ui(self):
        self.header_lbl.setText(tr("Épisode suivant"))
        self.btn_play_now.setText(tr("Lire maintenant"))
        self.btn_cancel.setText(tr("Annuler"))
        self._update_countdown_display()
