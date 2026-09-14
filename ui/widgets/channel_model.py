"""
Modèle de données haute performance pour la liste des chaînes IPTV.
"""

from typing import List, Dict, Optional
from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt, pyqtSignal

from core.models import Channel, EPGProgram


class ChannelRoles:
    ChannelData = Qt.ItemDataRole.UserRole + 1
    EPGData = Qt.ItemDataRole.UserRole + 2
    IsFavorite = Qt.ItemDataRole.UserRole + 3


class ChannelListModel(QAbstractListModel):
    favorite_toggled = pyqtSignal(int, bool)  # channel_id, is_favorite

    def __init__(self, parent=None):
        super().__init__(parent)
        self._channels: List[Channel] = []
        self._epg_map: Dict[str, EPGProgram] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._channels)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._channels)):
            return None

        channel = self._channels[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return channel.name
        elif role == Qt.ItemDataRole.UserRole:
            return channel
        elif role == ChannelRoles.ChannelData:
            return channel
        elif role == ChannelRoles.EPGData:
            return self._epg_map.get(channel.tvg_id) if channel.tvg_id else None
        elif role == ChannelRoles.IsFavorite:
            return channel.is_favorite

        return None

    def set_channels(self, channels: List[Channel], epg_map: Optional[Dict[str, EPGProgram]] = None):
        """Met à jour instantanément toutes les chaînes sans aucun lag UI."""
        self.beginResetModel()
        self._channels = channels
        if epg_map is not None:
            self._epg_map = epg_map
        self.endResetModel()

    def get_channel(self, row: int) -> Optional[Channel]:
        if 0 <= row < len(self._channels):
            return self._channels[row]
        return None

    def toggle_favorite(self, row: int):
        if 0 <= row < len(self._channels):
            ch = self._channels[row]
            ch.is_favorite = not ch.is_favorite
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [ChannelRoles.IsFavorite])
            if ch.id:
                self.favorite_toggled.emit(ch.id, ch.is_favorite)

    def update_for_logo(self, url: str):
        """Rafraîchit l'affichage pour les lignes utilisant cette image."""
        for row, ch in enumerate(self._channels):
            if ch.logo_url == url:
                idx = self.index(row, 0)
                self.dataChanged.emit(idx, idx)
