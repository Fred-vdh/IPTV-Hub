"""
Gestion centralisée de la version pour IPTV Hub.
Suit le versionnement sémantique (SemVer) : MAJEUR.MINEUR.CORRECTIF.
"""

import re
import sys
from pathlib import Path

__version__ = "2.1.6"
APP_NAME = "IPTV Hub"
BUILD_DATE = "2026-09-16"


def bump_version(part: str = "patch") -> str:
    """Incrémente la version (patch, minor, ou major) et met à jour ce fichier."""
    global __version__
    parts = [int(p) for p in __version__.split(".")]
    if len(parts) != 3:
        parts = [2, 1, 0]

    if part == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
    elif part == "minor":
        parts[1] += 1
        parts[2] = 0
    else:  # patch
        parts[2] += 1

    new_version = f"{parts[0]}.{parts[1]}.{parts[2]}"
    file_path = Path(__file__).resolve()
    content = file_path.read_text(encoding="utf-8")
    updated = re.sub(r'__version__ = ["\'][^"\']+["\']', f'__version__ = "{new_version}"', content, count=1)
    file_path.write_text(updated, encoding="utf-8")
    __version__ = new_version
    print(f"Version IPTV Hub incrémentée à : {new_version}")
    return new_version


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "current"
    if arg in ("patch", "minor", "major"):
        bump_version(arg)
    else:
        print(f"IPTV Hub version actuelle : {__version__}")
