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
from core.i18n import tr, I18nManager
from ui.icons import get_icon, DEFAULT_ICON_COLOR


class SettingsView(QWidget):
    settings_saved = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.settings: AppSettings = self.db.get_settings()
        self.setObjectName("settingsView")

        self._init_ui()
        self._load_values()

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

        self.nav_title = QLabel("Paramètres")
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

        self.btn_general = self._create_nav_btn("Général & Interface", "tune", 0, checked=True)
        self.btn_player = self._create_nav_btn("Lecteur Vidéo", "videocam", 1)
        self.btn_network = self._create_nav_btn("Réseau & Flux", "wifi", 2)
        self.btn_epg = self._create_nav_btn("Guide EPG", "calendar_today", 3)
        self.btn_storage = self._create_nav_btn("Données & Stockage", "storage", 4)
        self.btn_backup = self._create_nav_btn("Sauvegarde & Fichiers", "content_copy", 5)
        self.btn_about = self._create_nav_btn("À propos", "info", 6)

        for b in [self.btn_general, self.btn_player, self.btn_network, self.btn_epg, self.btn_storage, self.btn_backup, self.btn_about]:
            nav_layout.addWidget(b)

        nav_layout.addStretch()

        # Bouton fermer/retour
        self.close_btn = QPushButton("  Fermer les paramètres")
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

        self.save_btn = QPushButton(" Enregistrer les paramètres")
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

        t_lbl = QLabel(title)
        t_lbl.setProperty("class", "settings-card-title")
        layout.addWidget(t_lbl)

        d_lbl = QLabel(desc)
        d_lbl.setProperty("class", "settings-card-desc")
        d_lbl.setWordWrap(True)
        layout.addWidget(d_lbl)

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
        self.lbl_app_lang = QLabel("Langue de l'application :")
        r_app_lang.addWidget(self.lbl_app_lang)
        r_app_lang.addStretch()
        self.app_lang_combo = QComboBox()
        self.app_lang_combo.addItem("Français", "fr")
        self.app_lang_combo.addItem("English", "en")
        self.app_lang_combo.setFixedWidth(240)
        self.app_lang_combo.currentIndexChanged.connect(self._on_app_lang_changed)
        r_app_lang.addWidget(self.app_lang_combo)
        c_layout.addLayout(r_app_lang)

        # Thème
        r1 = QHBoxLayout()
        self.lbl_theme = QLabel("Thème de l'interface :")
        r1.addWidget(self.lbl_theme)
        r1.addStretch()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Gris foncé bleuté (Par défaut)", "Sombre moderne"])
        self.theme_combo.setFixedWidth(240)
        r1.addWidget(self.theme_combo)
        c_layout.addLayout(r1)

        # Langue audio préférée (Films & Séries)
        r_lang = QHBoxLayout()
        r_lang.addWidget(QLabel("Langue audio préférée (Films & Séries) :"))
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
        r2.addWidget(QLabel("Délai de masquage des contrôles vidéo :"))
        r2.addStretch()
        self.osd_timeout_spin = QSpinBox()
        self.osd_timeout_spin.setRange(1, 10)
        self.osd_timeout_spin.setSuffix(" secondes")
        self.osd_timeout_spin.setValue(4)
        self.osd_timeout_spin.setFixedWidth(140)
        r2.addWidget(self.osd_timeout_spin)
        c_layout.addLayout(r2)

        # Reprise de la dernière chaîne
        self.auto_resume_cb = QCheckBox(" Reprendre automatiquement la dernière chaîne au lancement")
        self.auto_resume_cb.setChecked(True)
        c_layout.addWidget(self.auto_resume_cb)

        # Enchaînement automatique des épisodes de série
        self.auto_play_next_cb = QCheckBox(" Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)")
        self.auto_play_next_cb.setChecked(True)
        c_layout.addWidget(self.auto_play_next_cb)

        layout.addWidget(card)
        layout.addStretch()
        return page

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
        r1.addWidget(QLabel("Décodage matériel (HW Accel) :"))
        r1.addStretch()
        self.hwdec_combo = QComboBox()
        self.hwdec_combo.addItems(["auto", "d3d11va (Windows DirectX)", "nvdec (NVIDIA)", "dxva2", "no (CPU)"])
        self.hwdec_combo.setFixedWidth(240)
        r1.addWidget(self.hwdec_combo)
        c_layout.addLayout(r1)

        # Désentrelacement
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Désentrelacement vidéo :"))
        r2.addStretch()
        self.deint_combo = QComboBox()
        self.deint_combo.addItems(["auto (Recommandé)", "yes (Toujours activé)", "no (Désactivé)"])
        self.deint_combo.setFixedWidth(240)
        r2.addWidget(self.deint_combo)
        c_layout.addLayout(r2)

        # Taille du tampon cache
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Taille du cache de préchargement :"))
        r3.addStretch()
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(10, 300)
        self.buffer_spin.setSuffix(" Mo")
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
        c_layout.addWidget(QLabel("User-Agent HTTP par défaut :"))
        self.ua_edit = QLineEdit()
        self.ua_edit.setPlaceholderText("Ex: VLC/3.0.18 LibVLC/3.0.18 ou Mozilla/5.0...")
        c_layout.addWidget(self.ua_edit)

        # Timeout de connexion
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Délai d'attente réseau (Timeout) :"))
        r2.addStretch()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(3, 60)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setValue(getattr(self.settings, "http_timeout", 15))
        self.timeout_spin.setFixedWidth(140)
        r2.addWidget(self.timeout_spin)
        c_layout.addLayout(r2)

        # Reconnexion automatique
        self.auto_reconnect_cb = QCheckBox(" Reconnexion automatique en cas de coupure de flux")
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
            "Guide Électronique des Programmes (EPG)",
            "Fréquence de synchronisation et décalage horaire pour les programmes TV."
        )

        # Intervalle d'actualisation EPG
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Intervalle d'actualisation automatique :"))
        r1.addStretch()
        self.epg_interval_spin = QSpinBox()
        self.epg_interval_spin.setRange(1, 48)
        self.epg_interval_spin.setSuffix(" heures")
        self.epg_interval_spin.setValue(self.settings.epg_refresh_hours)
        self.epg_interval_spin.setFixedWidth(140)
        r1.addWidget(self.epg_interval_spin)
        c_layout.addLayout(r1)

        # Décalage horaire EPG
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Décalage horaire EPG :"))
        r2.addStretch()
        self.epg_offset_spin = QSpinBox()
        self.epg_offset_spin.setRange(-12, 12)
        self.epg_offset_spin.setSuffix(" h")
        self.epg_offset_spin.setValue(0)
        self.epg_offset_spin.setFixedWidth(140)
        r2.addWidget(self.epg_offset_spin)
        c_layout.addLayout(r2)

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
        c_layout.addWidget(QLabel("Dossier de téléchargement des vidéos & films VOD :"))
        dl_row = QHBoxLayout()
        dl_row.setSpacing(8)

        self.download_dir_edit = QLineEdit()
        self.download_dir_edit.setPlaceholderText(get_default_download_dir())
        dl_row.addWidget(self.download_dir_edit, stretch=1)

        browse_dl_btn = QPushButton(" Parcourir...")
        browse_dl_btn.setIcon(get_icon("folder_open", color="#e2e8f0"))
        browse_dl_btn.setIconSize(QSize(16, 16))
        browse_dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_dl_btn.setStyleSheet("""
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
        browse_dl_btn.clicked.connect(self._browse_download_dir)
        dl_row.addWidget(browse_dl_btn)
        c_layout.addLayout(dl_row)

        sep_dl = QFrame()
        sep_dl.setFrameShape(QFrame.Shape.HLine)
        sep_dl.setStyleSheet("background-color: #20293d; margin: 10px 0px;")
        c_layout.addWidget(sep_dl)

        # 2. Emplacement de la base SQLite
        db_path = self.db.db_path
        c_layout.addWidget(QLabel(f"<b>Base SQLite :</b> <span style='color: #818cf8;'>{db_path}</span>"))

        # 3. Bouton vider le cache des logos
        clear_cache_btn = QPushButton("  Vider le cache des logos de chaînes")
        clear_cache_btn.setIcon(get_icon("delete", color="#ef4444"))
        clear_cache_btn.setIconSize(QSize(16, 16))
        clear_cache_btn.setProperty("class", "secondary-btn")
        clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_cache_btn.clicked.connect(self._clear_logo_cache)
        c_layout.addWidget(clear_cache_btn)

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
            "Enregistrez ou restaurez votre configuration complète sous forme de fichier. "
            "Vous pouvez facilement transférer ce fichier via une clé USB ou un dossier partagé vers un autre PC ou vers votre version Android TV."
        )

        # 1. Section Exportation (Enregistrer)
        export_box = QFrame()
        export_box.setStyleSheet("background-color: #161c28; border: 1px solid #28334a; border-radius: 8px; padding: 14px;")
        export_layout = QVBoxLayout(export_box)
        export_layout.setSpacing(10)

        exp_title = QLabel("💾 Enregistrer la configuration (Sauvegarde)")
        exp_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #ffffff;")
        export_layout.addWidget(exp_title)

        exp_desc = QLabel(
            "Exporte vos listes de lecture, comptes/serveurs, favoris, historique de visionnage, "
            "chaînes masquées et reprises de lecture dans un fichier JSON compact (~150 Ko).<br>"
            "<i>(Les chaînes brutes et affiches ne sont pas incluses pour garantir un fichier léger et rapide).</i>"
        )
        exp_desc.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")
        exp_desc.setWordWrap(True)
        export_layout.addWidget(exp_desc)

        exp_btn_row = QHBoxLayout()
        self.btn_export_config = QPushButton("  Enregistrer la configuration sous...")
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

        imp_title = QLabel("📂 Charger une configuration (Restauration)")
        imp_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #ffffff;")
        import_layout.addWidget(imp_title)

        imp_desc = QLabel(
            "Charge un fichier de configuration précédemment sauvegardé. "
            "Le système fusionne intelligemment vos listes, cumule vos favoris et applique "
            "les reprises de lecture les plus récentes sans écraser vos données locales."
        )
        imp_desc.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")
        imp_desc.setWordWrap(True)
        import_layout.addWidget(imp_desc)

        imp_btn_row = QHBoxLayout()
        self.btn_import_config = QPushButton("  Charger un fichier de configuration...")
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

        c_layout.addWidget(QLabel(f"<b>Version :</b> {__version__} (Édition Complète)"))
        c_layout.addWidget(QLabel("<b>Moteur de rendu :</b> libmpv (API de rendu OpenGL / QOpenGLWidget + D3D11VA)"))
        c_layout.addWidget(QLabel("<b>Framework UI :</b> PyQt6 & Material Symbols"))
        c_layout.addWidget(QLabel("<b>Raccourcis clés :</b> [F / F11] Plein écran  •  [Espace] Pause  •  [◀ / ▶] Recul/Avance 10s"))

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _load_values(self):
        self.settings = self.db.get_settings()
        self.ua_edit.setText(self.settings.user_agent)
        self.timeout_spin.setValue(getattr(self.settings, "http_timeout", 15))
        self.buffer_spin.setValue(self.settings.buffer_size_mb)
        self.auto_reconnect_cb.setChecked(getattr(self.settings, "auto_reconnect", True))
        self.epg_interval_spin.setValue(self.settings.epg_refresh_hours)
        self.download_dir_edit.setText(self.settings.download_dir or get_default_download_dir())
        self.auto_play_next_cb.setChecked(getattr(self.settings, "auto_play_next_episode", True))

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
        self.settings.epg_refresh_hours = self.epg_interval_spin.value()
        self.settings.download_dir = self.download_dir_edit.text().strip()
        self.settings.preferred_audio_lang = self.audio_lang_combo.currentData() or ""
        self.settings.auto_play_next_episode = self.auto_play_next_cb.isChecked()
        self.settings.app_language = self.app_lang_combo.currentData() or "fr"

        # hwdec
        hw_txt = self.hwdec_combo.currentText().split()[0]
        self.settings.hwdec = hw_txt

        deint_txt = "yes" in self.deint_combo.currentText().lower()
        self.settings.deinterlace = deint_txt

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
            QMessageBox.information(self, "Cache vidé", "Le cache des logos a été nettoyé avec succès.")
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible de vider le cache : {e}")

    def retranslate_ui(self):
        """Met à jour les textes des onglets, en-têtes et boutons de SettingsView."""
        if hasattr(self, "nav_title"):
            self.nav_title.setText(tr("Paramètres"))
        if hasattr(self, "close_btn"):
            self.close_btn.setText("  " + tr("Fermer les paramètres"))
        if hasattr(self, "save_btn"):
            self.save_btn.setText(" " + tr("Enregistrer les paramètres"))

        # Boutons de navigation
        if hasattr(self, "btn_general"):
            self.btn_general.setText("  " + tr("Général & Interface"))
        if hasattr(self, "btn_player"):
            self.btn_player.setText("  " + tr("Lecteur Vidéo"))
        if hasattr(self, "btn_network"):
            self.btn_network.setText("  " + tr("Réseau & Flux"))
        if hasattr(self, "btn_epg"):
            self.btn_epg.setText("  " + tr("Guide EPG"))
        if hasattr(self, "btn_storage"):
            self.btn_storage.setText("  " + tr("Données & Stockage"))
        if hasattr(self, "btn_backup"):
            self.btn_backup.setText("  " + tr("Sauvegarde & Fichiers"))
        if hasattr(self, "btn_about"):
            self.btn_about.setText("  " + tr("À propos"))

        # Labels de la page générale
        if hasattr(self, "lbl_app_lang"):
            self.lbl_app_lang.setText(tr("Langue de l'application :"))
        if hasattr(self, "lbl_theme"):
            self.lbl_theme.setText(tr("Thème de l'interface :"))
