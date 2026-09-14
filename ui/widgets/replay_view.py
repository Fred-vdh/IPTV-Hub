"""
Vue moderne pour le Replay TV (Catch-up / Timeshift) permettant de revoir les émissions
des 7 derniers jours sur les chaînes compatibles Xtream.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QSplitter,
    QFrame, QProgressBar, QButtonGroup
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap

from core.models import Channel
from core.database import Database
from core.xtream_client import XtreamClient
from core.image_loader import ImageLoader
from ui.icons import get_icon
from core.i18n import tr, get_locale_weekday, get_locale_month


class _ReplayEpgWorker(QThread):
    """Worker d'arrière-plan pour charger l'EPG complet d'archive d'une chaîne Xtream."""
    finished_data = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, client: XtreamClient, stream_id: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.client = client
        self.stream_id = stream_id

    def run(self):
        try:
            programs = self.client.get_simple_data_table(self.stream_id)
            self.finished_data.emit(programs or [])
        except Exception as e:
            self.error_occurred.emit(str(e))


class ReplayProgramCard(QFrame):
    """Carte représentant une émission passée disponible en Replay."""
    play_clicked = pyqtSignal(dict)  # Données du programme

    def __init__(self, program: Dict[str, Any], channel: Optional[Channel] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.program = program
        self.channel = channel
        self._target_logo_url: str = ""
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("replayProgramCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        start_str = str(self.program.get("start", ""))
        end_str = str(self.program.get("end", ""))
        start_dt: Optional[datetime] = None
        end_dt: Optional[datetime] = None

        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        try:
            end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        now = datetime.now()
        is_future = bool(start_dt and start_dt > now)

        self.setStyleSheet("""
            QFrame#replayProgramCard {
                background-color: #1a2232;
                border: 1px solid #28354c;
                border-radius: 6px;
            }
            QFrame#replayProgramCard:hover {
                background-color: #222c40;
                border-color: #4b5d82;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        # 1. Vignette émission ou Logo de la chaîne
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(50, 36)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("""
            QLabel {
                background-color: #121824;
                border: 1px solid #28354c;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.logo_label)
        self._load_logo()

        # 2. Colonne Heure et Durée
        time_widget = QWidget()
        time_widget.setFixedWidth(96)
        time_col = QVBoxLayout(time_widget)
        time_col.setContentsMargins(0, 0, 0, 0)
        time_col.setSpacing(2)
        time_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if start_dt and end_dt:
            t_start = start_dt.strftime("%H:%M")
            t_end = end_dt.strftime("%H:%M")
            dur_min = int((end_dt - start_dt).total_seconds() // 60)
            if dur_min >= 60:
                dur_str = f"{dur_min // 60}h {dur_min % 60:02d}m"
            else:
                dur_str = f"{dur_min} min"
            time_label = QLabel(f"{t_start} - {t_end}")
            dur_label = QLabel(dur_str)
        else:
            time_label = QLabel(start_str[11:16] if len(start_str) >= 16 else start_str)
            dur_label = QLabel("")

        time_label.setStyleSheet("color: #818cf8; font-weight: 700; font-size: 12px;")
        dur_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
        time_col.addWidget(time_label)
        if dur_label.text():
            time_col.addWidget(dur_label)
        layout.addWidget(time_widget)

        # 3. Colonne Titre & Description
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title = str(self.program.get("title", "")) or tr("Sans titre")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 700;")
        title_lbl.setWordWrap(True)
        info_col.addWidget(title_lbl)

        desc = str(self.program.get("description", "")).strip()
        if desc:
            if len(desc) > 180:
                desc = desc[:177] + "..."
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.2;")
            desc_lbl.setWordWrap(True)
            info_col.addWidget(desc_lbl)

        layout.addLayout(info_col, stretch=1)

        # 4. Bouton Regarder en Replay
        btn_col = QVBoxLayout()
        btn_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if is_future:
            future_badge = QLabel(tr("À venir"))
            future_badge.setStyleSheet("""
                color: #64748b;
                font-size: 11px;
                font-weight: 600;
                background-color: #1a2233;
                padding: 5px 10px;
                border-radius: 6px;
                border: 1px solid #28334a;
            """)
            btn_col.addWidget(future_badge)
        else:
            play_btn = QPushButton(" " + tr("Revoir"))
            play_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
            play_btn.setIconSize(QSize(14, 14))
            play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            play_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    padding: 6px 14px;
                    border-radius: 6px;
                    border: none;
                    min-width: 78px;
                }
                QPushButton:hover {
                    background-color: #6366f1;
                }
                QPushButton:pressed {
                    background-color: #4338ca;
                }
            """)
            play_btn.clicked.connect(lambda: self.play_clicked.emit(self.program))
            btn_col.addWidget(play_btn)

        layout.addLayout(btn_col)

    def _load_logo(self):
        url = (
            str(self.program.get("icon") or "")
            or str(self.program.get("image") or "")
            or str(self.program.get("poster") or "")
            or (self.channel.logo_url if self.channel else "")
        ).strip()

        self._target_logo_url = url
        if url:
            loader = ImageLoader.instance()
            cached = loader.get_cached_image(url)
            if cached and not cached.isNull():
                self._set_logo_pixmap(cached)
            else:
                loader.image_loaded.connect(self._on_logo_loaded)
                loader.request_image(url)
        else:
            self._set_fallback_icon()

    def _on_logo_loaded(self, url: str, pixmap: QPixmap):
        if self._target_logo_url and url == self._target_logo_url and not pixmap.isNull():
            self._set_logo_pixmap(pixmap)

    def _set_logo_pixmap(self, pixmap: QPixmap):
        scaled = pixmap.scaled(
            44, 30,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.logo_label.setPixmap(scaled)

    def _set_fallback_icon(self):
        fallback_pix = get_icon("live_tv", color="#475569").pixmap(22, 22)
        self.logo_label.setPixmap(fallback_pix)


class ReplayView(QWidget):
    """
    Vue principale Replay TV :
    - Volet gauche : Liste des chaînes supportant les archives
    - Volet droit : Sélecteur de date (Jours J-0 à J-6) et liste des programmes disponibles
    """
    # Émet : chaîne, titre émission, url timeshift, durée en secondes
    play_replay_requested = pyqtSignal(object, str, str, float)

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.playlist_id: Optional[int] = None
        self._channels: List[Channel] = []
        self._selected_channel: Optional[Channel] = None
        self._all_programs: List[Dict[str, Any]] = []
        self._selected_date: datetime.date = datetime.now().date()
        self._epg_worker: Optional[_ReplayEpgWorker] = None

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #111622;
                color: #e2e8f0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }
            QScrollBar:vertical {
                border: none;
                background: #111622;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #252f44;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3b4b69;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 16, 24, 16)
        root_layout.setSpacing(14)

        # 1. En-tête de la section
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_label = QPushButton()
        icon_label.setIcon(get_icon("replay", color="#818cf8"))
        icon_label.setIconSize(QSize(28, 28))
        icon_label.setFixedSize(42, 42)
        icon_label.setStyleSheet("background-color: #1e2638; border: 1px solid #2e3a52; border-radius: 8px;")
        header_layout.addWidget(icon_label)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.section_title = QLabel(tr("TV Replay (Rattrapage)"))
        self.section_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")
        self.section_sub = QLabel(tr("Revoyez vos émissions préférées des 7 derniers jours sur les chaînes compatibles."))
        self.section_sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_vbox.addWidget(self.section_title)
        title_vbox.addWidget(self.section_sub)
        header_layout.addLayout(title_vbox)

        header_layout.addStretch()
        root_layout.addLayout(header_layout)

        # 2. Splitter horizontal principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #1e2638;
                width: 1px;
            }
        """)

        # --- Panneau gauche : Recherche & Liste des chaînes ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 14, 0)
        left_layout.setSpacing(10)

        # Recherche de chaînes
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("Rechercher une chaîne..."))
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1b2232;
                color: #f1f5f9;
                border: 1px solid #2a354c;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        left_layout.addWidget(self.search_input)

        # Compteur de chaînes compatibles
        self.channel_count_lbl = QLabel(tr("0 chaîne compatible Replay"))
        self.channel_count_lbl.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 600; padding-left: 2px;")
        left_layout.addWidget(self.channel_count_lbl)

        # Liste des chaînes
        self.channel_list_widget = QListWidget()
        self.channel_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #151b29;
                border: 1px solid #232d40;
                border-radius: 8px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #1c2436;
                color: #cbd5e1;
                font-size: 13px;
                font-weight: 600;
            }
            QListWidget::item:hover {
                background-color: #1e283c;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #2b3852;
                color: #818cf8;
                border-left: 3px solid #6366f1;
            }
        """)
        self.channel_list_widget.currentRowChanged.connect(self._on_channel_selected_index)
        left_layout.addWidget(self.channel_list_widget, stretch=1)

        left_panel.setMinimumWidth(260)
        left_panel.setMaximumWidth(340)
        splitter.addWidget(left_panel)

        # --- Panneau droit : Sélecteur de date & Programmes ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 0, 0, 0)
        right_layout.setSpacing(12)

        # Barre des dates (7 derniers jours)
        self.date_bar_widget = QWidget()
        self.date_bar_layout = QHBoxLayout(self.date_bar_widget)
        self.date_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.date_bar_layout.setSpacing(6)
        self.date_btn_group = QButtonGroup(self)
        self.date_btn_group.setExclusive(True)

        self._build_date_buttons()
        right_layout.addWidget(self.date_bar_widget)

        # Info chaîne active + statut de chargement
        status_row = QHBoxLayout()
        status_row.setSpacing(10)

        self.active_channel_logo = QLabel()
        self.active_channel_logo.setFixedSize(36, 26)
        self.active_channel_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_channel_logo.setStyleSheet("""
            QLabel {
                background-color: #121824;
                border: 1px solid #28354c;
                border-radius: 4px;
            }
        """)
        self.active_channel_logo.hide()
        status_row.addWidget(self.active_channel_logo)

        self.active_channel_title = QLabel(tr("Sélectionnez une chaîne pour voir les programmes"))
        self.active_channel_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        status_row.addWidget(self.active_channel_title)
        status_row.addStretch()

        self.programs_count_lbl = QLabel("")
        self.programs_count_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        status_row.addWidget(self.programs_count_lbl)
        right_layout.addLayout(status_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e2638;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #6366f1;
            }
        """)
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        # Liste des programmes
        self.program_list_widget = QListWidget()
        self.program_list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.program_list_widget.setSpacing(4)
        self.program_list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)
        right_layout.addWidget(self.program_list_widget, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 920])

        root_layout.addWidget(splitter, stretch=1)

    def _build_date_buttons(self):
        """Construit les 7 boutons de sélection de jour (Aujourd'hui, Hier, J-2... J-6)."""
        current_checked_idx = self.date_btn_group.checkedId()
        if current_checked_idx < 0:
            current_checked_idx = 0

        for btn in self.date_btn_group.buttons():
            self.date_btn_group.removeButton(btn)
            btn.deleteLater()

        today = datetime.now().date()

        for i in range(7):
            d = today - timedelta(days=i)
            if i == 0:
                label_txt = tr("Aujourd'hui")
            elif i == 1:
                label_txt = tr("Hier")
            else:
                label_txt = get_locale_weekday(d.weekday(), short=False)

            sub_txt = f"{d.day} {get_locale_month(d.month, short=True)}"

            btn = QPushButton(f"{label_txt}\n{sub_txt}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(44)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e2638;
                    color: #cbd5e1;
                    border: 1px solid #2e3a52;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 10px;
                    line-height: 1.2;
                }
                QPushButton:hover {
                    background-color: #273248;
                    color: #ffffff;
                }
                QPushButton:checked {
                    background-color: #4f46e5;
                    color: #ffffff;
                    border-color: #6366f1;
                }
            """)
            if i == current_checked_idx:
                btn.setChecked(True)
                self._selected_date = d

            btn.clicked.connect(lambda checked, target_date=d: self._on_date_changed(target_date))
            self.date_btn_group.addButton(btn, i)
            self.date_bar_layout.addWidget(btn)

    def set_playlist_id(self, playlist_id: Optional[int]):
        self.playlist_id = playlist_id

    def refresh_view(self):
        """Charge les chaînes compatibles Replay de la liste actuelle."""
        query = self.search_input.text().strip()
        self._channels = self.db.get_archive_channels(self.playlist_id, search_query=query)

        self.channel_list_widget.blockSignals(True)
        self.channel_list_widget.clear()

        count = len(self._channels)
        if count <= 1:
            self.channel_count_lbl.setText(tr("{count} chaîne compatible", count=count))
        else:
            self.channel_count_lbl.setText(tr("{count} chaînes compatibles", count=count))

        for ch in self._channels:
            dur = ch.tv_archive_duration or 7
            item = QListWidgetItem(f"{ch.name}  ({dur}j)")
            item.setData(Qt.ItemDataRole.UserRole, ch)
            item.setToolTip(f"{ch.name} (Archive {dur} jours)")
            self.channel_list_widget.addItem(item)

        self.channel_list_widget.blockSignals(False)

        if self._channels:
            self.channel_list_widget.setCurrentRow(0)
        else:
            self.active_channel_title.setText(tr("Aucune chaîne avec Replay disponible."))
            self.program_list_widget.clear()
            self.programs_count_lbl.setText("")

    def _on_search_text_changed(self, text: str):
        self.refresh_view()

    def _on_channel_selected_index(self, row: int):
        if row < 0 or row >= len(self._channels):
            return
        ch = self._channels[row]
        self._selected_channel = ch
        self.active_channel_title.setText(tr("Programmes : {name}", name=ch.name))
        if ch.logo_url:
            self.active_channel_logo.show()
            loader = ImageLoader.instance()
            cached = loader.get_cached_image(ch.logo_url)
            if cached and not cached.isNull():
                self.active_channel_logo.setPixmap(cached.scaled(32, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                loader.image_loaded.connect(self._on_active_channel_logo_loaded)
                loader.request_image(ch.logo_url)
        else:
            self.active_channel_logo.hide()
        self._load_channel_epg(ch)

    def _on_active_channel_logo_loaded(self, url: str, pixmap: QPixmap):
        if self._selected_channel and url == self._selected_channel.logo_url and not pixmap.isNull():
            self.active_channel_logo.setPixmap(pixmap.scaled(32, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _load_channel_epg(self, channel: Channel):
        """Interroge le serveur Xtream pour récupérer la grille EPG complète de la chaîne."""
        if self._epg_worker and self._epg_worker.isRunning():
            try:
                self._epg_worker.finished_data.disconnect()
                self._epg_worker.error_occurred.disconnect()
            except Exception:
                pass
            self._epg_worker.requestInterruption()
            self._epg_worker.wait(200)
            self._epg_worker = None

        self.program_list_widget.clear()
        self.programs_count_lbl.setText(tr("Chargement du guide..."))
        self.progress_bar.setVisible(True)

        playlist = self.db.get_playlist(channel.playlist_id or 0)
        if not playlist or playlist.playlist_type != "xtream":
            self.progress_bar.setVisible(False)
            self.programs_count_lbl.setText(tr("Replay disponible uniquement sur les flux Xtream."))
            return

        client = XtreamClient(playlist.server_url, playlist.username, playlist.password)
        stream_id = channel.stream_id or channel.tvg_id

        self._epg_worker = _ReplayEpgWorker(client, stream_id, self)
        self._epg_worker.finished_data.connect(self._on_epg_loaded)
        self._epg_worker.error_occurred.connect(self._on_epg_error)
        self._epg_worker.start()

    def _on_epg_loaded(self, programs: list):
        self.progress_bar.setVisible(False)
        self._all_programs = programs
        self._filter_programs_by_date()

    def _on_epg_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.programs_count_lbl.setText(tr("Impossible de charger les programmes d'archive."))

    def _on_date_changed(self, target_date: datetime.date):
        self._selected_date = target_date
        self._filter_programs_by_date()

    def _filter_programs_by_date(self):
        """Filtre les émissions pour n'afficher que celles correspondant au jour sélectionné."""
        self.program_list_widget.clear()

        if not self._all_programs:
            item = QListWidgetItem(self.program_list_widget)
            lbl = QLabel(tr("Aucun programme répertorié pour cette chaîne."))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #64748b; font-size: 13px; padding: 40px;")
            item.setSizeHint(QSize(0, 100))
            self.program_list_widget.setItemWidget(item, lbl)
            self.programs_count_lbl.setText(tr("0 programme"))
            return

        matching_programs: List[Dict[str, Any]] = []
        target_str = self._selected_date.strftime("%Y-%m-%d")

        for p in self._all_programs:
            start_val = str(p.get("start", ""))
            if start_val.startswith(target_str):
                matching_programs.append(p)

        p_count = len(matching_programs)
        if p_count <= 1:
            self.programs_count_lbl.setText(tr("{count} programme", count=p_count))
        else:
            self.programs_count_lbl.setText(tr("{count} programmes", count=p_count))

        if not matching_programs:
            item = QListWidgetItem(self.program_list_widget)
            lbl = QLabel(tr("Aucun programme trouvé pour le {date}.", date=self._selected_date.strftime('%d/%m/%Y')))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #64748b; font-size: 13px; padding: 40px;")
            item.setSizeHint(QSize(0, 100))
            self.program_list_widget.setItemWidget(item, lbl)
            return

        for p in matching_programs:
            item = QListWidgetItem(self.program_list_widget)
            card = ReplayProgramCard(p, channel=self._selected_channel)
            card.play_clicked.connect(self._on_play_program_clicked)
            desc = str(p.get("description", "")).strip()
            card_height = 68 if desc else 50
            item.setSizeHint(QSize(0, card_height))
            self.program_list_widget.setItemWidget(item, card)

    def _on_play_program_clicked(self, program: Dict[str, Any]):
        """Génère l'URL timeshift et demande la lecture."""
        if not self._selected_channel:
            return

        start_str = str(program.get("start", ""))
        end_str = str(program.get("end", ""))
        title = str(program.get("title", "")) or tr("Sans titre")

        duration_minutes = 60
        duration_seconds = 3600.0
        try:
            dt_start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
            diff_sec = (dt_end - dt_start).total_seconds()
            duration_minutes = max(1, int(diff_sec // 60))
            duration_seconds = max(60.0, diff_sec)
        except Exception:
            dt_start = start_str

        playlist = self.db.get_playlist(self._selected_channel.playlist_id or 0)
        if not playlist or playlist.playlist_type != "xtream":
            return

        client = XtreamClient(playlist.server_url, playlist.username, playlist.password)
        stream_id = self._selected_channel.stream_id or self._selected_channel.tvg_id

        stream_url = client.get_timeshift_stream_url(stream_id, dt_start, duration_minutes)

        self.play_replay_requested.emit(self._selected_channel, title, stream_url, duration_seconds)

    def stop_workers(self):
        """Arrête proprement les workers d'arrière-plan."""
        if hasattr(self, "_epg_worker") and self._epg_worker and self._epg_worker.isRunning():
            try:
                self._epg_worker.finished_data.disconnect()
                self._epg_worker.error_occurred.disconnect()
            except Exception:
                pass
            self._epg_worker.requestInterruption()
            self._epg_worker.wait(200)
            self._epg_worker = None

    def closeEvent(self, event):
        self.stop_workers()
        super().closeEvent(event)

    def retranslate_ui(self):
        """Met à jour les textes et libellés du Replay."""
        if hasattr(self, "section_title"):
            self.section_title.setText(tr("TV Replay (Rattrapage)"))
        if hasattr(self, "section_sub"):
            self.section_sub.setText(tr("Revoyez vos émissions préférées des 7 derniers jours sur les chaînes compatibles."))
        if hasattr(self, "search_input"):
            self.search_input.setPlaceholderText(tr("Rechercher une chaîne..."))

        self._build_date_buttons()

        count = len(self._channels)
        if hasattr(self, "channel_count_lbl"):
            if count <= 1:
                self.channel_count_lbl.setText(tr("{count} chaîne compatible", count=count))
            else:
                self.channel_count_lbl.setText(tr("{count} chaînes compatibles", count=count))

        if hasattr(self, "active_channel_title"):
            if self._selected_channel:
                self.active_channel_title.setText(tr("Programmes : {name}", name=self._selected_channel.name))
            elif not self._channels:
                self.active_channel_title.setText(tr("Aucune chaîne avec Replay disponible."))
            else:
                self.active_channel_title.setText(tr("Sélectionnez une chaîne pour voir les programmes"))

        self._filter_programs_by_date()
