import pytest
from core.models import Channel
from core.tmdb_client import (
    normalize_title_for_matching,
    clean_search_title,
    match_artist_credits_with_library,
)


def test_normalize_title_handles_superscripts():
    # Exposants courants dans l'IPTV
    title = "|FR| Quand Harry Rencontre Sally (1989) ᴴ²⁶⁵"
    norm = normalize_title_for_matching(title)
    assert norm == "quandharryrencontresally", f"Got: {norm}"

    tmdb_title = "Quand Harry rencontre Sally…"
    norm_tmdb = normalize_title_for_matching(tmdb_title)
    assert norm_tmdb == "quandharryrencontresally"
    assert norm == norm_tmdb


def test_clean_search_title_handles_superscripts():
    title = "|FR| Quand Harry Rencontre Sally (1989) ᴴ²⁶⁵"
    cleaned = clean_search_title(title)
    assert "H265" not in cleaned
    assert "ᴴ" not in cleaned
    assert "Quand Harry Rencontre Sally" in cleaned


def test_match_artist_credits_quand_harry_rencontre_sally():
    # Simuler les crédits TMDB de Billy Crystal
    credits_data = {
        "combined_credits": {
            "cast": [
                {
                    "media_type": "movie",
                    "title": "Quand Harry rencontre Sally…",
                    "original_title": "When Harry Met Sally...",
                    "release_date": "1989-07-12",
                    "character": "Harry Burns",
                    "vote_average": 7.5,
                },
                {
                    "media_type": "movie",
                    "title": "Princess Bride",
                    "original_title": "The Princess Bride",
                    "release_date": "1987-09-25",
                    "character": "Miracle Max",
                    "vote_average": 7.7,
                }
            ],
            "crew": []
        }
    }

    # Chaînes en bibliothèque locale
    channels = [
        Channel(
            id=101,
            playlist_id=1,
            name="|FR| Quand Harry Rencontre Sally (1989) ᴴ²⁶⁵",
            stream_url="http://stream1",
            stream_type="movie",
            year="",
        ),
        Channel(
            id=102,
            playlist_id=1,
            name="|FR| Princess Bride (1987)",
            stream_url="http://stream2",
            stream_type="movie",
            year="1987",
        ),
        Channel(
            id=103,
            playlist_id=1,
            name="|FR| Autre Film Inconnu (2020)",
            stream_url="http://stream3",
            stream_type="movie",
            year="2020",
        )
    ]

    matched = match_artist_credits_with_library(credits_data, channels)
    matched_movies = matched["movies"]
    assert len(matched_movies) == 2

    titles = [m["title"] for m in matched_movies]
    channel_ids = [m["channel"].id for m in matched_movies]
    assert "Quand Harry rencontre Sally…" in titles
    assert 101 in channel_ids
    assert 102 in channel_ids
