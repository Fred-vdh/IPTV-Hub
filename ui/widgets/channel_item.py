"""
Composant graphique représentant une chaîne dans la liste IPTV.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from core.models import Channel, EPGProgram
from core.image_loader import ImageLoader


class ChannelItemWidget(QWidget):
    favorite_toggled = pyqtSignal(int, bool)  # channel_id, is_favorite

    def __init__(self, channel: Channel, epg_program: Optional[EPGProgram] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.epg_program = epg_program
        self._init_ui()
        self._load_logo()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # 1. Logo de la chaîne
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(42, 42)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("""
            background-color: #1a202c;
            border-radius: 8px;
            border: 1px solid #2d3748;
        """)
        self._set_default_logo()
        layout.addWidget(self.logo_label)

        # 2. Informations textuelles (Nom, Groupe, EPG)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        # Ligne du haut : Nom de la chaîne
        title_row = QHBoxLayout()
        title_row.setSpacing(6)

        self.name_label = QLabel(self.channel.name)
        self.name_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #f8fafc;")
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_row.addWidget(self.name_label)

        # Badge de groupe
        if self.channel.group_title:
            group_badge = QLabel(self.channel.group_title)
            group_badge.setStyleSheet("""
                background-color: #1e293b;
                color: #94a3b8;
                font-size: 10px;
                padding: 1px 6px;
                border-radius: 4px;
                border: 1px solid #334155;
            """)
            title_row.addWidget(group_badge)

        text_layout.addLayout(title_row)

        # Ligne du bas : EPG en cours ou statut
        if self.epg_program:
            self.epg_label = QLabel(f"▶ {self.epg_program.title}")
            self.epg_label.setStyleSheet("font-size: 11px; color: #818cf8;")
            text_layout.addWidget(self.epg_label)

            # Barre de progression EPG
            pct = int(self.epg_program.progress_percentage())
            if pct > 0:
                self.progress_bar = QProgressBar()
                self.progress_bar.setFixedHeight(3)
                self.progress_bar.setTextVisible(False)
                self.progress_bar.setValue(pct)
                self.progress_bar.setStyleSheet("""
                    QProgressBar { background-color: #242b3d; border-radius: 1px; }
                    QProgressBar::chunk { background-color: #6366f1; border-radius: 1px; }
                """)
                text_layout.addWidget(self.progress_bar)
        else:
            self.sub_label = QLabel(self.channel.tvg_name or self.channel.group_title or "Direct")
            self.sub_label.setStyleSheet("font-size: 11px; color: #64748b;")
            text_layout.addWidget(self.sub_label)

        layout.addLayout(text_layout)

        # 3. Bouton Favori (★)
        self.fav_btn = QPushButton("★" if self.channel.is_favorite else "☆")
        self.fav_btn.setFixedSize(28, 28)
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_fav_style()
        self.fav_btn.clicked.connect(self._on_fav_clicked)
        layout.addWidget(self.fav_btn)

    def _set_default_logo(self):
        self.logo_label.setText("📺")
        self.logo_label.setStyleSheet("""
            background-color: #1a202c;
            border-radius: 8px;
            border: 1px solid #2d3748;
            font-size: 18px;
        """)

    def _load_logo(self):
        if not self.channel.logo_url:
            return

        loader = ImageLoader.instance()
        loader.image_loaded.connect(self._on_image_loaded)
        pix = loader.load_image(self.channel.logo_url)
        if pix:
            self._set_pixmap(pix)

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        if url == self.channel.logo_url:
            self._set_pixmap(pixmap)

    def _set_pixmap(self, pixmap: QPixmap):
        scaled = pixmap.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.logo_label.setPixmap(scaled)
        self.logo_label.setText("")

    def _update_fav_style(self):
        if self.channel.is_favorite:
            self.fav_btn.setText("★")
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(245, 158, 11, 0.15);
                    color: #fbbf24;
                    font-size: 16px;
                    border: 1px solid rgba(245, 158, 11, 0.3);
                    border-radius: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(245, 158, 11, 0.3);
                }
            """)
        else:
            self.fav_btn.setText("☆")
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #475569;
                    font-size: 16px;
                    border: none;
                }
                QPushButton:hover {
                    color: #fbbf24;
                }
            """)

    def _on_fav_clicked(self):
        self.channel.is_favorite = not self.channel.is_favorite
        self._update_fav_style()
        if self.channel.id:
            self.favorite_toggled.emit(self.channel.id, self.channel.is_favorite)

    def update_epg(self, epg: Optional[EPGProgram]):
        self.epg_program = epg
        if epg and hasattr(self, "epg_label"):
            self.epg_label.setText(f"▶ {epg.title}")
            pct = int(epg.progress_percentage())
            if hasattr(self, "progress_bar"):
                self.progress_bar.setValue(pct)
