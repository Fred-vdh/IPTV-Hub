"""
Vue dédiée aux Téléchargements dans IPTV Hub (calquée sur IPTV Hub Android).
Affiche les téléchargements en cours (avec progression, vitesse, pause/reprise, annulation),
les téléchargements terminés (lecture hors-ligne, suppression), et les statistiques de stockage.
"""

from typing import Dict, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QProgressBar, QGridLayout, QMessageBox
)

from core.download_manager import (
    DownloadManager, DownloadItem, DownloadStatus
)
from ui.icons import get_icon
from core.i18n import tr
from core.image_loader import ImageLoader
from ui.widgets.rounded_poster import RoundedPosterLabel


class OngoingDownloadCard(QFrame):
    """Carte horizontale représentant un téléchargement en cours, en pause, ou en attente."""
    pause_resume_clicked = pyqtSignal(DownloadItem)
    cancel_clicked = pyqtSignal(DownloadItem)

    def __init__(self, item: DownloadItem, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("ongoingDownloadCard")
        self.setStyleSheet("""
            QFrame#ongoingDownloadCard {
                background-color: #161f30;
                border: 1px solid #1e293b;
                border-radius: 10px;
            }
            QFrame#ongoingDownloadCard:hover {
                border-color: #334155;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(16)

        # 1. Vignette (60x90)
        self.thumb = RoundedPosterLabel(radius=6, border_color="#1e293b", fallback_icon="movie", parent=self)
        self.thumb.setFixedSize(60, 90)
        if item.poster_url:
            cached = ImageLoader.instance().get_cached_image(item.poster_url)
            if cached:
                self.thumb.set_pixmap(cached)
            else:
                ImageLoader.instance().load_image(
                    item.poster_url,
                    on_success=lambda px: self.thumb.set_pixmap(px) if self.thumb else None
                )
        layout.addWidget(self.thumb)

        # 2. Informations centrales
        info_col = QVBoxLayout()
        info_col.setSpacing(6)

        self.title_lbl = QLabel(item.title)
        self.title_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: 700;")
        info_col.addWidget(self.title_lbl)

        sub_text = item.sub_title if item.sub_title else (f"{tr('Film')} • {item.container_extension.upper()}")
        self.sub_lbl = QLabel(sub_text)
        self.sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_col.addWidget(self.sub_lbl)

        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(item.progress_percent)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0f172a;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 3px;
            }
        """)
        info_col.addWidget(self.progress_bar)

        # Ligne d'état (progression + vitesse/statut)
        status_row = QHBoxLayout()
        status_row.setSpacing(10)

        self.prog_info_lbl = QLabel(item.get_formatted_progress())
        self.prog_info_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        status_row.addWidget(self.prog_info_lbl)

        status_row.addStretch()

        self.speed_status_lbl = QLabel()
        self.speed_status_lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
        status_row.addWidget(self.speed_status_lbl)

        info_col.addLayout(status_row)
        layout.addLayout(info_col, stretch=1)

        # 3. Boutons d'action
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.pause_resume_btn = QPushButton()
        self.pause_resume_btn.setFixedSize(36, 36)
        self.pause_resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #475569;
            }
        """)
        self.pause_resume_btn.clicked.connect(lambda: self.pause_resume_clicked.emit(self.item))
        btn_box.addWidget(self.pause_resume_btn)

        self.cancel_btn = QPushButton()
        self.cancel_btn.setFixedSize(36, 36)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setIcon(get_icon("close", color="#f87171"))
        self.cancel_btn.setIconSize(QSize(16, 16))
        self.cancel_btn.setToolTip(tr("Annuler le téléchargement"))
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #7f1d1d;
                border-color: #ef4444;
            }
        """)
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.item))
        btn_box.addWidget(self.cancel_btn)

        layout.addLayout(btn_box)

        self.update_state(item)

    def update_state(self, item: DownloadItem):
        self.item = item
        self.progress_bar.setValue(item.progress_percent)
        self.prog_info_lbl.setText(item.get_formatted_progress())

        if item.status == DownloadStatus.DOWNLOADING:
            self.pause_resume_btn.setIcon(get_icon("pause", color="#ffffff"))
            self.pause_resume_btn.setToolTip(tr("Mettre en pause"))
            is_reconnecting = bool(item.error_message and item.error_message.startswith("Reconnexion"))
            if is_reconnecting:
                self.speed_status_lbl.setText(item.error_message)
                self.speed_status_lbl.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: 600;")
            else:
                self.speed_status_lbl.setText(item.get_formatted_speed())
                self.speed_status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        elif item.status == DownloadStatus.PAUSED:
            self.pause_resume_btn.setIcon(get_icon("play_arrow", color="#ffffff"))
            self.pause_resume_btn.setToolTip(tr("Reprendre"))
            txt = item.error_message if item.error_message else tr("En pause")
            self.speed_status_lbl.setText(txt)
            self.speed_status_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        elif item.status == DownloadStatus.QUEUED:
            self.pause_resume_btn.setIcon(get_icon("pause", color="#ffffff"))
            self.pause_resume_btn.setToolTip(tr("Mettre en pause"))
            self.speed_status_lbl.setText(tr("En attente..."))
            self.speed_status_lbl.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: 600;")
        elif item.status == DownloadStatus.ERROR:
            self.pause_resume_btn.setIcon(get_icon("replay", color="#ef4444"))
            self.pause_resume_btn.setToolTip(tr("Relancer"))
            txt = item.error_message if item.error_message else tr("Interrompu • Relancer")
            self.speed_status_lbl.setText(txt)
            self.speed_status_lbl.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 600;")


class CompletedDownloadCard(QFrame):
    """Carte affiche pour un téléchargement terminé avec badge hors-ligne et bouton suppression."""
    clicked = pyqtSignal(DownloadItem)
    delete_clicked = pyqtSignal(DownloadItem)

    def __init__(self, item: DownloadItem, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self.setFixedSize(160, 270)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("completedDownloadCard")
        self.setStyleSheet("""
            QFrame#completedDownloadCard {
                background-color: #161f30;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QFrame#completedDownloadCard:hover {
                border-color: #38bdf8;
                background-color: #1e293b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Conteneur pour le poster avec overlays (badge + bouton suppression)
        poster_container = QWidget(self)
        poster_container.setFixedSize(144, 200)

        self.poster_label = RoundedPosterLabel(radius=6, border_color="#0f172a", fallback_icon="movie", parent=poster_container)
        self.poster_label.setGeometry(0, 0, 144, 200)

        if item.poster_url:
            cached = ImageLoader.instance().get_cached_image(item.poster_url)
            if cached:
                self.poster_label.set_pixmap(cached)
            else:
                ImageLoader.instance().load_image(
                    item.poster_url,
                    on_success=lambda px: self.poster_label.set_pixmap(px) if self.poster_label else None
                )

        # Badge "✓ HORS LIGNE"
        self.badge_lbl = QLabel(tr("✓ HORS LIGNE"), poster_container)
        self.badge_lbl.setStyleSheet("""
            background-color: rgba(6, 78, 59, 0.9);
            color: #34d399;
            font-size: 9px;
            font-weight: 700;
            padding: 3px 6px;
            border-radius: 4px;
            border: 1px solid rgba(5, 150, 105, 0.6);
        """)
        self.badge_lbl.move(6, 6)

        # Bouton poubelle (supprimer)
        self.del_btn = QPushButton(poster_container)
        self.del_btn.setFixedSize(28, 28)
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setIcon(get_icon("delete", color="#f87171"))
        self.del_btn.setIconSize(QSize(14, 14))
        self.del_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(15, 23, 42, 0.85);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                border-color: #ef4444;
            }
        """)
        self.del_btn.setToolTip(tr("Supprimer du disque"))
        self.del_btn.move(144 - 28 - 6, 6)
        self.del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.item))

        layout.addWidget(poster_container)

        # Titre
        self.title_lbl = QLabel(item.title)
        self.title_lbl.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 700;")
        self.title_lbl.setWordWrap(False)
        self.title_lbl.setFixedHeight(16)
        layout.addWidget(self.title_lbl)

        # Sous-titre / Taille
        sub = item.sub_title if item.sub_title else item.get_formatted_size()
        self.sub_lbl = QLabel(f"{sub} • {item.get_formatted_size()}")
        self.sub_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self.sub_lbl.setWordWrap(False)
        self.sub_lbl.setFixedHeight(14)
        layout.addWidget(self.sub_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Ne pas déclencher la lecture si on a cliqué sur le bouton de suppression
            child = self.childAt(event.position().toPoint())
            if child != self.del_btn:
                self.clicked.emit(self.item)
        super().mousePressEvent(event)


class DownloadsView(QWidget):
    """
    Vue principale affichant l'ensemble des téléchargements IPTV Hub.
    """
    play_download_requested = pyqtSignal(DownloadItem)

    def __init__(self, db, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.mgr = DownloadManager.instance()
        self._ongoing_cards: Dict[str, OngoingDownloadCard] = {}

        self._init_ui()

        # Connecter les signaux du DownloadManager
        self.mgr.download_progress.connect(self._on_download_progress)
        self.mgr.download_status_changed.connect(self._on_status_changed)
        self.mgr.downloads_changed.connect(self.refresh)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. En-tête de la vue (64px, fond #161f30)
        header_widget = QWidget()
        header_widget.setFixedHeight(64)
        header_widget.setStyleSheet("background-color: #161f30; border-bottom: 1px solid #1e293b;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("file_download", color="#6366f1").pixmap(26, 26))
        header_layout.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QLabel(tr("Téléchargements"))
        self.title_lbl.setStyleSheet("color: #f8fafc; font-size: 18px; font-weight: 700;")
        title_col.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel(tr("Gérez vos vidéos téléchargées pour une lecture hors-ligne"))
        self.subtitle_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_col.addWidget(self.subtitle_lbl)

        header_layout.addLayout(title_col, stretch=1)

        # Statistiques de stockage
        stats_col = QVBoxLayout()
        stats_col.setSpacing(2)
        stats_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.storage_free_lbl = QLabel()
        self.storage_free_lbl.setStyleSheet("color: #34d399; font-size: 12px; font-weight: 700;")
        self.storage_free_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats_col.addWidget(self.storage_free_lbl)

        self.storage_used_lbl = QLabel()
        self.storage_used_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.storage_used_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        stats_col.addWidget(self.storage_used_lbl)

        header_layout.addLayout(stats_col)
        root_layout.addWidget(header_widget)

        # 2. Zone de défilement principale
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #0b0f19; }")

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: #0b0f19;")
        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setContentsMargins(24, 20, 24, 24)
        self.content_layout.setSpacing(20)

        # --- Section En cours ---
        self.ongoing_section = QWidget()
        self.ongoing_layout = QVBoxLayout(self.ongoing_section)
        self.ongoing_layout.setContentsMargins(0, 0, 0, 0)
        self.ongoing_layout.setSpacing(10)

        self.ongoing_header = QLabel(tr("Téléchargements en cours (0)"))
        self.ongoing_header.setStyleSheet("color: #a5b4fc; font-size: 15px; font-weight: 700;")
        self.ongoing_layout.addWidget(self.ongoing_header)

        self.ongoing_cards_container = QVBoxLayout()
        self.ongoing_cards_container.setSpacing(10)
        self.ongoing_layout.addLayout(self.ongoing_cards_container)

        self.content_layout.addWidget(self.ongoing_section)

        # --- Section Terminés ---
        self.completed_section = QWidget()
        self.completed_layout = QVBoxLayout(self.completed_section)
        self.completed_layout.setContentsMargins(0, 0, 0, 0)
        self.completed_layout.setSpacing(10)

        comp_header_row = QHBoxLayout()
        self.completed_header = QLabel(tr("Téléchargements terminés (0)"))
        self.completed_header.setStyleSheet("color: #a5b4fc; font-size: 15px; font-weight: 700;")
        comp_header_row.addWidget(self.completed_header)
        comp_header_row.addStretch()

        self.completed_layout.addLayout(comp_header_row)

        self.completed_grid = QGridLayout()
        self.completed_grid.setSpacing(16)
        self.completed_layout.addLayout(self.completed_grid)

        self.content_layout.addWidget(self.completed_section)

        # --- État vide ---
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(0, 60, 0, 60)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)

        empty_icon = QLabel()
        empty_icon.setPixmap(get_icon("file_download", color="#475569").pixmap(56, 56))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_title = QLabel(tr("Aucun téléchargement"))
        empty_title.setStyleSheet("color: #f1f5f9; font-size: 18px; font-weight: 700;")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)

        empty_desc = QLabel(tr("Téléchargez vos films et épisodes préférés pour les regarder même sans connexion Internet."))
        empty_desc.setStyleSheet("color: #64748b; font-size: 13px;")
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_desc)

        self.content_layout.addWidget(self.empty_widget)

        self.content_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll_area)

    def refresh(self):
        """Met à jour l'affichage de l'ensemble de la vue."""
        # 1. Mise à jour du stockage
        stats = self.mgr.get_disk_stats()
        self.storage_free_lbl.setText(stats.get_formatted_available())
        self.storage_used_lbl.setText(stats.get_formatted_occupied())

        ongoing = self.mgr.get_ongoing_downloads()
        completed = self.mgr.get_completed_downloads()

        # 2. Section En cours
        self._ongoing_cards.clear()
        # Vider le conteneur
        while self.ongoing_cards_container.count() > 0:
            child = self.ongoing_cards_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if ongoing:
            self.ongoing_section.show()
            self.ongoing_header.setText(tr("Téléchargements en cours ({count})", count=len(ongoing)))
            for item in ongoing:
                card = OngoingDownloadCard(item, parent=self.ongoing_section)
                card.pause_resume_clicked.connect(self._on_pause_resume_item)
                card.cancel_clicked.connect(self._on_cancel_item)
                self.ongoing_cards_container.addWidget(card)
                self._ongoing_cards[item.id] = card
        else:
            self.ongoing_section.hide()

        # 3. Section Terminés
        while self.completed_grid.count() > 0:
            child = self.completed_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if completed:
            self.completed_section.show()
            self.completed_header.setText(tr("Téléchargements terminés ({count})", count=len(completed)))
            cols = 5
            for idx, item in enumerate(completed):
                card = CompletedDownloadCard(item, parent=self.completed_section)
                card.clicked.connect(self.play_download_requested.emit)
                card.delete_clicked.connect(self._on_delete_completed_item)
                row = idx // cols
                col = idx % cols
                self.completed_grid.addWidget(card, row, col)
        else:
            self.completed_section.hide()

        # 4. État vide
        if not ongoing and not completed:
            self.empty_widget.show()
        else:
            self.empty_widget.hide()

    def _on_download_progress(self, item: DownloadItem):
        if item.id in self._ongoing_cards:
            self._ongoing_cards[item.id].update_state(item)

    def _on_status_changed(self, item: DownloadItem):
        if item.id in self._ongoing_cards:
            self._ongoing_cards[item.id].update_state(item)

    def _on_pause_resume_item(self, item: DownloadItem):
        if item.status == DownloadStatus.DOWNLOADING:
            self.mgr.pause_download(item.id)
        elif item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
            self.mgr.resume_download(item.id)

    def _on_cancel_item(self, item: DownloadItem):
        res = QMessageBox.question(
            self,
            tr("Annuler le téléchargement"),
            tr("Voulez-vous vraiment annuler le téléchargement de '{name}' ?", name=item.title),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.cancel_download(item.id)
            self.refresh()

    def _on_delete_completed_item(self, item: DownloadItem):
        res = QMessageBox.question(
            self,
            tr("Supprimer le fichier"),
            tr("Voulez-vous supprimer définitivement '{name}' du disque ?", name=item.title),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.mgr.delete_download(item.id)
            self.refresh()
