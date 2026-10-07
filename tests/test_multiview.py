import sys
import os
import unittest
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtTest import QTest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.models import Channel, AppSettings, EPGProgram
from ui.widgets.multiview_widget import MultiViewWidget, MultiViewSlotWidget


class _FakePlayer:
    """Lecteur minimal simulant un lecteur libmpv (aucun appel natif)."""

    def __init__(self, failing: bool = False):
        self.failing = failing
        self.stop_calls = 0
        self.cleanup_calls = 0
        self.mute = None
        self.played_url = None

    def stop(self):
        self.stop_calls += 1
        if self.failing:
            raise RuntimeError("mpv figé (simulation)")

    def set_mute(self, value):
        self.mute = value
        if self.failing:
            raise RuntimeError("mpv figé (simulation)")

    def play(self, stream_url):
        self.played_url = stream_url
        if self.failing:
            raise RuntimeError("mpv figé (simulation)")

    def cleanup(self):
        self.cleanup_calls += 1
        if self.failing:
            raise RuntimeError("mpv figé (simulation)")


class TestMultiView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.db = Database(self.db_path)
        self.settings = AppSettings()

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_multiview_initialization_and_slots(self):
        mv = MultiViewWidget(self.db, self.settings)
        self.assertEqual(len(mv.slots), 4)
        self.assertEqual(mv.layout_mode, "1x2")

        # In 1x2 mode, slot 0 and slot 1 are visible, 2 and 3 hidden
        self.assertFalse(mv.slots[0].isHidden())
        self.assertFalse(mv.slots[1].isHidden())
        self.assertTrue(mv.slots[2].isHidden())
        self.assertTrue(mv.slots[3].isHidden())

        mv.stop_all()

    def test_layout_mode_changes(self):
        mv = MultiViewWidget(self.db, self.settings)

        mv.set_layout_mode("2x2")
        self.assertEqual(mv.layout_mode, "2x2")
        for s in mv.slots:
            self.assertFalse(s.isHidden())

        mv.set_layout_mode("1+2")
        self.assertEqual(mv.layout_mode, "1+2")
        self.assertFalse(mv.slots[0].isHidden())
        self.assertFalse(mv.slots[1].isHidden())
        self.assertFalse(mv.slots[2].isHidden())
        self.assertTrue(mv.slots[3].isHidden())

        mv.stop_all()

    def test_slot_focus_and_audio_toggle(self):
        mv = MultiViewWidget(self.db, self.settings)
        mv.start_multiview(None)

        # Slot 0 has initial audio focus
        self.assertTrue(mv.slots[0].is_active_audio)
        self.assertFalse(mv.slots[1].is_active_audio)

        # Switch focus to Slot 1
        mv._on_slot_focused(1)
        self.assertEqual(mv.active_slot_idx, 1)
        self.assertFalse(mv.slots[0].is_active_audio)
        self.assertTrue(mv.slots[1].is_active_audio)

        mv.stop_all()

    def test_fullscreen_ui_sync(self):
        mv = MultiViewWidget(self.db, self.settings)
        mv.set_fullscreen_ui(True)
        self.assertIn("Quitter", mv.fs_btn.text())

        mv.set_fullscreen_ui(False)
        self.assertIn("Plein écran", mv.fs_btn.text())

        mv.stop_all()

    # ------------------------------------------------ sortie du Multiview

    @staticmethod
    def _fake_channel(name: str = "TF1 HD", sid: str = "101", group: str = "FR | TNT") -> Channel:
        return Channel(
            playlist_id=1,
            name=name,
            stream_url=f"http://example.com/live/{sid}.m3u8",
            stream_id=sid,
            group_title=group,
            stream_type="live",
        )

    def test_deactivate_resets_all_screens_and_players(self):
        """deactivate() doit vider TOUS les écrans : seul l'écran de base subsiste."""
        mv = MultiViewWidget(self.db, self.settings)
        mv.start_multiview(None)
        self.assertTrue(mv.is_active)

        fake = _FakePlayer()
        mv.slots[0].player = fake
        mv.slots[0].channel = self._fake_channel()
        mv.slots[0].title_lbl.setText("TF1 HD")
        mv.slots[0].stack.setCurrentIndex(1)
        mv.active_slot_idx = 0

        mv.deactivate(staggered=False)

        self.assertFalse(mv.is_active)
        self.assertEqual(mv.active_slot_idx, 0)
        self.assertIsNone(mv.slots[0].player)
        self.assertEqual(fake.cleanup_calls, 1)
        for slot in mv.slots:
            self.assertIsNone(slot.channel)
            self.assertEqual(slot.stack.currentIndex(), 0)
            self.assertEqual(slot.title_lbl.text(), "")
            self.assertFalse(slot.is_active_audio)
        self.assertFalse(mv.has_running_slots())

    def test_exit_button_always_emits_and_resets_screens(self):
        """Un clic sur « Quitter Multiview » signale la sortie ET vide les écrans."""
        mv = MultiViewWidget(self.db, self.settings)
        mv.start_multiview(None)
        ch = self._fake_channel()
        mv.slots[1].player = _FakePlayer()
        mv.slots[1].channel = ch
        mv.active_slot_idx = 1
        received = []
        mv.exit_requested.connect(received.append)

        mv._on_exit_clicked()

        self.assertEqual(received, [ch])
        self.assertFalse(mv.is_active)
        self.assertIsNone(mv.slots[1].channel)
        self.assertEqual(mv.slots[1].stack.currentIndex(), 0)
        mv.stop_all()

    def test_exit_survives_a_wedged_mpv_core(self):
        """Un lecteur libmpv bloqué/planté ne doit jamais empêcher la sortie."""
        mv = MultiViewWidget(self.db, self.settings)
        mv.start_multiview(None)
        mv.slots[0].player = _FakePlayer(failing=True)
        mv.slots[0].channel = self._fake_channel()
        received = []
        mv.exit_requested.connect(received.append)

        mv._on_exit_clicked()          # ne doit lever aucune exception

        self.assertEqual(len(received), 1)
        self.assertFalse(mv.is_active)
        self.assertIsNone(mv.slots[0].channel)
        # La destruction différée ne doit pas lever non plus.
        mv._teardown_next()
        mv.stop_all()

    def test_deferred_teardown_completes_on_event_loop(self):
        """Le cœur libmpv est détruit par la boucle d'événements, pas dans le clic."""
        mv = MultiViewWidget(self.db, self.settings)
        mv.start_multiview(None)
        fake = _FakePlayer()
        mv.slots[0].player = fake
        mv.slots[0].channel = self._fake_channel()

        mv.deactivate(staggered=True)

        # Immédiatement après l'appel : écran remis à zéro, lecteur encore vivant
        # (aucune opération lente n'est exécutée dans le gestionnaire de clic).
        self.assertIsNone(mv.slots[0].channel)
        self.assertIs(mv.slots[0].player, fake)
        self.assertEqual(fake.cleanup_calls, 0)

        for _ in range(10):
            self.app.processEvents()
            QTest.qWait(10)

        self.assertIsNone(mv.slots[0].player)
        self.assertEqual(fake.cleanup_calls, 1)

    def test_layout_switch_keeps_interface_responsive(self):
        """Changer de disposition ferme les écrans masqués sans bloquer l'interface."""
        mv = MultiViewWidget(self.db, self.settings)
        mv.start_multiview(None)
        mv.set_layout_mode("2x2")
        fake = _FakePlayer()
        mv.slots[3].player = fake
        mv.slots[3].channel = self._fake_channel(name="Canal+", sid="301")

        mv.set_layout_mode("1x2")

        self.assertEqual(mv.layout_mode, "1x2")
        self.assertTrue(mv.slots[2].isHidden())
        self.assertTrue(mv.slots[3].isHidden())
        self.assertIsNone(mv.slots[3].channel)
        # La disposition mémorisée est conservée pour le prochain passage en Multiview
        mv.start_multiview(None)
        self.assertEqual(mv.layout_mode, "1x2")
        self.assertTrue(mv.is_active)
        mv.stop_all()


    # ------------------------------------------------ bandeau OSD des écrans

    def test_banner_mirrors_the_solo_player_osd(self):
        """Le bandeau de chaque écran reprend les codes visuels de l'OSD du lecteur solo."""
        slot = MultiViewSlotWidget(0, self.db, self.settings)
        self.assertEqual(slot.top_bar.height(), MultiViewSlotWidget.BANNER_HEIGHT)
        # Nom de la chaîne + programme, aux mêmes tailles que l'OSD solo.
        self.assertIn("font-size: 15px", slot.title_lbl.styleSheet())
        self.assertIn("font-size: 13px", slot.epg_info_lbl.styleSheet())
        self.assertEqual(slot.badge_live.text(), "DIRECT")
        self.assertIn("#ef4444", slot.badge_live.styleSheet())
        # Deux icônes d'action : changer / supprimer la chaîne de l'écran.
        self.assertFalse(slot.change_btn.icon().isNull())
        self.assertFalse(slot.delete_btn.icon().isNull())
        self.assertIn("Changer", slot.change_btn.toolTip())
        self.assertIn("Supprimer", slot.delete_btn.toolTip())
        # Masqué tant qu'aucune chaîne n'occupe l'écran.
        self.assertTrue(slot.top_bar.isHidden())

    def test_banner_never_exceeds_the_screen_width(self):
        """Le bandeau tient toujours dans la largeur attribuée à la diffusion."""
        mv = MultiViewWidget(self.db, self.settings)
        mv.resize(1200, 700)
        mv.show()
        self.app.processEvents()

        for slot in mv.slots:
            slot._sync_banner_geometry()
            self.assertGreater(slot.top_bar.width(), 0)
            self.assertLessEqual(slot.top_bar.width(), slot.video_container.width())
            self.assertLess(slot.top_bar.geometry().right(), slot.video_container.width())

        mv.stop_all()
        mv.hide()

    def test_banner_elides_a_very_long_channel_name(self):
        """Un nom de chaîne très long est tronqué au lieu de déborder de l'écran."""
        mv = MultiViewWidget(self.db, self.settings)
        mv.resize(1000, 600)
        mv.show()
        self.app.processEvents()

        slot = mv.slots[0]
        long_name = "Chaine " + "Tres Longue " * 12
        slot._raw_channel_title = long_name
        slot._raw_epg_info = ""
        slot._sync_banner_geometry()

        text = slot.title_lbl.text()
        self.assertLess(len(text), len(long_name))
        self.assertTrue(text.endswith("…"))
        fm = QFontMetrics(slot.title_lbl.font())
        self.assertLessEqual(fm.horizontalAdvance(text), slot.top_bar.width())

        mv.stop_all()
        mv.hide()

    def test_banner_hides_the_program_when_the_screen_is_narrow(self):
        """Sur un écran très étroit, le titre reste et le programme laisse la place."""
        slot = MultiViewSlotWidget(0, self.db, self.settings)
        slot._raw_channel_title = "TF1 HD"
        slot._raw_epg_info = "—  Le Journal de 20h"
        slot.top_bar.setGeometry(0, 0, 200, MultiViewSlotWidget.BANNER_HEIGHT)
        slot._update_banner_elision()
        self.assertTrue(slot.title_lbl.text())
        self.assertTrue(slot.epg_info_lbl.isHidden())

    def test_banner_shows_the_current_program_and_resets_on_close(self):
        """Le programme en cours (EPG) s'affiche et le bandeau suit la vie de l'écran."""
        slot = MultiViewSlotWidget(
            0, self.db, self.settings,
            epg_provider=lambda tvg_id: EPGProgram(tvg_id=tvg_id, title="Le Journal de 20h"),
        )
        slot.player = _FakePlayer()
        channel = self._fake_channel()
        channel.tvg_id = "TF1.fr"

        slot.set_channel(channel)

        self.assertEqual(slot.stack.currentIndex(), 1)
        self.assertFalse(slot.top_bar.isHidden())
        self.assertEqual(slot.badge_live.text(), "DIRECT")
        self.assertEqual(slot.title_lbl.text(), "TF1 HD")
        self.assertIn("Le Journal de 20h", slot.epg_info_lbl.text())
        self.assertIn("Le Journal de 20h", slot.epg_info_lbl.toolTip())
        # Le programme est rafraîchi périodiquement (changement d'émission).
        self.assertIsNotNone(slot._epg_timer)
        self.assertTrue(slot._epg_timer.isActive())

        slot.close_slot()

        self.assertTrue(slot.top_bar.isHidden())
        self.assertFalse(slot._epg_timer.isActive())
        self.assertEqual(slot.title_lbl.text(), "")

    def test_banner_falls_back_to_the_group_without_epg(self):
        """Sans programme EPG, le groupe de la chaîne sert de sous-titre."""
        slot = MultiViewSlotWidget(0, self.db, self.settings)
        self.assertIn("FR | TNT", slot._epg_text_for(self._fake_channel()))

    def test_banner_tolerates_an_epg_failure(self):
        """Une erreur du fournisseur EPG ne doit jamais casser le bandeau."""
        def boom(tvg_id):
            raise RuntimeError("EPG indisponible")

        slot = MultiViewSlotWidget(0, self.db, self.settings, epg_provider=boom)
        channel = self._fake_channel(group="Sport")
        channel.tvg_id = "beIN.fr"
        self.assertIn("Sport", slot._epg_text_for(channel))

    def test_banner_badge_follows_the_stream_type(self):
        """Le badge reprend les libellés/couleurs de l'OSD solo selon le type de flux."""
        slot = MultiViewSlotWidget(0, self.db, self.settings)

        slot._update_banner_badge("live")
        self.assertEqual(slot.badge_live.text(), "DIRECT")
        self.assertIn("#ef4444", slot.badge_live.styleSheet())

        slot._update_banner_badge("replay")
        self.assertEqual(slot.badge_live.text(), "REPLAY")
        self.assertIn("#818cf8", slot.badge_live.styleSheet())

        slot._update_banner_badge("inconnu")
        self.assertEqual(slot.badge_live.text(), "VOD")

    def test_multiview_provides_the_epg_to_each_screen(self):
        """Le fournisseur EPG de la fenêtre principale est transmis à chaque écran."""
        asked = []

        def provider(tvg_id):
            asked.append(tvg_id)
            return None

        mv = MultiViewWidget(self.db, self.settings, epg_provider=provider)
        for slot in mv.slots:
            self.assertIs(slot.epg_provider, mv.epg_provider)

        channel = self._fake_channel()
        channel.tvg_id = "TF1.fr"
        mv.slots[2].player = _FakePlayer()
        mv.slots[2].set_channel(channel)

        self.assertEqual(asked, ["TF1.fr"])
        mv.stop_all()

if __name__ == "__main__":
    unittest.main()
