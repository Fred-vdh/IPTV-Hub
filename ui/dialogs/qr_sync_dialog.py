"""
Boîte de dialogue de synchronisation locale par QR Code (Passerelle Mobile).
Permet de synchroniser favoris, playlists, progression de lecture et paramètres
sans cloud, via un smartphone connecté au même réseau local ou partage de connexion.
"""

from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QLineEdit, QApplication, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from core.database import Database
from core.qr_sync_server import QRSyncServer, get_local_ip_addresses, generate_qr_pixmap
from ui.icons import get_icon, get_pixmap
from core.i18n import tr


class QRSyncDialog(QDialog):
    """
    Dialogue affichant le QR Code et pilotant le serveur web éphémère.
    """
    sync_completed = pyqtSignal(dict)  # Émet les statistiques lors d'une importation réussie

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(tr("Passerelle de synchronisation"))
        self.setFixedSize(540, 680)
        self.setModal(True)

        self.server = QRSyncServer(self.db, self)
        self.all_ips: List[str] = get_local_ip_addresses()

        self._init_ui()
        self._connect_signals()

        # Démarrage automatique du serveur local
        self._start_server()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f1f5f9;
            }
            QLabel {
                color: #f1f5f9;
            }
            QComboBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                color: #f8fafc;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                border: 1px solid #334155;
                selection-background-color: #4f46e5;
                color: #f8fafc;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                color: #94a3b8;
                font-family: monospace;
                font-size: 12px;
            }
            QPushButton.btn-primary {
                background-color: #4f46e5;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton.btn-primary:hover {
                background-color: #4338ca;
            }
            QPushButton.btn-secondary {
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton.btn-secondary:hover {
                background-color: #334155;
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # ---------------- 1. EN-TÊTE ----------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(get_pixmap("qr_code", color="#818cf8", size=32))
        icon_label.setFixedSize(36, 36)
        header_layout.addWidget(icon_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel(tr("Passerelle de synchronisation"))
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        title_col.addWidget(self.title_label)

        self.desc_label = QLabel(tr("Synchronisez vos données via votre smartphone en réseau local."))
        self.desc_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_col.addWidget(self.desc_label)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        # Badge d'état du serveur
        self.status_badge = QLabel(tr("Serveur actif"))
        self.status_badge.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid #059669;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.status_badge)

        layout.addLayout(header_layout)

        # ---------------- 2. ZONE CENTRALE : QR CODE ----------------
        qr_card = QFrame()
        qr_card.setStyleSheet("""
            QFrame {
                background-color: #151d30;
                border: 1px solid #24304c;
                border-radius: 12px;
            }
        """)
        qr_layout = QVBoxLayout(qr_card)
        qr_layout.setContentsMargins(16, 16, 16, 16)
        qr_layout.setSpacing(12)
        qr_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Label d'image QR Code
        self.qr_image_label = QLabel()
        self.qr_image_label.setFixedSize(220, 220)
        self.qr_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_image_label.setStyleSheet("background-color: #0b0f19; border-radius: 8px; border: 1px solid #1e293b;")
        qr_layout.addWidget(self.qr_image_label, 0, Qt.AlignmentFlag.AlignCenter)

        # Sélecteur d'interface IP (si plusieurs IPs disponibles)
        if len(self.all_ips) > 1:
            ip_row = QHBoxLayout()
            ip_row.setSpacing(8)
            self.ip_label = QLabel(tr("Adresse réseau :"))
            self.ip_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
            ip_row.addWidget(self.ip_label)

            self.ip_combo = QComboBox()
            for i, ip in enumerate(self.all_ips):
                label = f"{ip} ({tr('Recommandée')})" if i == 0 else ip
                self.ip_combo.addItem(label, userData=ip)
            self.ip_combo.currentIndexChanged.connect(self._on_ip_changed)
            ip_row.addWidget(self.ip_combo, stretch=1)
            qr_layout.addLayout(ip_row)
        else:
            self.ip_label = None
            self.ip_combo = None

        # Champ d'URL textuelle + bouton copier
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setReadOnly(True)
        url_row.addWidget(self.url_edit, stretch=1)

        self.copy_btn = QPushButton(tr("Copier"))
        self.copy_btn.setProperty("class", "btn-secondary")
        self.copy_btn.setIcon(get_icon("content_copy", color="#cbd5e1"))
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self._copy_url)
        url_row.addWidget(self.copy_btn)
        qr_layout.addLayout(url_row)

        layout.addWidget(qr_card)

        # ---------------- 3. ZONE D'ÉTAT EN DIRECT ----------------
        self.live_status_card = QFrame()
        self.live_status_card.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        live_layout = QHBoxLayout(self.live_status_card)
        live_layout.setContentsMargins(12, 10, 12, 10)
        live_layout.setSpacing(10)

        self.live_icon = QLabel()
        self.live_icon.setPixmap(get_pixmap("wifi", color="#818cf8", size=20))
        live_layout.addWidget(self.live_icon)

        self.live_status_text = QLabel(tr("En attente de connexion du smartphone..."))
        self.live_status_text.setStyleSheet("font-size: 13px; color: #cbd5e1;")
        self.live_status_text.setWordWrap(True)
        live_layout.addWidget(self.live_status_text, stretch=1)

        layout.addWidget(self.live_status_card)

        # ---------------- 4. RAPPEL RÉSEAU ----------------
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(59, 130, 246, 0.08);
                border: 1px solid rgba(59, 130, 246, 0.25);
                border-radius: 8px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(10)

        info_icon = QLabel()
        info_icon.setPixmap(get_pixmap("info", color="#60a5fa", size=18))
        info_layout.addWidget(info_icon)

        self.info_text = QLabel(tr("Veillez à ce que votre téléphone et cet appareil soient connectés au même réseau (Wi-Fi ou partage de connexion)."))
        self.info_text.setStyleSheet("font-size: 12px; color: #93c5fd;")
        self.info_text.setWordWrap(True)
        info_layout.addWidget(self.info_text, stretch=1)

        layout.addWidget(info_frame)

        # ---------------- 5. BOUTON FERMER ----------------
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.close_btn = QPushButton(tr("Fermer"))
        self.close_btn.setProperty("class", "btn-primary")
        self.close_btn.setMinimumWidth(120)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(self.close_btn)

        layout.addLayout(bottom_layout)

    def _connect_signals(self):
        self.server.server_started.connect(self._on_server_started)
        self.server.client_connected.connect(self._on_client_connected)
        self.server.export_completed.connect(self._on_export_completed)
        self.server.import_completed.connect(self._on_import_completed)
        self.server.server_error.connect(self._on_server_error)
        self.server.server_stopped.connect(self._on_server_stopped)

        from core.i18n import I18nManager
        I18nManager.instance().language_changed.connect(self._on_language_changed)

    def _on_language_changed(self, new_lang: str):
        self.server.current_app_language = new_lang
        url = self.server.get_sync_url()
        self._update_qr_code(url)
        self.retranslate_ui()

    def retranslate_ui(self):
        """Met à jour dynamiquement tous les libellés de l'interface lors d'un changement de langue."""
        self.setWindowTitle(tr("Passerelle de synchronisation"))
        if hasattr(self, "title_label"):
            self.title_label.setText(tr("Passerelle de synchronisation"))
        if hasattr(self, "desc_label"):
            self.desc_label.setText(tr("Synchronisez vos données via votre smartphone en réseau local."))
        if hasattr(self, "status_badge"):
            if self.server and self.server.server:
                self.status_badge.setText(tr("Serveur actif"))
            else:
                self.status_badge.setText(tr("Serveur arrêté"))
        if hasattr(self, "ip_label") and self.ip_label:
            self.ip_label.setText(tr("Adresse réseau :"))
        if hasattr(self, "ip_combo") and self.ip_combo:
            curr_idx = self.ip_combo.currentIndex()
            self.ip_combo.blockSignals(True)
            self.ip_combo.clear()
            for i, ip in enumerate(self.all_ips):
                label = f"{ip} ({tr('Recommandée')})" if i == 0 else ip
                self.ip_combo.addItem(label, userData=ip)
            self.ip_combo.setCurrentIndex(curr_idx)
            self.ip_combo.blockSignals(False)
        if hasattr(self, "copy_btn"):
            self.copy_btn.setText(tr("Copier"))
        if hasattr(self, "info_text"):
            self.info_text.setText(tr("Veillez à ce que votre téléphone et cet appareil soient connectés au même réseau (Wi-Fi ou partage de connexion)."))
        if hasattr(self, "close_btn"):
            self.close_btn.setText(tr("Fermer"))
        if hasattr(self, "live_status_text") and not getattr(self, "_has_active_event", False):
            self.live_status_text.setText(tr("En attente de connexion du smartphone..."))

    def _start_server(self):
        preferred_ip = self.all_ips[0] if self.all_ips else "127.0.0.1"
        if self.ip_combo:
            preferred_ip = self.ip_combo.currentData()

        ok, url_or_err = self.server.start(preferred_ip=preferred_ip)
        if not ok:
            self._set_status_error(url_or_err)

    def _on_ip_changed(self, index: int):
        if not self.ip_combo:
            return
        selected_ip = self.ip_combo.itemData(index)
        if selected_ip:
            self.server.set_active_ip(selected_ip)
            url = self.server.get_sync_url()
            self._update_qr_code(url)

    def _update_qr_code(self, url: str):
        self.url_edit.setText(url)
        pixmap = generate_qr_pixmap(url, size=210, fg_color="#ffffff", bg_color="#0b0f19")
        self.qr_image_label.setPixmap(pixmap)

    def _on_server_started(self, ip: str, port: int, token: str):
        url = self.server.get_sync_url()
        self._update_qr_code(url)
        self.status_badge.setText(tr("Serveur actif"))
        self.status_badge.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid #059669;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
        """)

    def _on_client_connected(self, client_ip: str):
        self._has_active_event = True
        self.live_icon.setPixmap(get_pixmap("smartphone", color="#34d399", size=20))
        self.live_status_text.setText(tr("Appareil mobile connecté ({ip}). En attente d'action...", ip=client_ip))

    def _on_export_completed(self):
        self._has_active_event = True
        self.live_icon.setPixmap(get_pixmap("cloud_download", color="#60a5fa", size=20))
        self.live_status_text.setText(tr("Fichier de sauvegarde téléchargé avec succès sur le smartphone !"))
        self.live_status_card.setStyleSheet("""
            QFrame {
                background-color: rgba(59, 130, 246, 0.15);
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 10px;
            }
        """)

    def _on_import_completed(self, stats: Dict[str, int]):
        self._has_active_event = True
        self.live_icon.setPixmap(get_pixmap("check_circle", color="#34d399", size=20))
        msg_details = []
        if stats.get("playlists_synced", 0) > 0:
            msg_details.append(f"{stats['playlists_synced']} {tr('liste(s)')}")
        if stats.get("favorites_added", 0) > 0:
            msg_details.append(f"{stats['favorites_added']} {tr('favori(s)')}")
        if stats.get("progress_updated", 0) > 0:
            msg_details.append(f"{stats['progress_updated']} {tr('reprise(s)')}")

        summary = ", ".join(msg_details) if msg_details else tr("Toutes les données sont déjà à jour.")
        self.live_status_text.setText(f"✅ {tr('Synchronisation réussie')} ! ({summary})")
        self.live_status_card.setStyleSheet("""
            QFrame {
                background-color: rgba(16, 185, 129, 0.2);
                border: 1px solid #10b981;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        # Émission du signal vers la fenêtre principale pour rafraîchissement en direct
        self.sync_completed.emit(stats)

    def _on_server_error(self, err: str):
        self._has_active_event = True
        self._set_status_error(err)

    def _on_server_stopped(self):
        self.status_badge.setText(tr("Serveur arrêté"))
        self.status_badge.setStyleSheet("""
            background-color: #334155;
            color: #94a3b8;
            border: 1px solid #475569;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
        """)

    def _set_status_error(self, err_msg: str):
        self.status_badge.setText(tr("Erreur"))
        self.status_badge.setStyleSheet("""
            background-color: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid #dc2626;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
        """)
        self.live_status_text.setText(f"❌ {err_msg}")

    def _copy_url(self):
        clipboard = QApplication.clipboard()
        if clipboard and self.url_edit.text():
            clipboard.setText(self.url_edit.text())
            self.copy_btn.setText(tr("Copié !"))
            QTimer.singleShot(1800, lambda: self.copy_btn.setText(tr("Copier")))

    def closeEvent(self, event):
        """Arrête le serveur HTTP dès que la boîte de dialogue est fermée."""
        if self.server:
            self.server.stop()
        super().closeEvent(event)
