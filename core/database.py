"""
Module de gestion de la base de données SQLite pour l'application IPTV.
Stocke les playlists, chaînes, favoris, historique, cache EPG et état d'activation des catégories/chaînes.
"""

import sqlite3
import json
import dataclasses
from pathlib import Path
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Tuple, Generator, Set
from datetime import datetime
from core.models import Playlist, Channel, EPGProgram, WatchHistory, AppSettings

import os
import sys
import re


def _instantiate_dataclass(cls, d: dict):
    """Instancie une dataclass en ignorant automatiquement les champs inconnus (sécurité d'évolution du schéma)."""
    known_fields = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in known_fields})


def get_data_dir() -> Path:
    """
    Retourne le dossier persistant pour les données de l'application.
    - Windows : %APPDATA%/IPTV_Hub
    - Linux / macOS : $XDG_DATA_HOME/IPTV_Hub ou ~/.local/share/IPTV_Hub (avec fallback ~/.iptv_hub)
    """
    appdata = os.environ.get("APPDATA")
    if appdata and (sys.platform == "win32" or "APPDATA" in os.environ):
        base_dir = Path(appdata) / "IPTV_Hub"
    else:
        # Si un ancien dossier ~/.iptv_hub existe déjà, le conserver pour la compatibilité
        legacy_dir = Path.home() / ".iptv_hub"
        if legacy_dir.exists() and (legacy_dir / "iptv.db").exists():
            base_dir = legacy_dir
        else:
            xdg_data = os.environ.get("XDG_DATA_HOME")
            if xdg_data:
                base_dir = Path(xdg_data) / "IPTV_Hub"
            else:
                base_dir = Path.home() / ".local" / "share" / "IPTV_Hub"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_cache_dir() -> Path:
    """
    Retourne le dossier de cache pour les pochettes et images.
    - Windows : %APPDATA%/IPTV_Hub/cache
    - Linux / macOS : $XDG_CACHE_HOME/IPTV_Hub ou ~/.cache/IPTV_Hub
    """
    if sys.platform == "win32":
        cache_dir = get_data_dir() / "cache"
    else:
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            cache_dir = Path(xdg_cache) / "IPTV_Hub"
        else:
            cache_dir = Path.home() / ".cache" / "IPTV_Hub"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(get_data_dir() / "iptv.db")
        self.db_path = db_path
        self._init_db()
        self.deduplicate_watch_history()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Table des playlists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url_or_path TEXT NOT NULL,
                    playlist_type TEXT DEFAULT 'm3u',
                    server_url TEXT,
                    username TEXT,
                    password TEXT,
                    epg_url TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    channel_count INTEGER DEFAULT 0
                )
            """)

            # Table des chaînes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    stream_url TEXT NOT NULL,
                    logo_url TEXT,
                    group_title TEXT DEFAULT 'Général',
                    tvg_id TEXT,
                    tvg_name TEXT,
                    user_agent TEXT,
                    http_referrer TEXT,
                    is_favorite INTEGER DEFAULT 0,
                    is_enabled INTEGER DEFAULT 1,
                    stream_type TEXT DEFAULT 'live',
                    stream_id TEXT,
                    container_extension TEXT,
                    rating TEXT,
                    year TEXT,
                    extra_headers TEXT,
                    favorite_added_at TEXT,
                    added_at TEXT,
                    FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
                )
            """)

            # Migration douce si colonnes absentes dans channels
            for col_def in (
                "is_enabled INTEGER DEFAULT 1",
                "favorite_added_at TEXT",
                "added_at TEXT",
                "tv_archive INTEGER DEFAULT 0",
                "tv_archive_duration INTEGER DEFAULT 0"
            ):
                try:
                    cursor.execute(f"ALTER TABLE channels ADD COLUMN {col_def};")
                except Exception:
                    pass

            # Migration douce si colonnes absentes dans playlists
            for col_def in (
                "account_status TEXT",
                "exp_date TEXT",
                "max_connections TEXT",
                "active_cons TEXT"
            ):
                try:
                    cursor.execute(f"ALTER TABLE playlists ADD COLUMN {col_def};")
                except Exception:
                    pass

            # Index pour requêtes ultra-rapides
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_playlist ON channels(playlist_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_group ON channels(playlist_id, group_title);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_favorite ON channels(playlist_id, is_favorite);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_fav_date ON channels(favorite_added_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_added_at ON channels(playlist_id, stream_type, added_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_enabled ON channels(playlist_id, is_enabled);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_archive ON channels(playlist_id, stream_type, tv_archive);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_tvg ON channels(tvg_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_stream ON channels(stream_url);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_stream_id ON channels(playlist_id, stream_type, stream_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_series_name ON channels(stream_type, name COLLATE NOCASE);")
            # Table persistante des favoris (garantit la conservation éternelle même lors du rechargement des playlists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persistent_favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    stream_url TEXT,
                    stream_id TEXT,
                    stream_type TEXT DEFAULT 'live',
                    logo_url TEXT,
                    group_title TEXT,
                    favorite_added_at TEXT,
                    UNIQUE(name, stream_type)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pers_fav_stream ON persistent_favorites(stream_type, stream_url);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pers_fav_name ON persistent_favorites(name, stream_type);")

            # Table persistante des chaînes désactivées (garantit la conservation des filtres même lors du rechargement des playlists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persistent_disabled_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    group_title TEXT,
                    stream_url TEXT,
                    stream_id TEXT,
                    stream_type TEXT DEFAULT 'live',
                    playlist_id INTEGER,
                    UNIQUE(name, stream_type, playlist_id)
                )
            """)
            try:
                cursor.execute("ALTER TABLE persistent_disabled_channels ADD COLUMN group_title TEXT;")
            except Exception:
                pass
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pers_dis_stream ON persistent_disabled_channels(stream_type, stream_url);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pers_dis_name ON persistent_disabled_channels(name, stream_type, playlist_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pers_dis_name_grp ON persistent_disabled_channels(name, group_title, stream_type, playlist_id);")

            # Table persistante des catégories désactivées (garantit que tout nouvel ajout dans un groupe désactivé reste masqué)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persistent_disabled_groups (
                    group_title TEXT NOT NULL,
                    stream_type TEXT NOT NULL,
                    playlist_id INTEGER NOT NULL,
                    PRIMARY KEY (group_title, stream_type, playlist_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pers_dis_grp ON persistent_disabled_groups(playlist_id, stream_type, group_title);")

            # Migration de sécurité : renseigner group_title dans persistent_disabled_channels si manquant
            cursor.execute("""
                UPDATE persistent_disabled_channels
                SET group_title = (
                    SELECT ch.group_title FROM channels ch
                    WHERE ch.playlist_id = persistent_disabled_channels.playlist_id
                      AND ch.stream_type = persistent_disabled_channels.stream_type
                      AND (
                          (ch.stream_id IS NOT NULL AND ch.stream_id != '' AND ch.stream_id = persistent_disabled_channels.stream_id)
                          OR (ch.stream_url IS NOT NULL AND ch.stream_url != '' AND ch.stream_url = persistent_disabled_channels.stream_url)
                          OR (ch.name = persistent_disabled_channels.name)
                      )
                    LIMIT 1
                )
                WHERE group_title IS NULL;
            """)

            # Réconciliation au démarrage : garantir que toutes les chaînes enregistrées dans persistent_disabled_channels
            # ou dont la catégorie est désactivée restent bien masquées (is_enabled = 0)
            cursor.execute("""
                UPDATE channels SET is_enabled = 0
                WHERE is_enabled = 1
                  AND (
                      (stream_id IS NOT NULL AND stream_id != '' AND (playlist_id, stream_type, stream_id) IN (
                          SELECT playlist_id, stream_type, stream_id FROM persistent_disabled_channels
                          WHERE stream_id IS NOT NULL AND stream_id != ''
                      ))
                      OR (stream_url IS NOT NULL AND stream_url != '' AND (playlist_id, stream_type, stream_url) IN (
                          SELECT playlist_id, stream_type, stream_url FROM persistent_disabled_channels
                          WHERE stream_url IS NOT NULL AND stream_url != ''
                      ))
                      OR ((playlist_id, stream_type, name, group_title) IN (
                          SELECT playlist_id, stream_type, name, group_title FROM persistent_disabled_channels
                          WHERE group_title IS NOT NULL
                      ))
                      OR (group_title IN (
                          SELECT group_title FROM persistent_disabled_groups
                          WHERE stream_type = channels.stream_type AND playlist_id = channels.playlist_id
                      ))
                  );
            """)

            # Migration unique : nettoyage des anciens emojis codés en dur dans la base de données
            cursor.execute("PRAGMA user_version;")
            ver_row = cursor.fetchone()
            current_ver = ver_row[0] if ver_row else 0
            if current_ver < 2:
                cursor.execute("UPDATE OR IGNORE channels SET group_title = TRIM(SUBSTR(group_title, 3)) WHERE group_title LIKE '🎬 %' OR group_title LIKE '🍿 %';")
                cursor.execute("UPDATE OR IGNORE persistent_favorites SET group_title = TRIM(SUBSTR(group_title, 3)) WHERE group_title LIKE '🎬 %' OR group_title LIKE '🍿 %';")
                cursor.execute("UPDATE OR IGNORE persistent_disabled_groups SET group_title = TRIM(SUBSTR(group_title, 3)) WHERE group_title LIKE '🎬 %' OR group_title LIKE '🍿 %';")
                cursor.execute("UPDATE OR IGNORE persistent_disabled_channels SET group_title = TRIM(SUBSTR(group_title, 3)) WHERE group_title LIKE '🎬 %' OR group_title LIKE '🍿 %';")
                cursor.execute("PRAGMA user_version = 2;")

            # Table du guide des programmes (EPG)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS epg_programs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tvg_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    category TEXT,
                    icon_url TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_epg_tvg_time ON epg_programs(tvg_id, start_time, end_time);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_epg_times ON epg_programs(start_time, end_time);")

            # Table de l'historique
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watch_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    channel_name TEXT NOT NULL,
                    stream_url TEXT NOT NULL,
                    logo_url TEXT,
                    group_title TEXT,
                    watched_at TEXT NOT NULL,
                    playback_position REAL DEFAULT 0.0,
                    duration REAL DEFAULT 0.0
                )
            """)

            # Table de reprise de lecture (films et épisodes de séries)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playback_progress (
                    channel_id INTEGER,
                    stream_url TEXT NOT NULL PRIMARY KEY,
                    channel_name TEXT,
                    playback_position REAL DEFAULT 0.0,
                    duration REAL DEFAULT 0.0,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_playback_progress_chid ON playback_progress(channel_id);")

            # Table des paramètres
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Table de mémorisation du tri par catégorie (Films & Séries)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS category_sort_preferences (
                    playlist_id INTEGER NOT NULL,
                    stream_type TEXT NOT NULL,
                    category_name TEXT NOT NULL,
                    sort_order TEXT NOT NULL,
                    PRIMARY KEY (playlist_id, stream_type, category_name)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cat_sort_pref ON category_sort_preferences(playlist_id, stream_type, category_name);")

            # Table de cache persistant des séries (saisons, épisodes et métadonnées complètes)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS series_cache (
                    playlist_id INTEGER NOT NULL,
                    series_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (playlist_id, series_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_cache_lookup ON series_cache(playlist_id, series_id);")
            conn.commit()

    # ------------------ PLAYLISTS ------------------

    def add_playlist(self, p: Playlist) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO playlists (
                    name, url_or_path, playlist_type, server_url, username, password,
                    epg_url, created_at, updated_at, channel_count,
                    account_status, exp_date, max_connections, active_cons
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p.name, p.url_or_path, p.playlist_type, p.server_url, p.username, p.password,
                p.epg_url, p.created_at, p.updated_at, p.channel_count,
                p.account_status, p.exp_date, p.max_connections, p.active_cons
            ))
            conn.commit()
            return cursor.lastrowid or 0

    def get_playlists(self) -> List[Playlist]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM playlists ORDER BY id ASC")
            rows = cursor.fetchall()
            return [_instantiate_dataclass(Playlist, dict(r)) for r in rows]

    def get_playlist_by_id(self, playlist_id: int) -> Optional[Playlist]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
            row = cursor.fetchone()
            return _instantiate_dataclass(Playlist, dict(row)) if row else None

    def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        return self.get_playlist_by_id(playlist_id)

    def update_playlist(self, p: Playlist):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE playlists
                SET name=?, url_or_path=?, playlist_type=?, server_url=?, username=?, password=?, epg_url=?,
                    updated_at=?, channel_count=?, account_status=?, exp_date=?, max_connections=?, active_cons=?
                WHERE id=?
            """, (
                p.name, p.url_or_path, p.playlist_type, p.server_url, p.username, p.password, p.epg_url,
                p.updated_at, p.channel_count, p.account_status, p.exp_date, p.max_connections, p.active_cons, p.id
            ))
            conn.commit()

    def update_playlist_account_info(
        self,
        playlist_id: int,
        account_status: Optional[str] = None,
        exp_date: Optional[str] = None,
        max_connections: Optional[str] = None,
        active_cons: Optional[str] = None
    ):
        """Met à jour les métadonnées de compte d'une playlist Xtream."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE playlists
                SET account_status = COALESCE(?, account_status),
                    exp_date = COALESCE(?, exp_date),
                    max_connections = COALESCE(?, max_connections),
                    active_cons = COALESCE(?, active_cons)
                WHERE id = ?
            """, (account_status, exp_date, max_connections, active_cons, playlist_id))
            conn.commit()

    def get_playlist_stream_counts(self, playlist_id: int) -> dict:
        """Retourne les décomptes par stream_type (live, movie, series) en une seule requête SQL optimisée."""
        counts = {"live": 0, "movie": 0, "series": 0}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT stream_type, COUNT(*) as count 
                FROM channels 
                WHERE playlist_id = ? 
                GROUP BY stream_type
            """, (playlist_id,))
            for row in cursor.fetchall():
                st = (row["stream_type"] or "live").lower()
                if st in ("vod", "movie"):
                    counts["movie"] += row["count"]
                elif st in ("series",):
                    counts["series"] += row["count"]
                else:
                    counts["live"] += row["count"]
        return counts

    def delete_playlist(self, playlist_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM channels WHERE playlist_id=?", (playlist_id,))
            cursor.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
            conn.commit()

    # ------------------ CHANNELS ------------------

    def save_channels_batch(self, playlist_id: int, channels: List[Channel], replace: bool = True):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Préserver favoris et filtres de chaînes désactivées avant suppression
            if replace:
                cursor.execute(
                    "SELECT name, stream_url, stream_id, stream_type, logo_url, group_title, favorite_added_at FROM channels WHERE playlist_id=? AND is_favorite=1",
                    (playlist_id,)
                )
                for r in cursor.fetchall():
                    cursor.execute("""
                        INSERT INTO persistent_favorites (name, stream_url, stream_id, stream_type, logo_url, group_title, favorite_added_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name, stream_type) DO UPDATE SET
                            stream_url=excluded.stream_url,
                            stream_id=excluded.stream_id,
                            logo_url=excluded.logo_url,
                            favorite_added_at=excluded.favorite_added_at
                    """, (r["name"], r["stream_url"], r["stream_id"], r["stream_type"], r["logo_url"], r["group_title"], r["favorite_added_at"] or datetime.now().isoformat()))

                cursor.execute("""
                    SELECT c.name, c.group_title, c.stream_url, c.stream_id, c.stream_type, c.playlist_id 
                    FROM channels c 
                    WHERE c.playlist_id=? AND c.is_enabled=0
                      AND c.group_title NOT IN (
                          SELECT group_title FROM persistent_disabled_groups 
                          WHERE stream_type = c.stream_type AND playlist_id = c.playlist_id
                      )
                """, (playlist_id,))
                for r in cursor.fetchall():
                    cursor.execute("""
                        INSERT INTO persistent_disabled_channels (name, group_title, stream_url, stream_id, stream_type, playlist_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name, stream_type, playlist_id) DO UPDATE SET
                            group_title=excluded.group_title,
                            stream_url=excluded.stream_url,
                            stream_id=excluded.stream_id
                    """, (r["name"], r["group_title"], r["stream_url"], r["stream_id"], r["stream_type"], r["playlist_id"]))

                # 1.ter Charger les dates d'ajout existantes pour ne pas les perdre si non fournies
                cursor.execute(
                    "SELECT stream_url, stream_id, stream_type, name, added_at FROM channels WHERE playlist_id=? AND added_at IS NOT NULL AND added_at != ''",
                    (playlist_id,)
                )
                existing_added = {}
                for r in cursor.fetchall():
                    if r["stream_id"]:
                        existing_added[(str(r["stream_id"]), r["stream_type"])] = r["added_at"]
                    if r["stream_url"]:
                        existing_added[r["stream_url"]] = r["added_at"]
                    if r["name"]:
                        existing_added[(r["name"], r["stream_type"])] = r["added_at"]

                cursor.execute("DELETE FROM channels WHERE playlist_id=?", (playlist_id,))
            else:
                existing_added = {}

            # 2. Charger l'index des favoris persistants pour réconciliation automatique
            cursor.execute("SELECT name, stream_url, stream_id, stream_type, favorite_added_at FROM persistent_favorites")
            pers_favs_by_url = {}
            pers_favs_by_id = {}
            pers_favs_by_name = {}
            for r in cursor.fetchall():
                f_date = r["favorite_added_at"] or datetime.now().isoformat()
                if r["stream_url"]:
                    pers_favs_by_url[r["stream_url"]] = f_date
                if r["stream_id"]:
                    pers_favs_by_id[(str(r["stream_id"]), r["stream_type"])] = f_date
                if r["name"]:
                    pers_favs_by_name[(r["name"], r["stream_type"])] = f_date

            # 2.bis Charger l'index des chaînes et des groupes désactivés pour réconciliation automatique
            cursor.execute("SELECT name, group_title, stream_url, stream_id, stream_type FROM persistent_disabled_channels WHERE playlist_id=?", (playlist_id,))
            pers_dis_by_url = set()
            pers_dis_by_id = set()
            pers_dis_by_name_grp = set()
            pers_dis_by_name = set()
            for r in cursor.fetchall():
                if r["stream_url"]:
                    pers_dis_by_url.add(r["stream_url"])
                if r["stream_id"]:
                    pers_dis_by_id.add((str(r["stream_id"]), r["stream_type"]))
                if r["name"] and r["group_title"]:
                    pers_dis_by_name_grp.add((r["name"], r["group_title"], r["stream_type"]))
                elif r["name"]:
                    pers_dis_by_name.add((r["name"], r["stream_type"]))

            cursor.execute("SELECT group_title, stream_type FROM persistent_disabled_groups WHERE playlist_id=?", (playlist_id,))
            pers_dis_groups = {(r["group_title"], r["stream_type"]) for r in cursor.fetchall()}

            params = []
            for c in channels:
                is_fav = bool(c.is_favorite)
                fav_date = None
                if not is_fav:
                    if c.stream_url and c.stream_url in pers_favs_by_url:
                        is_fav = True
                        fav_date = pers_favs_by_url[c.stream_url]
                    elif c.stream_id and (str(c.stream_id), c.stream_type) in pers_favs_by_id:
                        is_fav = True
                        fav_date = pers_favs_by_id[(str(c.stream_id), c.stream_type)]
                    elif (c.name, c.stream_type) in pers_favs_by_name:
                        is_fav = True
                        fav_date = pers_favs_by_name[(c.name, c.stream_type)]
                else:
                    fav_date = datetime.now().isoformat()

                # Vérifier si la chaîne doit rester désactivée selon les choix persistants de l'utilisateur
                # Priorité absolue au groupe désactivé : tout nouvel ajout dans un groupe désactivé est masqué d'office
                is_enabled = 1
                grp = c.group_title or "Général"
                st = c.stream_type or "live"
                if (grp, st) in pers_dis_groups:
                    is_enabled = 0
                elif c.stream_url and c.stream_url in pers_dis_by_url:
                    is_enabled = 0
                elif c.stream_id and (str(c.stream_id), c.stream_type) in pers_dis_by_id:
                    is_enabled = 0
                elif (c.name, grp, c.stream_type) in pers_dis_by_name_grp:
                    is_enabled = 0
                elif (c.name, c.stream_type) in pers_dis_by_name:
                    is_enabled = 0
                elif not c.is_enabled:
                    is_enabled = 0

                # Détermination de la date d'ajout réelle
                item_added_at = c.added_at
                if not item_added_at:
                    if c.stream_id and (str(c.stream_id), c.stream_type) in existing_added:
                        item_added_at = existing_added[(str(c.stream_id), c.stream_type)]
                    elif c.stream_url and c.stream_url in existing_added:
                        item_added_at = existing_added[c.stream_url]
                    elif (c.name, c.stream_type) in existing_added:
                        item_added_at = existing_added[(c.name, c.stream_type)]
                    else:
                        item_added_at = datetime.now().isoformat()

                params.append((
                    playlist_id,
                    c.name,
                    c.stream_url,
                    c.logo_url,
                    c.group_title or "Général",
                    c.tvg_id,
                    c.tvg_name,
                    c.user_agent,
                    c.http_referrer,
                    1 if is_fav else 0,
                    is_enabled,
                    c.stream_type or "live",
                    c.stream_id or "",
                    c.container_extension or "",
                    c.rating or "",
                    c.year or "",
                    json.dumps(c.extra_headers) if c.extra_headers else "{}",
                    fav_date,
                    item_added_at,
                    int(c.tv_archive or 0),
                    int(c.tv_archive_duration or 0)
                ))

            cursor.executemany("""
                INSERT INTO channels (
                    playlist_id, name, stream_url, logo_url, group_title,
                    tvg_id, tvg_name, user_agent, http_referrer, is_favorite, is_enabled,
                    stream_type, stream_id, container_extension, rating, year, extra_headers,
                    favorite_added_at, added_at, tv_archive, tv_archive_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, params)

            cursor.execute("UPDATE playlists SET channel_count = (SELECT COUNT(*) FROM channels WHERE playlist_id=?) WHERE id=?", (playlist_id, playlist_id))
            conn.commit()

    def get_channels(
        self,
        playlist_id: Optional[int] = None,
        group_title: Optional[str] = None,
        search_query: Optional[str] = None,
        favorites_only: bool = False,
        stream_type: Optional[str] = None,
        only_enabled: bool = True,
        order_by: str = "default",
        limit: int = 50000,
        offset: int = 0
    ) -> List[Channel]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []

            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)

            if group_title and group_title not in ("Tous les groupes", "Toutes les chaînes", "Tous les films"):
                conditions.append("group_title = ?")
                params.append(group_title)

            if favorites_only:
                conditions.append("is_favorite = 1")

            if only_enabled:
                conditions.append("is_enabled = 1")
                conditions.append("""
                    group_title NOT IN (
                        SELECT group_title FROM persistent_disabled_groups
                        WHERE (playlist_id = channels.playlist_id OR playlist_id IS NULL)
                          AND (stream_type = channels.stream_type OR stream_type IS NULL)
                    )
                """)

            if stream_type and stream_type != "all":
                conditions.append("stream_type = ?")
                params.append(stream_type)

            if search_query and search_query.strip():
                q = f"%{search_query.strip()}%"
                conditions.append("(name LIKE ? OR group_title LIKE ? OR tvg_name LIKE ?)")
                params.extend([q, q, q])

            if order_by == "favorite_date_desc":
                order_sql = "ORDER BY COALESCE(favorite_added_at, '') DESC, id DESC"
            elif order_by == "name_asc":
                order_sql = "ORDER BY name COLLATE NOCASE ASC"
            elif order_by == "name_desc":
                order_sql = "ORDER BY name COLLATE NOCASE DESC"
            elif order_by in ("date_desc", "recent"):
                order_sql = "ORDER BY CASE WHEN added_at IS NOT NULL AND added_at != '' THEN 0 ELSE 1 END, added_at DESC, id DESC"
            elif order_by == "date_asc":
                order_sql = "ORDER BY CASE WHEN added_at IS NOT NULL AND added_at != '' THEN 0 ELSE 1 END, added_at ASC, id ASC"
            elif order_by == "rating_desc":
                order_sql = "ORDER BY CAST(rating AS REAL) DESC, id DESC"
            elif order_by == "year_desc":
                order_sql = "ORDER BY CAST(year AS INTEGER) DESC, id DESC"
            else:
                order_sql = "ORDER BY id ASC"

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"SELECT * FROM channels{where_clause} {order_sql} LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            channels = []
            for r in rows:
                d = dict(r)
                d["is_favorite"] = bool(d.get("is_favorite", 0))
                d["is_enabled"] = bool(d.get("is_enabled", 1))
                extra = d.get("extra_headers")
                d["extra_headers"] = json.loads(extra) if extra else {}
                channels.append(_instantiate_dataclass(Channel, d))
            return channels

    def get_channel_count(
        self,
        playlist_id: Optional[int] = None,
        group_title: Optional[str] = None,
        search_query: Optional[str] = None,
        favorites_only: bool = False,
        stream_type: Optional[str] = None,
        only_enabled: bool = True
    ) -> int:
        """Retourne le nombre total d'éléments correspondant aux filtres pour la pagination."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []

            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)

            if group_title and group_title not in ("Tous les groupes", "Toutes les chaînes", "Tous les films"):
                conditions.append("group_title = ?")
                params.append(group_title)

            if favorites_only:
                conditions.append("is_favorite = 1")

            if only_enabled:
                conditions.append("is_enabled = 1")

            if stream_type:
                conditions.append("stream_type = ?")
                params.append(stream_type)

            if search_query and search_query.strip():
                q = f"%{search_query.strip()}%"
                conditions.append("(name LIKE ? OR group_title LIKE ? OR tvg_name LIKE ?)")
                params.extend([q, q, q])

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"SELECT COUNT(*) as count FROM channels{where_clause}"
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row["count"] if row else 0

    def get_archive_channels(
        self,
        playlist_id: Optional[int] = None,
        search_query: Optional[str] = None
    ) -> List[Channel]:
        """Retourne la liste des chaînes TV disposant du Replay/Catch-up (tv_archive = 1), actives et filtrées."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = [
                "stream_type = 'live'",
                "tv_archive = 1",
                "is_enabled = 1",
                """group_title NOT IN (
                    SELECT group_title FROM persistent_disabled_groups
                    WHERE (playlist_id = channels.playlist_id OR playlist_id IS NULL)
                      AND stream_type = 'live'
                )"""
            ]
            params: List[Any] = []
            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)
            if search_query and search_query.strip():
                conditions.append("(name LIKE ? OR group_title LIKE ?)")
                params.extend([f"%{search_query.strip()}%", f"%{search_query.strip()}%"])

            where_clause = " WHERE " + " AND ".join(conditions)
            query = f"SELECT * FROM channels{where_clause} ORDER BY id ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            channels = []
            for r in rows:
                d = dict(r)
                d["is_favorite"] = bool(d.get("is_favorite", 0))
                d["is_enabled"] = bool(d.get("is_enabled", 1))
                extra = d.get("extra_headers")
                d["extra_headers"] = json.loads(extra) if extra else {}
                channels.append(_instantiate_dataclass(Channel, d))
            return channels

    def get_watched_channel_ids(self) -> Set[int]:
        """Retourne l'ensemble des IDs de chaînes/films déjà visionnés dans l'historique."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT channel_id FROM watch_history WHERE channel_id > 0")
            return {r["channel_id"] for r in cursor.fetchall()}

    def get_recently_added_channels(
        self,
        playlist_id: Optional[int] = None,
        only_enabled: bool = True,
        limit: int = 150
    ) -> List[Channel]:
        """Retourne les éléments récemment ajoutés (TV, Films et Séries) triés par ID décroissant."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []

            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)

            if only_enabled:
                conditions.append("is_enabled = 1")
                conditions.append("""
                    group_title NOT IN (
                        SELECT group_title FROM persistent_disabled_groups
                        WHERE (playlist_id = channels.playlist_id OR playlist_id IS NULL)
                          AND (stream_type = channels.stream_type OR stream_type IS NULL)
                    )
                """)

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"""
                SELECT * FROM channels{where_clause}
                ORDER BY
                    CASE WHEN added_at IS NOT NULL AND added_at != '' THEN 0 ELSE 1 END,
                    added_at DESC,
                    id DESC
                LIMIT ?
            """
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            channels = []
            for r in rows:
                d = dict(r)
                d["is_favorite"] = bool(d.get("is_favorite", 0))
                d["is_enabled"] = bool(d.get("is_enabled", 1))
                extra = d.get("extra_headers")
                d["extra_headers"] = json.loads(extra) if extra else {}
                channels.append(Channel(**d))
            return channels

    def get_playlist_stats(self, playlist_id: Optional[int] = None) -> dict:
        """Retourne les statistiques d'une liste (total live, movies, series, favorites)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            where = "WHERE playlist_id = ? AND is_enabled = 1" if playlist_id is not None else "WHERE is_enabled = 1"
            params = (playlist_id,) if playlist_id is not None else ()

            cursor.execute(f"SELECT COUNT(*) as total FROM channels {where}", params)
            total = cursor.fetchone()["total"]

            cursor.execute(f"SELECT COUNT(*) as live FROM channels {where} AND stream_type = 'live'", params)
            live = cursor.fetchone()["live"]

            cursor.execute(f"SELECT COUNT(*) as movies FROM channels {where} AND stream_type = 'movie'", params)
            movies = cursor.fetchone()["movies"]

            cursor.execute(f"SELECT COUNT(*) as series FROM channels {where} AND stream_type = 'series'", params)
            series = cursor.fetchone()["series"]

            cursor.execute(f"SELECT COUNT(*) as favs FROM channels {where} AND is_favorite = 1", params)
            favs = cursor.fetchone()["favs"]

            return {
                "total": total,
                "live": live,
                "movies": movies,
                "series": series,
                "favorites": favs
            }

    def get_groups(
        self,
        playlist_id: Optional[int] = None,
        stream_type: Optional[str] = None,
        favorites_only: bool = False,
        only_enabled: bool = True,
        order_by: str = "default"
    ) -> List[Tuple[str, int]]:
        """Retourne la liste des groupes et le nombre de chaînes par groupe."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []

            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)

            if stream_type:
                conditions.append("stream_type = ?")
                params.append(stream_type)

            if favorites_only:
                conditions.append("is_favorite = 1")

            if only_enabled:
                conditions.append("is_enabled = 1")
                conditions.append("""
                    group_title NOT IN (
                        SELECT group_title FROM persistent_disabled_groups
                        WHERE (playlist_id = channels.playlist_id OR playlist_id IS NULL)
                          AND (stream_type = channels.stream_type OR stream_type IS NULL)
                    )
                """)

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            if order_by == "name_asc":
                order_sql = "ORDER BY group_title COLLATE NOCASE ASC"
            elif order_by == "name_desc":
                order_sql = "ORDER BY group_title COLLATE NOCASE DESC"
            elif order_by == "count_desc":
                order_sql = "ORDER BY cnt DESC"
            else:  # "default" = ordre d'apparition original du serveur
                order_sql = "ORDER BY MIN(id) ASC"

            query = f"SELECT group_title, COUNT(*) as cnt, MIN(id) as min_id FROM channels{where_clause} GROUP BY group_title {order_sql}"
            cursor.execute(query, params)
            return [(r["group_title"], r["cnt"]) for r in cursor.fetchall()]

    def get_all_categories_with_channels(
        self,
        playlist_id: Optional[int] = None,
        stream_type: Optional[str] = None
    ) -> Dict[str, List[Channel]]:
        """Retourne toutes les catégories avec l'intégralité de leurs chaînes (activées ou non)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []

            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)

            if stream_type:
                conditions.append("stream_type = ?")
                params.append(stream_type)

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"SELECT * FROM channels{where_clause} ORDER BY id ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            res: Dict[str, List[Channel]] = {}
            for r in rows:
                d = dict(r)
                d["is_favorite"] = bool(d.get("is_favorite", 0))
                d["is_enabled"] = bool(d.get("is_enabled", 1))
                extra = d.get("extra_headers")
                d["extra_headers"] = json.loads(extra) if extra else {}
                ch = Channel(**d)
                grp = ch.group_title or "Général"
                if grp not in res:
                    res[grp] = []
                res[grp].append(ch)
            return res

    def save_channels_enabled_status(self, enabled_ids: List[int], disabled_ids: List[int]):
        """Met à jour l'état d'activation des chaînes en lot et synchronise la table persistante."""
        if not enabled_ids and not disabled_ids:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if enabled_ids:
                for i in range(0, len(enabled_ids), 900):
                    chunk = enabled_ids[i:i+900]
                    ph = ",".join(["?"] * len(chunk))
                    cursor.execute(f"UPDATE channels SET is_enabled = 1 WHERE id IN ({ph})", chunk)
                    cursor.execute(f"""
                        DELETE FROM persistent_disabled_channels
                        WHERE (name, stream_type, playlist_id) IN (
                            SELECT name, stream_type, playlist_id FROM channels WHERE id IN ({ph})
                        )
                    """, chunk)
                    cursor.execute(f"""
                        DELETE FROM persistent_disabled_channels
                        WHERE (stream_type, stream_url) IN (
                            SELECT stream_type, stream_url FROM channels WHERE id IN ({ph}) AND stream_url IS NOT NULL
                        )
                    """, chunk)
            if disabled_ids:
                for i in range(0, len(disabled_ids), 900):
                    chunk = disabled_ids[i:i+900]
                    ph = ",".join(["?"] * len(chunk))
                    cursor.execute(f"UPDATE channels SET is_enabled = 0 WHERE id IN ({ph})", chunk)
                    cursor.execute(f"""
                        INSERT INTO persistent_disabled_channels (name, group_title, stream_url, stream_id, stream_type, playlist_id)
                        SELECT name, group_title, stream_url, stream_id, stream_type, playlist_id
                        FROM channels
                        WHERE id IN ({ph})
                        ON CONFLICT(name, stream_type, playlist_id) DO UPDATE SET
                            group_title=excluded.group_title,
                            stream_url=excluded.stream_url,
                            stream_id=excluded.stream_id
                    """, chunk)
            conn.commit()

    def get_disabled_groups(
        self,
        playlist_id: Optional[int] = None,
        stream_type: Optional[str] = None
    ) -> Set[str]:
        """Retourne l'ensemble des noms de catégories/groupes désactivés pour une playlist et/ou un stream_type."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []
            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)
            if stream_type:
                conditions.append("stream_type = ?")
                params.append(stream_type)
            where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
            cursor.execute(f"SELECT group_title FROM persistent_disabled_groups{where_sql}", params)
            return {r["group_title"] for r in cursor.fetchall()}

    def save_groups_enabled_status(
        self,
        playlist_id: Optional[int],
        stream_type: Optional[str],
        disabled_groups: List[str],
        enabled_groups: List[str]
    ):
        """Met à jour l'état d'activation des groupes de catégories dans persistent_disabled_groups et la table channels."""
        if playlist_id is None:
            return
        st = stream_type or "live"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for grp in enabled_groups:
                cursor.execute(
                    "DELETE FROM persistent_disabled_groups WHERE playlist_id=? AND stream_type=? AND group_title=?",
                    (playlist_id, st, grp)
                )
                cursor.execute("""
                    UPDATE channels SET is_enabled = 1 
                    WHERE playlist_id=? AND stream_type=? AND group_title=?
                      AND (stream_id IS NULL OR stream_id == '' OR (playlist_id, stream_type, stream_id) NOT IN (
                          SELECT playlist_id, stream_type, stream_id FROM persistent_disabled_channels 
                          WHERE playlist_id=? AND stream_type=? AND stream_id IS NOT NULL AND stream_id != ''
                      ))
                      AND (stream_url IS NULL OR stream_url == '' OR (playlist_id, stream_type, stream_url) NOT IN (
                          SELECT playlist_id, stream_type, stream_url FROM persistent_disabled_channels 
                          WHERE stream_url IS NOT NULL AND stream_url != ''
                      ))
                      AND (playlist_id, stream_type, name, group_title) NOT IN (
                          SELECT playlist_id, stream_type, name, group_title FROM persistent_disabled_channels 
                          WHERE playlist_id=? AND stream_type=? AND group_title IS NOT NULL
                      )
                """, (playlist_id, st, grp, playlist_id, st, playlist_id, st))
            for grp in disabled_groups:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO persistent_disabled_groups (group_title, stream_type, playlist_id)
                    VALUES (?, ?, ?)
                    """,
                    (grp, st, playlist_id)
                )
                cursor.execute(
                    "UPDATE channels SET is_enabled = 0 WHERE playlist_id=? AND stream_type=? AND group_title=?",
                    (playlist_id, st, grp)
                )
            conn.commit()


    def set_favorite(self, channel_id: int, is_favorite: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            fav_date = datetime.now().isoformat() if is_favorite else None
            cursor.execute(
                "UPDATE channels SET is_favorite = ?, favorite_added_at = ? WHERE id = ?",
                (1 if is_favorite else 0, fav_date, channel_id)
            )
            # Synchronisation de la table persistante
            cursor.execute("SELECT name, stream_url, stream_id, stream_type, logo_url, group_title FROM channels WHERE id = ?", (channel_id,))
            ch_row = cursor.fetchone()
            if ch_row:
                if is_favorite:
                    cursor.execute("""
                        INSERT INTO persistent_favorites (name, stream_url, stream_id, stream_type, logo_url, group_title, favorite_added_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name, stream_type) DO UPDATE SET
                            stream_url=excluded.stream_url,
                            stream_id=excluded.stream_id,
                            logo_url=excluded.logo_url,
                            favorite_added_at=excluded.favorite_added_at
                    """, (ch_row["name"], ch_row["stream_url"], ch_row["stream_id"], ch_row["stream_type"], ch_row["logo_url"], ch_row["group_title"], fav_date))
                else:
                    cursor.execute(
                        "DELETE FROM persistent_favorites WHERE (name = ? AND stream_type = ?) OR (stream_url IS NOT NULL AND stream_url = ?)",
                        (ch_row["name"], ch_row["stream_type"], ch_row["stream_url"])
                    )
            conn.commit()

    def toggle_favorite(self, channel_id: int, is_favorite: Optional[bool] = None) -> bool:
        """Bascule ou définit l'état favori d'une chaîne ou d'un film avec horodatage d'ajout."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if is_favorite is None:
                cursor.execute("SELECT is_favorite FROM channels WHERE id = ?", (channel_id,))
                row = cursor.fetchone()
                curr = bool(row["is_favorite"]) if row else False
                new_val = not curr
            else:
                new_val = bool(is_favorite)

            fav_date = datetime.now().isoformat() if new_val else None
            cursor.execute(
                "UPDATE channels SET is_favorite = ?, favorite_added_at = ? WHERE id = ?",
                (1 if new_val else 0, fav_date, channel_id)
            )
            # Synchronisation de la table persistante
            cursor.execute("SELECT name, stream_url, stream_id, stream_type, logo_url, group_title FROM channels WHERE id = ?", (channel_id,))
            ch_row = cursor.fetchone()
            if ch_row:
                if new_val:
                    cursor.execute("""
                        INSERT INTO persistent_favorites (name, stream_url, stream_id, stream_type, logo_url, group_title, favorite_added_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name, stream_type) DO UPDATE SET
                            stream_url=excluded.stream_url,
                            stream_id=excluded.stream_id,
                            logo_url=excluded.logo_url,
                            favorite_added_at=excluded.favorite_added_at
                    """, (ch_row["name"], ch_row["stream_url"], ch_row["stream_id"], ch_row["stream_type"], ch_row["logo_url"], ch_row["group_title"], fav_date))
                else:
                    cursor.execute(
                        "DELETE FROM persistent_favorites WHERE (name = ? AND stream_type = ?) OR (stream_url IS NOT NULL AND stream_url = ?)",
                        (ch_row["name"], ch_row["stream_type"], ch_row["stream_url"])
                    )
            conn.commit()
            return new_val

    def clear_all_favorites(self, playlist_id: Optional[int] = None, stream_type: Optional[str] = None):
        """Retire tous les favoris selon les filtres (playlist et/ou type de média)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = ["is_favorite = 1"]
            params: List[Any] = []
            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)
            if stream_type is not None:
                conditions.append("stream_type = ?")
                params.append(stream_type)

            where_clause = " WHERE " + " AND ".join(conditions)
            cursor.execute(f"UPDATE channels SET is_favorite = 0, favorite_added_at = NULL{where_clause}", params)
            if stream_type:
                cursor.execute("DELETE FROM persistent_favorites WHERE stream_type = ?", (stream_type,))
            else:
                cursor.execute("DELETE FROM persistent_favorites")
            conn.commit()

    def update_channel_logo(self, channel_id: int, logo_url: str):
        """Met à jour l'URL du logo/affiche d'une chaîne, d'un film ou d'une série."""
        if not channel_id or not logo_url:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE channels SET logo_url = ? WHERE id = ?", (logo_url, channel_id))
            conn.commit()

    def get_recently_added(
        self,
        playlist_id: Optional[int] = None,
        stream_type: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 30
    ) -> List[Channel]:
        """Retourne les éléments récemment ajoutés triés par date d'ajout réelle décroissante."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = [
                "is_enabled = 1",
                """group_title NOT IN (
                    SELECT group_title FROM persistent_disabled_groups
                    WHERE (playlist_id = channels.playlist_id OR playlist_id IS NULL)
                      AND (stream_type = channels.stream_type OR stream_type IS NULL)
                )"""
            ]
            params: List[Any] = []

            if playlist_id is not None:
                conditions.append("playlist_id = ?")
                params.append(playlist_id)

            if stream_type:
                conditions.append("stream_type = ?")
                params.append(stream_type)

            if search_query and search_query.strip():
                conditions.append("name LIKE ?")
                params.append(f"%{search_query.strip()}%")

            where_clause = " WHERE " + " AND ".join(conditions)
            query = f"""
                SELECT * FROM channels{where_clause}
                ORDER BY
                    CASE WHEN added_at IS NOT NULL AND added_at != '' THEN 0 ELSE 1 END,
                    added_at DESC,
                    id DESC
                LIMIT ?
            """
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            channels = []
            for r in rows:
                d = dict(r)
                d["is_favorite"] = bool(d.get("is_favorite", 0))
                d["is_enabled"] = bool(d.get("is_enabled", 1))
                extra = d.get("extra_headers")
                d["extra_headers"] = json.loads(extra) if extra else {}
                channels.append(Channel(**d))
            return channels

    def get_channel_by_id(self, channel_id: int) -> Optional[Channel]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["is_favorite"] = bool(d.get("is_favorite", 0))
                d["is_enabled"] = bool(d.get("is_enabled", 1))
                extra = d.get("extra_headers")
                d["extra_headers"] = json.loads(extra) if extra else {}
                return Channel(**d)
            return None

    def get_channel(self, channel_id: int) -> Optional[Channel]:
        """Alias pour get_channel_by_id."""
        return self.get_channel_by_id(channel_id)

    # ------------------ EPG ------------------

    def save_epg_batch(self, programs: List[EPGProgram], clear_existing: bool = False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if clear_existing:
                cursor.execute("DELETE FROM epg_programs")

            params = [
                (p.tvg_id, p.title, p.description, p.start_time, p.end_time, p.category, p.icon_url)
                for p in programs
            ]
            cursor.executemany("""
                INSERT INTO epg_programs (tvg_id, title, description, start_time, end_time, category, icon_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, params)

            # Nettoyage des vieux programmes (> 24h)
            cursor.execute("DELETE FROM epg_programs WHERE end_time < datetime('now', '-1 day')")
            conn.commit()

    def get_current_program(self, tvg_id: str) -> Optional[EPGProgram]:
        now_iso = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM epg_programs 
                WHERE tvg_id = ? AND start_time <= ? AND end_time >= ?
                ORDER BY start_time ASC LIMIT 1
            """, (tvg_id, now_iso, now_iso))
            row = cursor.fetchone()
            if row:
                return EPGProgram(**dict(row))
            return None

    def get_current_epg_map(self, tvg_ids: List[str]) -> Dict[str, EPGProgram]:
        """Retourne les programmes actuellement en cours pour une liste de tvg_ids."""
        if not tvg_ids:
            return {}
        now_iso = datetime.now().isoformat()
        clean_ids = [t for t in set(tvg_ids) if t]
        if not clean_ids:
            return {}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            res = {}
            for i in range(0, len(clean_ids), 500):
                chunk = clean_ids[i:i+500]
                placeholders = ",".join(["?"] * len(chunk))
                query = f"""
                    SELECT * FROM epg_programs
                    WHERE tvg_id IN ({placeholders})
                    AND start_time <= ? AND end_time >= ?
                """
                params = list(chunk) + [now_iso, now_iso]
                try:
                    cursor.execute(query, params)
                    for r in cursor.fetchall():
                        prog = EPGProgram(**dict(r))
                        res[prog.tvg_id] = prog
                except Exception:
                    pass
            return res

    def get_current_programs_map(self) -> Dict[str, EPGProgram]:
        """Récupère l'ensemble des programmes en cours en une seule requête SQL ultra-optimisée."""
        now_iso = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM epg_programs
                WHERE start_time <= ? AND end_time >= ?
            """, (now_iso, now_iso))
            rows = cursor.fetchall()
            return {r["tvg_id"]: EPGProgram(**dict(r)) for r in rows}

    def get_epg_for_channel(self, tvg_id: str, limit: int = 20) -> List[EPGProgram]:
        if not tvg_id:
            return []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM epg_programs
                WHERE tvg_id = ? AND end_time >= datetime('now', '-2 hours')
                ORDER BY start_time ASC LIMIT ?
            """, (tvg_id, limit))
            return [EPGProgram(**dict(r)) for r in cursor.fetchall()]

    def get_channel_epg(self, tvg_id: str, limit: int = 20) -> List[EPGProgram]:
        return self.get_epg_for_channel(tvg_id, limit)

    def get_channel_epg_timeline(self, channel: Channel, start_iso: str, end_iso: str) -> List[EPGProgram]:
        """Récupère tous les programmes d'une chaîne sur un intervalle temporel donné (ex: 24h)."""
        ids_to_try = [i for i in [channel.tvg_id, channel.tvg_name, channel.name] if i]
        if not ids_to_try:
            return []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(ids_to_try))
            date_prefix = start_iso[:10]  # "YYYY-MM-DD"
            query = f"""
                SELECT * FROM epg_programs
                WHERE tvg_id IN ({placeholders})
                AND (
                    (start_time < ? AND end_time > ?)
                    OR substr(start_time, 1, 10) = ?
                )
                ORDER BY start_time ASC
            """
            params = list(ids_to_try) + [end_iso, start_iso, date_prefix]
            try:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [EPGProgram(**dict(r)) for r in rows]
            except Exception:
                return []

    # ------------------ WATCH HISTORY ------------------

    def deduplicate_watch_history(self, max_per_type: int = 30):
        """Nettoie les doublons existants et limite la mémorisation à 30 éléments maximum par type (films, séries, TV en direct)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT w.id, w.channel_id, w.channel_name, w.stream_url,
                           COALESCE(c1.stream_type, c2.stream_type) as c_stream_type
                    FROM watch_history w
                    LEFT JOIN channels c1 ON (w.channel_id IS NOT NULL AND w.channel_id > 0 AND w.channel_id = c1.id)
                    LEFT JOIN channels c2 ON (w.stream_url = c2.stream_url)
                    ORDER BY w.id DESC
                """)
                rows = cursor.fetchall()
                if not rows:
                    return

                seen_keys = set()
                type_counts = {"series": 0, "movie": 0, "live": 0, "replay": 0}
                ids_to_delete = []

                for r in rows:
                    h_id = r["id"]
                    raw_name = r["channel_name"] or ""
                    s_url = r["stream_url"] or ""
                    ch_id = r["channel_id"]
                    c_st = r["c_stream_type"] or ""

                    if "/timeshift/" in s_url.lower() or c_st == "replay":
                        key = ("replay", ch_id if (ch_id and ch_id > 0) else raw_name.lower())
                        cat = "replay"
                    elif (
                        c_st == "series"
                        or "/series/" in s_url.lower()
                        or bool(re.search(r"\bS\d{1,2}[\s\.:-]*E\d{1,2}\b", raw_name, re.IGNORECASE))
                    ):
                        name_split = re.split(r"[\s\u2013\u2014\-]+S\d{1,2}E\d{1,2}", raw_name, flags=re.IGNORECASE)
                        s_name = name_split[0].strip() if (name_split and name_split[0].strip()) else raw_name
                        key = ("series", s_name.lower())
                        cat = "series"
                    elif c_st in ("movie", "vod") or "/movie/" in s_url or s_url.endswith((".mp4", ".mkv", ".avi")):
                        key = ("movie", ch_id if (ch_id and ch_id > 0) else raw_name.lower())
                        cat = "movie"
                    else:
                        key = ("live", ch_id if (ch_id and ch_id > 0) else raw_name.lower())
                        cat = "live"

                    if key in seen_keys:
                        ids_to_delete.append(h_id)
                    else:
                        seen_keys.add(key)
                        type_counts[cat] = type_counts.get(cat, 0) + 1
                        if type_counts[cat] > max_per_type:
                            ids_to_delete.append(h_id)

                if ids_to_delete:
                    placeholders = ",".join("?" for _ in ids_to_delete)
                    cursor.execute(f"DELETE FROM watch_history WHERE id IN ({placeholders})", ids_to_delete)
                    conn.commit()
        except Exception:
            pass

    def add_watch_history(self, history: WatchHistory):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            raw_name = history.channel_name or ""
            s_url = history.stream_url or ""
            ch_id = history.channel_id

            is_series = (
                "/series/" in s_url.lower()
                or bool(re.search(r"\bS\d{1,2}[\s\.:-]*E\d{1,2}\b", raw_name, re.IGNORECASE))
            )
            if is_series:
                name_split = re.split(r"[\s\u2013\u2014\-]+S\d{1,2}E\d{1,2}", raw_name, flags=re.IGNORECASE)
                series_name = name_split[0].strip() if (name_split and name_split[0].strip()) else raw_name
                cursor.execute("""
                    DELETE FROM watch_history
                    WHERE stream_url = ?
                       OR channel_name LIKE ?
                       OR (channel_id IS NOT NULL AND channel_id > 0 AND channel_id = ?)
                """, (s_url, f"{series_name}%", ch_id))
            else:
                cursor.execute("""
                    DELETE FROM watch_history
                    WHERE stream_url = ?
                       OR (channel_id IS NOT NULL AND channel_id > 0 AND channel_id = ?)
                       OR (channel_name = ? COLLATE NOCASE)
                """, (s_url, ch_id, raw_name))

            cursor.execute("""
                INSERT INTO watch_history (channel_id, channel_name, stream_url, logo_url, group_title, watched_at, playback_position, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (history.channel_id, history.channel_name, history.stream_url, history.logo_url, history.group_title, history.watched_at, history.playback_position, history.duration))
            conn.commit()

        # Nettoyage et plafonnement strict à 30 par type
        self.deduplicate_watch_history(max_per_type=30)

    def get_watch_history(self, limit: int = 50) -> List[WatchHistory]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM watch_history ORDER BY id DESC LIMIT ?", (limit,))
            return [WatchHistory(**dict(r)) for r in cursor.fetchall()]

    def remove_watch_history(self, history_id: int):
        """Supprime un élément spécifique de l'historique de visionnage (et tous ses épisodes si série), ainsi que sa progression de lecture."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_name, stream_url, channel_id FROM watch_history WHERE id = ?", (history_id,))
            row = cursor.fetchone()
            if row:
                raw_name = row["channel_name"] or ""
                s_url = row["stream_url"] or ""
                ch_id = row["channel_id"]
                is_series = (
                    "/series/" in s_url.lower()
                    or bool(re.search(r"\bS\d{1,2}[\s\.:-]*E\d{1,2}\b", raw_name, re.IGNORECASE))
                )
                if is_series:
                    name_split = re.split(r"[\s\u2013\u2014\-]+S\d{1,2}E\d{1,2}", raw_name, flags=re.IGNORECASE)
                    series_name = name_split[0].strip() if (name_split and name_split[0].strip()) else raw_name
                    pattern = f"{series_name}%" if series_name else ""
                    cursor.execute("""
                        DELETE FROM watch_history
                        WHERE id = ?
                           OR (? != '' AND stream_url = ?)
                           OR (? != '' AND channel_name LIKE ?)
                           OR (? > 0 AND channel_id = ?)
                    """, (history_id, s_url, s_url, pattern, pattern, ch_id or 0, ch_id or 0))

                    cursor.execute("""
                        DELETE FROM playback_progress
                        WHERE (? != '' AND stream_url = ?)
                           OR (? != '' AND channel_name LIKE ?)
                           OR (? > 0 AND channel_id = ?)
                    """, (s_url, s_url, pattern, pattern, ch_id or 0, ch_id or 0))
                else:
                    cursor.execute("""
                        DELETE FROM watch_history
                        WHERE id = ?
                           OR (? != '' AND stream_url = ?)
                           OR (? > 0 AND channel_id = ?)
                           OR (? != '' AND channel_name = ? COLLATE NOCASE)
                    """, (history_id, s_url, s_url, ch_id or 0, ch_id or 0, raw_name, raw_name))

                    cursor.execute("""
                        DELETE FROM playback_progress
                        WHERE (? != '' AND stream_url = ?)
                           OR (? > 0 AND channel_id = ?)
                           OR (? != '' AND channel_name = ? COLLATE NOCASE)
                    """, (s_url, s_url, ch_id or 0, ch_id or 0, raw_name, raw_name))
            else:
                cursor.execute("DELETE FROM watch_history WHERE id = ?", (history_id,))
            conn.commit()

    def get_recently_watched_items(
        self,
        playlist_id: Optional[int] = None,
        stream_type: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique complet des éléments récemment regardés,
        enrichi avec affiches, métadonnées, type de flux et progression.
        """
        import re
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT w.id as history_id, w.channel_id, w.channel_name, w.stream_url, w.logo_url,
                       w.group_title, w.watched_at, w.playback_position, w.duration,
                       COALESCE(c1.id, c2.id) as c_id,
                       COALESCE(c1.playlist_id, c2.playlist_id) as playlist_id,
                       COALESCE(c1.name, c2.name) as c_name,
                       COALESCE(c1.logo_url, c2.logo_url) as c_logo,
                       COALESCE(c1.stream_type, c2.stream_type) as c_stream_type,
                       COALESCE(c1.stream_id, c2.stream_id) as stream_id,
                       COALESCE(c1.stream_url, c2.stream_url) as c_stream_url,
                       COALESCE(c1.rating, c2.rating) as rating,
                       COALESCE(c1.year, c2.year) as year,
                       COALESCE(c1.tvg_id, c2.tvg_id) as tvg_id,
                       COALESCE(c1.tvg_name, c2.tvg_name) as tvg_name,
                       pl.name as playlist_name, pl.playlist_type
                FROM watch_history w
                LEFT JOIN channels c1 ON (w.channel_id IS NOT NULL AND w.channel_id > 0 AND w.channel_id = c1.id)
                LEFT JOIN channels c2 ON (w.stream_url = c2.stream_url)
                LEFT JOIN playlists pl ON COALESCE(c1.playlist_id, c2.playlist_id) = pl.id
                WHERE 1=1
                  AND COALESCE(c1.is_enabled, c2.is_enabled, 1) = 1
                  AND COALESCE(c1.group_title, c2.group_title, '') NOT IN (
                      SELECT group_title FROM persistent_disabled_groups
                      WHERE (playlist_id = COALESCE(c1.playlist_id, c2.playlist_id) OR playlist_id IS NULL)
                        AND (stream_type = COALESCE(c1.stream_type, c2.stream_type) OR stream_type IS NULL)
                  )
            """
            params: List[Any] = []
            if playlist_id is not None:
                query += " AND (COALESCE(c1.playlist_id, c2.playlist_id) = ? OR COALESCE(c1.playlist_id, c2.playlist_id) IS NULL)"
                params.append(playlist_id)
            query += " ORDER BY w.id DESC LIMIT ?"
            params.append(max(100, limit * 3))

            cursor.execute(query, params)
            rows = cursor.fetchall()

            items: List[Dict[str, Any]] = []
            seen_keys = set()

            for r in rows:
                s_url = r["stream_url"]
                if not s_url:
                    continue

                raw_name = r["channel_name"] or r["c_name"] or "Sans titre"
                ch_id = r["channel_id"] or r["c_id"]
                logo_url = r["logo_url"] or r["c_logo"] or ""
                group_title = r["group_title"] or ""
                rating = r["rating"]
                year = r["year"]
                st_type = r["c_stream_type"] or ""
                stream_id = r["stream_id"]

                # Détection intelligente du stream_type si non défini
                is_series = False
                episode_text = ""
                series_name = raw_name

                if "/timeshift/" in s_url.lower() or st_type == "replay":
                    st_type = "replay"
                elif st_type == "series" or "/series/" in s_url or re.search(r"\bS\d{1,2}[\s\.:-]*E\d{1,2}\b", raw_name, re.IGNORECASE):
                    is_series = True
                    st_type = "series"
                    m_ep = re.search(r"\bS(\d{1,2})[\s\.:-]*E(\d{1,2})\b", raw_name, re.IGNORECASE)
                    if m_ep:
                        episode_text = f"S{int(m_ep.group(1))}:E{int(m_ep.group(2))}"
                    name_split = re.split(r"[\s\u2013\u2014\-]+S\d{1,2}E\d{1,2}", raw_name, flags=re.IGNORECASE)
                    if name_split and name_split[0].strip():
                        series_name = name_split[0].strip()

                    stream_id = r["stream_id"]
                    series_stream_url = r["c_stream_url"] or s_url
                    pl_id = r["playlist_id"] or 0

                    # Résoudre l'affiche et métadonnées complètes de la série parente
                    s_row = None
                    if ch_id and r["c_stream_type"] == "series":
                        cursor.execute(
                            "SELECT id, name, logo_url, group_title, rating, year, stream_id, stream_url, playlist_id FROM channels WHERE id = ? AND stream_type = 'series' LIMIT 1",
                            (ch_id,)
                        )
                        s_row = cursor.fetchone()

                    if not s_row:
                        cursor.execute(
                            "SELECT id, name, logo_url, group_title, rating, year, stream_id, stream_url, playlist_id FROM channels WHERE stream_type = 'series' AND name = ? COLLATE NOCASE LIMIT 1",
                            (series_name,)
                        )
                        s_row = cursor.fetchone()

                    if not s_row and "(" in series_name:
                        cursor.execute(
                            "SELECT id, name, logo_url, group_title, rating, year, stream_id, stream_url, playlist_id FROM channels WHERE stream_type = 'series' AND name LIKE ? LIMIT 1",
                            (f"{series_name}%",)
                        )
                        s_row = cursor.fetchone()

                    if s_row:
                        ch_id = s_row["id"]
                        series_name = s_row["name"] or series_name
                        logo_url = s_row["logo_url"] or logo_url
                        group_title = s_row["group_title"] or group_title
                        rating = s_row["rating"] or rating
                        year = s_row["year"] or year
                        stream_id = s_row["stream_id"] or stream_id
                        series_stream_url = s_row["stream_url"] or (f"xtream_series://{stream_id}" if stream_id else s_url)
                        if s_row["playlist_id"]:
                            pl_id = s_row["playlist_id"]

                elif st_type in ("movie", "vod") or "/movie/" in s_url or s_url.endswith((".mp4", ".mkv", ".avi")):
                    st_type = "movie"
                elif not st_type:
                    st_type = "live"

                # Déduplication stricte : un seul poster par série, film, replay ou chaîne (on ne garde que le visionnage le plus récent)
                if st_type == "replay":
                    dedup_key = ("replay", ch_id if (ch_id and ch_id > 0) else raw_name.lower().strip())
                elif is_series:
                    dedup_key = ("series", ch_id if (ch_id and ch_id > 0) else series_name.lower().strip())
                elif st_type in ("movie", "vod"):
                    m_title = (r["c_name"] or raw_name).lower().strip()
                    dedup_key = ("movie", ch_id if (ch_id and ch_id > 0) else m_title)
                else:
                    live_title = (r["c_name"] or raw_name).lower().strip()
                    dedup_key = ("live", ch_id if (ch_id and ch_id > 0) else live_title)

                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                # Filtrage par type demandé
                if stream_type and stream_type != "all":
                    if stream_type == "movie" and st_type not in ("movie", "vod"):
                        continue
                    elif stream_type == "series" and st_type != "series":
                        continue
                    elif stream_type == "replay" and st_type != "replay":
                        continue
                    elif stream_type == "live" and st_type != "live":
                        continue

                # Filtrage par recherche
                if search_query:
                    sq_lower = search_query.lower()
                    if sq_lower not in raw_name.lower() and sq_lower not in series_name.lower():
                        continue

                pos = float(r["playback_position"] or 0.0)
                dur = float(r["duration"] or 0.0)
                pct = 0.0
                if dur > 0 and pos > 0:
                    pct = min(100.0, (pos / dur) * 100.0)

                ch = Channel(
                    id=ch_id,
                    playlist_id=pl_id if is_series else (r["playlist_id"] or 0),
                    name=series_name if is_series else raw_name,
                    stream_url=series_stream_url if is_series else s_url,
                    logo_url=logo_url,
                    group_title=group_title,
                    stream_type=st_type,
                    stream_id=str(stream_id) if stream_id else (str(r["stream_id"]) if r["stream_id"] else None),
                    rating=rating,
                    year=year,
                    tvg_id=r["tvg_id"] or "",
                    tvg_name=r["tvg_name"] or ""
                )

                items.append({
                    "history_id": r["history_id"],
                    "channel": ch,
                    "raw_name": raw_name,
                    "series_name": series_name if is_series else "",
                    "episode_text": episode_text,
                    "playback_position": pos,
                    "duration": dur,
                    "percentage": pct,
                    "watched_at": r["watched_at"],
                    "playlist_name": r["playlist_name"] or "",
                    "stream_url": s_url,
                    "episode_stream_url": s_url,
                })

                if len(items) >= limit:
                    break

            return items

    def clear_history(self, playlist_id: Optional[int] = None, stream_type: Optional[str] = None):
        """Efface l'historique de visionnage et la progression de lecture selon les filtres (playlist et/ou type de média)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if playlist_id is None and (stream_type is None or stream_type == "all"):
                cursor.execute("DELETE FROM watch_history")
                cursor.execute("DELETE FROM playback_progress")
            else:
                items = self.get_recently_watched_items(playlist_id=playlist_id, stream_type=stream_type, limit=5000)
                h_ids = [item["history_id"] for item in items if "history_id" in item]
                if h_ids:
                    placeholders = ",".join("?" for _ in h_ids)
                    cursor.execute(f"DELETE FROM watch_history WHERE id IN ({placeholders})", h_ids)
                    for it in items:
                        ch = it.get("channel")
                        s_url = ch.stream_url if ch else ""
                        ch_id = ch.id if ch else 0
                        raw_name = it.get("raw_name") or ""
                        series_name = it.get("series_name") or ""
                        if series_name:
                            pattern = f"{series_name}%"
                            cursor.execute("""
                                DELETE FROM playback_progress
                                WHERE (? != '' AND stream_url = ?)
                                   OR (? != '' AND channel_name LIKE ?)
                                   OR (? > 0 AND channel_id = ?)
                            """, (s_url, s_url, pattern, pattern, ch_id or 0, ch_id or 0))
                        else:
                            cursor.execute("""
                                DELETE FROM playback_progress
                                WHERE (? != '' AND stream_url = ?)
                                   OR (? > 0 AND channel_id = ?)
                                   OR (? != '' AND channel_name = ? COLLATE NOCASE)
                            """, (s_url, s_url, ch_id or 0, ch_id or 0, raw_name, raw_name))
            conn.commit()

    # ------------------ REPRISE DE LECTURE (VOD & SÉRIES) ------------------

    def save_playback_progress(self, channel_id: Optional[int], stream_url: str, channel_name: str, position: float, duration: float):
        """Mémorise la position de lecture ou l'état terminé si le film/épisode a été vu à plus de 90%."""
        if not stream_url:
            return

        # Ne pas enregistrer de progression pour la télévision en direct (hors replay/timeshift)
        s_url_lower = stream_url.lower()
        if "/live/" in s_url_lower and "/timeshift/" not in s_url_lower:
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()

            cursor.execute("SELECT playback_position, duration FROM playback_progress WHERE stream_url = ?", (stream_url,))
            existing = cursor.fetchone()
            existing_pos = float(existing["playback_position"] or 0.0) if existing else 0.0
            existing_dur = float(existing["duration"] or 0.0) if existing else 0.0

            # S'assurer d'une durée effective positive sans JAMAIS utiliser position (ce qui forcerait 100% de progression)
            if duration > 0:
                effective_dur = duration
            elif existing_dur > 0:
                effective_dur = existing_dur
            else:
                effective_dur = 3600.0

            # Si visionné à >= 90% ou forcé à completion, on enregistre à 100%
            if position >= effective_dur * 0.90 or (effective_dur - position) <= 60:
                saved_pos = effective_dur
            else:
                saved_pos = position

            # Si l'élément était déjà marqué comme terminé (100%), une lecture brève ou fugitive (< 90%)
            # ne doit pas écraser ou dévalider ce statut terminé (seul un clic explicite sur la coche le fait)
            if existing and existing_dur > 0 and (existing_pos >= existing_dur * 0.90 or (existing_dur - existing_pos) <= 60):
                if saved_pos < effective_dur * 0.90 and (effective_dur - saved_pos) > 60:
                    return

            if saved_pos >= 5.0 or (effective_dur > 0 and saved_pos >= effective_dur * 0.90):
                cursor.execute("""
                    INSERT INTO playback_progress (channel_id, stream_url, channel_name, playback_position, duration, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stream_url) DO UPDATE SET
                        channel_id = excluded.channel_id,
                        channel_name = excluded.channel_name,
                        playback_position = excluded.playback_position,
                        duration = excluded.duration,
                        updated_at = excluded.updated_at
                """, (channel_id, stream_url, channel_name, saved_pos, effective_dur, now_iso))
            conn.commit()

    def get_playback_progress(self, channel_id: Optional[int] = None, stream_url: Optional[str] = None) -> Optional[Tuple[float, float]]:
        """Retourne (position, duration) si une reprise valide existe (< 95% et > 10s), sinon None."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            row = None
            if stream_url:
                cursor.execute("SELECT playback_position, duration FROM playback_progress WHERE stream_url = ?", (stream_url,))
                row = cursor.fetchone()
            if not row and channel_id and channel_id > 0:
                cursor.execute("SELECT playback_position, duration FROM playback_progress WHERE channel_id = ?", (channel_id,))
                row = cursor.fetchone()

            if row:
                pos = float(row["playback_position"] or 0.0)
                dur = float(row["duration"] or 0.0)
                if pos >= 10.0 and (dur <= 0 or pos / dur < 0.95):
                    return (pos, dur)
            return None

    def clear_playback_progress(self, channel_id: Optional[int] = None, stream_url: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if stream_url:
                cursor.execute("DELETE FROM playback_progress WHERE stream_url = ?", (stream_url,))
            elif channel_id and channel_id > 0:
                cursor.execute("DELETE FROM playback_progress WHERE channel_id = ?", (channel_id,))
            conn.commit()

    def get_all_playback_progress_map(self) -> Dict[Any, Tuple[float, float]]:
        """Retourne un dictionnaire {identifiant: (position, duration)} pour tous les flux ayant une progression enregistrée."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id, stream_url, playback_position, duration FROM playback_progress")
            res = {}
            for r in cursor.fetchall():
                chid = r["channel_id"]
                surl = r["stream_url"]
                pos = float(r["playback_position"] or 0.0)
                dur = float(r["duration"] or 0.0)
                if pos >= 5.0 or (dur > 0 and pos >= dur * 0.90):
                    if chid:
                        res[chid] = (pos, dur)
                    if surl:
                        res[surl] = (pos, dur)
            return res

    def get_series_progress_rows(self, series_name: str) -> List[Dict[str, Any]]:
        """Retourne les lignes de progression mémorisées appartenant à une série donnée.

        Filtre sur le nom de la série présent dans le channel_name (format
        "Nom de la série — SxxExx : Titre de l'épisode"). Permet d'afficher immédiatement
        les épisodes déjà mémorisés avant toute recherche réseau.
        """
        if not series_name:
            return []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT channel_id, stream_url, channel_name, playback_position, duration, updated_at
                FROM playback_progress
                WHERE channel_name LIKE ? || ' — %'
            """, (series_name,))
            rows = cursor.fetchall()
            res: List[Dict[str, Any]] = []
            for r in rows:
                res.append({
                    "channel_id": r["channel_id"],
                    "stream_url": r["stream_url"],
                    "channel_name": r["channel_name"],
                    "playback_position": float(r["playback_position"] or 0.0),
                    "duration": float(r["duration"] or 0.0),
                    "updated_at": r["updated_at"],
                })
            return res

    # ------------------ SETTINGS ------------------

    def get_settings(self) -> AppSettings:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()
            data = {r["key"]: r["value"] for r in rows}

            settings = AppSettings()
            if "user_agent" in data:
                settings.user_agent = data["user_agent"]
            if "hwdec" in data:
                settings.hwdec = data["hwdec"]
            if "buffer_size_mb" in data:
                settings.buffer_size_mb = int(data["buffer_size_mb"])
            if "default_aspect_ratio" in data:
                settings.default_aspect_ratio = data["default_aspect_ratio"]
            if "volume" in data:
                settings.volume = int(data["volume"])
            if "theme" in data:
                settings.theme = data["theme"]
            if "auto_refresh_epg" in data:
                settings.auto_refresh_epg = data["auto_refresh_epg"].lower() == "true"
            if "epg_refresh_hours" in data:
                settings.epg_refresh_hours = int(data["epg_refresh_hours"])
            if "cache_logos" in data:
                settings.cache_logos = data["cache_logos"].lower() == "true"
            if "deinterlace" in data:
                settings.deinterlace = data["deinterlace"].lower() == "true"
            if "preferred_audio_lang" in data:
                settings.preferred_audio_lang = data["preferred_audio_lang"]
            if "preferred_subtitle_lang" in data:
                settings.preferred_subtitle_lang = data["preferred_subtitle_lang"]
            if "subtitles_enabled" in data:
                settings.subtitles_enabled = data["subtitles_enabled"].lower() == "true"
            if "outer_splitter_sizes" in data:
                settings.outer_splitter_sizes = data["outer_splitter_sizes"]
            if "inner_splitter_sizes" in data:
                settings.inner_splitter_sizes = data["inner_splitter_sizes"]
            if "category_panel_width" in data:
                settings.category_panel_width = int(data["category_panel_width"])
            if "channel_list_width" in data:
                settings.channel_list_width = int(data["channel_list_width"])
            if "categories_collapsed" in data:
                settings.categories_collapsed = data["categories_collapsed"].lower() == "true"
            if "epg_panel_height" in data:
                settings.epg_panel_height = int(data["epg_panel_height"])
            if "epg_panel_visible" in data:
                settings.epg_panel_visible = data["epg_panel_visible"].lower() == "true"
            if "window_x" in data:
                settings.window_x = int(data["window_x"])
            if "window_y" in data:
                settings.window_y = int(data["window_y"])
            if "window_width" in data:
                settings.window_width = int(data["window_width"])
            if "window_height" in data:
                settings.window_height = int(data["window_height"])
            if "window_maximized" in data:
                settings.window_maximized = data["window_maximized"].lower() == "true"
            if "window_fullscreen" in data:
                settings.window_fullscreen = data["window_fullscreen"].lower() == "true"
            if "download_dir" in data:
                settings.download_dir = data["download_dir"]
            if "sync_enabled" in data:
                settings.sync_enabled = data["sync_enabled"].lower() == "true"
            if "sync_folder" in data:
                settings.sync_folder = data["sync_folder"]
            if "sync_last_timestamp" in data:
                settings.sync_last_timestamp = data["sync_last_timestamp"]
            if "auto_play_next_episode" in data:
                settings.auto_play_next_episode = data["auto_play_next_episode"].lower() == "true"
            if "app_language" in data:
                settings.app_language = data["app_language"]
            return settings

    def save_settings(self, settings: AppSettings):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            data = {
                "user_agent": settings.user_agent,
                "hwdec": settings.hwdec,
                "buffer_size_mb": str(settings.buffer_size_mb),
                "default_aspect_ratio": settings.default_aspect_ratio,
                "volume": str(settings.volume),
                "theme": settings.theme,
                "auto_refresh_epg": str(settings.auto_refresh_epg),
                "epg_refresh_hours": str(settings.epg_refresh_hours),
                "cache_logos": str(settings.cache_logos),
                "deinterlace": str(settings.deinterlace),
                "preferred_audio_lang": settings.preferred_audio_lang,
                "preferred_subtitle_lang": settings.preferred_subtitle_lang,
                "subtitles_enabled": str(settings.subtitles_enabled),
                "outer_splitter_sizes": settings.outer_splitter_sizes,
                "inner_splitter_sizes": settings.inner_splitter_sizes,
                "category_panel_width": str(settings.category_panel_width),
                "channel_list_width": str(settings.channel_list_width),
                "categories_collapsed": str(settings.categories_collapsed),
                "epg_panel_height": str(settings.epg_panel_height),
                "epg_panel_visible": str(settings.epg_panel_visible),
                "window_x": str(settings.window_x),
                "window_y": str(settings.window_y),
                "window_width": str(settings.window_width),
                "window_height": str(settings.window_height),
                "window_maximized": str(settings.window_maximized),
                "window_fullscreen": str(settings.window_fullscreen),
                "download_dir": settings.download_dir,
                "sync_enabled": str(settings.sync_enabled),
                "sync_folder": settings.sync_folder,
                "sync_last_timestamp": settings.sync_last_timestamp,
                "auto_play_next_episode": str(settings.auto_play_next_episode),
                "app_language": settings.app_language,
            }
            for k, v in data.items():
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
            conn.commit()

    def update_panel_widths(
        self,
        category_w: Optional[int] = None,
        channel_w: Optional[int] = None,
        collapsed: Optional[bool] = None
    ):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if category_w is not None and category_w > 0:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('category_panel_width', ?)", (str(category_w),))
            if channel_w is not None and channel_w > 0:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('channel_list_width', ?)", (str(channel_w),))
            if collapsed is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('categories_collapsed', ?)", (str(collapsed),))
            conn.commit()

    def update_volume(self, volume: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('volume', ?)", (str(volume),))
            conn.commit()

    def update_splitter_sizes(
        self,
        outer_sizes: Optional[str] = None,
        inner_sizes: Optional[str] = None
    ):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if outer_sizes:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('outer_splitter_sizes', ?)", (outer_sizes,))
            if inner_sizes:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('inner_splitter_sizes', ?)", (inner_sizes,))
            conn.commit()

    def update_audio_subtitle_prefs(
        self,
        audio_lang: Optional[str] = None,
        subtitle_lang: Optional[str] = None,
        subtitles_enabled: Optional[bool] = None
    ):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if audio_lang is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('preferred_audio_lang', ?)", (audio_lang,))
            if subtitle_lang is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('preferred_subtitle_lang', ?)", (subtitle_lang,))
            if subtitles_enabled is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('subtitles_enabled', ?)", (str(subtitles_enabled),))
            conn.commit()

    # ------------------ PRÉFÉRENCES DE TRI PAR CATÉGORIE (VOD & SÉRIES) ------------------

    def get_category_sort_order(self, playlist_id: int, stream_type: str, category_name: str) -> Optional[str]:
        """Récupère l'ordre de tri mémorisé pour une catégorie donnée (films ou séries)."""
        if not category_name:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sort_order FROM category_sort_preferences WHERE playlist_id=? AND stream_type=? AND category_name=?",
                (playlist_id or 0, stream_type, category_name)
            )
            row = cursor.fetchone()
            return row["sort_order"] if row else None

    def set_category_sort_order(self, playlist_id: int, stream_type: str, category_name: str, sort_order: str) -> None:
        """Enregistre l'ordre de tri pour une catégorie donnée (films ou séries)."""
        if not category_name or not sort_order:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO category_sort_preferences (playlist_id, stream_type, category_name, sort_order)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(playlist_id, stream_type, category_name) DO UPDATE SET
                    sort_order=excluded.sort_order
                """,
                (playlist_id or 0, stream_type, category_name, sort_order)
            )
            conn.commit()

    # ------------------ DASHBOARD QUERIES ------------------

    def get_dashboard_continue_watching(self, playlist_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Retourne la liste des médias commencés mais non terminés pour le Tableau de bord."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT p.channel_id, p.stream_url, p.channel_name, p.playback_position, p.duration, p.updated_at,
                       COALESCE(c1.id, c2.id) as ch_id,
                       COALESCE(c1.name, c2.name) as ch_name,
                       COALESCE(c1.logo_url, c2.logo_url) as logo_url,
                       COALESCE(c1.stream_type, c2.stream_type) as stream_type,
                       COALESCE(c1.group_title, c2.group_title) as group_title,
                       COALESCE(c1.rating, c2.rating) as rating,
                       COALESCE(c1.year, c2.year) as year,
                       COALESCE(c1.playlist_id, c2.playlist_id) as playlist_id,
                       COALESCE(c1.stream_id, c2.stream_id) as stream_id,
                       COALESCE(c1.stream_url, c2.stream_url) as c_stream_url,
                       pl.name as playlist_name, pl.playlist_type
                FROM playback_progress p
                LEFT JOIN channels c1 ON (p.channel_id IS NOT NULL AND p.channel_id > 0 AND p.channel_id = c1.id)
                LEFT JOIN channels c2 ON (p.stream_url = c2.stream_url)
                LEFT JOIN playlists pl ON COALESCE(c1.playlist_id, c2.playlist_id) = pl.id
                WHERE p.duration > 0
                  AND p.playback_position >= 5.0
                  AND (
                      (p.playback_position / p.duration) < 0.95
                      OR COALESCE(c1.stream_type, c2.stream_type, '') = 'series'
                      OR p.stream_url LIKE '%/series/%'
                      OR p.channel_name LIKE '%S__E__%'
                      OR p.channel_name LIKE '%S_E_%'
                  )
                  AND (
                      COALESCE(c1.stream_type, c2.stream_type, '') != 'live'
                      OR p.stream_url LIKE '%/timeshift/%'
                  )
                  AND COALESCE(c1.is_enabled, c2.is_enabled, 1) = 1
                  AND COALESCE(c1.group_title, c2.group_title, '') NOT IN (
                      SELECT group_title FROM persistent_disabled_groups
                      WHERE (playlist_id = COALESCE(c1.playlist_id, c2.playlist_id) OR playlist_id IS NULL)
                        AND (stream_type = COALESCE(c1.stream_type, c2.stream_type) OR stream_type IS NULL)
                  )
            """
            params: List[Any] = []
            if playlist_id is not None:
                query += " AND (COALESCE(c1.playlist_id, c2.playlist_id) = ? OR COALESCE(c1.playlist_id, c2.playlist_id) IS NULL)"
                params.append(playlist_id)

            query += " ORDER BY p.updated_at DESC LIMIT ?"
            params.append(max(60, limit * 3))

            cursor.execute(query, params)
            rows = cursor.fetchall()
            items: List[Dict[str, Any]] = []
            seen_keys = set()

            for r in rows:
                pos = float(r["playback_position"] or 0.0)
                dur = float(r["duration"] or 1.0)
                ch_id = r["channel_id"]
                raw_name = r["channel_name"] or r["ch_name"] or "Vidéo"
                series_name = r["ch_name"] or raw_name
                stream_url = r["stream_url"] or ""
                logo_url = r["logo_url"] or ""
                stream_type = r["stream_type"] or ""
                group_title = r["group_title"] or ""
                rating = r["rating"] or ""
                year = r["year"] or ""
                stream_id = r["stream_id"]
                series_stream_url = r["c_stream_url"] or stream_url
                pl_id = r["playlist_id"] or 0
                pl_name = r["playlist_name"] or "Playlist"
                pl_type = (r["playlist_type"] or "m3u").upper()

                # Détection intelligente : Replay, Série ou Film
                is_replay = (
                    stream_type == "replay"
                    or "/timeshift/" in stream_url.lower()
                    or "/timeshift/" in (r["stream_url"] or "").lower()
                )

                # Détection automatique de série si channel_id orphelin ou s'il s'agit d'un épisode
                is_series = (
                    not is_replay and (
                        stream_type == "series"
                        or "/series/" in stream_url.lower()
                        or bool(re.search(r"[\s\u2013\u2014\-]+S\d{1,2}E\d{1,2}", raw_name, re.IGNORECASE))
                    )
                )

                is_completed = (dur > 0 and (pos / dur) >= 0.95)

                # Écarter les films ou replays déjà terminés
                if not is_series and is_completed:
                    continue

                # Écarter les chaînes directes éventuelles
                if not is_series and not is_replay and (stream_type == "live" or r["stream_type"] == "live"):
                    continue

                if is_completed:
                    pct = 0
                    rem_sec = 0
                    from core.i18n import tr
                    rem_str = tr("Épisode suivant disponible")
                else:
                    pct = min(99, max(1, int((pos / dur) * 100)))
                    rem_sec = max(0, int(dur - pos))
                    rem_h = rem_sec // 3600
                    rem_m = (rem_sec % 3600) // 60
                    from core.i18n import tr
                    if rem_h > 0:
                        rem_str = tr("Il reste {hours} h {mins:02d} min", hours=rem_h, mins=rem_m)
                    else:
                        rem_str = tr("Il reste {mins} min", mins=max(1, rem_m))

                episode_text = ""

                if is_replay:
                    stream_type = "replay"
                elif is_series:
                    stream_type = "series"
                    m_ep = re.search(r"\bS(\d{1,2})[\s\.:-]*E(\d{1,2})\b", raw_name, re.IGNORECASE)
                    if m_ep:
                        s_num = int(m_ep.group(1))
                        e_num = int(m_ep.group(2))
                        if is_completed:
                            episode_text = f"S{s_num}:E{e_num + 1}"
                        else:
                            episode_text = f"S{s_num}:E{e_num}"

                    name_split = re.split(r"[\s\u2013\u2014\-]+S\d{1,2}E\d{1,2}", raw_name, flags=re.IGNORECASE)
                    if name_split and name_split[0].strip():
                        series_name = name_split[0].strip()

                    # Si pas de logo_url ou pas de channel_id valide lié à la série parente ou stream_id manquant
                    if not logo_url or not ch_id or r["stream_type"] != "series" or not stream_id:
                        find_q = """
                            SELECT c.id, c.name, c.logo_url, c.group_title, c.rating, c.year, c.playlist_id, c.stream_id, c.stream_url,
                                   pl.name as pl_name, pl.playlist_type as pl_type
                            FROM channels c
                            LEFT JOIN playlists pl ON c.playlist_id = pl.id
                            WHERE c.stream_type = 'series' AND (c.id = ? OR c.name = ? COLLATE NOCASE)
                            LIMIT 1
                        """
                        cursor.execute(find_q, (ch_id or 0, series_name))
                        s_row = cursor.fetchone()
                        if not s_row and "(" in series_name:
                            cursor.execute(
                                """
                                SELECT c.id, c.name, c.logo_url, c.group_title, c.rating, c.year, c.playlist_id, c.stream_id, c.stream_url,
                                       pl.name as pl_name, pl.playlist_type as pl_type
                                FROM channels c
                                LEFT JOIN playlists pl ON c.playlist_id = pl.id
                                WHERE c.stream_type = 'series' AND c.name LIKE ? LIMIT 1
                                """,
                                (f"{series_name}%",)
                            )
                            s_row = cursor.fetchone()

                        if s_row:
                            ch_id = s_row["id"]
                            series_name = s_row["name"] or series_name
                            logo_url = s_row["logo_url"] or logo_url
                            group_title = s_row["group_title"] or group_title
                            rating = s_row["rating"] or rating
                            year = s_row["year"] or year
                            stream_id = s_row["stream_id"] or stream_id
                            series_stream_url = s_row["stream_url"] or (f"xtream_series://{stream_id}" if stream_id else stream_url)
                            if s_row["playlist_id"]:
                                pl_id = s_row["playlist_id"]
                            if s_row["pl_name"]:
                                pl_name = s_row["pl_name"]
                            if s_row["pl_type"]:
                                pl_type = s_row["pl_type"].upper()

                            # Auto-guérison : associer définitivement le channel_id parent dans playback_progress
                            try:
                                cursor.execute(
                                    "UPDATE playback_progress SET channel_id = ? WHERE stream_url = ?",
                                    (ch_id, stream_url)
                                )
                                conn.commit()
                            except Exception:
                                pass

                if not stream_type or stream_type == "live":
                    if not is_replay:
                        stream_type = "movie"

                ch = Channel(
                    id=ch_id,
                    playlist_id=pl_id,
                    name=series_name if is_series else raw_name,
                    stream_url=series_stream_url if is_series else stream_url,
                    logo_url=logo_url,
                    group_title="TV Replay" if is_replay else group_title,
                    stream_type=stream_type,
                    stream_id=str(stream_id) if stream_id else (str(r["stream_id"]) if r["stream_id"] else None),
                    rating=rating,
                    year=year
                )

                # Déduplication : une seule carte par série, replay ou film (le plus récent)
                if is_replay:
                    dedup_key = ("replay", stream_url)
                elif is_series:
                    dedup_key = ("series", ch_id if (ch_id and ch_id > 0) else series_name.lower().strip())
                else:
                    m_title = (r["ch_name"] or raw_name).lower().strip()
                    dedup_key = ("movie", ch_id if (ch_id and ch_id > 0) else m_title)

                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                items.append({
                    "channel": ch,
                    "raw_title": raw_name,
                    "series_name": series_name if is_series else "",
                    "episode_text": episode_text,
                    "position": 0.0 if is_completed else pos,
                    "duration": dur,
                    "remaining_seconds": rem_sec,
                    "remaining_str": rem_str,
                    "percentage": pct,
                    "is_completed": is_completed,
                    "playlist_name": pl_name,
                    "playlist_type": pl_type,
                    "updated_at": r["updated_at"]
                })

                if len(items) >= limit:
                    break
            return items

    def get_dashboard_recent_live(self, playlist_id: Optional[int] = None, limit: int = 15) -> List[Dict[str, Any]]:
        """Retourne les chaînes TV en direct récemment visionnées pour le Tableau de bord."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Depuis l'historique
            query = """
                SELECT DISTINCT COALESCE(c1.id, c2.id) as id,
                                COALESCE(c1.playlist_id, c2.playlist_id) as playlist_id,
                                COALESCE(c1.name, c2.name) as name,
                                COALESCE(c1.stream_url, c2.stream_url) as stream_url,
                                COALESCE(c1.logo_url, c2.logo_url) as logo_url,
                                COALESCE(c1.group_title, c2.group_title) as group_title,
                                COALESCE(c1.tvg_id, c2.tvg_id) as tvg_id,
                                COALESCE(c1.tvg_name, c2.tvg_name) as tvg_name,
                                COALESCE(c1.stream_type, c2.stream_type) as stream_type,
                                pl.name as playlist_name, pl.playlist_type,
                                w.watched_at
                FROM watch_history w
                LEFT JOIN channels c1 ON (w.channel_id IS NOT NULL AND w.channel_id > 0 AND w.channel_id = c1.id)
                LEFT JOIN channels c2 ON (w.stream_url = c2.stream_url)
                LEFT JOIN playlists pl ON COALESCE(c1.playlist_id, c2.playlist_id) = pl.id
                WHERE COALESCE(c1.stream_type, c2.stream_type) = 'live'
                  AND COALESCE(c1.is_enabled, c2.is_enabled, 1) = 1
                  AND COALESCE(c1.group_title, c2.group_title, '') NOT IN (
                      SELECT group_title FROM persistent_disabled_groups
                      WHERE (playlist_id = COALESCE(c1.playlist_id, c2.playlist_id) OR playlist_id IS NULL)
                        AND stream_type = 'live'
                  )
            """
            params: List[Any] = []
            if playlist_id is not None:
                query += " AND COALESCE(c1.playlist_id, c2.playlist_id) = ?"
                params.append(playlist_id)
            query += " ORDER BY w.id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            res: List[Dict[str, Any]] = []
            seen_ids = set()
            for r in rows:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    ch = Channel(
                        id=r["id"],
                        playlist_id=r["playlist_id"] or 0,
                        name=r["name"],
                        stream_url=r["stream_url"],
                        logo_url=r["logo_url"] or "",
                        group_title=r["group_title"] or "",
                        tvg_id=r["tvg_id"] or "",
                        tvg_name=r["tvg_name"] or "",
                        stream_type="live"
                    )
                    res.append({
                        "channel": ch,
                        "playlist_name": r["playlist_name"] or "Direct",
                        "source_label": f"{ (r['playlist_type'] or 'M3U').upper() } · Direct"
                    })

            return res

    # ------------------ CACHE DES SÉRIES (ÉPISODES & SAISONS) ------------------

    def get_series_info(self, playlist_id: int, series_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les données complètes en cache (saisons, épisodes, métadonnées) d'une série."""
        if not playlist_id or not series_id:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data_json FROM series_cache WHERE playlist_id = ? AND series_id = ?",
                (int(playlist_id), str(series_id))
            )
            row = cursor.fetchone()
            if row and row["data_json"]:
                try:
                    data = json.loads(row["data_json"])
                    if isinstance(data, dict):
                        return data
                except Exception as e:
                    print(f"[Database] Erreur lecture cache série ({series_id}) : {e}")
            return None

    def save_series_info(self, playlist_id: int, series_id: str, data: Dict[str, Any]) -> None:
        """Enregistre ou met à jour les données complètes d'une série dans le cache SQLite."""
        if not playlist_id or not series_id or not isinstance(data, dict):
            return
        try:
            data_json = json.dumps(data, ensure_ascii=False)
        except Exception as e:
            print(f"[Database] Erreur sérialisation cache série ({series_id}) : {e}")
            return

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO series_cache (playlist_id, series_id, data_json, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (int(playlist_id), str(series_id), data_json))
            conn.commit()

