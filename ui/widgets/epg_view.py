"""
Vue et boîte de dialogue pour le Guide Électronique des Programmes (EPG).
Utilise les icônes Google Material Symbols (Outlined).
"""

from typing import Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QSize

from core.models import Channel, EPGProgram
from core.database import Database
from ui.icons import get_icon, DEFAULT_ICON_COLOR


class EPGProgramItemWidget(QFrame):
    def __init__(self, program: EPGProgram, parent: Optional[QFrame] = None):
        super().__init__(parent)
        self.program = program
        self._init_ui()

    def _init_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        is_cur = self.program.is_current()

        if is_cur:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e2438;
                    border: 1px solid #4f46e5;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #141824;
                    border: 1px solid #232a3d;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # En-tête : Heure & Titre
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        time_str = self._format_time_range()
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #818cf8; font-weight: 700; font-size: 12px;")
        header_row.addWidget(time_label)

        if is_cur:
            now_badge = QLabel("EN CE MOMENT")
            now_badge.setStyleSheet("background-color: #ef4444; color: #fff; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 3px;")
            header_row.addWidget(now_badge)

        header_row.addStretch()

        if self.program.category:
            cat_label = QLabel(self.program.category)
            cat_label.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 10px; padding: 2px 6px; border-radius: 4px;")
            header_row.addWidget(cat_label)

        layout.addLayout(header_row)

        # Titre
        title_label = QLabel(self.program.title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #f8fafc;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Description
        if self.program.description:
            desc_label = QLabel(self.program.description)
            desc_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        # Barre de progression si en cours
        if is_cur:
            pct = int(self.program.progress_percentage())
            pbar = QProgressBar()
            pbar.setFixedHeight(4)
            pbar.setTextVisible(False)
            pbar.setValue(pct)
            pbar.setStyleSheet("QProgressBar { background-color: #2b354d; border-radius: 2px; } QProgressBar::chunk { background-color: #6366f1; border-radius: 2px; }")
            layout.addWidget(pbar)

    def _format_time_range(self) -> str:
        try:
            st = datetime.fromisoformat(self.program.start_time).strftime("%H:%M")
            et = datetime.fromisoformat(self.program.end_time).strftime("%H:%M")
            return f"{st} - {et}"
        except Exception:
            return f"{self.program.start_time} - {self.program.end_time}"


class EPGDialog(QDialog):
    def __init__(self, channel: Channel, db: Database, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.channel = channel
        self.db = db
        self.setWindowTitle(f"Guide des programmes — {channel.name}")
        self.resize(550, 650)
        self._init_ui()
        self._load_epg()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # En-tête
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel(f"  Programme TV : {self.channel.name}")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton()
        close_btn.setIcon(get_icon("close", color=DEFAULT_ICON_COLOR))
        close_btn.setIconSize(QSize(18, 18))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        close_btn.setProperty("class", "secondary-btn")
        header.addWidget(close_btn)

        layout.addLayout(header)

        # Liste des programmes
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        layout.addWidget(self.list_widget)

    def _load_epg(self):
        programs = self.db.get_channel_epg(self.channel.tvg_id or self.channel.name, limit=60)
        self.list_widget.clear()

        if not programs:
            no_info_item = QListWidgetItem(self.list_widget)
            label = QLabel("Aucun guide des programmes disponible pour cette chaîne.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #64748b; font-size: 13px; padding: 40px;")
            self.list_widget.setItemWidget(no_info_item, label)
            return

        for prog in programs:
            item = QListWidgetItem(self.list_widget)
            widget = EPGProgramItemWidget(prog)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(item, widget)
