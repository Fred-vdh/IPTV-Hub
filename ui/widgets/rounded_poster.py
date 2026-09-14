"""
Widget d'affiche (poster) avec coins arrondis et bordure élégante.
Découpe proprement toute image (QPixmap) avec antialiasing pour garantir
que les affiches aient toujours des coins arrondis dans toute l'application.
"""

from typing import Optional
from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QPen

from ui.icons import get_icon
from ui.widgets.poster_utils import draw_added_date_badge


class RoundedPosterLabel(QLabel):
    """
    QLabel spécialisé pour l'affichage des affiches (films, séries) :
    - Découpe avec un arrondi net et antialiasé (défaut : 10px).
    - Ajustement KeepAspectRatioByExpanding avec centrage automatique.
    - Fond sombre et icône élégante si aucune image n'est disponible.
    - Bordure fine assortie aux coins arrondis.
    """

    def __init__(
        self,
        radius: int = 10,
        border_color: str = "#334155",
        bg_color: str = "#1e293b",
        fallback_icon: str = "movie",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.radius = radius
        self.border_color = border_color
        self.bg_color = bg_color
        self.fallback_icon = fallback_icon
        self.added_at: Optional[str] = None
        self.stream_type: str = "movie"
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent; border: none;")
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_added_at(self, added_at: Optional[str], stream_type: str = "movie"):
        self.added_at = added_at
        self.stream_type = stream_type
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = self.rect()
        w = float(rect.width())
        h = float(rect.height())
        r = float(self.radius)

        # 1. Découpe arrondie antialiasée
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.0, 0.0, w, h), r, r)
        painter.setClipPath(path)

        # 2. Dessin de l'affiche ou du fond de secours
        pm = self.pixmap()
        if pm and not pm.isNull():
            scaled = pm.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            sx = int((w - scaled.width()) / 2)
            sy = int((h - scaled.height()) / 2)
            painter.drawPixmap(sx, sy, scaled)
        else:
            painter.fillRect(rect, QColor(self.bg_color))
            icon_size = max(24, min(48, int(min(w, h) / 3)))
            icon_pix = get_icon(self.fallback_icon, color="#475569").pixmap(icon_size, icon_size)
            ix = int((w - icon_size) / 2)
            iy = int((h - icon_size) / 2)
            painter.drawPixmap(ix, iy, icon_pix)

        # 3. Bordure soignée aux coins arrondis
        painter.setClipping(False)
        painter.setPen(QPen(QColor(self.border_color), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)

        # 4. Badge date d'ajout (Films et Séries)
        if self.added_at and self.stream_type in ("movie", "series"):
            draw_added_date_badge(painter, self.added_at, int(w), int(h), bottom_offset=8, left_offset=8, font_size=8)