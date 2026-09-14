"""
Client pour l'API Xtream Codes (Live, VOD, Séries avec saisons et épisodes, EPG).
"""

import json
import urllib.request
import urllib.parse
import base64
from datetime import datetime
from typing import Dict, List, Any, Optional
from core.models import Channel


def _parse_timestamp_or_date(val: Any) -> Optional[str]:
    """Parse un timestamp unix (entier ou chaîne numérique) ou une chaîne de date en ISO-8601."""
    if not val:
        return None
    try:
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(int(val)).isoformat()
        if isinstance(val, str):
            val_clean = val.strip()
            if not val_clean:
                return None
            if val_clean.isdigit():
                return datetime.fromtimestamp(int(val_clean)).isoformat()
            val_iso = val_clean.replace(" ", "T")
            return datetime.fromisoformat(val_iso).isoformat()
    except Exception:
        pass
    return None


class XtreamClient:
    def __init__(self, server_url: str, username: str, password: str, user_agent: Optional[str] = None):
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    def _get_api_url(self, params: Optional[Dict[str, str]] = None) -> str:
        base = f"{self.server_url}/player_api.php?username={urllib.parse.quote(self.username)}&password={urllib.parse.quote(self.password)}"
        if params:
            base += "&" + urllib.parse.urlencode(params)
        return base

    def _fetch_json(self, params: Optional[Dict[str, str]] = None) -> Any:
        url = self._get_api_url(params)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
            return json.loads(data)

    def authenticate(self) -> Dict[str, Any]:
        """Authentifie les identifiants Xtream et retourne les infos du compte."""
        data = self._fetch_json()
        user_info = data.get("user_info", {})
        if user_info.get("auth") != 1 and user_info.get("status") != "Active":
            raise ValueError(f"Authentification Xtream échouée: {user_info.get('message', 'Compte invalide')}")
        return data

    def get_live_categories(self) -> Dict[str, str]:
        """Retourne un dictionnaire {category_id: category_name}."""
        categories = self._fetch_json({"action": "get_live_categories"})
        if not isinstance(categories, list):
            return {}
        return {str(cat.get("category_id")): cat.get("category_name", "Général") for cat in categories if isinstance(cat, dict)}

    def get_vod_categories(self) -> Dict[str, str]:
        categories = self._fetch_json({"action": "get_vod_categories"})
        if not isinstance(categories, list):
            return {}
        return {str(cat.get("category_id")): cat.get("category_name", "Films") for cat in categories if isinstance(cat, dict)}

    def get_series_categories(self) -> Dict[str, str]:
        categories = self._fetch_json({"action": "get_series_categories"})
        if not isinstance(categories, list):
            return {}
        return {str(cat.get("category_id")): cat.get("category_name", "Séries") for cat in categories if isinstance(cat, dict)}

    def get_live_streams(self, playlist_id: int = 0) -> List[Channel]:
        """Récupère toutes les chaînes en direct."""
        categories = self.get_live_categories()
        streams = self._fetch_json({"action": "get_live_streams"})
        if not isinstance(streams, list):
            return []
        channels = []

        for s in streams:
            if not isinstance(s, dict):
                continue
            stream_id = str(s.get("stream_id", ""))
            cat_id = str(s.get("category_id", ""))
            group = categories.get(cat_id, "Direct")
            stream_url = f"{self.server_url}/live/{self.username}/{self.password}/{stream_id}.ts"

            added_at = _parse_timestamp_or_date(s.get("added"))

            ch = Channel(
                playlist_id=playlist_id,
                name=s.get("name", "Sans nom"),
                stream_url=stream_url,
                logo_url=s.get("stream_icon", ""),
                group_title=group,
                tvg_id=s.get("epg_channel_id", "") or str(s.get("stream_id", "")),
                tvg_name=s.get("name", ""),
                user_agent=self.user_agent,
                stream_type="live",
                stream_id=stream_id,
                rating=str(s.get("rating", "")),
                added_at=added_at,
                tv_archive=int(s.get("tv_archive") or 0),
                tv_archive_duration=int(s.get("tv_archive_duration") or 0)
            )
            channels.append(ch)
        return channels

    def get_vod_streams(self, playlist_id: int = 0) -> List[Channel]:
        """Récupère les films VOD."""
        categories = self.get_vod_categories()
        streams = self._fetch_json({"action": "get_vod_streams"})
        if not isinstance(streams, list):
            return []
        channels = []

        for s in streams:
            if not isinstance(s, dict):
                continue
            stream_id = str(s.get("stream_id", ""))
            ext = s.get("container_extension", "mp4")
            cat_id = str(s.get("category_id", ""))
            group = categories.get(cat_id, "Films")
            stream_url = f"{self.server_url}/movie/{self.username}/{self.password}/{stream_id}.{ext}"
            added_at = _parse_timestamp_or_date(s.get("added"))

            ch = Channel(
                playlist_id=playlist_id,
                name=s.get("name", "Film"),
                stream_url=stream_url,
                logo_url=s.get("stream_icon", ""),
                group_title=group,
                tvg_id="",
                user_agent=self.user_agent,
                stream_type="movie",
                stream_id=stream_id,
                container_extension=ext,
                rating=str(s.get("rating", "")),
                year=str(s.get("year", "")),
                added_at=added_at
            )
            channels.append(ch)
        return channels

    def get_series(self, playlist_id: int = 0) -> List[Channel]:
        """Récupère toutes les séries Xtream."""
        categories = self.get_series_categories()
        series_list = self._fetch_json({"action": "get_series"})
        if not isinstance(series_list, list):
            return []
        channels = []

        for s in series_list:
            if not isinstance(s, dict):
                continue
            series_id = str(s.get("series_id", ""))
            cat_id = str(s.get("category_id", ""))
            group = categories.get(cat_id, "Séries")
            added_at = _parse_timestamp_or_date(s.get("last_modified") or s.get("added") or s.get("releaseDate"))

            ch = Channel(
                playlist_id=playlist_id,
                name=s.get("name", "Série"),
                stream_url=f"xtream_series://{series_id}",
                logo_url=s.get("cover", ""),
                group_title=group,
                tvg_id="",
                user_agent=self.user_agent,
                stream_type="series",
                stream_id=series_id,
                rating=str(s.get("rating", "")),
                year=str(s.get("releaseDate", "") or s.get("year", "")),
                added_at=added_at
            )
            channels.append(ch)
        return channels

    def get_series_info(self, series_id: str) -> Dict[str, Any]:
        """Récupère les saisons, épisodes et synopsis d'une série."""
        return self._fetch_json({"action": "get_series_info", "series_id": str(series_id)})

    def get_vod_info(self, vod_id: str) -> Dict[str, Any]:
        """Récupère les détails enrichis d'un film VOD (synopsis, casting, durée, etc.)."""
        return self._fetch_json({"action": "get_vod_info", "vod_id": str(vod_id)})

    def get_episode_stream_url(self, episode_id: str, container_extension: str = "mp4") -> str:
        """Génère l'URL de lecture pour un épisode spécifique."""
        ext = container_extension.strip(".") or "mp4"
        return f"{self.server_url}/series/{self.username}/{self.password}/{episode_id}.{ext}"

    def get_epg_url(self) -> str:
        """Retourne l'URL XMLTV complète pour cette source Xtream."""
        return f"{self.server_url}/xmltv.php?username={urllib.parse.quote(self.username)}&password={urllib.parse.quote(self.password)}"

    def get_simple_data_table(self, stream_id: str) -> List[Dict[str, Any]]:
        """
        Récupère le guide EPG détaillé et les archives Replay d'une chaîne spécifique.
        Décode automatiquement les titres et descriptions encodés en Base64 par Xtream.
        """
        data = self._fetch_json({"action": "get_simple_data_table", "stream_id": str(stream_id)})
        if not isinstance(data, dict):
            return []
        listings = data.get("epg_listings", [])
        if not isinstance(listings, list):
            return []

        results = []
        for p in listings:
            if not isinstance(p, dict):
                continue
            raw_title = p.get("title", "")
            raw_desc = p.get("description", "")

            # Décodage Base64 sécurisé
            title = raw_title
            desc = raw_desc
            if raw_title:
                try:
                    title = base64.b64decode(raw_title).decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass
            if raw_desc:
                try:
                    desc = base64.b64decode(raw_desc).decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass

            results.append({
                "id": str(p.get("id", "")),
                "title": title or "Sans titre",
                "description": desc or "",
                "start": p.get("start", ""),
                "end": p.get("end", ""),
                "start_timestamp": p.get("start_timestamp", ""),
                "stop_timestamp": p.get("stop_timestamp", ""),
                "now_playing": bool(p.get("now_playing")),
                "has_archive": bool(p.get("has_archive") == 1 or str(p.get("has_archive")) == "1")
            })
        return results

    def get_timeshift_stream_url(self, stream_id: str, start_dt_or_str: Any, duration_minutes: int) -> str:
        """
        Génère l'URL de streaming timeshift/replay pour une émission passée.
        Format standard Xtream : {server_url}/timeshift/{username}/{password}/{duration_min}/{YYYY-MM-DD:HH-mm}/{stream_id}.ts
        """
        if isinstance(start_dt_or_str, datetime):
            start_fmt = start_dt_or_str.strftime("%Y-%m-%d:%H-%M")
        elif isinstance(start_dt_or_str, str):
            clean = start_dt_or_str.strip()
            try:
                if " " in clean:
                    dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
                elif "T" in clean:
                    dt = datetime.fromisoformat(clean)
                else:
                    dt = datetime.strptime(clean, "%Y-%m-%d:%H-%M")
                start_fmt = dt.strftime("%Y-%m-%d:%H-%M")
            except Exception:
                start_fmt = clean.replace(" ", ":").replace("/", "-")
        else:
            start_fmt = str(start_dt_or_str)

        dur = max(1, int(duration_minutes))
        return f"{self.server_url}/timeshift/{self.username}/{self.password}/{dur}/{start_fmt}/{stream_id}.ts"
