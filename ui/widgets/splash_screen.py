"""
Écran de démarrage moderne (Splash Screen) pour IPTV Hub.
S'affiche instantanément dès le lancement pour un démarrage perçu à froid fluide.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QApplication,
    QGraphicsDropShadowEffect,
)

from ui.icons import get_app_logo_pixmap


class SplashScreen(QWidget):
    """Écran d'accueil affiché immédiatement au démarrage de l'application."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(480, 280)

        # Centrage sur l'écran actif
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

        # Effet d'ombre portée subtil
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 25)
        layout.setSpacing(8)

        # Logo
        self.logo_label = QLabel(self)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pix = get_app_logo_pixmap(64)
        if not logo_pix.isNull():
            self.logo_label.setPixmap(logo_pix)
        layout.addWidget(self.logo_label)

        # Titre
        self.title_label = QLabel("IPTV Hub", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-top: 4px;
        """)
        layout.addWidget(self.title_label)

        # Sous-titre
        self.sub_label = QLabel("Lecteur Moderne & Haute Performance", self)
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 11px;
            font-weight: 500;
            margin-bottom: 12px;
        """)
        layout.addWidget(self.sub_label)

        layout.addStretch()

        # Barre de progression fine et moderne
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(10)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e2433;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #818cf8);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Texte d'état
        self.status_label = QLabel("Initialisation du système...", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            color: #cbd5e1;
            font-size: 11px;
            margin-top: 4px;
        """)
        layout.addWidget(self.status_label)

    def paintEvent(self, event):
        """Dessine un fond sombre arrondi avec dégradé subtil."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), 16.0, 16.0)

        # Dégradé de fond
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(24, 28, 38, 250))
        grad.setColorAt(1.0, QColor(17, 20, 28, 252))

        painter.fillPath(path, grad)

        # Bordure fine
        painter.setPen(QColor(51, 65, 85, 140))
        painter.drawPath(path)

    def set_status(self, text: str, progress: int = -1):
        """Met à jour le message et la progression en forçant l'affichage immédiat."""
        self.status_label.setText(text)
        if progress >= 0:
            self.progress_bar.setValue(progress)
        QApplication.processEvents()

    def finish(self, window: QWidget):
        """Ferme le splash screen une fois la fenêtre principale prête."""
        self.close()
        self.deleteLater()
