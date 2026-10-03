"""
Dialogue des paramètres de l'application IPTV avec icônes Material Symbols.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSlider, QCheckBox, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QSize

from core.database import Database
from ui.icons import get_icon, DEFAULT_ICON_COLOR


class SettingsDialog(QDialog):
    def __init__(self, db: Database, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.db = db
        self.settings = self.db.get_settings()
        self.setWindowTitle("Paramètres")
        self.resize(520, 520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_lbl = QLabel("Paramètres de l'application")
        header_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        header_row.addWidget(header_lbl)
        layout.addLayout(header_row)

        # 1. User-Agent
        layout.addWidget(QLabel("User-Agent HTTP par défaut :"))
        self.ua_input = QLineEdit(self.settings.user_agent)
        self.ua_input.setPlaceholderText("Mozilla/5.0 ...")
        layout.addWidget(self.ua_input)

        # 2. Accélération matérielle
        hw_layout = QHBoxLayout()
        hw_layout.addWidget(QLabel("Accélération matérielle (GPU) :"))
        self.hw_combo = QComboBox()
        self.hw_combo.addItems(["auto", "d3d11va", "nvdec", "no"])
        self.hw_combo.setCurrentText(self.settings.hwdec)
        hw_layout.addWidget(self.hw_combo)
        layout.addLayout(hw_layout)

        # 3. Mémoire tampon (Buffer Demuxer)
        buf_layout = QHBoxLayout()
        self.buf_label = QLabel(f"Taille du tampon vidéo : {self.settings.buffer_size_mb} Mo")
        buf_layout.addWidget(self.buf_label)
        self.buf_slider = QSlider(Qt.Orientation.Horizontal)
        self.buf_slider.setRange(8, 128)
        self.buf_slider.setValue(self.settings.buffer_size_mb)
        self.buf_slider.valueChanged.connect(lambda v: self.buf_label.setText(f"Taille du tampon vidéo : {v} Mo"))
        buf_layout.addWidget(self.buf_slider)
        layout.addLayout(buf_layout)

        # 4. Désentrelacement
        self.deinterlace_cb = QCheckBox("Activer le désentrelacement automatique (YADIF)")
        self.deinterlace_cb.setChecked(self.settings.deinterlace)
        layout.addWidget(self.deinterlace_cb)

        # 5. Cache des logos
        self.cache_logos_cb = QCheckBox("Mettre en cache les logos de chaînes localement")
        self.cache_logos_cb.setChecked(self.settings.cache_logos)
        layout.addWidget(self.cache_logos_cb)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #1e2433;")
        layout.addWidget(sep)

        # 6. Dossier de téléchargement
        from core.download_manager import get_default_download_dir

        layout.addWidget(QLabel("Dossier de téléchargement :"))
        dl_row = QHBoxLayout()
        self.dl_input = QLineEdit(self.settings.download_dir or get_default_download_dir())
        dl_row.addWidget(self.dl_input)
        browse_btn = QPushButton(" Parcourir...")
        browse_btn.setIcon(get_icon("folder_open", color=DEFAULT_ICON_COLOR))
        browse_btn.clicked.connect(self._browse_download_dir)
        dl_row.addWidget(browse_btn)
        layout.addLayout(dl_row)

        # 7. Vitesse de téléchargement max
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Limitation de vitesse de téléchargement :"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItem("Illimitée", 0)
        self.speed_combo.addItem("1.5 Mo/s", 1500 * 1024)
        self.speed_combo.addItem("3.0 Mo/s", 3000 * 1024)
        self.speed_combo.addItem("5.0 Mo/s", 5000 * 1024)
        self.speed_combo.addItem("10.0 Mo/s", 10000 * 1024)
        cur_spd = getattr(self.settings, "download_speed_limit", 0)
        s_idx = 0
        for i in range(self.speed_combo.count()):
            if self.speed_combo.itemData(i) == cur_spd:
                s_idx = i
                break
        self.speed_combo.setCurrentIndex(s_idx)
        speed_row.addWidget(self.speed_combo)
        layout.addLayout(speed_row)

        # Nettoyage du cache
        cache_row = QHBoxLayout()
        cache_row.addWidget(QLabel("Gestion du stockage local :"))
        cache_row.addStretch()

        clear_cache_btn = QPushButton(" Vider le cache")
        clear_cache_btn.setIcon(get_icon("delete", color=DEFAULT_ICON_COLOR))
        clear_cache_btn.setIconSize(QSize(16, 16))
        clear_cache_btn.setProperty("class", "secondary-btn")
        clear_cache_btn.clicked.connect(self._clear_cache)
        cache_row.addWidget(clear_cache_btn)
        layout.addLayout(cache_row)

        layout.addStretch()

        # Boutons Sauvegarder / Annuler
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton(" Annuler")
        cancel_btn.setIcon(get_icon("close", color=DEFAULT_ICON_COLOR))
        cancel_btn.setIconSize(QSize(18, 18))
        cancel_btn.setProperty("class", "secondary-btn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton(" Enregistrer")
        save_btn.setIcon(get_icon("edit", color="#ffffff"))
        save_btn.setIconSize(QSize(18, 18))
        save_btn.setProperty("class", "primary-btn")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _browse_download_dir(self):
        from PyQt6.QtWidgets import QFileDialog
        from core.download_manager import get_default_download_dir
        curr = self.dl_input.text().strip() or get_default_download_dir()
        selected = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier de téléchargement", curr)
        if selected:
            self.dl_input.setText(selected)

    def _clear_cache(self):
        from core.database import get_cache_dir
        import shutil
        logos_dir = get_cache_dir() / "logos"
        if logos_dir.exists():
            shutil.rmtree(logos_dir)
            logos_dir.mkdir(exist_ok=True)
            QMessageBox.information(self, "Cache vidé", "Le cache des logos a été vidé avec succès.")

    def _save(self):
        self.settings.user_agent = self.ua_input.text().strip()
        self.settings.hwdec = self.hw_combo.currentText()
        self.settings.buffer_size_mb = self.buf_slider.value()
        self.settings.deinterlace = self.deinterlace_cb.isChecked()
        self.settings.cache_logos = self.cache_logos_cb.isChecked()
        if hasattr(self, "dl_input"):
            self.settings.download_dir = self.dl_input.text().strip()
        if hasattr(self, "speed_combo"):
            self.settings.download_speed_limit = self.speed_combo.currentData() or 0

        self.db.save_settings(self.settings)
        try:
            from core.download_manager import DownloadManager
            DownloadManager.instance().set_speed_limit(getattr(self.settings, "download_speed_limit", 0))
        except Exception:
            pass
        self.accept()
