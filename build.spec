# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

block_cipher = None
project_dir = Path.cwd()

# Garantir que les packages locaux (ui, core) sont importables pendant l'analyse.
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# Données additionnelles et DLLs
datas = [
    (str(project_dir / "assets"), "assets"),
]
binaries = []

if sys.platform == "win32":
    win_binaries = [
        ("libmpv-2.dll", "lib"),
        ("yt-dlp.exe", "lib"),
        ("vulkan-1.dll", "lib"),
        ("vulkan-1.dll", "."),
        ("msvcp140.dll", "lib"),
        ("msvcp140.dll", "."),
        ("msvcp140_1.dll", "lib"),
        ("msvcp140_1.dll", "."),
        ("msvcp140_2.dll", "lib"),
        ("msvcp140_2.dll", "."),
    ]
    for filename, dest in win_binaries:
        fpath = project_dir / "lib" / filename
        if fpath.exists():
            binaries.append((str(fpath), dest))

hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtSvg",
    "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets",
    "mpv",
    "requests",
    "aiohttp",
    "m3u8",
    "lxml",
    "sqlite3",
    "certifi",
    "ssl",
]

# Inclusion explicite de TOUS les sous-modules des packages locaux.
# Necessaire car main.py manipule sys.path dynamiquement, ce qui empeche
# l'analyseur statique de PyInstaller de suivre les imports ui.* et core.*.
hiddenimports += [
    "ui",
    "ui.dialogs",
    "ui.dialogs.add_playlist",
    "ui.dialogs.manage_categories_dialog",
    "ui.dialogs.manage_playlists_dialog",
    "ui.dialogs.movie_details_dialog",
    "ui.dialogs.series_dialog",
    "ui.dialogs.settings_dialog",
    "ui.icons",
    "ui.main_window",
    "ui.theme",
    "ui.widgets",
    "ui.widgets.categories_panel",
    "ui.widgets.channel_delegate",
    "ui.widgets.channel_item",
    "ui.widgets.channel_list",
    "ui.widgets.channel_model",
    "ui.widgets.custom_titlebar",
    "ui.widgets.dashboard_view",
    "ui.widgets.epg_grid_view",
    "ui.widgets.epg_timeline",
    "ui.widgets.epg_view",
    "ui.widgets.favorites_view",
    "ui.widgets.gl_video_surface",
    "ui.widgets.movie_details_view",
    "ui.widgets.mpv_widget",
    "ui.widgets.player_controls",
    "ui.widgets.poster_utils",
    "ui.widgets.recently_added_view",
    "ui.widgets.recently_watched_view",
    "ui.widgets.replay_view",
    "ui.widgets.rounded_poster",
    "ui.widgets.series_details_view",
    "ui.widgets.settings_view",
    "ui.widgets.sidebar",
    "ui.widgets.vod_grid",
    "core",
    "core.database",
    "core.download_manager",
    "core.epg_manager",
    "core.image_loader",
    "core.m3u_parser",
    "core.models",
    "core.mpv_render",
    "core.mpv_setup",
    "core.player_controller",
    "core.sync_manager",
    "core.tmdb_client",
    "core.version",
    "core.xtream_client",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Mode dossier standalone (recommandé pour un démarrage instantané avec libmpv)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IPTV_Hub",
    icon=str(project_dir / "assets" / "logo.ico") if sys.platform == "win32" else str(project_dir / "assets" / "logo.png"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Fenêtre graphique pure sans terminal noir
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="IPTV_Hub",
)
