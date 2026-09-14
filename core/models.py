"""
Modèles de données pour l'application IPTV.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any


@dataclass
class Playlist:
    id: Optional[int] = None
    name: str = ""
    url_or_path: str = ""
    playlist_type: str = "m3u"  # "m3u", "xtream"
    server_url: str = ""
    username: str = ""
    password: str = ""
    epg_url: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    channel_count: int = 0
    account_status: Optional[str] = None
    exp_date: Optional[str] = None
    max_connections: Optional[str] = None
    active_cons: Optional[str] = None


@dataclass
class Channel:
    id: Optional[int] = None
    playlist_id: int = 0
    name: str = ""
    stream_url: str = ""
    logo_url: str = ""
    group_title: str = "Général"
    tvg_id: str = ""
    tvg_name: str = ""
    user_agent: str = ""
    http_referrer: str = ""
    is_favorite: bool = False
    is_enabled: bool = True
    stream_type: str = "live"  # "live", "movie", "series"
    stream_id: Optional[str] = None  # Xtream stream ID
    container_extension: str = ""
    rating: str = ""
    year: str = ""
    extra_headers: Dict[str, str] = field(default_factory=dict)
    favorite_added_at: Optional[str] = None
    added_at: Optional[str] = None
    tv_archive: int = 0
    tv_archive_duration: int = 0


def parse_movie_metadata(name: str, raw_rating: str = "", raw_year: str = "") -> Dict[str, str]:
    """
    Extrait les métadonnées d'un film à partir de son nom et des données brutes :
    - title: Titre formaté
    - year: Année (ex: "2026")
    - quality_tag: Tag audio / qualité (ex: "MULTI VFF", "VFF", "MULTI VFQ", "4K", etc.)
    - rating: Note formatée (ex: "7.3")
    """
    clean_name = name.strip()

    # 1. Extraction de la qualité / format audio
    quality_patterns = [
        r"\b(MULTI\s+VFF)\b", r"\b(MULTI\s+VFQ)\b", r"\b(MULTI\s+VF)\b",
        r"\b(MULTI\s+VOSTFR)\b", r"\b(MULTI)\b", r"\b(VFF)\b", r"\b(VFQ)\b",
        r"\b(TRUEFRENCH)\b", r"\b(FRENCH)\b", r"\b(VOSTFR)\b", r"\b(VOST)\b",
        r"\b(4K\s+HDR)\b", r"\b(4K\s+UHD)\b", r"\b(4K\s+DOLBY\s+VISION)\b", r"\b(4K)\b", r"\b(UHD)\b",
        r"\b(1080P|FHD)\b", r"\b(720P|HD)\b", r"\b(HEVC|X265|H265)\b",
        r"\b(DOLBY\s+VISION)\b"
    ]
    quality_tag = ""
    for pat in quality_patterns:
        m = re.search(pat, clean_name, re.IGNORECASE)
        if m:
            quality_tag = m.group(1).upper()
            break

    # 2. Extraction de l'année
    year = str(raw_year).strip() if raw_year is not None else ""
    if not year:
        m_year = re.search(r"\((\d{4})\)|\[(\d{4})\]|\b(19\d{2}|20\d{2})\b", clean_name)
        if m_year:
            year = m_year.group(1) or m_year.group(2) or m_year.group(3)

    # 3. Extraction de la note
    rating = str(raw_rating).strip() if raw_rating is not None else ""
    if not rating:
        m_rat = re.search(r"★\s*(\d+(?:\.\d+)?)|(?:rating|note|imdb)\s*[:=]\s*(\d+(?:\.\d+)?)", clean_name, re.IGNORECASE)
        if m_rat:
            rating = m_rat.group(1) or m_rat.group(2)

    # Formatage de la note
    if rating:
        try:
            r_val = float(rating)
            if r_val > 10.0 and r_val <= 100.0:
                r_val = r_val / 10.0
            rating = f"{r_val:.1f}"
        except Exception:
            pass

    return {
        "title": clean_name,
        "year": year,
        "quality_tag": quality_tag,
        "rating": rating
    }


@dataclass
class EPGProgram:
    id: Optional[int] = None
    tvg_id: str = ""
    title: str = ""
    description: str = ""
    start_time: str = ""  # ISO format string or timestamp
    end_time: str = ""    # ISO format string or timestamp
    category: str = ""
    icon_url: str = ""

    def is_current(self, now: Optional[datetime] = None) -> bool:
        """Indique si le programme est actuellement en cours de diffusion."""
        if not self.start_time or not self.end_time:
            return False
        if now is None:
            now = datetime.now().astimezone()
        try:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            # Conversion pour comparaison cohérente de fuseaux horaires
            if start.tzinfo is None and now.tzinfo is not None:
                start = start.astimezone()
            if end.tzinfo is None and now.tzinfo is not None:
                end = end.astimezone()
            return start <= now <= end
        except Exception:
            return False

    def progress_percentage(self, now: Optional[datetime] = None) -> float:
        """Calcule le pourcentage d'avancement du programme (0 à 100)."""
        if not self.start_time or not self.end_time:
            return 0.0
        if now is None:
            now = datetime.now().astimezone()
        try:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            if start.tzinfo is None and now.tzinfo is not None:
                start = start.astimezone()
            if end.tzinfo is None and now.tzinfo is not None:
                end = end.astimezone()

            total_seconds = (end - start).total_seconds()
            if total_seconds <= 0:
                return 0.0
            elapsed = (now - start).total_seconds()
            return max(0.0, min(100.0, (elapsed / total_seconds) * 100.0))
        except Exception:
            return 0.0

    @property
    def start_time_display(self) -> str:
        if not self.start_time:
            return ""
        try:
            dt = datetime.fromisoformat(self.start_time)
            return dt.strftime("%H:%M")
        except Exception:
            return self.start_time[:5] if len(self.start_time) >= 5 else ""

    @property
    def end_time_display(self) -> str:
        if not self.end_time:
            return ""
        try:
            dt = datetime.fromisoformat(self.end_time)
            return dt.strftime("%H:%M")
        except Exception:
            return self.end_time[:5] if len(self.end_time) >= 5 else ""


@dataclass
class WatchHistory:
    id: Optional[int] = None
    channel_id: int = 0
    channel_name: str = ""
    stream_url: str = ""
    logo_url: str = ""
    group_title: str = ""
    watched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    playback_position: float = 0.0
    duration: float = 0.0


@dataclass
class AppSettings:
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    hwdec: str = "auto"  # "auto", "d3d11va", "nvdec", "no"
    buffer_size_mb: int = 32
    default_aspect_ratio: str = "-1"  # "-1" = auto, "16:9", "4:3", etc.
    volume: int = 80
    theme: str = "dark"
    auto_refresh_epg: bool = True
    epg_refresh_hours: int = 24
    cache_logos: bool = True
    deinterlace: bool = False
    preferred_audio_lang: str = "fre,fra,fr,French,français"
    preferred_subtitle_lang: str = "off"
    subtitles_enabled: bool = False
    outer_splitter_sizes: str = "640,780"
    inner_splitter_sizes: str = "280,360"
    category_panel_width: int = 280
    channel_list_width: int = 360
    categories_collapsed: bool = False
    epg_panel_height: int = 220
    epg_panel_visible: bool = True
    window_x: int = -1
    window_y: int = -1
    window_width: int = 1400
    window_height: int = 850
    window_maximized: bool = False
    window_fullscreen: bool = False
    download_dir: str = ""
    sync_enabled: bool = False
    sync_folder: str = ""
    sync_last_timestamp: str = ""
    auto_play_next_episode: bool = True

def clean_category_display_name(name: str) -> str:
    """
    Nettoie un nom de catégorie pour l'affichage :
    - Supprime les émojis et symboles d'icônes en tête (🎬, 🍿, 📺, ⓟ, etc.)
    - Supprime les bannières / préfixes serveurs récurrents tels que 'TV  ║  ', 'LIVE  ║  ', etc.
    Retourne un nom épuré et lisible respectant la charte graphique de l'application.
    """
    if not name:
        return ""
    # 1. Suppression des émojis et symboles spéciaux au début (émojis Unicode, symboles divers, caractères entourés)
    cleaned = re.sub(
        r"^[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u2460-\u24ff\u2022\u25a0-\u25ff\s]+",
        "",
        str(name)
    )
    # 2. Suppression des préfixes bannières serveurs (ex: 'TV  ║  ', 'TV | ', 'LIVE ║ ')
    cleaned = re.sub(
        r"^(?:TV\s*[║\|]\s*|LIVE\s*[║\|]\s*|VOD\s*[║\|]\s*|SERIES?\s*[║\|]\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = cleaned.strip()
    return cleaned or str(name)


def normalize_category_name(name: str) -> str:
    """Normalise un nom de catégorie (suppression des accents, emojis et ponctuation pour comparaison robuste)."""
    if not name:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(name))
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    clean = re.sub(r"[^\w\s\d]", " ", no_accents).upper()
    return re.sub(r"\s+", " ", clean).strip()


def prioritize_categories(cat_list: List[Any]) -> List[Any]:
    """
    Trie les catégories de films ou séries en plaçant en tête de liste :
    1. Les catégories 'Nouveautés' / 'Récents' / 'New'
    2. Les catégories 'Top 100' / 'Top' / 'Populaires'
    3. Les autres catégories (ordre conservé)

    Fonctionne avec des tuples (cat_name, count) ou des chaînes simples.
    """
    if not cat_list:
        return []

    rank_1_new = []
    rank_2_top = []
    rank_3_others = []

    new_keywords = (
        "NOUVEAUTE", "NOUVEAUTES", "NOUVEAU", "NOUVELLE", "NOUVELLES",
        "NEW", "RECENT", "RECENTS", "RECENTES", "DERNIER", "DERNIERS",
        "DERNIERE", "DERNIERES", "AJOUT", "AJOUTS", "LATEST", "SORTIE", "SORTIES"
    )

    top_keywords = (
        "TOP 100", "TOP 50", "TOP 20", "TOP 10", "TOP100", "TOP50", "TOP20", "TOP10",
        "TOP", "POPULAIRE", "POPULAIRES", "TENDANCE", "TENDANCES",
        "MEILLEUR", "MEILLEURS", "MEILLEURE", "MEILLEURES",
        "BEST", "TRENDING", "BOX OFFICE", "IMDB"
    )

    for item in cat_list:
        if isinstance(item, (tuple, list)):
            cat_name = str(item[0])
        else:
            cat_name = str(item)

        norm = normalize_category_name(cat_name)
        tokens = set(norm.split())

        # Vérification Rang 1 (Nouveautés)
        is_new = any(kw in tokens or kw in norm for kw in new_keywords)
        # Vérification Rang 2 (Top 100 / Top)
        is_top = any(kw in tokens or kw in norm for kw in top_keywords)

        if is_new:
            rank_1_new.append(item)
        elif is_top:
            rank_2_top.append(item)
        else:
            rank_3_others.append(item)

    return rank_1_new + rank_2_top + rank_3_others


def format_seconds(seconds: float) -> str:
    """Formate des secondes en HH:MM:SS ou MM:SS."""
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

