"""
Tests de régression du cache d'icônes (ui/icons.py).

Contexte : QSvgRenderer.render() exécuté PENDANT un paintEvent corrompt la mémoire
(access violation aléatoire, notamment au premier affichage de la grille VOD).
Le correctif rend chaque icône UNE seule fois à la taille de référence
(MASTER_ICON_SIZE) hors paintEvent, puis dérive les autres tailles via
QPixmap.scaled() (opération sûre dans tous les contextes).

Ces tests verrouillent cet invariant : après le pré-chauffage, plus aucun rendu
SVG ne doit avoir lieu, en particulier depuis un paintEvent.

Lancement : python tests/test_icons_pixmap_cache.py
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

import ui.icons as ic  # noqa: E402


# Tailles réellement demandées par l'interface (72 = MASTER_ICON_SIZE).
UI_SIZES = (16, 18, 20, 24, 28, 32, 48, 56, 72)


def _reset_cache():
    """Remet le module ui.icons dans son état initial (cache vide, zéro rendu)."""
    ic._svg_cache.clear()
    ic._master_pixmaps.clear()
    ic._pixmap_cache.clear()
    ic._icon_cache.clear()
    ic._render_count = 0
    ic._prewarm_state = None


class _PaintProbe(QWidget):
    """Widget dont le paintEvent demande des icônes, comme l'UI réelle."""

    def __init__(self, names, colors):
        super().__init__()
        self.names = names
        self.colors = colors
        self.paint_count = 0

    def paintEvent(self, event):  # noqa: N802 (API Qt)
        self.paint_count += 1
        for name in self.names:
            for color in self.colors:
                for size in UI_SIZES:
                    ic.get_pixmap(name, color, size)
                ic.get_icon(name, color=color)


class TestIconPixmapCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        # Les tests valident le comportement par défaut : on neutralise une
        # éventuelle variable d'environnement présente dans le shell appelant
        # (test_07 la pose explicitement pour vérifier la désactivation).
        os.environ.pop("IPTV_NO_ICON_PREWARM", None)
        _reset_cache()
        self.names = ic.iter_icon_names()
        self.assertEqual(
            len(self.names), len(set(self.names)), "noms d'icônes dupliqués"
        )

    def tearDown(self):
        os.environ.pop("IPTV_NO_ICON_PREWARM", None)
        _reset_cache()

    # ------------------------------------------------------------------ #
    # 1. Pré-chauffage
    # ------------------------------------------------------------------ #
    def test_01_prechauffage_rend_un_seul_master_par_motif(self):
        n, dt = ic.prewarm_pixmap_cache()
        stats = ic.pixmap_cache_stats()
        attendu = len(self.names) * len(ic.PRECACHE_COLORS)

        self.assertEqual(n, attendu, "un motif par couple (icône, couleur)")
        self.assertEqual(stats["masters"], attendu)
        self.assertEqual(stats["svg_renders"], attendu, "un seul rendu SVG par master")
        self.assertEqual(stats["pixmaps"], 0, "le pré-chauffage ne crée que les masters")
        self.assertEqual(stats["icons"], 0, "le pré-chauffage ne crée pas de QIcon")
        self.assertGreaterEqual(dt, 0.0)

    def test_02_prechauffage_idempotent(self):
        n, dt = ic.prewarm_pixmap_cache()
        avant = ic.pixmap_cache_stats()["svg_renders"]

        t0 = time.perf_counter()
        self.assertEqual(ic.prewarm_pixmap_cache(), (n, dt))
        self.assertLess(time.perf_counter() - t0, 0.05, "2e appel instantané")
        self.assertEqual(ic.pixmap_cache_stats()["svg_renders"], avant)

    # ------------------------------------------------------------------ #
    # 2. Invariant principal : aucun rendu SVG dans le chemin chaud
    # ------------------------------------------------------------------ #
    def test_03_chemin_chaud_sans_rendu_svg(self):
        ic.prewarm_pixmap_cache()
        avant = ic.pixmap_cache_stats()["svg_renders"]

        for name in self.names:
            for color in ic.PRECACHE_COLORS:
                pm = ic.get_pixmap(name, color, 24)
                self.assertFalse(pm.isNull(), f"pixmap nul pour {name}/{color}")
                ic.get_icon(name, color=color)
                ic.get_icon(name, color=color, active_color="#ffffff")

        self.assertEqual(
            ic.pixmap_cache_stats()["svg_renders"],
            avant,
            "aucun rendu SVG ne doit avoir lieu après le pré-chauffage",
        )

    def test_04_tailles_derivees_par_mise_a_l_echelle(self):
        ic.prewarm_pixmap_cache()
        avant = ic.pixmap_cache_stats()["svg_renders"]

        for size in UI_SIZES:
            pm = ic.get_pixmap("play_arrow", "#ffffff", size)
            self.assertEqual(
                (pm.width(), pm.height()), (size, size), f"taille {size}px incorrecte"
            )
            img = pm.toImage()
            opaques = sum(
                1
                for y in range(img.height())
                for x in range(img.width())
                if img.pixelColor(x, y).alpha() > 20
            )
            self.assertGreater(opaques, size, f"icône {size}px vide")

        self.assertEqual(
            ic.pixmap_cache_stats()["svg_renders"],
            avant,
            "les tailles dérivées ne doivent pas re-rendre le SVG",
        )

    def test_05_couleur_hors_palette_rendue_une_seule_fois(self):
        ic.prewarm_pixmap_cache()
        avant = ic.pixmap_cache_stats()["svg_renders"]

        pm = ic.get_pixmap("search", "#ab12cd", 32)
        self.assertFalse(pm.isNull())
        self.assertEqual(ic.pixmap_cache_stats()["svg_renders"], avant + 1)

        self.assertEqual(ic.get_pixmap("search", "#ab12cd", 24).width(), 24)
        self.assertEqual(
            ic.pixmap_cache_stats()["svg_renders"],
            avant + 1,
            "une nouvelle taille réutilise le master de cette couleur",
        )

    # ------------------------------------------------------------------ #
    # 3. Le pixmap de référence n'est jamais exposé
    # ------------------------------------------------------------------ #
    def test_06_master_jamais_expose(self):
        master = ic.get_master_pixmap("search", "#ab12cd")
        expose = ic.get_pixmap("search", "#ab12cd", ic.MASTER_ICON_SIZE)

        self.assertIsNot(expose, master, "get_pixmap doit renvoyer une copie")
        self.assertEqual(
            (expose.width(), expose.height()),
            (ic.MASTER_ICON_SIZE, ic.MASTER_ICON_SIZE),
        )

        # Décorer le pixmap renvoyé ne doit jamais contaminer le master :
        # une icône dérivée avant la modification doit rester intacte.
        derivee = ic.get_pixmap("search", "#ab12cd", 24)
        expose.fill(Qt.GlobalColor.magenta)

        img = derivee.toImage()
        magenta = sum(
            1
            for y in range(img.height())
            for x in range(img.width())
            if img.pixelColor(x, y).alpha() > 200
            and img.pixelColor(x, y).red() > 200
            and img.pixelColor(x, y).blue() > 200
            and img.pixelColor(x, y).green() < 60
        )
        self.assertLess(
            magenta,
            24 * 24,
            "le pixmap renvoyé ne doit pas partager la mémoire du master",
        )

    # ------------------------------------------------------------------ #
    # 4. Désactivation / repli paresseux
    # ------------------------------------------------------------------ #
    def test_07_desactivation_par_variable_environnement(self):
        os.environ["IPTV_NO_ICON_PREWARM"] = "1"
        _reset_cache()

        self.assertEqual(ic.prewarm_pixmap_cache(), (0, 0.0))
        self.assertEqual(ic.pixmap_cache_stats()["svg_renders"], 0)

        # Le rendu paresseux (hors paintEvent) reste fonctionnel.
        self.assertFalse(ic.get_pixmap("delete_outline", "#ab12cd", 24).isNull())
        self.assertEqual(ic.pixmap_cache_stats()["svg_renders"], 1)

        self.assertEqual(ic.get_pixmap("delete_outline", "#ab12cd", 48).width(), 48)
        self.assertEqual(
            ic.pixmap_cache_stats()["svg_renders"],
            1,
            "les autres tailles restent dérivées du master",
        )

    # ------------------------------------------------------------------ #
    # 5. Bout en bout : un paintEvent ne doit déclencher aucun rendu
    # ------------------------------------------------------------------ #
    def test_08_paint_event_sans_rendu_svg(self):
        ic.prewarm_pixmap_cache()
        avant = ic.pixmap_cache_stats()["svg_renders"]

        sonde = _PaintProbe(self.names, (ic.DEFAULT_ICON_COLOR, "#94a3b8"))
        sonde.resize(320, 240)
        cible = QPixmap(320, 240)
        cible.fill(Qt.GlobalColor.transparent)
        sonde.render(cible)

        self.assertGreater(sonde.paint_count, 0, "le paintEvent doit s'être exécuté")
        self.assertEqual(
            ic.pixmap_cache_stats()["svg_renders"],
            avant,
            "aucun rendu SVG ne doit avoir lieu pendant un paintEvent",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
