"""
Tests unitaires pour ThemedInputDialog.
"""

import unittest
from PyQt6.QtWidgets import QApplication

from ui.dialogs.themed_input_dialog import ThemedInputDialog


class TestThemedInputDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def test_dialog_init_and_value(self):
        dlg = ThemedInputDialog(
            title="Nouvelle liste",
            label="Nom de la liste :",
            text="Salon HD",
            placeholder="ex: Salon HD",
            icon_name="playlist_add"
        )
        self.assertEqual(dlg.get_value(), "Salon HD")
        self.assertTrue(dlg.btn_ok.isEnabled())

        dlg.input_edit.setText("")
        self.assertEqual(dlg.get_value(), "")
        self.assertFalse(dlg.btn_ok.isEnabled())

        dlg.input_edit.setText("   ")
        self.assertFalse(dlg.btn_ok.isEnabled())

        dlg.input_edit.setText("Van SD")
        self.assertTrue(dlg.btn_ok.isEnabled())
        self.assertEqual(dlg.get_value(), "Van SD")


if __name__ == "__main__":
    unittest.main()
