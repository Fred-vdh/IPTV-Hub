"""
Tests unitaires pour le parser M3U et la base de données SQLite.
"""

import unittest
import tempfile
import os
import gc

from core.models import Playlist, Channel, prioritize_categories
from core.database import Database
from core.m3u_parser import M3UParser
from core.epg_manager import parse_xmltv_date, EPGManager


SAMPLE_M3U = """#EXTM3U
#EXTINF:-1 tvg-id="TF1.fr" tvg-name="TF1 HD" tvg-logo="https://example.com/tf1.png" group-title="Généraliste",TF1 HD
http://stream.example.com/tf1.m3u8
#EXTINF:-1 tvg-id="FR2.fr" tvg-name="France 2" tvg-logo="https://example.com/fr2.png" group-title="Généraliste",France 2
#EXTVLCOPT:http-user-agent=CustomUA/1.0
http://stream.example.com/fr2.m3u8
#EXTINF:-1 tvg-id="CANAL.fr" tvg-name="Canal+ Cinema" group-title="Cinéma",Canal+ Cinema (Film)
http://stream.example.com/vod/movie.mp4
"""

SAMPLE_XMLTV_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="TF1.fr">
    <display-name>TF1</display-name>
  </channel>
  <programme start="{start}" stop="{stop}" channel="TF1.fr">
    <title>Le Journal de 20h</title>
    <desc>Journal télévisé d'information.</desc>
    <category>Information</category>
  </programme>
</tv>
"""


class TestM3UParser(unittest.TestCase):
    def test_parse_content(self):
        lines = SAMPLE_M3U.strip().splitlines()
        channels = M3UParser.parse_content(lines, playlist_id=1)

        self.assertEqual(len(channels), 3)

        # Chaîne 1
        self.assertEqual(channels[0].name, "TF1 HD")
        self.assertEqual(channels[0].tvg_id, "TF1.fr")
        self.assertEqual(channels[0].logo_url, "https://example.com/tf1.png")
        self.assertEqual(channels[0].group_title, "Généraliste")
        self.assertEqual(channels[0].stream_type, "live")

        # Chaîne 2 avec custom User-Agent
        self.assertEqual(channels[1].name, "France 2")
        self.assertEqual(channels[1].user_agent, "CustomUA/1.0")

        # Chaîne 3 VOD
        self.assertEqual(channels[2].name, "Canal+ Cinema (Film)")
        self.assertEqual(channels[2].stream_type, "movie")
        self.assertEqual(channels[2].container_extension, "mp4")


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db = Database(self.temp_db_path)

    def tearDown(self):
        del self.db
        gc.collect()
        self.temp_dir.cleanup()

    def test_playlist_and_channels(self):
        p = Playlist(name="Test Playlist", url_or_path="http://example.com/list.m3u")
        pid = self.db.add_playlist(p)
        self.assertIsNotNone(pid)

        channels = [
            Channel(playlist_id=pid, name="TF1", stream_url="http://tf1.m3u8", group_title="France", tvg_id="TF1.fr"),
            Channel(playlist_id=pid, name="M6", stream_url="http://m6.m3u8", group_title="France", tvg_id="M6.fr"),
            Channel(playlist_id=pid, name="BBC One", stream_url="http://bbc.m3u8", group_title="UK", tvg_id="BBC1.uk"),
        ]
        self.db.save_channels_batch(pid, channels)

        # Récupération de tous
        res = self.db.get_channels(playlist_id=pid)
        self.assertEqual(len(res), 3)

        # Filtre par groupe
        res_fr = self.db.get_channels(playlist_id=pid, group_title="France")
        self.assertEqual(len(res_fr), 2)

        # Recherche
        res_search = self.db.get_channels(playlist_id=pid, search_query="BBC")
        self.assertEqual(len(res_search), 1)
        self.assertEqual(res_search[0].name, "BBC One")

        # Favoris : on favorise TF1 spécifiquement
        tf1_ch = next(c for c in res if c.name == "TF1")
        self.db.set_favorite(tf1_ch.id, True)
        res_fav = self.db.get_channels(playlist_id=pid, favorites_only=True)
        self.assertEqual(len(res_fav), 1)
        self.assertEqual(res_fav[0].name, "TF1")

        # Groupes
        groups = self.db.get_groups(playlist_id=pid)
        self.assertEqual(len(groups), 2)


class TestEPG(unittest.TestCase):
    def test_date_parsing(self):
        d = parse_xmltv_date("20260831200000 +0200")
        self.assertEqual(d, "2026-08-31T20:00:00+02:00")

    def test_epg_xml_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, "epg_test.db")
            db = Database(temp_path)
            mgr = EPGManager(db)

            import io
            from datetime import datetime, timedelta
            now = datetime.now()
            start_str = now.strftime("%Y%m%d%H%M%S")
            stop_str = (now + timedelta(hours=2)).strftime("%Y%m%d%H%M%S")
            xml_content = SAMPLE_XMLTV_TEMPLATE.format(start=start_str, stop=stop_str)

            stream = io.BytesIO(xml_content.encode("utf-8"))
            count = mgr.parse_xmltv_stream(stream)
            self.assertEqual(count, 1)

            prog = db.get_channel_epg("TF1.fr")
            self.assertEqual(len(prog), 1)
            self.assertEqual(prog[0].title, "Le Journal de 20h")

            del db
            gc.collect()


class TestMovieMetadataAndVOD(unittest.TestCase):
    def test_parse_movie_metadata(self):
        from core.models import parse_movie_metadata

        meta1 = parse_movie_metadata("[FR] The Whisper Man (2026) MULTI VFF", raw_rating="7.3")
        self.assertEqual(meta1["year"], "2026")
        self.assertEqual(meta1["quality_tag"], "MULTI VFF")
        self.assertEqual(meta1["rating"], "7.3")

        meta2 = parse_movie_metadata("Normal (2026) MULTI VFQ", raw_rating="8.54")
        self.assertEqual(meta2["year"], "2026")
        self.assertEqual(meta2["quality_tag"], "MULTI VFQ")
        self.assertEqual(meta2["rating"], "8.5")

        meta3 = parse_movie_metadata("Desert Warrior [2025] 4K HDR", raw_rating="9.0")
        self.assertEqual(meta3["year"], "2025")
        self.assertEqual(meta3["quality_tag"], "4K HDR")
        self.assertEqual(meta3["rating"], "9.0")

    def test_vod_database_pagination_and_sorting(self):
        temp_dir = tempfile.TemporaryDirectory()
        temp_db = os.path.join(temp_dir.name, "vod_test.db")
        db = Database(temp_db)

        pid = db.add_playlist(Playlist(name="VOD List"))
        movies = [
            Channel(playlist_id=pid, name="Film C (2023)", stream_type="movie", group_title="Nouveautés", rating="7.0", year="2023"),
            Channel(playlist_id=pid, name="Film A (2025)", stream_type="movie", group_title="Nouveautés", rating="8.5", year="2025"),
            Channel(playlist_id=pid, name="Film B (2024)", stream_type="movie", group_title="Action", rating="6.5", year="2024"),
        ]
        db.save_channels_batch(pid, movies)

        # Total count
        count = db.get_channel_count(playlist_id=pid, stream_type="movie")
        self.assertEqual(count, 3)

        # Count per category
        count_nouv = db.get_channel_count(playlist_id=pid, group_title="Nouveautés", stream_type="movie")
        self.assertEqual(count_nouv, 2)

        # Sort by name_asc
        sorted_name = db.get_channels(playlist_id=pid, stream_type="movie", order_by="name_asc")
        self.assertEqual(sorted_name[0].name, "Film A (2025)")
        self.assertEqual(sorted_name[1].name, "Film B (2024)")
        self.assertEqual(sorted_name[2].name, "Film C (2023)")

        # Sort by rating_desc
        sorted_rating = db.get_channels(playlist_id=pid, stream_type="movie", order_by="rating_desc")
        self.assertEqual(sorted_rating[0].name, "Film A (2025)")
        self.assertEqual(sorted_rating[1].name, "Film C (2023)")
        # Test Watch History
        from core.models import WatchHistory
        h1 = WatchHistory(channel_name="Film A (2025)", stream_url="http://stream/a.mp4", watched_at="2026-09-05T10:00:00", playback_position=600, duration=3600)
        h2 = WatchHistory(channel_name="Série S01E01", stream_url="http://stream/series/s1e1.mkv", watched_at="2026-09-05T11:00:00", playback_position=1200, duration=2400)
        db.add_watch_history(h1)
        db.add_watch_history(h2)

        items = db.get_recently_watched_items(playlist_id=None, stream_type="all")
        self.assertEqual(len(items), 2)
        # Check percentage
        self.assertAlmostEqual(items[0]["percentage"], 50.0, places=1) # h2
        self.assertAlmostEqual(items[1]["percentage"], 16.66, places=1) # h1

        # Test Watch History & Playback Progress synchronization
        db.save_playback_progress(channel_id=None, stream_url="http://stream/a.mp4", channel_name="Film A (2025)", position=600, duration=3600)
        db.save_playback_progress(channel_id=None, stream_url="http://stream/series/s1e1.mkv", channel_name="Série S01E01", position=1200, duration=2400)
        self.assertEqual(len(db.get_dashboard_continue_watching()), 2)

        # Test single removal
        h2_id = items[0]["history_id"]
        db.remove_watch_history(h2_id)
        items_after_remove = db.get_recently_watched_items()
        self.assertEqual(len(items_after_remove), 1)
        self.assertEqual(items_after_remove[0]["raw_name"], "Film A (2025)")

        # Verify playback progress was also removed for h2 and reflects in dashboard
        continue_items = db.get_dashboard_continue_watching()
        self.assertEqual(len(continue_items), 1)
        self.assertEqual(continue_items[0]["channel"].stream_url, "http://stream/a.mp4")

        # Test clear history
        db.clear_history()
        self.assertEqual(len(db.get_recently_watched_items()), 0)
        self.assertEqual(len(db.get_dashboard_continue_watching()), 0)

        # Test intercalated repeated watch of series and films
        s1 = WatchHistory(channel_name="Super Série S01E01", stream_url="http://stream/series/s1e1.mkv", watched_at="2026-09-05T08:00:00", playback_position=100, duration=2000)
        m1 = WatchHistory(channel_name="Mon Film Super", stream_url="http://stream/film1.mp4", watched_at="2026-09-05T09:00:00", playback_position=200, duration=3000)
        s2 = WatchHistory(channel_name="Super Série S01E02", stream_url="http://stream/series/s1e2.mkv", watched_at="2026-09-05T10:00:00", playback_position=500, duration=2000)
        m2 = WatchHistory(channel_name="Mon Film Super", stream_url="http://stream/film1.mp4", watched_at="2026-09-05T11:00:00", playback_position=1500, duration=3000)

        db.add_watch_history(s1)
        db.add_watch_history(m1)
        db.add_watch_history(s2)
        db.add_watch_history(m2)

        items_intercalated = db.get_recently_watched_items(playlist_id=None, stream_type="all")
        # Doit contenir exactement 2 affiches uniques : Mon Film Super et Super Série
        self.assertEqual(len(items_intercalated), 2)
        # Le premier doit être Mon Film Super (visionné en dernier à 11:00)
        self.assertEqual(items_intercalated[0]["raw_name"], "Mon Film Super")
        # Le second doit être Super Série avec l'épisode S1:E2 (visionné à 10:00)
        self.assertEqual(items_intercalated[1]["series_name"], "Super Série")
        self.assertEqual(items_intercalated[1]["episode_text"], "S1:E2")

        del db
        gc.collect()
        temp_dir.cleanup()


class TestCategoryPrioritization(unittest.TestCase):
    def test_prioritize_categories(self):
        cats = [
            ("🎬 Action", 50),
            ("🎬 Comédie", 30),
            ("🎬 TOP 100", 100),
            ("🎬 Nouveautés 2025", 80),
            ("🎬 Drame", 40),
            ("🎬 Meilleurs Films", 60),
            ("🎬 Derniers Ajouts", 25),
        ]
        res = prioritize_categories(cats)
        names = [c[0] for c in res]

        # Rang 1 : Nouveautés / Derniers Ajouts
        self.assertIn(names[0], ("🎬 Nouveautés 2025", "🎬 Derniers Ajouts"))
        self.assertIn(names[1], ("🎬 Nouveautés 2025", "🎬 Derniers Ajouts"))

        # Rang 2 : TOP 100 / Meilleurs Films
        self.assertIn(names[2], ("🎬 TOP 100", "🎬 Meilleurs Films"))
        self.assertIn(names[3], ("🎬 TOP 100", "🎬 Meilleurs Films"))

        # Rang 3 : Autres catégories
        self.assertEqual(names[4:], ["🎬 Action", "🎬 Comédie", "🎬 Drame"])


class TestRecentlyAddedDates(unittest.TestCase):
    def test_recently_added_ordering_and_formatting(self):
        from ui.widgets.recently_added_view import format_recent_date

        temp_dir = tempfile.TemporaryDirectory()
        temp_db = os.path.join(temp_dir.name, "recent_test.db")
        db = Database(temp_db)

        pid = db.add_playlist(Playlist(name="Recent Test"))
        movies = [
            Channel(playlist_id=pid, name="Film Ancien", stream_type="movie", added_at="2024-01-10T12:00:00"),
            Channel(playlist_id=pid, name="Film Récent", stream_type="movie", added_at="2026-09-01T15:30:00"),
            Channel(playlist_id=pid, name="Film Très Récent", stream_type="movie", added_at="2026-09-05T08:00:00"),
        ]
        db.save_channels_batch(pid, movies)

        recents = db.get_recently_added(playlist_id=pid, stream_type="movie", limit=10)
        self.assertEqual(len(recents), 3)
        self.assertEqual(recents[0].name, "Film Très Récent")
        self.assertEqual(recents[1].name, "Film Récent")
        self.assertEqual(recents[2].name, "Film Ancien")

        # Test date format
        self.assertEqual(format_recent_date(None), "")
        self.assertEqual(format_recent_date(""), "")
        self.assertIn("sept.", format_recent_date("2026-09-05T08:00:00"))
        self.assertIn("2024", format_recent_date("2024-01-10T12:00:00"))


if __name__ == "__main__":
    unittest.main()

