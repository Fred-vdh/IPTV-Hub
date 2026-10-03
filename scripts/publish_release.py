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

    # 2. Création de la Release v2.3.0
    release_body = f"""## 🚀 IPTV Hub {tag_name} - Gestionnaire de téléchargements VOD & Séries, chapitrage interactif et confort de lecture

Bienvenue dans la version **{__version__}** d'**IPTV Hub**, le lecteur multimédia IPTV & VOD moderne, rapide et élégant propulsé nativement par PyQt6 et libmpv !

---

### ✨ Nouveautés & Améliorations de cette version :

1. **📥 Gestionnaire de Téléchargements VOD & Séries (Mode Hors-ligne)** :
   - Enregistrez vos films et séries préférés en un clic directement depuis leur fiche de détails.
   - File d'attente FIFO intelligente (un seul flux simultané pour préserver votre abonnement IPTV).
   - Reprise automatique des téléchargements interrompus via requêtes `HTTP Range`.
   - Nouvelle section dédiée **Téléchargements** dans la barre latérale sous *Récemment ajouté*, avec onglets *En cours* et *Terminés*.
   - Choix du dossier de destination des vidéos et limitation optionnelle du débit dans les Paramètres (*Données & Téléchargements*).
   - Débit de téléchargement optimisé (chunks 128 Ko et régulation fine de bande passante).

2. **🎞️ Chapitrage & Marqueurs interactifs sur la timeline vidéo** :
   - Détection et extraction automatique des chapitres intégrés aux conteneurs vidéo (MKV, MP4).
   - Marqueurs visuels discrets sur la barre de progression respectant fidèlement la charte graphique.
   - Infobulles ergonomiques au survol affichant le titre du chapitre et le timer précis, sans aucun scintillement d'affichage.

3. **📻 Filtrage des catégories & Radios fiabilisé** :
   - Sauvegarde pérenne des sélections de catégories dans la boîte de dialogue de gestion des catégories.
   - Prise en charge complète des bouquets de stations de radios en direct sans réinitialisation involontaire.

4. **🎬 Ergonomie des fiches de détails & Reprise de lecture** :
   - Fiches de films et séries : suppression des boutons redondants pour une interface épurée (*Reprendre du début* unique et clair).
   - Curseur contextuel optimisé (main cliquable uniquement sur les éléments interactifs).
   - Masquage automatique des bandes-annonces pendant la lecture vidéo pour économiser les ressources.

5. **⚡ Optimisations sous le capot & Stabilité** :
   - Résolution de conflits de signaux Qt sous Windows et fiabilisation des threads de fond.
   - Mises à jour des traductions françaises et anglaises.

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
