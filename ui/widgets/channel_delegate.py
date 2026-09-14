"""
Délégué de rendu haute performance (QStyledItemDelegate) pour les chaînes IPTV.
Affiche le logo, le nom, le programme EPG en cours, et la barre de progression temporelle.
"""

from typing import Optional
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtCore import Qt, QSize, QRectF, QModelIndex, QEvent
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPainterPath, QPixmap, QPen,
    QMouseEvent, QFontMetrics
)

from core.models import Channel, EPGProgram
from core.image_loader import ImageLoader
from ui.widgets.channel_model import ChannelRoles, ChannelListModel
from ui.icons import get_pixmap


class ChannelItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_loader = ImageLoader.instance()
        # Pré-rendu des icônes réutilisées
        self._pix_tv = get_pixmap("tv", color="#64748b", size=24)
        self._pix_movie = get_pixmap("movie", color="#64748b", size=24)
        self._pix_series = get_pixmap("video_library", color="#64748b", size=24)
        self._pix_fav_on = get_pixmap("star_filled", color="#fbbf24", size=18)
        self._pix_fav_off = get_pixmap("star_border", color="#94a3b8", size=18)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        # Hauteur confortable de 72px pour logo + 3 lignes (Nom, Programme, Barre de progression)
        return QSize(0, 72)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        channel: Channel = index.data(ChannelRoles.ChannelData)
        if not channel:
            return

        epg: Optional[EPGProgram] = index.data(ChannelRoles.EPGData)
        is_favorite = index.data(ChannelRoles.IsFavorite)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = option.rect
        card_rect = rect.adjusted(4, 2, -4, -2)
        corner_radius = 12.0

        # 1. Arrière-plan de la carte (style moderne / bordure bleue lumineuse sur sélection)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_selected:
            # Fond bleu nuit translucide avec bordure bleue vive tout autour
            painter.setBrush(QColor(30, 52, 84, 235))
            painter.setPen(QPen(QColor("#3b82f6"), 1.5))
            painter.drawRoundedRect(QRectF(card_rect), corner_radius, corner_radius)
        elif is_hover:
            painter.setBrush(QColor(30, 41, 59, 140))
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.drawRoundedRect(QRectF(card_rect), corner_radius, corner_radius)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(Qt.PenStyle.NoPen)

        # 2. Logo de la chaîne (44x44 centré verticalement avec coins arrondis)
        logo_size = 44
        logo_x = card_rect.left() + 10
        logo_y = card_rect.top() + (card_rect.height() - logo_size) / 2
        logo_rect = QRectF(logo_x, logo_y, logo_size, logo_size)

        painter.setBrush(QColor("#1e2533"))
        painter.setPen(QPen(QColor("#2d3748"), 1))
        painter.drawRoundedRect(logo_rect, 10, 10)

        pixmap: Optional[QPixmap] = None
        if channel.logo_url:
            pixmap = self.image_loader.get_cached_image(channel.logo_url)
            if not pixmap:
                self.image_loader.request_image(channel.logo_url)

        if pixmap and not pixmap.isNull():
            path = QPainterPath()
            path.addRoundedRect(logo_rect.adjusted(1, 1, -1, -1), 9, 9)
            painter.save()
            painter.setClipPath(path)
            scaled = pixmap.scaled(
                int(logo_rect.width() - 4),
                int(logo_rect.height() - 4),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            px = logo_rect.left() + (logo_rect.width() - scaled.width()) / 2
            py = logo_rect.top() + (logo_rect.height() - scaled.height()) / 2
            painter.drawPixmap(int(px), int(py), scaled)
            painter.restore()
        else:
            # Icône fallback
            if channel.stream_type == "series":
                fallback_pix = self._pix_series
            elif channel.stream_type == "movie":
                fallback_pix = self._pix_movie
            else:
                fallback_pix = self._pix_tv

            if fallback_pix:
                px = logo_rect.left() + (logo_rect.width() - fallback_pix.width()) / 2
                py = logo_rect.top() + (logo_rect.height() - fallback_pix.height()) / 2
                painter.drawPixmap(int(px), int(py), fallback_pix)

        # 3. Textes & Barre de progression EPG
        text_left = logo_rect.right() + 12
        fav_button_width = 30
        text_right = card_rect.right() - fav_button_width - 8
        available_width = max(60.0, text_right - text_left)

        # 3.1 Ligne 1 : Nom de la chaîne
        name_font = QFont("Segoe UI", 10, QFont.Weight.Bold if is_selected else QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(QColor("#93c5fd" if is_selected else "#ffffff"))
        fm_name = QFontMetrics(name_font)
        elided_name = fm_name.elidedText(channel.name, Qt.TextElideMode.ElideRight, int(available_width))
        name_y = card_rect.top() + 18
        painter.drawText(int(text_left), int(name_y), elided_name)

        # 3.2 Ligne 2 : Programme en cours (ou groupe si absent)
        prog_font = QFont("Segoe UI", 9, QFont.Weight.Normal)
        painter.setFont(prog_font)
        fm_prog = QFontMetrics(prog_font)

        if epg and epg.title:
            prog_text = epg.title
            painter.setPen(QColor("#94a3b8"))
        else:
            prog_text = channel.group_title or "Direct"
            painter.setPen(QColor("#64748b"))

        elided_prog = fm_prog.elidedText(prog_text, Qt.TextElideMode.ElideRight, int(available_width))
        prog_y = name_y + 16
        painter.drawText(int(text_left), int(prog_y), elided_prog)

        # 3.3 Ligne 3 : Barre de progression temporelle & Horaires (style moderne)
        bar_y = prog_y + 8
        time_font = QFont("Segoe UI", 8, QFont.Weight.Medium)
        painter.setFont(time_font)
        fm_time = QFontMetrics(time_font)

        start_str = epg.start_time_display if epg else ""
        end_str = epg.end_time_display if epg else ""

        if start_str and end_str:
            # Heure début à gauche
            painter.setPen(QColor("#93c5fd" if is_selected else "#94a3b8"))
            painter.drawText(int(text_left), int(bar_y + 8), start_str)
            start_w = fm_time.horizontalAdvance(start_str) + 6

            # Heure fin à droite
            end_w = fm_time.horizontalAdvance(end_str) + 6
            painter.drawText(int(text_right - end_w + 6), int(bar_y + 8), end_str)

            # Barre de progression centrale
            bar_left = text_left + start_w
            bar_width = max(20.0, text_right - end_w - bar_left)
            bar_height = 3.5

            # Fond de la barre (rainure)
            groove_rect = QRectF(bar_left, bar_y + 3, bar_width, bar_height)
            painter.setBrush(QColor("#334155"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(groove_rect, 1.75, 1.75)

            # Remplissage de la progression (bleu lumineux)
            pct = epg.progress_percentage() if epg else 0.0
            fill_width = bar_width * (pct / 100.0)
            if fill_width > 0:
                fill_rect = QRectF(bar_left, bar_y + 3, max(4.0, fill_width), bar_height)
                painter.setBrush(QColor("#60a5fa"))
                painter.drawRoundedRect(fill_rect, 1.75, 1.75)
        else:
            # Si pas d'horaires, afficher une discrète pastille ou laisser épuré
            badge_rect = QRectF(text_left, bar_y + 2, 44, 14)
            painter.setBrush(QColor("#1e293b"))
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.drawRoundedRect(badge_rect, 4, 4)

            painter.setPen(QColor("#818cf8"))
            badge_font = QFont("Segoe UI", 7, QFont.Weight.Bold)
            painter.setFont(badge_font)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, channel.stream_type.upper())

        # 4. Bouton Favori (Cœur) à droite
        fav_pix = self._pix_fav_on if is_favorite else self._pix_fav_off
        fav_x = card_rect.right() - fav_button_width + 4
        fav_y = card_rect.top() + (card_rect.height() - fav_pix.height()) / 2
        painter.drawPixmap(int(fav_x), int(fav_y), fav_pix)

        painter.restore()

    def editorEvent(self, event: QEvent, model: ChannelListModel, option: QStyleOptionViewItem, index: QModelIndex) -> bool:
        """Gère le clic sur l'icône de favori."""
        if event.type() == QEvent.Type.MouseButtonRelease:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
                rect = option.rect
                card_rect = rect.adjusted(4, 2, -4, -2)
                fav_x = card_rect.right() - 34
                if event.position().x() >= fav_x:
                    model.toggle_favorite(index.row())
                    return True
        return super().editorEvent(event, model, option, index)
