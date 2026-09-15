"""
Fenêtre principale du lecteur IPTV moderne sans bordure (Frameless) avec barre de titre
personnalisée intégrée, thème gris foncé bleuté, et panneau des paramètres intégré in-place.
"""

import time
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStackedWidget, QMessageBox, QApplication, QSizeGrip, QPushButton,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut, QCursor

from core.models import Channel, WatchHistory, Playlist
from core.database import Database
from core.player_controller import PlayerController

from ui.widgets.custom_titlebar import CustomTitleBar
from ui.widgets.sidebar import Sidebar
from ui.widgets.categories_panel import CategoriesPanel
from ui.widgets.channel_list import ChannelListPanel
from ui.widgets.mpv_widget import MPVVideoWidget
from ui.widgets.settings_view import SettingsView
from ui.widgets.epg_view import EPGDialog
from ui.widgets.epg_timeline import EPGTimelinePanel
from ui.dialogs.add_playlist import AddPlaylistDialog, PlaylistImportWorker
from ui.dialogs.manage_playlists_dialog import ManagePlaylistsDialog
from ui.widgets.vod_grid import VODGridView
from ui.widgets.series_details_view import SeriesDetailsView
from ui.widgets.movie_details_view import MovieDetailsView
from ui.widgets.favorites_view import FavoritesView
from ui.widgets.recently_watched_view import RecentlyWatchedView
from ui.widgets.recently_added_view import RecentlyAddedView
from ui.widgets.dashboard_view import DashboardView
from ui.widgets.epg_grid_view import EPGGridView
from ui.widgets.replay_view import ReplayView
from ui.icons import get_app_logo_icon, get_icon
from core.i18n import tr, I18nManager


class MainWindow(QMainWindow):
    def _get_safe_normal_geometry(self) -> tuple[int, int, int, int]:
        """Calcule une géométrie de fenêtre normale (fenêtrée / réduite) saine et utilisable."""
        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        w = self.settings.window_width
        h = self.settings.window_height

        # Dimensions réduites par défaut (82% de l'écran, minimum 980x600)
        default_w = max(980, min(int(avail.width() * 0.82), avail.width() - 80))
        default_h = max(600, min(int(avail.height() * 0.82), avail.height() - 80))
        default_x = avail.x() + max(0, (avail.width() - default_w) // 2)
        default_y = avail.y() + max(0, (avail.height() - default_h) // 2)

        # Si dimensions non initialisées, trop petites ou occupant tout l'écran (les deux dimensions en même temps)
        is_fully_max = (w >= avail.width() - 15 and h >= avail.height() - 15)
        if w < 980 or h < 600 or is_fully_max:
            return (default_x, default_y, default_w, default_h)

        # Respecter les dimensions normales personnalisées de l'utilisateur (clamper à l'écran disponible)
        w = max(980, min(w, avail.width()))
        h = max(600, min(h, avail.height()))

        x = self.settings.window_x
        y = self.settings.window_y

        if x <= -10000 or y <= -10000 or not avail.contains(QPoint(x + 60, y + 30)):
            x = avail.x() + max(0, (avail.width() - w) // 2)
            y = avail.y() + max(0, (avail.height() - h) // 2)
        else:
            if x + w > avail.right():
                x = max(avail.x(), avail.right() - w)
            if y + h > avail.bottom():
                y = max(avail.y(), avail.bottom() - h)

        return (x, y, w, h)

    def __init__(self, db: Optional[Database] = None):
        super().__init__()
        self.setWindowTitle("IPTV Hub — Lecteur Moderne")
        self.setWindowIcon(get_app_logo_icon())

        self.db = db or Database()
        self.settings = self.db.get_settings()

        # Calculer une géométrie fenêtrée saine et utilisable
        norm_x, norm_y, norm_w, norm_h = self._get_safe_normal_geometry()
        self.resize(norm_w, norm_h)
        self.move(norm_x, norm_y)
        self.setMinimumSize(980, 600)

        # Fenêtre moderne sans bordure avec barre de titre sur mesure
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.video_widget = MPVVideoWidget(parent=self)

        # Rendu vidéo via l'API OpenGL de libmpv (mpv_render_context) dans le
        # QOpenGLWidget interne : plus de fenêtre native séparée, l'OSD Qt
        # s'affiche directement par-dessus la vidéo.
        self.player_controller = PlayerController(
            render_mode=True,
            initial_volume=self.settings.volume,
            preferred_audio_lang=self.settings.preferred_audio_lang,
            preferred_subtitle_lang=self.settings.preferred_subtitle_lang,
            subtitles_enabled=self.settings.subtitles_enabled,
            parent=self
        )
        self.video_widget.set_player(self.player_controller)
        self.video_widget.controls.set_epg_provider(lambda tvg_id: self.db.get_current_program(tvg_id))

        self.current_channel: Optional[Channel] = None
        self.current_section: str = "dashboard"
        self._series_episodes: list = []
        self._current_series_idx: int = -1
        self._stopped_at_episode_end: bool = False
        self.is_fullscreen = False
        self._was_maximized_before_fullscreen = bool(self.settings.window_maximized)
        self._saved_splitter_sizes = [640, 780]
        self._saved_window_geom = QRect(norm_x, norm_y, norm_w, norm_h)
        self._refresh_worker: Optional[PlaylistImportWorker] = None

        # Variables pour le suivi de la reprise de lecture
        self._current_playback_pos: float = 0.0
        self._current_playback_dur: float = 0.0
        self._last_progress_saved_time: float = 0.0

        # Variables pour le redimensionnement depuis les bords
        self._edge_margin = 8
        self._drag_edge = None
        self._drag_start_pos = QPoint()
        self._drag_start_geometry = QRect()
        self._cursor_overridden = False
        self.setMouseTracking(True)

        # Initialisation de la langue de l'application AVANT de construire l'UI
        saved_lang = getattr(self.settings, "app_language", "fr")
        I18nManager.instance().set_language(saved_lang)
        I18nManager.instance().language_changed.connect(lambda _: self.retranslate_ui())

        self._init_ui()
        self._connect_signals()
        self._setup_shortcuts()

        self._update_search_placeholder(self.current_section)
        self._load_initial_data()

        # Restauration de l'état plein écran ou maximisé
        self._startup_fs_timer: Optional[QTimer] = None
        if self.settings.window_fullscreen:
            self._startup_fs_timer = QTimer(self)
            self._startup_fs_timer.setSingleShot(True)
            self._startup_fs_timer.timeout.connect(self.toggle_fullscreen)
            self._startup_fs_timer.start(80)
        elif self.settings.window_maximized:
            self.title_bar.set_maximized_icon(True)
            QTimer.singleShot(80, self.showMaximized)

        # Installation du filtre global d'événements pour le redimensionnement par les bords
        app_inst = QApplication.instance()
        if app_inst:
            app_inst.installEventFilter(self)

    def _init_ui(self):
        self.central_widget = QFrame(self)
        self.central_widget.setObjectName("centralWidget")
        self.central_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.central_widget.setStyleSheet("""
            #centralWidget {
                background-color: #1b2232;
                border: 1px solid #334155;
            }
        """)
        self.setCentralWidget(self.central_widget)

        root_layout = QVBoxLayout(self.central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Size grip pour le redimensionnement en bas à droite
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(18, 18)
        self.size_grip.setStyleSheet("""
            QSizeGrip {
                background: transparent;
                width: 18px;
                height: 18px;
            }
        """)

        # ------------------ 1. BARRE DE TITRE PERSONNALISÉE (HAUT) ------------------
        self.title_bar = CustomTitleBar(self)
        root_layout.addWidget(self.title_bar)

        # ------------------ 2. CORPS DE L'APPLICATION ------------------
        self.body_widget = QFrame()
        self.body_widget.setObjectName("bodyWidget")
        self.body_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.body_widget.setStyleSheet("#bodyWidget { background-color: #1b2232; }")
        body_layout = QHBoxLayout(self.body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # 2.1 Barre latérale de navigation compacte (Gauche, 56px)
        self.sidebar = Sidebar(self.db, self)
        body_layout.addWidget(self.sidebar)

        # 2.2 Stack principal : Page 0 = Lecteur / Chaînes, Page 1 = Vue Paramètres
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: #1b2232;")

        # Page 0 : Mode Lecteur (Splitter 3 Volets : Catégories + Chaînes + Lecteur Vidéo)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(8)
        self.splitter.setStyleSheet("""
            QSplitter { background-color: #1b2232; }
            QSplitter::handle:horizontal {
                background-color: transparent;
                border-left: 1px solid #28334a;
                border-right: 1px solid #141a26;
                margin: 0px 2px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #3b82f6;
                border: none;
                border-radius: 2px;
            }
            QSplitter::handle:horizontal:pressed {
                background-color: #2563eb;
            }
        """)

        # 1. Volet 0 : Panneau des Catégories
        self.categories_panel = CategoriesPanel(self)
        self.splitter.addWidget(self.categories_panel)

        # 2. Volet 1 : Panneau de la Liste des Chaînes
        self.channel_panel = ChannelListPanel(self.db, self)
        self.splitter.addWidget(self.channel_panel)

        # 3. Volet 2 : Stack principal droite : Lecteur Live TV vs Galerie VOD Films
        self.main_content_stack = QStackedWidget()
        self.main_content_stack.setStyleSheet("background-color: #111622;")
        self.main_content_stack.setMinimumWidth(0)

        # Page 0 : Lecteur Vidéo + Frise Chronologique EPG (Live TV & VOD Playback)
        self.right_container = QWidget()
        self.right_container.setObjectName("rightContainer")
        self.right_container.setStyleSheet("#rightContainer { background-color: #111622; }")
        self.right_container.setMinimumWidth(0)

        right_layout = QVBoxLayout(self.right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_layout.addWidget(self.video_widget, stretch=1)

        self.epg_timeline_panel = EPGTimelinePanel(self.db, self)
        if not self.settings.epg_panel_visible:
            self.epg_timeline_panel.set_collapsed(True)
        right_layout.addWidget(self.epg_timeline_panel, stretch=0)

        self.main_content_stack.addWidget(self.right_container)

        # Page 1 : Galerie VOD Films (Grille d'affiches + barre d'outils)
        self.vod_grid_view = VODGridView(self.db, stream_type="movie", parent=self)
        self.main_content_stack.addWidget(self.vod_grid_view)

        # Page 2 : Galerie Séries (Grille d'affiches + barre d'outils)
        self.series_grid_view = VODGridView(self.db, stream_type="series", parent=self)
        self.main_content_stack.addWidget(self.series_grid_view)

        # Page 3 : Fiche Série Détaillée
        self.series_details_view = SeriesDetailsView(self.db, parent=self)
        self.main_content_stack.addWidget(self.series_details_view)

        # Page 4 : Fiche Film VOD (vue intégrée — remplace MovieDetailsDialog)
        self.movie_details_view = MovieDetailsView(self.db, parent=self)
        self.main_content_stack.addWidget(self.movie_details_view)

        self.splitter.addWidget(self.main_content_stack)

        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, True)
        self.splitter.setCollapsible(2, False)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)

        cat_w = self.settings.category_panel_width if self.settings.category_panel_width > 160 else 280
        ch_w = self.settings.channel_list_width if self.settings.channel_list_width >= 200 else 360
        self.splitter.setSizes([cat_w, ch_w, 1000])
        self._saved_splitter_sizes = [cat_w, ch_w, 1000]

        self.content_stack.addWidget(self.splitter)

        # Page 1 : Mode Paramètres In-Place (Sous-menu + Contenu centré)
        self.settings_view = SettingsView(self.db, self)
        self.content_stack.addWidget(self.settings_view)

        # Page 2 : Vue Favoris Dédiée (Films / Séries, Toutes les listes, suppression rapide ×)
        self.favorites_view = FavoritesView(self.db, parent=self)
        self.content_stack.addWidget(self.favorites_view)

        # Page 3 : Vue Récemment Ajoutés (Carrousels Films, Séries, TV en direct)
        self.recently_added_view = RecentlyAddedView(self.db, parent=self)
        self.content_stack.addWidget(self.recently_added_view)

        # Page 4 : Vue Tableau de Bord Dédiée (Hero Banner, Reprise de lecture, Live TV récent, Favoris, Playlists, Récents)
        self.dashboard_view = DashboardView(self.db, parent=self)
        self.content_stack.addWidget(self.dashboard_view)

        # Page 5 : Vue Guide des Programmes EPG (Grille multi-chaînes synchronisée, Hero Card, Sélecteur de dates)
        self.epg_grid_view = EPGGridView(self.db, parent=self)
        self.content_stack.addWidget(self.epg_grid_view)

        # Page 6 : Vue Récemment regardé Dédiée (Films, Séries, TV en direct avec progression)
        self.history_view = RecentlyWatchedView(self.db, parent=self)
        self.content_stack.addWidget(self.history_view)

        # Page 7 : Vue TV Replay Dédiée (Rattrapage 7 jours)
        self.replay_view = ReplayView(self.db, parent=self)
        self.content_stack.addWidget(self.replay_view)

        body_layout.addWidget(self.content_stack, stretch=1)
        root_layout.addWidget(self.body_widget, stretch=1)

    def _connect_signals(self):
        # Contrôles de fenêtre (Custom Title Bar)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.search_text_changed.connect(self._on_search_text_changed)
        self.title_bar.playlist_changed.connect(self._on_playlist_changed)
        self.title_bar.refresh_clicked.connect(self._on_refresh_active_playlist)
        self.title_bar.add_playlist_clicked.connect(self._show_add_playlist_dialog)

        # Navigation Sidebar
        self.sidebar.section_changed.connect(self._on_section_changed)
        self.sidebar.manage_playlists_clicked.connect(self._show_manage_playlists_dialog)
        self.sidebar.settings_clicked.connect(self._open_settings_view)

        # Vue Paramètres
        self.settings_view.settings_saved.connect(self._on_settings_saved)
        self.settings_view.close_requested.connect(self._close_settings_view)

        # Vue Favoris
        self.favorites_view.movie_selected.connect(self._open_movie_details)
        self.favorites_view.series_selected.connect(self._open_series_details)
        self.favorites_view.channel_selected.connect(self.play_channel)

        # Vue Récemment Ajoutés
        self.recently_added_view.movie_selected.connect(self._open_movie_details)
        self.recently_added_view.series_selected.connect(self._open_series_details)
        self.recently_added_view.channel_selected.connect(self.play_channel)
        self.recently_added_view.browse_section_requested.connect(self._on_browse_section_requested)

        # Vue Tableau de Bord
        self.dashboard_view.movie_selected.connect(self._open_movie_details)
        self.dashboard_view.series_selected.connect(self._open_series_details)
        self.dashboard_view.channel_selected.connect(self.play_channel)
        self.dashboard_view.resume_playback_requested.connect(self._on_resume_playback)
        self.dashboard_view.navigate_section_requested.connect(self._on_dashboard_navigate)
        self.dashboard_view.playlist_switched.connect(self._on_dashboard_playlist_switched)

        # Vue Guide TV (EPG)
        self.epg_grid_view.play_channel_requested.connect(self.play_channel)
        self.epg_grid_view.manage_categories_requested.connect(self._open_manage_categories_dialog)

        # Vue Récemment regardé
        self.history_view.movie_selected.connect(self._open_movie_details)
        self.history_view.series_selected.connect(self._open_series_details)
        self.history_view.channel_selected.connect(self.play_channel)
        self.history_view.resume_playback_requested.connect(self._on_resume_playback)
        self.history_view.history_changed.connect(self.dashboard_view.refresh_view)
        self.history_view.history_changed.connect(self.vod_grid_view.update_all_progress_bars)

        # Vue TV Replay (Rattrapage)
        self.replay_view.play_replay_requested.connect(self._on_play_replay_requested)

        # Catégories
        self.categories_panel.category_selected.connect(self._on_category_selected)
        self.categories_panel.manage_categories_requested.connect(self._open_manage_categories_dialog)

        # Liste des chaînes
        self.channel_panel.channel_selected.connect(self._on_channel_selected)
        self.channel_panel.view_epg_requested.connect(self._show_epg_dialog)
        self.channel_panel.toggle_categories_requested.connect(self._toggle_categories_panel)

        # Contrôles Vidéo (Zapping, Seek 10s & Plein écran)
        self.video_widget.fullscreen_requested.connect(self.toggle_fullscreen)
        self.video_widget.play_pause_requested.connect(self._on_play_pause_requested)
        self.video_widget.controls.next_channel_clicked.connect(self._play_next_channel)
        self.video_widget.controls.previous_channel_clicked.connect(self._play_previous_channel)
        self.video_widget.controls.rewind_10_clicked.connect(lambda: self.player_controller.seek(-10, relative=True))
        self.video_widget.controls.forward_10_clicked.connect(lambda: self.player_controller.seek(10, relative=True))
        self.video_widget.controls.auto_next_toggled.connect(self._on_auto_next_toggled)
        self.video_widget.controls.set_auto_next_state(getattr(self.settings, "auto_play_next_episode", True))

        # Suivi de la position et de la durée pour la reprise de lecture
        self.player_controller.time_changed.connect(self._on_player_time_pos_changed)
        self.player_controller.duration_changed.connect(self._on_player_duration_changed)
        # Enchaînement automatique des épisodes de série en fin de lecture
        self.player_controller.playback_finished.connect(self._on_playback_finished)

        # Mémorisation dynamique des préférences de lecture (Volume, Langue audio, Sous-titres)
        self.video_widget.controls.volume_changed.connect(self._on_volume_changed)
        self.player_controller.volume_changed.connect(self._on_volume_changed)
        self.player_controller.audio_preference_changed.connect(self._on_audio_pref_changed)
        self.player_controller.subtitle_preference_changed.connect(self._on_subtitle_pref_changed)

        # Galerie VOD Films & Contrôles
        self.vod_grid_view.movie_selected.connect(self._on_vod_movie_selected)
        self.vod_grid_view.movie_details_requested.connect(self._open_movie_details)
        if hasattr(self.vod_grid_view, "artist_search_requested"):
            self.vod_grid_view.artist_search_requested.connect(self._show_artist_filmography)
        self.video_widget.controls.back_clicked.connect(self._return_to_vod_grid)

        # Galerie Séries & Fiche Série Détaillée
        self.series_grid_view.movie_selected.connect(self._open_series_details)
        self.series_grid_view.movie_details_requested.connect(self._open_series_details)
        if hasattr(self.series_grid_view, "artist_search_requested"):
            self.series_grid_view.artist_search_requested.connect(self._show_artist_filmography)
        self.series_details_view.back_clicked.connect(self._back_to_series_grid)
        self.series_details_view.fullscreen_requested.connect(self.toggle_fullscreen)
        self.series_details_view.favorite_toggled.connect(self._on_series_favorite_toggled)
        self.series_details_view.play_episode_requested.connect(self._on_series_play_episode_requested)
        self.series_details_view.play_trailer_requested.connect(lambda t, u: self._on_play_trailer_requested(t, u, "series"))
        self.series_details_view.artist_clicked.connect(self._show_artist_filmography)

        # Fiche Film VOD (vue intégrée)
        self.movie_details_view.back_clicked.connect(self._back_to_vod_grid_from_details)
        self.movie_details_view.play_requested.connect(self._on_movie_details_play_requested)
        self.movie_details_view.play_trailer_requested.connect(lambda t, u: self._on_play_trailer_requested(t, u, "movie"))
        self.movie_details_view.progress_cleared.connect(lambda _: (self.vod_grid_view.update_all_progress_bars(), self.dashboard_view.refresh_view()))
        self.movie_details_view.artist_clicked.connect(self._show_artist_filmography)

        # Mémorisation du redimensionnement libre des panneaux
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

    def _setup_shortcuts(self):
        # F ou F11 pour plein écran
        QShortcut(QKeySequence("F"), self, self.toggle_fullscreen)
        QShortcut(QKeySequence("F11"), self, self.toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self, self._exit_fullscreen)
        # Espace pour pause / reprise intelligente
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._on_play_pause_requested)
        # Flèches gauche/droite pour seek 10s
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.player_controller.seek(-10, relative=True))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.player_controller.seek(10, relative=True))

    def _load_initial_data(self):
        self.refresh_playlists_combo()
        playlists = self.db.get_playlists()
        if playlists:
            first_pl = playlists[0]
            self._apply_current_section(first_pl.id)
        else:
            QTimer.singleShot(500, self._prompt_first_playlist)

    def _prompt_first_playlist(self):
        playlists = self.db.get_playlists()
        if not playlists:
            self._show_add_playlist_dialog()

    # ------------------ GESTION PROPRE DE L'OSD LORS DES REDIMENSIONNEMENTS ------------------

    def _suspend_osd(self):
        """Masque immédiatement l'OSD vidéo pour éviter tout bug d'affichage lors des transitions de taille."""
        if hasattr(self, "_osd_resume_timer") and self._osd_resume_timer:
            try:
                self._osd_resume_timer.stop()
            except Exception:
                pass
            self._osd_resume_timer = None

        if hasattr(self, "video_widget"):
            self.video_widget._osd_suspended = True
            if hasattr(self.video_widget, "controls"):
                try:
                    self.video_widget.osd_timer.stop()
                    self.video_widget.controls.hide()
                    self.video_widget.controls.hide_bars()
                except Exception:
                    pass

    def _resume_osd(self, delay_ms: int = 180):
        """Recalcule la géométrie et réaffiche l'OSD une fois la nouvelle taille de fenêtre stabilisée."""
        if hasattr(self, "_osd_resume_timer") and self._osd_resume_timer:
            try:
                self._osd_resume_timer.stop()
            except Exception:
                pass

        self._osd_resume_timer = QTimer(self)
        self._osd_resume_timer.setSingleShot(True)
        self._osd_resume_timer.timeout.connect(self._do_resume_osd)
        self._osd_resume_timer.start(delay_ms)

    def _do_resume_osd(self):
        self._osd_resume_timer = None
        if hasattr(self, "video_widget"):
            self.video_widget._osd_suspended = False

        if not self.isVisible() or not hasattr(self, "video_widget") or not hasattr(self.video_widget, "controls"):
            return

        if not getattr(self.video_widget.controls, "has_active_media", False):
            return

        # Vérifier si la vidéo est actuellement dans la vue active
        is_video_visible = False
        if self.content_stack.currentIndex() == 0:
            if self.main_content_stack.currentIndex() == 0:
                is_video_visible = True
            elif self.main_content_stack.currentIndex() == 3 and getattr(self, "_is_playing_series_in_details", False):
                is_video_visible = True
            elif self.main_content_stack.currentIndex() == 4 and getattr(self, "_is_playing_movie_in_details", False):
                is_video_visible = True
            elif getattr(self, "_is_playing_trailer", False):
                is_video_visible = True

        if is_video_visible:
            self.video_widget._sync_geometry()
            if self.is_fullscreen and self.video_widget.controls.has_active_media and not getattr(self.video_widget.controls, "is_paused", False):
                self.video_widget.hide_mouse_cursor()

    # ------------------ GESTION DE LA BARRE DE TITRE & MAXIMIZE ------------------

    def _toggle_maximize(self):
        # Verrouillage réentrant et debounce pour éviter les conflits lors de clics rapides consécutifs
        if getattr(self, "_is_toggling_maximize", False):
            return
        now = time.monotonic()
        if now - getattr(self, "_last_maximize_toggle_time", 0.0) < 0.35:
            return
        self._is_toggling_maximize = True

        self._suspend_osd()

        # Si la fenêtre est en plein écran, quitter le plein écran d'abord et forcer le mode fenêtré
        was_in_fullscreen = bool(getattr(self, "is_fullscreen", False) or self.isFullScreen())
        if was_in_fullscreen:
            self._was_maximized_before_fullscreen = False
            self._exit_fullscreen()

        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        # Déterminer si la fenêtre est physiquement maximisée
        is_currently_max = bool(not was_in_fullscreen and (self.isMaximized() or (self.width() >= avail.width() - 15 and self.height() >= avail.height() - 15)))

        if is_currently_max or was_in_fullscreen:
            # Revenir en mode fenêtré (Normal)
            self.showNormal()
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.settings.window_maximized = False
            self.title_bar.set_maximized_icon(False)

            target_geom = None
            if (
                hasattr(self, "_saved_window_geom")
                and self._saved_window_geom.isValid()
                and self._saved_window_geom.width() >= 980
                and self._saved_window_geom.height() >= 600
                and not (self._saved_window_geom.width() >= avail.width() - 15 and self._saved_window_geom.height() >= avail.height() - 15)
            ):
                # Clamper impérativement les coordonnées x et y dans l'écran visible pour éviter toute disparition hors écran
                gx = max(avail.x(), min(self._saved_window_geom.x(), avail.right() - self._saved_window_geom.width()))
                gy = max(avail.y(), min(self._saved_window_geom.y(), avail.bottom() - self._saved_window_geom.height()))
                target_geom = QRect(gx, gy, self._saved_window_geom.width(), self._saved_window_geom.height())

            if target_geom is None:
                norm_x, norm_y, norm_w, norm_h = self._get_safe_normal_geometry()
                target_geom = QRect(norm_x, norm_y, norm_w, norm_h)
                self._saved_window_geom = target_geom

            self.resize(target_geom.width(), target_geom.height())
            self.move(target_geom.x(), target_geom.y())
            self.setVisible(True)
            self.raise_()
            self.activateWindow()

            self.settings.window_x = target_geom.x()
            self.settings.window_y = target_geom.y()
            self.settings.window_width = target_geom.width()
            self.settings.window_height = target_geom.height()

            if hasattr(self, "size_grip"):
                self.size_grip.show()
                self.size_grip.raise_()
            self._apply_layout_geometry(target_width=target_geom.width())
            QTimer.singleShot(50, lambda: self._apply_layout_geometry())
        else:
            # Passer en mode maximisé
            curr_geom = self.geometry()
            if not (curr_geom.width() >= avail.width() - 15 and curr_geom.height() >= avail.height() - 15):
                self._saved_window_geom = curr_geom
                self.settings.window_x = curr_geom.x()
                self.settings.window_y = curr_geom.y()
                self.settings.window_width = curr_geom.width()
                self.settings.window_height = curr_geom.height()

            self.showMaximized()
            self.setVisible(True)
            self.raise_()
            self.activateWindow()
            self.settings.window_maximized = True
            self.title_bar.set_maximized_icon(True)
            if hasattr(self, "size_grip"):
                self.size_grip.hide()
            self._apply_layout_geometry(target_width=avail.width())
            QTimer.singleShot(50, lambda: self._apply_layout_geometry())

        try:
            self.db.save_settings(self.settings)
        except Exception:
            pass

        self._update_details_video_geometry()
        QTimer.singleShot(60, self._update_details_video_geometry)
        QTimer.singleShot(150, self._update_details_video_geometry)
        QTimer.singleShot(250, self._update_details_video_geometry)
        self.update()
        self._refresh_chrome()
        QTimer.singleShot(60, self._refresh_chrome)
        self._resume_osd(delay_ms=180)

        def _unlock_max():
            self._is_toggling_maximize = False
            self._last_maximize_toggle_time = time.monotonic()
        QTimer.singleShot(150, _unlock_max)


    # ------------------ GESTION DU MENU DÉROULANT DES LISTES ------------------

    def refresh_playlists_combo(self, select_playlist_id: Optional[int] = None):
        """Met à jour le menu déroulant des listes de lecture dans la barre de titre."""
        prev_id = select_playlist_id or self.get_selected_playlist_id()
        self.title_bar.playlist_combo.blockSignals(True)
        self.title_bar.playlist_combo.clear()

        playlists = self.db.get_playlists()
        from core.i18n import tr
        if not playlists:
            self.title_bar.playlist_combo.addItem(tr("Aucune liste de lecture"), userData=None)
        else:
            selected_idx = 0
            for i, p in enumerate(playlists):
                icon = get_icon("account_circle" if p.playlist_type == "xtream" else "link", color="#818cf8")
                p_display_name = tr(p.name)
                self.title_bar.playlist_combo.addItem(icon, f" {p_display_name} ({p.channel_count})", userData=p.id)
                if prev_id and p.id == prev_id:
                    selected_idx = i
            self.title_bar.playlist_combo.setCurrentIndex(selected_idx)

        self.title_bar.playlist_combo.blockSignals(False)

    def get_selected_playlist_id(self) -> Optional[int]:
        return self.title_bar.playlist_combo.currentData()

    def _on_playlist_changed(self, playlist_id: int):
        self._save_current_playback_progress()
        self.player_controller.stop()
        self.video_widget.controls.hide()
        self.current_channel = None
        self._current_playback_pos = 0.0
        self._current_playback_dur = 0.0
        self._apply_current_section(playlist_id)

    def _on_refresh_active_playlist(self):
        """Rafraîchit et synchronise la liste de lecture active."""
        pl_id = self.get_selected_playlist_id()
        if not pl_id:
            self._show_add_playlist_dialog()
            return

        playlist = self.db.get_playlist(pl_id)
        if not playlist:
            return

        self.title_bar.status_label.setText(f"Synchronisation de '{playlist.name}'...")
        self.title_bar.progress_bar.setVisible(True)
        self.title_bar.refresh_btn.setEnabled(False)

        self._refresh_worker = PlaylistImportWorker(self.db, playlist, self)
        self._refresh_worker.progress.connect(self.title_bar.status_label.setText)
        self._refresh_worker.finished_success.connect(self._on_refresh_success)
        self._refresh_worker.error.connect(self._on_refresh_error)
        self._refresh_worker.start()

    def _on_refresh_success(self, playlist_id: int):
        self.title_bar.progress_bar.setVisible(False)
        self.title_bar.refresh_btn.setEnabled(True)
        self.title_bar.status_label.setText("Synchronisation réussie !")
        QTimer.singleShot(3000, lambda: self.title_bar.status_label.setText(""))

        self.refresh_playlists_combo(select_playlist_id=playlist_id)
        self._refresh_active_views_data(playlist_id)

    def _refresh_active_views_data(self, playlist_id: Optional[int]):
        """Met à jour les données de la liste et des vues après synchronisation sans jamais changer d'écran."""
        if not playlist_id:
            return

        current_content_idx = self.content_stack.currentIndex()
        current_main_idx = self.main_content_stack.currentIndex()
        is_playing = bool(self.current_channel and self.player_controller._current_state in ("playing", "paused", "buffering"))
        is_playing_in_details = getattr(self, "_is_playing_series_in_details", False) or getattr(self, "_is_playing_movie_in_details", False)

        # 1. Si on est sur une vue dédiée du conteneur racine (hors navigation standard)
        if current_content_idx == 2 and hasattr(self, "favorites_view"):
            self.favorites_view.set_playlist_id(playlist_id)
            self.favorites_view.refresh_view()
            return
        elif current_content_idx == 3 and hasattr(self, "recently_added_view"):
            self.recently_added_view.set_playlist_id(playlist_id)
            self.recently_added_view.refresh_view()
            return
        elif current_content_idx == 4 and hasattr(self, "dashboard_view"):
            self.dashboard_view.set_playlist_id(playlist_id)
            self.dashboard_view.refresh_view()
            return
        elif current_content_idx == 5 and hasattr(self, "epg_grid_view"):
            self.epg_grid_view.set_playlist_id(playlist_id)
            self.epg_grid_view.refresh_view()
            return
        elif current_content_idx == 6 and hasattr(self, "history_view"):
            self.history_view.set_playlist_id(playlist_id)
            self.history_view.refresh_view()
            return
        elif current_content_idx == 7 and hasattr(self, "replay_view"):
            self.replay_view.set_playlist_id(playlist_id)
            self.replay_view.refresh_view()
            return
        elif current_content_idx == 1:
            # Mode Paramètres : ne rien changer
            return

        # 2. Navigation standard (content_stack == 0) : Live, VOD ou Séries
        stream_type = self.current_section if self.current_section in ("live", "vod", "series") else "live"
        if stream_type == "vod":
            stream_type = "movie"
        fav_only = (self.current_section == "favorites")

        groups = self.db.get_groups(
            playlist_id=playlist_id,
            stream_type=stream_type if not fav_only else None,
            favorites_only=fav_only,
            only_enabled=True
        )

        cat_list = groups
        if self.current_section in ("vod", "series"):
            from core.models import prioritize_categories
            cat_list = prioritize_categories(groups)

        current_selected_cat = getattr(self.categories_panel, "_current_selected_cat", "")
        available_cat_names = [g[0] for g in cat_list]
        target_cat = current_selected_cat if current_selected_cat in available_cat_names else (cat_list[0][0] if cat_list else "")

        # Mettre à jour le panneau des catégories en conservant la catégorie courante
        if hasattr(self, "categories_panel"):
            self.categories_panel.set_categories(cat_list, default_selected=target_cat)

        # Si l'utilisateur est dans une fiche détaillée ou en lecture (série ou film)
        if current_main_idx in (3, 4) or is_playing_in_details:
            # Préserver strictement la fiche et le lecteur en cours (aucun changement d'écran)
            return

        # Si une vidéo est en cours dans le lecteur principal
        if current_main_idx == 0:
            if is_playing:
                # Lecture en cours : ne surtout pas basculer l'écran
                if self.current_section == "live" and hasattr(self, "channel_panel"):
                    self.channel_panel.set_playlist(playlist_id, stream_type=stream_type if not fav_only else None, favorites_only=fav_only)
                    if target_cat:
                        self.channel_panel.set_category(target_cat)
                return

        # Si l'utilisateur est sur la galerie VOD Films (main_content_stack == 1)
        if current_main_idx == 1 and hasattr(self, "vod_grid_view"):
            self.vod_grid_view.set_playlist_and_category(playlist_id, target_cat)
            return

        # Si l'utilisateur est sur la galerie Séries (main_content_stack == 2)
        if current_main_idx == 2 and hasattr(self, "series_grid_view"):
            self.series_grid_view.set_playlist_and_category(playlist_id, target_cat)
            return

        # Si l'utilisateur est sur la liste des chaînes en direct
        if hasattr(self, "channel_panel"):
            self.channel_panel.set_playlist(playlist_id, stream_type=stream_type if not fav_only else None, favorites_only=fav_only)
            if target_cat:
                self.channel_panel.set_category(target_cat)

    def _on_refresh_error(self, err_msg: str):
        self.title_bar.progress_bar.setVisible(False)
        self.title_bar.refresh_btn.setEnabled(True)
        self.title_bar.status_label.setText("")
        QMessageBox.critical(self, "Erreur de synchronisation", f"Impossible de synchroniser la liste :\n{err_msg}")

    # ------------------ GESTION DE LA LECTURE & SÉRIES ------------------

    def _on_channel_selected(self, channel: Channel):
        """Gère la sélection d'un élément (chaîne directe, film VOD ou série)."""
        if channel.stream_type == "series" and (channel.stream_url.startswith("xtream_series://") or channel.stream_id):
            self._open_series_details(channel)
        else:
            self._series_episodes = []
            self._current_series_idx = -1
            self.play_channel(channel)

    def _on_series_episode_chosen(self, episodes: list, current_idx: int):
        self._series_episodes = episodes
        self._current_series_idx = current_idx
        if 0 <= current_idx < len(episodes):
            ep = episodes[current_idx]
            self.play_channel(ep)
            if hasattr(self, "series_details_view") and getattr(ep, "stream_id", None):
                self.series_details_view.set_active_playing_episode(str(ep.stream_id))

    def _on_player_time_pos_changed(self, pos: float):
        if pos > 0:
            self._current_playback_pos = pos

        # Mise à jour en temps réel de la barre de progression sous la vignette de l'épisode de série (cadencée à 1s)
        if (
            self.current_channel
            and self.current_channel.stream_type == "series"
            and hasattr(self, "series_details_view")
            and (getattr(self, "_is_playing_series_in_details", False) or self.main_content_stack.currentIndex() == 3)
        ):
            if abs(pos - getattr(self, "_last_series_ui_progress_pos", 0.0)) >= 1.0:
                self._last_series_ui_progress_pos = pos
                ep_id = str(getattr(self.current_channel, "stream_id", "") or self.current_channel.id or "")
                self.series_details_view.update_playback_progress(
                    episode_id=ep_id,
                    position=pos,
                    duration=self._current_playback_dur,
                    stream_url=self.current_channel.stream_url or ""
                )

        # Sauvegarde périodique toutes les 5 secondes pour les films, séries et replays (hors bandes-annonces)
        if (
            not getattr(self, "_is_playing_trailer", False)
            and self.current_channel
            and self.current_channel.stream_type in ("movie", "vod", "series", "replay")
            and pos > 0
        ):
            import time
            now = time.time()
            if now - self._last_progress_saved_time >= 5.0:
                self._last_progress_saved_time = now
                self._save_current_playback_progress()

    def _on_player_duration_changed(self, dur: float):
        if dur > 0:
            self._current_playback_dur = dur
            if (
                self._current_playback_pos > 0
                and self.current_channel
                and self.current_channel.stream_type == "series"
                and hasattr(self, "series_details_view")
                and (getattr(self, "_is_playing_series_in_details", False) or self.main_content_stack.currentIndex() == 3)
            ):
                ep_id = str(getattr(self.current_channel, "stream_id", "") or self.current_channel.id or "")
                self.series_details_view.update_playback_progress(
                    episode_id=ep_id,
                    position=self._current_playback_pos,
                    duration=dur,
                    stream_url=self.current_channel.stream_url or ""
                )

    def _save_current_playback_progress(self):
        if not self.current_channel or getattr(self, "_is_playing_trailer", False) or self.current_channel.stream_type == "trailer":
            return
        if self.current_channel.stream_type in ("movie", "vod", "series", "replay") or self._current_playback_dur > 0:
            self.db.save_playback_progress(
                channel_id=self.current_channel.id,
                stream_url=self.current_channel.stream_url,
                channel_name=self.current_channel.name,
                position=self._current_playback_pos,
                duration=self._current_playback_dur
            )

    def _on_series_episode_started(self, channel: Channel):
        """Enregistre l'épisode de série en cours de lecture dans l'historique."""
        self._save_current_playback_progress()
        self.current_channel = channel
        history = WatchHistory(
            channel_id=channel.id or 0,
            channel_name=channel.name,
            stream_url=channel.stream_url,
            logo_url=channel.logo_url,
            group_title=channel.group_title
        )
        self.db.add_watch_history(history)

    def play_channel(self, channel: Channel, start_time: Optional[float] = None):
        """Lance la lecture d'une chaîne, d'un film ou d'un épisode avec reprise optionnelle."""
        self._stopped_at_episode_end = False
        self._save_current_playback_progress()
        self.current_channel = channel

        # S'assurer que le conteneur principal du lecteur est visible
        self.content_stack.setCurrentIndex(0)
        self.main_content_stack.setCurrentIndex(0)

        if channel.logo_url:
            from core.image_loader import ImageLoader
            ImageLoader.instance().request_image_priority(channel.logo_url)

        if channel.stream_type == "replay" or "/timeshift/" in (channel.stream_url or "").lower():
            channel.stream_type = "replay"

        epg = self.db.get_current_program(channel.tvg_id) if (channel.tvg_id and channel.stream_type == "live") else None

        self.video_widget.controls.update_channel_info(channel, epg)
        if self.current_section == "dashboard":
            self.video_widget.controls.set_back_button_text("‹  Retour au tableau de bord")
        elif self.current_section == "favorites":
            self.video_widget.controls.set_back_button_text("‹  Retour aux favoris")
        elif self.current_section == "history":
            self.video_widget.controls.set_back_button_text("‹  Retour à l'historique")
        elif self.current_section == "recently_added":
            self.video_widget.controls.set_back_button_text("‹  Retour aux récents")
        elif self.current_section == "epg":
            self.video_widget.controls.set_back_button_text("‹  Retour au guide TV")
        elif self.current_section == "replay":
            self.video_widget.controls.set_back_button_text("‹  Retour au Replay")
        elif self.current_section == "vod":
            self.video_widget.controls.set_back_button_text("‹  Retour aux films")
        elif self.current_section == "series":
            self.video_widget.controls.set_back_button_text("‹  Retour aux séries")
        elif getattr(self, "_return_target_index", 1) == 4:
            self.video_widget.controls.set_back_button_text("‹  Retour à la fiche")
        elif getattr(self, "_return_target_index", 1) == 3:
            self.video_widget.controls.set_back_button_text("‹  Retour à la fiche série")

        if channel.stream_type == "live":
            self.current_section = "live"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("live")
            self._update_search_placeholder("live", clear_text=True)

            playlist_id = channel.playlist_id or self.get_selected_playlist_id()
            cat_list = self.db.get_groups(playlist_id=playlist_id, stream_type="live", only_enabled=True)

            target_cat = ""
            if channel.group_title:
                ch_grp_clean = channel.group_title.strip().lower()
                for g_name, _ in cat_list:
                    if g_name.strip().lower() == ch_grp_clean:
                        target_cat = g_name
                        break
            if not target_cat:
                target_cat = channel.group_title or (cat_list[0][0] if cat_list else "")

            self.categories_panel.set_title("Catégories en direct")
            self.categories_panel.set_categories(cat_list, default_selected=target_cat)
            self.categories_panel.select_category(target_cat, emit_signal=False)

            self.channel_panel.set_playlist(playlist_id, stream_type="live", favorites_only=False)
            if target_cat:
                self.channel_panel.set_category(target_cat)
            self.channel_panel.select_channel(channel, scroll_to_top=False)

            self.channel_panel.show()
            self._apply_layout_geometry()
            self.epg_timeline_panel.setVisible(True)
            self.epg_timeline_panel.set_channel(channel)
            self.epg_timeline_panel.set_current_program_info(epg)
        else:
            self.channel_panel.hide()
            self.epg_timeline_panel.setVisible(False)
            self._apply_layout_geometry()
            self._update_video_widget_geometry()

        history = WatchHistory(
            channel_id=channel.id or 0,
            channel_name=channel.name,
            stream_url=channel.stream_url,
            logo_url=channel.logo_url,
            group_title=channel.group_title
        )
        self.db.add_watch_history(history)

        # Détermination du point de départ
        if start_time is None:
            if channel.stream_type in ("movie", "vod", "series", "replay"):
                prog = self.db.get_playback_progress(channel.id, channel.stream_url)
                start_time = prog[0] if prog else 0.0
            else:
                start_time = 0.0

        self._current_playback_pos = start_time
        self._current_playback_dur = 0.0
        self._last_progress_saved_time = 0.0

        ua = channel.user_agent or self.settings.user_agent
        self.player_controller.play(
            url=channel.stream_url,
            start_time=start_time,
            user_agent=ua,
            http_referrer=channel.http_referrer,
            extra_headers=channel.extra_headers
        )
        self.video_widget.setFocus()

    def _play_next_channel(self):
        if not self.current_channel:
            return

        if self.current_channel.stream_type == "series":
            # 1. Marquer l'épisode quitté comme lu à 100%
            old_ep = self.current_channel
            dur = self._current_playback_dur if self._current_playback_dur > 0 else (self._current_playback_pos if self._current_playback_pos > 0 else 3600.0)
            self.db.save_playback_progress(
                channel_id=old_ep.id,
                stream_url=old_ep.stream_url,
                channel_name=old_ep.name,
                position=dur,
                duration=dur
            )

            # 2. Déterminer l'épisode suivant
            if self._series_episodes and 0 <= self._current_series_idx < len(self._series_episodes) - 1:
                self._current_series_idx += 1
                next_ep = self._series_episodes[self._current_series_idx]
            elif self._series_episodes and len(self._series_episodes) > 0:
                self._current_series_idx = 0
                next_ep = self._series_episodes[0]
            else:
                next_ep = None

            if next_ep:
                self.current_channel = None
                self._current_playback_pos = 0.0
                self._current_playback_dur = 0.0
                if getattr(self, "_is_playing_series_in_details", False):
                    self._play_series_episode_in_details(next_ep, start_pos=0.0)
                    if hasattr(self, "series_details_view"):
                        self.series_details_view.refresh_progress()
                else:
                    self.play_channel(next_ep, start_time=0.0)
                    if hasattr(self, "series_details_view") and getattr(next_ep, "stream_id", None):
                        self.series_details_view.set_active_playing_episode(str(next_ep.stream_id))
        elif self.current_channel.stream_type == "live":
            # Navigation vers la chaîne suivante en direct
            channels = self.channel_panel.get_channels()
            if not channels:
                pl_id = self.get_selected_playlist_id()
                channels = self.db.get_channels(playlist_id=pl_id, stream_type="live", only_enabled=True)
            if not channels:
                return
            try:
                curr_idx = -1
                for i, c in enumerate(channels):
                    if (c.id and self.current_channel.id and c.id == self.current_channel.id) or c.stream_url == self.current_channel.stream_url:
                        curr_idx = i
                        break
                if curr_idx != -1:
                    next_idx = (curr_idx + 1) % len(channels)
                    self.play_channel(channels[next_idx])
                else:
                    self.play_channel(channels[0])
            except Exception:
                if channels:
                    self.play_channel(channels[0])

    def _play_next_series_episode(self) -> bool:
        """Enchaîne sur l'épisode de série suivant dans l'ordre (S N -> S N+1).

        Retourne True si un épisode suivant a été trouvé et lancé, False sinon.
        """
        self._stopped_at_episode_end = False
        next_ep = None
        if self._series_episodes and 0 <= self._current_series_idx < len(self._series_episodes) - 1:
            self._current_series_idx += 1
            next_ep = self._series_episodes[self._current_series_idx]

        if not next_ep:
            # Dernier épisode de la série : on ne fait rien, la lecture s'arrête.
            if hasattr(self, "series_details_view"):
                self.series_details_view.refresh_progress()
            return False

        self.current_channel = None
        self._current_playback_pos = 0.0
        self._current_playback_dur = 0.0
        self._last_progress_saved_time = 0.0
        if getattr(self, "_is_playing_series_in_details", False):
            self._play_series_episode_in_details(next_ep, start_pos=0.0)
            if hasattr(self, "series_details_view"):
                self.series_details_view.refresh_progress()
        else:
            self.play_channel(next_ep, start_time=0.0)
            if hasattr(self, "series_details_view") and getattr(next_ep, "stream_id", None):
                self.series_details_view.set_active_playing_episode(str(next_ep.stream_id))
        return True

    def _on_play_pause_requested(self):
        """Gestion centralisée de la commande Play/Pause (Bouton OSD ou barre d'espace)."""
        if getattr(self, "_stopped_at_episode_end", False):
            if getattr(self.settings, "auto_play_next_episode", True):
                if self._play_next_series_episode():
                    return
            # Si pas d'épisode suivant ou lecture auto désactivée, relancer l'épisode actuel au début
            if self.current_channel:
                self._stopped_at_episode_end = False
                if getattr(self, "_is_playing_series_in_details", False):
                    self._play_series_episode_in_details(self.current_channel, start_pos=0.0)
                else:
                    self.play_channel(self.current_channel, start_time=0.0)
                return
        self.player_controller.toggle_pause()

    def _on_playback_finished(self):
        """Appelé quand un média à durée finie atteint sa fin (fin de fichier).

        Comportement :
        - Séries : enchaîne AUTOMATIQUEMENT sur l'épisode suivant (et passage de la
          dernière saison à la première saison suivante) tant qu'il en existe un.
          Sur le tout dernier épisode, on ne fait rien (la lecture s'arrête).
        - Films et TV en direct : rien de particulier (la lecture s'arrête).
        """
        if not self.current_channel:
            return
        # Ne concerne QUE les séries : jamais les films ni la TV en direct.
        if self.current_channel.stream_type != "series":
            return

        # 1. Marquer l'épisode qui vient de se terminer comme vu à 100%
        old_ep = self.current_channel
        dur = self._current_playback_dur if self._current_playback_dur > 0 else (self._current_playback_pos if self._current_playback_pos > 0 else 3600.0)
        self.db.save_playback_progress(
            channel_id=old_ep.id,
            stream_url=old_ep.stream_url,
            channel_name=old_ep.name,
            position=dur,
            duration=dur
        )

        # Si l'enchaînement automatique est désactivé, arrêter la lecture ici et mémoriser l'état
        if not getattr(self.settings, "auto_play_next_episode", True):
            self._stopped_at_episode_end = True
            if hasattr(self, "series_details_view"):
                self.series_details_view.refresh_progress()
            if hasattr(self, "video_widget") and hasattr(self.video_widget, "controls"):
                self.video_widget.controls.show_bars()
                self.video_widget.controls.set_playing_state("stopped")
            return

        # 2. Enchaîner sur l'épisode suivant
        self._play_next_series_episode()

    def _play_previous_channel(self):
        if not self.current_channel:
            return

        if self.current_channel.stream_type == "series":
            # Sauvegarder la position de l'épisode actuel qu'on quitte
            self._save_current_playback_progress()

            if self._series_episodes and self._current_series_idx > 0:
                self._current_series_idx -= 1
                prev_ep = self._series_episodes[self._current_series_idx]
            elif self._series_episodes and len(self._series_episodes) > 0:
                self._current_series_idx = len(self._series_episodes) - 1
                prev_ep = self._series_episodes[-1]
            else:
                prev_ep = None

            if prev_ep:
                self.current_channel = None
                self._current_playback_pos = 0.0
                self._current_playback_dur = 0.0
                if getattr(self, "_is_playing_series_in_details", False):
                    self._play_series_episode_in_details(prev_ep, start_pos=0.0)
                    if hasattr(self, "series_details_view"):
                        self.series_details_view.refresh_progress()
                else:
                    self.play_channel(prev_ep, start_time=0.0)
                    if hasattr(self, "series_details_view") and getattr(prev_ep, "stream_id", None):
                        self.series_details_view.set_active_playing_episode(str(prev_ep.stream_id))
        elif self.current_channel.stream_type == "live":
            # Navigation vers la chaîne précédente en direct
            channels = self.channel_panel.get_channels()
            if not channels:
                pl_id = self.get_selected_playlist_id()
                channels = self.db.get_channels(playlist_id=pl_id, stream_type="live", only_enabled=True)
            if not channels:
                return
            try:
                curr_idx = -1
                for i, c in enumerate(channels):
                    if (c.id and self.current_channel.id and c.id == self.current_channel.id) or c.stream_url == self.current_channel.stream_url:
                        curr_idx = i
                        break
                if curr_idx != -1:
                    prev_idx = (curr_idx - 1) % len(channels)
                    self.play_channel(channels[prev_idx])
                else:
                    self.play_channel(channels[-1])
            except Exception:
                if channels:
                    self.play_channel(channels[-1])

    # ------------------ SECTIONS NAVIGATION & PARAMÈTRES ------------------

    def _update_search_placeholder(self, section_id: Optional[str] = None, clear_text: bool = False):
        """Met à jour le placeholder de la zone de recherche selon la section active et nettoie la saisie si demandé."""
        sec = section_id or self.__dict__.get("current_section", "dashboard")
        tb = self.__dict__.get("title_bar")
        if tb:
            tb.set_category_placeholder(sec)
            if clear_text and hasattr(tb, "search_box") and tb.search_box.text():
                tb.search_box.clear()

    def _on_section_changed(self, section_id: str):
        # Sortie du plein écran si actif
        if self.is_fullscreen:
            self._exit_fullscreen()

        self._details_origin_section = None

        if getattr(self, "_is_playing_movie_in_details", False):
            self._stop_movie_details_playback()
        if getattr(self, "_is_playing_series_in_details", False):
            self._stop_series_details_playback()

        # Arrêt immédiat de toute diffusion en cours et mémorisation de la progression
        self._save_current_playback_progress()
        self.player_controller.stop()
        self.video_widget.controls.hide()
        self.current_channel = None
        self._current_playback_pos = 0.0
        self._current_playback_dur = 0.0

        # Rebascule sur le lecteur si on était dans les paramètres ou favoris
        self.current_section = section_id
        self._update_search_placeholder(section_id, clear_text=True)

        pl_id = self.get_selected_playlist_id()

        if section_id == "favorites":
            self.content_stack.setCurrentIndex(2)  # Vue Favoris Dédiée
            self.favorites_view.set_playlist_id(pl_id)
            self.favorites_view.refresh_view()
        elif section_id == "history":
            self.content_stack.setCurrentIndex(6)  # Vue Récemment regardé Dédiée
            self.history_view.set_playlist_id(pl_id)
            self.history_view.refresh_view()
        elif section_id == "recently_added":
            self.content_stack.setCurrentIndex(3)  # Vue Récemment Ajoutés (Carrousels)
            self.recently_added_view.set_playlist_id(pl_id)
            self.recently_added_view.refresh_view()
        elif section_id == "dashboard":
            self.content_stack.setCurrentIndex(4)  # Vue Tableau de Bord Dédiée
            self.dashboard_view.set_playlist_id(pl_id)
            self.dashboard_view.refresh_view()
        elif section_id == "epg":
            self.content_stack.setCurrentIndex(5)  # Vue Guide des Programmes EPG
            self.epg_grid_view.set_playlist_id(pl_id)
            self.epg_grid_view.refresh_view()
        elif section_id == "replay":
            self.content_stack.setCurrentIndex(7)  # Vue TV Replay (Rattrapage 7 jours)
            self.replay_view.set_playlist_id(pl_id)
            self.replay_view.refresh_view()
        elif section_id == "vod":
            self.content_stack.setCurrentIndex(0)
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            self.main_content_stack.setCurrentIndex(1)  # Vue Galerie VOD Films
            self._apply_layout_geometry()
            self._load_categories_and_channels()
        elif section_id == "series":
            self.content_stack.setCurrentIndex(0)
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            self.main_content_stack.setCurrentIndex(2)  # Vue Galerie Séries
            self._apply_layout_geometry()
            self._load_categories_and_channels()
        elif section_id == "live":
            self.content_stack.setCurrentIndex(0)
            self.channel_panel.show()
            self.main_content_stack.setCurrentIndex(0)  # Vue Lecteur / Chaînes
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.setVisible(True)
            self._apply_layout_geometry()
            self._apply_current_section(pl_id)
        else:
            self.content_stack.setCurrentIndex(0)
            self.channel_panel.show()
            self.main_content_stack.setCurrentIndex(0)
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.setVisible(False)
            self._apply_layout_geometry()
            self._apply_current_section(pl_id)

    def _apply_current_section(self, playlist_id: Optional[int]):
        self._update_search_placeholder(self.current_section)
        if self.current_section == "favorites":
            self.content_stack.setCurrentIndex(2)
            self.favorites_view.set_playlist_id(playlist_id)
            self.favorites_view.refresh_view()
        elif self.current_section == "history":
            self.content_stack.setCurrentIndex(6)
            self.history_view.set_playlist_id(playlist_id)
            self.history_view.refresh_view()
        elif self.current_section == "recently_added":
            self.content_stack.setCurrentIndex(3)
            self.recently_added_view.set_playlist_id(playlist_id)
            self.recently_added_view.refresh_view()
        elif self.current_section == "dashboard":
            self.content_stack.setCurrentIndex(4)
            self.dashboard_view.set_playlist_id(playlist_id)
            self.dashboard_view.refresh_view()
        elif self.current_section == "epg":
            self.content_stack.setCurrentIndex(5)
            self.epg_grid_view.set_playlist_id(playlist_id)
            self.epg_grid_view.refresh_view()
        elif self.current_section == "replay":
            self.content_stack.setCurrentIndex(7)
            self.replay_view.set_playlist_id(playlist_id)
            self.replay_view.refresh_view()
        elif self.current_section == "vod":
            self.content_stack.setCurrentIndex(0)
            self.main_content_stack.setCurrentIndex(1)
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            self._apply_layout_geometry()
            self._load_categories_and_channels()
        elif self.current_section == "series":
            self.content_stack.setCurrentIndex(0)
            self.main_content_stack.setCurrentIndex(2)
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            self._apply_layout_geometry()
            self._load_categories_and_channels()
        elif self.current_section == "live":
            self.content_stack.setCurrentIndex(0)
            self.channel_panel.show()
            self.main_content_stack.setCurrentIndex(0)
            self._apply_layout_geometry()
            self._load_categories_and_channels()


    def _load_categories_and_channels(self):
        playlist_id = self.get_selected_playlist_id()
        stream_type = self.current_section if self.current_section in ("live", "vod", "series") else "live"
        if stream_type == "vod":
            stream_type = "movie"
        fav_only = (self.current_section == "favorites")

        # Titre des catégories
        if self.current_section == "live":
            self.categories_panel.set_title("Catégories en direct")
        elif self.current_section == "vod":
            self.categories_panel.set_title("Catégories de films")
        elif self.current_section == "series":
            self.categories_panel.set_title("Catégories Séries")
        elif fav_only:
            self.categories_panel.set_title("Catégories Favoris")
        else:
            self.categories_panel.set_title("Catégories")

        # Groupes
        groups = self.db.get_groups(
            playlist_id=playlist_id,
            stream_type=stream_type if not fav_only else None,
            favorites_only=fav_only,
            only_enabled=True
        )

        cat_list = groups
        if self.current_section in ("vod", "series"):
            from core.models import prioritize_categories
            cat_list = prioritize_categories(groups)

        default_cat = cat_list[0][0] if cat_list else ""

        if self.current_section == "vod":
            self.categories_panel.set_categories(cat_list, default_selected=default_cat)
            self.vod_grid_view.set_playlist_and_category(playlist_id, default_cat)
        elif self.current_section == "series":
            self.categories_panel.set_categories(cat_list, default_selected=default_cat)
            self.series_grid_view.set_playlist_and_category(playlist_id, default_cat)
        else:
            self.categories_panel.set_categories(cat_list, default_selected=default_cat)
            self.channel_panel.set_playlist(playlist_id, stream_type=stream_type if not fav_only else None, favorites_only=fav_only)
            if default_cat:
                self.channel_panel.set_category(default_cat)

    def _on_search_text_changed(self, text: str):
        query = text.strip()
        if self.current_section == "dashboard":
            dash = self.__dict__.get("dashboard_view")
            if dash:
                dash.set_search_query(query)
        elif self.current_section == "settings":
            pass
        elif self.current_section == "favorites":
            fav = self.__dict__.get("favorites_view")
            if fav:
                fav.set_search_query(query)
        elif self.current_section == "history":
            hist = self.__dict__.get("history_view")
            if hist:
                hist.set_search_query(query)
        elif self.current_section == "recently_added":
            rec = self.__dict__.get("recently_added_view")
            if rec:
                rec.set_search_query(query)
        elif self.current_section == "vod":
            stack = self.__dict__.get("main_content_stack")
            if stack and stack.currentIndex() != 1:
                stack.setCurrentIndex(1)
            vod = self.__dict__.get("vod_grid_view")
            if vod:
                vod.set_search_query(query)
        elif self.current_section == "series":
            stack = self.__dict__.get("main_content_stack")
            if stack and stack.currentIndex() != 2:
                stack.setCurrentIndex(2)
            ser = self.__dict__.get("series_grid_view")
            if ser:
                ser.set_search_query(query)
        elif self.current_section == "epg":
            epg = self.__dict__.get("epg_grid_view")
            if epg and hasattr(epg, "search_input"):
                epg.search_input.setText(query)
        elif self.current_section == "replay":
            rep = self.__dict__.get("replay_view")
            if rep and hasattr(rep, "search_input"):
                rep.search_input.setText(query)
        else:
            cp = self.__dict__.get("channel_panel")
            if cp:
                cp.set_search_query(query)

    def _on_play_replay_requested(self, channel: Channel, program_title: str, stream_url: str, duration_sec: float):
        """Lance la lecture d'une émission en Replay/Timeshift avec contrôles de lecture complets."""
        self.current_section = "replay"
        self._update_search_placeholder("replay", clear_text=True)
        self._return_target_index = 7

        replay_channel = Channel(
            id=channel.id,
            playlist_id=channel.playlist_id,
            name=f"{channel.name} : {program_title}",
            stream_url=stream_url,
            logo_url=channel.logo_url,
            group_title="TV Replay",
            stream_type="replay",  # type dédié replay pour OSD et contrôles de lecture
            user_agent=channel.user_agent,
            http_referrer=channel.http_referrer,
            extra_headers=channel.extra_headers
        )
        self.play_channel(replay_channel, start_time=0.0)
        self.video_widget.controls.set_back_button_text("‹  Retour au Replay")

    def _on_favorite_movie_selected(self, channel: Channel, start_time: Optional[float] = None):
        """Lance la lecture d'un film depuis la vue des favoris."""
        self.current_section = "vod"
        self._update_search_placeholder("vod", clear_text=True)
        self.content_stack.setCurrentIndex(0)
        self.main_content_stack.setCurrentIndex(0)
        self.channel_panel.hide()
        if hasattr(self, "epg_timeline_panel"):
            self.epg_timeline_panel.hide()
        self.play_channel(channel, start_time=start_time)

    def _on_category_selected(self, category_name: str):
        if self.current_section == "vod":
            if getattr(self, "_is_playing_movie_in_details", False):
                self._stop_movie_details_playback()
            self.main_content_stack.setCurrentIndex(1)
            self.vod_grid_view.set_playlist_and_category(self.get_selected_playlist_id(), category_name)
        elif self.current_section == "series":
            if getattr(self, "_is_playing_series_in_details", False):
                self._stop_series_details_playback()
            self.main_content_stack.setCurrentIndex(2)
            self.series_grid_view.set_playlist_and_category(self.get_selected_playlist_id(), category_name)
        else:
            self.channel_panel.show()
            self.main_content_stack.setCurrentIndex(0)
            self.channel_panel.set_category(category_name)

    def _open_series_details(self, channel: Channel, start_time: Optional[float] = None):
        """Ouvre la fiche détaillée de la série avec saisons, épisodes et lecteur intégré."""
        if getattr(self, "_is_playing_trailer", False):
            self._stop_trailer_playback()
        if getattr(self, "_is_playing_series_in_details", False):
            self._stop_series_details_playback()
        if getattr(self, "_is_playing_movie_in_details", False):
            self._stop_movie_details_playback()

        # Mémoriser la section d'origine avant ouverture de la fiche
        self._details_origin_section = self.current_section

        self.current_section = "series"
        if hasattr(self, "sidebar"):
            self.sidebar.set_active_section("series")
        self._update_search_placeholder("series", clear_text=True)
        self.content_stack.setCurrentIndex(0)
        self.main_content_stack.setCurrentIndex(3)

        # Résolution défensive de la série parente si stream_id est manquant ou si l'URL est un épisode
        if (not channel.stream_id or not str(channel.stream_id).strip() or not (channel.stream_url or "").startswith("xtream_series://")) and self.db:
            resolved_ch = None
            if channel.id:
                resolved_ch = self.db.get_channel_by_id(channel.id)
            if not resolved_ch or not resolved_ch.stream_id:
                matching = self.db.get_channels(
                    playlist_id=channel.playlist_id or self.get_selected_playlist_id(),
                    search_query=channel.name,
                    stream_type="series",
                    limit=10
                )
                for cand in matching:
                    if cand.stream_type == "series" and cand.stream_id:
                        if cand.name.lower().strip() == channel.name.lower().strip():
                            resolved_ch = cand
                            break
            if resolved_ch and resolved_ch.stream_id:
                channel = resolved_ch

        # S'assurer que le panneau des catégories contient bien les catégories de séries
        playlist_id = channel.playlist_id or self.get_selected_playlist_id()
        cat_to_select = channel.group_title or "Toutes les séries"
        if not getattr(self.categories_panel, "_all_categories", None) or self.categories_panel.title_label.text() != "Catégories Séries":
            groups = self.db.get_groups(
                playlist_id=playlist_id,
                stream_type="series",
                only_enabled=True,
            )
            from core.models import prioritize_categories
            cat_list = prioritize_categories(groups)
            self.categories_panel.set_title("Catégories Séries")
            self.categories_panel.set_categories(cat_list, default_selected=cat_to_select)
        elif channel.group_title:
            self.categories_panel.select_category(channel.group_title, emit_signal=False)

        self.categories_panel.show()
        self.channel_panel.hide()
        if hasattr(self, "epg_timeline_panel"):
            self.epg_timeline_panel.hide()
        self._apply_layout_geometry()

        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.series_details_view.setCursor(Qt.CursorShape.ArrowCursor)
        self.series_details_view.load_series(channel)

    def _back_to_series_grid(self):
        """Retourne de la fiche série à son point d'origine (tableau de bord, favoris, historique, récents ou galerie séries)."""
        if self.is_fullscreen:
            self._exit_fullscreen()
        if getattr(self, "_is_playing_trailer", False):
            self._stop_trailer_playback()
        if getattr(self, "_is_playing_series_in_details", False):
            self._stop_series_details_playback()
        self.series_details_view.close_player()

        origin = getattr(self, "_details_origin_section", None) or "series"
        self._details_origin_section = None

        if origin == "dashboard":
            self.current_section = "dashboard"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("dashboard")
            self.content_stack.setCurrentIndex(4)
            self.dashboard_view.refresh_view()
        elif origin == "favorites":
            self.current_section = "favorites"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("favorites")
            self.content_stack.setCurrentIndex(2)
            self.favorites_view.refresh_view()
        elif origin == "history":
            self.current_section = "history"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("history")
            self.content_stack.setCurrentIndex(6)
            self.history_view.refresh_view()
        elif origin == "recently_added":
            self.current_section = "recently_added"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("recently_added")
            self.content_stack.setCurrentIndex(3)
            self.recently_added_view.refresh_view()
        elif origin == "series":
            self.current_section = "series"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("series")
            self.content_stack.setCurrentIndex(0)
            if not self.settings.categories_collapsed:
                self.categories_panel.show()
            self.channel_panel.hide()
            self.main_content_stack.setCurrentIndex(2)
            target_cat = getattr(self.categories_panel, "_current_selected_cat", "") or "Toutes les séries"
            pl_id = self.get_selected_playlist_id()
            if self.series_grid_view.current_playlist_id != pl_id or self.series_grid_view.current_category != target_cat:
                self.series_grid_view.set_playlist_and_category(pl_id, target_cat)
            self.series_grid_view.update_all_progress_bars()
        else:
            self.current_section = origin
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section(origin)
            self.content_stack.setCurrentIndex(0)
            self.main_content_stack.setCurrentIndex(2)
            target_cat = getattr(self.categories_panel, "_current_selected_cat", "") or "Toutes les séries"
            pl_id = self.get_selected_playlist_id()
            if self.series_grid_view.current_playlist_id != pl_id or self.series_grid_view.current_category != target_cat:
                self.series_grid_view.set_playlist_and_category(pl_id, target_cat)
            self.series_grid_view.update_all_progress_bars()
        self._update_search_placeholder(self.current_section, clear_text=True)
        self._apply_layout_geometry()

    def _on_series_favorite_toggled(self, channel: Channel, is_fav: bool):
        self.series_grid_view.refresh()
        if hasattr(self, "favorites_view"):
            self.favorites_view.refresh_view()

    def _on_vod_movie_selected(self, channel: Channel, start_time: Optional[float] = None):
        """Ouvre la fiche détaillée d'un film VOD depuis la galerie."""
        self._open_movie_details(channel)

    def _on_series_play_episode_requested(self, channel: Channel, episodes: list, idx: int, start_pos: float):
        """Lance la lecture d'un épisode de série dans le conteneur scrollable de sa fiche détaillée."""
        if getattr(self, "_is_playing_trailer", False):
            self._stop_trailer_playback()
        self._return_target_index = 3
        self._series_episodes = episodes
        self._current_series_idx = idx

        if not getattr(self, "_is_playing_series_in_details", False):
            self._is_playing_series_in_details = True
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            self._apply_layout_geometry()

            # Détacher le lecteur vidéo du conteneur de droite et l'attacher à la fiche série
            self.right_container.layout().removeWidget(self.video_widget)
            self.series_details_view.attach_video_widget(self.video_widget)

        self._play_series_episode_in_details(channel, start_pos=start_pos)

    def _play_series_episode_in_details(self, episode_channel: Channel, start_pos: float = 0.0):
        """Joue un épisode directement dans la vue détaillée de la série sans quitter la fiche."""
        self._stopped_at_episode_end = False
        self._save_current_playback_progress()
        self.current_channel = episode_channel
        self._current_playback_pos = start_pos
        self._current_playback_dur = 0.0
        self._last_progress_saved_time = 0.0

        self.video_widget.controls.update_channel_info(episode_channel)
        self.video_widget.controls.set_back_button_text("‹  Retour à la fiche série")
        self.video_widget.controls.has_active_media = True

        if episode_channel.stream_id:
            self.series_details_view.set_active_playing_episode(str(episode_channel.stream_id))
        if hasattr(self, "series_details_view") and hasattr(self.series_details_view, "scroll_area"):
            self.series_details_view.scroll_area.verticalScrollBar().setValue(0)

        history = WatchHistory(
            channel_id=episode_channel.id or 0,
            channel_name=episode_channel.name,
            stream_url=episode_channel.stream_url,
            logo_url=episode_channel.logo_url,
            group_title=episode_channel.group_title,
        )
        self.db.add_watch_history(history)

        ua = episode_channel.user_agent or self.settings.user_agent
        self.player_controller.play(
            url=episode_channel.stream_url,
            start_time=start_pos,
            user_agent=ua,
            http_referrer=episode_channel.http_referrer,
            extra_headers=episode_channel.extra_headers,
        )
        self.video_widget._sync_geometry()
        self.video_widget._show_osd()

    def _stop_series_details_playback(self):
        """Arrête la lecture d'un épisode dans la fiche détaillée de série et remet le lecteur en place."""
        if not getattr(self, "_is_playing_series_in_details", False):
            return
        self._is_playing_series_in_details = False
        self._save_current_playback_progress()
        self.current_channel = None
        self._current_playback_pos = 0.0
        self._current_playback_dur = 0.0
        self.player_controller.stop()
        if hasattr(self, "video_widget"):
            self.video_widget.controls.hide()
            self.series_details_view.detach_video_widget(self.video_widget)
            self.right_container.layout().insertWidget(0, self.video_widget, stretch=1)
            self.video_widget.setMinimumHeight(0)
            self.video_widget.setMaximumHeight(16777215)
            self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_layout_geometry()
        self.series_details_view.refresh_progress()

    def _open_movie_details(self, channel: Channel):
        """Ouvre la fiche détaillée d'un film VOD dans la vue intégrée."""
        if getattr(self, "_is_playing_trailer", False):
            self._stop_trailer_playback()
        if getattr(self, "_is_playing_movie_in_details", False):
            self._stop_movie_details_playback()
        if getattr(self, "_is_playing_series_in_details", False):
            self._stop_series_details_playback()

        # Mémoriser la section d'origine avant ouverture de la fiche
        self._details_origin_section = self.current_section

        self.current_section = "vod"
        if hasattr(self, "sidebar"):
            self.sidebar.set_active_section("vod")
        self._update_search_placeholder("vod", clear_text=True)
        self.content_stack.setCurrentIndex(0)
        self.main_content_stack.setCurrentIndex(4)

        # S'assurer que le panneau des catégories contient bien les catégories de films
        playlist_id = channel.playlist_id or self.get_selected_playlist_id()
        cat_to_select = channel.group_title or "Tous les films"
        if not getattr(self.categories_panel, "_all_categories", None) or self.categories_panel.title_label.text() != "Catégories de films":
            groups = self.db.get_groups(
                playlist_id=playlist_id,
                stream_type="movie",
                only_enabled=True,
            )
            from core.models import prioritize_categories
            cat_list = prioritize_categories(groups)
            self.categories_panel.set_title("Catégories de films")
            self.categories_panel.set_categories(cat_list, default_selected=cat_to_select)
        elif channel.group_title:
            self.categories_panel.select_category(channel.group_title, emit_signal=False)

        self.categories_panel.show()
        self.channel_panel.hide()
        if hasattr(self, "epg_timeline_panel"):
            self.epg_timeline_panel.hide()
        self._apply_layout_geometry()

        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.movie_details_view.setCursor(Qt.CursorShape.ArrowCursor)
        self.movie_details_view.load_movie(channel)

    def _show_artist_filmography(self, artist_name: str, person_id: Optional[int] = None):
        """Ouvre le dialogue de filmographie croisée pour l'artiste sélectionné."""
        if not artist_name:
            return
        from ui.dialogs.artist_filmography_dialog import ArtistFilmographyDialog
        from core.tmdb_client import get_tmdb_language_code
        pl_id = self.get_selected_playlist_id()
        lang = get_tmdb_language_code(getattr(self.settings, "preferred_audio_lang", "fr"))
        dialog = ArtistFilmographyDialog(
            artist_name,
            self.db,
            playlist_id=pl_id,
            language=lang,
            person_id=person_id,
            parent=self,
        )
        dialog.movie_selected.connect(self._open_movie_details)
        dialog.series_selected.connect(self._open_series_details)
        dialog.exec()

    def _back_to_vod_grid_from_details(self):
        """Retour depuis la fiche film VOD vers son point d'origine."""
        if getattr(self, "is_fullscreen", False) or self.isFullScreen():
            self._exit_fullscreen()
        if getattr(self, "_is_playing_trailer", False):
            self._stop_trailer_playback()
        if getattr(self, "_is_playing_movie_in_details", False):
            self._stop_movie_details_playback()

        origin = getattr(self, "_details_origin_section", None) or "vod"
        self._details_origin_section = None

        if origin == "dashboard":
            self.current_section = "dashboard"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("dashboard")
            self.content_stack.setCurrentIndex(4)
            self.dashboard_view.refresh_view()
        elif origin == "favorites":
            self.current_section = "favorites"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("favorites")
            self.content_stack.setCurrentIndex(2)
            self.favorites_view.refresh_view()
        elif origin == "history":
            self.current_section = "history"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("history")
            self.content_stack.setCurrentIndex(6)
            self.history_view.refresh_view()
        elif origin == "recently_added":
            self.current_section = "recently_added"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("recently_added")
            self.content_stack.setCurrentIndex(3)
            self.recently_added_view.refresh_view()
        else:
            self.current_section = "vod"
            if hasattr(self, "sidebar"):
                self.sidebar.set_active_section("vod")
            self.content_stack.setCurrentIndex(0)
            self.main_content_stack.setCurrentIndex(1)
            target_cat = getattr(self.categories_panel, "_current_selected_cat", "") or "Tous les films"
            pl_id = self.get_selected_playlist_id()
            if self.vod_grid_view.current_playlist_id != pl_id or self.vod_grid_view.current_category != target_cat:
                self.vod_grid_view.set_playlist_and_category(pl_id, target_cat)
            self.vod_grid_view.update_all_progress_bars()
        self._update_search_placeholder(self.current_section, clear_text=True)
        self._apply_layout_geometry()

    def _on_movie_details_play_requested(self, channel: Channel, start_pos: float):
        """Lance la lecture d'un film dans le conteneur scrollable de sa fiche détaillée."""
        if getattr(self, "_is_playing_trailer", False):
            self._stop_trailer_playback()
        self._is_playing_movie_in_details = True
        self._return_target_index = 4
        self.current_channel = channel

        # Le panneau catégorie reste affiché à gauche (sauf si replié)
        self.channel_panel.hide()
        if hasattr(self, "epg_timeline_panel"):
            self.epg_timeline_panel.hide()
        self._apply_layout_geometry()

        # Détacher le lecteur vidéo du conteneur de droite et l'attacher à la fiche film
        self.right_container.layout().removeWidget(self.video_widget)
        self.movie_details_view.attach_video_widget(self.video_widget)

        # Mettre à jour l'OSD complet
        self.video_widget.controls.update_channel_info(channel)
        self.video_widget.controls.set_back_button_text("‹  Retour à la fiche")
        self.video_widget.controls.has_active_media = True

        # Enregistrer l'historique
        history = WatchHistory(
            channel_id=channel.id or 0,
            channel_name=channel.name,
            stream_url=channel.stream_url,
            logo_url=channel.logo_url,
            group_title=channel.group_title,
        )
        self.db.add_watch_history(history)

        self._current_playback_pos = start_pos
        self._current_playback_dur = 0.0
        self._last_progress_saved_time = 0.0

        ua = channel.user_agent or self.settings.user_agent
        self.player_controller.play(
            url=channel.stream_url,
            start_time=start_pos,
            user_agent=ua,
            http_referrer=channel.http_referrer,
            extra_headers=channel.extra_headers,
        )
        self.video_widget._sync_geometry()
        self.video_widget._show_osd()

    def _stop_movie_details_playback(self):
        """Arrête la lecture du film dans la fiche détaillée et remet le lecteur en place."""
        if not getattr(self, "_is_playing_movie_in_details", False):
            return
        self._is_playing_movie_in_details = False
        self._save_current_playback_progress()
        self.current_channel = None
        self._current_playback_pos = 0.0
        self._current_playback_dur = 0.0
        self.player_controller.stop()
        if hasattr(self, "video_widget"):
            self.video_widget.controls.hide()
            self.movie_details_view.detach_video_widget(self.video_widget)
            self.right_container.layout().insertWidget(0, self.video_widget, stretch=1)
            self.video_widget.setMinimumHeight(0)
            self.video_widget.setMaximumHeight(16777215)
            self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_layout_geometry()
        self.movie_details_view.refresh_progress()

    def _on_play_trailer_requested(self, title: str, trailer_url: str, origin: str):
        """Lance la lecture d'une bande-annonce YouTube intégrée dans la fiche (film ou série)."""
        if getattr(self, "_is_playing_movie_in_details", False):
            self._stop_movie_details_playback()
        if getattr(self, "_is_playing_series_in_details", False):
            self._stop_series_details_playback()
        if getattr(self, "_is_playing_trailer", False):
            self._stop_trailer_playback()

        self._is_playing_trailer = True
        self._trailer_origin = origin

        target_view = self.movie_details_view if origin == "movie" else self.series_details_view
        current_ch = target_view.channel if hasattr(target_view, "channel") else None

        trailer_channel = Channel(
            id=0,
            name=f"Bande-annonce : {title}",
            stream_url=trailer_url,
            stream_type="trailer",
            logo_url=current_ch.logo_url if current_ch else "",
            group_title="Bande-annonce"
        )
        self.current_channel = trailer_channel
        self._current_playback_pos = 0.0
        self._current_playback_dur = 0.0
        self._last_progress_saved_time = 0.0

        self.channel_panel.hide()
        if hasattr(self, "epg_timeline_panel"):
            self.epg_timeline_panel.hide()
        self._apply_layout_geometry()

        self.right_container.layout().removeWidget(self.video_widget)
        target_view.attach_video_widget(self.video_widget)

        self.video_widget.controls.update_channel_info(trailer_channel)
        back_text = "‹  Retour à la fiche" if origin == "movie" else "‹  Retour à la fiche série"
        self.video_widget.controls.set_back_button_text(back_text)
        self.video_widget.controls.has_active_media = True

        ua = current_ch.user_agent if current_ch else self.settings.user_agent
        self.player_controller.play(
            url=trailer_url,
            start_time=0.0,
            user_agent=ua,
        )
        self.video_widget._sync_geometry()
        self.video_widget._show_osd()

    def _stop_trailer_playback(self):
        """Arrête la bande-annonce et restaure proprement la fiche détaillée."""
        if not getattr(self, "_is_playing_trailer", False):
            return
        self._is_playing_trailer = False
        origin = getattr(self, "_trailer_origin", "movie")
        target_view = self.movie_details_view if origin == "movie" else self.series_details_view

        self.player_controller.stop()
        if hasattr(self, "video_widget"):
            self.video_widget.controls.hide()
            target_view.detach_video_widget(self.video_widget)
            self.right_container.layout().insertWidget(0, self.video_widget, stretch=1)
            self.video_widget.setMinimumHeight(0)
            self.video_widget.setMaximumHeight(16777215)
            self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._apply_layout_geometry()
        if hasattr(target_view, "refresh_progress"):
            target_view.refresh_progress()

    def _return_to_vod_grid(self):
        """Retourne à la vue précédente (Fiche film, Fiche série, Galerie), quitte le plein écran si actif et coupe la lecture."""
        if self.is_fullscreen:
            self._exit_fullscreen()

        if getattr(self, "_is_playing_trailer", False):
            self._stop_trailer_playback()
            return

        if getattr(self, "_is_playing_movie_in_details", False):
            self._stop_movie_details_playback()
            return

        if getattr(self, "_is_playing_series_in_details", False):
            self._stop_series_details_playback()
            return

        self._save_current_playback_progress()
        self.player_controller.stop()
        self.video_widget.controls.hide()

        if self.current_section == "dashboard":
            self.content_stack.setCurrentIndex(4)
            self._update_search_placeholder("dashboard", clear_text=True)
            self.dashboard_view.refresh_view()
            return

        if self.current_section == "favorites":
            self.content_stack.setCurrentIndex(2)
            self._update_search_placeholder("favorites", clear_text=True)
            self.favorites_view.refresh_view()
            return

        if self.current_section == "history":
            self.content_stack.setCurrentIndex(6)
            self._update_search_placeholder("history", clear_text=True)
            self.history_view.refresh_view()
            return

        if self.current_section == "recently_added":
            self.content_stack.setCurrentIndex(3)
            self._update_search_placeholder("recently_added", clear_text=True)
            self.recently_added_view.refresh_view()
            return

        if self.current_section == "epg":
            self.content_stack.setCurrentIndex(5)
            self._update_search_placeholder("epg", clear_text=True)
            self.epg_grid_view.refresh_view()
            return

        if self.current_section == "replay":
            self.content_stack.setCurrentIndex(7)
            self._update_search_placeholder("replay", clear_text=True)
            self.replay_view.refresh_view()
            return

        target_idx = getattr(self, "_return_target_index", 1)
        if target_idx == 4 and hasattr(self, "movie_details_view"):
            self.current_section = "vod"
            self._update_search_placeholder("vod", clear_text=True)
            self.main_content_stack.setCurrentIndex(4)
            self.movie_details_view.refresh_progress()
        elif target_idx == 3 and hasattr(self, "series_details_view"):
            self.current_section = "series"
            self._update_search_placeholder("series", clear_text=True)
            self.main_content_stack.setCurrentIndex(3)
            self.series_details_view.refresh_progress()
        elif target_idx == 2 and hasattr(self, "series_grid_view"):
            self.current_section = "series"
            self._update_search_placeholder("series", clear_text=True)
            self.main_content_stack.setCurrentIndex(2)
            self.series_grid_view.update_all_progress_bars()
        else:
            self.current_section = "vod"
            self._update_search_placeholder("vod", clear_text=True)
            self.main_content_stack.setCurrentIndex(1)
            self.vod_grid_view.update_all_progress_bars()
        self._apply_layout_geometry()

    def _on_browse_section_requested(self, section_id: str):
        """Navigue directement vers la section sélectionnée depuis les carrousels Récents."""
        self.sidebar.select_section(section_id)

    def _on_resume_playback(self, channel: Channel, position: float):
        """Reprend la lecture d'un flux (film, épisode ou replay) depuis le tableau de bord ou l'historique."""
        if channel.stream_type == "replay" or "/timeshift/" in (channel.stream_url or "").lower():
            channel.stream_type = "replay"
            self._return_target_index = 6 if self.current_section == "history" else (4 if self.current_section == "dashboard" else 7)
            self.play_channel(channel, start_time=position)
            if self.current_section == "history":
                self.video_widget.controls.set_back_button_text("‹  Retour à l'historique")
            elif self.current_section == "dashboard":
                self.video_widget.controls.set_back_button_text("‹  Retour au tableau de bord")
            else:
                self.video_widget.controls.set_back_button_text("‹  Retour au Replay")
        elif channel.stream_type == "series":
            series_channel = channel
            if channel.id:
                found = self.db.get_channel_by_id(channel.id)
                if found and found.stream_type == "series":
                    series_channel = found
            self._open_series_details(series_channel)
        elif channel.stream_type in ("movie", "vod"):
            movie_channel = channel
            if channel.id:
                found = self.db.get_channel_by_id(channel.id)
                if found and found.stream_type in ("movie", "vod"):
                    movie_channel = found
            self._open_movie_details(movie_channel)
        else:
            self.play_channel(channel, start_time=position)

    def _on_dashboard_navigate(self, section_key: str):
        """Redirige la navigation depuis les boutons 'Voir tout >' du tableau de bord."""
        if section_key == "manage_playlists":
            self._show_manage_playlists_dialog()
        elif section_key in ("live", "vod", "series", "favorites", "history", "epg", "recently_added"):
            self.sidebar.select_section(section_key)

    def _on_dashboard_playlist_switched(self, playlist: Playlist):
        """Bascule sur la liste de lecture sélectionnée depuis le carrousel des sources du tableau de bord."""
        if playlist.id:
            self.refresh_playlists_combo(select_playlist_id=playlist.id)
            self._on_playlist_changed(playlist.id)


    def _open_manage_categories_dialog(self):
        from ui.dialogs.manage_categories_dialog import ManageCategoriesDialog
        playlist_id = self.get_selected_playlist_id()
        stream_type = self.current_section if self.current_section in ("live", "vod", "series") else "live"
        if stream_type == "vod":
            stream_type = "movie"
        dlg = ManageCategoriesDialog(self.db, playlist_id, stream_type, self)
        dlg.categories_updated.connect(self._load_categories_and_channels)
        if stream_type == "live":
            dlg.categories_updated.connect(self.epg_grid_view.refresh_view)
        dlg.exec()

    def _load_dashboard_view(self, playlist_id: Optional[int]):
        """Charge le tableau de bord avec aperçu des flux et statistiques."""
        favs = self.db.get_channels(playlist_id=playlist_id, favorites_only=True, limit=50)
        recent = self.db.get_recently_added_channels(playlist_id=playlist_id, limit=50)
        combined = []
        seen = set()
        for c in favs + recent:
            if c.id not in seen:
                seen.add(c.id)
                combined.append(c)

        self.categories_panel.set_categories([("Tableau de bord", len(combined))], default_selected="Tableau de bord")
        self.channel_panel.cat_title_label.setText("Tableau de bord")
        self.channel_panel.cat_count_badge.setText(str(len(combined)))
        self.channel_panel.model.set_channels(combined)

    def _load_recently_added_view(self, playlist_id: Optional[int]):
        """Charge tout ce qui a été récemment ajouté (TV, Films VOD, Séries)."""
        recent = self.db.get_recently_added_channels(playlist_id=playlist_id, limit=250)
        self.categories_panel.set_categories([("Ajouts récents", len(recent))], default_selected="Ajouts récents")
        self.channel_panel.cat_title_label.setText("Tous les ajouts récents")
        self.channel_panel.cat_count_badge.setText(str(len(recent)))
        self.channel_panel.model.set_channels(recent)


    def _open_settings_view(self):
        """Ouvre la vue des paramètres in-place à droite de la sidebar."""
        self._save_current_playback_progress()
        self.player_controller.stop()
        self.video_widget.controls.hide()
        self.current_channel = None
        self._current_playback_pos = 0.0
        self._current_playback_dur = 0.0
        if hasattr(self, "settings_view"):
            self.settings_view._load_values()
        self.content_stack.setCurrentIndex(1)
        self.sidebar.btn_settings.setChecked(True)
        self._update_search_placeholder("settings", clear_text=True)

    def _close_settings_view(self):
        """Ferme la vue des paramètres et restaure fidèlement la section active."""
        target_section = self.current_section or "live"
        self._on_section_changed(target_section)
        btn_map = {
            "dashboard": self.sidebar.btn_dashboard,
            "favorites": self.sidebar.btn_favorites,
            "history": self.sidebar.btn_history,
            "live": self.sidebar.btn_live,
            "replay": self.sidebar.btn_replay,
            "vod": self.sidebar.btn_vod,
            "series": self.sidebar.btn_series,
            "epg": self.sidebar.btn_epg,
            "recently_added": self.sidebar.btn_recent_added,
        }
        btn = btn_map.get(target_section, self.sidebar.btn_live)
        if btn:
            btn.setChecked(True)
        if self.video_widget.controls.is_playing:
            self.video_widget._show_osd()

    def _on_settings_saved(self):
        self.settings = self.db.get_settings()
        self.player_controller.set_hwdec(self.settings.hwdec)
        self.player_controller.set_deinterlace(self.settings.deinterlace)
        self.player_controller.set_preferred_audio_lang(self.settings.preferred_audio_lang)
        self.player_controller.set_preferred_subtitle_lang(self.settings.preferred_subtitle_lang, self.settings.subtitles_enabled)
        if hasattr(self, "video_widget") and hasattr(self.video_widget, "controls"):
            self.video_widget.controls.set_auto_next_state(
                getattr(self.settings, "auto_play_next_episode", True)
            )
        if getattr(self.settings, "auto_play_next_episode", True) and getattr(self, "_stopped_at_episode_end", False):
            self._play_next_series_episode()

    def _on_auto_next_toggled(self, enabled: bool):
        self.settings.auto_play_next_episode = enabled
        self.db.save_settings(self.settings)
        try:
            if hasattr(self, "settings_view") and hasattr(self.settings_view, "auto_play_next_cb"):
                self.settings_view.auto_play_next_cb.blockSignals(True)
                self.settings_view.auto_play_next_cb.setChecked(enabled)
                self.settings_view.auto_play_next_cb.blockSignals(False)
        except Exception:
            pass

        if enabled and getattr(self, "_stopped_at_episode_end", False):
            self._play_next_series_episode()

    def _on_volume_changed(self, vol: int):
        self.db.update_volume(vol)

    def _on_audio_pref_changed(self, lang: str):
        self.settings.preferred_audio_lang = lang
        self.db.update_audio_subtitle_prefs(audio_lang=lang)

    def _on_subtitle_pref_changed(self, lang: str, enabled: bool):
        self.settings.preferred_subtitle_lang = lang
        self.settings.subtitles_enabled = enabled
        self.db.update_audio_subtitle_prefs(subtitle_lang=lang, subtitles_enabled=enabled)

    # ------------------ GESTION DU GEL GRAPHIQUE POUR PLEIN ÉCRAN ATOMIQUE ------------------

    def _refresh_chrome(self):
        """Force le rafraîchissement et le redessin synchrone des barres de navigation et de titre."""
        if hasattr(self, "sidebar") and self.sidebar.isVisible():
            self.sidebar.show()
            if hasattr(self.sidebar, "refresh_buttons"):
                self.sidebar.refresh_buttons()
            else:
                self.sidebar.update()
                for btn in self.sidebar.findChildren(QPushButton):
                    btn.update()
                    btn.repaint()
                self.sidebar.repaint()
        if hasattr(self, "title_bar") and self.title_bar.isVisible():
            self.title_bar.show()
            self.title_bar.update()
            self.title_bar.repaint()
        self.update()
        self.repaint()

    def _freeze_ui(self):
        """Gèle le rafraîchissement au niveau Qt pour éliminer les transitions en deux temps sans perturber le DWM Windows."""
        self._is_ui_frozen = True
        self.setUpdatesEnabled(False)

    def _unfreeze_ui(self):
        """Dégèle le rafraîchissement Qt et provoque un rendu de l'état final."""
        if not getattr(self, "_is_ui_frozen", False):
            return
        self._is_ui_frozen = False
        self.setUpdatesEnabled(True)
        if hasattr(self, "video_widget") and hasattr(self.video_widget, "video_surface"):
            try:
                self.video_widget.video_surface.update()
            except Exception:
                pass
        self._refresh_chrome()
        self._is_toggling_fullscreen = False
        self._last_fullscreen_toggle_time = time.monotonic()

    def _schedule_save_settings(self, delay_ms: int = 1500):
        """Planifie une sauvegarde asynchrone des paramètres en arrière-plan sans bloquer le thread GUI."""
        if not hasattr(self, "_save_settings_timer"):
            self._save_settings_timer = QTimer(self)
            self._save_settings_timer.setSingleShot(True)
            self._save_settings_timer.timeout.connect(self._do_deferred_save_settings)
        self._save_settings_timer.start(delay_ms)

    def _do_deferred_save_settings(self):
        try:
            self.db.save_settings(self.settings)
        except Exception:
            pass

    # ------------------ PLEIN ÉCRAN ------------------

    def toggle_fullscreen(self):
        if getattr(self, "_startup_fs_timer", None):
            try:
                self._startup_fs_timer.stop()
            except Exception:
                pass
            self._startup_fs_timer = None

        # Verrouillage réentrant et debounce pour éviter les clics multiples rapides ou rebonds
        if getattr(self, "_is_toggling_fullscreen", False):
            return
        now = time.monotonic()
        if now - getattr(self, "_last_fullscreen_toggle_time", 0.0) < 0.5:
            return
        self._is_toggling_fullscreen = True
        self._last_fullscreen_toggle_time = now

        is_actually_fs = bool(getattr(self, "is_fullscreen", False) or self.isFullScreen())

        if not is_actually_fs:
            self._suspend_osd()

            screen = self.screen() or QApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

            # Mémoriser si la fenêtre du programme était VRAIMENT maximisée
            is_physically_max = bool(self.isMaximized() or (self.width() >= avail.width() - 15 and self.height() >= avail.height() - 15))
            self._was_maximized_before_fullscreen = is_physically_max

            # Si on était en mode fenêtré normal, mémoriser la géométrie normale
            if not is_physically_max:
                curr_geom = self.geometry()
                if curr_geom.isValid() and curr_geom.width() >= 980 and curr_geom.height() >= 600:
                    self._saved_window_geom = curr_geom
                    self.settings.window_x = curr_geom.x()
                    self.settings.window_y = curr_geom.y()
                    self.settings.window_width = curr_geom.width()
                    self.settings.window_height = curr_geom.height()

            # Sauvegarde des largeurs réelles du splitter avant masquage
            if self.content_stack.currentIndex() == 0 and self.splitter.isVisible():
                sizes = self.splitter.sizes()
                if len(sizes) == 3:
                    if sizes[0] >= 160 and not self.settings.categories_collapsed:
                        self.settings.category_panel_width = sizes[0]
                    if sizes[1] >= 200 and self.current_section not in ("vod", "series"):
                        self.settings.channel_list_width = sizes[1]
                self._saved_splitter_sizes = sizes

            self.is_fullscreen = True
            self.settings.window_fullscreen = True
            self._schedule_save_settings(2000)

            self._freeze_ui()

            self.title_bar.hide()
            self.sidebar.hide()
            self.channel_panel.hide()
            self.categories_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            if hasattr(self, "size_grip"):
                self.size_grip.hide()

            # Aplatir le splitter sur le volet vidéo
            self.splitter.setSizes([0, 0, 100000])
            self.splitter.setHandleWidth(0)
            self.splitter.setStyleSheet("""
                QSplitter { background-color: #000000; border: none; margin: 0; padding: 0; }
                QSplitter::handle { background-color: #000000; border: none; width: 0px; height: 0px; margin: 0; }
            """)

            # Tous les conteneurs en noir pur sans bordure ni marge
            self.central_widget.setStyleSheet("#centralWidget { background-color: #000000; border: none; margin: 0; padding: 0; }")
            if hasattr(self, "body_widget"):
                self.body_widget.setStyleSheet("#bodyWidget { background-color: #000000; border: none; margin: 0; padding: 0; }")
            self.content_stack.setStyleSheet("background-color: #000000; border: none; margin: 0; padding: 0;")
            self.main_content_stack.setStyleSheet("background-color: #000000; border: none; margin: 0; padding: 0;")
            self.right_container.setStyleSheet("#rightContainer { background-color: #000000; border: none; margin: 0; padding: 0; }")
            self.video_widget.setStyleSheet("background-color: #000000; border: none; margin: 0; padding: 0;")
            self.video_widget.stack.setStyleSheet("background-color: #000000; border: none; margin: 0; padding: 0;")
            self.video_widget.video_surface.setStyleSheet("background-color: #000000; border: none; margin: 0; padding: 0;")
            self.video_widget.set_fullscreen(True)
            if getattr(self, "_is_playing_movie_in_details", False) or (getattr(self, "_trailer_origin", "") == "movie" and getattr(self, "_is_playing_trailer", False)):
                self.movie_details_view.set_fullscreen(True)
            if getattr(self, "_is_playing_series_in_details", False) or (getattr(self, "_trailer_origin", "") == "series" and getattr(self, "_is_playing_trailer", False)):
                self.series_details_view.set_fullscreen(True)

            self.showFullScreen()
            self.setVisible(True)
            self.raise_()
            self.activateWindow()
            QTimer.singleShot(50, self._unfreeze_ui)

            if getattr(self, "_is_playing_movie_in_details", False) or (getattr(self, "_trailer_origin", "") == "movie" and getattr(self, "_is_playing_trailer", False)):
                self.movie_details_view._update_video_geometry()
            if getattr(self, "_is_playing_series_in_details", False) or (getattr(self, "_trailer_origin", "") == "series" and getattr(self, "_is_playing_trailer", False)):
                self.series_details_view._update_video_geometry()
            if self.video_widget.controls.has_active_media and not getattr(self.video_widget.controls, "is_paused", False):
                self.video_widget.hide_mouse_cursor()
                self.setCursor(Qt.CursorShape.BlankCursor)
            self._resume_osd(delay_ms=180)

            def _unlock_fs():
                self._is_toggling_fullscreen = False
                self._last_fullscreen_toggle_time = time.monotonic()
            QTimer.singleShot(150, _unlock_fs)
        else:
            self._exit_fullscreen()

    def _exit_fullscreen(self):
        is_actually_fs = bool(getattr(self, "is_fullscreen", False) or self.isFullScreen())
        if not is_actually_fs:
            return

        self._suspend_osd()
        self.is_fullscreen = False
        self.settings.window_fullscreen = False

        was_max = getattr(self, "_was_maximized_before_fullscreen", False)

        self._freeze_ui()

        self.splitter.setHandleWidth(8)
        self.splitter.setStyleSheet("""
            QSplitter { background-color: #1b2232; }
            QSplitter::handle:horizontal {
                background-color: transparent;
                border-left: 1px solid #28334a;
                border-right: 1px solid #141a26;
                margin: 0px 2px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #3b82f6;
                border: none;
                border-radius: 2px;
            }
            QSplitter::handle:horizontal:pressed {
                background-color: #2563eb;
            }
        """)
        if hasattr(self, "body_widget"):
            self.body_widget.setStyleSheet("#bodyWidget { background-color: #1b2232; }")
        self.content_stack.setStyleSheet("background-color: #1b2232;")
        self.main_content_stack.setStyleSheet("background-color: #111622;")
        self.right_container.setStyleSheet("#rightContainer { background-color: #111622; }")
        self.video_widget.setStyleSheet("background-color: #0f131d;")
        self.video_widget.stack.setStyleSheet("background-color: #0f131d;")
        if hasattr(self, "video_widget") and hasattr(self.video_widget, "controls"):
            self.video_widget.controls.hide()
            self.video_widget.controls.hide_bars()
            self.video_widget.set_fullscreen(False)
            self.video_widget.show_mouse_cursor()
        self.unsetCursor()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if getattr(self, "_is_playing_movie_in_details", False) or (getattr(self, "_is_playing_trailer", False) and getattr(self, "_trailer_origin", "") == "movie"):
            self.movie_details_view.set_fullscreen(False)
        if getattr(self, "_is_playing_series_in_details", False) or (getattr(self, "_is_playing_trailer", False) and getattr(self, "_trailer_origin", "") == "series"):
            self.series_details_view.set_fullscreen(False)

        self.title_bar.show()
        self.sidebar.show()

        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        # 1. Purger impérativement le mode plein écran sous Windows
        self.showNormal()
        self.setWindowState(Qt.WindowState.WindowNoState)
        QApplication.processEvents()

        if was_max:
            self.central_widget.setStyleSheet("#centralWidget { background-color: #1b2232; border: none; }")
            self.showMaximized()
            self.setVisible(True)
            self.raise_()
            self.activateWindow()
            self.settings.window_maximized = True
            self.title_bar.set_maximized_icon(True)
            target_w = avail.width()
        else:
            self.central_widget.setStyleSheet("#centralWidget { background-color: #1b2232; border: 1px solid #334155; }")
            self.settings.window_maximized = False
            self.title_bar.set_maximized_icon(False)

            target_geom = None
            if (
                hasattr(self, "_saved_window_geom")
                and self._saved_window_geom.isValid()
                and self._saved_window_geom.width() >= 980
                and self._saved_window_geom.height() >= 600
                and not (self._saved_window_geom.width() >= avail.width() - 15 and self._saved_window_geom.height() >= avail.height() - 15)
            ):
                gx = max(avail.x(), min(self._saved_window_geom.x(), avail.right() - self._saved_window_geom.width()))
                gy = max(avail.y(), min(self._saved_window_geom.y(), avail.bottom() - self._saved_window_geom.height()))
                target_geom = QRect(gx, gy, self._saved_window_geom.width(), self._saved_window_geom.height())

            if target_geom is None:
                norm_x, norm_y, norm_w, norm_h = self._get_safe_normal_geometry()
                target_geom = QRect(norm_x, norm_y, norm_w, norm_h)
                self._saved_window_geom = target_geom

            self.resize(target_geom.width(), target_geom.height())
            self.move(target_geom.x(), target_geom.y())
            self.setVisible(True)
            self.raise_()
            self.activateWindow()

            self.settings.window_x = target_geom.x()
            self.settings.window_y = target_geom.y()
            self.settings.window_width = target_geom.width()
            self.settings.window_height = target_geom.height()
            target_w = target_geom.width()

        if hasattr(self, "size_grip"):
            self.size_grip.setVisible(not was_max)
            if not was_max:
                self.size_grip.raise_()

        self._apply_layout_geometry(target_width=target_w)
        self._update_details_video_geometry()

        QTimer.singleShot(50, lambda: self._apply_layout_geometry())
        QTimer.singleShot(60, self._unfreeze_ui)
        QTimer.singleShot(100, self._refresh_chrome)
        QTimer.singleShot(120, self._update_details_video_geometry)
        QTimer.singleShot(200, self._refresh_chrome)
        QTimer.singleShot(220, self._update_details_video_geometry)

        self._schedule_save_settings(2000)

        self._resume_osd(delay_ms=180)

        def _unlock_fs():
            self._is_toggling_fullscreen = False
            self._last_fullscreen_toggle_time = time.monotonic()
        QTimer.singleShot(150, _unlock_fs)


    # ------------------ GESTION GLOBALE DES ÉVÉNEMENTS & REDIMENSIONNEMENT ------------------

    def eventFilter(self, watched, event: QEvent) -> bool:
        if not hasattr(self, "is_fullscreen") or not hasattr(self, "settings"):
            return super().eventFilter(watched, event)

        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        is_physically_max = bool(self.isMaximized() or (self.width() >= avail.width() - 15 and self.height() >= avail.height() - 15))

        if self.is_fullscreen or self.isFullScreen() or is_physically_max:
            if getattr(self, "_cursor_overridden", False):
                self._set_resize_cursor(None)
            return super().eventFilter(watched, event)

        etype = event.type()

        if etype == QEvent.Type.MouseMove:
            if getattr(self, "_drag_edge", None) and event.buttons() & Qt.MouseButton.LeftButton:
                delta = event.globalPosition().toPoint() - self._drag_start_pos
                geom = QRect(self._drag_start_geometry)
                min_w = self.minimumWidth()
                min_h = self.minimumHeight()

                if "left" in self._drag_edge:
                    new_left = min(geom.right() - min_w, geom.left() + delta.x())
                    geom.setLeft(new_left)
                if "right" in self._drag_edge:
                    new_right = max(geom.left() + min_w, geom.right() + delta.x())
                    geom.setRight(new_right)
                if "top" in self._drag_edge:
                    new_top = min(geom.bottom() - min_h, geom.top() + delta.y())
                    geom.setTop(new_top)
                if "bottom" in self._drag_edge:
                    new_bottom = max(geom.top() + min_h, geom.bottom() + delta.y())
                    geom.setBottom(new_bottom)

                self.setGeometry(geom)
                if hasattr(self, "movie_details_view"):
                    self.movie_details_view._update_video_geometry()
                if hasattr(self, "series_details_view"):
                    self.series_details_view._update_video_geometry()
                return True
            else:
                global_pos = event.globalPosition().toPoint()
                if hasattr(self, "title_bar") and self.title_bar.isVisible():
                    tb_geo = QRect(self.title_bar.mapToGlobal(QPoint(0, 0)), self.title_bar.size())
                    if tb_geo.contains(global_pos):
                        if getattr(self, "_cursor_overridden", False):
                            self._set_resize_cursor(None)
                        return super().eventFilter(watched, event)

                local_pos = self.mapFromGlobal(global_pos)
                if self.rect().contains(local_pos):
                    edge = self._get_resize_edge(local_pos)
                    if edge:
                        self._set_resize_cursor(edge)
                    elif getattr(self, "_cursor_overridden", False):
                        self._set_resize_cursor(None)
                elif getattr(self, "_cursor_overridden", False):
                    self._set_resize_cursor(None)

        elif etype == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                global_pos = event.globalPosition().toPoint()
                if hasattr(self, "title_bar") and self.title_bar.isVisible():
                    tb_geo = QRect(self.title_bar.mapToGlobal(QPoint(0, 0)), self.title_bar.size())
                    if tb_geo.contains(global_pos):
                        return super().eventFilter(watched, event)

                local_pos = self.mapFromGlobal(global_pos)
                if self.rect().contains(local_pos):
                    edge = self._get_resize_edge(local_pos)
                    if edge:
                        self._suspend_osd()
                        self._drag_edge = edge
                        self._drag_start_pos = global_pos
                        self._drag_start_geometry = self.geometry()
                        return True

        elif etype == QEvent.Type.MouseButtonRelease:
            if getattr(self, "_drag_edge", None) and event.button() == Qt.MouseButton.LeftButton:
                self._drag_edge = None
                self._set_resize_cursor(None)
                x, y, w, h = self.x(), self.y(), self.width(), self.height()
                if w >= 980 and h >= 600:
                    self.settings.window_x = x
                    self.settings.window_y = y
                    self.settings.window_width = w
                    self.settings.window_height = h
                    self._saved_window_geom = QRect(x, y, w, h)
                    self._schedule_save_settings(1500)
                self._resume_osd(delay_ms=120)
                return True

        return super().eventFilter(watched, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        is_physically_max = bool(self.isMaximized() or (self.width() >= avail.width() - 15 and self.height() >= avail.height() - 15))

        if (
            hasattr(self, "is_fullscreen")
            and hasattr(self, "settings")
            and not self.is_fullscreen
            and not self.isFullScreen()
            and not is_physically_max
            and not self.isMinimized()
            and self.isVisible()
        ):
            x, y = self.x(), self.y()
            if x > -10000 and y > -10000:
                self.settings.window_x = x
                self.settings.window_y = y
                if hasattr(self, "_saved_window_geom") and self._saved_window_geom.isValid():
                    self._saved_window_geom.moveTo(x, y)
                self._schedule_save_settings(1500)
        if hasattr(self, "video_widget"):
            self.video_widget._sync_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sidebar"):
            self.sidebar.update()
            for btn in self.sidebar.findChildren(QPushButton):
                btn.update()
        if hasattr(self, "size_grip"):
            self.size_grip.move(self.width() - 20, self.height() - 20)
            self.size_grip.raise_()

        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        is_physically_max = bool(self.isMaximized() or (self.width() >= avail.width() - 15 and self.height() >= avail.height() - 15))

        if (
            hasattr(self, "is_fullscreen")
            and hasattr(self, "settings")
            and not self.is_fullscreen
            and not self.isFullScreen()
            and not is_physically_max
            and not self.isMinimized()
            and self.isVisible()
        ):
            w, h = self.width(), self.height()
            if w >= 980 and h >= 600:
                self.settings.window_width = w
                self.settings.window_height = h
                if hasattr(self, "_saved_window_geom"):
                    self._saved_window_geom = QRect(self.x(), self.y(), w, h)
                self._schedule_save_settings(1500)
        if (
            hasattr(self, "is_fullscreen")
            and not self.is_fullscreen
            and not self.isFullScreen()
            and self.content_stack.currentIndex() == 0
            and hasattr(self, "splitter")
            and self.splitter.isVisible()
        ):
            self._apply_layout_geometry()

        self._update_video_widget_geometry()
        self._update_details_video_geometry()

    def _get_resize_edge(self, pos: QPoint) -> Optional[str]:
        m = self._edge_margin
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()

        edges = []
        if x < m:
            edges.append("left")
        elif x > w - m:
            edges.append("right")
        if y < m:
            edges.append("top")
        elif y > h - m:
            edges.append("bottom")

        return "-".join(edges) if edges else None

    def _set_resize_cursor(self, edge: Optional[str]):
        if not edge:
            if getattr(self, "_cursor_overridden", False):
                QApplication.restoreOverrideCursor()
                self._cursor_overridden = False
        else:
            shape = None
            if edge in ("top-left", "bottom-right"):
                shape = Qt.CursorShape.SizeFDiagCursor
            elif edge in ("top-right", "bottom-left"):
                shape = Qt.CursorShape.SizeBDiagCursor
            elif edge in ("left", "right"):
                shape = Qt.CursorShape.SizeHorCursor
            elif edge in ("top", "bottom"):
                shape = Qt.CursorShape.SizeVerCursor

            if shape:
                if not getattr(self, "_cursor_overridden", False):
                    QApplication.setOverrideCursor(QCursor(shape))
                    self._cursor_overridden = True
                else:
                    QApplication.changeOverrideCursor(QCursor(shape))

    # ------------------ DIALOGUES ------------------

    def _show_add_playlist_dialog(self):
        dlg = AddPlaylistDialog(self.db, parent=self)
        dlg.playlist_added.connect(self._on_playlist_added)
        dlg.exec()

    def _on_playlist_added(self, playlist_id: int):
        self.refresh_playlists_combo(select_playlist_id=playlist_id)
        self._apply_current_section(playlist_id)

    def _show_manage_playlists_dialog(self):
        playing_pl_id = None
        if self.current_channel and getattr(self.player_controller, "is_playing", False):
            playing_pl_id = self.current_channel.playlist_id
        dlg = ManagePlaylistsDialog(self.db, currently_playing_playlist_id=playing_pl_id, parent=self)
        dlg.playlists_modified.connect(self._on_playlists_modified)
        dlg.exec()

    def _on_playlists_modified(self):
        self.refresh_playlists_combo()
        pl_id = self.get_selected_playlist_id()
        self._refresh_active_views_data(pl_id)

    def _show_epg_dialog(self, channel: Channel):
        dlg = EPGDialog(channel, self.db, parent=self)
        dlg.exec()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_layout_geometry)

    def _apply_layout_geometry(self, target_width: Optional[int] = None):
        cat_w = max(160, self.settings.category_panel_width or 280)
        ch_w = max(200, self.settings.channel_list_width or 360)
        collapsed = self.settings.categories_collapsed
        w = target_width if (target_width and target_width > 0) else self.width()
        total_w = w - (self.sidebar.width() or 56)

        # 1. Si on est sur une vue dédiée hors splitter (paramètres, favoris, dashboard, récents, epg)
        if self.content_stack.currentIndex() != 0:
            self.categories_panel.hide()
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            return

        # 1. Protection absolue : en VOD, Séries ou Replay, la liste des chaînes TV (channel_panel) est TOUJOURS masquée
        if self.current_section in ("vod", "series", "replay") or getattr(self, "_return_target_index", None) in (2, 3, 4, 7):
            self.channel_panel.hide()

        # 2. Si une vidéo VOD, Série ou Replay est en cours de lecture dans le conteneur principal (main_content_stack index 0)
        is_vod_series_playback = (
            self.main_content_stack.currentIndex() == 0
            and (self.current_section in ("vod", "series", "replay") or (self.current_channel is not None and self.current_channel.stream_type in ("series", "movie", "vod", "replay")))
        )
        if is_vod_series_playback:
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            self.categories_panel.hide()
            self.splitter.setSizes([0, 0, max(200, total_w)])
            self._update_video_widget_geometry()
            return

        # 3. Si on est sur la fiche détaillée d'une série (SeriesDetailsView, index 3) ou d'un film (MovieDetailsView, index 4)
        # Le panneau catégories (Séries ou Films) est affiché à gauche (si non replié), channel_panel masqué
        if self.main_content_stack.currentIndex() in (3, 4):
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            if collapsed:
                self.categories_panel.hide()
                self.splitter.setSizes([0, 0, max(200, total_w)])
            else:
                self.categories_panel.show()
                details_w = max(200, total_w - cat_w)
                self.splitter.setSizes([cat_w, 0, details_w])
            self._update_details_video_geometry()
            return

        # 5. Si on est sur les galeries VOD ou Séries (grilles d'affiches, index 1 ou 2)
        if self.current_section in ("vod", "series") or self.main_content_stack.currentIndex() in (1, 2):
            self.channel_panel.hide()
            if hasattr(self, "epg_timeline_panel"):
                self.epg_timeline_panel.hide()
            if collapsed:
                self.categories_panel.hide()
                self.splitter.setSizes([0, 0, max(200, total_w)])
            else:
                self.categories_panel.show()
                vod_w = max(200, total_w - cat_w)
                self.splitter.setSizes([cat_w, 0, vod_w])
            return

        # 6. Live TV (section "live" ou mode chaîne en direct)
        self.channel_panel.set_categories_collapsed(collapsed)
        self.channel_panel.show()
        if hasattr(self, "epg_timeline_panel"):
            self.epg_timeline_panel.setVisible(self.settings.epg_panel_visible)

        if collapsed:
            self.categories_panel.hide()
            video_w = max(200, total_w - ch_w)
            self.splitter.setSizes([0, ch_w, video_w])
        else:
            self.categories_panel.show()
            video_w = max(200, total_w - cat_w - ch_w)
            self.splitter.setSizes([cat_w, ch_w, video_w])
        self._update_video_widget_geometry()

    def _update_details_video_geometry(self):
        """Met à jour la géométrie vidéo et synchronise l'OSD pour la fiche série ou film."""
        if hasattr(self, "main_content_stack") and self.main_content_stack.currentIndex() == 3:
            if hasattr(self, "series_details_view"):
                self.series_details_view._update_video_geometry()
        elif hasattr(self, "main_content_stack") and self.main_content_stack.currentIndex() == 4:
            if hasattr(self, "movie_details_view") and hasattr(self.movie_details_view, "_update_video_geometry"):
                self.movie_details_view._update_video_geometry()
        if hasattr(self, "video_widget") and self.video_widget and self.video_widget.isVisible():
            self.video_widget._sync_geometry()

    def _update_video_widget_geometry(self):
        """Gère la géométrie de base du lecteur vidéo principal ou synchronise la fiche active."""
        if hasattr(self, "main_content_stack") and self.main_content_stack.currentIndex() == 3:
            self._update_details_video_geometry()
            return
        if hasattr(self, "video_widget") and self.video_widget:
            self.video_widget.setMinimumHeight(0)
            self.video_widget.setMaximumHeight(16777215)
            self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.video_widget._sync_geometry()

    def changeEvent(self, event):
        etype = event.type()
        if etype == QEvent.Type.ActivationChange:
            self._refresh_chrome()
            if self.isMinimized() or not self.isActiveWindow():
                if hasattr(self, "video_widget") and hasattr(self.video_widget, "controls"):
                    self.video_widget.controls.hide()
            elif self.content_stack.currentIndex() == 0 and hasattr(self, "video_widget") and hasattr(self.video_widget, "controls"):
                self.video_widget._sync_geometry()

        elif etype == QEvent.Type.WindowStateChange:
            # Synchronisation stricte de l'état plein écran interne si l'OS a modifié l'état de la fenêtre
            if not self.isFullScreen() and getattr(self, "is_fullscreen", False):
                self.is_fullscreen = False
                self.settings.window_fullscreen = False
            elif self.isFullScreen() and not getattr(self, "is_fullscreen", False):
                self.is_fullscreen = True
                self.settings.window_fullscreen = True

            screen = self.screen() or QApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
            is_physically_max = bool(self.isMaximized() or (self.width() >= avail.width() - 15 and self.height() >= avail.height() - 15))

            if hasattr(self, "title_bar"):
                self.title_bar.set_maximized_icon(is_physically_max)
            if hasattr(self, "size_grip"):
                self.size_grip.setVisible(not is_physically_max and not self.is_fullscreen and not self.isFullScreen())
                if not is_physically_max and not self.is_fullscreen and not self.isFullScreen():
                    self.size_grip.raise_()
            if self.isMinimized():
                if hasattr(self, "video_widget") and hasattr(self.video_widget, "controls"):
                    self.video_widget.controls.hide()
            if hasattr(self, "central_widget"):
                if self.isFullScreen() or getattr(self, "is_fullscreen", False):
                    self.central_widget.setStyleSheet("#centralWidget { background-color: #000000; border: none; margin: 0; padding: 0; }")
                elif is_physically_max:
                    self.central_widget.setStyleSheet("#centralWidget { background-color: #1b2232; border: none; }")
                elif not self.isMinimized():
                    self.central_widget.setStyleSheet("#centralWidget { background-color: #1b2232; border: 1px solid #334155; }")
            self._update_details_video_geometry()
            QTimer.singleShot(60, self._update_details_video_geometry)
            QTimer.singleShot(150, self._update_details_video_geometry)
            QTimer.singleShot(250, self._update_details_video_geometry)
            self._unfreeze_ui()
            self._refresh_chrome()
            QTimer.singleShot(60, self._refresh_chrome)
            QTimer.singleShot(150, self._refresh_chrome)
            self.update()

        super().changeEvent(event)


    def _on_splitter_moved(self, _pos: int, _index: int):
        sizes = self.splitter.sizes()
        if len(sizes) == 3:
            if not self.settings.categories_collapsed and sizes[0] >= 160:
                self.settings.category_panel_width = sizes[0]
            if self.current_section not in ("vod", "series") and sizes[1] >= 200:
                self.settings.channel_list_width = sizes[1]

            self.db.update_panel_widths(
                category_w=self.settings.category_panel_width,
                channel_w=self.settings.channel_list_width,
                collapsed=self.settings.categories_collapsed
            )
        self._update_video_widget_geometry()
        self._update_details_video_geometry()

    def _toggle_categories_panel(self):
        is_visible = self.categories_panel.isVisible()
        cat_w = max(160, self.settings.category_panel_width or 280)
        ch_w = max(200, self.settings.channel_list_width or 360)

        total_sizes = self.splitter.sizes()
        total_w = sum(total_sizes) if (total_sizes and sum(total_sizes) > 0) else (self.width() - (self.sidebar.width() or 56))

        if is_visible:
            # On replie le panneau des catégories
            self.settings.categories_collapsed = True
            self.categories_panel.setVisible(False)
            self.channel_panel.set_categories_collapsed(True)
            if self.current_section in ("vod", "series"):
                self.splitter.setSizes([0, 0, max(200, total_w)])
            else:
                video_w = max(200, total_w - ch_w)
                self.splitter.setSizes([0, ch_w, video_w])
        else:
            # On redéploie le panneau des catégories
            self.settings.categories_collapsed = False
            self.categories_panel.setVisible(True)
            self.channel_panel.set_categories_collapsed(False)
            if self.current_section in ("vod", "series"):
                vod_w = max(200, total_w - cat_w)
                self.splitter.setSizes([cat_w, 0, vod_w])
            else:
                video_w = max(200, total_w - cat_w - ch_w)
                self.splitter.setSizes([cat_w, ch_w, video_w])

        self.db.update_panel_widths(
            category_w=cat_w,
            channel_w=ch_w,
            collapsed=self.settings.categories_collapsed
        )

    def closeEvent(self, event):
        # 1. Mémorisation précise de l'état (Plein écran vs Maximisé vs Fenêtré/Réduit) et de la géométrie AVANT TOUT MASQUAGE
        is_fs = getattr(self, "is_fullscreen", False) or self.isFullScreen()
        is_max = self.isMaximized()
        is_min = self.isMinimized()

        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        if is_fs:
            # Réouverture en plein écran, tout en conservant la position réduite enregistrée pour basculer
            self.settings.window_fullscreen = True
            self.settings.window_maximized = False
            if hasattr(self, "_saved_window_geom") and self._saved_window_geom.isValid():
                if self._saved_window_geom.x() > -10000 and self._saved_window_geom.y() > -10000:
                    sg_w, sg_h = self._saved_window_geom.width(), self._saved_window_geom.height()
                    if sg_w >= 980 and sg_h >= 620 and not (sg_w >= avail.width() - 15 and sg_h >= avail.height() - 15):
                        self.settings.window_x = self._saved_window_geom.x()
                        self.settings.window_y = self._saved_window_geom.y()
                        self.settings.window_width = sg_w
                        self.settings.window_height = sg_h
        elif is_max or (self.width() >= avail.width() - 15 and self.height() >= avail.height() - 15):
            self.settings.window_fullscreen = False
            self.settings.window_maximized = True
            if (
                hasattr(self, "_saved_window_geom")
                and self._saved_window_geom.isValid()
                and self._saved_window_geom.width() >= 980
                and self._saved_window_geom.height() >= 600
                and not (self._saved_window_geom.width() >= avail.width() - 15 and self._saved_window_geom.height() >= avail.height() - 15)
            ):
                self.settings.window_x = self._saved_window_geom.x()
                self.settings.window_y = self._saved_window_geom.y()
                self.settings.window_width = self._saved_window_geom.width()
                self.settings.window_height = self._saved_window_geom.height()
            else:
                norm_geo = self.normalGeometry()
                if (
                    norm_geo.isValid()
                    and norm_geo.x() > -10000
                    and norm_geo.y() > -10000
                    and norm_geo.width() >= 980
                    and not (norm_geo.width() >= avail.width() - 15 and norm_geo.height() >= avail.height() - 15)
                ):
                    self.settings.window_x = norm_geo.x()
                    self.settings.window_y = norm_geo.y()
                    self.settings.window_width = norm_geo.width()
                    self.settings.window_height = norm_geo.height()
                else:
                    norm_x, norm_y, norm_w, norm_h = self._get_safe_normal_geometry()
                    self.settings.window_x = norm_x
                    self.settings.window_y = norm_y
                    self.settings.window_width = norm_w
                    self.settings.window_height = norm_h
        elif is_min:
            self.settings.window_fullscreen = False
            norm_geo = self.normalGeometry()
            if (
                norm_geo.isValid()
                and norm_geo.x() > -10000
                and norm_geo.y() > -10000
                and norm_geo.width() >= 980
                and not (norm_geo.width() >= avail.width() - 15 and norm_geo.height() >= avail.height() - 15)
            ):
                self.settings.window_x = norm_geo.x()
                self.settings.window_y = norm_geo.y()
                self.settings.window_width = norm_geo.width()
                self.settings.window_height = norm_geo.height()
        else:
            self.settings.window_fullscreen = False
            self.settings.window_maximized = False
            curr_x, curr_y = self.x(), self.y()
            curr_w, curr_h = self.width(), self.height()
            if (
                curr_x > -10000
                and curr_y > -10000
                and curr_w >= 980
                and curr_h >= 600
                and not (curr_w >= avail.width() - 15 and curr_h >= avail.height() - 15)
            ):
                self.settings.window_x = curr_x
                self.settings.window_y = curr_y
                self.settings.window_width = curr_w
                self.settings.window_height = curr_h

        # 2. Sauvegarde des largeurs du splitter
        if self.content_stack.currentIndex() == 0 and self.splitter.isVisible() and not is_fs:
            sizes = self.splitter.sizes()
            if len(sizes) == 3:
                if not self.settings.categories_collapsed and sizes[0] >= 160:
                    self.settings.category_panel_width = sizes[0]
                if self.current_section not in ("vod", "series") and sizes[1] >= 200:
                    self.settings.channel_list_width = sizes[1]

        # 3. Sauvegarde du panneau EPG
        if hasattr(self, "epg_timeline_panel"):
            self.settings.epg_panel_visible = not self.epg_timeline_panel.is_collapsed
            if not self.epg_timeline_panel.is_collapsed and self.epg_timeline_panel.height() > 50:
                self.settings.epg_panel_height = self.epg_timeline_panel.height()

        # 4. Sauvegarde du volume actuel
        if hasattr(self, "video_widget") and hasattr(self.video_widget, "controls"):
            vol = self.video_widget.controls.volume_slider.value()
            if vol >= 0:
                self.settings.volume = vol
                self.db.update_volume(vol)

        # 5. Sauvegarde de la position de lecture en cours
        if getattr(self, "_is_playing_movie_in_details", False):
            self._stop_movie_details_playback()
        if getattr(self, "_is_playing_series_in_details", False):
            self._stop_series_details_playback()
        self._save_current_playback_progress()

        # 6. Sauvegarde définitive dans la base de données
        self.db.save_settings(self.settings)

        # 7. Destruction propre de l'OSD et fermeture
        if hasattr(self, "video_widget") and hasattr(self.video_widget, "controls"):
            controls = self.video_widget.controls
            controls.hide_bars()
            controls.hide()
            controls.close()
            controls.deleteLater()
            if hasattr(self.video_widget, "osd_timer"):
                self.video_widget.osd_timer.stop()

        if hasattr(self, "vod_grid_view") and hasattr(self.vod_grid_view, "stop_workers"):
            self.vod_grid_view.stop_workers()
        if hasattr(self, "series_grid_view") and hasattr(self.series_grid_view, "stop_workers"):
            self.series_grid_view.stop_workers()
        if hasattr(self, "series_details_view") and hasattr(self.series_details_view, "stop_workers"):
            self.series_details_view.stop_workers()

        self.hide()
        QApplication.processEvents()

        self.player_controller.cleanup()
        event.accept()

    def retranslate_ui(self):
        """Met à jour l'ensemble des textes de l'interface en temps réel lors d'un changement de langue."""
        self.setWindowTitle("IPTV Hub — " + tr("IPTV Hub"))

        if hasattr(self, "title_bar") and hasattr(self.title_bar, "retranslate_ui"):
            self.title_bar.retranslate_ui()

        if hasattr(self, "sidebar") and hasattr(self.sidebar, "retranslate_ui"):
            self.sidebar.retranslate_ui()

        if hasattr(self, "categories_panel") and hasattr(self.categories_panel, "retranslate_ui"):
            self.categories_panel.retranslate_ui()

        if hasattr(self, "channel_panel") and hasattr(self.channel_panel, "retranslate_ui"):
            self.channel_panel.retranslate_ui()
        elif hasattr(self, "channel_list_panel") and hasattr(self.channel_list_panel, "retranslate_ui"):
            self.channel_list_panel.retranslate_ui()

        if hasattr(self, "settings_view") and hasattr(self.settings_view, "retranslate_ui"):
            self.settings_view.retranslate_ui()

        if hasattr(self, "vod_grid_view") and hasattr(self.vod_grid_view, "retranslate_ui"):
            self.vod_grid_view.retranslate_ui()

        if hasattr(self, "series_grid_view") and hasattr(self.series_grid_view, "retranslate_ui"):
            self.series_grid_view.retranslate_ui()

        if hasattr(self, "dashboard_view") and hasattr(self.dashboard_view, "retranslate_ui"):
            self.dashboard_view.retranslate_ui()

        if hasattr(self, "epg_grid_view") and hasattr(self.epg_grid_view, "retranslate_ui"):
            self.epg_grid_view.retranslate_ui()

        if hasattr(self, "replay_view") and hasattr(self.replay_view, "retranslate_ui"):
            self.replay_view.retranslate_ui()

        if hasattr(self, "epg_timeline_panel") and hasattr(self.epg_timeline_panel, "retranslate_ui"):
            self.epg_timeline_panel.retranslate_ui()

        if hasattr(self, "favorites_view") and hasattr(self.favorites_view, "retranslate_ui"):
            self.favorites_view.retranslate_ui()

        if hasattr(self, "history_view") and hasattr(self.history_view, "retranslate_ui"):
            self.history_view.retranslate_ui()

        if hasattr(self, "recently_added_view") and hasattr(self.recently_added_view, "retranslate_ui"):
            self.recently_added_view.retranslate_ui()

        if hasattr(self, "player_controls") and hasattr(self.player_controls, "retranslate_ui"):
            self.player_controls.retranslate_ui()

        if hasattr(self, "movie_details_view") and hasattr(self.movie_details_view, "retranslate_ui"):
            self.movie_details_view.retranslate_ui()

        if hasattr(self, "series_details_view") and hasattr(self.series_details_view, "retranslate_ui"):
            self.series_details_view.retranslate_ui()

        self.refresh_playlists_combo()
        self._update_search_placeholder(self.current_section)

