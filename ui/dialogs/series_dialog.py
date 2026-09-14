"""
Dialogue moderne de navigation dans les saisons et épisodes d'une série IPTV.
Utilise les icônes Google Material Symbols (Outlined).
"""

from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QProgressBar,
    QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap

from core.models import Channel, Playlist
from core.database import Database
from core.xtream_client import XtreamClient
from core.image_loader import ImageLoader
from ui.icons import get_icon, DEFAULT_ICON_COLOR
from ui.widgets.rounded_poster import RoundedPosterLabel


class SeriesInfoWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, client: XtreamClient, series_id: str, parent=None):
        super().__init__(parent)
        self.client = client
        self.series_id = series_id

    def run(self):
        try:
            data = self.client.get_series_info(self.series_id)
            if not isinstance(data, dict):
                raise ValueError("Format de réponse de série invalide")
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class SeriesEpisodesDialog(QDialog):
    episode_selected = pyqtSignal(Channel)  # Chaîne virtuelle pour l'épisode à lire
    series_context_selected = pyqtSignal(list, int)  # (liste des épisodes, index de l'épisode actuel)

    def __init__(self, channel: Channel, db: Database, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.channel = channel
        self.db = db
        self.playlist: Optional[Playlist] = self.db.get_playlist(channel.playlist_id)
        self.series_data: Dict[str, Any] = {}
        self.episodes_by_season: Dict[str, List[Dict[str, Any]]] = {}

        self.setWindowTitle(f"Série : {channel.name}")
        self.resize(750, 580)
        self.setMinimumSize(600, 450)

        self._worker: Optional[SeriesInfoWorker] = None
        self._init_ui()
        self._load_series_info()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # 1. En-tête : Poster, Titre, Synopsis & Métadonnées
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background-color: #141824;
                border: 1px solid #232a3d;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(16)

        # Poster avec coins arrondis
        self.poster_label = RoundedPosterLabel(radius=8, border_color="#283044", bg_color="#1a202e", fallback_icon="video_library", parent=self)
        self.poster_label.setFixedSize(90, 130)
        self._set_default_poster()
        header_layout.addWidget(self.poster_label)

        # Infos textuelles
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title_row = QHBoxLayout()
        self.title_label = QLabel(self.channel.name)
        self.title_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #ffffff;")
        title_row.addWidget(self.title_label)

        if self.channel.rating:
            rating_badge = QLabel(f"⭐ {self.channel.rating}")
            rating_badge.setStyleSheet("background-color: rgba(245, 158, 11, 0.15); color: #fbbf24; font-weight: 700; font-size: 11px; padding: 2px 6px; border-radius: 4px;")
            title_row.addWidget(rating_badge)

        title_row.addStretch()
        info_layout.addLayout(title_row)

        self.meta_label = QLabel(f"Genre : {self.channel.group_title.replace('🍿', '').strip()}  •  {self.channel.year}")
        self.meta_label.setStyleSheet("color: #818cf8; font-size: 12px; font-weight: 500;")
        info_layout.addWidget(self.meta_label)

        self.plot_label = QLabel("Chargement des informations de la série...")
        self.plot_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.plot_label.setWordWrap(True)
        self.plot_label.setMaximumHeight(70)
        info_layout.addWidget(self.plot_label)

        header_layout.addLayout(info_layout)
        layout.addWidget(header_card)

        # 2. Sélecteur de Saison
        season_row = QHBoxLayout()
        season_row.setSpacing(10)

        season_lbl = QLabel("Saison :")
        season_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #f8fafc;")
        season_row.addWidget(season_lbl)

        self.season_combo = QComboBox()
        self.season_combo.currentIndexChanged.connect(self._on_season_changed)
        season_row.addWidget(self.season_combo, stretch=1)

        layout.addLayout(season_row)

        # Barre de progression de chargement
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        # 3. Liste des Épisodes
        self.episodes_list = QListWidget()
        self.episodes_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.episodes_list.itemDoubleClicked.connect(self._on_episode_double_clicked)
        layout.addWidget(self.episodes_list)

        # 4. Bas de page : Boutons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        close_btn = QPushButton(" Fermer")
        close_btn.setIcon(get_icon("close", color=DEFAULT_ICON_COLOR))
        close_btn.setIconSize(QSize(18, 18))
        close_btn.setProperty("class", "secondary-btn")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        self.play_btn = QPushButton(" Lire l'épisode")
        self.play_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
        self.play_btn.setIconSize(QSize(20, 20))
        self.play_btn.setProperty("class", "primary-btn")
        self.play_btn.clicked.connect(self._on_play_clicked)
        btn_row.addWidget(self.play_btn)

        layout.addLayout(btn_row)

    def _set_default_poster(self):
        self.poster_label.clear()

    def _load_series_info(self):
        if not self.playlist or self.playlist.playlist_type != "xtream":
            self.progress_bar.setVisible(False)
            self.plot_label.setText("Cette série n'est pas issue d'une source Xtream Codes.")
            return

        # Charger le poster si disponible
        if self.channel.logo_url:
            cached = ImageLoader.instance().get_cached_image(self.channel.logo_url)
            if cached:
                self.poster_label.setPixmap(cached)
            else:
                self.poster_label.clear()
                ImageLoader.instance().image_loaded.connect(self._on_poster_loaded)
                ImageLoader.instance().request_image(self.channel.logo_url)
        else:
            self.poster_label.clear()

        # Récupération asynchrone des épisodes
        if not self.playlist or self.playlist.playlist_type != "xtream":
            return

        client = XtreamClient(
            server_url=self.playlist.server_url,
            username=self.playlist.username,
            password=self.playlist.password
        )

        self._worker = SeriesInfoWorker(client, self.channel.stream_id or "", self)
        self._worker.finished.connect(self._on_series_data_loaded)
        self._worker.error.connect(self._on_series_data_error)
        self._worker.start()

    def _on_poster_loaded(self, url: str, pixmap: QPixmap):
        if url == self.channel.logo_url:
            self.poster_label.setPixmap(pixmap)

    def _on_series_data_loaded(self, data: Dict[str, Any]):
        self.progress_bar.setVisible(False)
        self.series_data = data

        info = data.get("info", {})
        if isinstance(info, dict):
            plot = info.get("plot", "") or info.get("description", "")
            if plot:
                self.plot_label.setText(plot)
            genre = info.get("genre", "")
            year = info.get("releaseDate", "")
            if genre or year:
                self.meta_label.setText(f"Genre : {genre}  •  Année : {year}")

        # Extraction des saisons et épisodes
        episodes_raw = data.get("episodes", {})
        self.episodes_by_season = {}

        if isinstance(episodes_raw, dict):
            for season_key, ep_list in episodes_raw.items():
                items = ep_list if isinstance(ep_list, list) else (list(ep_list.values()) if isinstance(ep_list, dict) else [])
                s_str = str(season_key)
                if s_str not in self.episodes_by_season:
                    self.episodes_by_season[s_str] = []
                for ep in items:
                    if isinstance(ep, dict):
                        self.episodes_by_season[s_str].append(ep)
        elif isinstance(episodes_raw, list):
            for idx, item in enumerate(episodes_raw):
                if isinstance(item, list):
                    # Format liste de listes (ex: Euphoria où les saisons commencent à 0)
                    for ep in item:
                        if isinstance(ep, dict):
                            s_val = ep.get("season")
                            s_str = str(s_val) if s_val is not None and str(s_val).strip() != "" else str(idx)
                            if s_str not in self.episodes_by_season:
                                self.episodes_by_season[s_str] = []
                            self.episodes_by_season[s_str].append(ep)
                elif isinstance(item, dict):
                    # Format liste plate d'épisodes
                    s_val = item.get("season")
                    s_str = str(s_val) if s_val is not None and str(s_val).strip() != "" else "1"
                    if s_str not in self.episodes_by_season:
                        self.episodes_by_season[s_str] = []
                    self.episodes_by_season[s_str].append(item)

        # Remplissage de la liste des saisons
        self.season_combo.blockSignals(True)
        self.season_combo.clear()

        # Tri numérique des saisons
        sorted_seasons = sorted(self.episodes_by_season.keys(), key=lambda k: int(k) if k.isdigit() else 999)

        if not sorted_seasons:
            self.season_combo.addItem("Aucune saison disponible")
        else:
            default_idx = 0
            for idx, s in enumerate(sorted_seasons):
                ep_count = len(self.episodes_by_season[s])
                self.season_combo.addItem(f"Saison {s} ({ep_count} épisode{'s' if ep_count > 1 else ''})", userData=s)
                if s == "1":
                    default_idx = idx
            self.season_combo.setCurrentIndex(default_idx)

        self.season_combo.blockSignals(False)
        self._populate_episodes()

    def _on_series_data_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.plot_label.setText("Impossible de charger les épisodes de cette série.")
        QMessageBox.warning(self, "Erreur", f"Erreur lors de la récupération des épisodes :\n{err_msg}")

    def _on_season_changed(self):
        self._populate_episodes()

    def _populate_episodes(self):
        self.episodes_list.clear()
        selected_season = self.season_combo.currentData()
        if not selected_season or selected_season not in self.episodes_by_season:
            return

        client = None
        if self.playlist and self.playlist.playlist_type == "xtream":
            client = XtreamClient(
                server_url=self.playlist.server_url,
                username=self.playlist.username,
                password=self.playlist.password
            )

        episodes = self.episodes_by_season[selected_season]

        for ep in episodes:
            ep_num = ep.get("episode_num", 1)
            title = ep.get("title", f"Épisode {ep_num}")
            container = ep.get("container_extension", "mp4")
            ep_id = str(ep.get("id", ""))

            # Vérification de la reprise
            prog_text = ""
            icon_color = "#818cf8"
            if client and ep_id:
                ep_url = client.get_episode_stream_url(ep_id, container_extension=container)
                prog = self.db.get_playback_progress(stream_url=ep_url)
                if prog:
                    pos, _ = prog
                    s = int(pos)
                    m, s = divmod(s, 60)
                    h, m = divmod(m, 60)
                    t_str = f"{h}h{m:02d}m" if h > 0 else f"{m:02d}:{s:02d}"
                    prog_text = f"  [▶ Reprendre à {t_str}]"
                    icon_color = "#4ade80"

            item = QListWidgetItem(self.episodes_list)
            item.setIcon(get_icon("play_arrow", color=icon_color))
            item.setText(f"  Épisode {ep_num} — {title} ({container.upper()}){prog_text}")
            item.setData(Qt.ItemDataRole.UserRole, ep)

        if self.episodes_list.count() > 0:
            self.episodes_list.setCurrentRow(0)

    def _on_episode_double_clicked(self, item: QListWidgetItem):
        self._play_item(item)

    def _on_play_clicked(self):
        item = self.episodes_list.currentItem()
        if item:
            self._play_item(item)

    def _play_item(self, item: QListWidgetItem):
        ep_data = item.data(Qt.ItemDataRole.UserRole)
        if not ep_data or not self.playlist:
            return

        ep_id = str(ep_data.get("id", ""))
        season_num = self.season_combo.currentData() or "1"

        client = XtreamClient(
            server_url=self.playlist.server_url,
            username=self.playlist.username,
            password=self.playlist.password
        )

        # Construire la séquence complète ordonnée de tous les épisodes de la série
        all_series_episodes: List[Channel] = []
        current_ep_idx = 0
        sorted_seasons = sorted(self.episodes_by_season.keys(), key=lambda x: int(x) if x.isdigit() else 999)

        for s in sorted_seasons:
            for ep in self.episodes_by_season[s]:
                curr_ep_id = str(ep.get("id", ""))
                curr_ext = ep.get("container_extension", "mp4")
                curr_ep_num = ep.get("episode_num", 1)
                curr_ep_title = ep.get("title", f"Épisode {curr_ep_num}")
                curr_stream_url = client.get_episode_stream_url(curr_ep_id, container_extension=curr_ext)

                ep_ch = Channel(
                    playlist_id=self.playlist.id or 0,
                    name=f"{self.channel.name} — S{s}E{curr_ep_num} : {curr_ep_title}",
                    stream_url=curr_stream_url,
                    logo_url=self.channel.logo_url,
                    group_title=self.channel.group_title,
                    stream_type="series",
                    container_extension=curr_ext
                )

                if str(s) == str(season_num) and curr_ep_id == ep_id:
                    current_ep_idx = len(all_series_episodes)

                all_series_episodes.append(ep_ch)

        if all_series_episodes:
            selected_ep = all_series_episodes[current_ep_idx]
            self.episode_selected.emit(selected_ep)
            self.series_context_selected.emit(all_series_episodes, current_ep_idx)

        self.accept()

    def stop_worker(self):
        if self._worker:
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except Exception:
                pass
            self._worker.requestInterruption()
            self._worker.quit()
            self._worker.wait(500)
            self._worker = None

    def closeEvent(self, event):
        self.stop_worker()
        super().closeEvent(event)

