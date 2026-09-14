"""
Dialogue de gestion des listes de lecture enregistrées dans SQLite (Ajout, Modification, Synchronisation, Suppression).
Cartes spacieuses et confortables avec une hauteur généreuse pour une visibilité totale de toutes les informations.
"""

from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QMessageBox, QFrame, QWidget,
    QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread

from core.models import Playlist
from core.database import Database
from core.xtream_client import XtreamClient
from ui.icons import get_icon, DEFAULT_ICON_COLOR
from ui.dialogs.add_playlist import AddPlaylistDialog, PlaylistImportWorker
from core.i18n import tr, get_locale_month


def _format_exp_date(exp_str: Optional[str]) -> str:
    if not exp_str:
        return tr("Inconnue")
    try:
        from core.i18n import I18nManager
        val = int(exp_str)
        dt = datetime.fromtimestamp(val)
        m_name = get_locale_month(dt.month, short=True)
        lang = I18nManager.instance().current_language
        date_str = f"{m_name} {dt.day}, {dt.year}" if lang == "en" else f"{dt.day} {m_name} {dt.year}"
        now = datetime.now()
        days_left = (dt - now).days
        if days_left > 0:
            return f"{date_str} (" + tr("{days} j restants", days=days_left) + ")"
        elif days_left == 0:
            return tr("Aujourd'hui, {time}", time=dt.strftime('%H:%M'))
        else:
            return tr("Expiré ({date})", date=date_str)
    except Exception:
        return str(exp_str)


class _AccountWorker(QThread):
    finished_info = pyqtSignal(dict)
    info_fetched = finished_info  # Alias de compatibilité

    def __init__(self, playlist: Playlist, parent=None):
        super().__init__(parent)
        self.playlist = playlist

    def run(self):
        try:
            client = XtreamClient(
                self.playlist.server_url,
                self.playlist.username,
                self.playlist.password
            )
            auth_data = client.authenticate()
            u_info = auth_data.get("user_info", {})
            self.finished_info.emit({
                "account_status": u_info.get("status", "Active"),
                "exp_date": str(u_info.get("exp_date", "")),
                "max_connections": str(u_info.get("max_connections", "1")),
                "active_cons": str(u_info.get("active_cons", "0"))
            })
        except Exception:
            pass


class PlaylistItemWidget(QFrame):
    delete_clicked = pyqtSignal(int)
    edit_clicked = pyqtSignal(object)  # Playlist
    sync_clicked = pyqtSignal(object)  # Playlist

    def __init__(
        self,
        playlist: Playlist,
        db: Optional[Database] = None,
        is_currently_playing: bool = False,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.playlist = playlist
        self.db = db
        self.is_currently_playing = is_currently_playing
        self._worker: Optional[_AccountWorker] = None
        self._init_ui()
        self._check_account_info()

    def _init_ui(self):
        self.setMinimumHeight(116)
        self.setStyleSheet("""
            PlaylistItemWidget {
                background-color: #222b3d;
                border: 1px solid #33415c;
                border-radius: 10px;
            }
            PlaylistItemWidget:hover {
                background-color: #263147;
                border-color: #435579;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)

        # 1. Icône de type de playlist (44x44)
        icon_name = "account_circle" if self.playlist.playlist_type == "xtream" else "link"
        type_btn = QPushButton()
        type_btn.setIcon(get_icon(icon_name, color="#818cf8"))
        type_btn.setIconSize(QSize(26, 26))
        type_btn.setFixedSize(44, 44)
        type_btn.setStyleSheet("""
            background-color: #2b364c;
            border: 1px solid #3b4b69;
            border-radius: 8px;
        """)
        layout.addWidget(type_btn)

        # 2. Informations détaillées de la liste
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        name_row = QHBoxLayout()
        name_row.setSpacing(10)

        name_label = QLabel(self.playlist.name)
        name_label.setStyleSheet("font-weight: 700; font-size: 16px; color: #f8fafc;")
        name_row.addWidget(name_label)

        type_badge = QLabel(self.playlist.playlist_type.upper())
        type_badge.setStyleSheet("""
            background-color: #2e3952;
            color: #a5b4fc;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #435272;
        """)
        name_row.addWidget(type_badge)
        name_row.addStretch()
        info_layout.addLayout(name_row)

        # Découpage du chiffre global en 3 : chaînes TV, films et séries
        if self.db and self.playlist.id:
            try:
                counts = self.db.get_playlist_stream_counts(self.playlist.id)
                live_c = counts.get("live", 0)
                movie_c = counts.get("movie", 0)
                series_c = counts.get("series", 0)
                live_str = f"{live_c:,} {tr('chaînes TV')}".replace(",", " ")
                movie_str = f"{movie_c:,} {tr('films')}".replace(",", " ")
                series_str = f"{series_c:,} {tr('séries')}".replace(",", " ")
                counts_text = f"{live_str}   •   {movie_str}   •   {series_str}"
            except Exception:
                counts_text = f"{self.playlist.channel_count:,} {tr('chaînes')}".replace(",", " ")
        else:
            counts_text = f"{self.playlist.channel_count:,} {tr('chaînes')}".replace(",", " ")

        counts_label = QLabel(counts_text)
        counts_label.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 600;")
        info_layout.addWidget(counts_label)

        # Source (URL / Serveur) placée sur sa propre ligne sous les chaînes
        src_info = self.playlist.server_url if self.playlist.playlist_type == "xtream" else self.playlist.url_or_path
        display_src = src_info
        if len(display_src) > 75:
            display_src = display_src[:72] + "..."
        source_label = QLabel(tr("Source : {source}", source=display_src))
        source_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 400;")
        source_label.setToolTip(src_info)
        info_layout.addWidget(source_label)

        # Rangée de badges compte Xtream (Statut, Expiration, Connexions)
        self.account_row_widget = QWidget()
        self.account_row = QHBoxLayout(self.account_row_widget)
        self.account_row.setContentsMargins(0, 2, 0, 0)
        self.account_row.setSpacing(8)

        if self.playlist.playlist_type == "xtream":
            self.status_badge = QLabel()
            self.exp_badge = QLabel()
            self.conn_badge = QLabel()
            self.account_row.addWidget(self.status_badge)
            self.account_row.addWidget(self.exp_badge)
            self.account_row.addWidget(self.conn_badge)
            self.account_row.addStretch()
            info_layout.addWidget(self.account_row_widget)
            self._update_account_badges()
        else:
            self.account_row_widget.hide()

        layout.addLayout(info_layout, stretch=1)

        # 3. Boutons d'action confortables et aérés
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Synchroniser / Recharger
        sync_btn = QPushButton(" " + tr("Recharger"))
        sync_btn.setIcon(get_icon("sync", color=DEFAULT_ICON_COLOR))
        sync_btn.setIconSize(QSize(16, 16))
        sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sync_btn.setToolTip(tr("Recharger et synchroniser les flux depuis le serveur"))
        sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b364c;
                border: 1px solid #3b4b69;
                border-radius: 8px;
                padding: 7px 15px;
                color: #f1f5f9;
                font-size: 12px;
                font-weight: 600;
                min-width: 98px;
                min-height: 34px;
            }
            QPushButton:hover {
                background-color: #364460;
                color: #818cf8;
                border-color: #818cf8;
            }
        """)
        sync_btn.clicked.connect(lambda: self.sync_clicked.emit(self.playlist))
        btn_layout.addWidget(sync_btn)

        # Modifier
        edit_btn = QPushButton(" " + tr("Modifier"))
        edit_btn.setIcon(get_icon("edit", color=DEFAULT_ICON_COLOR))
        edit_btn.setIconSize(QSize(16, 16))
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setToolTip(tr("Modifier les identifiants ou l'URL de cette liste"))
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b364c;
                border: 1px solid #3b4b69;
                border-radius: 8px;
                padding: 7px 15px;
                color: #f1f5f9;
                font-size: 12px;
                font-weight: 600;
                min-width: 90px;
                min-height: 34px;
            }
            QPushButton:hover {
                background-color: #364460;
                color: #6366f1;
                border-color: #6366f1;
            }
        """)
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.playlist))
        btn_layout.addWidget(edit_btn)

        # Supprimer
        del_btn = QPushButton(" " + tr("Supprimer"))
        del_btn.setIcon(get_icon("delete", color="#f87171"))
        del_btn.setIconSize(QSize(16, 16))
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip(tr("Supprimer cette liste de lecture et ses chaînes de SQLite"))
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 8px;
                padding: 7px 15px;
                font-size: 12px;
                font-weight: 600;
                min-width: 98px;
                min-height: 34px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
                border-color: #ef4444;
            }
        """)
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.playlist.id))
        btn_layout.addWidget(del_btn)

        layout.addLayout(btn_layout)

    def _format_exp_date(self, exp_val: Optional[str]) -> str:
        if not exp_val or exp_val == "None" or exp_val == "0":
            return tr("Illimitée")
        try:
            ts = float(exp_val)
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%d/%m/%Y")
        except (ValueError, OSError):
            return str(exp_val)[:10]

    def _update_account_badges(self):
        if self.playlist.playlist_type != "xtream":
            return

        status = (self.playlist.account_status or "Inconnu").strip()
        status_lower = status.lower()
        if status_lower in ("active", "actif"):
            status_text = tr("Actif")
            status_color = "#10b981"
            status_bg = "rgba(16, 185, 129, 0.15)"
            status_border = "rgba(16, 185, 129, 0.35)"
        elif status_lower in ("expired", "expiré", "banned", "disabled"):
            status_text = tr("Expiré") if "expir" in status_lower else tr("Inactif")
            status_color = "#ef4444"
            status_bg = "rgba(239, 68, 68, 0.15)"
            status_border = "rgba(239, 68, 68, 0.35)"
        else:
            status_text = status if status != "Inconnu" else tr("Inconnu")
            status_color = "#94a3b8"
            status_bg = "rgba(148, 163, 184, 0.15)"
            status_border = "rgba(148, 163, 184, 0.35)"

        self.status_badge.setText(f"● {status_text}")
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {status_bg};
                color: {status_color};
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 4px;
                border: 1px solid {status_border};
            }}
        """)

        # Expiration
        exp_str = self._format_exp_date(self.playlist.exp_date)
        self.exp_badge.setText(tr("Expiration : {date}", date=exp_str))
        self.exp_badge.setStyleSheet("""
            QLabel {
                background-color: #2b364c;
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 500;
                padding: 2px 8px;
                border-radius: 4px;
                border: 1px solid #3b4b69;
            }
        """)

        # Écrans connectés / max (prise en compte du serveur Xtream ET de la lecture en cours sur l'application)
        max_c = self.playlist.max_connections or "1"
        try:
            server_act = int(self.playlist.active_cons or 0)
        except (ValueError, TypeError):
            server_act = 0

        local_act = 1 if getattr(self, "is_currently_playing", False) else 0
        total_act = max(server_act, local_act)
        self.conn_badge.setText(tr("Écrans : {active} / {max}", active=total_act, max=max_c))

        if total_act > 0:
            self.conn_badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(56, 189, 248, 0.15);
                    color: #38bdf8;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 8px;
                    border-radius: 4px;
                    border: 1px solid rgba(56, 189, 248, 0.35);
                }
            """)
        else:
            self.conn_badge.setStyleSheet("""
                QLabel {
                    background-color: #2b364c;
                    color: #cbd5e1;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 2px 8px;
                    border-radius: 4px;
                    border: 1px solid #3b4b69;
                }
            """)

    def _check_account_info(self):
        if self.playlist.playlist_type != "xtream":
            return
        if not (self.playlist.server_url and self.playlist.username and self.playlist.password):
            return
        # Rafraîchissement systématique en arrière-plan des métadonnées du compte et du nombre d'écrans réels
        try:
            self._worker = _AccountWorker(self.playlist, self)
            self._worker.finished_info.connect(self._on_account_info_fetched)
            self._worker.start()
        except Exception:
            pass

    def closeEvent(self, event):
        if getattr(self, "_worker", None) and self._worker.isRunning():
            self._worker.quit()
        super().closeEvent(event)

    def _on_account_info_fetched(self, data: dict):
        self.playlist.account_status = data.get("account_status", "")
        self.playlist.exp_date = data.get("exp_date", "")
        self.playlist.max_connections = data.get("max_connections", "1")
        self.playlist.active_cons = data.get("active_cons", "0")
        if self.db:
            try:
                self.db.update_playlist_account_info(
                    self.playlist.id,
                    self.playlist.account_status,
                    self.playlist.exp_date,
                    self.playlist.max_connections,
                    self.playlist.active_cons
                )
            except Exception:
                pass
        self._update_account_badges()


class ManagePlaylistsDialog(QDialog):
    playlists_modified = pyqtSignal()

    def __init__(
        self,
        db: Database,
        currently_playing_playlist_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.db = db
        self.currently_playing_playlist_id = currently_playing_playlist_id
        self.setWindowTitle(tr("Gestion des listes de lecture"))
        self.resize(960, 620)
        self.setMinimumSize(840, 520)
        self._sync_worker: Optional[PlaylistImportWorker] = None
        self._init_ui()
        self._load_playlists()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1b2232;
                color: #e2e8f0;
            }
            QListWidget {
                background-color: #1b2232;
                border: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # En-tête avec bouton d'ajout
        header_row = QHBoxLayout()
        header_label = QLabel(tr("Listes de lecture enregistrées"))
        header_label.setStyleSheet("font-size: 19px; font-weight: 700; color: #ffffff;")
        header_row.addWidget(header_label)
        header_row.addStretch()

        add_btn = QPushButton(" " + tr("Ajouter une liste"))
        add_btn.setIcon(get_icon("add", color="#ffffff"))
        add_btn.setIconSize(QSize(18, 18))
        add_btn.setProperty("class", "primary-btn")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_new_clicked)
        header_row.addWidget(add_btn)

        layout.addLayout(header_row)

        # Statut de synchronisation & barre de progression
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #818cf8; font-weight: 500; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Liste des playlists
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setSpacing(8)
        layout.addWidget(self.list_widget)

        # Bouton fermer
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        close_btn = QPushButton(" " + tr("Fermer"))
        close_btn.setIcon(get_icon("close", color=DEFAULT_ICON_COLOR))
        close_btn.setIconSize(QSize(18, 18))
        close_btn.setProperty("class", "secondary-btn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _load_playlists(self):
        self.list_widget.clear()
        playlists = self.db.get_playlists()

        if not playlists:
            item = QListWidgetItem(self.list_widget)
            lbl = QLabel(tr("Aucune liste de lecture enregistrée dans la base SQLite.\nCliquez sur 'Ajouter une liste' pour importer vos chaînes Xtream ou M3U."))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #64748b; font-size: 14px; padding: 40px; line-height: 1.6;")
            item.setSizeHint(QSize(0, 120))
            self.list_widget.setItemWidget(item, lbl)
            return

        for p in playlists:
            item = QListWidgetItem(self.list_widget)
            is_playing = bool(self.currently_playing_playlist_id and p.id == self.currently_playing_playlist_id)
            widget = PlaylistItemWidget(p, db=self.db, is_currently_playing=is_playing)
            widget.delete_clicked.connect(self._on_delete_playlist)
            widget.edit_clicked.connect(self._on_edit_playlist)
            widget.sync_clicked.connect(self._on_sync_playlist)
            # Hauteur généreuse de 128px pour aérer chaque ligne d'information et les boutons
            item.setSizeHint(QSize(0, 128))
            self.list_widget.setItemWidget(item, widget)

    def _on_add_new_clicked(self):
        dlg = AddPlaylistDialog(self.db, parent=self)
        if dlg.exec():
            self.playlists_modified.emit()
            self._load_playlists()

    def _on_edit_playlist(self, playlist: Playlist):
        dlg = AddPlaylistDialog(self.db, playlist=playlist, parent=self)
        if dlg.exec():
            self.playlists_modified.emit()
            self._load_playlists()

    def _on_sync_playlist(self, playlist: Playlist):
        self.status_label.setText(tr("Synchronisation de '{name}' en cours...", name=playlist.name))
        self.progress_bar.setVisible(True)

        self._sync_worker = PlaylistImportWorker(self.db, playlist, self)
        self._sync_worker.progress.connect(self.status_label.setText)
        self._sync_worker.finished_success.connect(self._on_sync_finished)
        self._sync_worker.error.connect(self._on_sync_error)
        self._sync_worker.start()

    def _on_sync_finished(self, _playlist_id: int):
        self.progress_bar.setVisible(False)
        self.status_label.setText(tr("Synchronisation réussie !"))
        self.playlists_modified.emit()
        self._load_playlists()

    def _on_sync_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        QMessageBox.critical(self, tr("Erreur de synchronisation"), tr("Impossible de synchroniser la liste :\n{error}", error=err_msg))

    def _on_delete_playlist(self, playlist_id: int):
        reply = QMessageBox.question(
            self,
            tr("Confirmer la suppression"),
            tr("Êtes-vous sûr de vouloir supprimer cette liste de lecture et toutes ses chaînes de SQLite ?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_playlist(playlist_id)
            self.playlists_modified.emit()
            self._load_playlists()

    def closeEvent(self, event):
        if self._sync_worker and self._sync_worker.isRunning():
            try:
                self._sync_worker.terminate()
                self._sync_worker.wait(500)
            except Exception:
                pass
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            w = self.list_widget.itemWidget(item)
            if isinstance(w, PlaylistItemWidget) and w._worker and w._worker.isRunning():
                try:
                    w._worker.terminate()
                    w._worker.wait(500)
                except Exception:
                    pass
        super().closeEvent(event)
