#!/usr/bin/env python3
"""
Script de publication de release GitHub pour IPTV Hub.
Crée la release GitHub v2.1.6 et téléverse les packages d'installation.
"""

import subprocess
import urllib.request
import json
from pathlib import Path


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

    # 2. Création de la Release v2.2.2
    release_body = """## 🚀 IPTV Hub v2.2.2 - Listes personnalisées, synchronisation QR et confort de lecture

Bienvenue dans la version **2.2.2** d'**IPTV Hub**, le lecteur multimédia IPTV & VOD moderne et réactif propulsé nativement par PyQt6 et libmpv !

---

### ✨ Nouveautés & Améliorations de cette version :

1. **Listes de chaînes personnalisées** :
   - Créez et gérez vos bouquets de chaînes sur-mesure (ex: *Salon HD*, *Van SD*, *Sport*, *Enfants*).
   - Intégration ergonomique dans la fenêtre de gestion et de filtrage des catégories (réservée au direct).
   - Tri naturel automatique respectant l'ordre TNT et de la playlist d'origine.
   - Possibilité de renommer et supprimer vos listes personnalisées en un clic.

2. **Synchronisation locale par QR Code & Auto-sync** :
   - Partagez vos listes, favoris, historique et listes personnalisées entre appareils en scannant un QR code sur votre réseau local.
   - Serveur de synchronisation léger intégré et mécanisme d'auto-synchronisation.

3. **Confort de visionnage & Séries** :
   - **Détection des génériques (IntroDB)** : Bouton discret permettant de sauter l'intro en un clic ou de manière automatique.
   - **Enchaînement automatique** (*Auto-Play*) de l'épisode suivant avec overlay interactif.
   - Amélioration de la gestion des sous-titres et des flux audio multilingues.

4. **Corrections & Optimisations d'interface** :
   - Exclusion stricte des listes personnalisées lors du filtrage des films ou séries pour un affichage et chargement instantanés.
   - Correction de la redirection *"Voir tout >"* au-dessus de *Reprendre la lecture* vers la section *Récemment regardé*.
   - Palette de couleurs Slate Blue-Grey cohérente dans l'ensemble des boîtes de dialogue.

---

### 📦 Fichiers téléchargeables disponibles :
- **Windows (Installateur complet)** : `IPTV_Hub_Setup.exe` (assistant d'installation avec raccourcis Bureau / Démarrer et dépendances).
- **Windows (Version Portable)** : `IPTV_Hub_Portable_Win64.zip` (prêt à l'emploi sans installation).
- **Linux (Toutes distributions)** : `IPTV_Hub_Linux.tar.gz` (script d'installation automatique avec intégration bureau XDG).
"""

    release_data = {
        'tag_name': 'v2.2.2',
        'target_commitish': 'main',
        'name': 'IPTV Hub v2.2.2',
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
            f"https://api.github.com/repos/{repo}/releases/tags/v2.2.2",
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

    print("\n[OK] Publication de la Release GitHub v2.1.6 terminee avec succes !")


if __name__ == "__main__":
    main()
