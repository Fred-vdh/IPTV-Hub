import os
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt6.QtGui import QPixmap

from core.models import Channel, Playlist, parse_movie_metadata
from core.database import Database
from core.xtream_client import XtreamClient
from core.image_loader import ImageLoader
from core.download_manager import DownloadManager, get_default_download_dir, DownloadTask
from ui.icons import get_icon
from ui.widgets.rounded_poster import RoundedPosterLabel


class MovieInfoWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, client: XtreamClient, stream_id: str, parent=None):
        super().__init__(parent)
        self.client = client
        self.stream_id = stream_id

    def run(self):
        try:
            data = self.client.get_vod_info(self.stream_id)
            if isinstance(data, dict):
                self.finished.emit(data)
        except Exception:
            pass


def format_seconds(seconds: float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m:02d}:{s:02d}"


class MovieDetailsDialog(QDialog):
    play_requested = pyqtSignal(Channel, float)
    progress_cleared = pyqtSignal(Channel)

    def __init__(self, channel: Channel, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.channel = channel
        self.db = db
        self.meta = parse_movie_metadata(channel.name, channel.rating, channel.year)
        self.playlist: Optional[Playlist] = self.db.get_playlist(channel.playlist_id)
        self.extra_info: Dict[str, Any] = {}
        self.download_task: Optional[DownloadTask] = None

        # Détection de la position de reprise
        prog = self.db.get_playback_progress(channel.id, channel.stream_url)
        self.resume_pos = prog[0] if prog else 0.0

        self.setWindowTitle(f"Détails - {channel.name}")
        self.setFixedSize(820, 480)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("""
            QDialog {
                background-color: #111827;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)

        self._init_ui()
        self._load_poster()
        self._fetch_extra_info()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        # ------------------ EN-TÊTE AVEC BOUTON FERMER ------------------
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        header_title = QLabel("FICHE DU FILM")
        header_title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
                border-color: #ef4444;
            }
        """)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        root_layout.addLayout(header_layout)

        # ------------------ CORPS : POSTER (GAUCHE) + INFOS (DROITE) ------------------
        body_layout = QHBoxLayout()
        body_layout.setSpacing(20)

        # 1. Affiche à gauche (180x270) avec coins arrondis
        self.poster_label = RoundedPosterLabel(radius=10, border_color="#334155", fallback_icon="movie", parent=self)
        self.poster_label.setFixedSize(180, 270)
        body_layout.addWidget(self.poster_label)

        # 2. Zone d'infos à droite
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)

        # Titre du film
        self.title_label = QLabel(self.channel.name)
        self.title_label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 700;")
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)

        # Ligne de Badges : Année, Qualité, Note, Catégorie
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(8)

        if self.meta.get("year"):
            year_lbl = QLabel(self.meta["year"])
            year_lbl.setStyleSheet("""
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
            badges_layout.addWidget(year_lbl)

        q_tag = self.meta.get("quality_tag")
        if q_tag:
            q_lbl = QLabel(q_tag)
            q_lbl.setStyleSheet("""
                background-color: #15803d;
                color: #ffffff;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
            badges_layout.addWidget(q_lbl)

        if self.meta.get("rating"):
            rat_lbl = QLabel(f"★ {self.meta['rating']} / 10")
            rat_lbl.setStyleSheet("""
                background-color: #0f172a;
                color: #4ade80;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
            badges_layout.addWidget(rat_lbl)

        grp_lbl = QLabel(self.channel.group_title)
        grp_lbl.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 500;")
        badges_layout.addWidget(grp_lbl)
        badges_layout.addStretch()

        info_layout.addLayout(badges_layout)

        # Métadonnées détaillées (Genre, Durée, Casting)
        self.details_label = QLabel()
        self.details_label.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.4;")
        self.details_label.setWordWrap(True)
        info_layout.addWidget(self.details_label)

        # Synopsis défilable
        synopsis_scroll = QScrollArea()
        synopsis_scroll.setWidgetResizable(True)
        synopsis_scroll.setStyleSheet("background: transparent; border: none;")

        self.synopsis_label = QLabel("Chargement des informations du film...")
        self.synopsis_label.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.5;")
        self.synopsis_label.setWordWrap(True)
        self.synopsis_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        synopsis_scroll.setWidget(self.synopsis_label)
        info_layout.addWidget(synopsis_scroll, stretch=1)

        body_layout.addLayout(info_layout, stretch=1)
        root_layout.addLayout(body_layout, stretch=1)

        # ------------------ PIED DE PAGE : ACTIONS ------------------
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        # 1. Bouton Favoris
        self.fav_btn = QPushButton()
        self._update_fav_btn()
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.clicked.connect(self._toggle_favorite)
        actions_layout.addWidget(self.fav_btn)

        # 2. Bouton Télécharger
        self.download_btn = QPushButton("  Télécharger")
        self.download_btn.setIcon(get_icon("file_download", color="#38bdf8"))
        self.download_btn.setIconSize(QSize(16, 16))
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_download_btn_style()
        self.download_btn.clicked.connect(self._on_download)
        actions_layout.addWidget(self.download_btn)

        actions_layout.addStretch()

        # 3. Bouton Annuler la reprise (si reprise disponible)
        if self.resume_pos > 0:
            self.clear_resume_btn = QPushButton("  Annuler reprise")
            self.clear_resume_btn.setIcon(get_icon("restart_alt", color="#f87171"))
            self.clear_resume_btn.setIconSize(QSize(16, 16))
            self.clear_resume_btn.setToolTip("Efface le point de reprise et remet la barre de progression à zéro")
            self.clear_resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.clear_resume_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #f87171;
                    border: 1px solid #7f1d1d;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #991b1b;
                    color: #ffffff;
                }
            """)
            self.clear_resume_btn.clicked.connect(self._on_clear_resume)
            actions_layout.addWidget(self.clear_resume_btn)

            # 4. Bouton Recommencer du début
            self.restart_btn = QPushButton("  Du début")
            self.restart_btn.setIcon(get_icon("replay", color="#cbd5e1"))
            self.restart_btn.setIconSize(QSize(16, 16))
            self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.restart_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #cbd5e1;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 8px 14px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #334155;
                    color: #ffffff;
                }
            """)
            self.restart_btn.clicked.connect(self._on_restart)
            actions_layout.addWidget(self.restart_btn)

        # 5. Bouton Principal (Reprendre ou Regarder)
        if self.resume_pos > 0:
            play_text = f"  Reprendre à {format_seconds(self.resume_pos)}"
        else:
            play_text = "  Regarder le film"

        self.play_btn = QPushButton(play_text)
        self.play_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
        self.play_btn.setIconSize(QSize(18, 18))
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.play_btn.clicked.connect(self._on_play)
        actions_layout.addWidget(self.play_btn)

        root_layout.addLayout(actions_layout)

    def _update_download_btn_style(self):
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: #ffffff;
            }
        """)

    def _on_clear_resume(self):
        self.db.clear_playback_progress(self.channel.id, self.channel.stream_url)
        self.resume_pos = 0.0
        self.play_btn.setText("  Regarder le film")
        if hasattr(self, "restart_btn") and self.restart_btn:
            self.restart_btn.hide()
        if hasattr(self, "clear_resume_btn") and self.clear_resume_btn:
            self.clear_resume_btn.hide()
        self.progress_cleared.emit(self.channel)

    def _on_download(self):
        settings = self.db.get_settings()
        dest_dir = settings.download_dir or get_default_download_dir()
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erreur de dossier", f"Impossible d'accéder au dossier de téléchargement :\n{dest_dir}\n\nErreur: {e}")
            return

        self.download_btn.setEnabled(False)
        self.download_btn.setText("  Téléchargement (0%)...")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
        """)

        headers = {}
        if self.channel.http_referrer:
            headers["Referer"] = self.channel.http_referrer
        if self.channel.extra_headers:
            headers.update(self.channel.extra_headers)

        ua = self.channel.user_agent or settings.user_agent
        self.download_task = DownloadManager.instance().start_download(
            url=self.channel.stream_url,
            dest_dir=dest_dir,
            base_name=self.channel.name,
            user_agent=ua,
            headers=headers
        )
        self.download_task.progress.connect(self._on_download_progress)
        self.download_task.finished.connect(self._on_download_finished)
        self.download_task.error.connect(self._on_download_error)

    def _on_download_progress(self, downloaded: int, total: int, speed: str):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.download_btn.setText(f"  {pct}% ({speed})")
        else:
            mb = downloaded / (1024 * 1024)
            self.download_btn.setText(f"  {mb:.1f} Mo ({speed})")

    def _on_download_finished(self, output_path: str):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("  ✓ Téléchargé (Ouvrir)")
        self.download_btn.setIcon(get_icon("check_circle", color="#4ade80"))
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                color: #4ade80;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #047857;
                color: #ffffff;
            }
        """)
        try:
            self.download_btn.clicked.disconnect()
        except Exception:
            pass
        self.download_btn.clicked.connect(lambda: os.startfile(os.path.dirname(output_path)))

    def _on_download_error(self, err_msg: str):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("  Télécharger")
        self.download_btn.setIcon(get_icon("file_download", color="#38bdf8"))
        self._update_download_btn_style()

    def _update_fav_btn(self):
        is_fav = bool(self.channel.is_favorite)
        text = "  Retirer des favoris" if is_fav else "  Ajouter aux favoris"
        icon_name = "favorite" if is_fav else "favorite_border"

        self.fav_btn.setText(text)
        self.fav_btn.setIcon(get_icon(icon_name, color="#f43f5e"))
        self.fav_btn.setIconSize(QSize(16, 16))
        if is_fav:
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(244, 63, 94, 0.15);
                    color: #f43f5e;
                    border: 1px solid rgba(244, 63, 94, 0.4);
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: rgba(244, 63, 94, 0.25);
                }
            """)
        else:
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #cbd5e1;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #242f44;
                    border-color: #f43f5e;
                    color: #f43f5e;
                }
            """)

    def _toggle_favorite(self):
        new_fav = not self.channel.is_favorite
        self.channel.is_favorite = new_fav
        if self.channel.id:
            self.db.toggle_favorite(self.channel.id, new_fav)
        self._update_fav_btn()

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)

    def reject(self):
        self._cleanup()
        super().reject()

    def accept(self):
        self._cleanup()
        super().accept()

    def _cleanup(self):
        try:
            loader = ImageLoader.instance()
            loader.image_loaded.disconnect(self._on_poster_loaded)
        except Exception:
            pass
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(500)

    def _on_play(self):
        self.accept()
        self.play_requested.emit(self.channel, self.resume_pos)

    def _on_restart(self):
        self.db.clear_playback_progress(self.channel.id, self.channel.stream_url)
        self.accept()
        self.play_requested.emit(self.channel, 0.0)

    def _load_poster(self):
        if not self.channel.logo_url:
            self.poster_label.clear()
            return

        loader = ImageLoader.instance()
        cached = loader.get_cached_image(self.channel.logo_url)
        if cached:
            self._set_poster_pixmap(cached)
        else:
            self.poster_label.clear()
            loader.image_loaded.connect(self._on_poster_loaded)
            loader.request_image_priority(self.channel.logo_url)

    def _on_poster_loaded(self, url: str, pixmap: QPixmap):
        if url == self.channel.logo_url:
            self._set_poster_pixmap(pixmap)

    def _set_poster_pixmap(self, pixmap: QPixmap):
        self.poster_label.setPixmap(pixmap)

    def _fetch_extra_info(self):
        if self.playlist and self.playlist.playlist_type == "xtream" and self.channel.stream_id:
            client = XtreamClient(
                self.playlist.server_url,
                self.playlist.username,
                self.playlist.password,
                self.channel.user_agent or self.playlist.user_agent
            )
            self.worker = MovieInfoWorker(client, self.channel.stream_id, self)
            self.worker.finished.connect(self._on_extra_info_loaded)
            self.worker.start()
        else:
            # Info par défaut
            self.synopsis_label.setText(
                f"Film : {self.channel.name}\nCatégorie : {self.channel.group_title}\n\n"
                "Prêt pour le streaming en haute définition."
            )

    def _on_extra_info_loaded(self, data: dict):
        info = data.get("info", {})
        if not info:
            info = data.get("movie_data", {})

        # Si l'affiche est présente dans les métadonnées et différente, la charger immédiatement
        cover = info.get("movie_image", "") or info.get("cover_big", "") or info.get("cover", "")
        if cover and cover.startswith("http"):
            if not self.channel.logo_url or self.poster_label.pixmap() is None or self.poster_label.pixmap().isNull():
                self.channel.logo_url = cover
                if self.channel.id:
                    self.db.update_channel_logo(self.channel.id, cover)
                ImageLoader.instance().request_image_priority(cover)

        plot = info.get("plot") or info.get("description") or "Aucun résumé disponible pour ce film."
        genre = info.get("genre", "")
        duration = info.get("duration", "")
        director = info.get("director", "")
        cast = info.get("cast", "")

        details_txt = []
        if genre:
            details_txt.append(f"<b>Genre :</b> {genre}")
        if duration:
            details_txt.append(f"<b>Durée :</b> {duration}")
        if director:
            details_txt.append(f"<b>Réalisateur :</b> {director}")
        if cast:
            details_txt.append(f"<b>Acteurs :</b> {cast}")

        self.details_label.setText("<br>".join(details_txt))
        self.synopsis_label.setText(plot)
