"""
Dialogue d'ajout de liste de lecture IPTV (M3U distant, Fichier M3U local, Xtream Codes).
Enregistre de manière persistante tous les paramètres dans SQLite.
"""

from typing import Optional, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QWidget, QFileDialog, QProgressBar,
    QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal, QSize

from core.models import Playlist, Channel
from core.database import Database
from core.m3u_parser import M3UParser
from core.xtream_client import XtreamClient
from core.epg_manager import EPGManager
from ui.icons import get_icon, DEFAULT_ICON_COLOR


class PlaylistImportWorker(QThread):
    progress = pyqtSignal(str)          # Message de statut
    finished_success = pyqtSignal(int)  # Playlist ID
    error = pyqtSignal(str)

    def __init__(self, db: Database, playlist: Playlist, parent=None):
        super().__init__(parent)
        self.db = db
        self.playlist = playlist

    def run(self):
        try:
            # 1. Enregistrement ou mise à jour de la playlist dans SQLite
            self.progress.emit("Enregistrement des paramètres dans SQLite...")
            if not self.playlist.id:
                playlist_id = self.db.add_playlist(self.playlist)
                self.playlist.id = playlist_id
            else:
                self.db.update_playlist(self.playlist)
                playlist_id = self.playlist.id

            channels: List[Channel] = []

            # 2. Traitement selon le type (M3U ou Xtream Codes)
            if self.playlist.playlist_type == "m3u":
                if self.playlist.url_or_path.startswith("http://") or self.playlist.url_or_path.startswith("https://"):
                    self.progress.emit("Téléchargement de la playlist M3U...")
                    channels = M3UParser.parse_url(
                        self.playlist.url_or_path,
                        playlist_id=playlist_id,
                        progress_callback=lambda c: self.progress.emit(f"Parsing M3U : {c} chaînes trouvées...")
                    )
                else:
                    self.progress.emit("Lecture du fichier M3U local...")
                    channels = M3UParser.parse_file(
                        self.playlist.url_or_path,
                        playlist_id=playlist_id,
                        progress_callback=lambda c: self.progress.emit(f"Parsing M3U : {c} chaînes trouvées...")
                    )

            elif self.playlist.playlist_type == "xtream":
                self.progress.emit("Connexion au serveur Xtream Codes...")
                client = XtreamClient(
                    server_url=self.playlist.server_url,
                    username=self.playlist.username,
                    password=self.playlist.password
                )
                client.authenticate()

                self.progress.emit("Récupération des chaînes en direct...")
                live_channels = client.get_live_streams(playlist_id=playlist_id)

                self.progress.emit("Récupération des films VOD...")
                vod_channels = client.get_vod_streams(playlist_id=playlist_id)

                self.progress.emit("Récupération des séries...")
                series_channels = client.get_series(playlist_id=playlist_id)

                channels = live_channels + vod_channels + series_channels
                if not self.playlist.epg_url:
                    self.playlist.epg_url = client.get_epg_url()
                    self.db.update_playlist(self.playlist)

            # 3. Sauvegarde des chaînes dans SQLite
            self.progress.emit(f"Enregistrement de {len(channels)} éléments dans la base de données...")
            self.db.save_channels_batch(playlist_id, channels)

            # 4. Traitement optionnel de l'EPG
            if self.playlist.epg_url:
                try:
                    self.progress.emit("Téléchargement et mise à jour du guide EPG...")
                    epg_mgr = EPGManager(self.db)
                    if self.playlist.epg_url.startswith("http"):
                        epg_mgr.load_from_url(
                            self.playlist.epg_url,
                            progress_callback=lambda count: self.progress.emit(f"Parsing EPG : {count} programmes...")
                        )
                    else:
                        epg_mgr.load_from_file(
                            self.playlist.epg_url,
                            progress_callback=lambda count: self.progress.emit(f"Parsing EPG : {count} programmes...")
                        )
                except Exception as epg_err:
                    print(f"Erreur non bloquante EPG: {epg_err}")

            self.progress.emit("Liste de lecture enregistrée avec succès !")
            self.finished_success.emit(playlist_id)

        except Exception as e:
            self.error.emit(str(e))


class AddPlaylistDialog(QDialog):
    playlist_added = pyqtSignal(int)  # playlist_id

    def __init__(self, db: Database, playlist: Optional[Playlist] = None, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.db = db
        self.edit_playlist = playlist
        self.setWindowTitle("Modifier la liste de lecture" if playlist else "Ajouter une liste de lecture")
        self.resize(520, 440)
        self._worker: Optional[PlaylistImportWorker] = None
        self._init_ui()
        if self.edit_playlist:
            self._fill_existing_data()

    def _init_ui(self):
        self.setStyleSheet("QDialog { background-color: #1b2232; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Onglets avec icônes Material Symbols
        self.tabs = QTabWidget()

        # Onglet 1 : URL M3U
        tab_url = QWidget()
        url_layout = QVBoxLayout(tab_url)
        url_layout.setSpacing(10)

        self.url_name_input = QLineEdit()
        self.url_name_input.setPlaceholderText("Ex: Ma Liste IPTV")
        url_layout.addWidget(QLabel("Nom de la liste de lecture :"))
        url_layout.addWidget(self.url_name_input)

        self.url_link_input = QLineEdit()
        self.url_link_input.setPlaceholderText("http://exemple.com/playlist.m3u8")
        url_layout.addWidget(QLabel("URL M3U / M3U8 :"))
        url_layout.addWidget(self.url_link_input)

        self.url_epg_input = QLineEdit()
        self.url_epg_input.setPlaceholderText("Optionnel (URL XMLTV .xml ou .xml.gz)")
        url_layout.addWidget(QLabel("URL EPG (Guide des programmes) :"))
        url_layout.addWidget(self.url_epg_input)
        url_layout.addStretch()

        self.tabs.addTab(tab_url, get_icon("link", color=DEFAULT_ICON_COLOR), "URL M3U")

        # Onglet 2 : Fichier Local M3U
        tab_file = QWidget()
        file_layout = QVBoxLayout(tab_file)
        file_layout.setSpacing(10)

        self.file_name_input = QLineEdit()
        self.file_name_input.setPlaceholderText("Ex: Liste Locale")
        file_layout.addWidget(QLabel("Nom de la liste de lecture :"))
        file_layout.addWidget(self.file_name_input)

        file_browse_row = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Chemin vers le fichier .m3u ou .m3u8")
        file_browse_row.addWidget(self.file_path_input)

        browse_btn = QPushButton(" Parcourir...")
        browse_btn.setIcon(get_icon("folder", color=DEFAULT_ICON_COLOR))
        browse_btn.setIconSize(QSize(18, 18))
        browse_btn.setProperty("class", "secondary-btn")
        browse_btn.clicked.connect(self._browse_file)
        file_browse_row.addWidget(browse_btn)

        file_layout.addWidget(QLabel("Fichier M3U :"))
        file_layout.addLayout(file_browse_row)

        self.file_epg_input = QLineEdit()
        self.file_epg_input.setPlaceholderText("Optionnel (URL ou chemin XMLTV)")
        file_layout.addWidget(QLabel("EPG (Optionnel) :"))
        file_layout.addWidget(self.file_epg_input)
        file_layout.addStretch()

        self.tabs.addTab(tab_file, get_icon("folder", color=DEFAULT_ICON_COLOR), "Fichier M3U")

        # Onglet 3 : Xtream Codes
        tab_xtream = QWidget()
        xtream_layout = QVBoxLayout(tab_xtream)
        xtream_layout.setSpacing(8)

        self.xc_name_input = QLineEdit()
        self.xc_name_input.setPlaceholderText("Ex: Serveur Premium")
        xtream_layout.addWidget(QLabel("Nom de la liste de lecture :"))
        xtream_layout.addWidget(self.xc_name_input)

        self.xc_url_input = QLineEdit()
        self.xc_url_input.setPlaceholderText("http://serveur.com:8080")
        xtream_layout.addWidget(QLabel("URL du serveur :"))
        xtream_layout.addWidget(self.xc_url_input)

        cred_row = QHBoxLayout()
        self.xc_user_input = QLineEdit()
        self.xc_user_input.setPlaceholderText("Nom d'utilisateur")
        cred_row.addWidget(self.xc_user_input)

        self.xc_pass_input = QLineEdit()
        self.xc_pass_input.setPlaceholderText("Mot de passe")
        self.xc_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        cred_row.addWidget(self.xc_pass_input)

        xtream_layout.addWidget(QLabel("Identifiants Xtream :"))
        xtream_layout.addLayout(cred_row)
        xtream_layout.addStretch()

        self.tabs.addTab(tab_xtream, get_icon("account_circle", color=DEFAULT_ICON_COLOR), "Xtream Codes")

        layout.addWidget(self.tabs)

        # Progression & statut
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #818cf8; font-weight: 500;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Boutons d'action
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton(" Annuler")
        self.cancel_btn.setIcon(get_icon("close", color=DEFAULT_ICON_COLOR))
        self.cancel_btn.setIconSize(QSize(18, 18))
        self.cancel_btn.setProperty("class", "secondary-btn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        save_btn_text = " Enregistrer les modifications" if self.edit_playlist else " Importer la liste"
        self.save_btn = QPushButton(save_btn_text)
        self.save_btn.setIcon(get_icon("add" if not self.edit_playlist else "edit", color="#ffffff"))
        self.save_btn.setIconSize(QSize(18, 18))
        self.save_btn.setProperty("class", "primary-btn")
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

    def _fill_existing_data(self):
        p = self.edit_playlist
        if not p:
            return
        if p.playlist_type == "xtream":
            self.tabs.setCurrentIndex(2)
            self.xc_name_input.setText(p.name)
            self.xc_url_input.setText(p.server_url)
            self.xc_user_input.setText(p.username)
            self.xc_pass_input.setText(p.password)
        elif p.url_or_path.startswith("http"):
            self.tabs.setCurrentIndex(0)
            self.url_name_input.setText(p.name)
            self.url_link_input.setText(p.url_or_path)
            self.url_epg_input.setText(p.epg_url)
        else:
            self.tabs.setCurrentIndex(1)
            self.file_name_input.setText(p.name)
            self.file_path_input.setText(p.url_or_path)
            self.file_epg_input.setText(p.epg_url)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier M3U", "", "Playlists M3U (*.m3u *.m3u8);;Tous les fichiers (*.*)")
        if path:
            self.file_path_input.setText(path)
            if not self.file_name_input.text():
                from pathlib import Path
                self.file_name_input.setText(Path(path).stem)

    def _on_save_clicked(self):
        tab_idx = self.tabs.currentIndex()
        playlist = self.edit_playlist or Playlist()

        if tab_idx == 0:  # M3U URL
            name = self.url_name_input.text().strip() or "Liste URL"
            url = self.url_link_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Erreur", "Veuillez renseigner une URL valide.")
                return
            playlist.name = name
            playlist.url_or_path = url
            playlist.playlist_type = "m3u"
            playlist.epg_url = self.url_epg_input.text().strip()

        elif tab_idx == 1:  # Fichier M3U
            name = self.file_name_input.text().strip() or "Liste Fichier"
            path = self.file_path_input.text().strip()
            if not path:
                QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un fichier M3U.")
                return
            playlist.name = name
            playlist.url_or_path = path
            playlist.playlist_type = "m3u"
            playlist.epg_url = self.file_epg_input.text().strip()

        elif tab_idx == 2:  # Xtream Codes
            name = self.xc_name_input.text().strip() or "Serveur Xtream"
            server = self.xc_url_input.text().strip()
            user = self.xc_user_input.text().strip()
            pwd = self.xc_pass_input.text().strip()
            if not server or not user or not pwd:
                QMessageBox.warning(self, "Erreur", "Veuillez renseigner l'URL du serveur, l'identifiant et le mot de passe.")
                return
            playlist.name = name
            playlist.server_url = server
            playlist.username = user
            playlist.password = pwd
            playlist.url_or_path = f"{server}/player_api.php?username={user}"
            playlist.playlist_type = "xtream"

        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(True)

        self._worker = PlaylistImportWorker(self.db, playlist, self)
        self._worker.progress.connect(self.status_label.setText)
        self._worker.finished_success.connect(self._on_import_finished)
        self._worker.error.connect(self._on_import_error)
        self._worker.start()

    def _on_import_finished(self, playlist_id: int):
        self.playlist_added.emit(playlist_id)
        self.accept()

    def _on_import_error(self, err_msg: str):
        self.save_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        QMessageBox.critical(self, "Erreur d'importation", f"Impossible d'importer la liste :\n{err_msg}")
