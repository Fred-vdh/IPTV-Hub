"""
Tests automatisés complets pour l'internationalisation (i18n) et le basculement dynamique.
"""

import os
import tempfile
import unittest
from PyQt6.QtWidgets import QApplication

from core.i18n import I18nManager, tr, TRANSLATIONS
from core.models import AppSettings
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


if __name__ == "__main__":
    unittest.main()
