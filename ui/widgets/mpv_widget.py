"""
Widget d'affichage vidéo encapsulant libmpv avec overlay OSD escamotable moderne et réactif.
Gère le plein écran au double-clic et la pause/reprise au simple clic (en lecture comme en pause).
"""

from typing import Optional
import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QStackedWidget, QScrollArea
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QEvent, QPoint, QRect
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QWheelEvent, QCursor

from core.player_controller import PlayerController
from ui.widgets.player_controls import PlayerControls
from ui.widgets.gl_video_surface import GLVideoSurface
from ui.icons import get_pixmap


class MPVVideoWidget(QWidget):
    fullscreen_requested = pyqtSignal()
    play_pause_requested = pyqtSignal()

    def __init__(self, player_controller: Optional[PlayerController] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("videoContainer")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #0f131d;")

        self.player: Optional[PlayerController] = player_controller

        # 1. Stack central isolant le placeholder Qt pur de la surface vidéo libmpv
        self.stack = QStackedWidget(self)
        self.stack.setStyleSheet("background-color: #0f131d;")

        # Page 0 : Placeholder central d'attente (pur Qt, garanti visible)
        self.placeholder = QWidget()
        self.placeholder.setObjectName("videoPlaceholder")
        self.placeholder.setStyleSheet("background-color: #0f131d;")
        p_layout = QVBoxLayout(self.placeholder)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_layout.setSpacing(14)

        p_icon = QLabel()
        p_icon.setPixmap(get_pixmap("live_tv", color="#3b82f6", size=72))
        p_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_layout.addWidget(p_icon)

        p_title = QLabel("Aucune chaîne en cours de lecture")
        p_title.setStyleSheet("color: #f1f5f9; font-size: 16px; font-weight: 600;")
        p_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_layout.addWidget(p_title)

        p_text = QLabel("Veuillez sélectionner une chaîne dans la liste de gauche pour démarrer la diffusion")
        p_text.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 400;")
        p_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_layout.addWidget(p_text)

        self.stack.addWidget(self.placeholder)

        # Page 1 : Surface vidéo OpenGL (rendu libmpv via mpv_render_context).
        # L'OSD (contrôles) est un widget enfant ordinaire qui s'affiche par-dessus.
        self.video_surface = GLVideoSurface(self)
        self.video_surface.setStyleSheet("background-color: #000000;")
        self.stack.addWidget(self.video_surface)

        # Layout principal de MPVVideoWidget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stack)

        self.stack.setCurrentIndex(0)

        # 2. Overlay OSD des contrôles — widget enfant ordinaire, positionné par-dessus stack
        self.controls = PlayerControls(self)
        self.controls.setMouseTracking(True)
        self.controls.hide()

        # 3. Timer pour masquer l'OSD après 3.5 secondes d'inactivité
        self.osd_timer = QTimer(self)
        self.osd_timer.setInterval(3500)
        self.osd_timer.setSingleShot(True)
        self.osd_timer.timeout.connect(self._hide_osd)

        # Timer pour différencier le simple clic (pause/play) du double-clic (plein écran)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._handle_single_click)
        self._ignore_next_release = False
        self._last_dblclick_time: float = 0.0

        self._last_mouse_pos: Optional[QPoint] = None
        self._osd_suspended: bool = False
        self._was_mouse_on_controls: bool = False
        self._install_controls_event_filters()
        self.video_surface.installEventFilter(self)
        self.installEventFilter(self)

        if self.player:
            self._connect_player()

    def _install_controls_event_filters(self):
        """Installe le filtre d'événements sur la fenêtre de contrôle et tous ses sous-widgets."""
        if not hasattr(self, "controls") or not self.controls:
            return
        self.controls.installEventFilter(self)
        for w in self.controls.findChildren(QWidget):
            w.setMouseTracking(True)
            w.installEventFilter(self)

    def set_player(self, player: PlayerController):
        self.player = player
        self._connect_player()
        # Branchement de la surface OpenGL sur le handle brut de libmpv.
        if self.player is not None:
            handle = self.player.mpv_handle
            if handle:
                self.video_surface.set_mpv_handle(handle)
            self.controls.set_volume_ui(self.player._initial_volume)

    def _connect_player(self):
        if not self.player:
            return
        # Connexion des signaux du PlayerController vers l'UI
        self.player.state_changed.connect(self._on_player_state_changed)
        self.player.time_changed.connect(lambda t: self.controls.set_position(t, self.controls.total_duration))
        self.player.duration_changed.connect(lambda d: self.controls.set_position(0, d))
        self.player.volume_changed.connect(self.controls.set_volume_ui)
        self.player.mute_changed.connect(self.controls.set_mute_ui)
        self.player.tracks_changed.connect(self.controls.set_tracks)

        # Connexion des contrôles OSD vers le PlayerController
        self.controls.play_pause_clicked.connect(self._trigger_play_pause)
        self.controls.seek_requested.connect(lambda pos: self.player.seek(pos, relative=False))
        self.controls.volume_changed.connect(self.player.set_volume)
        self.controls.mute_toggled.connect(self.player.toggle_mute)
        self.controls.aspect_ratio_selected.connect(self.player.set_aspect_ratio)
        self.controls.audio_track_selected.connect(self.player.set_audio_track)
        self.controls.subtitle_track_selected.connect(self.player.set_subtitle_track)
        self.controls.fullscreen_toggled.connect(self.fullscreen_requested.emit)

    def showEvent(self, event):
        super().showEvent(event)
        if self.player:
            handle = self.player.mpv_handle
            if handle:
                self.video_surface.set_mpv_handle(handle)
        self._sync_geometry()
        if self.controls.has_active_media:
            self.stack.setCurrentIndex(1)
            self._show_osd()
        else:
            self.stack.setCurrentIndex(0)
            self.controls.hide()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.controls.hide()
        self.osd_timer.stop()

    def closeEvent(self, event):
        if hasattr(self, "controls") and self.controls:
            self.controls.hide_bars()
            self.controls.hide()
        if hasattr(self, "osd_timer"):
            self.osd_timer.stop()
        if hasattr(self, "video_surface") and self.video_surface:
            try:
                self.video_surface.cleanup_render_context()
            except Exception:
                pass
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._last_mouse_pos = QCursor.pos()
        self._sync_geometry()

    def _find_scroll_area(self) -> Optional[QScrollArea]:
        p = self.parentWidget()
        while p:
            if isinstance(p, QScrollArea):
                return p
            p = p.parentWidget()
        return None

    def _sync_geometry(self):
        """Positionne l'OSD (widget enfant) sur toute la zone vidéo.

        Depuis la migration OpenGL, l'OSD n'est plus une fenêtre native séparée :
        on le dimensionne simplement sur la totalité du widget vidéo (coordonnées
        relatives au parent) et on le remonte au-dessus de la surface vidéo.
        """
        self._last_mouse_pos = QCursor.pos()
        if not hasattr(self, "controls") or not self.controls:
            return
        if self.isVisible() and self.controls.has_active_media:
            self.controls.setGeometry(0, 0, self.width(), self.height())
            if self.controls.isVisible():
                self.controls.raise_()
        else:
            self.controls.hide()

    def _is_click_on_controls_bar(self, global_pos: QPoint) -> bool:
        """Vérifie si la position globale se trouve sur l'une des barres interactives de l'OSD."""
        return self._is_mouse_on_controls_bar(global_pos)

    def _is_mouse_on_controls_bar(self, global_pos: Optional[QPoint] = None) -> bool:
        """Vérifie si le curseur de la souris se trouve actuellement au-dessus d'une barre de l'OSD."""
        if not hasattr(self, "controls") or not self.controls or not self.controls.isVisible():
            return False
        if hasattr(self.controls, "is_mouse_on_bars"):
            return self.controls.is_mouse_on_bars(global_pos)
        if global_pos is None:
            global_pos = QCursor.pos()
        if hasattr(self.controls, "bottom_bar") and self.controls.bottom_bar.isVisible():
            bot_rect = QRect(self.controls.bottom_bar.mapToGlobal(QPoint(0, 0)), self.controls.bottom_bar.size())
            if bot_rect.contains(global_pos):
                return True
        if hasattr(self.controls, "top_bar") and self.controls.top_bar.isVisible():
            top_rect = QRect(self.controls.top_bar.mapToGlobal(QPoint(0, 0)), self.controls.top_bar.size())
            if top_rect.contains(global_pos):
                return True
        return False

    def _handle_single_click(self):
        """Action exécutée uniquement lorsqu'un vrai simple clic est confirmé (pas de double clic)."""
        if self.controls.has_active_media:
            self._trigger_play_pause()

    def _trigger_play_pause(self):
        """Déclenche la pause/reprise via play_pause_requested ou directement sur le player."""
        if self.receivers(self.play_pause_requested) > 0:
            self.play_pause_requested.emit()
        elif self.player:
            self.player.toggle_pause()

    def _handle_wheel_volume(self, event: QWheelEvent) -> bool:
        """Ajuste le volume sonore lors du défilement de la molette au-dessus de la zone vidéo."""
        if not self.controls.has_active_media:
            return False
        delta = event.angleDelta().y()
        if delta != 0:
            step = 5 if delta > 0 else -5
            cur_vol = self.controls.volume_slider.value()
            new_vol = max(0, min(100, cur_vol + step))
            if new_vol != cur_vol:
                self.controls.volume_slider.setValue(new_vol)
                if self.player:
                    self.player.set_volume(new_vol)
            self._show_osd()
            return True
        return False

    def wheelEvent(self, event: QWheelEvent):
        if self._handle_wheel_volume(event):
            event.accept()
            return
        super().wheelEvent(event)

    def eventFilter(self, watched, event: QEvent) -> bool:
        event_type = event.type()
        if event_type in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
            if isinstance(event, QMouseEvent):
                global_pos = event.globalPosition().toPoint()
            else:
                global_pos = QCursor.pos()

            # Vérifier si la souris est positionnée sur la barre de contrôle de l'OSD
            if self._is_mouse_on_controls_bar(global_pos):
                self.osd_timer.stop()
                self._was_mouse_on_controls = True
                self.show_mouse_cursor()
                if not self.controls.isVisible() and self.controls.has_active_media:
                    self._show_osd()
            else:
                if getattr(self, "_was_mouse_on_controls", False):
                    # Transition : la souris vient de sortir de la zone de la barre de contrôle
                    self._was_mouse_on_controls = False
                    self._last_mouse_pos = global_pos
                    if self.controls.has_active_media and not getattr(self.controls, "is_paused", False) and not getattr(self.controls, "is_error", False):
                        self.osd_timer.start()
                else:
                    if self._last_mouse_pos is not None:
                        if (global_pos - self._last_mouse_pos).manhattanLength() < 4:
                            return False
                    self._last_mouse_pos = global_pos
                    if self.controls.has_active_media:
                        self._show_osd()

        elif event_type == QEvent.Type.Leave:
            if getattr(self, "_was_mouse_on_controls", False) and not self._is_mouse_on_controls_bar():
                self._was_mouse_on_controls = False
                if self.controls.has_active_media and not getattr(self.controls, "is_paused", False) and not getattr(self.controls, "is_error", False):
                    self.osd_timer.start()

        elif event_type == QEvent.Type.Enter:
            if self._is_mouse_on_controls_bar():
                self.osd_timer.stop()
                self._was_mouse_on_controls = True
                self.show_mouse_cursor()

        elif event_type == QEvent.Type.MouseButtonDblClick:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
                global_pos = event.globalPosition().toPoint()
                self._last_mouse_pos = global_pos
                if not self._is_click_on_controls_bar(global_pos) and self.controls.has_active_media:
                    self._click_timer.stop()
                    self._last_dblclick_time = time.monotonic()
                    self._ignore_next_release = False
                    self.fullscreen_requested.emit()
                    return True

        elif event_type == QEvent.Type.MouseButtonRelease:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
                global_pos = event.globalPosition().toPoint()
                self._last_mouse_pos = global_pos
                if not self._is_click_on_controls_bar(global_pos) and self.controls.has_active_media:
                    # Si un double-clic vient de se produire (< 350ms), ignorer le release résiduel
                    if time.monotonic() - getattr(self, "_last_dblclick_time", 0.0) < 0.35:
                        return True
                    if self._ignore_next_release:
                        self._ignore_next_release = False
                        return True
                    self._click_timer.stop()
                    # Intervalle réactif (220ms) pour une pause/reprise rapide sans latence
                    self._click_timer.start(220)
                    return True

        elif event_type == QEvent.Type.MouseButtonPress:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
                global_pos = event.globalPosition().toPoint()
                self._last_mouse_pos = global_pos
                if not self._is_click_on_controls_bar(global_pos) and self.controls.has_active_media:
                    self.setFocus()
                    win = self.window()
                    if win and not win.isActiveWindow():
                        win.activateWindow()

        elif event_type == QEvent.Type.Wheel:
            if isinstance(event, QWheelEvent) and self._handle_wheel_volume(event):
                return True

        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event: QMouseEvent):
        global_pos = event.globalPosition().toPoint()
        if self._is_mouse_on_controls_bar(global_pos):
            self.osd_timer.stop()
            self._was_mouse_on_controls = True
        else:
            if getattr(self, "_was_mouse_on_controls", False):
                self._was_mouse_on_controls = False
                if self.controls.has_active_media and not getattr(self.controls, "is_paused", False) and not getattr(self.controls, "is_error", False):
                    self.osd_timer.start()
            else:
                if self._last_mouse_pos is not None:
                    if (global_pos - self._last_mouse_pos).manhattanLength() < 4:
                        return
                self._last_mouse_pos = global_pos
                if self.controls.has_active_media:
                    self._show_osd()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if not self.player:
            return
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.player.toggle_pause()
            if self.controls.has_active_media:
                self._show_osd()
        elif key in (Qt.Key.Key_F, Qt.Key.Key_F11):
            self.fullscreen_requested.emit()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            delta = -10 if key == Qt.Key.Key_Left else 10
            self.player.seek(delta, relative=True)
            if self.controls.has_active_media:
                self._show_osd()
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            delta = 5 if key == Qt.Key.Key_Up else -5
            cur_vol = self.controls.volume_slider.value()
            new_vol = max(0, min(100, cur_vol + delta))
            self.controls.volume_slider.setValue(new_vol)
            self.player.set_volume(new_vol)
            if self.controls.has_active_media:
                self._show_osd()
        elif key == Qt.Key.Key_M:
            self.player.toggle_mute()
            if self.controls.has_active_media:
                self._show_osd()
        elif key == Qt.Key.Key_Escape and self.window().isFullScreen():
            self.fullscreen_requested.emit()
        else:
            super().keyPressEvent(event)

    def _on_player_state_changed(self, state: str):
        if state in ("playing", "buffering", "paused"):
            self.stack.setCurrentIndex(1)
            self.video_surface.set_rendering_active(True)
            self.controls.set_playing_state(state)
            if self.controls.isVisible():
                self._show_osd()
            elif state == "playing" and (self.window().isFullScreen() or getattr(self.controls, "is_fullscreen", False)):
                self.hide_mouse_cursor()
        elif state == "error":
            self.stack.setCurrentIndex(1)
            self.video_surface.set_rendering_active(False)
            self.controls.set_playing_state("error")
            self._show_osd()
            self.osd_timer.stop()
            self.show_mouse_cursor()
        else:
            self.stack.setCurrentIndex(0)
            self.video_surface.set_rendering_active(False)
            self.controls.set_playing_state("stopped")
            self.controls.hide()
            self.show_mouse_cursor()
            self.osd_timer.stop()

    def hide_mouse_cursor(self):
        """Masque le curseur de la souris sur le widget vidéo, la surface native et les contrôles."""
        self.setCursor(Qt.CursorShape.BlankCursor)
        if hasattr(self, "video_surface") and self.video_surface:
            self.video_surface.setCursor(Qt.CursorShape.BlankCursor)
        if hasattr(self, "controls") and self.controls:
            self.controls.setCursor(Qt.CursorShape.BlankCursor)

    def show_mouse_cursor(self):
        """Rétablit le curseur standard de la souris."""
        self.unsetCursor()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if hasattr(self, "video_surface") and self.video_surface:
            self.video_surface.unsetCursor()
            self.video_surface.setCursor(Qt.CursorShape.ArrowCursor)
        if hasattr(self, "controls") and self.controls:
            self.controls.unsetCursor()
            self.controls.setCursor(Qt.CursorShape.ArrowCursor)

    def set_fullscreen(self, is_fs: bool):
        """Met à jour l'UI plein écran et masque automatiquement le curseur si un média est en cours de lecture."""
        self.controls.set_fullscreen_ui(is_fs)
        if is_fs:
            if self.controls.has_active_media and not getattr(self.controls, "is_paused", False):
                self.hide_mouse_cursor()
        else:
            self.show_mouse_cursor()

    def _show_osd(self):
        if getattr(self, "_osd_suspended", False):
            return
        if not self.player or not self.controls.has_active_media:
            self.controls.hide()
            return

        self._sync_geometry()
        self.controls.show()
        self.controls.show_bars()
        self.controls.raise_()
        self.show_mouse_cursor()

        if self._is_mouse_on_controls_bar():
            self.osd_timer.stop()
            self._was_mouse_on_controls = True
        elif not getattr(self.controls, "is_paused", False) and not getattr(self.controls, "is_error", False):
            self.osd_timer.start()
        else:
            self.osd_timer.stop()

    def _hide_osd(self):
        """Masque complètement l'OSD après timeout d'inactivité."""
        if getattr(self.controls, "is_paused", False) or getattr(self.controls, "is_error", False):
            return

        # Ne jamais masquer si la souris se trouve sur la barre de contrôle
        if self._is_mouse_on_controls_bar():
            self.osd_timer.stop()
            self._was_mouse_on_controls = True
            return

        if self.controls.has_active_media:
            self.controls.hide()
            self.hide_mouse_cursor()

