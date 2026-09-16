"""
Composant d'animation de chargement et de mise en mémoire tampon (Buffering).
Rendu vectoriel fluide avec double arc orbital et pulsation d'ondes radio IPTV.
Version épurée (animation seule sans texte) avec temporisation d'affichage
(1.5 seconde par défaut) pour éviter tout clignotement lors des chargements rapides.
"""

import math
import time
from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QConicalGradient,
    QRadialGradient, QPaintEvent
)


class OrbitalPulseGraphic(QWidget):
    """Sous-widget dédié au dessin vectoriel de l'anneau orbital et de l'onde de signal."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(74, 74)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._outer_angle: float = 0.0
        self._inner_angle: float = 0.0
        self._pulse_phase: float = 0.0

    def update_animation(self, delta_ms: float):
        # Rotation de l'arc orbital externe (~220° par seconde)
        self._outer_angle = (self._outer_angle + (delta_ms * 0.24)) % 360.0
        # Rotation inverse plus rapide de l'anneau interne
        self._inner_angle = (self._inner_angle - (delta_ms * 0.36)) % 360.0
        # Pulsation de l'onde radio centrale (fréquence douce ~1.5 Hz)
        self._pulse_phase = (self._pulse_phase + (delta_ms * 0.0055)) % (2 * math.pi)
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        center = QPointF(cx, cy)

        # 1. Halo lumineux doux d'arrière-plan (lueur bleue subtile)
        halo_radius = 32.0
        radial_glow = QRadialGradient(center, halo_radius)
        radial_glow.setColorAt(0.0, QColor(59, 130, 246, 55))
        radial_glow.setColorAt(0.7, QColor(37, 99, 235, 20))
        radial_glow.setColorAt(1.0, QColor(15, 23, 42, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(radial_glow))
        painter.drawEllipse(center, halo_radius, halo_radius)

        # 2. Anneau guide d'orbite discret (gris bleuté très estompé)
        track_pen = QPen(QColor(51, 65, 85, 90))
        track_pen.setWidthF(2.5)
        painter.setPen(track_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, 27.0, 27.0)

        # 3. Arc orbital externe lumineux (bleu électrique -> cyan -> blanc)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._outer_angle)

        outer_rect = QRectF(-27.0, -27.0, 54.0, 54.0)
        # Dégradé conique pour une queue d'arc effilée et lumineuse
        gradient = QConicalGradient(0, 0, 0)
        gradient.setColorAt(0.0, QColor(96, 165, 250, 0))
        gradient.setColorAt(0.5, QColor(59, 130, 246, 120))
        gradient.setColorAt(0.85, QColor(56, 189, 248, 230))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 255))

        arc_pen = QPen(QBrush(gradient), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        # On dessine un arc de 160 degrés
        painter.drawArc(outer_rect, 0, int(160 * 16))
        painter.restore()

        # 4. Arc interne rapide (cyan cobalt néon)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._inner_angle)

        inner_rect = QRectF(-19.0, -19.0, 38.0, 38.0)
        inner_pen = QPen(QColor(129, 140, 248, 190), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(inner_pen)
        painter.drawArc(inner_rect, 0, int(110 * 16))
        painter.restore()

        # 5. Cœur central : signal de diffusion / pulsation d'ondes radio IPTV
        # Deux ondes concentriques en respiration sinusoïdale
        pulse_val = (math.sin(self._pulse_phase) + 1.0) / 2.0  # [0.0, 1.0]

        # Onde externe pulsante
        wave_radius = 7.0 + (pulse_val * 4.5)
        wave_alpha = int((1.0 - pulse_val) * 150)
        wave_pen = QPen(QColor(96, 165, 250, wave_alpha), 1.5)
        painter.setPen(wave_pen)
        painter.drawEllipse(center, wave_radius, wave_radius)

        # Disque central lumineux constant avec point blanc
        core_color = QColor(59, 130, 246, 235)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(core_color))
        painter.drawEllipse(center, 4.2, 4.2)

        # Micro-point blanc au centre (lueur intense)
        painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
        painter.drawEllipse(center, 1.8, 1.8)


class StreamBufferingIndicator(QWidget):
    """
    Pastille circulaire flottante semi-transparente affichant exclusivement l'animation
    vectorielle originale de chargement / resynchronisation, avec temporisation de déclenchement.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("streamBufferingIndicator")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._last_tick_time: float = 0.0

        # Timer d'animation vectorielle (~60 FPS)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

        # Timer de délai d'apparition (1.5s par défaut pour éviter les micro-flashs)
        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.setInterval(1500)
        self._delay_timer.timeout.connect(self._show_and_run)

        self._init_ui()

    def _init_ui(self):
        # Pastille compacte épurée centrée sur l'animation
        self.setFixedSize(96, 96)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Graphique vectoriel animé
        self._graphic = OrbitalPulseGraphic(self)
        layout.addWidget(self._graphic, alignment=Qt.AlignmentFlag.AlignCenter)

        # Style circulaire moderne en verre fumé avec bordure bleutée
        self.setStyleSheet("""
            #streamBufferingIndicator {
                background-color: rgba(15, 23, 42, 0.88);
                border: 1.5px solid rgba(59, 130, 246, 0.45);
                border-radius: 48px;
            }
        """)

        # Ombre portée douce
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def set_messages(self, title: Optional[str] = None, subtitle: Optional[str] = None):
        """Conservé pour compatibilité sans affichage de texte."""
        pass

    def start(self, delay_ms: int = 1500):
        """
        Déclenche l'affichage avec temporisation (1.5 seconde par défaut).
        Si le flux démarre avant la fin du délai, l'animation ne s'affichera pas.
        """
        self._delay_timer.stop()
        if delay_ms <= 0:
            self._show_and_run()
        else:
            self._delay_timer.start(delay_ms)

    def _show_and_run(self):
        """Active l'animation et affiche la pastille."""
        self._last_tick_time = time.monotonic()
        if not self._timer.isActive():
            self._timer.start()
        self.show()
        self.raise_()

    def stop(self):
        """Arrête tous les timers et masque immédiatement le widget."""
        self._delay_timer.stop()
        if self._timer.isActive():
            self._timer.stop()
        self.hide()

    def _on_tick(self):
        now = time.monotonic()
        delta_ms = (now - self._last_tick_time) * 1000.0
        self._last_tick_time = now

        # Clamping pour éviter les à-coups après suspension
        if delta_ms > 100.0:
            delta_ms = 16.0

        self._graphic.update_animation(delta_ms)
