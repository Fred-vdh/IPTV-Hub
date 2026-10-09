"""
Tests unitaires pour la recherche croisée et le matching de filmographie d'artiste.
"""

import unittest
from core.models import Channel
from core.tmdb_client import (
    normalize_title_for_matching,
    match_artist_credits_with_library
)


class TestArtistFilmography(unittest.TestCase):

    def test_normalize_title(self):
        self.assertEqual(normalize_title_for_matching("|FR-4K| Inception (2010) MULTI"), "inception")
        self.assertEqual(normalize_title_for_matching("[FR] Breaking Bad S01-S05"), "breakingbad")
        self.assertEqual(normalize_title_for_matching("The Last of Us (2023) 4K HDR"), "thelastofus")
        self.assertEqual(normalize_title_for_matching("Silo (2023) Saison 1"), "silo")

    def test_match_artist_credits_separation(self):
        # Simulation d'une bibliothèque locale avec films et séries
        library = [
            Channel(id=1, name="|FR-4K| Gladiator II (2024)", stream_type="movie", year="2024"),
            Channel(id=2, name="|FR| The Last of Us (2023)", stream_type="series", year="2023"),
            Channel(id=3, name="|FR| Unrelated Movie (2020)", stream_type="movie", year="2020"),
            Channel(id=4, name="|FR| Argo (2012)", stream_type="movie", year="2012"),
        ]

        # Simulation de crédits TMDB combinés
        fake_credits = {
            "combined_credits": {
                "cast": [
                    {
                        "media_type": "movie",
                        "title": "Gladiator II",
                        "original_title": "Gladiator II",
                        "release_date": "2024-11-13",
                        "character": "Marcus Acacius",
                        "vote_average": 7.2
                    },
                    {
                        "media_type": "tv",
                        "name": "The Last of Us",
                        "original_name": "The Last of Us",
                        "first_air_date": "2023-01-15",
                        "character": "Joel Miller",
                        "vote_average": 8.6
                    },
                    {
                        "media_type": "movie",
                        "title": "Un film introuvable",
                        "original_title": "Not In Library",
                        "release_date": "2022-01-01",
                        "character": "Inconnu",
                        "vote_average": 5.0
                    }
                ],
                "crew": [
                    {
                        "job": "Director",
                        "media_type": "movie",
                        "title": "Argo",
                        "original_title": "Argo",
                        "release_date": "2012-10-12",
                        "vote_average": 7.7
                    }
                ]
            }
        }

        matched = match_artist_credits_with_library(fake_credits, library)

        # 1. Vérification films
        movies = matched.get("movies", [])
        self.assertEqual(len(movies), 1)
        self.assertEqual(movies[0]["channel"].id, 1)
        self.assertEqual(movies[0]["role"], "Marcus Acacius")

        # 2. Vérification séries
        series = matched.get("series", [])
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["channel"].id, 2)
        self.assertEqual(series[0]["role"], "Joel Miller")

        # 3. Vérification réalisation
        directed = matched.get("directed", [])
        self.assertEqual(len(directed), 1)
        self.assertEqual(directed[0]["channel"].id, 4)
        self.assertEqual(directed[0]["role"], "Réalisateur")

    def test_experimental_flag_and_signals(self):
        from ui.widgets.vod_grid import EXPERIMENTAL_ARTIST_SEARCH, VODGridView
        self.assertTrue(EXPERIMENTAL_ARTIST_SEARCH)
        self.assertTrue(hasattr(VODGridView, "artist_search_requested"))

    def test_artist_prompt_dialog(self):
        from PyQt6.QtWidgets import QApplication
        from ui.dialogs.artist_filmography_dialog import ArtistSearchPromptDialog
        _app = QApplication.instance() or QApplication([])
        dialog = ArtistSearchPromptDialog(initial_text="")
        dialog.input_edit.setText("Christopher Nolan")
        self.assertEqual(dialog.get_artist_name(), "Christopher Nolan")
        dialog._stop_worker()

    def test_match_artist_creator_and_writer(self):
        """Vérifie que les créateurs de séries (comme Bill Lawrence pour Spin City) sont bien inclus dans 'directed'."""
        library = [
            Channel(id=10, name="|FR| Spin City (1996)", stream_type="series", year="1996"),
            Channel(id=11, name="|FR| Scrubs", stream_type="series", year="2001"),
        ]

        fake_credits = {
            "combined_credits": {
                "cast": [],
                "crew": [
                    {
                        "job": "Creator",
                        "department": "Creator",
                        "media_type": "tv",
                        "name": "Spin City",
                        "original_name": "Spin City",
                        "first_air_date": "1996-09-17",
                        "vote_average": 7.0
                    },
                    {
                        "job": "Writer",
                        "department": "Writing",
                        "media_type": "tv",
                        "name": "Spin City",
                        "original_name": "Spin City",
                        "first_air_date": "1996-09-17",
                        "vote_average": 7.0
                    },
                    {
                        "job": "Creator",
                        "department": "Creator",
                        "media_type": "tv",
                        "name": "Scrubs",
                        "original_name": "Scrubs",
                        "first_air_date": "2001-10-02",
                        "vote_average": 8.0
                    },
                    {
                        "job": "Director",
                        "department": "Directing",
                        "media_type": "tv",
                        "name": "Scrubs",
                        "original_name": "Scrubs",
                        "first_air_date": "2001-10-02",
                        "vote_average": 8.0
                    }
                ]
            }
        }

        matched = match_artist_credits_with_library(fake_credits, library)
        directed = matched.get("directed", [])
        self.assertEqual(len(directed), 2)

        # Spin City doit être présent avec le rôle Créateur
        spin_city = next((x for x in directed if x["channel"].id == 10), None)
        self.assertIsNotNone(spin_city, "Spin City doit être présent dans la filmographie de réalisation/création")
        self.assertEqual(spin_city["role"], "Créateur")

        # Scrubs doit être présent avec le rôle combiné Créateur / Réalisateur
        scrubs = next((x for x in directed if x["channel"].id == 11), None)
        self.assertIsNotNone(scrubs)
        self.assertEqual(scrubs["role"], "Créateur / Réalisateur")


if __name__ == "__main__":
    unittest.main()

