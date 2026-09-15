"""
Tests automatisés complets pour l'internationalisation (i18n) et le basculement dynamique.
"""

import os
import tempfile
import unittest
from PyQt6.QtWidgets import QApplication

from core.i18n import I18nManager, tr, TRANSLATIONS
from core.database import Database


class TestI18n(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.i18n = I18nManager.instance()
        self.i18n.set_language("fr")

    def tearDown(self):
        self.i18n.set_language("fr")

    def test_translations_dict_structure(self):
        """Vérifie que chaque entrée de TRANSLATIONS possède une traduction 'fr' et 'en' valide."""
        for key, val in TRANSLATIONS.items():
            self.assertIsInstance(val, dict, f"La valeur pour '{key}' doit être un dictionnaire.")
            self.assertIn("fr", val, f"La clé '{key}' n'a pas de traduction en français.")
            self.assertIn("en", val, f"La clé '{key}' n'a pas de traduction en anglais.")
            self.assertTrue(bool(val["fr"].strip()), f"Traduction 'fr' vide pour '{key}'")
            self.assertTrue(bool(val["en"].strip()), f"Traduction 'en' vide pour '{key}'")

    def test_tr_function_french_and_english(self):
        """Vérifie la fonction tr() en français et en anglais."""
        self.i18n.set_language("fr")
        self.assertEqual(tr("Tableau de bord"), "Tableau de bord")
        self.assertEqual(tr("Paramètres"), "Paramètres")
        self.assertEqual(tr("TV en direct"), "TV en direct")

        self.i18n.set_language("en")
        self.assertEqual(tr("Tableau de bord"), "Dashboard")
        self.assertEqual(tr("Paramètres"), "Settings")
        self.assertEqual(tr("TV en direct"), "Live TV")

    def test_tr_fallback_for_unknown_key(self):
        """Vérifie que tr() retourne la clé d'origine sans planter pour un texte inconnu."""
        unknown_text = "Chaîne inconnue test_12345"
        self.i18n.set_language("en")
        self.assertEqual(tr(unknown_text), unknown_text)
        self.i18n.set_language("fr")
        self.assertEqual(tr(unknown_text), unknown_text)

    def test_tr_with_formatting_kwargs(self):
        """Vérifie le formatage dynamique {arg}."""
        self.i18n.set_language("fr")
        fr_res = tr("Page {current} sur {total}", current=2, total=5)
        self.assertEqual(fr_res, "Page 2 sur 5")

        self.i18n.set_language("en")
        en_res = tr("Page {current} sur {total}", current=2, total=5)
        self.assertEqual(en_res, "Page 2 of 5")

    def test_signal_language_changed_emitted(self):
        """Vérifie que le signal Qt language_changed est bien émis lors d'un changement de langue."""
        received = []
        self.i18n.language_changed.connect(lambda lang: received.append(lang))

        self.i18n.set_language("en")
        self.assertEqual(received, ["en"])

        # Même langue : ne doit pas réémettre
        self.i18n.set_language("en")
        self.assertEqual(received, ["en"])

        # Revenir en français
        self.i18n.set_language("fr")
        self.assertEqual(received, ["en", "fr"])

    def test_database_settings_app_language_persistence(self):
        """Vérifie que app_language est correctement sauvegardé et rechargé depuis SQLite."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db_path = f.name

        try:
            db = Database(temp_db_path)
            # Paramètres par défaut : fr
            settings = db.get_settings()
            self.assertEqual(settings.app_language, "fr")

            # Modification en anglais
            settings.app_language = "en"
            db.save_settings(settings)

            # Rechargement
            loaded_settings = db.get_settings()
            self.assertEqual(loaded_settings.app_language, "en")

            # Remise en français
            loaded_settings.app_language = "fr"
            db.save_settings(loaded_settings)
            reloaded = db.get_settings()
            self.assertEqual(reloaded.app_language, "fr")
        finally:
            if os.path.exists(temp_db_path):
                try:
                    os.unlink(temp_db_path)
                except Exception:
                    pass

    def test_new_translations_hero_and_cards(self):
        """Vérifie la traduction des éléments du bandeau hero, des cartes et de la barre de titre."""
        self.i18n.set_language("fr")
        self.assertEqual(tr("Liste :"), "Liste :")
        self.assertEqual(tr("Ma liste de lecture"), "Ma liste de lecture")
        self.assertEqual(tr("ma liste de lecture"), "ma liste de lecture")
        self.assertEqual(tr("Film"), "Film")
        self.assertEqual(tr("Série"), "Série")
        self.assertEqual(tr("Reprendre l'épisode"), "Reprendre l'épisode")
        self.assertEqual(tr("Il reste {mins} min", mins=34), "Il reste 34 min")
        self.assertEqual(tr("{pct}% regardé", pct=29), "29 % regardé")

        self.i18n.set_language("en")
        self.assertEqual(tr("Liste :"), "Playlist:")
        self.assertEqual(tr("Ma liste de lecture"), "My playlist")
        self.assertEqual(tr("ma liste de lecture"), "my playlist")
        self.assertEqual(tr("Film"), "Movie")
        self.assertEqual(tr("Série"), "Series")
        self.assertEqual(tr("Reprendre l'épisode"), "Resume episode")
        self.assertEqual(tr("Il reste {mins} min", mins=34), "34 min left")
        self.assertEqual(tr("{pct}% regardé", pct=29), "29% watched")
        self.assertEqual(tr("Reprendre la lecture"), "Continue Watching")
        self.assertEqual(tr("TV en direct récemment regardée"), "Recently watched live TV")
        self.assertEqual(tr("Films & Séries favoris"), "Favorite movies & series")

    def test_format_locale_date(self):
        """Vérifie le formatage localisé des dates (FR / EN)."""
        from datetime import datetime
        from core.i18n import format_locale_date
        test_dt = datetime(2026, 9, 14, 22, 30)

        self.i18n.set_language("fr")
        self.assertEqual(format_locale_date(test_dt, "short"), "14/09/2026")
        self.assertEqual(format_locale_date(test_dt, "friendly"), "14 sept., 22:30")

        self.i18n.set_language("en")
        self.assertEqual(format_locale_date(test_dt, "short"), "09/14/2026")
        self.assertEqual(format_locale_date(test_dt, "friendly"), "Sep 14, 22:30")

    def test_widgets_hot_retranslation(self):
        """Vérifie que les composants graphiques se mettent à jour automatiquement lors d'un changement de langue."""
        from ui.widgets.custom_titlebar import CustomTitleBar
        from ui.widgets.favorites_view import FavoritesView
        from ui.widgets.recently_watched_view import RecentlyWatchedView
        from ui.widgets.dashboard_view import DashboardView

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        try:
            db = Database(temp_db)

            # 1. CustomTitleBar
            self.i18n.set_language("fr")
            tb = CustomTitleBar()
            self.assertEqual(tb.pl_label.text(), "Liste :")
            self.i18n.set_language("en")
            self.assertEqual(tb.pl_label.text(), "Playlist:")

            # 2. FavoritesView
            self.i18n.set_language("fr")
            fav = FavoritesView(db)
            self.assertEqual(fav.title_label.text(), "Favoris")
            self.assertEqual(fav.btn_movies.text(), "Films")
            self.assertEqual(fav.btn_series.text(), "Séries")
            self.assertEqual(fav.btn_live.text(), "TV en direct")
            self.assertIn("Cette liste de lecture", fav.btn_this_playlist.text())
            self.assertIn("Toutes les listes de lecture", fav.btn_all_playlists.text())

            self.i18n.set_language("en")
            self.assertEqual(fav.title_label.text(), "Favorites")
            self.assertEqual(fav.btn_movies.text(), "Movies")
            self.assertEqual(fav.btn_series.text(), "Series")
            self.assertEqual(fav.btn_live.text(), "Live TV")
            self.assertIn("This playlist", fav.btn_this_playlist.text())
            self.assertIn("All playlists", fav.btn_all_playlists.text())

            # 3. RecentlyWatchedView
            self.i18n.set_language("fr")
            hist = RecentlyWatchedView(db)
            self.assertEqual(hist.title_label.text(), "Récemment regardés")
            self.assertEqual(hist.btn_all.text(), "Tous")
            self.assertEqual(hist.btn_movies.text(), "Films")
            self.assertEqual(hist.btn_series.text(), "Séries")
            self.assertEqual(hist.btn_live.text(), "TV en direct")
            self.assertIn("Cette liste de lecture", hist.btn_this_playlist.text())
            self.assertIn("Toutes les listes de lecture", hist.btn_all_playlists.text())

            self.i18n.set_language("en")
            self.assertEqual(hist.title_label.text(), "Recently Watched")
            self.assertEqual(hist.btn_all.text(), "All")
            self.assertEqual(hist.btn_movies.text(), "Movies")
            self.assertEqual(hist.btn_series.text(), "Series")
            self.assertEqual(hist.btn_live.text(), "Live TV")
            self.assertIn("This playlist", hist.btn_this_playlist.text())
            self.assertIn("All playlists", hist.btn_all_playlists.text())

            # 4. DashboardView
            self.i18n.set_language("fr")
            dash = DashboardView(db)
            dash.refresh_view()
            self.assertEqual(dash.sec_continue.title_label.text(), "Reprendre la lecture")
            self.assertEqual(dash.sec_recent_live.title_label.text(), "TV en direct récemment regardée")
            self.assertEqual(dash.sec_favs.title_label.text(), "Films & Séries favoris")
            self.assertEqual(dash.sec_recents.title_label.text(), "Récemment ajoutés sur la liste")

            self.i18n.set_language("en")
            self.assertEqual(dash.sec_continue.title_label.text(), "Continue Watching")
            self.assertEqual(dash.sec_recent_live.title_label.text(), "Recently watched live TV")
            self.assertEqual(dash.sec_favs.title_label.text(), "Favorite movies & series")
            self.assertEqual(dash.sec_recents.title_label.text(), "Recently added on the playlist")
        finally:
            self.i18n.set_language("fr")
            if os.path.exists(temp_db):
                try:
                    os.unlink(temp_db)
                except Exception:
                    pass

    def test_epg_and_episode_translations(self):
        """Vérifie la traduction dynamique des épisodes, du bouton voir tout et d'EPGGridView."""
        from ui.widgets.epg_grid_view import EPGGridView
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        try:
            db = Database(temp_db)

            # Test des clés formatées
            self.i18n.set_language("fr")
            self.assertEqual(tr("Voir les {count} >", count=30), "Voir les 30 >")
            self.assertEqual(tr("Épisode {num}", num=12), "Épisode 12")
            self.assertEqual(tr("Guide des programmes EPG"), "Guide des programmes EPG")
            self.assertEqual(tr("Aller à maintenant"), "Aller à maintenant")
            self.assertEqual(tr("Regarder la chaîne"), "Regarder la chaîne")

            self.i18n.set_language("en")
            self.assertEqual(tr("Voir les {count} >", count=30), "See all 30 >")
            self.assertEqual(tr("Épisode {num}", num=12), "Episode 12")
            self.assertEqual(tr("Guide des programmes EPG"), "TV Guide EPG")
            self.assertEqual(tr("Aller à maintenant"), "Go to Now")
            self.assertEqual(tr("Regarder la chaîne"), "Watch channel")

            # Test du widget EPGGridView
            self.i18n.set_language("fr")
            epg = EPGGridView(db)
            self.assertEqual(epg.title_lbl.text(), "Guide des programmes EPG")
            self.assertIn("Aller à maintenant", epg.now_btn.text())
            self.assertIn("Regarder la chaîne", epg.hero_card.play_btn.text())

            self.i18n.set_language("en")
            self.assertEqual(epg.title_lbl.text(), "TV Guide EPG")
            self.assertIn("Go to Now", epg.now_btn.text())
            self.assertIn("Watch channel", epg.hero_card.play_btn.text())

        finally:
            self.i18n.set_language("fr")
            if os.path.exists(temp_db):
                try:
                    os.unlink(temp_db)
                except Exception:
                    pass

    def test_vod_sort_settings_and_expiration_translations(self):
        """Vérifie la traduction du tri Films/Séries, de la date d'expiration et des paramètres."""
        from ui.widgets.vod_grid import VODGridView
        from ui.widgets.settings_view import SettingsView
        from ui.dialogs.manage_playlists_dialog import _format_exp_date

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        try:
            db = Database(temp_db)

            # 1. Date d'expiration
            future_ts = 1790000000  # un timestamp futur
            self.i18n.set_language("fr")
            exp_fr = _format_exp_date(str(future_ts))
            self.i18n.set_language("en")
            exp_en = _format_exp_date(str(future_ts))
            self.assertIn("restants", exp_fr)
            self.assertIn("remaining", exp_en)

            # 2. Clés des paramètres
            self.i18n.set_language("fr")
            self.assertEqual(tr("Reprendre automatiquement la dernière chaîne au lancement"), "Reprendre automatiquement la dernière chaîne au lancement")
            self.assertEqual(tr("Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)"), "Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)")
            self.assertEqual(tr("Reconnexion automatique en cas de coupure de flux"), "Reconnexion automatique en cas de coupure de flux")
            self.assertEqual(tr("Vider le cache des logos de chaînes"), "Vider le cache des logos de chaînes")
            self.assertEqual(tr("Enregistrer la configuration sous..."), "Enregistrer la configuration sous...")
            self.assertEqual(tr("Charger un fichier de configuration..."), "Charger un fichier de configuration...")
            self.assertEqual(tr("auto (Recommandé)"), "auto (Recommandé)")
            self.assertEqual(tr("Trier : Date d'ajout (plus récents...)"), "Trier : Date d'ajout (plus récents...)")

            self.i18n.set_language("en")
            self.assertEqual(tr("Reprendre automatiquement la dernière chaîne au lancement"), "Automatically resume last channel on startup")
            self.assertEqual(tr("Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)"), "Automatically play next episode when current episode finishes (Series)")
            self.assertEqual(tr("Reconnexion automatique en cas de coupure de flux"), "Automatic reconnection if stream drops")
            self.assertEqual(tr("Vider le cache des logos de chaînes"), "Clear channel logo cache")
            self.assertEqual(tr("Enregistrer la configuration sous..."), "Save configuration as...")
            self.assertEqual(tr("Charger un fichier de configuration..."), "Load configuration file...")
            self.assertEqual(tr("auto (Recommandé)"), "auto (Recommended)")
            self.assertEqual(tr("Trier : Date d'ajout (plus récents...)"), "Sort: Date added (Newest first)")

            # 3. Widgets VODGridView & SettingsView
            self.i18n.set_language("fr")
            vod = VODGridView(db, stream_type="movie")
            self.assertEqual(vod.category_title_label.text(), "TOUS LES FILMS")
            self.assertIn("film", vod.items_count_label.text().lower())
            self.assertIn("Trier", vod.sort_combo.itemText(0))

            settings_view = SettingsView(db)
            self.assertEqual(settings_view.auto_resume_cb.text().strip(), "Reprendre automatiquement la dernière chaîne au lancement")
            self.assertEqual(settings_view.auto_reconnect_cb.text().strip(), "Reconnexion automatique en cas de coupure de flux")
            self.assertEqual(settings_view.clear_cache_btn.text().strip(), "Vider le cache des logos de chaînes")
            self.assertEqual(settings_view.btn_export_config.text().strip(), "Enregistrer la configuration sous...")
            self.assertEqual(settings_view.btn_import_config.text().strip(), "Charger un fichier de configuration...")

            # Basculement en anglais
            self.i18n.set_language("en")
            self.assertEqual(vod.category_title_label.text(), "ALL MOVIES")
            self.assertIn("movie", vod.items_count_label.text().lower())
            self.assertIn("Sort", vod.sort_combo.itemText(0))

            self.assertEqual(settings_view.auto_resume_cb.text().strip(), "Automatically resume last channel on startup")
            self.assertEqual(settings_view.auto_reconnect_cb.text().strip(), "Automatic reconnection if stream drops")
            self.assertEqual(settings_view.clear_cache_btn.text().strip(), "Clear channel logo cache")
            self.assertEqual(settings_view.btn_export_config.text().strip(), "Save configuration as...")
            self.assertEqual(settings_view.btn_import_config.text().strip(), "Load configuration file...")

        finally:
            self.i18n.set_language("fr")
            if os.path.exists(temp_db):
                try:
                    os.unlink(temp_db)
                except Exception:
                    pass

    def test_epg_combo_channel_search_and_settings_switch_to_fr(self):
        """Vérifie la traduction de 'Toutes les chaînes', 'Rechercher dans cette catégorie...' et le retour sans crash à FR."""
        from ui.widgets.epg_grid_view import EPGGridView
        from ui.widgets.channel_list import ChannelListPanel
        from ui.widgets.epg_timeline import EPGTimelinePanel

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        try:
            db = Database(temp_db)

            # Clés pures
            self.i18n.set_language("fr")
            self.assertEqual(tr("Toutes les chaînes"), "Toutes les chaînes")
            self.assertEqual(tr("Rechercher dans cette catégorie..."), "Rechercher dans cette catégorie...")

            self.i18n.set_language("en")
            self.assertEqual(tr("Toutes les chaînes"), "All channels")
            self.assertEqual(tr("Rechercher dans cette catégorie..."), "Search in this category...")

            # Widgets
            self.i18n.set_language("fr")
            epg_grid = EPGGridView(db)
            ch_list = ChannelListPanel(db)
            timeline = EPGTimelinePanel(db)

            self.assertEqual(epg_grid.cat_combo.itemText(0), "Toutes les chaînes")
            self.assertEqual(ch_list.search_input.placeholderText(), "Rechercher dans cette catégorie...")
            self.assertEqual(timeline.channel_title_label.text(), "Guide des programmes")

            # Basculement vers EN
            self.i18n.set_language("en")
            self.assertEqual(epg_grid.cat_combo.itemText(0), "All channels")
            self.assertEqual(ch_list.search_input.placeholderText(), "Search in this category...")
            self.assertEqual(timeline.channel_title_label.text(), "TV Guide")

            # Retour vers FR (test du correctif de non-crash dans EPGTimelinePanel)
            self.i18n.set_language("fr")
            self.assertEqual(epg_grid.cat_combo.itemText(0), "Toutes les chaînes")
            self.assertEqual(ch_list.search_input.placeholderText(), "Rechercher dans cette catégorie...")
            self.assertEqual(timeline.channel_title_label.text(), "Guide des programmes")

        finally:
            self.i18n.set_language("fr")
            if os.path.exists(temp_db):
                try:
                    os.unlink(temp_db)
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()


