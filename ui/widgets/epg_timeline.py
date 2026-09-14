"""
Composant de frise chronologique EPG (Timeline) sous le lecteur vidéo (style IPTVnator moderne).
Affiche l'axe des temps, les cartes de programmes dynamiques, le repère rouge "En direct",
le zoom temporel, la navigation jour par jour et le centrage immédiat sur le programme en cours.
"""

from typing import List, Optional
from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QScrollArea, QFrame, QToolTip, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QFontMetrics,
    QMouseEvent, QWheelEvent
)

from core.models import Channel, EPGProgram
from core.database import Database
from ui.icons import get_icon
from core.i18n import tr


def normalize_to_naive_dt(dt_or_str) -> Optional[datetime]:
    """Convertit une date ou chaîne ISO en datetime naïf local pour des calculs fiables."""
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


class EPGTimelineCanvas(QWidget):
    """
    Zone de dessin haute performance pour l'axe temporel,
    les cartes de programmes et le repère rouge 'En direct'.
    """
    program_selected = pyqtSignal(EPGProgram)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.programs: List[EPGProgram] = []
        self.target_date: date = date.today()
        self.px_per_minute: float = 4.0  # Échelle de zoom par défaut
        self.hovered_prog_idx: int = -1

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(140)

        # Minuteur pour actualiser le repère rouge 'En direct'
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(30000)  # Toutes les 30s
        self.refresh_timer.timeout.connect(self.update)
        self.refresh_timer.start()

    def set_data(self, programs: List[EPGProgram], target_date: date, px_per_minute: float):
        self.programs = programs
        self.target_date = target_date
        self.px_per_minute = px_per_minute
        self._update_dimensions()
        self.update()

    def set_zoom(self, px_per_minute: float):
        self.px_per_minute = max(1.5, min(14.0, px_per_minute))
        self._update_dimensions()
        self.update()

    def get_timeline_start(self) -> datetime:
        day_start = datetime.combine(self.target_date, datetime.min.time())
        return day_start - timedelta(hours=8)

    def get_timeline_end(self) -> datetime:
        day_start = datetime.combine(self.target_date, datetime.min.time())
        return day_start + timedelta(hours=32)

    def _update_dimensions(self):
        # 40 heures au total (8h avant minuit + 24h du jour + 8h après)
        total_minutes = 40 * 60
        total_width = int(total_minutes * self.px_per_minute) + 100
        self.setFixedWidth(max(1200, total_width))

    def get_now_x_position(self) -> Optional[int]:
        """Retourne la coordonnée X du repère rouge actuel si l'heure actuelle est dans la plage temporelle de la frise."""
        now = datetime.now()
        timeline_start = self.get_timeline_start()
        timeline_end = self.get_timeline_end()
        if not (timeline_start <= now <= timeline_end):
            return None

        mins_since_start = (now - timeline_start).total_seconds() / 60.0
        return int(mins_since_start * self.px_per_minute)

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            width = self.width()
            height = self.height()
            time_bar_h = 28
            card_y = time_bar_h + 6
            card_h = height - card_y - 8

            # 1. Arrière-plan global
            painter.fillRect(0, 0, width, height, QColor("#111622"))

            # 2. Axe temporel supérieur (00:00 -> 24:00+)
            painter.fillRect(0, 0, width, time_bar_h, QColor("#161d2d"))
            painter.setPen(QPen(QColor("#243048"), 1))
            painter.drawLine(0, time_bar_h, width, time_bar_h)

            time_font = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
            painter.setFont(time_font)

            timeline_start = self.get_timeline_start()

            # Graduations toutes les 30 minutes sur 40 heures (2400 minutes)
            for minute in range(0, 2401, 30):
                x = int(minute * self.px_per_minute)
                cur_dt = timeline_start + timedelta(minutes=minute)
                is_hour = (cur_dt.minute == 0)

                if is_hour:
                    hour = cur_dt.hour
                    painter.setPen(QPen(QColor("#33415c"), 1))
                    painter.drawLine(x, 0, x, time_bar_h)

                    if cur_dt.date() < self.target_date:
                        time_label = f"Hier {hour:02d}:00" if hour % 2 == 0 else f"{hour:02d}:00"
                    elif cur_dt.date() > self.target_date:
                        time_label = f"+1j {hour:02d}:00"
                    else:
                        time_label = f"{hour:02d}:00"

                    painter.setPen(QColor("#94a3b8"))
                    painter.drawText(x + 6, 18, time_label)

                    painter.setPen(QPen(QColor("#182133"), 1, Qt.PenStyle.DotLine))
                    painter.drawLine(x, time_bar_h, x, height)
                else:
                    painter.setPen(QPen(QColor("#222c3f"), 1))
                    painter.drawLine(x, 14, x, time_bar_h)

            # 3. Rendu des cartes de programmes
            now = datetime.now()

            card_title_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            card_sub_font = QFont("Segoe UI", 8)
            fm_title = QFontMetrics(card_title_font)
            fm_sub = QFontMetrics(card_sub_font)

            visible_left = event.rect().left()

            for idx, prog in enumerate(self.programs):
                st = normalize_to_naive_dt(prog.start_time)
                et = normalize_to_naive_dt(prog.end_time)
                if not st or not et or et <= st:
                    continue

                st_mins = (st - timeline_start).total_seconds() / 60.0
                et_mins = (et - timeline_start).total_seconds() / 60.0
                card_x = int(st_mins * self.px_per_minute)
                card_w = max(24, int((et_mins - st_mins) * self.px_per_minute) - 3)
                card_rect = QRectF(card_x, card_y, card_w, card_h)

                if card_rect.right() < event.rect().left() or card_rect.left() > event.rect().right():
                    continue

                is_current = (st <= now <= et)
                is_hover = (idx == self.hovered_prog_idx)

                if is_current:
                    bg_color = QColor("#1e293b")
                    border_color = QColor("#3b82f6") if is_hover else QColor("#2563eb")
                    border_w = 2.0
                elif is_hover:
                    bg_color = QColor("#1e2638")
                    border_color = QColor("#475569")
                    border_w = 1.5
                else:
                    bg_color = QColor("#151c2a")
                    border_color = QColor("#232c3f")
                    border_w = 1.0

                painter.setBrush(QBrush(bg_color))
                painter.setPen(QPen(border_color, border_w))
                painter.drawRoundedRect(card_rect, 6, 6)

                if is_current:
                    accent_bar = QRectF(card_rect.left(), card_rect.top(), 3.5, card_rect.height())
                    painter.fillRect(accent_bar, QColor("#3b82f6"))

                # Positionnement dynamique du texte pour ne jamais le cacher si la carte déborde à gauche
                text_left = max(card_rect.left() + 8, visible_left + 8)
                available_w = card_rect.right() - 8 - text_left

                if available_w > 30:
                    time_range = f"{st.strftime('%H:%M')} - {et.strftime('%H:%M')}"
                    painter.setFont(card_sub_font)
                    painter.setPen(QColor("#818cf8" if is_current else "#64748b"))
                    painter.drawText(int(text_left), int(card_rect.top() + 18), time_range)

                    painter.setFont(card_title_font)
                    painter.setPen(QColor("#ffffff" if is_current or is_hover else "#e2e8f0"))
                    elided_title = fm_title.elidedText(prog.title, Qt.TextElideMode.ElideRight, int(available_w))
                    painter.drawText(int(text_left), int(card_rect.top() + 36), elided_title)

                    desc_text = prog.category or prog.description
                    if desc_text and card_h > 45:
                        painter.setFont(card_sub_font)
                        painter.setPen(QColor("#94a3b8" if is_current else "#475569"))
                        elided_desc = fm_sub.elidedText(desc_text, Qt.TextElideMode.ElideRight, int(available_w))
                        painter.drawText(int(text_left), int(card_rect.top() + 54), elided_desc)

            # 4. Repère rouge 'En direct'
            now_x = self.get_now_x_position()
            if now_x is not None:
                panel = self.parent() if isinstance(self.parent(), EPGTimelinePanel) else None
                if panel and getattr(panel, "auto_scroll_to_now", False):
                    view_w = panel.scroll_area.viewport().width()
                    scroll_x = panel.scroll_area.horizontalScrollBar().value()
                    # Ancré fermement au centre exact de l'écran (viewport)
                    marker_x = scroll_x + view_w // 2
                else:
                    marker_x = now_x

                painter.setPen(QPen(QColor("#ef4444"), 2))
                painter.drawLine(marker_x, 0, marker_x, height)

                now_str = now.strftime("%H:%M")
                badge_w = 46
                badge_h = 18
                badge_rect = QRectF(marker_x - badge_w / 2, 5, badge_w, badge_h)

                painter.setBrush(QBrush(QColor("#ef4444")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(badge_rect, 4, 4)

                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, now_str)
        except Exception:
            pass

    def mouseMoveEvent(self, event: QMouseEvent):
        try:
            pos = event.position()
            timeline_start = self.get_timeline_start()

            found_idx = -1
            for idx, prog in enumerate(self.programs):
                st = normalize_to_naive_dt(prog.start_time)
                et = normalize_to_naive_dt(prog.end_time)
                if not st or not et:
                    continue
                st_mins = (st - timeline_start).total_seconds() / 60.0
                et_mins = (et - timeline_start).total_seconds() / 60.0
                card_x = int(st_mins * self.px_per_minute)
                card_w = max(24, int((et_mins - st_mins) * self.px_per_minute) - 3)
                rect = QRectF(card_x, 34, card_w, self.height() - 42)

                if rect.contains(pos):
                    found_idx = idx
                    break

            if found_idx != self.hovered_prog_idx:
                self.hovered_prog_idx = found_idx
                self.update()

                if found_idx >= 0:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    prog = self.programs[found_idx]
                    st = normalize_to_naive_dt(prog.start_time)
                    et = normalize_to_naive_dt(prog.end_time)
                    st_str = st.strftime("%H:%M") if st else ""
                    et_str = et.strftime("%H:%M") if et else ""
                    tip = f"<b>{prog.title}</b><br><span style='color:#818cf8;'>{st_str} - {et_str}</span>"
                    if prog.category:
                        tip += f"<br><i>Genre : {prog.category}</i>"
                    if prog.description:
                        tip += f"<br><br>{prog.description[:280]}"
                    QToolTip.showText(event.globalPosition().toPoint(), tip, self)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                    QToolTip.hideText()
        except Exception:
            pass

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.hovered_prog_idx >= 0:
            prog = self.programs[self.hovered_prog_idx]
            self.program_selected.emit(prog)


class EPGTimelinePanel(QWidget):
    """
    Panneau EPG complet avec en-tête d'actions (repliement, zoom, jour, maintenant)
    et zone de défilement horizontal fluide de la frise.
    """
    collapse_toggled = pyqtSignal(bool)

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.current_channel: Optional[Channel] = None
        self.current_date: date = date.today()
        self.is_collapsed: bool = False
        self.fixed_expanded_height: int = 185

        self.setObjectName("epgTimelineContainer")
        self.setStyleSheet("""
            #epgTimelineContainer {
                background-color: #111622;
                border-top: 1px solid #1e2638;
            }
        """)
        self.setFixedHeight(self.fixed_expanded_height)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.auto_scroll_to_now: bool = True
        self._user_scroll_timer = QTimer(self)
        self._user_scroll_timer.setSingleShot(True)
        self._user_scroll_timer.timeout.connect(self._resume_auto_scroll)

        # Minuteur live régulier (toutes les secondes) pour faire défiler les cases et le texte sous le repère fixe
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(1000)
        self.live_timer.timeout.connect(self._on_live_tick)
        self.live_timer.start()

        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ------------------ 1. BARRE D'EN-TÊTE EPG ------------------
        header_bar = QFrame()
        header_bar.setFixedHeight(38)
        header_bar.setMinimumWidth(0)
        header_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_bar.setStyleSheet("background-color: #141a27; border-bottom: 1px solid #1e2638;")

        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(10, 0, 12, 0)
        header_layout.setSpacing(8)

        # Bouton Replier / Déplier (Chevron visible)
        self.toggle_btn = QPushButton()
        self.toggle_btn.setIcon(get_icon("keyboard_arrow_down", color="#ffffff"))
        self.toggle_btn.setIconSize(QSize(20, 20))
        self.toggle_btn.setFixedSize(28, 28)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setToolTip("Masquer le guide EPG")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #242f44;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_collapsed)
        header_layout.addWidget(self.toggle_btn)

        # Titre Chaîne & Programme actuel
        self.channel_title_label = QLabel(tr("Guide des programmes"))
        self.channel_title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        self.channel_title_label.setMinimumWidth(0)
        self.channel_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(self.channel_title_label)

        self.cur_show_label = QLabel("")
        self.cur_show_label.setStyleSheet("font-size: 12px; font-weight: 500; color: #94a3b8;")
        self.cur_show_label.setMinimumWidth(0)
        self.cur_show_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(self.cur_show_label)

        # Note / Information centrale
        self.info_note_label = QLabel(tr("ℹ Programme uniquement. Ce fournisseur expose l'historique mais pas le catch-up."))
        self.info_note_label.setStyleSheet("color: #64748b; font-size: 11px;")
        self.info_note_label.setMinimumWidth(0)
        self.info_note_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(self.info_note_label, stretch=1)

        # Bouton « Maintenant » (Jump to Now)
        self.now_btn = QPushButton(tr("🕒 Maintenant"))
        self.now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.now_btn.setToolTip(tr("Centrer la frise sur l'heure actuelle"))
        self.now_btn.setStyleSheet("""
            QPushButton {
                background-color: #242f44;
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 5px;
                border: 1px solid #33415c;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                color: #ffffff;
                border-color: #60a5fa;
            }
        """)
        self.now_btn.clicked.connect(self.on_now_clicked)
        header_layout.addWidget(self.now_btn)

        # Zoom temporel
        zoom_icon = QLabel()
        zoom_icon.setPixmap(get_icon("search", color="#94a3b8").pixmap(16, 16))
        header_layout.addWidget(zoom_icon)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(2, 10)
        self.zoom_slider.setValue(4)
        self.zoom_slider.setFixedWidth(70)
        self.zoom_slider.setToolTip("Ajuster l'échelle de temps de la frise")
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        header_layout.addWidget(self.zoom_slider)

        # Sélecteur de date (‹ Aujourd'hui ›)
        self.prev_day_btn = QPushButton("‹")
        self.prev_day_btn.setFixedSize(22, 22)
        self.prev_day_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_day_btn.setStyleSheet("background: transparent; color: #94a3b8; font-size: 14px; font-weight: bold; border: none;")
        self.prev_day_btn.clicked.connect(lambda: self._shift_day(-1))
        header_layout.addWidget(self.prev_day_btn)

        self.date_label = QLabel("Aujourd'hui")
        self.date_label.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 600;")
        header_layout.addWidget(self.date_label)

        self.next_day_btn = QPushButton("›")
        self.next_day_btn.setFixedSize(22, 22)
        self.next_day_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_day_btn.setStyleSheet("background: transparent; color: #94a3b8; font-size: 14px; font-weight: bold; border: none;")
        self.next_day_btn.clicked.connect(lambda: self._shift_day(1))
        header_layout.addWidget(self.next_day_btn)

        root_layout.addWidget(header_bar)

        # ------------------ 2. ZONE DE DÉFILEMENT DE LA FRISE ------------------
        self.scroll_area = QScrollArea()
        self.scroll_area.setMinimumWidth(0)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: #111622; border: none; }
            QScrollBar:horizontal {
                background: #111622;
                height: 7px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #252f44;
                min-width: 40px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #3b82f6;
            }
        """)
        self.scroll_area.horizontalScrollBar().actionTriggered.connect(self._on_user_scroll_action)

        self.canvas = EPGTimelineCanvas(self)
        self.scroll_area.setWidget(self.canvas)

        root_layout.addWidget(self.scroll_area)

    def set_channel(self, channel: Channel):
        """Met à jour la chaîne active et recharge sa programmation."""
        self.current_channel = channel
        self.channel_title_label.setText(channel.name)
        today = date.today()
        if self.auto_scroll_to_now or self.current_date < today:
            self.current_date = today
            self.auto_scroll_to_now = True
        self._load_epg()

    def set_current_program_info(self, epg: Optional[EPGProgram]):
        if epg:
            self.cur_show_label.setText(f"— {epg.title}")
        else:
            self.cur_show_label.setText("")

    def _load_epg(self):
        try:
            if not self.current_channel:
                self.canvas.set_data([], self.current_date, self.zoom_slider.value())
                return

            day_start = datetime.combine(self.current_date, datetime.min.time())
            start_dt = day_start - timedelta(hours=8)
            end_dt = day_start + timedelta(hours=32)

            start_iso = start_dt.isoformat()
            end_iso = end_dt.isoformat()

            programs = self.db.get_channel_epg_timeline(self.current_channel, start_iso, end_iso)
            self.canvas.set_data(programs, self.current_date, float(self.zoom_slider.value()))

            today = date.today()
            if self.current_date == today:
                self.date_label.setText("Aujourd'hui")
                self.auto_scroll_to_now = True
                self._user_scroll_timer.stop()
            elif self.current_date == today - timedelta(days=1):
                self.date_label.setText("Hier")
                self.auto_scroll_to_now = False
            elif self.current_date == today + timedelta(days=1):
                self.date_label.setText("Demain")
                self.auto_scroll_to_now = False
            else:
                self.date_label.setText(self.current_date.strftime("%d %b"))
                self.auto_scroll_to_now = False

            if self.current_date == today:
                QTimer.singleShot(50, self.scroll_to_now)
                QTimer.singleShot(200, self.scroll_to_now)
        except Exception:
            pass

    def on_now_clicked(self):
        """Action du bouton 'Maintenant' : recentre immédiatement et réactive le suivi automatique."""
        self.auto_scroll_to_now = True
        self._user_scroll_timer.stop()
        if self.current_date != date.today():
            self.current_date = date.today()
            self._load_epg()
        else:
            self.scroll_to_now()

    def _on_user_scroll_action(self, action: int):
        # Déclenché uniquement lors de l'interaction manuelle de l'utilisateur (clic ou glissement sur scrollbar)
        if action != 0:
            self.auto_scroll_to_now = False
            self._user_scroll_timer.start(15000)
            self.canvas.update()

    def _resume_auto_scroll(self):
        if self.current_date == date.today():
            self.auto_scroll_to_now = True
            self.scroll_to_now()

    def _on_live_tick(self):
        """Tick périodique (1s) : fait défiler le contenu sous le repère fixe au centre et gère le passage de minuit."""
        if self.is_collapsed or not self.current_channel:
            return

        today = date.today()
        # Si minuit est passé pendant le visionnage en direct, basculer automatiquement sur le nouveau jour
        if self.auto_scroll_to_now and self.current_date != today:
            self.current_date = today
            self._load_epg()
            return

        if self.current_date != today:
            self.canvas.update()
            return

        if self.auto_scroll_to_now:
            self.scroll_to_now()
        else:
            self.canvas.update()

    def scroll_to_now(self):
        """Fait défiler la frise pour centrer le repère 'En direct'."""
        try:
            if self.current_date != date.today():
                self.current_date = date.today()
                self._load_epg()
                return

            now_x = self.canvas.get_now_x_position()
            if now_x is not None:
                view_width = self.scroll_area.viewport().width()
                if view_width <= 0:
                    QTimer.singleShot(100, self.scroll_to_now)
                    return
                target_scroll = max(0, int(now_x - view_width / 2))
                self.scroll_area.horizontalScrollBar().setValue(target_scroll)
                self.canvas.update()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_date == date.today() and not self.is_collapsed:
            QTimer.singleShot(50, self.scroll_to_now)

    def _on_zoom_changed(self, val: int):
        self.canvas.set_zoom(float(val))
        if self.current_date == date.today():
            QTimer.singleShot(80, self.scroll_to_now)

    def _shift_day(self, days: int):
        self.current_date += timedelta(days=days)
        self._load_epg()

    def toggle_collapsed(self):
        """Bascule entre état développé et replié."""
        self.set_collapsed(not self.is_collapsed)

    def set_collapsed(self, collapsed: bool):
        self.is_collapsed = collapsed
        self.scroll_area.setVisible(not collapsed)
        if collapsed:
            self.toggle_btn.setIcon(get_icon("keyboard_arrow_up", color="#ffffff"))
            self.toggle_btn.setToolTip("Afficher le guide EPG")
            self.setFixedHeight(38)
        else:
            self.toggle_btn.setIcon(get_icon("keyboard_arrow_down", color="#ffffff"))
            self.toggle_btn.setToolTip("Masquer le guide EPG")
            self.setFixedHeight(self.fixed_expanded_height)
            if self.current_date == date.today():
                QTimer.singleShot(80, self.scroll_to_now)

        self.collapse_toggled.emit(collapsed)

    def wheelEvent(self, event: QWheelEvent):
        if not self.is_collapsed:
            num_degrees = event.angleDelta().y()
            if num_degrees != 0:
                self.auto_scroll_to_now = False
                self._user_scroll_timer.start(15000)
                h_bar = self.scroll_area.horizontalScrollBar()
                h_bar.setValue(h_bar.value() - num_degrees)
                self.canvas.update()
                event.accept()
                return
        super().wheelEvent(event)

    def retranslate_ui(self):
        """Met à jour les textes traduits de la frise chronologique."""
        if hasattr(self, "channel_title_label") and not self.channel:
            self.channel_title_label.setText(tr("Guide des programmes"))
        if hasattr(self, "info_note_label"):
            self.info_note_label.setText(tr("ℹ Programme uniquement. Ce fournisseur expose l'historique mais pas le catch-up."))
        if hasattr(self, "now_btn"):
            self.now_btn.setText(tr("🕒 Maintenant"))
            self.now_btn.setToolTip(tr("Centrer la frise sur l'heure actuelle"))
