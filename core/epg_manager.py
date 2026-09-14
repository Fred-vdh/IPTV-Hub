"""
Gestionnaire et parseur EPG (XMLTV) haute performance pour l'IPTV.
Supporte les fichiers XML bruts et compressés (.gz).
"""

import gzip
import io
import urllib.request
import re
from pathlib import Path
from typing import List, Optional, Callable
import xml.etree.ElementTree as ET

from core.models import EPGProgram
from core.database import Database


def parse_xmltv_date(date_str: str) -> str:
    """
    Convertit une date XMLTV (ex: '20260831201500 +0200' ou '20260831201500') en format ISO 8601.
    """
    if not date_str:
        return ""
    clean = date_str.strip()
    match = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\s*([+-]\d{4})?", clean)
    if match:
        year, month, day, hour, minute, second, tz = match.groups()
        iso = f"{year}-{month}-{day}T{hour}:{minute}:{second}"
        if tz:
            iso += f"{tz[:3]}:{tz[3:]}"
        return iso
    return clean


class EPGManager:
    def __init__(self, db: Database):
        self.db = db

    def parse_xmltv_stream(
        self,
        stream,
        batch_size: int = 2000,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> int:
        """
        Parse un flux XMLTV avec iterparse pour minimiser l'empreinte mémoire.
        """
        context = ET.iterparse(stream, events=("end",))
        programs_batch: List[EPGProgram] = []
        total_count = 0

        for event, elem in context:
            if elem.tag == "programme":
                channel_id = elem.attrib.get("channel", "")
                start_raw = elem.attrib.get("start", "")
                stop_raw = elem.attrib.get("stop", "")

                title_elem = elem.find("title")
                desc_elem = elem.find("desc")
                category_elem = elem.find("category")
                icon_elem = elem.find("icon")

                title = title_elem.text if title_elem is not None and title_elem.text else "Programme"
                desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                category = category_elem.text if category_elem is not None and category_elem.text else ""
                icon_src = icon_elem.attrib.get("src", "") if icon_elem is not None else ""

                start_iso = parse_xmltv_date(start_raw)
                stop_iso = parse_xmltv_date(stop_raw)

                if channel_id and start_iso and stop_iso:
                    prog = EPGProgram(
                        tvg_id=channel_id,
                        title=title,
                        description=desc,
                        start_time=start_iso,
                        end_time=stop_iso,
                        category=category,
                        icon_url=icon_src
                    )
                    programs_batch.append(prog)
                    total_count += 1

                if len(programs_batch) >= batch_size:
                    self.db.save_epg_batch(programs_batch)
                    programs_batch = []
                    if progress_callback:
                        progress_callback(total_count)

                # Libération mémoire du nœud analysé
                elem.clear()

        if programs_batch:
            self.db.save_epg_batch(programs_batch)

        if progress_callback:
            progress_callback(total_count)

        return total_count

    def load_from_file(self, file_path: str, progress_callback: Optional[Callable[[int], None]] = None) -> int:
        """Charge l'EPG depuis un fichier local .xml ou .xml.gz."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Fichier EPG introuvable: {file_path}")

        if file_path.endswith(".gz"):
            with gzip.open(file_path, "rb") as gz_file:
                return self.parse_xmltv_stream(gz_file, progress_callback=progress_callback)
        else:
            with open(file_path, "rb") as f:
                return self.parse_xmltv_stream(f, progress_callback=progress_callback)

    def load_from_url(self, url: str, user_agent: Optional[str] = None, progress_callback: Optional[Callable[[int], None]] = None) -> int:
        """Télécharge et parse l'EPG depuis une URL distante."""
        headers = {
            "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as response:
            raw_data = response.read()

            # Vérification du magic number gzip (0x1f, 0x8b)
            if raw_data.startswith(b"\x1f\x8b") or url.endswith(".gz"):
                decompressed = gzip.decompress(raw_data)
                return self.parse_xmltv_stream(io.BytesIO(decompressed), progress_callback=progress_callback)
            else:
                return self.parse_xmltv_stream(io.BytesIO(raw_data), progress_callback=progress_callback)
