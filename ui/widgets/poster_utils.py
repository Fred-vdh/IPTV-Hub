from typing import Any
from datetime import datetime
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QFont, QPen

SHOW_POSTER_ADDED_DATE: bool = True

def format_poster_added_date(dt_input: Any) -> str:
    if not dt_input:
        return ''
    try:
        if isinstance(dt_input, (int, float)):
            dt = datetime.fromtimestamp(dt_input)
        elif isinstance(dt_input, str):
            clean_str = dt_input.strip()
            if not clean_str:
                return ''
            if clean_str.isdigit():
                dt = datetime.fromtimestamp(int(clean_str))
            else:
                clean_str = clean_str.replace(' ', 'T')
                dt = datetime.fromisoformat(clean_str)
        elif isinstance(dt_input, datetime):
            dt = dt_input
        else:
            return ''
        return dt.strftime('%d/%m/%Y')
    except Exception:
        return ''

def draw_added_date_badge(painter: QPainter, added_at: Any, poster_width: int, poster_height: int, bottom_offset: int = 6, left_offset: int = 6, font_size: int = 7) -> bool:
    if not SHOW_POSTER_ADDED_DATE:
        return False
    date_str = format_poster_added_date(added_at)
    if not date_str:
        return False
    painter.save()
    font = QFont('Segoe UI', font_size, QFont.Weight.DemiBold)
    painter.setFont(font)
    metrics = painter.fontMetrics()
    text = date_str
    bw = metrics.horizontalAdvance(text) + 10
    bh = 16
    bx = left_offset
    by = poster_height - bh - bottom_offset
    painter.setBrush(QColor(15, 23, 42, 220))
    painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
    painter.drawRoundedRect(QRect(bx, by, bw, bh), 3, 3)
    painter.setPen(QColor('#cbd5e1'))
    painter.drawText(QRect(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()
    return True
