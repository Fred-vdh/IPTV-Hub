"""
Vue intégrée des Paramètres pour IPTV Hub.
Barre de sous-menus latérale à gauche et formulaires de configuration centrés à droite.
"""

from typing import Optional
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QButtonGroup, QFrame, QComboBox,
    QLineEdit, QSpinBox, QCheckBox, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from core.database import Database
from core.models import AppSettings
from core.download_manager import get_default_download_dir
from core.version import __version__
from core.sync_manager import (
    export_config_to_file,
    import_config_from_file,
)
from core.auto_sync_manager import format_last_sync
from core.i18n import tr, I18nManager
from ui.icons import get_icon, DEFAULT_ICON_COLOR


class SettingsView(QWidget):
    settings_saved = pyqtSignal()
    close_requested = pyqtSignal()
    manual_sync_requested = pyqtSignal(str)
    qr_sync_requested = pyqtSignal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.settings: AppSettings = self.db.get_settings()
        self.setObjectName("settingsView")
        self._cards = []
        self._current_playlist_id: Optional[int] = None

        self._init_ui()
        self._load_values()

        I18nManager.instance().language_changed.connect(self._on_language_changed)

    def _on_language_changed(self, _=None):
        try:
            self.retranslate_ui()
        except (RuntimeError, Exception):
            pass

    def closeEvent(self, event):
        try:
            I18nManager.instance().language_changed.disconnect(self._on_language_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # =========================================================================
        # 1. COLONNE DE GAUCHE : BARRE DE SOUS-MENUS "PARAMÈTRES"
        # =========================================================================
        nav_panel = QWidget()
        nav_panel.setObjectName("settingsNavPanel")
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(0, 0, 0, 16)
        nav_layout.setSpacing(4)

        # En-tête "Paramètres"
        title_row = QHBoxLayout()
        title_row.setContentsMargins(18, 16, 18, 14)
        title_row.setSpacing(8)

        self.nav_title = QLabel(tr("Paramètres"))
        self.nav_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        title_row.addWidget(self.nav_title)
        title_row.addStretch()

        nav_layout.addLayout(title_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #20293d; margin: 0px 14px 8px 14px;")
        nav_layout.addWidget(sep)

        # Boutons de sous-menus
        self.nav_btn_group = QButtonGroup(self)
        self.nav_btn_group.setExclusive(True)

        self.btn_general = self._create_nav_btn(tr("Général & Interface"), "tune", 0, checked=True)
        self.btn_player = self._create_nav_btn(tr("Lecteur Vidéo"), "videocam", 1)
        self.btn_network = self._create_nav_btn(tr("Réseau & Flux"), "wifi", 2)
        self.btn_epg = self._create_nav_btn(tr("Synchronisation & EPG"), "sync", 3)
        self.btn_storage = self._create_nav_btn(tr("Données & Stockage"), "storage", 4)
        self.btn_backup = self._create_nav_btn(tr("Sauvegarde & Fichiers"), "content_copy", 5)
        self.btn_about = self._create_nav_btn(tr("À propos"), "info", 6)

        for b in [self.btn_general, self.btn_player, self.btn_network, self.btn_epg, self.btn_storage, self.btn_backup, self.btn_about]:
            nav_layout.addWidget(b)

        nav_layout.addStretch()

        # Bouton fermer/retour
        self.close_btn = QPushButton("  " + tr("Fermer les paramètres"))
        self.close_btn.setIcon(get_icon("close", color=DEFAULT_ICON_COLOR))
        self.close_btn.setIconSize(QSize(16, 16))
        self.close_btn.setProperty("class", "secondary-btn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("margin: 8px 14px;")
        self.close_btn.clicked.connect(self.close_requested.emit)
        nav_layout.addWidget(self.close_btn)

        root_layout.addWidget(nav_panel)

        # =========================================================================
        # 2. ZONE CENTRALE : CONTENU DES PAGES CENTRÉ
        # =========================================================================
        content_area = QWidget()
        content_area.setObjectName("settingsContentArea")
        content_layout = QHBoxLayout(content_area)
        content_layout.setContentsMargins(30, 24, 30, 24)

        content_layout.addStretch(1)

        # Conteneur centré avec largeur maximale contrôlée (680px)
        center_card_container = QWidget()
        center_card_container.setMinimumWidth(540)
        center_card_container.setMaximumWidth(720)
        center_vlayout = QVBoxLayout(center_card_container)
        center_vlayout.setContentsMargins(0, 0, 0, 0)
        center_vlayout.setSpacing(16)

        # Stack de pages
        self.stack = QStackedWidget()

        self.page_general = self._build_general_page()
        self.page_player = self._build_player_page()
        self.page_network = self._build_network_page()
        self.page_epg = self._build_epg_page()
        self.page_storage = self._build_storage_page()
        self.page_backup = self._build_backup_page()
        self.page_about = self._build_about_page()

        self.stack.addWidget(self.page_general)
        self.stack.addWidget(self.page_player)
        self.stack.addWidget(self.page_network)
        self.stack.addWidget(self.page_epg)
        self.stack.addWidget(self.page_storage)
        self.stack.addWidget(self.page_backup)
        self.stack.addWidget(self.page_about)

        center_vlayout.addWidget(self.stack, stretch=1)

        # Barre d'actions du bas (Sauvegarder)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.save_status = QLabel("")
        self.save_status.setStyleSheet("color: #818cf8; font-weight: 500; font-size: 13px;")
        bottom_row.addWidget(self.save_status)
        bottom_row.addStretch()

        self.save_btn = QPushButton(" " + tr("Enregistrer les paramètres"))
        self.save_btn.setIcon(get_icon("check_circle", color="#ffffff"))
        self.save_btn.setIconSize(QSize(18, 18))
        self.save_btn.setProperty("class", "primary-btn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet("padding: 10px 22px; font-size: 13px;")
        self.save_btn.clicked.connect(self._save_settings)
        bottom_row.addWidget(self.save_btn)

        center_vlayout.addLayout(bottom_row)

        content_layout.addWidget(center_card_container)
        content_layout.addStretch(1)

        root_layout.addWidget(content_area, stretch=1)

    def _create_nav_btn(self, text: str, icon_name: str, page_idx: int, checked: bool = False) -> QPushButton:
        btn = QPushButton(f"  {text}")
        btn.setIcon(get_icon(icon_name, color=DEFAULT_ICON_COLOR, active_color="#ffffff"))
        btn.setIconSize(QSize(20, 20))
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setProperty("class", "settings-nav-btn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nav_btn_group.addButton(btn)

        btn.clicked.connect(lambda: self.stack.setCurrentIndex(page_idx))
        return btn

    # ------------------ PAGES DE CONFIGURATION ------------------

    def _build_card(self, title: str, desc: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setProperty("class", "settings-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        t_lbl = QLabel(tr(title))
        t_lbl.setProperty("class", "settings-card-title")
        layout.addWidget(t_lbl)

        d_lbl = QLabel(tr(desc))
        d_lbl.setProperty("class", "settings-card-desc")
        d_lbl.setWordWrap(True)
        layout.addWidget(d_lbl)

        self._cards.append((t_lbl, d_lbl, title, desc))
        return card, layout

    def _build_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card, c_layout = self._build_card(
            "Général & Apparence",
            "Personnalisez l'affichage, le comportement au démarrage et l'interface utilisateur."
        )

        # Langue de l'application
        r_app_lang = QHBoxLayout()
        self.lbl_app_lang = QLabel(tr("Langue de l'application :"))
        r_app_lang.addWidget(self.lbl_app_lang)
        r_app_lang.addStretch()
        self.app_lang_combo = QComboBox()
        for code, label in I18nManager.SUPPORTED_LANGUAGES.items():
            self.app_lang_combo.addItem(label, code)
        self.app_lang_combo.setFixedWidth(240)
        self.app_lang_combo.currentIndexChanged.connect(self._on_app_lang_changed)
        r_app_lang.addWidget(self.app_lang_combo)
        c_layout.addLayout(r_app_lang)

        # Thème
        r1 = QHBoxLayout()
        self.lbl_theme = QLabel(tr("Thème de l'interface :"))
        r1.addWidget(self.lbl_theme)
        r1.addStretch()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([tr("Gris foncé bleuté (Par défaut)"), tr("Sombre moderne")])
        self.theme_combo.setFixedWidth(240)
        r1.addWidget(self.theme_combo)
        c_layout.addLayout(r1)

        # Langue audio préférée (Films & Séries)
        r_lang = QHBoxLayout()
        self.lbl_audio_lang = QLabel(tr("Langue audio préférée (Films & Séries) :"))
        r_lang.addWidget(self.lbl_audio_lang)
        r_lang.addStretch()
        self.audio_lang_combo = QComboBox()
        self.audio_lang_combo.addItem("Français (France, VFF, VFQ)", "fra,fre,fr,French,Français,francais,VF,VFF,VFQ,TrueFrench")
        self.audio_lang_combo.addItem("Anglais (English / VO)", "eng,en,English,anglais,VO")
        self.audio_lang_combo.addItem("Espagnol (Español / Castellano)", "spa,es,Spanish,Español,espanol")
        self.audio_lang_combo.addItem("Allemand (Deutsch)", "ger,deu,de,German,Deutsch")
        self.audio_lang_combo.addItem("Italien (Italiano)", "ita,it,Italian,Italiano")
        self.audio_lang_combo.addItem("Portugais (Português)", "por,pt,Portuguese,Português")
        self.audio_lang_combo.addItem("Arabe (العربية)", "ara,ar,Arabic,arabe")
        self.audio_lang_combo.addItem("Original / Par défaut (Sans préférence)", "")
        self.audio_lang_combo.setFixedWidth(260)
        r_lang.addWidget(self.audio_lang_combo)
        c_layout.addLayout(r_lang)

        # Masquage auto de l'OSD
        r2 = QHBoxLayout()
        self.lbl_osd = QLabel(tr("Délai de masquage des contrôles vidéo :"))
        r2.addWidget(self.lbl_osd)
        r2.addStretch()
        self.osd_timeout_spin = QSpinBox()
        self.osd_timeout_spin.setRange(1, 10)
        self.osd_timeout_spin.setSuffix(" " + tr("secondes"))
        self.osd_timeout_spin.setValue(4)
        self.osd_timeout_spin.setFixedWidth(140)
        r2.addWidget(self.osd_timeout_spin)
        c_layout.addLayout(r2)

        # Reprise de la dernière chaîne
        self.auto_resume_cb = QCheckBox(" " + tr("Reprendre automatiquement la dernière chaîne au lancement"))
        self.auto_resume_cb.setChecked(True)
        c_layout.addWidget(self.auto_resume_cb)

        # Enchaînement automatique des épisodes de série
        self.auto_play_next_cb = QCheckBox(" " + tr("Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)"))
        self.auto_play_next_cb.setChecked(True)
        c_layout.addWidget(self.auto_play_next_cb)

        # Détection générique de début IntroDB
        self.introdb_intro_cb = QCheckBox(" " + tr("Proposer de passer le générique de début (IntroDB)"))
        self.introdb_intro_cb.setChecked(getattr(self.settings, "introdb_intro_skip", True))
        self.introdb_intro_cb.setStyleSheet("color: #f1f5f9; font-size: 13px;")
        c_layout.addWidget(self.introdb_intro_cb)

        # Détection générique de fin IntroDB
        self.introdb_outro_cb = QCheckBox(" " + tr("Détecter le début du générique de fin pour proposer l'épisode suivant (IntroDB)"))
        self.introdb_outro_cb.setChecked(getattr(self.settings, "introdb_outro_skip", True))
        self.introdb_outro_cb.setStyleSheet("margin-left: 20px; color: #94a3b8; font-size: 12px;")
        self.auto_play_next_cb.toggled.connect(self.introdb_outro_cb.setEnabled)
        c_layout.addWidget(self.introdb_outro_cb)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _populate_deint_combo(self):
        curr_data = self.deint_combo.currentData() if hasattr(self, "deint_combo") and self.deint_combo.count() > 0 else "auto"
        self.deint_combo.blockSignals(True)
        self.deint_combo.clear()
        self.deint_combo.addItem(f"auto ({tr('Recommandé')})", "auto")
        self.deint_combo.addItem(f"yes ({tr('Toujours activé')})", "yes")
        self.deint_combo.addItem(f"no ({tr('Désactivé')})", "no")
        idx = 0
        for i in range(self.deint_combo.count()):
            if self.deint_combo.itemData(i) == curr_data:
                idx = i
                break
        self.deint_combo.setCurrentIndex(idx)
        self.deint_combo.blockSignals(False)

    def _build_player_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card, c_layout = self._build_card(
            "Moteur de Lecture libmpv",
            "Options matérielles de décodage et de fluidité pour les flux HD/4K."
        )

        # Décodage matériel
        r1 = QHBoxLayout()
        self.lbl_hwdec = QLabel(tr("Décodage matériel (HW Accel) :"))
        r1.addWidget(self.lbl_hwdec)
        r1.addStretch()
        self.hwdec_combo = QComboBox()
        self.hwdec_combo.addItems(["auto", "d3d11va (Windows DirectX)", "nvdec (NVIDIA)", "dxva2", "no (CPU)"])
        self.hwdec_combo.setFixedWidth(240)
        r1.addWidget(self.hwdec_combo)
        c_layout.addLayout(r1)

        # Désentrelacement
        r2 = QHBoxLayout()
        self.lbl_deint = QLabel(tr("Désentrelacement vidéo :"))
        r2.addWidget(self.lbl_deint)
        r2.addStretch()
        self.deint_combo = QComboBox()
        self.deint_combo.setFixedWidth(240)
        self._populate_deint_combo()
        r2.addWidget(self.deint_combo)
        c_layout.addLayout(r2)

        # Taille du tampon cache
        r3 = QHBoxLayout()
        self.lbl_buffer = QLabel(tr("Taille du cache de préchargement :"))
        r3.addWidget(self.lbl_buffer)
        r3.addStretch()
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(10, 300)
        self.buffer_spin.setSuffix(" " + tr("Mo"))
        self.buffer_spin.setValue(self.settings.buffer_size_mb)
        self.buffer_spin.setFixedWidth(140)
        r3.addWidget(self.buffer_spin)
        c_layout.addLayout(r3)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_network_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card, c_layout = self._build_card(
            "Réseau & Streaming",
            "Paramètres de connexion aux serveurs IPTV et entêtes HTTP."
        )

        # User-Agent personnalisé
        self.lbl_ua = QLabel(tr("User-Agent HTTP par défaut :"))
        c_layout.addWidget(self.lbl_ua)
        self.ua_edit = QLineEdit()
        self.ua_edit.setPlaceholderText(tr("Ex: VLC/3.0.18 LibVLC/3.0.18 ou Mozilla/5.0..."))
        c_layout.addWidget(self.ua_edit)

        # Timeout de connexion
        r2 = QHBoxLayout()
        self.lbl_timeout = QLabel(tr("Délai d'attente réseau (Timeout) :"))
        r2.addWidget(self.lbl_timeout)
        r2.addStretch()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(3, 60)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setValue(getattr(self.settings, "http_timeout", 15))
        self.timeout_spin.setFixedWidth(140)
        r2.addWidget(self.timeout_spin)
        c_layout.addLayout(r2)

        # Reconnexion automatique
        self.auto_reconnect_cb = QCheckBox(" " + tr("Reconnexion automatique en cas de coupure de flux"))
        self.auto_reconnect_cb.setChecked(getattr(self.settings, "auto_reconnect", True))
        c_layout.addWidget(self.auto_reconnect_cb)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_epg_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card, c_layout = self._build_card(
            "Synchronisation automatique & Guide EPG",
            "Planification des rafraîchissements et guide des programmes"
        )

        # 1. Chaînes en direct
        self.sync_live_cb = QCheckBox(" " + tr("Synchroniser automatiquement les chaînes en direct"))
        self.sync_live_cb.setStyleSheet("font-weight: 600; font-size: 13px; color: #f1f5f9;")
        c_layout.addWidget(self.sync_live_cb)

        r_live = QHBoxLayout()
        r_live.setContentsMargins(22, 0, 0, 0)
        self.lbl_sync_live_interval = QLabel(tr("Intervalle d'actualisation :"))
        r_live.addWidget(self.lbl_sync_live_interval)
        r_live.addStretch()
        self.sync_live_spin = QSpinBox()
        self.sync_live_spin.setRange(1, 90)
        self.sync_live_spin.setSuffix(" " + tr("jour(s)"))
        self.sync_live_spin.setFixedWidth(130)
        r_live.addWidget(self.sync_live_spin)
        c_layout.addLayout(r_live)

        r_live_status = QHBoxLayout()
        r_live_status.setContentsMargins(22, 0, 0, 4)
        self.lbl_sync_live_status = QLabel(tr("Dernière synchronisation :") + " --")
        self.lbl_sync_live_status.setStyleSheet("color: #94a3b8; font-size: 12px;")
        r_live_status.addWidget(self.lbl_sync_live_status)
        r_live_status.addStretch()
        self.btn_sync_live = QPushButton(" " + tr("Synchroniser"))
        self.btn_sync_live.setIcon(get_icon("sync", color=DEFAULT_ICON_COLOR))
        self.btn_sync_live.setProperty("class", "secondary-btn")
        self.btn_sync_live.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync_live.setFixedHeight(28)
        self.btn_sync_live.clicked.connect(lambda: self.manual_sync_requested.emit("live"))
        r_live_status.addWidget(self.btn_sync_live)
        c_layout.addLayout(r_live_status)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background-color: #26334d; margin: 4px 0;")
        c_layout.addWidget(sep1)

        # 2. Films VOD
        self.sync_vod_cb = QCheckBox(" " + tr("Synchroniser automatiquement les films"))
        self.sync_vod_cb.setStyleSheet("font-weight: 600; font-size: 13px; color: #f1f5f9;")
        c_layout.addWidget(self.sync_vod_cb)

        r_vod = QHBoxLayout()
        r_vod.setContentsMargins(22, 0, 0, 0)
        self.lbl_sync_vod_interval = QLabel(tr("Intervalle d'actualisation :"))
        r_vod.addWidget(self.lbl_sync_vod_interval)
        r_vod.addStretch()
        self.sync_vod_spin = QSpinBox()
        self.sync_vod_spin.setRange(1, 90)
        self.sync_vod_spin.setSuffix(" " + tr("jour(s)"))
        self.sync_vod_spin.setFixedWidth(130)
        r_vod.addWidget(self.sync_vod_spin)
        c_layout.addLayout(r_vod)

        r_vod_status = QHBoxLayout()
        r_vod_status.setContentsMargins(22, 0, 0, 4)
        self.lbl_sync_vod_status = QLabel(tr("Dernière synchronisation :") + " --")
        self.lbl_sync_vod_status.setStyleSheet("color: #94a3b8; font-size: 12px;")
        r_vod_status.addWidget(self.lbl_sync_vod_status)
        r_vod_status.addStretch()
        self.btn_sync_vod = QPushButton(" " + tr("Synchroniser"))
        self.btn_sync_vod.setIcon(get_icon("sync", color=DEFAULT_ICON_COLOR))
        self.btn_sync_vod.setProperty("class", "secondary-btn")
        self.btn_sync_vod.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync_vod.setFixedHeight(28)
        self.btn_sync_vod.clicked.connect(lambda: self.manual_sync_requested.emit("vod"))
        r_vod_status.addWidget(self.btn_sync_vod)
        c_layout.addLayout(r_vod_status)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #26334d; margin: 4px 0;")
        c_layout.addWidget(sep2)

        # 3. Séries TV
        self.sync_series_cb = QCheckBox(" " + tr("Synchroniser automatiquement les séries"))
        self.sync_series_cb.setStyleSheet("font-weight: 600; font-size: 13px; color: #f1f5f9;")
        c_layout.addWidget(self.sync_series_cb)

        r_series = QHBoxLayout()
        r_series.setContentsMargins(22, 0, 0, 0)
        self.lbl_sync_series_interval = QLabel(tr("Intervalle d'actualisation :"))
        r_series.addWidget(self.lbl_sync_series_interval)
        r_series.addStretch()
        self.sync_series_spin = QSpinBox()
        self.sync_series_spin.setRange(1, 90)
        self.sync_series_spin.setSuffix(" " + tr("jour(s)"))
        self.sync_series_spin.setFixedWidth(130)
        r_series.addWidget(self.sync_series_spin)
        c_layout.addLayout(r_series)

        r_series_status = QHBoxLayout()
        r_series_status.setContentsMargins(22, 0, 0, 4)
        self.lbl_sync_series_status = QLabel(tr("Dernière synchronisation :") + " --")
        self.lbl_sync_series_status.setStyleSheet("color: #94a3b8; font-size: 12px;")
        r_series_status.addWidget(self.lbl_sync_series_status)
        r_series_status.addStretch()
        self.btn_sync_series = QPushButton(" " + tr("Synchroniser"))
        self.btn_sync_series.setIcon(get_icon("sync", color=DEFAULT_ICON_COLOR))
        self.btn_sync_series.setProperty("class", "secondary-btn")
        self.btn_sync_series.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync_series.setFixedHeight(28)
        self.btn_sync_series.clicked.connect(lambda: self.manual_sync_requested.emit("series"))
        r_series_status.addWidget(self.btn_sync_series)
        c_layout.addLayout(r_series_status)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("background-color: #26334d; margin: 4px 0;")
        c_layout.addWidget(sep3)

        # 4. Guide des programmes (EPG)
        self.sync_epg_cb = QCheckBox(" " + tr("Synchroniser automatiquement le guide EPG"))
        self.sync_epg_cb.setStyleSheet("font-weight: 600; font-size: 13px; color: #f1f5f9;")
        c_layout.addWidget(self.sync_epg_cb)

        r_epg = QHBoxLayout()
        r_epg.setContentsMargins(22, 0, 0, 0)
        self.lbl_epg_interval = QLabel(tr("Intervalle d'actualisation :"))
        r_epg.addWidget(self.lbl_epg_interval)
        r_epg.addStretch()
        self.epg_interval_spin = QSpinBox()
        self.epg_interval_spin.setRange(1, 90)
        self.epg_interval_spin.setSuffix(" " + tr("jour(s)"))
        self.epg_interval_spin.setFixedWidth(130)
        r_epg.addWidget(self.epg_interval_spin)
        c_layout.addLayout(r_epg)

        r_epg_offset = QHBoxLayout()
        r_epg_offset.setContentsMargins(22, 0, 0, 0)
        self.lbl_epg_offset = QLabel(tr("Décalage horaire EPG :"))
        r_epg_offset.addWidget(self.lbl_epg_offset)
        r_epg_offset.addStretch()
        self.epg_offset_spin = QSpinBox()
        self.epg_offset_spin.setRange(-12, 12)
        self.epg_offset_spin.setSuffix(" h")
        self.epg_offset_spin.setValue(0)
        self.epg_offset_spin.setFixedWidth(130)
        r_epg_offset.addWidget(self.epg_offset_spin)
        c_layout.addLayout(r_epg_offset)

        r_epg_status = QHBoxLayout()
        r_epg_status.setContentsMargins(22, 0, 0, 4)
        self.lbl_sync_epg_status = QLabel(tr("Dernière synchronisation :") + " --")
        self.lbl_sync_epg_status.setStyleSheet("color: #94a3b8; font-size: 12px;")
        r_epg_status.addWidget(self.lbl_sync_epg_status)
        r_epg_status.addStretch()
        self.btn_sync_epg = QPushButton(" " + tr("Synchroniser"))
        self.btn_sync_epg.setIcon(get_icon("sync", color=DEFAULT_ICON_COLOR))
        self.btn_sync_epg.setProperty("class", "secondary-btn")
        self.btn_sync_epg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync_epg.setFixedHeight(28)
        self.btn_sync_epg.clicked.connect(lambda: self.manual_sync_requested.emit("epg"))
        r_epg_status.addWidget(self.btn_sync_epg)
        c_layout.addLayout(r_epg_status)

        sep4 = QFrame()
        sep4.setFrameShape(QFrame.Shape.HLine)
        sep4.setStyleSheet("background-color: #26334d; margin: 6px 0;")
        c_layout.addWidget(sep4)

        # 5. Options au démarrage et bouton Global
        self.sync_on_startup_cb = QCheckBox(" " + tr("Vérifier et synchroniser au démarrage de l'application"))
        self.sync_on_startup_cb.setStyleSheet("font-size: 13px; color: #f1f5f9;")
        c_layout.addWidget(self.sync_on_startup_cb)

        r_all = QHBoxLayout()
        r_all.setContentsMargins(0, 8, 0, 0)
        r_all.addStretch()
        self.btn_sync_all = QPushButton("  " + tr("Tout synchroniser maintenant"))
        self.btn_sync_all.setIcon(get_icon("sync", color="#ffffff"))
        self.btn_sync_all.setProperty("class", "primary-btn")
        self.btn_sync_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync_all.setFixedHeight(34)
        self.btn_sync_all.clicked.connect(lambda: self.manual_sync_requested.emit("all"))
        r_all.addWidget(self.btn_sync_all)
        c_layout.addLayout(r_all)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_storage_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card, c_layout = self._build_card(
            "Données, Téléchargements & Cache",
            "Configuration du dossier de téléchargement des films VOD et gestion du cache local."
        )

        # 1. Dossier de téléchargement
        self.lbl_dl = QLabel(tr("Dossier de téléchargement des vidéos & films VOD :"))
        c_layout.addWidget(self.lbl_dl)
        dl_row = QHBoxLayout()
        dl_row.setSpacing(8)

        self.download_dir_edit = QLineEdit()
        self.download_dir_edit.setPlaceholderText(get_default_download_dir())
        dl_row.addWidget(self.download_dir_edit, stretch=1)

        self.browse_dl_btn = QPushButton(" " + tr("Parcourir..."))
        self.browse_dl_btn.setIcon(get_icon("folder_open", color="#e2e8f0"))
        self.browse_dl_btn.setIconSize(QSize(16, 16))
        self.browse_dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_dl_btn.setStyleSheet("""
            QPushButton {
                background-color: #20293d;
                color: #e2e8f0;
                border: 1px solid #303e5c;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #29354d;
                color: #ffffff;
            }
        """)
        self.browse_dl_btn.clicked.connect(self._browse_download_dir)
        dl_row.addWidget(self.browse_dl_btn)
        c_layout.addLayout(dl_row)

        sep_dl = QFrame()
        sep_dl.setFrameShape(QFrame.Shape.HLine)
        sep_dl.setStyleSheet("background-color: #20293d; margin: 10px 0px;")
        c_layout.addWidget(sep_dl)

        # 2. Emplacement de la base SQLite
        db_path = self.db.db_path
        self.lbl_db_path = QLabel(f"<b>{tr('Base SQLite :')}</b> <span style='color: #818cf8;'>{db_path}</span>")
        c_layout.addWidget(self.lbl_db_path)

        # 3. Bouton vider le cache des logos
        self.clear_cache_btn = QPushButton("  " + tr("Vider le cache des logos de chaînes"))
        self.clear_cache_btn.setIcon(get_icon("delete", color="#ef4444"))
        self.clear_cache_btn.setIconSize(QSize(16, 16))
        self.clear_cache_btn.setProperty("class", "secondary-btn")
        self.clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_cache_btn.clicked.connect(self._clear_logo_cache)
        c_layout.addWidget(self.clear_cache_btn)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _browse_download_dir(self):
        curr = self.download_dir_edit.text().strip() or get_default_download_dir()
        selected = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier de téléchargement", curr)
        if selected:
            self.download_dir_edit.setText(selected)

    def _build_backup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card, c_layout = self._build_card(
            "Sauvegarde & Configuration",
            "Enregistrez ou restaurez votre configuration complète sous forme de fichier ou via QR Code. "
            "Vous pouvez facilement synchroniser avec un smartphone ou transférer un fichier vers un autre appareil."
        )

        # 0. Passerelle Mobile QR Code
        qr_box = QFrame()
        qr_box.setStyleSheet("background-color: #161c28; border: 1px solid #312e81; border-radius: 8px; padding: 14px;")
        qr_layout = QVBoxLayout(qr_box)
        qr_layout.setSpacing(10)

        self.qr_box_title = QLabel(tr("📱 Passerelle de synchronisation (QR Code)"))
        self.qr_box_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #a5b4fc;")
        qr_layout.addWidget(self.qr_box_title)

        self.qr_box_desc = QLabel(tr(
            "Démarre un mini-serveur local sécurisé et affiche un QR Code à scanner avec votre smartphone. "
            "Permet d'exporter ou d'importer vos favoris, playlists et reprises de lecture directement en réseau local."
        ))
        self.qr_box_desc.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")
        self.qr_box_desc.setWordWrap(True)
        qr_layout.addWidget(self.qr_box_desc)

        qr_btn_row = QHBoxLayout()
        self.btn_open_qr_sync = QPushButton("  " + tr("Ouvrir la passerelle QR Code..."))
        self.btn_open_qr_sync.setIcon(get_icon("qr_code", color="#ffffff"))
        self.btn_open_qr_sync.setIconSize(QSize(18, 18))
        self.btn_open_qr_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_qr_sync.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #4338ca;
            }
        """)
        self.btn_open_qr_sync.clicked.connect(self.qr_sync_requested.emit)
        qr_btn_row.addWidget(self.btn_open_qr_sync)
        qr_btn_row.addStretch()
        qr_layout.addLayout(qr_btn_row)

        c_layout.addWidget(qr_box)

        # 1. Section Exportation (Enregistrer)
        export_box = QFrame()
        export_box.setStyleSheet("background-color: #161c28; border: 1px solid #28334a; border-radius: 8px; padding: 14px;")
        export_layout = QVBoxLayout(export_box)
        export_layout.setSpacing(10)

        self.exp_title = QLabel(tr("💾 Enregistrer la configuration (Sauvegarde)"))
        self.exp_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #ffffff;")
        export_layout.addWidget(self.exp_title)

        self.exp_desc = QLabel(tr(
            "Exporte vos listes de lecture, comptes/serveurs, favoris, historique de visionnage, "
            "chaînes masquées et reprises de lecture dans un fichier JSON compact (~150 Ko).<br>"
            "<i>(Les chaînes brutes et affiches ne sont pas incluses pour garantir un fichier léger et rapide).</i>"
        ))
        self.exp_desc.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")
        self.exp_desc.setWordWrap(True)
        export_layout.addWidget(self.exp_desc)

        exp_btn_row = QHBoxLayout()
        self.btn_export_config = QPushButton("  " + tr("Enregistrer la configuration sous..."))
        self.btn_export_config.setIcon(get_icon("cloud_upload", color="#ffffff"))
        self.btn_export_config.setIconSize(QSize(18, 18))
        self.btn_export_config.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_config.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.btn_export_config.clicked.connect(self._on_export_config)
        exp_btn_row.addWidget(self.btn_export_config)
        exp_btn_row.addStretch()
        export_layout.addLayout(exp_btn_row)

        c_layout.addWidget(export_box)

        # 2. Section Importation (Charger)
        import_box = QFrame()
        import_box.setStyleSheet("background-color: #161c28; border: 1px solid #28334a; border-radius: 8px; padding: 14px;")
        import_layout = QVBoxLayout(import_box)
        import_layout.setSpacing(10)

        self.imp_title = QLabel(tr("📂 Charger une configuration (Restauration)"))
        self.imp_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #ffffff;")
        import_layout.addWidget(self.imp_title)

        self.imp_desc = QLabel(tr(
            "Charge un fichier de configuration précédemment sauvegardé. "
            "Le système fusionne intelligemment vos listes, cumule vos favoris et applique "
            "les reprises de lecture les plus récentes sans écraser vos données locales."
        ))
        self.imp_desc.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")
        self.imp_desc.setWordWrap(True)
        import_layout.addWidget(self.imp_desc)

        imp_btn_row = QHBoxLayout()
        self.btn_import_config = QPushButton("  " + tr("Charger un fichier de configuration..."))
        self.btn_import_config.setIcon(get_icon("cloud_download", color="#ffffff"))
        self.btn_import_config.setIconSize(QSize(18, 18))
        self.btn_import_config.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_import_config.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_import_config.clicked.connect(self._on_import_config)
        imp_btn_row.addWidget(self.btn_import_config)
        imp_btn_row.addStretch()
        import_layout.addLayout(imp_btn_row)

        c_layout.addWidget(import_box)

        # Label d'information sur la dernière action
        self.backup_status_lbl = QLabel("")
        self.backup_status_lbl.setStyleSheet("color: #818cf8; font-size: 12px; font-weight: 500;")
        c_layout.addWidget(self.backup_status_lbl)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _on_export_config(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer la configuration IPTV Hub",
            "iptv_config.json",
            "Fichier de configuration JSON (*.json);;Tous les fichiers (*.*)"
        )
        if not file_path:
            return

        ok, msg = export_config_to_file(self.db, file_path)
        if ok:
            self.backup_status_lbl.setText(f"✓ Dernière sauvegarde effectuée : {os.path.basename(file_path)}")
            QMessageBox.information(self, "Sauvegarde réussie", msg)
        else:
            QMessageBox.critical(self, "Erreur de sauvegarde", msg)

    def _on_import_config(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier de configuration IPTV Hub",
            "",
            "Fichier de configuration JSON (*.json);;Tous les fichiers (*.*)"
        )
        if not file_path:
            return

        confirm = QMessageBox.question(
            self,
            "Confirmer le chargement",
            f"Voulez-vous charger et fusionner la configuration depuis le fichier suivant ?\n\n{file_path}\n\n"
            "Vos favoris, playlists et reprises de visionnage seront combinés sans perte.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        ok, msg, stats = import_config_from_file(self.db, file_path)
        if ok:
            self.backup_status_lbl.setText(f"✓ Dernière configuration chargée : {os.path.basename(file_path)}")
            nb_pl = stats.get('playlists', 0)
            nb_pr = stats.get('progress', 0)
            nb_fav = stats.get('favorites', 0)
            nb_ch = stats.get('disabled_channels', 0)
            nb_grp = stats.get('disabled_groups', 0)
            nb_set = stats.get('settings', 0)

            details = (
                f"{msg}\n\n"
                f"• Listes de lecture : {nb_pl}\n"
                f"• Reprises de visionnage : {nb_pr}\n"
                f"• Favoris : {nb_fav}\n"
                f"• Chaînes masquées : {nb_ch}\n"
                f"• Groupes masqués : {nb_grp}\n"
                f"• Paramètres généraux : {nb_set}"
            )
            QMessageBox.information(self, "Restauration terminée", details)
            self.settings_saved.emit()
        else:
            QMessageBox.critical(self, "Erreur de chargement", msg)

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card, c_layout = self._build_card(
            "À propos d'IPTV Hub",
            "Lecteur multimédia moderne pour flux IPTV, Xtream Codes, VOD et Séries."
        )

        self.lbl_about_v = QLabel(f"<b>{tr('Version :')}</b> {__version__} ({tr('Édition Complète')})")
        self.lbl_about_engine = QLabel(f"<b>{tr('Moteur de rendu :')}</b> libmpv (API OpenGL / QOpenGLWidget + D3D11VA)")
        self.lbl_about_framework = QLabel(f"<b>{tr('Framework UI :')}</b> PyQt6 & Material Symbols")
        self.lbl_about_shortcuts = QLabel(f"<b>{tr('Raccourcis clés :')}</b> [F / F11] {tr('Plein écran')}  •  [{tr('Espace')}] {tr('Pause')}  •  [◀ / ▶] {tr('Recul/Avance 10s')}")

        c_layout.addWidget(self.lbl_about_v)
        c_layout.addWidget(self.lbl_about_engine)
        c_layout.addWidget(self.lbl_about_framework)
        c_layout.addWidget(self.lbl_about_shortcuts)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def set_playlist_id(self, playlist_id: Optional[int]):
        """Définit la playlist courante pour afficher les statuts de synchronisation récents."""
        self._current_playlist_id = playlist_id
        self.refresh_sync_status()

    def refresh_sync_status(self, playlist_id: Optional[int] = None):
        """Met à jour l'affichage des horodatages de synchronisation des 4 flux."""
        target_id = playlist_id or self._current_playlist_id
        if not target_id:
            pls = self.db.get_playlists()
            if pls:
                target_id = pls[0].id
                self._current_playlist_id = target_id

        if not target_id:
            if hasattr(self, "lbl_sync_live_status"):
                self.lbl_sync_live_status.setText(f"{tr('Dernière synchronisation :')} {tr('Jamais')}")
            if hasattr(self, "lbl_sync_vod_status"):
                self.lbl_sync_vod_status.setText(f"{tr('Dernière synchronisation :')} {tr('Jamais')}")
            if hasattr(self, "lbl_sync_series_status"):
                self.lbl_sync_series_status.setText(f"{tr('Dernière synchronisation :')} {tr('Jamais')}")
            if hasattr(self, "lbl_sync_epg_status"):
                self.lbl_sync_epg_status.setText(f"{tr('Dernière synchronisation :')} {tr('Jamais')}")
            return

        ts_map = self.db.get_playlist_sync_timestamps(target_id)
        if hasattr(self, "lbl_sync_live_status"):
            self.lbl_sync_live_status.setText(f"{tr('Dernière synchronisation :')} <b style='color:#cbd5e1;'>{format_last_sync(ts_map.get('live'))}</b>")
        if hasattr(self, "lbl_sync_vod_status"):
            self.lbl_sync_vod_status.setText(f"{tr('Dernière synchronisation :')} <b style='color:#cbd5e1;'>{format_last_sync(ts_map.get('vod'))}</b>")
        if hasattr(self, "lbl_sync_series_status"):
            self.lbl_sync_series_status.setText(f"{tr('Dernière synchronisation :')} <b style='color:#cbd5e1;'>{format_last_sync(ts_map.get('series'))}</b>")
        if hasattr(self, "lbl_sync_epg_status"):
            self.lbl_sync_epg_status.setText(f"{tr('Dernière synchronisation :')} <b style='color:#cbd5e1;'>{format_last_sync(ts_map.get('epg'))}</b>")

    def _load_values(self):
        self.settings = self.db.get_settings()
        self.ua_edit.setText(self.settings.user_agent)
        self.timeout_spin.setValue(getattr(self.settings, "http_timeout", 15))
        self.buffer_spin.setValue(self.settings.buffer_size_mb)
        self.auto_reconnect_cb.setChecked(getattr(self.settings, "auto_reconnect", True))
        self.download_dir_edit.setText(self.settings.download_dir or get_default_download_dir())
        self.auto_play_next_cb.setChecked(getattr(self.settings, "auto_play_next_episode", True))
        if hasattr(self, "introdb_intro_cb"):
            self.introdb_intro_cb.setChecked(getattr(self.settings, "introdb_intro_skip", True))
        if hasattr(self, "introdb_outro_cb"):
            self.introdb_outro_cb.setChecked(getattr(self.settings, "introdb_outro_skip", True))
            self.introdb_outro_cb.setEnabled(self.auto_play_next_cb.isChecked())

        # Auto-Sync & EPG
        if hasattr(self, "sync_live_cb"):
            self.sync_live_cb.setChecked(getattr(self.settings, "auto_sync_live", True))
        if hasattr(self, "sync_live_spin"):
            self.sync_live_spin.setValue(getattr(self.settings, "sync_interval_live_days", 1))

        if hasattr(self, "sync_vod_cb"):
            self.sync_vod_cb.setChecked(getattr(self.settings, "auto_sync_vod", True))
        if hasattr(self, "sync_vod_spin"):
            self.sync_vod_spin.setValue(getattr(self.settings, "sync_interval_vod_days", 3))

        if hasattr(self, "sync_series_cb"):
            self.sync_series_cb.setChecked(getattr(self.settings, "auto_sync_series", True))
        if hasattr(self, "sync_series_spin"):
            self.sync_series_spin.setValue(getattr(self.settings, "sync_interval_series_days", 2))

        if hasattr(self, "sync_epg_cb"):
            self.sync_epg_cb.setChecked(getattr(self.settings, "auto_refresh_epg", True))
        if hasattr(self, "epg_interval_spin"):
            self.epg_interval_spin.setValue(getattr(self.settings, "epg_refresh_days", 1))

        if hasattr(self, "sync_on_startup_cb"):
            self.sync_on_startup_cb.setChecked(getattr(self.settings, "sync_on_startup", True))

        self.refresh_sync_status()

        # Langue audio préférée
        pref_lang = (self.settings.preferred_audio_lang or "").lower()
        sel_idx = 0
        for i in range(self.audio_lang_combo.count()):
            data_val = (self.audio_lang_combo.itemData(i) or "").lower()
            if pref_lang:
                tokens = [t.strip() for t in pref_lang.split(",") if t.strip()]
                if any(t in data_val for t in tokens):
                    sel_idx = i
                    break
            else:
                if not data_val:
                    sel_idx = i
                    break
        self.audio_lang_combo.setCurrentIndex(sel_idx)

        hw = self.settings.hwdec.lower()
        idx = 0
        for i in range(self.hwdec_combo.count()):
            if hw in self.hwdec_combo.itemText(i).lower():
                idx = i
                break
        self.hwdec_combo.setCurrentIndex(idx)

        # Désentrelacement
        deint_val = "yes" if getattr(self.settings, "deinterlace", False) else "auto"
        for i in range(self.deint_combo.count()):
            if self.deint_combo.itemData(i) == deint_val:
                self.deint_combo.setCurrentIndex(i)
                break

        # Langue de l'application
        app_lang = getattr(self.settings, "app_language", "fr")
        for i in range(self.app_lang_combo.count()):
            if self.app_lang_combo.itemData(i) == app_lang:
                self.app_lang_combo.blockSignals(True)
                self.app_lang_combo.setCurrentIndex(i)
                self.app_lang_combo.blockSignals(False)
                break

    def _on_app_lang_changed(self, index: int):
        lang_code = self.app_lang_combo.itemData(index)
        if lang_code:
            self.settings.app_language = lang_code
            I18nManager.instance().set_language(lang_code)

    def _save_settings(self):
        self.settings.user_agent = self.ua_edit.text().strip() or "Mozilla/5.0"
        self.settings.buffer_size_mb = self.buffer_spin.value()
        self.settings.download_dir = self.download_dir_edit.text().strip()
        self.settings.preferred_audio_lang = self.audio_lang_combo.currentData() or ""
        self.settings.auto_play_next_episode = self.auto_play_next_cb.isChecked()
        if hasattr(self, "introdb_intro_cb"):
            self.settings.introdb_intro_skip = self.introdb_intro_cb.isChecked()
        if hasattr(self, "introdb_outro_cb"):
            self.settings.introdb_outro_skip = self.introdb_outro_cb.isChecked()
        self.settings.app_language = self.app_lang_combo.currentData() or "fr"

        # Auto-Sync & EPG
        if hasattr(self, "sync_live_cb"):
            self.settings.auto_sync_live = self.sync_live_cb.isChecked()
        if hasattr(self, "sync_live_spin"):
            self.settings.sync_interval_live_days = self.sync_live_spin.value()

        if hasattr(self, "sync_vod_cb"):
            self.settings.auto_sync_vod = self.sync_vod_cb.isChecked()
        if hasattr(self, "sync_vod_spin"):
            self.settings.sync_interval_vod_days = self.sync_vod_spin.value()

        if hasattr(self, "sync_series_cb"):
            self.settings.auto_sync_series = self.sync_series_cb.isChecked()
        if hasattr(self, "sync_series_spin"):
            self.settings.sync_interval_series_days = self.sync_series_spin.value()

        if hasattr(self, "sync_epg_cb"):
            self.settings.auto_refresh_epg = self.sync_epg_cb.isChecked()
        if hasattr(self, "epg_interval_spin"):
            self.settings.epg_refresh_days = self.epg_interval_spin.value()

        if hasattr(self, "sync_on_startup_cb"):
            self.settings.sync_on_startup = self.sync_on_startup_cb.isChecked()

        # hwdec
        hw_txt = self.hwdec_combo.currentText().split()[0]
        self.settings.hwdec = hw_txt

        deint_data = self.deint_combo.currentData() or "auto"
        self.settings.deinterlace = (deint_data == "yes")

        self.db.save_settings(self.settings)
        self.save_status.setText("✓ " + tr("Paramètres enregistrés"))
        self.settings_saved.emit()

    def _clear_logo_cache(self):
        from core.database import get_cache_dir
        cache_dir = get_cache_dir()
        try:
            for f in os.listdir(cache_dir):
                fp = os.path.join(cache_dir, f)
                if os.path.isfile(fp):
                    os.unlink(fp)
            QMessageBox.information(
                self,
                tr("Succès"),
                tr("Le cache des logos a été vidé avec succès !")
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("Erreur"),
                tr("Impossible de vider le cache : {error}", error=str(e))
            )

    def retranslate_ui(self, *args):
        """Met à jour dynamiquement tous les libellés de l'écran des paramètres."""
        try:
            self._retranslate_ui_impl()
        except (RuntimeError, Exception):
            pass

    def _retranslate_ui_impl(self):
        # Navigation latérale et en-tête
        if hasattr(self, "nav_title"):
            self.nav_title.setText(tr("Paramètres"))
        if hasattr(self, "close_btn"):
            self.close_btn.setText("  " + tr("Fermer les paramètres"))
        if hasattr(self, "save_btn"):
            self.save_btn.setText(" " + tr("Enregistrer les paramètres"))

        if hasattr(self, "btn_general"):
            self.btn_general.setText("  " + tr("Général & Interface"))
        if hasattr(self, "btn_player"):
            self.btn_player.setText("  " + tr("Lecteur Vidéo"))
        if hasattr(self, "btn_network"):
            self.btn_network.setText("  " + tr("Réseau & Flux"))
        if hasattr(self, "btn_epg"):
            self.btn_epg.setText("  " + tr("Synchronisation & EPG"))
        if hasattr(self, "btn_storage"):
            self.btn_storage.setText("  " + tr("Données & Stockage"))
        if hasattr(self, "btn_backup"):
            self.btn_backup.setText("  " + tr("Sauvegarde & Fichiers"))
        if hasattr(self, "btn_about"):
            self.btn_about.setText("  " + tr("À propos"))

        # Cartes enregistrées
        if hasattr(self, "_cards"):
            for t_lbl, d_lbl, title, desc in self._cards:
                t_lbl.setText(tr(title))
                d_lbl.setText(tr(desc))

        # Page Général
        if hasattr(self, "lbl_app_lang"):
            self.lbl_app_lang.setText(tr("Langue de l'application :"))
        if hasattr(self, "app_lang_combo"):
            curr_lang = I18nManager.instance().current_language
            for i in range(self.app_lang_combo.count()):
                if self.app_lang_combo.itemData(i) == curr_lang:
                    self.app_lang_combo.blockSignals(True)
                    self.app_lang_combo.setCurrentIndex(i)
                    self.app_lang_combo.blockSignals(False)
                    break
        if hasattr(self, "lbl_theme"):
            self.lbl_theme.setText(tr("Thème de l'interface :"))
        if hasattr(self, "theme_combo"):
            curr_th = self.theme_combo.currentIndex()
            self.theme_combo.setItemText(0, tr("Gris foncé bleuté (Par défaut)"))
            self.theme_combo.setItemText(1, tr("Sombre moderne"))
            self.theme_combo.setCurrentIndex(curr_th)
        if hasattr(self, "lbl_audio_lang"):
            self.lbl_audio_lang.setText(tr("Langue audio préférée (Films & Séries) :"))
        if hasattr(self, "lbl_osd"):
            self.lbl_osd.setText(tr("Délai de masquage des contrôles vidéo :"))
        if hasattr(self, "osd_timeout_spin"):
            self.osd_timeout_spin.setSuffix(" " + tr("secondes"))
        if hasattr(self, "auto_resume_cb"):
            self.auto_resume_cb.setText(" " + tr("Reprendre automatiquement la dernière chaîne au lancement"))
        if hasattr(self, "auto_play_next_cb"):
            self.auto_play_next_cb.setText(" " + tr("Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)"))
        if hasattr(self, "introdb_intro_cb"):
            self.introdb_intro_cb.setText(" " + tr("Proposer de passer le générique de début (IntroDB)"))
        if hasattr(self, "introdb_outro_cb"):
            self.introdb_outro_cb.setText(" " + tr("Détecter le début du générique de fin pour proposer l'épisode suivant (IntroDB)"))

        # Page Lecteur Vidéo
        if hasattr(self, "lbl_hwdec"):
            self.lbl_hwdec.setText(tr("Décodage matériel (HW Accel) :"))
        if hasattr(self, "lbl_deint"):
            self.lbl_deint.setText(tr("Désentrelacement vidéo :"))
        if hasattr(self, "deint_combo"):
            self._populate_deint_combo()
        if hasattr(self, "lbl_buffer"):
            self.lbl_buffer.setText(tr("Taille du cache de préchargement :"))
        if hasattr(self, "buffer_spin"):
            self.buffer_spin.setSuffix(" " + tr("Mo"))

        # Page Réseau
        if hasattr(self, "lbl_ua"):
            self.lbl_ua.setText(tr("User-Agent HTTP par défaut :"))
        if hasattr(self, "ua_edit"):
            self.ua_edit.setPlaceholderText(tr("Ex: VLC/3.0.18 LibVLC/3.0.18 ou Mozilla/5.0..."))
        if hasattr(self, "lbl_timeout"):
            self.lbl_timeout.setText(tr("Délai d'attente réseau (Timeout) :"))
        if hasattr(self, "auto_reconnect_cb"):
            self.auto_reconnect_cb.setText(" " + tr("Reconnexion automatique en cas de coupure de flux"))

        # Page Synchronisation & EPG
        if hasattr(self, "sync_live_cb"):
            self.sync_live_cb.setText(" " + tr("Synchroniser automatiquement les chaînes en direct"))
        if hasattr(self, "lbl_sync_live_interval"):
            self.lbl_sync_live_interval.setText(tr("Intervalle d'actualisation :"))
        if hasattr(self, "sync_live_spin"):
            self.sync_live_spin.setSuffix(" " + tr("jour(s)"))
        if hasattr(self, "btn_sync_live"):
            self.btn_sync_live.setText(" " + tr("Synchroniser"))

        if hasattr(self, "sync_vod_cb"):
            self.sync_vod_cb.setText(" " + tr("Synchroniser automatiquement les films"))
        if hasattr(self, "lbl_sync_vod_interval"):
            self.lbl_sync_vod_interval.setText(tr("Intervalle d'actualisation :"))
        if hasattr(self, "sync_vod_spin"):
            self.sync_vod_spin.setSuffix(" " + tr("jour(s)"))
        if hasattr(self, "btn_sync_vod"):
            self.btn_sync_vod.setText(" " + tr("Synchroniser"))

        if hasattr(self, "sync_series_cb"):
            self.sync_series_cb.setText(" " + tr("Synchroniser automatiquement les séries"))
        if hasattr(self, "lbl_sync_series_interval"):
            self.lbl_sync_series_interval.setText(tr("Intervalle d'actualisation :"))
        if hasattr(self, "sync_series_spin"):
            self.sync_series_spin.setSuffix(" " + tr("jour(s)"))
        if hasattr(self, "btn_sync_series"):
            self.btn_sync_series.setText(" " + tr("Synchroniser"))

        if hasattr(self, "sync_epg_cb"):
            self.sync_epg_cb.setText(" " + tr("Synchroniser automatiquement le guide EPG"))
        if hasattr(self, "lbl_epg_interval"):
            self.lbl_epg_interval.setText(tr("Intervalle d'actualisation :"))
        if hasattr(self, "epg_interval_spin"):
            self.epg_interval_spin.setSuffix(" " + tr("jour(s)"))
        if hasattr(self, "lbl_epg_offset"):
            self.lbl_epg_offset.setText(tr("Décalage horaire EPG :"))
        if hasattr(self, "btn_sync_epg"):
            self.btn_sync_epg.setText(" " + tr("Synchroniser"))

        if hasattr(self, "sync_on_startup_cb"):
            self.sync_on_startup_cb.setText(" " + tr("Vérifier et synchroniser au démarrage de l'application"))
        if hasattr(self, "btn_sync_all"):
            self.btn_sync_all.setText("  " + tr("Tout synchroniser maintenant"))

        self.refresh_sync_status()

        # Page Stockage
        if hasattr(self, "lbl_dl"):
            self.lbl_dl.setText(tr("Dossier de téléchargement des vidéos & films VOD :"))
        if hasattr(self, "browse_dl_btn"):
            self.browse_dl_btn.setText(" " + tr("Parcourir..."))
        if hasattr(self, "lbl_db_path"):
            self.lbl_db_path.setText(f"<b>{tr('Base SQLite :')}</b> <span style='color: #818cf8;'>{self.db.db_path}</span>")
        if hasattr(self, "clear_cache_btn"):
            self.clear_cache_btn.setText("  " + tr("Vider le cache des logos de chaînes"))

        # Page Sauvegarde
        if hasattr(self, "qr_box_title"):
            self.qr_box_title.setText(tr("📱 Passerelle de synchronisation (QR Code)"))
        if hasattr(self, "qr_box_desc"):
            self.qr_box_desc.setText(tr(
                "Démarre un mini-serveur local sécurisé et affiche un QR Code à scanner avec votre smartphone. "
                "Permet d'exporter ou d'importer vos favoris, playlists et reprises de lecture directement en réseau local."
            ))
        if hasattr(self, "btn_open_qr_sync"):
            self.btn_open_qr_sync.setText("  " + tr("Ouvrir la passerelle QR Code..."))
        if hasattr(self, "exp_title"):
            self.exp_title.setText(tr("💾 Enregistrer la configuration (Sauvegarde)"))
        if hasattr(self, "exp_desc"):
            self.exp_desc.setText(tr(
                "Exporte vos listes de lecture, comptes/serveurs, favoris, historique de visionnage, "
                "chaînes masquées et reprises de lecture dans un fichier JSON compact (~150 Ko).<br>"
                "<i>(Les chaînes brutes et affiches ne sont pas incluses pour garantir un fichier léger et rapide).</i>"
            ))
        if hasattr(self, "btn_export_config"):
            self.btn_export_config.setText("  " + tr("Enregistrer la configuration sous..."))
        if hasattr(self, "imp_title"):
            self.imp_title.setText(tr("📂 Charger une configuration (Restauration)"))
        if hasattr(self, "imp_desc"):
            self.imp_desc.setText(tr(
                "Charge un fichier de configuration précédemment sauvegardé. "
                "Le système fusionne intelligemment vos listes, cumule vos favoris et applique "
                "les reprises de lecture les plus récentes sans écraser vos données locales."
            ))
        if hasattr(self, "btn_import_config"):
            self.btn_import_config.setText("  " + tr("Charger un fichier de configuration..."))

        # Page À propos
        if hasattr(self, "lbl_about_v"):
            self.lbl_about_v.setText(f"<b>{tr('Version :')}</b> {__version__} ({tr('Édition Complète')})")
        if hasattr(self, "lbl_about_engine"):
            self.lbl_about_engine.setText(f"<b>{tr('Moteur de rendu :')}</b> libmpv (API OpenGL / QOpenGLWidget + D3D11VA)")
        if hasattr(self, "lbl_about_framework"):
            self.lbl_about_framework.setText(f"<b>{tr('Framework UI :')}</b> PyQt6 & Material Symbols")
        if hasattr(self, "lbl_about_shortcuts"):
            self.lbl_about_shortcuts.setText(f"<b>{tr('Raccourcis clés :')}</b> [F / F11] {tr('Plein écran')}  •  [{tr('Espace')}] {tr('Pause')}  •  [◀ / ▶] {tr('Recul/Avance 10s')}")
