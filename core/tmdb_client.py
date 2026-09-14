"""
Client API The Movie Database (TMDB) pour récupérer les avis et métadonnées complémentaires.
Ce module est conçu de manière autonome pour pouvoir être modifié ou supprimé facilement.
"""

import json
import re
import ssl
import logging
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

TMDB_API_KEY = "f090bb54758cabf231fb605d3e3e0468"
BASE_URL = "https://api.themoviedb.org/3"


def _get_ssl_context() -> ssl.SSLContext:
    """Retourne un contexte SSL valide (avec certifi si disponible, ou fallback)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        return ssl.create_default_context()
    except Exception:
        return ssl._create_unverified_context()


def _fetch_tmdb_json(url: str, timeout: int = 12) -> Optional[Dict[str, Any]]:
    """
    Exécute une requête HTTP TMDB robuste avec gestion des certificats SSL et du timeout.
    Gère gracieusement les environnements de machines virtuelles et Windows vierges.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    ctx = _get_ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except ssl.SSLCertVerificationError:
        # Fallback pour les environnements où les certificats racines Windows ne sont pas encore peuplés
        try:
            unverified_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=unverified_ctx) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning("Erreur TMDB SSL fallback: %s (%s)", url, e)
    except Exception as e:
        logger.warning("Erreur requête TMDB: %s (%s)", url, e)
    return None



def get_tmdb_language_code(preferred_audio_lang: str) -> str:
    """Convertit la préférence de langue audio de l'application en code langue TMDB."""
    pref = (preferred_audio_lang or "").lower()
    if any(k in pref for k in ("fr", "fra", "fre", "french", "français", "francais", "vf")):
        return "fr-FR"
    elif any(k in pref for k in ("en", "eng", "english", "anglais", "vo")):
        return "en-US"
    elif any(k in pref for k in ("es", "spa", "spanish", "espagnol", "espanol")):
        return "es-ES"
    elif any(k in pref for k in ("de", "ger", "deu", "german", "allemand")):
        return "de-DE"
    elif any(k in pref for k in ("it", "ita", "italian", "italien")):
        return "it-IT"
    elif any(k in pref for k in ("pt", "por", "portuguese", "portugais")):
        return "pt-PT"
    elif any(k in pref for k in ("ar", "ara", "arabic", "arabe")):
        return "ar-SA"
    return "fr-FR"


def clean_search_title(raw_title: str) -> str:
    """Nettoie un titre pour maximiser la pertinence de recherche TMDB."""
    t = str(raw_title or "").strip()
    # Supprimer les balises courantes [MULTI], 4K, FHD, VF, VOSTFR, etc.
    t = re.sub(r"\[.*?\]|\(.*?\)", " ", t)
    t = re.sub(
        r"\b(MULTI|TRUEFRENCH|FRENCH|VOSTFR|VOST|VF|VFF|VFQ|4K|UHD|HDR|1080P|720P|FHD|HD|HEVC|H265|X265|WEB-DL|BLURAY|DVDRIP)\b",
        " ",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\bS\d{1,2}(?:E\d{1,2})?\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\bSaison\s*\d+\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"[^\w\s\d]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def search_tmdb_id(media_type: str, title: str, year: str = "") -> Optional[str]:
    """Recherche l'identifiant TMDB d'un film ou d'une série par son titre et année."""
    clean_t = clean_search_title(title)
    if not clean_t:
        return None

    api_type = "movie" if media_type == "movie" else "tv"
    q = urllib.parse.quote(clean_t)
    url = f"{BASE_URL}/search/{api_type}?api_key={TMDB_API_KEY}&query={q}"
    if year and year.isdigit() and len(year) == 4:
        if api_type == "movie":
            url += f"&year={year}"
        else:
            url += f"&first_air_date_year={year}"

    data = _fetch_tmdb_json(url)
    if data:
        results = data.get("results", [])
        if results:
            return str(results[0].get("id", ""))
    return None


def find_best_trailer(
    media_type: str,  # "movie" ou "tv"
    tmdb_id: str = "",
    title: str = "",
    year: str = "",
    preferred_audio_lang: str = "fre,fra,fr",
    orig_trailer: str = "",
) -> Dict[str, Any]:
    """
    Recherche la meilleure bande-annonce YouTube disponible :
    1. Dans la langue préférée configurée (ex: VF / VOSTFR pour le français)
    2. En fallback : bande-annonce originale (VO) TMDB
    3. En ultime fallback : trailer fourni par le serveur Xtream
    """
    target_lang = get_tmdb_language_code(preferred_audio_lang)
    api_type = "movie" if media_type == "movie" else "tv"

    clean_id = str(tmdb_id or "").strip()
    if not clean_id or not clean_id.isdigit():
        clean_id = search_tmdb_id(api_type, title, year) or ""

    def _fetch_videos(lang: str = "") -> List[Dict[str, Any]]:
        if not clean_id:
            return []
        u = f"{BASE_URL}/{api_type}/{clean_id}/videos?api_key={TMDB_API_KEY}"
        if lang:
            u += f"&language={lang}"
        d = _fetch_tmdb_json(u)
        if d:
            return [
                v for v in d.get("results", [])
                if v.get("site") == "YouTube" and v.get("key")
            ]
        return []

    # 1. Recherche dans la langue préférée (ex: fr-FR puis fr)
    vids = _fetch_videos(target_lang)
    if not vids and "-" in target_lang:
        vids = _fetch_videos(target_lang.split("-")[0])

    if vids:
        # Prioriser les Trailers sur les Teasers / Clips
        trailers = [v for v in vids if v.get("type") == "Trailer"]
        target_list = trailers if trailers else vids

        # Détection VF prioritaire si en français
        if target_lang.startswith("fr"):
            vf_list = [
                v for v in target_list
                if "vf" in v.get("name", "").lower()
                or "français" in v.get("name", "").lower()
                or "francais" in v.get("name", "").lower()
            ]
            if vf_list:
                return {
                    "key": vf_list[0].get("key"),
                    "name": vf_list[0].get("name", "Bande-annonce VF"),
                    "badge": "VF",
                    "site": "YouTube",
                    "is_fallback": False,
                }
            vost_list = [v for v in target_list if "vost" in v.get("name", "").lower()]
            if vost_list:
                return {
                    "key": vost_list[0].get("key"),
                    "name": vost_list[0].get("name", "Bande-annonce VOST"),
                    "badge": "VOSTFR",
                    "site": "YouTube",
                    "is_fallback": False,
                }
            return {
                "key": target_list[0].get("key"),
                "name": target_list[0].get("name", "Bande-annonce"),
                "badge": "VF",
                "site": "YouTube",
                "is_fallback": False,
            }
        else:
            lang_short = target_lang.split("-")[0].upper()
            return {
                "key": target_list[0].get("key"),
                "name": target_list[0].get("name", "Bande-annonce"),
                "badge": lang_short,
                "site": "YouTube",
                "is_fallback": False,
            }

    # 2. Fallback TMDB : Version originale / multilingue
    vids_vo = _fetch_videos("")
    if vids_vo:
        trailers_vo = [v for v in vids_vo if v.get("type") == "Trailer"]
        chosen = trailers_vo[0] if trailers_vo else vids_vo[0]
        return {
            "key": chosen.get("key"),
            "name": chosen.get("name", "Trailer (VO)"),
            "badge": "VO",
            "site": "YouTube",
            "is_fallback": True,
        }

    # 3. Fallback ultime : Trailer d'origine fourni par le serveur Xtream
    orig_clean = str(orig_trailer or "").strip()
    if orig_clean:
        # Extraire l'ID si c'est une URL
        orig_key = orig_clean
        if "v=" in orig_clean:
            orig_key = orig_clean.split("v=")[1].split("&")[0]
        elif "youtu.be/" in orig_clean:
            orig_key = orig_clean.split("youtu.be/")[1].split("?")[0]

        return {
            "key": orig_key,
            "name": "Bande-annonce d'origine",
            "badge": "VO",
            "site": "YouTube",
            "is_fallback": True,
        }

    return {}


def get_movie_reviews(tmdb_id: str) -> List[Dict[str, Any]]:
    """
    Récupère les avis des spectateurs pour un film donné depuis l'API TMDB.
    Tente d'abord en français, puis en fallback global si aucun avis n'est disponible en français.
    """
    if not tmdb_id:
        return []

    clean_id = str(tmdb_id).strip()
    if not clean_id.isdigit():
        return []

    def _fetch_reviews(lang: str = "") -> List[Dict[str, Any]]:
        url = f"{BASE_URL}/movie/{clean_id}/reviews?api_key={TMDB_API_KEY}"
        if lang:
            url += f"&language={lang}"
        data = _fetch_tmdb_json(url)
        if data:
            results = data.get("results", [])
            formatted = []
            for r in results:
                author_details = r.get("author_details", {}) or {}
                formatted.append({
                    "id": r.get("id", ""),
                    "author": r.get("author", "Spectateur"),
                    "username": author_details.get("username", ""),
                    "rating": author_details.get("rating"),
                    "created_at": str(r.get("created_at", ""))[:10],
                    "content": r.get("content", "").strip(),
                    "url": r.get("url", "")
                })
            return formatted
        return []

    # 1. Essai en français
    reviews_fr = _fetch_reviews("fr-FR")
    if reviews_fr:
        return reviews_fr

    # 2. Fallback multilingue / anglais
    return _fetch_reviews("")


# ------------------ ARTISTES / FILMOGRAPHIE CROISÉE ------------------

def search_person(name: str, language: str = "fr-FR") -> Optional[Dict[str, Any]]:
    """
    Recherche un acteur ou réalisateur par son nom sur TMDB.
    Retourne ses informations de base (id, nom, photo de profil, département, popularité).
    """
    clean_name = str(name or "").strip()
    if not clean_name:
        return None

    q = urllib.parse.quote(clean_name)
    url = f"{BASE_URL}/search/person?api_key={TMDB_API_KEY}&query={q}&language={language}"
    data = _fetch_tmdb_json(url)
    if data:
        results = data.get("results", [])
        if results:
            return results[0]

    # Fallback : si la recherche avec filtre de langue ne donne rien, tester sans filtre de langue
    if language:
        url_fallback = f"{BASE_URL}/search/person?api_key={TMDB_API_KEY}&query={q}"
        data_fb = _fetch_tmdb_json(url_fallback)
        if data_fb:
            results_fb = data_fb.get("results", [])
            if results_fb:
                return results_fb[0]

    return None


def search_persons_list(name: str, language: str = "fr-FR", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Recherche une liste de personnes correspondantes sur TMDB.
    Retourne jusqu'à 'limit' candidats triés par pertinence/popularité.
    """
    clean_name = str(name or "").strip()
    if not clean_name:
        return []

    q = urllib.parse.quote(clean_name)
    url = f"{BASE_URL}/search/person?api_key={TMDB_API_KEY}&query={q}&language={language}"
    data = _fetch_tmdb_json(url)
    if data:
        results = data.get("results", [])
        if results:
            return results[:limit]

    # Fallback sans filtre de langue
    if language:
        url_fallback = f"{BASE_URL}/search/person?api_key={TMDB_API_KEY}&query={q}"
        data_fb = _fetch_tmdb_json(url_fallback)
        if data_fb:
            results_fb = data_fb.get("results", [])
            if results_fb:
                return results_fb[:limit]

    return []


def get_person_details_and_credits(person_id: int, language: str = "fr-FR") -> Dict[str, Any]:
    """
    Récupère la fiche détaillée d'un artiste et l'ensemble de ses crédits (films et séries,
    aussi bien en tant qu'acteur que réalisateur/équipe).
    """
    if not person_id:
        return {}

    url = f"{BASE_URL}/person/{person_id}?api_key={TMDB_API_KEY}&language={language}&append_to_response=combined_credits"
    data = _fetch_tmdb_json(url) or {}

    # Si la biographie est absente dans la langue demandée (ex: non traduite en français),
    # tenter de récupérer la biographie en version originale (anglais) en fallback
    if data and not data.get("biography") and language not in ("en-US", "en"):
        url_en = f"{BASE_URL}/person/{person_id}?api_key={TMDB_API_KEY}&language=en-US"
        en_data = _fetch_tmdb_json(url_en)
        if en_data and en_data.get("biography"):
            data["biography"] = en_data["biography"]

    return data


def normalize_title_for_matching(title: str) -> str:
    """Normalise un titre de film ou série pour un matching insensible aux balises IPTV, ponctuation et casse."""
    if not title:
        return ""
    t = re.sub(r"\[.*?\]|\(.*?\)|\|.*?\|", " ", title)
    t = re.sub(
        r"\b(MULTI|TRUEFRENCH|FRENCH|VOSTFR|VOST|VF|VFF|VFQ|4K|UHD|HDR|1080P|720P|FHD|HD|HEVC|H265|X265|WEB-DL|BLURAY|DVDRIP|(?:SAISON|SEASON|S)\s*\d+(?:-S?\d+)?)\b",
        " ",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", t)
    t = re.sub(r"[^\w\d]", "", t).lower()
    return t.strip()


def _extract_year(val: Any, fallback_text: str = "") -> Optional[int]:
    """Extrait une année sur 4 chiffres de manière sécurisée sans jamais lever d'exception."""
    if val:
        m = re.search(r"\b(19\d{2}|20\d{2})\b", str(val))
        if m:
            return int(m.group(1))
    if fallback_text:
        m2 = re.search(r"\((\d{4})\)", str(fallback_text))
        if m2:
            return int(m2.group(1))
    return None


def match_artist_credits_with_library(
    credits_data: Dict[str, Any],
    library_channels: List[Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Croise la filmographie TMDB d'un artiste avec la liste des chaînes/médias locaux.
    Sépare rigoureusement les résultats en :
    - 'movies' : Films où l'artiste joue (cast)
    - 'series' : Séries où l'artiste joue (cast)
    - 'directed' : Films ou séries réalisés par l'artiste (crew avec job == 'Director')
    """
    result: Dict[str, List[Dict[str, Any]]] = {
        "movies": [],
        "series": [],
        "directed": [],
    }

    if not credits_data or not library_channels:
        return result

    # Indexation de la bibliothèque locale
    # Structure : {norm_title: [Channel, ...]}
    movies_by_norm: Dict[str, List[Any]] = {}
    series_by_norm: Dict[str, List[Any]] = {}

    for ch in library_channels:
        st = getattr(ch, "stream_type", "") or ""
        name = getattr(ch, "name", "") or ""
        norm = normalize_title_for_matching(name)
        if not norm:
            continue

        if st in ("movie", "vod"):
            movies_by_norm.setdefault(norm, []).append(ch)
        elif st == "series":
            series_by_norm.setdefault(norm, []).append(ch)

    combined = credits_data.get("combined_credits", {})
    cast_list = combined.get("cast", [])
    crew_list = combined.get("crew", [])

    seen_movie_ids = set()
    seen_series_ids = set()
    seen_directed_ids = set()

    def _find_best_match(
        target_dict: Dict[str, List[Any]],
        fr_title: str,
        orig_title: str,
        year: str,
        is_movie: bool = True,
    ) -> Optional[Any]:
        norm_fr = normalize_title_for_matching(fr_title)
        norm_orig = normalize_title_for_matching(orig_title)

        candidates = target_dict.get(norm_fr, []) or target_dict.get(norm_orig, [])
        if not candidates:
            # Recherche par préfixe uniquement pour les titres avec longueur significative et proche
            for norm in (norm_fr, norm_orig):
                if not norm or len(norm) < 6:
                    continue
                for k, items in target_dict.items():
                    if len(k) < 6:
                        continue
                    if (k.startswith(norm) or norm.startswith(k)) and abs(len(k) - len(norm)) <= 3:
                        candidates = items
                        break
                if candidates:
                    break

        if not candidates:
            return None

        t_yr = _extract_year(year)
        if t_yr is not None:
            matching_year_candidates = []
            for c in candidates:
                c_yr = _extract_year(getattr(c, "year", ""), getattr(c, "name", ""))
                if c_yr is not None:
                    # Pour les films : tolérance de 2 ans (décalage de sortie internationale)
                    # Pour les séries : tolérance plus large (5 ans) car les saisons s'étalent
                    max_diff = 2 if is_movie else 5
                    if abs(c_yr - t_yr) <= max_diff:
                        matching_year_candidates.append(c)
                else:
                    # Année non renseignée en local : on retient le candidat
                    matching_year_candidates.append(c)

            if matching_year_candidates:
                return matching_year_candidates[0]
            else:
                # Tous les candidats locaux ont une année trop différente (ex: remake ultérieur)
                return None

        return candidates[0]

    # 1. Traitement des rôles d'acteur (Cast)
    for item in cast_list:
        m_type = item.get("media_type")
        fr_t = item.get("title") if m_type == "movie" else item.get("name")
        orig_t = item.get("original_title") if m_type == "movie" else item.get("original_name")
        rel_date = item.get("release_date") if m_type == "movie" else item.get("first_air_date")
        yr = str(rel_date or "")[:4] if rel_date else ""
        role = item.get("character", "").strip() or "Rôle non spécifié"

        if m_type == "movie":
            match = _find_best_match(movies_by_norm, fr_t or "", orig_t or "", yr, is_movie=True)
            if match and match.id not in seen_movie_ids:
                seen_movie_ids.add(match.id)
                result["movies"].append({
                    "channel": match,
                    "role": role,
                    "character": role,
                    "title": fr_t or match.name,
                    "year": yr or getattr(match, "year", ""),
                    "rating": str(item.get("vote_average", ""))[:3],
                    "poster_path": item.get("poster_path", ""),
                })
        elif m_type == "tv":
            match = _find_best_match(series_by_norm, fr_t or "", orig_t or "", yr, is_movie=False)
            if match and match.id not in seen_series_ids:
                seen_series_ids.add(match.id)
                result["series"].append({
                    "channel": match,
                    "role": role,
                    "character": role,
                    "title": fr_t or match.name,
                    "year": yr or getattr(match, "year", ""),
                    "rating": str(item.get("vote_average", ""))[:3],
                    "poster_path": item.get("poster_path", ""),
                })

    # 2. Traitement des rôles de réalisation (Crew -> Director)
    for item in crew_list:
        if item.get("job") != "Director":
            continue
        m_type = item.get("media_type")
        fr_t = item.get("title") if m_type == "movie" else item.get("name")
        orig_t = item.get("original_title") if m_type == "movie" else item.get("original_name")
        rel_date = item.get("release_date") if m_type == "movie" else item.get("first_air_date")
        yr = str(rel_date or "")[:4] if rel_date else ""

        target_dict = movies_by_norm if m_type == "movie" else series_by_norm
        match = _find_best_match(target_dict, fr_t or "", orig_t or "", yr, is_movie=(m_type == "movie"))
        if match and match.id not in seen_directed_ids:
            seen_directed_ids.add(match.id)
            result["directed"].append({
                "channel": match,
                "role": "Réalisateur",
                "character": "Réalisateur",
                "title": fr_t or match.name,
                "media_type": m_type,
                "year": yr or getattr(match, "year", ""),
                "rating": str(item.get("vote_average", ""))[:3],
                "poster_path": item.get("poster_path", ""),
            })

    return result


