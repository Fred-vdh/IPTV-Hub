"""
Module de synchronisation multi-machines pour IPTV Hub.
Gère l'export, l'import et la fusion intelligente (Smart Merge) des données utilisateur
via Google Drive, OneDrive ou tout dossier partagé local / cloud.
"""

import os
import sys
import json
import string
import platform
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List, Union

from core.database import Database

logger = logging.getLogger(__name__)

# Clés de paramètres exclues de la synchronisation (propres au matériel / écran local)
EXCLUDED_SETTINGS_KEYS = {
    "window_x",
    "window_y",
    "window_width",
    "window_height",
    "window_maximized",
    "window_fullscreen",
    "outer_splitter_sizes",
    "inner_splitter_sizes",
    "category_panel_width",
    "channel_list_width",
    "epg_panel_height",
    "download_dir",
    "sync_folder",
    "sync_last_timestamp",
}

SYNC_FILE_NAME = "iptv_sync.json"


def detect_default_sync_folder() -> Optional[Path]:
    """
    Détecte automatiquement le dossier 'IPTV Hub' dans Google Drive, OneDrive ou le profil utilisateur.
    Scrute dynamiquement l'ensemble des disques montés sous Windows pour ne pas supposer une lettre fixe.
    """
    candidates: List[Path] = []

    # 1. Vérification de tous les disques montés sous Windows (de C: à Z)
    if sys.platform == "win32" or platform.system() == "Windows":
        for letter in string.ascii_uppercase:
            drive_root = Path(f"{letter}:\\")
            if drive_root.exists():
                candidates.extend([
                    drive_root / "Mon Drive" / "IPTV Hub",
                    drive_root / "Mon Drive" / "IPTV_Hub",
                    drive_root / "My Drive" / "IPTV Hub",
                    drive_root / "My Drive" / "IPTV_Hub",
                    drive_root / "Google Drive" / "IPTV Hub",
                    drive_root / "Google Drive" / "IPTV_Hub",
                    drive_root / "IPTV Hub",
                    drive_root / "IPTV_Hub",
                ])

    # 2. Dossiers utilisateur standard
    user_home = Path.home()
    candidates.extend([
        user_home / "Google Drive" / "IPTV Hub",
        user_home / "Google Drive" / "IPTV_Hub",
        user_home / "Mon Drive" / "IPTV Hub",
        user_home / "OneDrive" / "IPTV Hub",
        user_home / "OneDrive" / "IPTV_Hub",
    ])

    for p in candidates:
        try:
            if p.exists() and p.is_dir():
                return p
        except Exception:
            continue

    return None


def get_sync_file_path(sync_folder: Union[str, Path]) -> Optional[Path]:
    """Retourne le chemin complet du fichier iptv_sync.json dans le dossier spécifié."""
    if not sync_folder:
        return None
    p = Path(sync_folder)
    return p / SYNC_FILE_NAME


def export_sync_data(db: Database) -> Dict[str, Any]:
    """
    Extrait l'ensemble des données utilisateur à haute valeur ajoutée depuis la base SQLite.
    Garantit un format JSON compact (< 100 Ko) sans aucune donnée brute jetable (channels, epg).
    """
    sync_payload: Dict[str, Any] = {
        "metadata": {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "device_name": platform.node(),
            "source_machine": platform.node(),
            "platform": platform.system(),
        },
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "source_machine": platform.node(),
        "playlists": [],
        "playback_progress": [],
        "watch_history": [],
        "persistent_favorites": [],
        "persistent_disabled_channels": [],
        "persistent_disabled_groups": [],
        "category_sort_preferences": [],
        "settings": {},
    }

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # 1. Playlists
        cursor.execute("""
            SELECT id, name, url_or_path, playlist_type, server_url, username, password, epg_url
            FROM playlists
        """)
        playlist_map = {}
        for r in cursor.fetchall():
            p_id = r["id"]
            p_dict = {
                "name": r["name"],
                "url_or_path": r["url_or_path"],
                "playlist_type": r["playlist_type"],
                "server_url": r["server_url"],
                "username": r["username"],
                "password": r["password"],
                "epg_url": r["epg_url"],
            }
            sync_payload["playlists"].append(p_dict)
            playlist_map[p_id] = r["name"]

        # 2. Progression de lecture (films & épisodes)
        cursor.execute("""
            SELECT channel_id, stream_url, channel_name, playback_position, duration, updated_at
            FROM playback_progress
        """)
        for r in cursor.fetchall():
            sync_payload["playback_progress"].append({
                "stream_url": r["stream_url"],
                "channel_name": r["channel_name"],
                "playback_position": float(r["playback_position"] or 0.0),
                "duration": float(r["duration"] or 0.0),
                "updated_at": str(r["updated_at"] or ""),
            })

        # 3. Historique de visionnage
        cursor.execute("""
            SELECT channel_name, stream_url, logo_url, group_title, watched_at, playback_position, duration
            FROM watch_history
            ORDER BY watched_at DESC
            LIMIT 200
        """)
        for r in cursor.fetchall():
            sync_payload["watch_history"].append({
                "channel_name": r["channel_name"],
                "stream_url": r["stream_url"],
                "logo_url": r["logo_url"],
                "group_title": r["group_title"],
                "watched_at": str(r["watched_at"] or ""),
                "playback_position": float(r["playback_position"] or 0.0),
                "duration": float(r["duration"] or 0.0),
            })

        # 4. Favoris persistants
        cursor.execute("""
            SELECT name, stream_url, stream_id, stream_type, logo_url, group_title, favorite_added_at
            FROM persistent_favorites
        """)
        for r in cursor.fetchall():
            sync_payload["persistent_favorites"].append({
                "name": r["name"],
                "stream_url": r["stream_url"],
                "stream_id": r["stream_id"],
                "stream_type": r["stream_type"],
                "logo_url": r["logo_url"],
                "group_title": r["group_title"],
                "favorite_added_at": str(r["favorite_added_at"] or ""),
            })

        # 5. Chaînes désactivées / masquées
        cursor.execute("""
            SELECT name, group_title, stream_url, stream_id, stream_type, playlist_id
            FROM persistent_disabled_channels
        """)
        for r in cursor.fetchall():
            sync_payload["persistent_disabled_channels"].append({
                "name": r["name"],
                "group_title": r["group_title"],
                "stream_url": r["stream_url"],
                "stream_id": r["stream_id"],
                "stream_type": r["stream_type"],
                "playlist_name": playlist_map.get(r["playlist_id"], ""),
            })

        # 6. Groupes / Catégories désactivés
        cursor.execute("""
            SELECT group_title, stream_type, playlist_id
            FROM persistent_disabled_groups
        """)
        for r in cursor.fetchall():
            sync_payload["persistent_disabled_groups"].append({
                "group_title": r["group_title"],
                "stream_type": r["stream_type"],
                "playlist_name": playlist_map.get(r["playlist_id"], ""),
            })

        # 7. Préférences de tri des catégories
        cursor.execute("""
            SELECT playlist_id, stream_type, category_name, sort_order
            FROM category_sort_preferences
        """)
        for r in cursor.fetchall():
            sync_payload["category_sort_preferences"].append({
                "playlist_name": playlist_map.get(r["playlist_id"], ""),
                "stream_type": r["stream_type"],
                "category_name": r["category_name"],
                "sort_order": r["sort_order"],
            })

        # 8. Paramètres de configuration (filtrés)
        cursor.execute("SELECT key, value FROM settings")
        for r in cursor.fetchall():
            k = r["key"]
            if k not in EXCLUDED_SETTINGS_KEYS:
                sync_payload["settings"][k] = r["value"]

    return sync_payload


def merge_sync_data(db: Database, remote_data: Dict[str, Any]) -> Dict[str, int]:
    """
    Fusionne intelligemment (Smart Merge) les données distantes dans la base locale SQLite.
    Préserve toujours les données les plus récentes par horodatage.
    """
    raw_playlists = remote_data.get("playlists", [])
    raw_progress = remote_data.get("playback_progress", [])
    raw_favorites = remote_data.get("persistent_favorites", [])
    raw_disabled_groups = remote_data.get("persistent_disabled_groups", [])
    raw_disabled_channels = remote_data.get("persistent_disabled_channels", [])
    raw_settings = [k for k in remote_data.get("settings", {}).keys() if k not in EXCLUDED_SETTINGS_KEYS]

    stats = {
        "playlists": len(raw_playlists),
        "progress": len(raw_progress),
        "favorites": len(raw_favorites),
        "disabled_channels": len(raw_disabled_channels),
        "disabled_groups": len(raw_disabled_groups),
        "settings": len(raw_settings),

        "progress_updated": 0,
        "favorites_added": 0,
        "disabled_groups_added": 0,
        "disabled_channels_added": 0,
        "playlists_synced": 0,
    }

    if not isinstance(remote_data, dict):
        return stats

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Construction du mapping local playlist_name -> playlist_id
        cursor.execute("SELECT id, name, server_url, username, url_or_path FROM playlists")
        local_playlists = cursor.fetchall()
        local_p_by_name = {p["name"]: p["id"] for p in local_playlists}

        # 1. Synchronisation des Playlists
        for p in raw_playlists:
            name = p.get("name")
            server_url = p.get("server_url") or ""
            username = p.get("username") or ""
            url_or_path = p.get("url_or_path") or ""

            # Trouver si la playlist existe déjà localement
            matched_id = None
            for lp in local_playlists:
                if (server_url and username and lp["server_url"] == server_url and lp["username"] == username) or (url_or_path and lp["url_or_path"] == url_or_path) or (lp["name"] == name):
                    matched_id = lp["id"]
                    break

            if matched_id is None and name:
                cursor.execute("""
                    INSERT INTO playlists (
                        name, url_or_path, playlist_type, server_url, username, password,
                        epg_url, created_at, updated_at, channel_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    name, url_or_path, p.get("playlist_type", "xtream"),
                    server_url, username, p.get("password", ""),
                    p.get("epg_url", ""),
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
                matched_id = cursor.lastrowid
                if matched_id:
                    local_p_by_name[name] = matched_id
                    stats["playlists_synced"] += 1
            elif matched_id is not None:
                # Mise à jour des identifiants au besoin
                cursor.execute("""
                    UPDATE playlists SET password = COALESCE(NULLIF(?, ''), password),
                                         epg_url = COALESCE(NULLIF(?, ''), epg_url)
                    WHERE id = ?
                """, (p.get("password", ""), p.get("epg_url", ""), matched_id))
                stats["playlists_synced"] += 1

        # Recharger le mapping complet des playlists
        cursor.execute("SELECT id, name FROM playlists")
        active_p_by_name = {p["name"]: p["id"] for p in cursor.fetchall()}
        default_playlist_id = list(active_p_by_name.values())[0] if active_p_by_name else 1

        # 2. Smart Merge Progression de lecture (playback_progress)
        # On compare l'horodatage updated_at : le plus récent l'emporte
        for pr in remote_data.get("playback_progress", []):
            s_url = pr.get("stream_url")
            if not s_url:
                continue

            r_updated = pr.get("updated_at", "")
            r_pos = float(pr.get("playback_position", 0.0))
            r_dur = float(pr.get("duration", 0.0))
            r_name = pr.get("channel_name", "")

            cursor.execute("SELECT playback_position, duration, updated_at FROM playback_progress WHERE stream_url = ?", (s_url,))
            local_row = cursor.fetchone()

            should_update = False
            if local_row is None:
                should_update = True
            else:
                loc_updated = str(local_row["updated_at"] or "")
                if r_updated > loc_updated:
                    should_update = True

            if should_update:
                cursor.execute("""
                    INSERT OR REPLACE INTO playback_progress (stream_url, channel_name, playback_position, duration, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (s_url, r_name, r_pos, r_dur, r_updated or datetime.now().isoformat()))
                stats["progress_updated"] += 1

        # 3. Smart Merge Historique (watch_history)
        for wh in remote_data.get("watch_history", []):
            s_url = wh.get("stream_url")
            if not s_url:
                continue
            w_at = wh.get("watched_at", "")
            cursor.execute("SELECT id, watched_at FROM watch_history WHERE stream_url = ?", (s_url,))
            loc_wh = cursor.fetchone()
            if loc_wh is None:
                cursor.execute("""
                    INSERT INTO watch_history (channel_name, stream_url, logo_url, group_title, watched_at, playback_position, duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    wh.get("channel_name", ""), s_url, wh.get("logo_url", ""),
                    wh.get("group_title", ""), w_at or datetime.now().isoformat(),
                    float(wh.get("playback_position", 0.0)), float(wh.get("duration", 0.0))
                ))
            elif w_at > str(loc_wh["watched_at"] or ""):
                cursor.execute("""
                    UPDATE watch_history SET watched_at = ?, playback_position = ?, duration = ?
                    WHERE id = ?
                """, (w_at, float(wh.get("playback_position", 0.0)), float(wh.get("duration", 0.0)), loc_wh["id"]))

        # 4. Favoris persistants (Union)
        for fav in remote_data.get("persistent_favorites", []):
            name = fav.get("name")
            st_type = fav.get("stream_type", "live")
            if not name:
                continue
            cursor.execute("""
                INSERT OR IGNORE INTO persistent_favorites (name, stream_url, stream_id, stream_type, logo_url, group_title, favorite_added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                name, fav.get("stream_url"), fav.get("stream_id"),
                st_type, fav.get("logo_url"), fav.get("group_title"),
                fav.get("favorite_added_at") or datetime.now().isoformat()
            ))
            if cursor.rowcount > 0:
                stats["favorites_added"] += 1
                # Mettre à jour également is_favorite dans la table channels si la chaîne existe
                cursor.execute("""
                    UPDATE channels SET is_favorite = 1, favorite_added_at = ?
                    WHERE name = ? AND stream_type = ? AND is_favorite = 0
                """, (fav.get("favorite_added_at") or datetime.now().isoformat(), name, st_type))

        # 5. Groupes désactivés (Union)
        for grp in remote_data.get("persistent_disabled_groups", []):
            g_title = grp.get("group_title")
            s_type = grp.get("stream_type", "live")
            p_name = grp.get("playlist_name", "")
            p_id = active_p_by_name.get(p_name, default_playlist_id)
            if not g_title:
                continue

            cursor.execute("""
                INSERT OR IGNORE INTO persistent_disabled_groups (group_title, stream_type, playlist_id)
                VALUES (?, ?, ?)
            """, (g_title, s_type, p_id))
            if cursor.rowcount > 0:
                stats["disabled_groups_added"] += 1
                cursor.execute("""
                    UPDATE channels SET is_enabled = 0
                    WHERE group_title = ? AND stream_type = ? AND playlist_id = ?
                """, (g_title, s_type, p_id))

        # 6. Chaînes désactivées (Union)
        for ch in remote_data.get("persistent_disabled_channels", []):
            name = ch.get("name")
            s_type = ch.get("stream_type", "live")
            p_name = ch.get("playlist_name", "")
            p_id = active_p_by_name.get(p_name, default_playlist_id)
            if not name:
                continue

            cursor.execute("""
                INSERT OR IGNORE INTO persistent_disabled_channels (name, group_title, stream_url, stream_id, stream_type, playlist_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name, ch.get("group_title"), ch.get("stream_url"),
                ch.get("stream_id"), s_type, p_id
            ))
            if cursor.rowcount > 0:
                stats["disabled_channels_added"] += 1
                cursor.execute("""
                    UPDATE channels SET is_enabled = 0
                    WHERE name = ? AND stream_type = ? AND playlist_id = ?
                """, (name, s_type, p_id))

        # 7. Tri des catégories
        for pref in remote_data.get("category_sort_preferences", []):
            c_name = pref.get("category_name")
            s_type = pref.get("stream_type", "vod")
            order = pref.get("sort_order", "alphabetical")
            p_name = pref.get("playlist_name", "")
            p_id = active_p_by_name.get(p_name, default_playlist_id)
            if c_name:
                cursor.execute("""
                    INSERT OR REPLACE INTO category_sort_preferences (playlist_id, stream_type, category_name, sort_order)
                    VALUES (?, ?, ?, ?)
                """, (p_id, s_type, c_name, order))

        # 8. Paramètres généraux (filtrés)
        for k, v in remote_data.get("settings", {}).items():
            if k not in EXCLUDED_SETTINGS_KEYS:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))

        conn.commit()

    return stats


def read_sync_file(sync_file: Union[str, Path]) -> Dict[str, Any]:
    """Lit et décode le fichier iptv_sync.json."""
    try:
        p = Path(sync_file)
        if not p.exists() or not p.is_file():
            return {}
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Impossible de lire le fichier de synchronisation %s: %s", sync_file, e)
        return {}


def sync_push_to_file(db: Database, sync_file: Union[str, Path]) -> Tuple[bool, str]:
    """
    Sauvegarde l'état local dans le fichier distant avec fusion préalable sécurisée.
    Écriture atomique pour éviter toute corruption de fichier en cas d'interruption.
    """
    try:
        p_sync_file = Path(sync_file)
        sync_folder = p_sync_file.parent
        sync_folder.mkdir(parents=True, exist_ok=True)

        # 1. Si un fichier distant existe déjà, fusionner ses données en premier pour ne rien écraser
        if p_sync_file.exists():
            try:
                with open(p_sync_file, "r", encoding="utf-8") as f:
                    remote_data = json.load(f)
                merge_sync_data(db, remote_data)
            except Exception as e:
                logger.warning("Fichier de synchro distant non lisible pour pré-fusion: %s", e)

        # 2. Exporter l'état local complet
        payload = export_sync_data(db)

        # 3. Écriture atomique via fichier temporaire dans le même dossier
        temp_file = sync_folder / f".tmp_{os.getpid()}_{SYNC_FILE_NAME}"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # Remplacement atomique
        temp_file.replace(p_sync_file)

        return True, "Synchronisation vers le Cloud réussie !"

    except Exception as e:
        logger.error("Erreur lors de la synchronisation vers le fichier: %s", e)
        return False, f"Erreur lors de l'envoi : {e}"


def sync_pull_from_file(db: Database, sync_file: Union[str, Path]) -> Tuple[bool, str, Dict[str, int]]:
    """
    Charge et fusionne les données distantes depuis le fichier de synchronisation.
    """
    p_sync_file = Path(sync_file)
    if not p_sync_file.exists():
        return False, "Le fichier de synchronisation n'existe pas encore dans ce dossier.", {}

    try:
        with open(p_sync_file, "r", encoding="utf-8") as f:
            remote_data = json.load(f)

        stats = merge_sync_data(db, remote_data)
        device = remote_data.get("metadata", {}).get("device_name", "autre machine")
        msg = f"Synchronisation réussie depuis '{device}' !"
        return True, msg, stats

    except Exception as e:
        logger.error("Erreur lors de la lecture du fichier de synchronisation: %s", e)
        return False, f"Erreur de lecture : {e}", {}


def export_config_to_file(db: Database, file_path: Union[str, Path]) -> Tuple[bool, str]:
    """
    Exporte la configuration et les données utilisateur vers un fichier JSON choisi.
    Idéal pour sauvegarder, transférer sur clé USB ou synchroniser avec Android TV / autres appareils.
    """
    try:
        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = export_sync_data(db)

        temp_target = target_path.parent / f".tmp_{os.getpid()}_{target_path.name}"
        with open(temp_target, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        temp_target.replace(target_path)

        return True, f"Configuration enregistrée avec succès dans :\n{target_path}"
    except Exception as e:
        logger.error("Erreur lors de l'export de configuration: %s", e)
        return False, f"Erreur lors de l'enregistrement de la configuration :\n{e}"


def import_config_from_file(db: Database, file_path: Union[str, Path]) -> Tuple[bool, str, Dict[str, int]]:
    """
    Importe et fusionne une configuration utilisateur depuis un fichier JSON.
    Applique la fusion intelligente (reprises les plus récentes, cumul des favoris et des masquages).
    """
    src_path = Path(file_path)
    if not src_path.exists() or not src_path.is_file():
        return False, "Le fichier de configuration sélectionné est introuvable.", {}

    try:
        with open(src_path, "r", encoding="utf-8") as f:
            remote_data = json.load(f)

        stats = merge_sync_data(db, remote_data)
        device = remote_data.get("metadata", {}).get("device_name") or remote_data.get("source_machine", "appareil externe")
        return True, f"Configuration importée et fusionnée avec succès (depuis {device}) !", stats
    except Exception as e:
        logger.error("Erreur lors de l'import de configuration: %s", e)
        return False, f"Erreur lors du chargement de la configuration :\n{e}", {}

