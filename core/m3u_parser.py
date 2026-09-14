"""
Parser M3U / M3U8 haute performance pour l'extraction des flux IPTV et métadonnées.
"""

import re
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Generator, Callable
from core.models import Channel


# Expressions régulières pour l'extraction d'attributs M3U
ATTR_REGEX = re.compile(r'([a-zA-Z0-9_-]+)="([^"]*)"')
EXTINF_REGEX = re.compile(r'^#EXTINF:\s*(-?\d+)?\s*(.*?),\s*(.*)$')


class M3UParser:
    @staticmethod
    def parse_attributes(attr_string: str) -> Dict[str, str]:
        """Extrait les paires clé-valeur d'une ligne #EXTINF."""
        return {k.lower(): v for k, v in ATTR_REGEX.findall(attr_string)}

    @classmethod
    def parse_content(
        cls,
        content_lines: Generator[str, None, None] | List[str],
        playlist_id: int = 0,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> List[Channel]:
        """
        Parse les lignes de contenu M3U et retourne une liste d'objets Channel.
        """
        channels: List[Channel] = []
        current_extinf_attrs: Dict[str, str] = {}
        current_name: str = ""
        current_group: str = "Général"
        current_user_agent: str = ""
        current_referrer: str = ""
        extra_headers: Dict[str, str] = {}

        count = 0

        for raw_line in content_lines:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                match = EXTINF_REGEX.match(line)
                if match:
                    _, attr_str, title = match.groups()
                    current_extinf_attrs = cls.parse_attributes(attr_str)
                    current_name = (title or "").strip()
                    if not current_name:
                        current_name = current_extinf_attrs.get("tvg-name", "Sans nom")
                else:
                    # Fallback si format non standard
                    parts = line.split(",", 1)
                    current_extinf_attrs = cls.parse_attributes(parts[0])
                    current_name = parts[1].strip() if len(parts) > 1 else "Sans nom"

                # Récupération du groupe
                current_group = current_extinf_attrs.get("group-title", "Général").strip() or "Général"

            elif line.startswith("#EXTGRP:"):
                # Tag alternatif pour le groupe
                grp = line.split(":", 1)[1].strip()
                if grp:
                    current_group = grp

            elif line.startswith("#EXTVLCOPT:") or line.startswith("#EXTOPT:"):
                opt = line.split(":", 1)[1].strip()
                if "=" in opt:
                    k, v = opt.split("=", 1)
                    k_lower = k.lower().replace("-", "_")
                    if "user_agent" in k_lower:
                        current_user_agent = v.strip()
                    elif "http_referrer" in k_lower or "referrer" in k_lower:
                        current_referrer = v.strip()

            elif line.startswith("#EXTHTTP:"):
                # Headers JSON
                try:
                    import json
                    json_str = line.split(":", 1)[1].strip()
                    extra_headers = json.loads(json_str)
                except Exception:
                    pass

            elif not line.startswith("#"):
                # C'est l'URL du flux
                stream_url = line

                # Détection du type de flux (live vs movie vs series)
                lower_url = stream_url.lower()
                stream_type = "live"
                container_ext = ""
                if any(lower_url.endswith(ext) or f"{ext}?" in lower_url for ext in [".mp4", ".mkv", ".avi", ".mov"]):
                    if "/series/" in lower_url:
                        stream_type = "series"
                    else:
                        stream_type = "movie"
                    container_ext = lower_url.split(".")[-1].split("?")[0]

                # Extraction date d'ajout si présente
                raw_added = current_extinf_attrs.get("added") or current_extinf_attrs.get("tvg-added") or current_extinf_attrs.get("date-added")
                added_at = None
                if raw_added:
                    try:
                        raw_clean = raw_added.strip()
                        if raw_clean.isdigit():
                            added_at = datetime.fromtimestamp(int(raw_clean)).isoformat()
                        else:
                            added_at = datetime.fromisoformat(raw_clean.replace(" ", "T")).isoformat()
                    except Exception:
                        pass
                if not added_at:
                    added_at = datetime.now().isoformat()

                # Création de l'objet Channel
                channel = Channel(
                    playlist_id=playlist_id,
                    name=current_name or "Chaîne inconnue",
                    stream_url=stream_url,
                    logo_url=current_extinf_attrs.get("tvg-logo", "").strip(),
                    group_title=current_group,
                    tvg_id=current_extinf_attrs.get("tvg-id", "").strip(),
                    tvg_name=current_extinf_attrs.get("tvg-name", "").strip(),
                    user_agent=current_user_agent or current_extinf_attrs.get("user-agent", ""),
                    http_referrer=current_referrer,
                    stream_type=stream_type,
                    container_extension=container_ext,
                    extra_headers=extra_headers.copy(),
                    added_at=added_at
                )
                channels.append(channel)
                count += 1
                if progress_callback and count % 500 == 0:
                    progress_callback(count)

                # Réinitialisation pour la prochaine chaîne
                current_extinf_attrs = {}
                current_name = ""
                current_user_agent = ""
                current_referrer = ""
                extra_headers = {}

        if progress_callback:
            progress_callback(count)

        return channels

    @classmethod
    def parse_file(cls, file_path: str, playlist_id: int = 0, progress_callback: Optional[Callable[[int], None]] = None) -> List[Channel]:
        """Lit et parse un fichier M3U local."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Fichier M3U introuvable : {file_path}")

        # Détection encodage utf-8 ou latin-1
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.parse_content(f, playlist_id, progress_callback)
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1") as f:
                return cls.parse_content(f, playlist_id, progress_callback)

    @classmethod
    def parse_url(cls, url: str, playlist_id: int = 0, user_agent: Optional[str] = None, progress_callback: Optional[Callable[[int], None]] = None) -> List[Channel]:
        """Télécharge et parse une playlist M3U distante."""
        headers = {
            "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            raw_data = response.read()
            # Décodage
            try:
                text = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_data.decode("latin-1", errors="ignore")
            lines = text.splitlines()
            return cls.parse_content(lines, playlist_id, progress_callback)
