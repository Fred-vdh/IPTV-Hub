"""
Widget de gestion du mode Multiview (2, 3 ou 4 écrans simultanés) pour IPTV Hub.
Gère les grilles vidéo multiples, le focus audio interactif au clic,
et le passage fluide en plein écran total.
"""

from typing import Callable, List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QStackedWidget, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFontMetrics, QMouseEvent, QResizeEvent

from core.models import Channel, AppSettings
from core.database import Database
from core.player_controller import PlayerController
from core.i18n import tr
from ui.widgets.gl_video_surface import GLVideoSurface
from ui.dialogs.channel_picker_dialog import ChannelPickerDialog
from ui.icons import get_icon, get_pixmap


class MultiViewSlotWidget(QFrame):
    """
    Case individuelle d'affichage dans la grille Multiview.
    Contient son propre lecteur libmpv indépendant, sa surface OpenGL,
    et son bandeau OSD (nom de la chaîne, programme en cours, badge, boutons).
    """

    focused = pyqtSignal(int)               # slot_index
    channel_changed = pyqtSignal(int, Channel)
    slot_closed = pyqtSignal(int)
    fullscreen_requested = pyqtSignal()

    # Bandeau OSD : mêmes proportions que l'OSD du lecteur solo, mais toujours
    # visible (c'est lui qui porte les boutons « changer » et « supprimer »).
    BANNER_MARGIN = 8
    BANNER_HEIGHT = 44
    EPG_REFRESH_MS = 60000

    def __init__(
        self,
        slot_index: int,
        db: Database,
        settings: AppSettings,
        parent: Optional[QWidget] = None,
        epg_provider: Optional[Callable[[str], object]] = None
    ):
        super().__init__(parent)
        self.slot_index = slot_index
        self.db = db
        self.settings = settings
        self.channel: Optional[Channel] = None
        self.is_active_audio = False

        self.player: Optional[PlayerController] = None
        self.surface: Optional[GLVideoSurface] = None

        # Bandeau OSD : texte d'origine conservé pour recalculer l'élision à
        # chaque redimensionnement, et fournisseur EPG optionnel.
        self.epg_provider = epg_provider
        self._raw_channel_title = ""
        self._raw_epg_info = ""
        self._epg_timer: Optional[QTimer] = None

        self.setObjectName(f"mvSlot_{slot_index}")
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #0b0f17;
                border: 2px solid #1e293b;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        self.stack = QStackedWidget(self)

        # Page 0 : Placeholder vide avec bouton "+"
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap("live_tv", color="#334155", size=56))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon_lbl)

        self.add_btn = QPushButton("  " + tr("Ajouter une chaîne"))
        self.add_btn.setIcon(get_icon("add", color="#ffffff"))
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)
        self.add_btn.clicked.connect(self._open_channel_picker)
        empty_layout.addWidget(self.add_btn)

        self.stack.addWidget(self.empty_widget)

        # Page 1 : Lecteur vidéo actif + bandeau OSD (largeur de l'écran)
        self.video_container = QWidget()
        v_layout = QVBoxLayout(self.video_container)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)

        # Surface OpenGL MPV
        self.surface = GLVideoSurface(self.video_container)
        v_layout.addWidget(self.surface, stretch=1)

        # Bandeau OSD en superposition au-dessus de la vidéo
        self.top_bar = self._build_top_bar()

        self.stack.addWidget(self.video_container)
        layout.addWidget(self.stack)

        self.stack.setCurrentIndex(0)

    # ------------------------------------------------------------ bandeau OSD

    def _build_top_bar(self) -> QFrame:
        """Construit le bandeau OSD de l'écran (mêmes codes visuels que l'OSD solo).

        Contenu : icône audio, nom de la chaîne, programme en cours (EPG), badge
        « DIRECT » puis les deux boutons d'action (changer / supprimer la chaîne).
        Le bandeau est un widget superposé : il ne réduit pas la surface vidéo, et
        sa géométrie est recalculée à chaque redimensionnement pour ne jamais
        dépasser la largeur attribuée à la diffusion de la chaîne.
        """
        bar = QFrame(self.video_container)
        bar.setObjectName(f"mvTopBar_{self.slot_index}")
        bar.setStyleSheet("""
            QFrame {
                background-color: rgba(28, 36, 52, 0.95);
                border: 1px solid #3d4f72;
                border-radius: 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 6px;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.18);
            }
            QPushButton:pressed {
                background-color: rgba(56, 189, 248, 0.35);
            }
        """)
        bar.setFixedHeight(self.BANNER_HEIGHT)

        tb_layout = QHBoxLayout(bar)
        tb_layout.setContentsMargins(12, 6, 8, 6)
        tb_layout.setSpacing(10)

        # Indicateur sonore / audio
        self.audio_icon_lbl = QLabel()
        self.audio_icon_lbl.setPixmap(get_pixmap("volume_off", color="#64748b", size=18))
        self.audio_icon_lbl.setFixedWidth(22)
        tb_layout.addWidget(self.audio_icon_lbl)

        # Nom de la chaîne (toujours éventuellement tronqué, jamais élargi)
        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet("color: #ffffff; font-weight: 700; font-size: 15px;")
        self.title_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        tb_layout.addWidget(self.title_lbl)

        # Programme en cours (EPG) ou, à défaut, le groupe de la chaîne
        self.epg_info_lbl = QLabel()
        self.epg_info_lbl.setStyleSheet("color: #818cf8; font-weight: 500; font-size: 13px;")
        self.epg_info_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        tb_layout.addWidget(self.epg_info_lbl)

        tb_layout.addStretch(1)

        # Badge du type de flux (DIRECT / SÉRIE / …)
        self.badge_live = QLabel("DIRECT")
        self.badge_live.setStyleSheet(self._badge_style("#ef4444"))
        tb_layout.addWidget(self.badge_live)

        # Bouton changer la chaîne de cet écran
        self.change_btn = QPushButton()
        self.change_btn.setIcon(get_icon("edit", color="#cbd5e1"))
        self.change_btn.setIconSize(QSize(19, 19))
        self.change_btn.setFixedSize(30, 28)
        self.change_btn.setToolTip(tr("Changer la chaîne de cet écran"))
        self.change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.change_btn.clicked.connect(self._open_channel_picker)
        tb_layout.addWidget(self.change_btn)

        # Bouton supprimer la chaîne de cet écran (libère l'écran)
        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(get_icon("delete", color="#f87171"))
        self.delete_btn.setIconSize(QSize(19, 19))
        self.delete_btn.setFixedSize(30, 28)
        self.delete_btn.setToolTip(tr("Supprimer la chaîne de cet écran"))
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self.close_slot)
        tb_layout.addWidget(self.delete_btn)

        # Alias historique conservé pour la compatibilité (même bouton).
        self.close_btn = self.delete_btn

        bar.hide()
        return bar

    @staticmethod
    def _badge_style(color: str) -> str:
        return (
            f"background-color: {color}; color: #ffffff; font-size: 10px;"
            " font-weight: 700; padding: 3px 8px; border-radius: 4px;"
        )

    def _ensure_player_created(self):
        if self.player is None:
            self.player = PlayerController(
                render_mode=True,
                initial_volume=self.settings.volume,
                preferred_audio_lang=self.settings.preferred_audio_lang,
                preferred_subtitle_lang="off",
                subtitles_enabled=False,
                initial_hwdec=self.settings.hwdec,
                parent=self
            )
            if self.surface:
                self.surface.set_mpv_handle(self.player.mpv_handle)
            self.player.state_changed.connect(self._on_player_state_changed)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._sync_banner_geometry()

    def _sync_banner_geometry(self):
        """Positionne le bandeau en haut de l'écran, sans jamais dépasser sa largeur."""
        bar = getattr(self, "top_bar", None)
        if bar is None or not hasattr(self, "video_container"):
            return

        container = self.video_container
        total = container.width() or self.width()
        if total <= 1:
            return

        available = total - 2 * self.BANNER_MARGIN
        if available < 140:
            # Écran très étroit : le bandeau occupe toute la largeur disponible.
            x, bar_w = 0, total
        else:
            x, bar_w = self.BANNER_MARGIN, available

        bar.setGeometry(x, self.BANNER_MARGIN, bar_w, self.BANNER_HEIGHT)
        self._update_banner_elision()

    def _update_banner_elision(self):
        """Tronque titre et EPG pour que le bandeau tienne dans la largeur de l'écran.

        Même stratégie que l'OSD du lecteur solo : le titre est prioritaire et le
        programme en cours est masqué dès que la place manque.
        """
        bar = getattr(self, "top_bar", None)
        if bar is None or bar.width() <= 60:
            return

        layout = bar.layout()
        margins = layout.contentsMargins() if layout else None
        spacing = layout.spacing() if layout else 10
        left_right = (margins.left() + margins.right()) if margins else 20
        fixed_width = (
            left_right
            + 6 * spacing
            + self.audio_icon_lbl.width()
            + self.badge_live.sizeHint().width()
            + self.change_btn.width() + self.delete_btn.width()
        )
        available = max(30, bar.width() - fixed_width)

        fm_title = QFontMetrics(self.title_lbl.font())
        fm_epg = QFontMetrics(self.epg_info_lbl.font())
        title_raw = self._raw_channel_title or ""
        epg_raw = self._raw_epg_info or ""
        elide = Qt.TextElideMode.ElideRight

        # Aucun programme à afficher : le titre occupe toute la place disponible.
        if not epg_raw.strip() or available < 220:
            self.epg_info_lbl.hide()
            self.epg_info_lbl.setText("")
            self.title_lbl.setText(fm_title.elidedText(title_raw, elide, available))
            return

        title_w = fm_title.horizontalAdvance(title_raw)
        epg_w = fm_epg.horizontalAdvance(epg_raw)

        if title_w + spacing + epg_w <= available:
            self.title_lbl.setText(title_raw)
            self.epg_info_lbl.setText(epg_raw)
            self.epg_info_lbl.show()
            return

        # Partage de l'espace restant : 60 % pour la chaîne, 40 % pour le programme.
        space_for_both = max(20, available - spacing)
        title_alloc = int(space_for_both * 0.6)
        epg_alloc = space_for_both - title_alloc

        if epg_alloc < 90:
            self.epg_info_lbl.hide()
            self.epg_info_lbl.setText("")
            self.title_lbl.setText(fm_title.elidedText(title_raw, elide, available))
            return

        if title_w <= title_alloc:
            title_alloc = title_w
            epg_alloc = space_for_both - title_alloc
            self.title_lbl.setText(title_raw)
        else:
            self.title_lbl.setText(fm_title.elidedText(title_raw, elide, title_alloc))

        if epg_w <= epg_alloc:
            self.epg_info_lbl.setText(epg_raw)
        else:
            self.epg_info_lbl.setText(fm_epg.elidedText(epg_raw, elide, epg_alloc))
        self.epg_info_lbl.show()


    def _epg_text_for(self, channel: Channel) -> str:
        """Programme en cours (« — Titre ») ou, à défaut, le groupe de la chaîne."""
        title = ""
        provider = getattr(self, "epg_provider", None)
        if provider is not None and getattr(channel, "tvg_id", None):
            try:
                program = provider(channel.tvg_id)
                if program is not None:
                    title = getattr(program, "title", "") or ""
            except Exception as e:
                print(f"[MultiView] EPG indisponible (écran {self.slot_index}) : {e}")
        if not title:
            title = channel.group_title or ""
        return f"—  {title}" if title else ""

    def _update_banner_badge(self, stream_type: str):
        """Badge coloré du bandeau, identique à celui de l'OSD du lecteur solo."""
        styles = {
            "live": ("DIRECT", "#ef4444"),
            "series": ("SÉRIE", "#10b981"),
            "replay": ("REPLAY", "#818cf8"),
            "movie": ("FILM", "#6366f1"),
            "vod": ("FILM", "#6366f1"),
        }
        text, color = styles.get(stream_type, ("VOD", "#6366f1"))
        self.badge_live.setText(text)
        self.badge_live.setStyleSheet(self._badge_style(color))

    def _start_epg_timer(self):
        """Actualise régulièrement le programme en cours affiché dans le bandeau."""
        if self._epg_timer is None:
            self._epg_timer = QTimer(self)
            self._epg_timer.setInterval(self.EPG_REFRESH_MS)
            self._epg_timer.timeout.connect(self._refresh_epg)
        self._epg_timer.start()

    def _stop_epg_timer(self):
        if self._epg_timer is not None:
            self._epg_timer.stop()

    def _refresh_epg(self):
        if self.channel is None:
            self._stop_epg_timer()
            return
        self._raw_epg_info = self._epg_text_for(self.channel)
        self.epg_info_lbl.setToolTip(self._raw_epg_info)
        self._update_banner_elision()

    def _on_player_state_changed(self, state: str):
        if self.surface:
            if state in ("playing", "buffering"):
                self.surface.set_rendering_active(True)
            elif state in ("stopped", "error", "idle"):
                self.surface.set_rendering_active(False)

    def set_channel(self, channel: Optional[Channel], play_audio: bool = False):
        self.channel = channel
        if not channel:
            self.close_slot()
            return

        self._ensure_player_created()

        # Bandeau OSD : nom de la chaîne, programme en cours, badge, boutons.
        self._raw_channel_title = channel.name or ""
        self._raw_epg_info = self._epg_text_for(channel)
        self.title_lbl.setToolTip(self._raw_channel_title)
        self.epg_info_lbl.setToolTip(self._raw_epg_info)
        self._update_banner_badge(getattr(channel, "stream_type", "live"))

        self.stack.setCurrentIndex(1)
        self.top_bar.show()
        self.top_bar.raise_()
        self._sync_banner_geometry()
        self._start_epg_timer()

        # Lancement de la vidéo
        self.player.play(channel.stream_url)
        self.set_audio_active(play_audio)

    def set_audio_active(self, active: bool):
        self.is_active_audio = active
        if self.player:
            try:
                self.player.set_mute(not active)
            except Exception:
                pass

        # Un écran peut être partiellement construit (nettoyage de secours) :
        # les éléments d'interface sont donc optionnels ici.
        icon_lbl = getattr(self, "audio_icon_lbl", None)
        if icon_lbl is None:
            return

        if active:
            icon_lbl.setPixmap(get_pixmap("volume_up", color="#38bdf8", size=18))
            self.setStyleSheet("""
                QFrame#mvSlot_%d {
                    background-color: #0b0f17;
                    border: 2px solid #38bdf8;
                    border-radius: 8px;
                }
            """ % self.slot_index)
        else:
            icon_lbl.setPixmap(get_pixmap("volume_off", color="#64748b", size=18))
            self.setStyleSheet("""
                QFrame#mvSlot_%d {
                    background-color: #0b0f17;
                    border: 2px solid #1e293b;
                    border-radius: 8px;
                }
            """ % self.slot_index)

    def close_slot(self):
        """Ferme cet écran : arrêt de la lecture puis retour au placeholder vide."""
        if getattr(self, "player", None):
            try:
                self.player.stop()
            except Exception as e:
                print(f"[MultiView] erreur d'arrêt du flux (écran {self.slot_index}) : {e}")
        if getattr(self, "surface", None):
            try:
                self.surface.set_rendering_active(False)
            except Exception:
                pass
        self.reset_slot()
        try:
            self.slot_closed.emit(self.slot_index)
        except Exception:
            # Un écran partiellement construit (nettoyage de secours) ne peut pas
            # émettre de signal : l'arrêt doit rester inconditionnel.
            pass

    def reset_slot(self):
        """Remet l'écran à l'état vide (placeholder « + Ajouter une chaîne »).

        Purement visuel et très rapide (aucune opération libmpv bloquante) : c'est
        ce qui permet de quitter le Multiview ou de masquer un écran
        instantanément, la destruction des cœurs libmpv (potentiellement lente)
        étant effectuée séparément, après coup, par ``destroy_player()``.
        """
        self.channel = None
        self._raw_channel_title = ""
        self._raw_epg_info = ""
        try:
            self._stop_epg_timer()
        except Exception:
            pass
        try:
            self.title_lbl.clear()
        except Exception:
            pass
        try:
            self.epg_info_lbl.clear()
            self.epg_info_lbl.hide()
        except Exception:
            pass
        try:
            self.top_bar.hide()
        except Exception:
            pass
        try:
            self.set_audio_active(False)
        except Exception:
            pass
        try:
            self.stack.setCurrentIndex(0)
        except Exception:
            pass

    def suspend(self):
        """Arrête la lecture et libère le contexte de rendu OpenGL de libmpv.

        DOIT être appelé pendant que le widget est encore affiché : le contexte
        OpenGL de Qt doit être valide pour ``mpv_render_context_free()``. C'est
        l'étape RAPIDE ; la destruction du cœur libmpv (``destroy_player()``,
        potentiellement lente sur un flux réseau) peut être différée.
        """
        self.close_slot()
        if getattr(self, "surface", None):
            try:
                self.surface.cleanup_render_context()
            except Exception as e:
                print(f"[MultiView] erreur de libération du rendu (écran {self.slot_index}) : {e}")

    def destroy_player(self):
        """Détruit le cœur libmpv de cet écran (appel potentiellement lent)."""
        if getattr(self, "player", None):
            try:
                self.player.cleanup()
            except Exception as e:
                print(f"[MultiView] erreur de destruction du lecteur (écran {self.slot_index}) : {e}")
            self.player = None

    def _open_channel_picker(self):
        pl_id = self.channel.playlist_id if self.channel else None
        dlg = ChannelPickerDialog(self.db, playlist_id=pl_id, parent=self.window())
        if dlg.exec() and dlg.selected_channel:
            self.set_channel(dlg.selected_channel, play_audio=self.is_active_audio)
            self.channel_changed.emit(self.slot_index, dlg.selected_channel)

    def mousePressEvent(self, event: QMouseEvent):
        # Un clic n'importe où dans la case lui donne le focus audio
        self.focused.emit(self.slot_index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        # Double clic = bascule en plein écran
        self.fullscreen_requested.emit()
        super().mouseDoubleClickEvent(event)

    def cleanup(self):
        """Libère intégralement cet écran (contrat historique : synchrone).

        ORDRE CRITIQUE : libmpv impose de libérer le contexte de rendu
        (mpv_render_context_free) AVANT la destruction du coeur mpv
        (player.cleanup -> mpv_terminate_destroy) ; voir render.h :
        "You must free the context with mpv_render_context_free() before the
         mpv core is destroyed. If this doesn't happen, undefined behavior
         will result." Dans le cas contraire : access violation aléatoire.
        """
        self.suspend()
        self.destroy_player()


class MultiViewWidget(QWidget):
    """
    Conteneur global de la mosaïque Multiview.
    Gère la disposition (2, 3 ou 4 fenêtres), la barre de commandes flottante,
    et la synchronisation avec la fenêtre principale.
    """
    exit_requested = pyqtSignal(object)       # channel actif à reprendre en solo
    fullscreen_requested = pyqtSignal()

    # Délai entre la destruction de deux cœurs libmpv lors d'une libération
    # différée : la boucle d'événements dispose ainsi de créneaux pour rester
    # réactive (affichage, clics) entre deux opérations potentiellement lentes.
    TEARDOWN_STEP_MS = 80

    def __init__(
        self,
        db: Database,
        settings: AppSettings,
        parent: Optional[QWidget] = None,
        epg_provider: Optional[Callable[[str], object]] = None
    ):
        super().__init__(parent)
        self.db = db
        self.settings = settings
        # Fournisseur EPG (tvg_id -> programme en cours) utilisé par le bandeau
        # OSD de chaque écran, comme l'OSD du lecteur solo.
        self.epg_provider = epg_provider
        self.layout_mode = "1x2"              # "1x2", "1+2", "2x2"
        self.active_slot_idx = 0
        self.slots: List[MultiViewSlotWidget] = []
        # Vrai tant que le mode Multiview est affiché (au moins un écran secondaire).
        self.is_active = False
        # File d'attente de libération DIFFÉRÉE des cœurs libmpv : chaque écran est
        # détruit un par un par le thread GUI, jamais dans le gestionnaire de clic
        # lui-même (voir _post_teardown/_teardown_next). Cela évite que
        # mpv_terminate_destroy(), parfois lent sur un flux réseau en cours de
        # connexion, ne fige l'interface (bouton « Quitter Multiview » sans réaction).
        self._teardown_queue: List[int] = []
        self._teardown_running = False
        self._exiting = False

        self.setObjectName("multiViewWidget")
        self.setStyleSheet("background-color: #090d14;")
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 10)
        main_layout.setSpacing(8)

        # 1. Barre supérieure de commandes Multiview
        self.toolbar = QFrame(self)
        self.toolbar.setFixedHeight(44)
        self.toolbar.setStyleSheet("""
            QFrame {
                background-color: #131b2a;
                border: 1px solid #202d44;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #293548;
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)

        tb_layout = QHBoxLayout(self.toolbar)
        tb_layout.setContentsMargins(12, 0, 12, 0)
        tb_layout.setSpacing(10)

        # Titre / Badge Multiview
        title_box = QHBoxLayout()
        title_box.setSpacing(8)
        mv_icon = QLabel()
        mv_icon.setPixmap(get_pixmap("dashboard", color="#38bdf8", size=20))
        title_box.addWidget(mv_icon)

        title_lbl = QLabel(tr("Mode Multiview"))
        title_lbl.setStyleSheet("color: #f8fafc; font-weight: 700; font-size: 14px;")
        title_box.addWidget(title_lbl)
        tb_layout.addLayout(title_box)

        tb_layout.addStretch()

        # Sélecteur de grille : 2 écrans (1x2)
        self.btn_1x2 = QPushButton(tr("2 Écrans (1x2)"))
        self.btn_1x2.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_1x2.clicked.connect(lambda: self.set_layout_mode("1x2"))
        tb_layout.addWidget(self.btn_1x2)

        # Sélecteur de grille : 3 écrans (1+2)
        self.btn_1p2 = QPushButton(tr("3 Écrans (1+2)"))
        self.btn_1p2.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_1p2.clicked.connect(lambda: self.set_layout_mode("1+2"))
        tb_layout.addWidget(self.btn_1p2)

        # Sélecteur de grille : 4 écrans (2x2)
        self.btn_2x2 = QPushButton(tr("4 Écrans (2x2)"))
        self.btn_2x2.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_2x2.clicked.connect(lambda: self.set_layout_mode("2x2"))
        tb_layout.addWidget(self.btn_2x2)

        # Bouton Plein écran (F)
        self.fs_btn = QPushButton("  " + tr("Plein écran"))
        self.fs_btn.setIcon(get_icon("fullscreen", color="#ffffff"))
        self.fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fs_btn.clicked.connect(self.fullscreen_requested.emit)
        tb_layout.addWidget(self.fs_btn)

        # Bouton Quitter le Multiview
        self.exit_btn = QPushButton("  " + tr("Quitter Multiview"))
        self.exit_btn.setIcon(get_icon("close", color="#f87171"))
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
            }
        """)
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.clicked.connect(self._on_exit_clicked)
        tb_layout.addWidget(self.exit_btn)

        main_layout.addWidget(self.toolbar)

        # 2. Grille centrale des slots vidéo
        self.grid_container = QWidget(self)
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(6)
        main_layout.addWidget(self.grid_container, stretch=1)

        # Création des 4 slots
        for i in range(4):
            slot = MultiViewSlotWidget(
                i, self.db, self.settings, parent=self, epg_provider=self.epg_provider
            )
            slot.focused.connect(self._on_slot_focused)
            slot.fullscreen_requested.connect(self.fullscreen_requested.emit)
            self.slots.append(slot)

        self._rebuild_grid()

    def _rebuild_grid(self):
        # Vider la grille sans détruire les slots
        while self.grid_layout.count() > 0:
            self.grid_layout.takeAt(0)

        # Mettre à jour les boutons actifs
        active_style = "background-color: #0284c7; color: #ffffff; border-color: #38bdf8;"
        normal_style = "background-color: #1e293b; color: #e2e8f0; border-color: #334155;"

        self.btn_1x2.setStyleSheet(active_style if self.layout_mode == "1x2" else normal_style)
        self.btn_1p2.setStyleSheet(active_style if self.layout_mode == "1+2" else normal_style)
        self.btn_2x2.setStyleSheet(active_style if self.layout_mode == "2x2" else normal_style)

        # Écrans devenus masqués par la nouvelle disposition : ils sont arrêtés
        # MAINTENANT (le contexte de rendu OpenGL de libmpv doit être libéré pendant
        # que le widget est encore affiché) alors que la destruction de leur cœur
        # libmpv est différée : un changement de disposition ne doit jamais figer
        # l'interface, même si un flux réseau se libère lentement.
        if self.layout_mode == "1x2":
            self._close_hidden_slots((2, 3))
        elif self.layout_mode == "1+2":
            self._close_hidden_slots((3,))

        if self.layout_mode == "1x2":
            # 2 écrans horizontaux (Slot 0 et Slot 1)
            self.grid_layout.addWidget(self.slots[0], 0, 0)
            self.grid_layout.addWidget(self.slots[1], 0, 1)
            self.slots[0].show()
            self.slots[1].show()
            self.slots[2].hide()
            self.slots[3].hide()

        elif self.layout_mode == "1+2":
            # 1 grand écran à gauche (Slot 0), 2 à droite (Slot 1 et Slot 2)
            self.grid_layout.addWidget(self.slots[0], 0, 0, 2, 1)
            self.grid_layout.addWidget(self.slots[1], 0, 1)
            self.grid_layout.addWidget(self.slots[2], 1, 1)
            self.slots[0].show()
            self.slots[1].show()
            self.slots[2].show()
            self.slots[3].hide()

        elif self.layout_mode == "2x2":
            # Grille 4 écrans
            self.grid_layout.addWidget(self.slots[0], 0, 0)
            self.grid_layout.addWidget(self.slots[1], 0, 1)
            self.grid_layout.addWidget(self.slots[2], 1, 0)
            self.grid_layout.addWidget(self.slots[3], 1, 1)
            for s in self.slots:
                s.show()

    def set_layout_mode(self, mode: str):
        if mode not in ("1x2", "1+2", "2x2"):
            mode = "1x2"
        self.layout_mode = mode
        self._rebuild_grid()

    def start_multiview(self, primary_channel: Optional[Channel]):
        """Initialise le mode Multiview avec la chaîne principale dans le premier écran."""
        # Aucun écran résiduel d'une session précédente ne doit subsister.
        for i in range(1, len(self.slots)):
            if self.slots[i].channel is not None or self.slots[i].player is not None:
                try:
                    self.slots[i].close_slot()
                except Exception as e:
                    print(f"[MultiView] erreur de réinitialisation de l'écran {i} : {e}")

        self.active_slot_idx = 0
        self.is_active = True

        if primary_channel:
            self.slots[0].set_channel(primary_channel, play_audio=True)
        else:
            self.slots[0].set_audio_active(True)

        for i in range(1, 4):
            self.slots[i].set_audio_active(False)

        # La disposition mémorisée (2, 3 ou 4 écrans) est conservée : après un
        # aller-retour, l'utilisateur retrouve l'écran de travail qu'il avait choisi.
        self.set_layout_mode(self.layout_mode)

    def _on_slot_focused(self, slot_idx: int):
        self.active_slot_idx = slot_idx
        for i, slot in enumerate(self.slots):
            slot.set_audio_active(i == slot_idx)

    def _on_exit_clicked(self):
        """Quitte le mode Multiview : l'interface réagit TOUJOURS immédiatement.

        L'ordre est essentiel : on signale d'abord la sortie (le lecteur solo
        reprend la chaîne aussitôt), puis on libère les écrans secondaires. Rien
        de lent (destruction d'un cœur libmpv sur un flux réseau) n'est exécuté
        dans le gestionnaire de clic : c'est ce qui évite le bouton « sans
        réaction » / interface figée constaté après des erreurs de flux.
        """
        if self._exiting:
            return
        self._exiting = True
        try:
            active_channel = self.active_channel()
            # 1. Sortie immédiate : le lecteur solo reprend la main tout de suite.
            self.exit_requested.emit(active_channel)
            # 2. Désactivation complète des écrans secondaires (libmpv différé).
            self.deactivate(staggered=True)
        except Exception as e:
            print(f"[MultiView] erreur à la sortie du mode Multiview : {e}")
        finally:
            self._exiting = False

    def active_channel(self) -> Optional[Channel]:
        """Chaîne à reprendre en solo : écran au focus audio, sinon premier occupé."""
        try:
            start = self.active_slot_idx if 0 <= self.active_slot_idx < len(self.slots) else 0
        except Exception:
            start = 0
        for idx in (start, 0, 1, 2, 3):
            if 0 <= idx < len(self.slots) and self.slots[idx].channel is not None:
                return self.slots[idx].channel
        return None

    def has_running_slots(self) -> bool:
        """Vrai si au moins un écran possède encore un lecteur ou une chaîne."""
        return any(
            getattr(slot, "player", None) is not None or getattr(slot, "channel", None) is not None
            for slot in self.slots
        )

    def deactivate(self, staggered: bool = True):
        """Désactive TOUS les écrans du Multiview : il ne reste que l'écran de base.

        Idempotent. ``staggered=True`` (utilisé par l'interface) libère les cœurs
        libmpv un écran à la fois via la boucle d'événements : le thread GUI n'est
        jamais bloqué, même si un flux réseau tarde à se libérer.
        ``staggered=False`` effectue tout de façon synchrone (fermeture de
        l'application, tests unitaires).
        """
        self.is_active = False
        # 1. Arrêt immédiat de la lecture et libération du contexte de rendu,
        #    pendant que les widgets sont encore affichés (contrainte libmpv).
        for slot in self.slots:
            try:
                slot.suspend()
            except Exception as e:
                print(f"[MultiView] erreur de réinitialisation d'un écran : {e}")
        self.active_slot_idx = 0
        # 2. Destruction des cœurs libmpv (partie lente)
        if staggered:
            pending = [i for i, s in enumerate(self.slots) if getattr(s, "player", None) is not None]
            self._post_teardown(pending)
        else:
            self.stop_all()

    def _close_hidden_slots(self, indices):
        """Ferme les écrans masqués par un changement de disposition.

        L'arrêt du flux est immédiat (rapide, contexte OpenGL encore valide) et la
        destruction du cœur libmpv est différée : un clic sur « 2/3/4 écrans »
        reste instantané en toutes circonstances.
        """
        pending: List[int] = []
        for idx in indices:
            if not (0 <= idx < len(self.slots)):
                continue
            slot = self.slots[idx]
            if getattr(slot, "player", None) is not None or getattr(slot, "channel", None) is not None:
                try:
                    slot.suspend()
                except Exception as e:
                    print(f"[MultiView] erreur de fermeture de l'écran {idx} : {e}")
                if getattr(slot, "player", None) is not None:
                    pending.append(idx)
        self._post_teardown(pending)

    def _post_teardown(self, indices) -> None:
        """Met en file la destruction différée des cœurs libmpv de ces écrans."""
        for idx in indices:
            if idx not in self._teardown_queue:
                self._teardown_queue.append(idx)
        if self._teardown_queue and not self._teardown_running:
            self._teardown_running = True
            QTimer.singleShot(0, self._teardown_next)

    def _teardown_next(self) -> None:
        """Détruit le cœur libmpv d'un écran, puis programme le suivant."""
        if not self._teardown_queue:
            self._teardown_running = False
            return
        idx = self._teardown_queue.pop(0)
        try:
            if 0 <= idx < len(self.slots):
                self.slots[idx].destroy_player()
        except Exception as e:
            print(f"[MultiView] erreur de destruction de l'écran {idx} : {e}")
        if self._teardown_queue:
            QTimer.singleShot(self.TEARDOWN_STEP_MS, self._teardown_next)
        else:
            self._teardown_running = False

    def stop_all(self):
        """Arrête tous les flux et libère les ressources (appel SYNCHRONE)."""
        self._teardown_queue = []
        self._teardown_running = False
        for slot in self.slots:
            try:
                slot.cleanup()
            except Exception as e:
                print(f"[MultiView] erreur d'arrêt d'un écran : {e}")

    def set_fullscreen_ui(self, is_fs: bool):
        if is_fs:
            self.fs_btn.setText("  " + tr("Quitter plein écran"))
            self.fs_btn.setIcon(get_icon("fullscreen_exit", color="#ffffff"))
        else:
            self.fs_btn.setText("  " + tr("Plein écran"))
            self.fs_btn.setIcon(get_icon("fullscreen", color="#ffffff"))
