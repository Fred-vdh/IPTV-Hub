"""
Client API IntroDB pour la récupération des marqueurs de génériques (intro et outro).
Permet d'identifier le minutage exact du générique de fin pour proposer l'enchaînement
vers l'épisode suivant sans jamais perturber la narration.
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Optional, Tuple, Dict
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal

from core.models import IntroDBSegments
from core.tmdb_client import TMDB_API_KEY

logger = logging.getLogger(__name__)

INTRODB_API_URL = "https://api.introdb.app/segments"

# Cache mémoire pour éviter les résolutions répétées de titre -> IMDb ID
_IMDB_CACHE: Dict[str, Optional[str]] = {}


def extract_series_title_and_year(raw_name: str) -> Tuple[str, str]:
    """Extrait le nom épuré de la série et son année de production éventuelle."""
    name = str(raw_name or "").strip()
    # Supprimer les préfixes de pays comme |FR|, |EN|, |VF|, 🍿 |FR|, etc.
    name = re.sub(r"^[^\w\s]*\s*\|[A-Z0-9\-\s\+]+(?:\|[A-Z0-9\-\s\+]+)*\|\s*", "", name, flags=re.IGNORECASE)
    # Emoji / symboles au début
    name = re.sub(r"^[🎬🍿📺⭐✨🔥]\s*", "", name)

    # Si le nom contient un tiret cadratin ou séparateur d'épisode (ex: "Silo (2023) — S01E02..."),
    # ne conserver que la partie titre de série à gauche
    if "—" in name:
        name = name.split("—")[0].strip()
    elif " - " in name and re.search(r"\bS\d{1,2}E\d{1,2}\b", name, re.IGNORECASE):
        parts = name.split(" - ")
        name = parts[0].strip()

    # Chercher une année (19xx ou 20xx)
    year = ""
    m_year = re.search(r"\(?\b(19\d\d|20\d\d)\b\)?", name)
    if m_year:
        year = re.search(r"\b(19\d\d|20\d\d)\b", m_year.group(0)).group(1)
        name = name[:m_year.start()] + name[m_year.end():]

    # Nettoyer les parenthèses vides résiduelles et balises courantes
    name = re.sub(r"\(\s*\)", "", name)
    name = re.sub(r"\[\s*\]", "", name)
    name = re.sub(r"\((?:VF|VOSTFR|VO|MULTI|FRENCH|TRUEFRENCH)[^\)]*\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\[[^\]]*\]", "", name)
    name = re.sub(r"\bS\d{1,2}(?:E\d{1,2})?\b", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*[-—:/]\s*$", "", name)
    name = re.sub(r"^\s*[-—:/]\s*", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name, year


def parse_episode_season_and_num(channel_name: str, stream_url: str = "") -> Tuple[int, int]:
    """Détecte la saison et le numéro d'épisode depuis le titre ou l'URL."""
    text = f"{channel_name or ''} {stream_url or ''}"

    # 1. Format standard : S01E02 ou s1e5
    m = re.search(r"\bS(\d{1,2})\s*E(\d{1,3})\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 2. Format 1x05
    m = re.search(r"\b(\d{1,2})x(\d{1,3})\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 3. Format Saison X Episode Y
    m = re.search(r"\bSaison\s*(\d{1,2})\b.*?\b[ÉE]pisode\s*(\d{1,3})\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 4. Format Episode seul (assume saison 1)
    m = re.search(r"\b[ÉE]pisode\s*(\d{1,3})\b", text, re.IGNORECASE)
    if m:
        return 1, int(m.group(1))

    # Fallback par défaut
    return 1, 1


def get_imdb_id_for_series(series_name: str, year: str = "") -> Optional[str]:
    """Résout l'identifiant IMDb (tt...) d'une série via l'API TMDB."""
    clean_name, extracted_year = extract_series_title_and_year(series_name)
    y = year or extracted_year

    cache_key = f"{clean_name.lower()}::{y}"
    if cache_key in _IMDB_CACHE:
        return _IMDB_CACHE[cache_key]

    if not clean_name:
        _IMDB_CACHE[cache_key] = None
        return None

    try:
        q = urllib.parse.quote(clean_name)
        url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={q}"
        if y:
            url += f"&first_air_date_year={y}"

        req = urllib.request.Request(url, headers={"User-Agent": "IPTV-Hub/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        results = data.get("results", []) if data else []
        if not results and y:
            # Essai de secours sans filtrer sur l'année
            url_no_year = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={q}"
            req = urllib.request.Request(url_no_year, headers={"User-Agent": "IPTV-Hub/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            results = data.get("results", []) if data else []

        if not results:
            _IMDB_CACHE[cache_key] = None
            return None

        tmdb_id = results[0].get("id")
        if not tmdb_id:
            _IMDB_CACHE[cache_key] = None
            return None

        # Récupération des external IDs de la série
        ext_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids?api_key={TMDB_API_KEY}"
        req = urllib.request.Request(ext_url, headers={"User-Agent": "IPTV-Hub/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            ext_data = json.loads(resp.read().decode())

        imdb_id = ext_data.get("imdb_id") if ext_data else None
        _IMDB_CACHE[cache_key] = imdb_id
        return imdb_id

    except Exception as e:
        logger.warning("Erreur lors de la résolution IMDb pour '%s': %s", series_name, e)
        _IMDB_CACHE[cache_key] = None
        return None


def fetch_introdb_segments(
    imdb_id: str,
    season: int,
    episode: int,
    db=None
) -> Optional[IntroDBSegments]:
    """Récupère les segments IntroDB (intro/outro) pour un épisode donné.

    Consulte d'abord le cache local SQLite (si db fourni), sinon interroge l'API IntroDB.
    """
    if not imdb_id or not str(imdb_id).startswith("tt"):
        return None

    # 1. Vérifier le cache SQLite local
    if db is not None:
        try:
            cached = db.get_introdb_segments(imdb_id, season, episode)
            if cached is not None:
                return cached
        except Exception as e:
            logger.debug("Erreur lecture cache local IntroDB: %s", e)

    # 2. Requête API IntroDB
    url = f"{INTRODB_API_URL}?imdb_id={imdb_id}&season={int(season)}&episode={int(episode)}"
    req = urllib.request.Request(url, headers={"User-Agent": "IPTV-Hub/1.0 (Desktop Player)"})

    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode())

        intro = data.get("intro") or {}
        outro = data.get("outro") or {}

        segments = IntroDBSegments(
            imdb_id=imdb_id,
            season=int(season),
            episode=int(episode),
            intro_start=intro.get("start_sec"),
            intro_end=intro.get("end_sec"),
            outro_start=outro.get("start_sec"),
            outro_end=outro.get("end_sec"),
            confidence=outro.get("confidence") or intro.get("confidence"),
            submission_count=outro.get("submission_count") or intro.get("submission_count") or 0,
            updated_at=datetime.now().isoformat()
        )

        # 3. Enregistrer dans le cache SQLite local
        if db is not None:
            try:
                db.save_introdb_segments(segments)
            except Exception as e:
                logger.debug("Erreur sauvegarde cache local IntroDB: %s", e)

        return segments

    except Exception as e:
        logger.debug("IntroDB non disponible ou aucun segment pour %s S%02dE%02d: %s", imdb_id, season, episode, e)
        return None


class IntroDBWorker(QThread):
    """Thread d'arrière-plan pour rechercher les marqueurs IntroDB sans bloquer la lecture."""
    segments_ready = pyqtSignal(object)  # Émet IntroDBSegments ou None

    def __init__(self, series_name: str, season: int, episode: int, db=None, parent=None):
        super().__init__(parent)
        self.series_name = series_name
        self.season = season
        self.episode = episode
        self.db = db

    def run(self):
        try:
            imdb_id = get_imdb_id_for_series(self.series_name)
            if not imdb_id:
                self.segments_ready.emit(None)
                return

            segments = fetch_introdb_segments(
                imdb_id=imdb_id,
                season=self.season,
                episode=self.episode,
                db=self.db
            )
            self.segments_ready.emit(segments)
        except Exception as e:
            logger.debug("Exception dans IntroDBWorker: %s", e)
            self.segments_ready.emit(None)
