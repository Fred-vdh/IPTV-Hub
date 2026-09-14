"""
Écran EPG (Guide Électronique des Programmes) moderne, interactif et complet pour IPTV Hub.
Comprend :
- Navigation temporelle par jour (Hier, Aujourd'hui, Demain, J+2...) avec bouton "Aller à maintenant"
- Filtrage par catégorie de chaînes et recherche en direct
- Fiche Hero du programme sélectionné avec synopsis, horaires, badge de diffusion et bouton "▶ Regarder la chaîne"
- Grille chronologique multi-chaînes haute performance synchronisée (Axe des heures, Colonne des chaînes, Blocs de programmes, Repère rouge en direct)
"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QScrollArea, QFrame, QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QPoint, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QFontMetrics,
    QMouseEvent, QPixmap
)

from core.models import Channel, EPGProgram
from core.database import Database
from core.image_loader import ImageLoader
from ui.icons import get_icon, get_pixmap

ROW_HEIGHT = 58
CHANNEL_COL_WIDTH = 220
TIME_HEADER_HEIGHT = 34
DEFAULT_PX_PER_MIN = 3.5  # 1 heure = 210 pixels


def normalize_to_naive_dt(dt_or_str) -> Optional[datetime]:
    """Convertit une date ou chaîne ISO en datetime naïf local."""
    if not dt_or_str:
        return None
    try:
        if isinstance(dt_or_str, str):
            dt = datetime.fromisoformat(dt_or_str.strip())
        else:
            dt = dt_or_str
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


class EPGHeroCard(QFrame):
    """
    Fiche d'aperçu Hero du programme actuellement sélectionné.
    Affiche le logo et nom de la chaîne, le titre de l'émission, les horaires,
    le badge de diffusion en direct, le synopsis complet et le bouton de lecture directe.
    """
    play_requested = pyqtSignal(Channel)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel: Optional[Channel] = None
        self.program: Optional[EPGProgram] = None

        self.setFixedHeight(122)
        self.setStyleSheet("""
            EPGHeroCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a2233, stop:0.5 #1f2a3f, stop:1 #171d2b);
                border: 1px solid #2d3b55;
                border-radius: 12px;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 20, 14)
        main_layout.setSpacing(18)

        # 1. Vignette / Logo de la chaîne (Gauche)
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(68, 68)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("""
            background-color: #121722;
            border: 1px solid #28354d;
            border-radius: 10px;
            color: #94a3b8;
            font-weight: 700;
            font-size: 13px;
        """)
        main_layout.addWidget(self.logo_label)

        # 2. Informations détaillées (Centre)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Ligne supérieure : Nom de la chaîne, Heures, Badges
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.channel_name_lbl = QLabel("Sélectionnez une émission")
        self.channel_name_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #a5b4fc;")
        top_row.addWidget(self.channel_name_lbl)

        self.time_lbl = QLabel("")
        self.time_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #94a3b8;")
        top_row.addWidget(self.time_lbl)

        self.status_badge = QLabel("EN DIRECT")
        self.status_badge.setStyleSheet("""
            background-color: #ef4444;
            color: #ffffff;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        self.status_badge.setVisible(False)
        top_row.addWidget(self.status_badge)

        self.category_badge = QLabel("")
        self.category_badge.setStyleSheet("""
            background-color: #242e44;
            color: #cbd5e1;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid #364666;
        """)
        self.category_badge.setVisible(False)
        top_row.addWidget(self.category_badge)

        top_row.addStretch()
        info_layout.addLayout(top_row)

        # Titre du programme
        self.title_lbl = QLabel("Aucun programme sélectionné")
        self.title_lbl.setStyleSheet("font-size: 17px; font-weight: 700; color: #f8fafc;")
        self.title_lbl.setWordWrap(False)
        info_layout.addWidget(self.title_lbl)

        # Description / Synopsis
        self.desc_lbl = QLabel("Cliquez sur un programme dans la grille ci-dessous pour voir ses détails ou double-cliquez pour regarder la chaîne.")
        self.desc_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; line-height: 1.3;")
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setMaximumHeight(36)
        info_layout.addWidget(self.desc_lbl)

        main_layout.addLayout(info_layout, stretch=1)

        # 3. Bouton d'action "Regarder la chaîne" (Droite)
        self.play_btn = QPushButton(" Regarder la chaîne")
        self.play_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
        self.play_btn.setIconSize(QSize(20, 20))
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setFixedSize(180, 42)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #3b82f6);
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #60a5fa);
            }
            QPushButton:pressed {
                background: #3730a3;
            }
            QPushButton:disabled {
                background: #252e42;
                color: #64748b;
            }
        """)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._on_play_clicked)
        main_layout.addWidget(self.play_btn)

    def set_content(self, channel: Optional[Channel], program: Optional[EPGProgram]):
        self.channel = channel
        self.program = program

        if not channel:
            self.channel_name_lbl.setText("Sélectionnez une émission")
            self.title_lbl.setText("Aucun programme sélectionné")
            self.time_lbl.setText("")
            self.desc_lbl.setText("Cliquez sur un programme dans la grille ci-dessous pour voir ses détails.")
            self.status_badge.setVisible(False)
            self.category_badge.setVisible(False)
            self.logo_label.setText("TV")
            self.logo_label.setPixmap(QPixmap())
            self.play_btn.setEnabled(False)
            return

        self.channel_name_lbl.setText(channel.name)
        self.play_btn.setEnabled(True)

        if channel.logo_url:
            pm = ImageLoader.instance().get_cached_image(channel.logo_url)
            if not pm:
                ImageLoader.instance().request_image(channel.logo_url)
            if pm and not pm.isNull():
                pm_scaled = pm.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.logo_label.setPixmap(pm_scaled)
                self.logo_label.setText("")
            else:
                self.logo_label.setPixmap(QPixmap())
                self.logo_label.setText(channel.name[:3].upper())
        else:
            self.logo_label.setPixmap(QPixmap())
            self.logo_label.setText(channel.name[:3].upper())

        if program:
            self.title_lbl.setText(program.title)
            st = normalize_to_naive_dt(program.start_time)
            et = normalize_to_naive_dt(program.end_time)
            if st and et:
                dur_mins = int((et - st).total_seconds() / 60)
                dur_str = f"{dur_mins // 60}h{dur_mins % 60:02d}" if dur_mins >= 60 else f"{dur_mins} min"
                self.time_lbl.setText(f"{st.strftime('%H:%M')} - {et.strftime('%H:%M')}  •  Durée : {dur_str}")
            else:
                self.time_lbl.setText("")

            is_cur = program.is_current()
            self.status_badge.setVisible(is_cur)

            if program.category:
                self.category_badge.setText(program.category)
                self.category_badge.setVisible(True)
            else:
                self.category_badge.setVisible(False)

            desc = program.description or "Aucun synopsis détaillé n'est fourni pour cette émission."
            self.desc_lbl.setText(desc)
        else:
            self.title_lbl.setText("Guide indisponible")
            self.time_lbl.setText("")
            self.status_badge.setVisible(False)
            self.category_badge.setVisible(False)
            self.desc_lbl.setText(f"Aucune information de programme EPG trouvée pour {channel.name}.")

    def _on_play_clicked(self):
        if self.channel:
            self.play_requested.emit(self.channel)


class EPGTimeHeaderCanvas(QWidget):
    """Bandeau temporel supérieur affichant les graduations d'heures."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.px_per_minute = DEFAULT_PX_PER_MIN
        self.target_date = date.today()
        self.setFixedHeight(TIME_HEADER_HEIGHT)
        self._update_width()

    def set_zoom_and_date(self, px_per_minute: float, target_date: date):
        self.px_per_minute = px_per_minute
        self.target_date = target_date
        self._update_width()
        self.update()

    def _update_width(self):
        total_w = int(1440 * self.px_per_minute) + 40
        self.setFixedWidth(max(800, total_w))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        painter.fillRect(self.rect(), QColor("#141a27"))

        painter.setPen(QPen(QColor("#253046"), 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        font = QFont("Segoe UI", 9)
        font.setBold(True)
        painter.setFont(font)

        for minute in range(0, 1440 + 1, 30):
            x = int(minute * self.px_per_minute)
            is_hour = (minute % 60 == 0)

            if is_hour:
                painter.setPen(QPen(QColor("#3b4b69"), 1))
                painter.drawLine(x, 18, x, self.height() - 1)

                h = minute // 60
                time_str = f"{h:02d}:00"
                painter.setPen(QColor("#cbd5e1"))
                painter.drawText(x + 4, 15, time_str)
            else:
                painter.setPen(QPen(QColor("#253046"), 1))
                painter.drawLine(x, 24, x, self.height() - 1)

                h = minute // 60
                time_str = f"{h:02d}:30"
                painter.setPen(QColor("#64748b"))
                painter.drawText(x + 4, 15, time_str)

        now = datetime.now()
        if self.target_date == now.date():
            mins_now = now.hour * 60 + now.minute + now.second / 60.0
            x_now = int(mins_now * self.px_per_minute)

            painter.setPen(QPen(QColor("#ef4444"), 2))
            painter.drawLine(x_now, 0, x_now, self.height())

            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(
                QPoint(x_now - 5, 0),
                QPoint(x_now + 5, 0),
                QPoint(x_now, 7)
            )

        painter.end()


class EPGChannelColumnCanvas(QWidget):
    """Colonne verticale des chaînes (Logo + Nom de la chaîne + Numéro)."""
    channel_clicked = pyqtSignal(Channel)
    channel_double_clicked = pyqtSignal(Channel)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channels: List[Channel] = []
        self.selected_channel_id: Optional[int] = None
        self.hovered_row: int = -1
        self.setFixedWidth(CHANNEL_COL_WIDTH)
        self.setMouseTracking(True)

    def set_channels(self, channels: List[Channel]):
        self.channels = channels
        self.setFixedHeight(max(400, len(channels) * ROW_HEIGHT))
        self.update()

    def set_selected_channel(self, channel_id: Optional[int]):
        self.selected_channel_id = channel_id
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        row = int(event.position().y() // ROW_HEIGHT)
        if 0 <= row < len(self.channels):
            if row != self.hovered_row:
                self.hovered_row = row
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.update()
        else:
            if self.hovered_row != -1:
                self.hovered_row = -1
                self.unsetCursor()
                self.update()

    def leaveEvent(self, event):
        self.hovered_row = -1
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        row = int(event.position().y() // ROW_HEIGHT)
        if 0 <= row < len(self.channels):
            ch = self.channels[row]
            self.selected_channel_id = ch.id
            self.channel_clicked.emit(ch)
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        row = int(event.position().y() // ROW_HEIGHT)
        if 0 <= row < len(self.channels):
            ch = self.channels[row]
            self.selected_channel_id = ch.id
            self.channel_double_clicked.emit(ch)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        clip_rect = event.rect()
        painter.fillRect(clip_rect, QColor("#161c2a"))

        start_row = max(0, clip_rect.top() // ROW_HEIGHT)
        end_row = min(len(self.channels), (clip_rect.bottom() // ROW_HEIGHT) + 1)

        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)
        fm = QFontMetrics(font)

        for r in range(start_row, end_row):
            ch = self.channels[r]
            y = r * ROW_HEIGHT

            is_sel = (self.selected_channel_id is not None and ch.id == self.selected_channel_id)
            is_hov = (r == self.hovered_row)

            if is_sel:
                painter.fillRect(0, y, self.width(), ROW_HEIGHT, QColor("#222d42"))
                painter.fillRect(0, y, 4, ROW_HEIGHT, QColor("#6366f1"))
            elif is_hov:
                painter.fillRect(0, y, self.width(), ROW_HEIGHT, QColor("#1c2436"))

            painter.setPen(QPen(QColor("#253046"), 1))
            painter.drawLine(0, y + ROW_HEIGHT - 1, self.width(), y + ROW_HEIGHT - 1)

            logo_x = 14
            logo_y = y + (ROW_HEIGHT - 34) // 2
            logo_rect = QRectF(logo_x, logo_y, 34, 34)

            painter.setBrush(QBrush(QColor("#111622")))
            painter.setPen(QPen(QColor("#28354d"), 1))
            painter.drawRoundedRect(logo_rect, 6, 6)

            if ch.logo_url:
                pm = ImageLoader.instance().get_cached_image(ch.logo_url)
                if not pm:
                    ImageLoader.instance().request_image(ch.logo_url)
                if pm and not pm.isNull():
                    pm_scaled = pm.scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    painter.drawPixmap(logo_x + 2, logo_y + 2, pm_scaled)
                else:
                    painter.setPen(QColor("#64748b"))
                    painter.drawText(logo_rect, Qt.AlignmentFlag.AlignCenter, str(r + 1))
            else:
                painter.setPen(QColor("#64748b"))
                painter.drawText(logo_rect, Qt.AlignmentFlag.AlignCenter, str(r + 1))

            text_x = logo_x + 44
            text_w = self.width() - text_x - 10
            painter.setPen(QColor("#f8fafc" if is_sel else "#e2e8f0"))
            elided_name = fm.elidedText(ch.name, Qt.TextElideMode.ElideRight, text_w)
            painter.drawText(text_x, y + (ROW_HEIGHT // 2) + 5, elided_name)

        painter.setPen(QPen(QColor("#253046"), 1))
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        painter.end()


class EPGProgramsGridCanvas(QWidget):
    """
    Grille centrale des cartes de programmes EPG.
    Chaque programme est tracé en fonction de son heure de début et de fin.
    """
    program_clicked = pyqtSignal(Channel, EPGProgram)
    program_double_clicked = pyqtSignal(Channel, EPGProgram)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channels: List[Channel] = []
        self.programs_by_channel: Dict[int, List[EPGProgram]] = {}
        self.target_date: date = date.today()
        self.px_per_minute: float = DEFAULT_PX_PER_MIN

        self.selected_prog_key: Optional[Tuple[int, int]] = None
        self.hovered_prog_key: Optional[Tuple[int, int]] = None

        self.setMouseTracking(True)
        self._update_dimensions()

        self.timer = QTimer(self)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self.update)
        self.timer.start()

    def set_data(self, channels: List[Channel], programs_by_channel: Dict[int, List[EPGProgram]], target_date: date, px_per_minute: float):
        self.channels = channels
        self.programs_by_channel = programs_by_channel
        self.target_date = target_date
        self.px_per_minute = px_per_minute
        self._update_dimensions()
        self.update()

    def set_zoom(self, px_per_minute: float):
        self.px_per_minute = px_per_minute
        self._update_dimensions()
        self.update()

    def _update_dimensions(self):
        total_w = int(1440 * self.px_per_minute) + 40
        total_h = max(400, len(self.channels) * ROW_HEIGHT)
        self.setFixedSize(max(800, total_w), total_h)

    def get_program_at_pos(self, pos: QPoint) -> Optional[Tuple[Channel, EPGProgram]]:
        row = int(pos.y() // ROW_HEIGHT)
        if not (0 <= row < len(self.channels)):
            return None

        channel = self.channels[row]
        ch_id = channel.id or row
        programs = self.programs_by_channel.get(ch_id, [])

        x = pos.x()
        for prog in programs:
            st = normalize_to_naive_dt(prog.start_time)
            et = normalize_to_naive_dt(prog.end_time)
            if not st or not et:
                continue

            day_start = datetime.combine(self.target_date, datetime.min.time())
            day_end = datetime.combine(self.target_date, datetime.max.time())

            if et <= day_start or st >= day_end:
                continue

            eff_st = max(st, day_start)
            eff_et = min(et, day_end)

            start_min = (eff_st - day_start).total_seconds() / 60.0
            dur_min = (eff_et - eff_st).total_seconds() / 60.0

            prog_x = int(start_min * self.px_per_minute)
            prog_w = max(24, int(dur_min * self.px_per_minute) - 3)

            if prog_x <= x <= prog_x + prog_w:
                return channel, prog

        return None

    def mouseMoveEvent(self, event: QMouseEvent):
        hit = self.get_program_at_pos(event.pos())
        if hit:
            channel, prog = hit
            key = (channel.id or 0, prog.id or 0)
            if key != self.hovered_prog_key:
                self.hovered_prog_key = key
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.update()
                st = normalize_to_naive_dt(prog.start_time)
                et = normalize_to_naive_dt(prog.end_time)
                time_range = f"{st.strftime('%H:%M')} - {et.strftime('%H:%M')}" if st and et else ""
                tip = f"<b>{prog.title}</b><br>{time_range}<br>{prog.description or ''}"
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            if self.hovered_prog_key is not None:
                self.hovered_prog_key = None
                self.unsetCursor()
                self.update()
                QToolTip.hideText()

    def leaveEvent(self, event):
        self.hovered_prog_key = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        hit = self.get_program_at_pos(event.pos())
        if hit:
            channel, prog = hit
            self.selected_prog_key = (channel.id or 0, prog.id or 0)
            self.program_clicked.emit(channel, prog)
            self.update()
        else:
            row = int(event.position().y() // ROW_HEIGHT)
            if 0 <= row < len(self.channels):
                ch = self.channels[row]
                self.program_clicked.emit(ch, None)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        hit = self.get_program_at_pos(event.pos())
        if hit:
            channel, prog = hit
            self.selected_prog_key = (channel.id or 0, prog.id or 0)
            self.program_double_clicked.emit(channel, prog)
            self.update()
        else:
            row = int(event.position().y() // ROW_HEIGHT)
            if 0 <= row < len(self.channels):
                ch = self.channels[row]
                self.program_double_clicked.emit(ch, None)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        clip = event.rect()
        painter.fillRect(clip, QColor("#111622"))

        start_row = max(0, clip.top() // ROW_HEIGHT)
        end_row = min(len(self.channels), (clip.bottom() // ROW_HEIGHT) + 1)

        font_bold = QFont("Segoe UI", 9)
        font_bold.setBold(True)
        fm_bold = QFontMetrics(font_bold)

        day_start = datetime.combine(self.target_date, datetime.min.time())
        day_end = datetime.combine(self.target_date, datetime.max.time())
        now = datetime.now()

        for r in range(start_row, end_row):
            y = r * ROW_HEIGHT
            painter.setPen(QPen(QColor("#1e283d"), 1))
            painter.drawLine(clip.left(), y + ROW_HEIGHT - 1, clip.right(), y + ROW_HEIGHT - 1)

        painter.setPen(QPen(QColor("#182133"), 1))
        for minute in range(0, 1440 + 1, 60):
            x = int(minute * self.px_per_minute)
            if clip.left() - 50 <= x <= clip.right() + 50:
                painter.drawLine(x, clip.top(), x, clip.bottom())

        for r in range(start_row, end_row):
            ch = self.channels[r]
            ch_id = ch.id or r
            y = r * ROW_HEIGHT + 4
            card_h = ROW_HEIGHT - 8

            programs = self.programs_by_channel.get(ch_id, [])
            if not programs:
                empty_w = int(1440 * self.px_per_minute)
                painter.setBrush(QBrush(QColor("#151c2a")))
                painter.setPen(QPen(QColor("#1e283d"), 1))
                painter.drawRoundedRect(QRectF(2, y, empty_w - 4, card_h), 6, 6)
                painter.setPen(QColor("#475569"))
                painter.setFont(font_bold)
                painter.drawText(QRectF(14, y, empty_w - 20, card_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "Aucun programme disponible pour cette journée")
                continue

            for prog in programs:
                st = normalize_to_naive_dt(prog.start_time)
                et = normalize_to_naive_dt(prog.end_time)
                if not st or not et:
                    continue

                if et <= day_start or st >= day_end:
                    continue

                eff_st = max(st, day_start)
                eff_et = min(et, day_end)

                start_min = (eff_st - day_start).total_seconds() / 60.0
                dur_min = (eff_et - eff_st).total_seconds() / 60.0

                prog_x = int(start_min * self.px_per_minute)
                prog_w = max(24, int(dur_min * self.px_per_minute) - 3)

                if prog_x + prog_w < clip.left() or prog_x > clip.right():
                    continue

                is_sel = (self.selected_prog_key == (ch.id or 0, prog.id or 0))
                is_hov = (self.hovered_prog_key == (ch.id or 0, prog.id or 0))
                is_cur = prog.is_current()

                card_rect = QRectF(prog_x, y, prog_w, card_h)

                if is_sel:
                    bg_col = QColor("#2b3b5c")
                    border_col = QColor("#6366f1")
                    border_w = 2
                elif is_hov:
                    bg_col = QColor("#27354f")
                    border_col = QColor("#4f648d")
                    border_w = 1
                elif is_cur:
                    bg_col = QColor("#202b3e")
                    border_col = QColor("#3b82f6")
                    border_w = 1
                else:
                    bg_col = QColor("#182132")
                    border_col = QColor("#26344d")
                    border_w = 1

                painter.setBrush(QBrush(bg_col))
                painter.setPen(QPen(border_col, border_w))
                painter.drawRoundedRect(card_rect, 6, 6)

                if is_cur and st < now < et:
                    total_dur = (et - st).total_seconds()
                    elapsed = (now - st).total_seconds()
                    ratio = min(1.0, max(0.0, elapsed / total_dur))
                    prog_bar_w = int(card_rect.width() * ratio)
                    painter.fillRect(QRectF(card_rect.left() + 2, card_rect.bottom() - 3, prog_bar_w, 3), QColor("#3b82f6"))

                if prog_w >= 40:
                    text_x = card_rect.left() + 8
                    text_w = card_rect.width() - 14

                    painter.setFont(font_bold)
                    painter.setPen(QColor("#f8fafc" if is_sel else ("#60a5fa" if is_cur else "#e2e8f0")))

                    time_txt = st.strftime("%H:%M")
                    full_txt = f"{time_txt}  {prog.title}"
                    elided = fm_bold.elidedText(full_txt, Qt.TextElideMode.ElideRight, int(text_w))
                    painter.drawText(int(text_x), int(card_rect.top() + 18), elided)

                    if card_h >= 40 and prog.description and prog_w >= 140:
                        font_desc = QFont("Segoe UI", 8)
                        painter.setFont(font_desc)
                        fm_desc = QFontMetrics(font_desc)
                        painter.setPen(QColor("#94a3b8"))
                        desc_elided = fm_desc.elidedText(prog.description, Qt.TextElideMode.ElideRight, int(text_w))
                        painter.drawText(int(text_x), int(card_rect.top() + 34), desc_elided)

        if self.target_date == now.date():
            mins_now = now.hour * 60 + now.minute + now.second / 60.0
            x_now = int(mins_now * self.px_per_minute)

            if clip.left() - 5 <= x_now <= clip.right() + 5:
                painter.setPen(QPen(QColor("#ef4444"), 2))
                painter.drawLine(x_now, clip.top(), x_now, clip.bottom())

        painter.end()


class EPGGridView(QFrame):
    """
    Écran EPG complet : En-tête de navigation temporelle et de filtre,
    Fiche Hero du programme sélectionné, et grille multi-chaînes synchronisée.
    """
    play_channel_requested = pyqtSignal(Channel)
    manage_categories_requested = pyqtSignal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.playlist_id: Optional[int] = None
        self.target_date: date = date.today()
        self.px_per_minute: float = DEFAULT_PX_PER_MIN

        self.all_channels: List[Channel] = []
        self.filtered_channels: List[Channel] = []
        self.programs_cache: Dict[int, List[EPGProgram]] = {}
        self.selected_channel: Optional[Channel] = None
        self.selected_program: Optional[EPGProgram] = None

        self._date_buttons: List[QPushButton] = []

        self.setStyleSheet("""
            EPGGridView {
                background-color: #131927;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        # 1. BARRE DE CONTRÔLES SUPÉRIEURE
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(12)

        title_box = QHBoxLayout()
        title_box.setSpacing(10)
        title_icon = QLabel()
        title_icon.setPixmap(get_pixmap("calendar_month", color="#60a5fa", size=24))
        title_icon.setFixedSize(24, 24)
        title_box.addWidget(title_icon)
        title_lbl = QLabel("Guide des Programmes (EPG)")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        title_box.addWidget(title_lbl)
        ctrl_bar.addLayout(title_box)

        self.date_bar = QHBoxLayout()
        self.date_bar.setSpacing(6)
        self._build_date_buttons()
        ctrl_bar.addLayout(self.date_bar)

        self.now_btn = QPushButton(" Aller à maintenant")
        self.now_btn.setIcon(get_icon("schedule", color="#60a5fa"))
        self.now_btn.setIconSize(QSize(16, 16))
        self.now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.now_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #3b82f6;
                color: #60a5fa;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
                color: #ffffff;
            }
        """)
        self.now_btn.clicked.connect(self.scroll_to_now)
        ctrl_bar.addWidget(self.now_btn)

        ctrl_bar.addStretch()

        self.cat_combo = QComboBox()
        self.cat_combo.setMinimumWidth(180)
        self.cat_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e2638;
                color: #f8fafc;
                border: 1px solid #33415c;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
            }
        """)
        self.cat_combo.currentIndexChanged.connect(self._on_category_changed)
        ctrl_bar.addWidget(self.cat_combo)

        self.filter_btn = QPushButton()
        self.filter_btn.setFixedSize(30, 30)
        self.filter_btn.setIcon(get_icon("filter_list", color="#cbd5e1"))
        self.filter_btn.setIconSize(QSize(16, 16))
        self.filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_btn.setToolTip("Gérer et filtrer les catégories et chaînes")
        self.filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2638;
                border: 1px solid #33415c;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2a374f;
                border-color: #6366f1;
            }
        """)
        self.filter_btn.clicked.connect(self.manage_categories_requested.emit)
        ctrl_bar.addWidget(self.filter_btn)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher une chaîne...")
        self.search_input.setFixedWidth(200)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e2638;
                color: #f8fafc;
                border: 1px solid #33415c;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        ctrl_bar.addWidget(self.search_input)

        zoom_box = QHBoxLayout()
        zoom_box.setSpacing(4)
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedSize(26, 26)
        zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        zoom_out_btn.setToolTip("Dézoomer la frise temporelle")
        zoom_out_btn.setStyleSheet("background-color: #1e2638; border: 1px solid #33415c; border-radius: 4px; color: #cbd5e1; font-weight: bold;")
        zoom_out_btn.clicked.connect(lambda: self._adjust_zoom(-0.6))
        zoom_box.addWidget(zoom_out_btn)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(26, 26)
        zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        zoom_in_btn.setToolTip("Zoomer la frise temporelle")
        zoom_in_btn.setStyleSheet("background-color: #1e2638; border: 1px solid #33415c; border-radius: 4px; color: #cbd5e1; font-weight: bold;")
        zoom_in_btn.clicked.connect(lambda: self._adjust_zoom(0.6))
        zoom_box.addWidget(zoom_in_btn)
        ctrl_bar.addLayout(zoom_box)

        root_layout.addLayout(ctrl_bar)

        # 2. FICHE HERO DU PROGRAMME
        self.hero_card = EPGHeroCard(self)
        self.hero_card.play_requested.connect(self.play_channel_requested.emit)
        root_layout.addWidget(self.hero_card)

        # 3. GRILLE CHRONOLOGIQUE SYNCHRONISÉE
        grid_container = QFrame()
        grid_container.setObjectName("epgGridContainer")
        grid_container.setStyleSheet("""
            QFrame#epgGridContainer {
                background-color: #161c2a;
                border: 1px solid #28334a;
                border-radius: 10px;
            }
        """)
        grid_vbox = QVBoxLayout(grid_container)
        grid_vbox.setContentsMargins(0, 0, 0, 0)
        grid_vbox.setSpacing(0)

        top_grid_row = QHBoxLayout()
        top_grid_row.setContentsMargins(0, 0, 0, 0)
        top_grid_row.setSpacing(0)

        corner_widget = QFrame()
        corner_widget.setObjectName("cornerWidget")
        corner_widget.setFixedSize(CHANNEL_COL_WIDTH, TIME_HEADER_HEIGHT)
        corner_widget.setStyleSheet("""
            QFrame#cornerWidget {
                background-color: #141a27;
                border: none;
                border-bottom: 1px solid #253046;
                border-right: 1px solid #253046;
                border-top-left-radius: 9px;
            }
        """)
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(14, 0, 10, 0)
        corner_lbl = QLabel("CHAÎNES")
        corner_lbl.setStyleSheet("background: transparent; border: none; font-size: 11px; font-weight: 700; color: #94a3b8; letter-spacing: 1px;")
        corner_layout.addWidget(corner_lbl)
        top_grid_row.addWidget(corner_widget)

        self.header_scroll = QScrollArea()
        self.header_scroll.setFixedHeight(TIME_HEADER_HEIGHT)
        self.header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.header_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.header_scroll.setStyleSheet("background: transparent; border: none; border-top-right-radius: 9px;")

        self.time_header_canvas = EPGTimeHeaderCanvas(self)
        self.header_scroll.setWidget(self.time_header_canvas)
        top_grid_row.addWidget(self.header_scroll, stretch=1)

        grid_vbox.addLayout(top_grid_row)

        main_grid_row = QHBoxLayout()
        main_grid_row.setContentsMargins(0, 0, 0, 0)
        main_grid_row.setSpacing(0)

        self.channel_scroll = QScrollArea()
        self.channel_scroll.setFixedWidth(CHANNEL_COL_WIDTH)
        self.channel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.channel_scroll.setStyleSheet("background: transparent; border: none; border-bottom-left-radius: 9px;")

        self.channel_col_canvas = EPGChannelColumnCanvas(self)
        self.channel_col_canvas.channel_clicked.connect(self._on_channel_clicked)
        self.channel_col_canvas.channel_double_clicked.connect(self.play_channel_requested.emit)
        self.channel_scroll.setWidget(self.channel_col_canvas)
        main_grid_row.addWidget(self.channel_scroll)

        self.grid_scroll = QScrollArea()
        self.grid_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_scroll.setStyleSheet("background: transparent; border: none; border-bottom-right-radius: 9px;")

        self.programs_grid_canvas = EPGProgramsGridCanvas(self)
        self.programs_grid_canvas.program_clicked.connect(self._on_program_clicked)
        self.programs_grid_canvas.program_double_clicked.connect(self._on_program_double_clicked)
        self.grid_scroll.setWidget(self.programs_grid_canvas)
        main_grid_row.addWidget(self.grid_scroll, stretch=1)

        grid_vbox.addLayout(main_grid_row, stretch=1)
        root_layout.addWidget(grid_container, stretch=1)

        self.grid_scroll.horizontalScrollBar().valueChanged.connect(
            self.header_scroll.horizontalScrollBar().setValue
        )
        self.grid_scroll.verticalScrollBar().valueChanged.connect(
            self.channel_scroll.verticalScrollBar().setValue
        )

    def _build_date_buttons(self):
        for btn in self._date_buttons:
            btn.deleteLater()
        self._date_buttons.clear()

        today = date.today()
        days_offset = [-1, 0, 1, 2, 3, 4, 5]

        weekday_fr = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]
        month_fr = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]

        for offset in days_offset:
            d = today + timedelta(days=offset)
            if offset == 0:
                label = "Aujourd'hui"
            elif offset == -1:
                label = "Hier"
            elif offset == 1:
                label = "Demain"
            else:
                w_str = weekday_fr[d.weekday()]
                m_str = month_fr[d.month - 1]
                label = f"{w_str} {d.day} {m_str}"

            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("target_date", d)

            is_active = (d == self.target_date)
            btn.setChecked(is_active)
            self._apply_date_button_style(btn, is_active)

            btn.clicked.connect(lambda _, b=btn: self._on_date_button_clicked(b))
            self.date_bar.addWidget(btn)
            self._date_buttons.append(btn)

    def _apply_date_button_style(self, btn: QPushButton, is_active: bool):
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5;
                    color: #ffffff;
                    border: 1px solid #6366f1;
                    border-radius: 6px;
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: 700;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e2638;
                    color: #94a3b8;
                    border: 1px solid #2d3b55;
                    border-radius: 6px;
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #27344c;
                    color: #f1f5f9;
                }
            """)

    def _on_date_button_clicked(self, clicked_btn: QPushButton):
        target_d = clicked_btn.property("target_date")
        if not target_d:
            return
        self.target_date = target_d
        for btn in self._date_buttons:
            active = (btn == clicked_btn)
            btn.setChecked(active)
            self._apply_date_button_style(btn, active)

        self.time_header_canvas.set_zoom_and_date(self.px_per_minute, self.target_date)
        self.load_epg_data()
        if self.target_date == date.today():
            QTimer.singleShot(150, self.scroll_to_now)

    def _adjust_zoom(self, delta: float):
        new_zoom = max(1.5, min(8.0, self.px_per_minute + delta))
        if abs(new_zoom - self.px_per_minute) > 0.05:
            self.px_per_minute = new_zoom
            self.time_header_canvas.set_zoom_and_date(self.px_per_minute, self.target_date)
            self.programs_grid_canvas.set_zoom(self.px_per_minute)

    def set_playlist_id(self, playlist_id: Optional[int]):
        self.playlist_id = playlist_id
        self._load_categories()
        self.refresh_view()

    def _load_categories(self):
        cur_data = self.cat_combo.currentData()
        self.cat_combo.blockSignals(True)
        self.cat_combo.clear()
        self.cat_combo.addItem("Toutes les chaînes", "")

        if self.playlist_id:
            groups = self.db.get_groups(self.playlist_id, stream_type="live", only_enabled=True)
            for g_name, count in groups:
                self.cat_combo.addItem(f"{g_name} ({count})", g_name)

        if cur_data:
            idx = self.cat_combo.findData(cur_data)
            if idx >= 0:
                self.cat_combo.setCurrentIndex(idx)
            else:
                self.cat_combo.setCurrentIndex(0)

        self.cat_combo.blockSignals(False)

    def _on_category_changed(self):
        self._filter_and_reload()

    def _on_search_changed(self):
        self._filter_and_reload()

    def refresh_view(self):
        if not self.playlist_id:
            playlists = self.db.get_playlists()
            if playlists:
                self.playlist_id = playlists[0].id

        if not self.playlist_id:
            return

        self._load_categories()
        self.all_channels = self.db.get_channels(self.playlist_id, stream_type="live", only_enabled=True)
        self._filter_and_reload()

    def _filter_and_reload(self):
        cat = self.cat_combo.currentData() or ""
        search = self.search_input.text().strip().lower()

        filtered = []
        for ch in self.all_channels:
            if cat and ch.group_title != cat:
                continue
            if search and search not in ch.name.lower():
                continue
            filtered.append(ch)

        self.filtered_channels = filtered[:60]
        self.channel_col_canvas.set_channels(self.filtered_channels)
        self.load_epg_data()

    def load_epg_data(self):
        if not self.filtered_channels:
            self.programs_cache.clear()
            self.programs_grid_canvas.set_data([], {}, self.target_date, self.px_per_minute)
            self.selected_channel = None
            self.selected_program = None
            self.hero_card.set_content(None, None)
            return

        tvg_id_map: Dict[str, List[int]] = {}
        for ch in self.filtered_channels:
            ids_to_try = [i for i in [ch.tvg_id, ch.tvg_name, ch.name] if i]
            for i in ids_to_try:
                tvg_id_map.setdefault(i, []).append(ch.id)

        all_ids = list(tvg_id_map.keys())
        day_start_iso = datetime.combine(self.target_date, datetime.min.time()).isoformat()
        day_end_iso = datetime.combine(self.target_date, datetime.max.time()).isoformat()

        self.programs_cache.clear()
        for ch in self.filtered_channels:
            self.programs_cache[ch.id] = []

        if all_ids:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for i in range(0, len(all_ids), 300):
                    chunk = all_ids[i:i + 300]
                    ph = ",".join(["?"] * len(chunk))
                    query = f"""
                        SELECT * FROM epg_programs
                        WHERE tvg_id IN ({ph})
                        AND (
                            (start_time < ? AND end_time > ?)
                            OR substr(start_time, 1, 10) = ?
                        )
                        ORDER BY start_time ASC
                    """
                    params = list(chunk) + [day_end_iso, day_start_iso, str(self.target_date)]
                    try:
                        cursor.execute(query, params)
                        rows = cursor.fetchall()
                        for r in rows:
                            prog = EPGProgram(**dict(r))
                            target_ch_ids = tvg_id_map.get(prog.tvg_id, [])
                            for cid in target_ch_ids:
                                self.programs_cache[cid].append(prog)
                    except Exception:
                        pass

        self.programs_grid_canvas.set_data(
            self.filtered_channels,
            self.programs_cache,
            self.target_date,
            self.px_per_minute
        )

        first_cur_ch = None
        first_cur_prog = None
        for ch in self.filtered_channels:
            for p in self.programs_cache.get(ch.id, []):
                if p.is_current():
                    first_cur_ch = ch
                    first_cur_prog = p
                    break
            if first_cur_ch:
                break

        if first_cur_ch and first_cur_prog:
            self._on_program_clicked(first_cur_ch, first_cur_prog)
        elif self.filtered_channels:
            first_ch = self.filtered_channels[0]
            ch_progs = self.programs_cache.get(first_ch.id, [])
            first_prog = ch_progs[0] if ch_progs else None
            self._on_program_clicked(first_ch, first_prog)
        else:
            self.selected_channel = None
            self.selected_program = None
            self.hero_card.set_content(None, None)

        if self.target_date == date.today():
            QTimer.singleShot(150, self.scroll_to_now)

    def _on_channel_clicked(self, channel: Channel):
        self.selected_channel = channel
        self.channel_col_canvas.set_selected_channel(channel.id)
        cur_prog = None
        for p in self.programs_cache.get(channel.id, []):
            if p.is_current():
                cur_prog = p
                break
        if not cur_prog:
            ch_progs = self.programs_cache.get(channel.id, [])
            cur_prog = ch_progs[0] if ch_progs else None

        self.selected_program = cur_prog
        self.hero_card.set_content(channel, cur_prog)

    def _on_program_clicked(self, channel: Channel, program: Optional[EPGProgram]):
        self.selected_channel = channel
        self.selected_program = program
        self.channel_col_canvas.set_selected_channel(channel.id)
        self.hero_card.set_content(channel, program)

    def _on_program_double_clicked(self, channel: Channel, program: Optional[EPGProgram]):
        self._on_program_clicked(channel, program)
        self.play_channel_requested.emit(channel)

    def scroll_to_now(self):
        """Recentre le défilement horizontal environ 30 minutes avant l'heure actuelle."""
        now = datetime.now()
        mins_now = now.hour * 60 + now.minute
        target_x = max(0, int((mins_now - 25) * self.px_per_minute))
        self.grid_scroll.horizontalScrollBar().setValue(target_x)
