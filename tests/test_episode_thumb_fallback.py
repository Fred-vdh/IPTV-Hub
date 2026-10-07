"""
Tests du repli des vignettes d'épisodes de série.

Contexte : certains fournisseurs Xtream renvoient les visuels de certains épisodes sur un domaine
hors service (HTTP 404) alors que le même fichier est bien servi, au même chemin, par le domaine
qui héberge l'affiche de la série (cas observé : « Lanterns » vs « Spin City »). De plus, un échec
de téléchargement laissait la vignette définitivement sur l'image par défaut car la chaîne de
repli (backdrop série → affiche saison → affiche série) n'était jamais déclenchée.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtNetwork import QNetworkReply
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.image_loader import ImageLoader
from core.models import Channel
from ui.widgets.series_details_view import EpisodeCardWidget, SeriesDetailsView


DEAD_HOST_EP = "http://1.pi-cname.com:8080/images/eamjkYDnuDcvS1MyynI4B9nE6KL_big.jpg"
GOOD_HOST_EP = "http://i.pure-redirect.com/images/eamjkYDnuDcvS1MyynI4B9nE6KL_big.jpg"
GOOD_HOST_LOGO = "http://i.pure-redirect.com/images/c12906f8be834be09573291a27dc8110.png"
DEAD_HOST_BACKDROP = "http://1.pi-cname.com:8080/images/95350_tv_backdrop_0.jpg"
GOOD_HOST_BACKDROP = "http://i.pure-redirect.com/images/95350_tv_backdrop_0.jpg"


class _FakeReply:
    """Faux QNetworkReply en erreur, sans réseau ni boucle d'événements."""

    def __init__(self, error=QNetworkReply.NetworkError.ContentNotFoundError):
        self._error = error

    def error(self):
        return self._error

    def deleteLater(self):
        pass


class _FakeLoader:
    """ImageLoader factice : enregistre les demandes au lieu de télécharger réellement."""

    def __init__(self):
        self.requests = []   # liste de dicts {url, on_success, on_failed}
        self.cached = {}     # url -> QPixmap
        self.cancelled = []

    def get_cached_image(self, url):
        return self.cached.get(url)

    def load_image(self, url, on_success=None, target=None, priority=False, on_failed=None):
        self.requests.append({"url": url, "on_success": on_success, "on_failed": on_failed})
        return None

    def cancel_target(self, target):
        self.cancelled.append(target)

    @property
    def last_url(self):
        return self.requests[-1]["url"] if self.requests else ""

    def fail_last(self):
        req = self.requests.pop()
        req["on_failed"](req["url"])

    def succeed_last(self, color="#2563eb"):
        req = self.requests.pop()
        pixmap = QPixmap(220, 124)
        pixmap.fill(QColor(color))
        req["on_success"](pixmap)



class TestAlternateHostUrls(unittest.TestCase):
    """Bascule de domaine : même chemin servi par un autre domaine du fournisseur."""

    def test_swap_keeps_path_and_uses_known_scheme(self):
        variants = ImageLoader.alternate_host_urls(DEAD_HOST_EP, [GOOD_HOST_LOGO, DEAD_HOST_EP])
        self.assertEqual(variants, [GOOD_HOST_EP])

    def test_limit_and_deduplication(self):
        known = [
            "http://a.example.com/x.png",
            "http://b.example.com/x.png",
            "http://c.example.com/x.png",
        ]
        variants = ImageLoader.alternate_host_urls("http://dead.example.com/img/ep.jpg", known, limit=2)
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0], "http://a.example.com/img/ep.jpg")
        self.assertEqual(variants[1], "http://b.example.com/img/ep.jpg")

    def test_same_authority_is_ignored(self):
        variants = ImageLoader.alternate_host_urls(DEAD_HOST_EP, [DEAD_HOST_EP, ""])
        self.assertEqual(variants, [])

    def test_known_urls_without_scheme_or_relative_are_ignored(self):
        variants = ImageLoader.alternate_host_urls(DEAD_HOST_EP, ["/images/x.jpg", "logo.png", None])
        self.assertEqual(variants, [])

    def test_invalid_source_url_returns_empty(self):
        self.assertEqual(ImageLoader.alternate_host_urls("", [GOOD_HOST_LOGO]), [])
        self.assertEqual(ImageLoader.alternate_host_urls("logo.png", [GOOD_HOST_LOGO]), [])

    def test_query_string_is_preserved(self):
        variants = ImageLoader.alternate_host_urls(
            "http://dead.example.com/img/ep.jpg?token=abc",
            ["https://good.example.com/other.png"],
        )
        self.assertEqual(variants, ["https://good.example.com/img/ep.jpg?token=abc"])


class TestImageLoaderFailureCallback(unittest.TestCase):
    """L'ImageLoader doit prévenir la vue lorsqu'une image échoue (pour enchaîner un repli)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.loader = ImageLoader.instance()
        self.addCleanup(self.loader._subscribers.clear)
        self.addCleanup(self.loader._failed_subscribers.clear)
        self.addCleanup(self.loader._target_urls.clear)
        self.calls = []

    def _register(self, url, target=None, on_failed=None):
        # Empêche toute requête réseau : on ne teste que l'abonnement et la notification d'échec.
        with patch.object(self.loader, "request_image_priority", lambda u: None):
            self.loader.load_image(
                url,
                None,
                target=target,
                priority=True,
                on_failed=on_failed or self.calls.append,
            )

    def _fail(self, url):
        reply = _FakeReply()
        self.loader.pending_replies[reply] = url
        self.loader._on_reply_finished(reply)

    def test_on_failed_called_for_failed_url(self):
        self._register(DEAD_HOST_EP)
        self._fail(DEAD_HOST_EP)
        self.assertEqual(self.calls, [DEAD_HOST_EP])
        self.assertNotIn(DEAD_HOST_EP, self.loader._failed_subscribers)

    def test_on_failed_called_once_only(self):
        self._register(DEAD_HOST_EP)
        self._fail(DEAD_HOST_EP)
        self._fail(DEAD_HOST_EP)
        self.assertEqual(self.calls, [DEAD_HOST_EP])

    def test_failure_of_other_url_does_not_notify(self):
        self._register(DEAD_HOST_EP)
        self._fail("http://other.example.com/x.png")
        self.assertEqual(self.calls, [])

    def test_target_destruction_prunes_failure_subscriber(self):
        target = QObject()
        self._register(DEAD_HOST_EP, target=target)
        self.loader.cancel_target(target)
        self._fail(DEAD_HOST_EP)
        self.assertEqual(self.calls, [])

    def test_decode_failure_also_notifies(self):
        self._register(DEAD_HOST_EP)
        reply = _FakeReply(error=QNetworkReply.NetworkError.NoError)
        reply.readAll = lambda: b"pas une image"
        self.loader.pending_replies[reply] = DEAD_HOST_EP
        self.loader._on_reply_finished(reply)
        self.assertEqual(self.calls, [DEAD_HOST_EP])


class TestEpisodeCardThumbnailFallback(unittest.TestCase):
    """La carte d'épisode doit basculer de domaine puis utiliser les visuels de repli."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.loader = _FakeLoader()
        patcher = patch.object(ImageLoader, "instance", staticmethod(lambda: self.loader))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = Database(str(Path(self.temp_dir.name) / "test.db"))

    def _make_card(self, image_url=DEAD_HOST_EP, fallback_urls=None, host_candidates=None):
        episode = {
            "id": "743900",
            "episode_num": 1,
            "title": "Pilote",
            "info": {"movie_image": image_url} if image_url else {},
        }
        return EpisodeCardWidget(
            episode=episode,
            season_num="1",
            fallback_urls=fallback_urls or [],
            host_candidates=host_candidates if host_candidates is not None else [GOOD_HOST_LOGO],
        )

    def test_dead_host_falls_back_to_working_host(self):
        card = self._make_card()
        self.assertEqual(self.loader.last_url, DEAD_HOST_EP)

        self.loader.fail_last()

        # Même chemin, autre domaine (celui de l'affiche déjà affichée) : cas réel « Lanterns ».
        self.assertEqual(self.loader.last_url, GOOD_HOST_EP)
        self.loader.succeed_last()
        self.assertIsNotNone(card.pixmap)
        self.assertFalse(card.pixmap.isNull())
        self.assertEqual(card._active_loading_url, GOOD_HOST_EP)
        card.cleanup()

    def test_falls_back_to_series_visual_when_all_hosts_fail(self):
        card = self._make_card(
            fallback_urls=[DEAD_HOST_BACKDROP, GOOD_HOST_LOGO],
            host_candidates=[DEAD_HOST_BACKDROP],  # aucun domaine valide connu
        )
        self.assertEqual(self.loader.last_url, DEAD_HOST_EP)

        self.loader.fail_last()   # vignette épisode KO
        self.assertEqual(self.loader.last_url, DEAD_HOST_BACKDROP)

        self.loader.fail_last()   # backdrop KO -> visuel de repli suivant
        self.assertEqual(self.loader.last_url, GOOD_HOST_LOGO)
        self.loader.succeed_last("#10b981")
        self.assertIsNotNone(card.pixmap)
        self.assertFalse(card.pixmap.isNull())
        card.cleanup()

    def test_placeholder_when_everything_fails_and_attempts_are_bounded(self):
        card = self._make_card(fallback_urls=[DEAD_HOST_BACKDROP])
        self.assertIsNotNone(self.loader.last_url)

        guard = 0
        while self.loader.requests and guard < 50:
            self.loader.fail_last()
            guard += 1

        self.assertIsNone(card.pixmap)          # image par défaut conservée
        self.assertLessEqual(guard, card._max_attempts)
        card.cleanup()

    def test_no_episode_image_uses_fallback_directly(self):
        card = self._make_card(image_url="", fallback_urls=[GOOD_HOST_LOGO])
        self.assertEqual(self.loader.last_url, GOOD_HOST_LOGO)
        self.loader.succeed_last()
        self.assertIsNotNone(card.pixmap)
        card.cleanup()

    def test_variant_already_cached_is_applied_without_request(self):
        self.loader.cached[GOOD_HOST_EP] = QPixmap(220, 124)
        card = self._make_card()
        requests_before = len(self.loader.requests)

        self.loader.fail_last()   # échec du domaine mort -> variante déjà en cache

        self.assertEqual(len(self.loader.requests), requests_before - 1)
        self.assertIsNotNone(card.pixmap)
        card.cleanup()

    def test_cleanup_resets_state_and_cancels_target(self):
        card = self._make_card()
        card.cleanup()
        self.assertIn(card, self.loader.cancelled)
        self.assertIsNone(card.pixmap)
        self.assertEqual(card._candidate_urls, [])
        self.assertEqual(card._active_loading_url, "")


class TestSeriesViewImageCandidates(unittest.TestCase):
    """La vue doit fournir aux cartes les domaines d'images connus de la série."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.loader = _FakeLoader()
        patcher = patch.object(ImageLoader, "instance", staticmethod(lambda: self.loader))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = Database(str(Path(self.temp_dir.name) / "test.db"))
        self.view = SeriesDetailsView(self.db)
        self.addCleanup(self.view.stop_workers)

    def _setup_series(self):
        self.view.channel = Channel(
            id=1, name="|FR| Lanterns (2026)", stream_type="series",
            stream_url="xtream_series://21132", logo_url=GOOD_HOST_LOGO,
        )
        self.view.series_data = {"info": {"backdrop_path": [DEAD_HOST_BACKDROP]}, "episodes": {}}
        self.view.season_covers = {"1": DEAD_HOST_BACKDROP}
        self.view.all_episodes_flat = [{"id": "743900", "info": {"movie_image": DEAD_HOST_EP}}]
        self.view.episodes_by_season = {
            "1": [{"id": "743900", "episode_num": 1, "title": "Pilote", "info": {"movie_image": DEAD_HOST_EP}}]
        }
        self.view.current_season = "1"

    def test_collect_known_image_urls_prefers_series_poster(self):
        self._setup_series()

        urls = self.view._collect_known_image_urls()

        self.assertEqual(urls[0], GOOD_HOST_LOGO)     # affiche affichée = domaine de référence
        self.assertIn(DEAD_HOST_BACKDROP, urls)
        self.assertIn(DEAD_HOST_EP, urls)
        self.assertEqual(len(urls), len(set(urls)))   # aucune doublon

    def test_episode_cards_receive_host_candidates(self):
        self._setup_series()

        self.view._populate_episodes_grid()

        cards = [
            self.view.episodes_grid.itemAt(i).widget()
            for i in range(self.view.episodes_grid.count())
            if isinstance(self.view.episodes_grid.itemAt(i).widget(), EpisodeCardWidget)
        ]
        self.assertEqual(len(cards), 1)
        self.assertIn(GOOD_HOST_LOGO, cards[0].host_candidates)
        self.assertEqual(self.loader.last_url, DEAD_HOST_EP)

    def test_failed_episode_thumbnail_switches_host(self):
        self._setup_series()
        self.view._populate_episodes_grid()

        self.assertTrue(any(req["on_failed"] for req in self.loader.requests))
        self.loader.fail_last()
        self.assertEqual(self.loader.last_url, GOOD_HOST_EP)

    def test_backdrop_switches_host_when_domain_is_dead(self):
        self._setup_series()

        self.view._load_backdrop_image(DEAD_HOST_BACKDROP)
        self.assertEqual(self.loader.last_url, DEAD_HOST_BACKDROP)

        self.loader.fail_last()

        self.assertEqual(self.loader.last_url, GOOD_HOST_BACKDROP)
        self.loader.succeed_last()
        self.assertIsNotNone(self.view._backdrop_pixmap)

    def test_backdrop_gives_up_after_one_switch(self):
        self._setup_series()

        self.view._load_backdrop_image(DEAD_HOST_BACKDROP)
        self.loader.fail_last()          # domaine mort
        self.loader.fail_last()          # variante KO -> abandon silencieux

        self.assertEqual(self.loader.requests, [])
        self.assertIsNone(self.view._backdrop_pixmap)


if __name__ == "__main__":
    unittest.main()
