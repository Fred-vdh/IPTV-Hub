"""
Tests unitaires pour la compatibilité Linux :
- Détection des bibliothèques libmpv Linux/macOS
- Respect des spécifications XDG pour les données et le cache
- Chargement d'icône multiplateforme
- Intégrité des scripts d'installation Linux
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication

from core.mpv_render import _get_lib_names
from core.database import get_data_dir, get_cache_dir
from ui.icons import get_app_logo_icon


class TestLinuxCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_lib_names_linux(self):
        with patch("sys.platform", "linux"), patch("ctypes.util.find_library", return_value=None):
            names = _get_lib_names()
            self.assertIn("libmpv.so.2", names)
            self.assertIn("libmpv.so.1", names)
            self.assertIn("libmpv.so", names)

    def test_lib_names_with_find_library(self):
        with patch("sys.platform", "linux"), patch("ctypes.util.find_library", return_value="/usr/lib/libmpv.so.2.1"):
            names = _get_lib_names()
            self.assertEqual(names[0], "/usr/lib/libmpv.so.2.1")

    def test_xdg_data_dir_linux(self):
        # Simuler un environnement Linux sans variable APPDATA
        env = dict(os.environ)
        env.pop("APPDATA", None)
        env["XDG_DATA_HOME"] = "/tmp/test_xdg_data"

        with patch.dict(os.environ, env, clear=True), patch("sys.platform", "linux"):
            data_dir = get_data_dir()
            self.assertEqual(data_dir, Path("/tmp/test_xdg_data/IPTV_Hub"))

    def test_xdg_cache_dir_linux(self):
        env = dict(os.environ)
        env.pop("APPDATA", None)
        env["XDG_CACHE_HOME"] = "/tmp/test_xdg_cache"

        with patch.dict(os.environ, env, clear=True), patch("sys.platform", "linux"):
            cache_dir = get_cache_dir()
            self.assertEqual(cache_dir, Path("/tmp/test_xdg_cache/IPTV_Hub"))

    def test_app_logo_icon_validity(self):
        icon = get_app_logo_icon()
        self.assertFalse(icon.isNull(), "L'icône de l'application ne doit pas être nulle")

    def test_linux_scripts_presence_and_shebang(self):
        root = Path(__file__).resolve().parent.parent
        scripts = [
            root / "scripts" / "install_linux.sh",
            root / "scripts" / "uninstall_linux.sh",
            root / "scripts" / "build_appimage.sh",
        ]
        for s in scripts:
            self.assertTrue(s.exists(), f"Le script {s.name} doit exister")
            first_line = s.read_text(encoding="utf-8").splitlines()[0]
            self.assertTrue(first_line.startswith("#!/"), f"Le script {s.name} doit avoir un shebang valide")

    def test_desktop_file_format(self):
        root = Path(__file__).resolve().parent.parent
        desktop_file = root / "scripts" / "iptv-hub.desktop"
        self.assertTrue(desktop_file.exists())
        content = desktop_file.read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", content)
        self.assertIn("Name=IPTV Hub", content)
        self.assertIn("Exec=iptv-hub", content)
    def test_install_script_pip_resilience(self):
        root = Path(__file__).resolve().parent.parent
        install_script = root / "scripts" / "install_linux.sh"
        content = install_script.read_text(encoding="utf-8")
        self.assertIn("without-pip", content)
        self.assertIn("get-pip.py", content)
        self.assertIn("ensurepip", content)
        self.assertIn("python3-venv", content)
        self.assertIn('if [ -f "$SCRIPT_DIR/requirements.txt" ]; then', content)
        self.assertIn('elif [ -f "$SCRIPT_DIR/../requirements.txt" ]; then', content)


if __name__ == "__main__":
    unittest.main()
