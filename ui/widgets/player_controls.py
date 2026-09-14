"""
Contrôles OSD (On-Screen Display) modernes avec icônes Google Material Symbols (Outlined).
Parfaitement centrés en bas de la vidéo avec marges confortables.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel,
    QMenu, QFrame, QSizePolicy, QLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint, QRect
from PyQt6.QtGui import QCursor, QMouseEvent, QWheelEvent, QFontMetrics

from core.models import Channel, EPGProgram
from ui.icons import get_icon, DEFAULT_ICON_COLOR


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


def format_seconds(seconds: float) -> str:
    """Formate des secondes en HH:MM:SS ou MM:SS."""
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class PlayerControls(QWidget):
    mouse_activity = pyqtSignal()
    play_pause_clicked = pyqtSignal()
    previous_channel_clicked = pyqtSignal()
    next_channel_clicked = pyqtSignal()
    rewind_10_clicked = pyqtSignal()
    forward_10_clicked = pyqtSignal()
    back_clicked = pyqtSignal()
    seek_requested = pyqtSignal(float)
    volume_changed = pyqtSignal(int)
    mute_toggled = pyqtSignal()
    fullscreen_toggled = pyqtSignal()
    aspect_ratio_selected = pyqtSignal(str)
    audio_track_selected = pyqtSignal(int)
    subtitle_track_selected = pyqtSignal(int)
    auto_next_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("osdContainer")
        # Widget enfant ordinaire, superposé à la surface vidéo OpenGL.
        # Depuis la migration vers le rendu OpenGL (QOpenGLWidget), l'OSD n'a plus
        # besoin d'être une fenêtre native séparée (Qt.Tool) : c'est justement cette
        # fenêtre séparée qui provoquait des flashs noirs à l'affichage/masquage de
        # l'OSD en plein écran (recomposition DWM de la surface OpenGL).
        # On garde un fond translucide pour laisser voir la vidéo dessous.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

        self.current_channel: Optional[Channel] = None
        self._raw_channel_title: str = "Aucune lecture"
        self._raw_epg_info: str = ""
        self.has_active_media = False
        self.is_playing = False
        self.is_paused = False
        self.is_error = False
        self.is_muted = False
        self.is_vod = False
        self.is_fullscreen = False
        self.total_duration = 0.0
        self.tracks: List[Dict[str, Any]] = []
        self.allow_wheel_scroll = False
        self.scroll_target: Optional[QWidget] = None
        self._custom_back_text: Optional[str] = None
        self._current_epg: Optional[EPGProgram] = None
        self._epg_provider: Optional[Callable[[str], Optional[EPGProgram]]] = None

        self._init_ui()

    def set_epg_provider(self, provider: Optional[Callable[[str], Optional[EPGProgram]]]):
        """Définit la fonction permettant d'interroger le programme EPG actuel pour une chaîne."""
        self._epg_provider = provider

    def _update_live_epg_timeline(self):
        """Met à jour la barre de progression en direct basée sur l'émission EPG."""
        if not self.current_channel or self.current_channel.stream_type != "live":
            return

        now = datetime.now()

        # Si un fournisseur d'EPG est disponible et que le programme est manquant ou dépassé, recharger
        if self._epg_provider and self.current_channel.tvg_id:
            need_refresh = False
            if not self._current_epg:
                need_refresh = True
            else:
                st = normalize_to_naive_dt(self._current_epg.start_time)
                et = normalize_to_naive_dt(self._current_epg.end_time)
                if not st or not et or now > et or now < st:
                    need_refresh = True

            if need_refresh:
                new_epg = self._epg_provider(self.current_channel.tvg_id)
                if new_epg and new_epg != self._current_epg:
                    self._current_epg = new_epg
                    if new_epg.title:
                        self._raw_epg_info = f"—  {new_epg.title}"
                    self.epg_info_label.setToolTip(self._raw_epg_info)
                    self._update_top_bar_elision()

        # Calcul de la progression si EPG valide et en cours
        has_valid_epg = False
        if self._current_epg and self._current_epg.start_time and self._current_epg.end_time:
            st = normalize_to_naive_dt(self._current_epg.start_time)
            et = normalize_to_naive_dt(self._current_epg.end_time)
            if st and et and et > st and (st <= now <= et):
                has_valid_epg = True
                total_sec = (et - st).total_seconds()
                elapsed_sec = (now - st).total_seconds()
                ratio = max(0.0, min(1.0, elapsed_sec / total_sec))
                val = int(ratio * 1000)

                self.curr_time_label.setText(st.strftime("%H:%M"))
                self.total_time_label.setText(et.strftime("%H:%M"))
                self.timeline_slider.setValue(val)
                self.timeline_row.setVisible(True)

        if not has_valid_epg:
            # EPG non disponible pour la diffusion en cours : figer le curseur au début de la barre de progression
            self.curr_time_label.setText("00:00")
            self.total_time_label.setText("--:--")
            self.timeline_slider.setValue(0)
            self.timeline_row.setVisible(True)

    def set_back_button_text(self, text: str):
        """Définit le libellé contextuel du bouton retour (ex: Retour aux favoris, Retour au tableau de bord)."""
        self._custom_back_text = text
        self.back_btn.setText(text)
        self._update_top_bar_elision()

    def show_bars(self):
        self._update_top_bar_elision()
        self._update_bottom_bar_responsive()
        self.top_bar.show()
        self.bottom_bar.show()
        self.unsetCursor()
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def hide_bars(self):
        self.top_bar.hide()
        self.bottom_bar.hide()
        self.setCursor(Qt.CursorShape.BlankCursor)

    def hide(self):
        self.top_bar.hide()
        self.bottom_bar.hide()
        super().hide()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_top_bar_elision()
        self._update_bottom_bar_responsive()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_top_bar_elision()
        self._update_bottom_bar_responsive()

    def hideEvent(self, event):
        self.top_bar.hide()
        self.bottom_bar.hide()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.hide_bars()
        super().closeEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if self.has_active_media:
            delta = event.angleDelta().y()
            if delta != 0:
                step = 5 if delta > 0 else -5
                current_vol = self.volume_slider.value()
                new_vol = max(0, min(100, current_vol + step))
                if new_vol != current_vol:
                    self.volume_slider.setValue(new_vol)
                    self.volume_changed.emit(new_vol)
                self.mouse_activity.emit()
                event.accept()
                return
        super().wheelEvent(event)

    def _init_ui(self):
        self.setMinimumSize(0, 0)
        main_layout = QVBoxLayout(self)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Barre supérieure : Informations sur la chaîne (pilule compacte en haut à gauche)
        top_container = QHBoxLayout()
        top_container.setContentsMargins(20, 18, 20, 0)

        self.top_bar = QWidget()
        self.top_bar.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.top_bar.setStyleSheet("""
            background-color: rgba(28, 36, 52, 0.95);
            border: 1px solid #3d4f72;
            border-radius: 10px;
        """)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(12, 6, 12, 6)
        top_layout.setSpacing(10)

        # Bouton Retour (visible pour VOD / Séries)
        self.back_btn = QPushButton("‹  Retour aux films")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.back_btn.clicked.connect(self.back_clicked.emit)
        self.back_btn.hide()
        top_layout.addWidget(self.back_btn)

        self.channel_title_label = QLabel("Aucune lecture")
        self.channel_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.channel_title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        self.channel_title_label.setToolTip(self._raw_channel_title)
        top_layout.addWidget(self.channel_title_label)

        self.epg_info_label = QLabel("")
        self.epg_info_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.epg_info_label.setStyleSheet("font-size: 13px; color: #818cf8; font-weight: 500;")
        top_layout.addWidget(self.epg_info_label)

        self.badge_live = QLabel("DIRECT")
        self.badge_live.setStyleSheet("""
            background-color: #ef4444;
            color: #ffffff;
            font-size: 10px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
        """)
        top_layout.addWidget(self.badge_live)

        top_container.addWidget(self.top_bar)
        top_container.addStretch()

        main_layout.addLayout(top_container)
        main_layout.addStretch(1)

        # 1.5 Notification centrale : Flux Indisponible / Erreur
        self.error_banner = QFrame()
        self.error_banner.setObjectName("errorBanner")
        self.error_banner.setStyleSheet("""
            #errorBanner {
                background-color: rgba(15, 23, 42, 0.94);
                border: 1.5px solid #ef4444;
                border-radius: 12px;
            }
        """)
        eb_layout = QHBoxLayout(self.error_banner)
        eb_layout.setSpacing(14)
        eb_layout.setContentsMargins(20, 14, 20, 14)

        self.error_icon = QLabel()
        self.error_icon.setPixmap(get_icon("videocam_off", color="#ef4444").pixmap(38, 38))
        eb_layout.addWidget(self.error_icon)

        eb_text_box = QVBoxLayout()
        eb_text_box.setSpacing(3)
        self.error_title = QLabel("FLUX INDISPONIBLE")
        self.error_title.setStyleSheet("color: #f87171; font-size: 15px; font-weight: 700; letter-spacing: 0.5px;")
        eb_text_box.addWidget(self.error_title)

        self.error_desc = QLabel("Le serveur ne diffuse aucun signal pour cette chaîne actuellement.")
        self.error_desc.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 400;")
        eb_text_box.addWidget(self.error_desc)
        eb_layout.addLayout(eb_text_box)

        eb_container = QHBoxLayout()
        eb_container.addStretch()
        eb_container.addWidget(self.error_banner)
        eb_container.addStretch()

        self.error_banner.hide()
        main_layout.addLayout(eb_container)
        main_layout.addStretch(1)

        # 2. Barre inférieure : Contrôles de lecture OSD (toute la largeur de la vidéo)
        self.bottom_bar = QWidget()
        self.bottom_bar.setObjectName("osdBar")
        self.bottom_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.bottom_bar.setMinimumSize(0, 0)
        bottom_layout = QVBoxLayout(self.bottom_bar)
        bottom_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        bottom_layout.setContentsMargins(18, 8, 18, 10)
        bottom_layout.setSpacing(6)

        # 2.1 Slider de progression (visible pour VOD / Catchup / Séries)
        self.timeline_row = QWidget()
        time_layout = QHBoxLayout(self.timeline_row)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(12)

        self.curr_time_label = QLabel("00:00")
        self.curr_time_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 600;")
        time_layout.addWidget(self.curr_time_label)

        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.sliderMoved.connect(self._on_slider_moved)
        self.timeline_slider.sliderReleased.connect(self._on_slider_released)
        time_layout.addWidget(self.timeline_slider)

        self.total_time_label = QLabel("00:00")
        self.total_time_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 600;")
        time_layout.addWidget(self.total_time_label)

        self.timeline_row.setVisible(False)
        bottom_layout.addWidget(self.timeline_row)

        # 2.2 Boutons de commande avec Material Symbols (Outlined #e3e3e3)
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(8)

        # Chaîne Précédente
        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(get_icon("skip_previous", color=DEFAULT_ICON_COLOR))
        self.prev_btn.setIconSize(QSize(22, 22))
        self.prev_btn.setProperty("class", "osd-btn")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setToolTip("Chaîne précédente")
        self.prev_btn.clicked.connect(self.previous_channel_clicked.emit)
        ctrl_row.addWidget(self.prev_btn)

        # Reculer de 10s (replay_10)
        self.rewind_btn = QPushButton()
        self.rewind_btn.setIcon(get_icon("replay_10", color=DEFAULT_ICON_COLOR))
        self.rewind_btn.setIconSize(QSize(20, 20))
        self.rewind_btn.setProperty("class", "osd-btn")
        self.rewind_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rewind_btn.setToolTip("Reculer de 10s")
        self.rewind_btn.clicked.connect(self.rewind_10_clicked.emit)
        ctrl_row.addWidget(self.rewind_btn)

        # Play / Pause (Bouton central accentué)
        self.play_btn = QPushButton()
        self.play_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
        self.play_btn.setIconSize(QSize(28, 28))
        self.play_btn.setProperty("class", "osd-play-btn")
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setToolTip("Lecture / Pause (Espace)")
        self.play_btn.clicked.connect(self.play_pause_clicked.emit)
        ctrl_row.addWidget(self.play_btn)

        # Avancer de 10s (forward_10)
        self.forward_btn = QPushButton()
        self.forward_btn.setIcon(get_icon("forward_10", color=DEFAULT_ICON_COLOR))
        self.forward_btn.setIconSize(QSize(20, 20))
        self.forward_btn.setProperty("class", "osd-btn")
        self.forward_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forward_btn.setToolTip("Avancer de 10s")
        self.forward_btn.clicked.connect(self.forward_10_clicked.emit)
        ctrl_row.addWidget(self.forward_btn)

        # Chaîne Suivante
        self.next_btn = QPushButton()
        self.next_btn.setIcon(get_icon("skip_next", color=DEFAULT_ICON_COLOR))
        self.next_btn.setIconSize(QSize(22, 22))
        self.next_btn.setProperty("class", "osd-btn")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setToolTip("Chaîne suivante")
        self.next_btn.clicked.connect(self.next_channel_clicked.emit)
        ctrl_row.addWidget(self.next_btn)

        # Volume & Mute
        self.mute_btn = QPushButton()
        self.mute_btn.setIcon(get_icon("volume_up", color=DEFAULT_ICON_COLOR))
        self.mute_btn.setIconSize(QSize(20, 20))
        self.mute_btn.setProperty("class", "osd-btn")
        self.mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mute_btn.setToolTip("Muet (M)")
        self.mute_btn.clicked.connect(self.mute_toggled.emit)
        ctrl_row.addWidget(self.mute_btn)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        ctrl_row.addWidget(self.volume_slider)

        ctrl_row.addStretch()

        # Enchaîner épisode suivant automatique (Séries uniquement) - Placé à gauche du groupe de droite
        self.auto_next_btn = QPushButton()
        self.auto_next_btn.setCheckable(True)
        self.auto_next_btn.setChecked(True)
        self.auto_next_btn.setProperty("class", "osd-btn")
        self.auto_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_next_btn.setIcon(get_icon("autoplay", color=DEFAULT_ICON_COLOR))
        self.auto_next_btn.setIconSize(QSize(20, 20))
        self.auto_next_btn.setToolTip("Lecture automatique de l'épisode suivant : Activée (cliquer pour bloquer)")
        self.auto_next_btn.clicked.connect(self._on_auto_next_clicked)
        self.auto_next_btn.setVisible(False)
        ctrl_row.addWidget(self.auto_next_btn)

        # Format d'image (aspect_ratio)
        self.ratio_btn = QPushButton()
        self.ratio_btn.setIcon(get_icon("aspect_ratio", color=DEFAULT_ICON_COLOR))
        self.ratio_btn.setIconSize(QSize(20, 20))
        self.ratio_btn.setProperty("class", "osd-btn")
        self.ratio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ratio_btn.setToolTip("Format d'image (16:9, 4:3, Auto)")
        self.ratio_btn.clicked.connect(self._show_ratio_menu)
        ctrl_row.addWidget(self.ratio_btn)

        # Pistes audio (music_note)
        self.audio_btn = QPushButton()
        self.audio_btn.setIcon(get_icon("music_note", color=DEFAULT_ICON_COLOR))
        self.audio_btn.setIconSize(QSize(20, 20))
        self.audio_btn.setProperty("class", "osd-btn")
        self.audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.audio_btn.setToolTip("Pistes audio")
        self.audio_btn.clicked.connect(self._show_audio_menu)
        ctrl_row.addWidget(self.audio_btn)

        # Sous-titres (subtitles)
        self.sub_btn = QPushButton()
        self.sub_btn.setIcon(get_icon("subtitles", color=DEFAULT_ICON_COLOR))
        self.sub_btn.setIconSize(QSize(20, 20))
        self.sub_btn.setProperty("class", "osd-btn")
        self.sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sub_btn.setToolTip("Sous-titres")
        self.sub_btn.clicked.connect(self._show_subtitles_menu)
        ctrl_row.addWidget(self.sub_btn)

        # Plein écran (fullscreen)
        self.fs_btn = QPushButton()
        self.fs_btn.setIcon(get_icon("fullscreen", color=DEFAULT_ICON_COLOR))
        self.fs_btn.setIconSize(QSize(22, 22))
        self.fs_btn.setProperty("class", "osd-btn")
        self.fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fs_btn.setToolTip("Plein écran (F)")
        self.fs_btn.clicked.connect(self.fullscreen_toggled.emit)
        ctrl_row.addWidget(self.fs_btn)

        bottom_layout.addLayout(ctrl_row)

        bottom_container = QHBoxLayout()
        bottom_container.setContentsMargins(20, 0, 20, 16)
        bottom_container.addWidget(self.bottom_bar)
        main_layout.addLayout(bottom_container)

    # ------------------ MISES À JOUR D'ÉTAT ------------------

    def _update_top_bar_elision(self):
        """Tronque dynamiquement le titre et l'EPG pour que top_bar ne dépasse jamais de la fenêtre vidéo."""
        if not hasattr(self, "top_bar") or not hasattr(self, "channel_title_label"):
            return

        total_width = self.width()
        if total_width <= 0:
            return

        # Marges du top_container : 20px à gauche + 20px à droite = 40px
        max_bar_width = max(80, total_width - 40)
        self.top_bar.setMaximumWidth(max_bar_width)

        # Ajuster le libellé du bouton retour selon la place disponible
        if self.back_btn.isVisible():
            if total_width < 460:
                self.back_btn.setText("‹  Retour")
            elif getattr(self, "_custom_back_text", None):
                self.back_btn.setText(self._custom_back_text)
            elif self.current_channel:
                if self.current_channel.stream_type == "series":
                    self.back_btn.setText("‹  Retour à la fiche série")
                elif self.current_channel.stream_type == "replay":
                    self.back_btn.setText("‹  Retour au Replay")
                elif self.current_channel.stream_type == "trailer":
                    self.back_btn.setText("‹  Retour à la fiche")
                elif self.current_channel.stream_type in ("movie", "vod"):
                    self.back_btn.setText("‹  Retour aux films")
                else:
                    self.back_btn.setText("‹  Retour à la galerie")

        # Calcul des éléments fixes dans top_layout
        top_layout = self.top_bar.layout()
        spacing = top_layout.spacing() if top_layout else 10
        margins = top_layout.contentsMargins() if top_layout else None
        layout_margins = (margins.left() + margins.right()) if margins else 24

        fixed_width = layout_margins + 4  # +4px marge de bordure

        if self.back_btn.isVisible():
            fixed_width += self.back_btn.sizeHint().width() + spacing

        if self.badge_live.isVisible():
            fixed_width += self.badge_live.sizeHint().width() + spacing

        available_for_labels = max(20, max_bar_width - fixed_width)

        # Polices et métriques
        fm_title = QFontMetrics(self.channel_title_label.font())
        title_raw = self._raw_channel_title or ""
        title_ideal_w = fm_title.horizontalAdvance(title_raw) if title_raw else 0

        epg_raw = self._raw_epg_info or ""
        has_epg = bool(epg_raw.strip())
        fm_epg = QFontMetrics(self.epg_info_label.font())
        epg_ideal_w = fm_epg.horizontalAdvance(epg_raw) if has_epg else 0

        # Cas 1 : Pas d'info EPG
        if not has_epg:
            self.epg_info_label.hide()
            self.epg_info_label.setText("")
            elided_title = fm_title.elidedText(title_raw, Qt.TextElideMode.ElideRight, available_for_labels)
            self.channel_title_label.setText(elided_title)
            return

        # Cas 2 : EPG présent, vérifions si tout rentre sans tronquer
        total_needed = title_ideal_w + spacing + epg_ideal_w
        if total_needed <= available_for_labels:
            self.channel_title_label.setText(title_raw)
            self.epg_info_label.setText(epg_raw)
            self.epg_info_label.show()
            return

        # Cas 3 : Espace trop restreint pour les deux (< 240px pour les labels)
        if available_for_labels < 240:
            self.epg_info_label.hide()
            elided_title = fm_title.elidedText(title_raw, Qt.TextElideMode.ElideRight, available_for_labels)
            self.channel_title_label.setText(elided_title)
            return

        # Cas 4 : Partage de l'espace avec priorité au titre
        space_for_both = max(20, available_for_labels - spacing)
        # Allocation cible : 65% pour le titre, 35% pour l'EPG
        target_title_w = int(space_for_both * 0.65)
        target_epg_w = space_for_both - target_title_w

        # Si l'espace alloué à l'EPG est inférieur à 100px, masquer l'EPG au profit du titre
        if target_epg_w < 100:
            self.epg_info_label.hide()
            elided_title = fm_title.elidedText(title_raw, Qt.TextElideMode.ElideRight, available_for_labels)
            self.channel_title_label.setText(elided_title)
            return

        if title_ideal_w <= target_title_w:
            # Le titre n'a pas besoin de tout son quota, le reste va à l'EPG
            title_alloc = title_ideal_w
            epg_alloc = space_for_both - title_alloc
            self.channel_title_label.setText(title_raw)
            elided_epg = fm_epg.elidedText(epg_raw, Qt.TextElideMode.ElideRight, max(20, epg_alloc))
            self.epg_info_label.setText(elided_epg)
            self.epg_info_label.show()
        elif epg_ideal_w <= target_epg_w:
            # L'EPG n'a pas besoin de tout son quota, le reste va au titre
            epg_alloc = epg_ideal_w
            title_alloc = space_for_both - epg_alloc
            elided_title = fm_title.elidedText(title_raw, Qt.TextElideMode.ElideRight, max(20, title_alloc))
            self.channel_title_label.setText(elided_title)
            self.epg_info_label.setText(epg_raw)
            self.epg_info_label.show()
        else:
            # Les deux doivent être tronqués
            elided_title = fm_title.elidedText(title_raw, Qt.TextElideMode.ElideRight, target_title_w)
            elided_epg = fm_epg.elidedText(epg_raw, Qt.TextElideMode.ElideRight, target_epg_w)
            self.channel_title_label.setText(elided_title)
            self.epg_info_label.setText(elided_epg)
            self.epg_info_label.show()

    def _update_bottom_bar_responsive(self):
        """Adapte les contrôles inférieurs lorsque la largeur de la fenêtre vidéo est réduite."""
        if not hasattr(self, "bottom_bar") or not hasattr(self, "volume_slider"):
            return

        w = self.width()
        if w <= 0:
            return

        is_narrow = w < 560
        is_very_narrow = w < 440

        # Saut +/- 10s masqué sur fenêtre étroite
        if hasattr(self, "rewind_btn") and hasattr(self, "forward_btn"):
            self.rewind_btn.setVisible(not is_narrow)
            self.forward_btn.setVisible(not is_narrow)

        # Bouton format d'image masqué sur fenêtre étroite
        if hasattr(self, "ratio_btn"):
            self.ratio_btn.setVisible(not is_narrow)

        # Slider volume réduit ou masqué
        if hasattr(self, "volume_slider"):
            if is_very_narrow:
                self.volume_slider.setVisible(False)
            elif is_narrow:
                self.volume_slider.setVisible(True)
                self.volume_slider.setFixedWidth(50)
            else:
                self.volume_slider.setVisible(True)
                self.volume_slider.setFixedWidth(90)

        # Bouton auto next masqué si très étroit
        if hasattr(self, "auto_next_btn") and self.current_channel and self.current_channel.stream_type == "series":
            self.auto_next_btn.setVisible(not is_very_narrow)

    def update_channel_info(self, channel: Channel, epg: Optional[EPGProgram] = None):
        self.current_channel = channel
        self._current_epg = epg
        self._custom_back_text = None
        self.error_banner.hide()
        self._raw_channel_title = channel.name or ""
        if epg and epg.title:
            self._raw_epg_info = f"—  {epg.title}"
        elif channel.group_title:
            self._raw_epg_info = f"—  {channel.group_title}"
        else:
            self._raw_epg_info = ""

        self.channel_title_label.setToolTip(self._raw_channel_title)
        self.epg_info_label.setToolTip(self._raw_epg_info)

        if channel.stream_type == "live":
            self.back_btn.setVisible(False)
            self.badge_live.setText("DIRECT")
            self.badge_live.setStyleSheet("background-color: #ef4444; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
            self.timeline_row.setVisible(True)
            self.timeline_slider.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.timeline_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._update_live_epg_timeline()
            self.prev_btn.setVisible(True)
            self.next_btn.setVisible(True)
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            self.prev_btn.setToolTip("Chaîne précédente")
            self.next_btn.setToolTip("Chaîne suivante")
            self.rewind_btn.setEnabled(False)
            self.forward_btn.setEnabled(False)
            self.rewind_btn.setToolTip("Non disponible en direct")
            self.forward_btn.setToolTip("Non disponible en direct")
            self.auto_next_btn.setVisible(False)
        elif channel.stream_type == "series":
            self.timeline_slider.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.timeline_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.rewind_btn.setEnabled(True)
            self.forward_btn.setEnabled(True)
            self.rewind_btn.setToolTip("Reculer de 10s")
            self.forward_btn.setToolTip("Avancer de 10s")
            self.back_btn.setText("‹  Retour à la fiche série")
            self.back_btn.setVisible(True)
            self.badge_live.setText("SÉRIE")
            self.badge_live.setStyleSheet("background-color: #10b981; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
            self.timeline_row.setVisible(True)
            self.prev_btn.setVisible(True)
            self.next_btn.setVisible(True)
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            self.prev_btn.setToolTip("Épisode précédent")
            self.next_btn.setToolTip("Épisode suivant")
            self.auto_next_btn.setVisible(True)
        elif channel.stream_type == "replay":
            self.timeline_slider.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.timeline_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.rewind_btn.setEnabled(True)
            self.forward_btn.setEnabled(True)
            self.rewind_btn.setToolTip("Reculer de 10s")
            self.forward_btn.setToolTip("Avancer de 10s")
            self.back_btn.setText("‹  Retour au Replay")
            self.back_btn.setVisible(True)
            self.badge_live.setText("REPLAY")
            self.badge_live.setStyleSheet("background-color: #818cf8; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
            self.timeline_row.setVisible(True)
            self.prev_btn.setVisible(False)
            self.next_btn.setVisible(False)
            self.auto_next_btn.setVisible(False)
        elif channel.stream_type == "trailer":
            self.timeline_slider.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.timeline_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.rewind_btn.setEnabled(True)
            self.forward_btn.setEnabled(True)
            self.rewind_btn.setToolTip("Reculer de 10s")
            self.forward_btn.setToolTip("Avancer de 10s")
            self.back_btn.setText("‹  Retour à la fiche")
            self.back_btn.setVisible(True)
            self.badge_live.setText("BANDE-ANNONCE")
            self.badge_live.setStyleSheet("background-color: #dc2626; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
            self.timeline_row.setVisible(True)
            self.prev_btn.setVisible(False)
            self.next_btn.setVisible(False)
            self.auto_next_btn.setVisible(False)
        elif channel.stream_type in ("movie", "vod"):
            self.timeline_slider.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.timeline_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.rewind_btn.setEnabled(True)
            self.forward_btn.setEnabled(True)
            self.rewind_btn.setToolTip("Reculer de 10s")
            self.forward_btn.setToolTip("Avancer de 10s")
            self.back_btn.setText("‹  Retour aux films")
            self.back_btn.setVisible(True)
            self.badge_live.setText("FILM")
            self.badge_live.setStyleSheet("background-color: #6366f1; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
            self.timeline_row.setVisible(True)
            self.prev_btn.setVisible(False)
            self.next_btn.setVisible(False)
            self.auto_next_btn.setVisible(False)
        else:
            self.timeline_slider.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.timeline_slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.rewind_btn.setEnabled(True)
            self.forward_btn.setEnabled(True)
            self.rewind_btn.setToolTip("Reculer de 10s")
            self.forward_btn.setToolTip("Avancer de 10s")
            self.back_btn.setText("‹  Retour à la galerie")
            self.back_btn.setVisible(True)
            self.badge_live.setText("VOD")
            self.badge_live.setStyleSheet("background-color: #6366f1; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
            self.timeline_row.setVisible(True)
            self.prev_btn.setVisible(False)
            self.next_btn.setVisible(False)
            self.auto_next_btn.setVisible(False)

        self._update_top_bar_elision()

    def _on_auto_next_clicked(self):
        is_active = self.auto_next_btn.isChecked()
        self._update_auto_next_appearance(is_active)
        self.auto_next_toggled.emit(is_active)

    def set_auto_next_state(self, enabled: bool):
        self.auto_next_btn.blockSignals(True)
        self.auto_next_btn.setChecked(enabled)
        self.auto_next_btn.blockSignals(False)
        self._update_auto_next_appearance(enabled)

    def _update_auto_next_appearance(self, enabled: bool):
        if enabled:
            self.auto_next_btn.setIcon(get_icon("autoplay", color=DEFAULT_ICON_COLOR))
            self.auto_next_btn.setToolTip("Lecture automatique de l'épisode suivant : Activée (cliquer pour bloquer)")
        else:
            self.auto_next_btn.setIcon(get_icon("autoplay", color="#526077"))
            self.auto_next_btn.setToolTip("Lecture automatique de l'épisode suivant : Bloquée (cliquer pour activer)")

    def set_playing_state(self, state: str):
        self.has_active_media = state in ("playing", "paused", "buffering", "error")
        self.is_playing = (state == "playing")
        self.is_paused = (state == "paused")
        self.is_error = (state == "error")

        if state == "error":
            self.error_banner.show()
            self.badge_live.setText("INDISPONIBLE")
            self.badge_live.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px; border: 1px solid #ef4444;")
            self.play_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
            self.play_btn.setToolTip("Flux indisponible")
        else:
            self.error_banner.hide()
            if self.current_channel:
                if self.current_channel.stream_type == "live":
                    self.badge_live.setText("DIRECT")
                    self.badge_live.setStyleSheet("background-color: #ef4444; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
                elif self.current_channel.stream_type == "series":
                    self.badge_live.setText("SÉRIE")
                    self.badge_live.setStyleSheet("background-color: #10b981; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
                elif self.current_channel.stream_type == "replay":
                    self.badge_live.setText("REPLAY")
                    self.badge_live.setStyleSheet("background-color: #818cf8; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
                elif self.current_channel.stream_type in ("movie", "vod"):
                    self.badge_live.setText("FILM")
                    self.badge_live.setStyleSheet("background-color: #6366f1; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
                else:
                    self.badge_live.setText("VOD")
                    self.badge_live.setStyleSheet("background-color: #6366f1; color: #fff; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;")
            if self.is_paused or not self.is_playing:
                self.play_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
                self.play_btn.setToolTip("Reprendre la lecture (Espace ou clic vidéo)")
            else:
                self.play_btn.setIcon(get_icon("pause", color="#ffffff"))
                self.play_btn.setToolTip("Mettre en pause (Espace ou clic vidéo)")

        self._update_top_bar_elision()

    def set_position(self, current_sec: float, total_sec: float):
        if self.current_channel and self.current_channel.stream_type == "live":
            self._update_live_epg_timeline()
            return

        self.total_duration = total_sec
        if total_sec > 0:
            self.timeline_row.setVisible(True)
            self.curr_time_label.setText(format_seconds(current_sec))
            self.total_time_label.setText(format_seconds(total_sec))
            if not self.timeline_slider.isSliderDown():
                val = int((current_sec / total_sec) * 1000)
                self.timeline_slider.setValue(val)
        else:
            self.timeline_row.setVisible(False)

    def set_volume_ui(self, vol: int):
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(vol)
        self.volume_slider.blockSignals(False)

    def set_mute_ui(self, muted: bool):
        self.is_muted = muted
        if muted:
            self.mute_btn.setIcon(get_icon("volume_off", color="#ef4444"))
        else:
            self.mute_btn.setIcon(get_icon("volume_up", color=DEFAULT_ICON_COLOR))

    def set_fullscreen_ui(self, is_fs: bool):
        self.is_fullscreen = is_fs
        if is_fs:
            self.fs_btn.setIcon(get_icon("fullscreen_exit", color=DEFAULT_ICON_COLOR))
        else:
            self.fs_btn.setIcon(get_icon("fullscreen", color=DEFAULT_ICON_COLOR))

    def set_tracks(self, tracks: List[Dict[str, Any]]):
        self.tracks = tracks

    # ------------------ ÉVÉNEMENTS ------------------

    def _on_slider_moved(self, value: int):
        if self.current_channel and self.current_channel.stream_type == "live":
            return
        if self.total_duration > 0:
            target = (value / 1000.0) * self.total_duration
            self.curr_time_label.setText(format_seconds(target))

    def _on_slider_released(self):
        if self.current_channel and self.current_channel.stream_type == "live":
            return
        if self.total_duration > 0:
            target = (self.timeline_slider.value() / 1000.0) * self.total_duration
            self.seek_requested.emit(target)

    def _show_ratio_menu(self):
        menu = QMenu(self)
        ratios = [("Auto", "-1"), ("16:9", "16:9"), ("4:3", "4:3"), ("21:9", "21:9"), ("1:1", "1:1")]
        for label, val in ratios:
            act = menu.addAction(label)
            act.triggered.connect(lambda checked, v=val: self.aspect_ratio_selected.emit(v))
        menu.exec(QCursor.pos())

    def _show_audio_menu(self):
        menu = QMenu(self)
        audio_tracks = [t for t in self.tracks if t.get("type") == "audio"]
        if not audio_tracks:
            act = menu.addAction("Piste par défaut")
            act.setCheckable(True)
            act.setChecked(True)
        else:
            for t in audio_tracks:
                tid = t.get("id", 1)
                lang = t.get("lang", "Inconnu")
                title = t.get("title", f"Piste {tid}")
                act = menu.addAction(f"{title} ({lang})")
                act.setCheckable(True)
                act.setChecked(bool(t.get("selected")))
                act.triggered.connect(lambda checked, track_id=tid: self.audio_track_selected.emit(track_id))
        menu.exec(QCursor.pos())

    def _show_subtitles_menu(self):
        menu = QMenu(self)
        sub_tracks = [t for t in self.tracks if t.get("type") == "sub"]
        selected_track = next((t for t in sub_tracks if t.get("selected")), None)

        act_none = menu.addAction("Désactiver les sous-titres")
        act_none.setCheckable(True)
        act_none.setChecked(selected_track is None)
        act_none.triggered.connect(lambda: self.subtitle_track_selected.emit(0))
        menu.addSeparator()

        for t in sub_tracks:
            tid = t.get("id", 1)
            lang = t.get("lang", "Inconnu")
            title = t.get("title", f"Sous-titre {tid}")
            act = menu.addAction(f"{title} ({lang})")
            act.setCheckable(True)
            act.setChecked(bool(t.get("selected")))
            act.triggered.connect(lambda checked, track_id=tid: self.subtitle_track_selected.emit(track_id))
        menu.exec(QCursor.pos())

    def is_mouse_on_bars(self, global_pos: Optional[QPoint] = None) -> bool:
        """Vérifie si le curseur de la souris se trouve au-dessus de l'une des barres de contrôle (inférieure ou supérieure)."""
        if not self.isVisible():
            return False
        if global_pos is None:
            global_pos = QCursor.pos()
        if hasattr(self, "bottom_bar") and self.bottom_bar.isVisible():
            bot_rect = QRect(self.bottom_bar.mapToGlobal(QPoint(0, 0)), self.bottom_bar.size())
            if bot_rect.contains(global_pos):
                return True
        if hasattr(self, "top_bar") and self.top_bar.isVisible():
            top_rect = QRect(self.top_bar.mapToGlobal(QPoint(0, 0)), self.top_bar.size())
            if top_rect.contains(global_pos):
                return True
        return False

