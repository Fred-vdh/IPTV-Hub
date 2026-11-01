#!/usr/bin/env python3
"""
Script de publication de release GitHub pour IPTV Hub.
Crée la release GitHub v2.1.6 et téléverse les packages d'installation.
"""

import subprocess
import urllib.request
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main():
    # 1. Récupération sécurisée du token GitHub via Git Credential Manager
    proc = subprocess.Popen(
        ['git', 'credential', 'fill'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, _ = proc.communicate('url=https://github.com/Fred-vdh/IPTV-Hub.git\n')
    token = None
    for line in out.splitlines():
        if line.startswith('password='):
            token = line.split('=', 1)[1].strip()

    if not token:
        raise RuntimeError("Token GitHub introuvable via git credential")

    print("Token GitHub récupéré avec succès.")

    repo = "Fred-vdh/IPTV-Hub"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'IPTV-Hub-Release-Script'
    }

    from core.version import __version__
    tag_name = f"v{__version__}"

    # 2. Création de la Release v2.4.0
    release_body = f"""## 🚀 IPTV Hub {tag_name} - Moteur hybride Rust, Fiabilité du lecteur & Nouvelle expérience OSD

Bienvenue dans la version **{__version__}** d'**IPTV Hub**, le lecteur multimédia IPTV & VOD moderne, rapide et élégant propulsé nativement par PyQt6, libmpv et accéléré en Rust !

---

### ✨ Nouveautés & Améliorations de cette version :

1. **🚀 Moteur Rust hybride ultra-rapide (`iptv_core_rs`)** :
   - Indexation en mémoire et moteur de recherche floue (fuzzy search) haute performance pour l'ensemble du catalogue.
   - Filtrage et tris instantanés des chaînes, films et séries sans aucune latence sur les playlists volumineuses.
   - Parsing accéléré et gestion optimisée des flux M3U et métadonnées EPG.

2. **🛡️ Fiabilisation du lecteur & Correction critique de l'écran noir** :
   - Correction d'une régression empêchant la pause/reprise normale au clic dans les fiches détaillées de films et provoquant un écran noir.
   - Exposition officielle de la propriété `state` sur `PlayerController` et sécurisation des transitions d'états.
   - Réinitialisation systématique des drapeaux de fin de série lors de l'ouverture d'un film ou d'une bande-annonce.
   - Protection de l'intégrité de la pile de lecture vidéo (`player_stack`) et détachement/rattachement sécurisé.

3. **🌟 Nouvel écran de démarrage (Splash Screen) & Confort visuel** :
   - Écran de chargement moderne et animé au démarrage informant de la progression de l'initialisation et du chargement de la base de données.
   - Mode survol intelligent pour l'OSD (`osd_hover_mode`) avec disparition automatique des contrôles et du curseur pour une immersion totale.
   - Fluidité accrue des commandes interactives de lecture et de saut temporel (+10s / -10s).

4. **🎬 Recherche d'artistes & Filmographie enrichie** :
   - Recherche globale d'acteurs et réalisateurs avec suggestions dynamiques et dialogue interactif.
   - Prise en compte enrichie des créateurs et scénaristes de séries.
   - Optimisation de la grille VOD et de la pagination asynchrone pour un défilement ultra-fluide.

---

### 📦 Fichiers téléchargeables disponibles :
- **Windows (Installateur complet)** : `IPTV_Hub_Setup.exe` (assistant d'installation avec raccourcis Bureau / Démarrer et dépendances).
- **Windows (Version Portable)** : `IPTV_Hub_Portable_Win64.zip` (prêt à l'emploi sans installation).
- **Linux (Toutes distributions)** : `IPTV_Hub_Linux.tar.gz` (script d'installation automatique avec intégration bureau XDG).
"""

    release_data = {
        'tag_name': tag_name,
        'target_commitish': 'main',
        'name': f'IPTV Hub {tag_name}',
        'body': release_body,
        'draft': False,
        'prerelease': False
    }

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases",
        data=json.dumps(release_data).encode('utf-8'),
        headers={**headers, 'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req) as resp:
            rel_info = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        print(f"Erreur API GitHub lors de la création de la release : {err_msg}")
        # Si la release existe déjà pour ce tag, tenter de la récupérer
        req_get = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases/tags/{tag_name}",
            headers=headers
        )
        with urllib.request.urlopen(req_get) as resp_get:
            rel_info = json.loads(resp_get.read().decode('utf-8'))

    print(f"Release prête : {rel_info.get('html_url')}")
    upload_url_template = rel_info['upload_url']
    upload_base = upload_url_template.split('{')[0]

    # 3. Upload des 3 assets
    dist_dir = Path("dist_installer")
    files_to_upload = [
        ("IPTV_Hub_Setup.exe", "application/octet-stream"),
        ("IPTV_Hub_Portable_Win64.zip", "application/zip"),
        ("IPTV_Hub_Linux.tar.gz", "application/gzip"),
    ]

    # Récupérer les assets existants pour éviter les doublons
    existing_assets = {a['name']: a['id'] for a in rel_info.get('assets', [])}

    for filename, content_type in files_to_upload:
        file_path = dist_dir / filename
        if not file_path.exists():
            print(f"Attention : {file_path} introuvable, upload ignoré.")
            continue

        # Si l'asset existe déjà, le supprimer d'abord
        if filename in existing_assets:
            del_id = existing_assets[filename]
            print(f"Suppression de l'ancien asset {filename} (ID: {del_id})...")
            del_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases/assets/{del_id}",
                headers=headers,
                method='DELETE'
            )
            with urllib.request.urlopen(del_req):
                pass

        size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"Upload de {filename} ({size_mb:.2f} MB)...")
        with open(file_path, 'rb') as f:
            file_bytes = f.read()

        upload_url = f"{upload_base}?name={filename}"
        req_upload = urllib.request.Request(
            upload_url,
            data=file_bytes,
            headers={
                **headers,
                'Content-Type': content_type,
                'Content-Length': str(len(file_bytes))
            },
            method='POST'
        )
        with urllib.request.urlopen(req_upload) as u_resp:
            asset_info = json.loads(u_resp.read().decode('utf-8'))
            print(f"-> {filename} téléversé avec succès ({asset_info.get('state')})")

    print(f"\n[OK] Publication de la Release GitHub {tag_name} terminée avec succès !")


if __name__ == "__main__":
    main()
