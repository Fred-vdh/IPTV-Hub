# DOSSIER DE PASSATION TECHNIQUE : ANALYSE & INTÉGRATION RUST DANS IPTV HUB

> **Destinataire :** Instance Agent IA (Antigravity / Gemini) reprenant le projet.  
> **Date de rédaction :** 17 Octobre 2026  
> **Statut du projet IPTV :** ~98 % terminé, stable et opérationnel en Python/PyQt6.  
> **Dossier source de référence :** `E:\prog-ia\IPTV`  
> **Dossier d'expérimentation Rust :** `E:\prog-ia\IPTV rust`

---

## 1. Contexte & Problématique Initiale

L'utilisateur possède un logiciel IPTV complet et mature (`IPTV Hub`), développé en **Python** avec les technologies suivantes :
- **UI :** PyQt6 (QWidgets, styles QSS sophistiqués, fenêtres transparentes, OSD plein écran, vues personnalisées, navigation clavier/souris).
- **Moteur Vidéo :** `python-mpv` (libmpv C avec accélération matérielle GPU, OpenGL/Direct3D FBO context, support multi-pistes audio/sous-titres, HLS/MPEG-TS).
- **Base de données :** SQLite (`core/database.py`, ~160 Ko de logique, schémas relationnels, gestion des favoris, reprise de lecture, historique).
- **Modules métier :** Client Xtream (`xtream_client.py`), Parser M3U (`m3u_parser.py`), EPG XMLTV (`epg_manager.py`), Téléchargements VOD (`download_manager.py`), Synchronisation Cloud Drive (`sync_manager.py`), QR Code Sync (`qr_sync_server.py`), etc.
- **Volume du code :** ~192 fichiers Python, ~4,4 Mo de code source.

### La question de l'utilisateur :
1. *Est-il possible de recréer une copie pixel-perfect à 100% identique (design, couleurs, animations, fonctionnalités) entièrement en Rust ?*
2. *Est-ce bénéfique pour le programme ?*
3. *Quelles fonctionnalités mériteraient d'être développées en Rust ?*

---

## 2. Verdict Stratégique & Arbitrage Technique

### ❌ Pourquoi réécrire l'application à 100% en Rust est DÉCONSEILLÉ :
1. **Absence d'écosystème GUI Rust mature au niveau de Qt :**
   - Les frameworks UI Rust actuels (*Iced, Slint, Egui, Floem, Tauri*) sont prometteurs mais immatures par rapport aux 25 ans d'expérience de PyQt/Qt.
   - Recréer les styles QSS au pixel près, les animations de tuiles, les overlays transparents au-dessus d'une vidéo accélérée matériellement et la gestion fine des événements Win32 sous Rust représenterait **plusieurs mois de réingénierie lourde**.
2. **Gain nul sur les performances vidéo :**
   - Le décodage, le démultiplexage et le rendu vidéo sont **déjà faits en C et sur le GPU par `mpv`**. Réécrire l'enrobage en Rust ne rendra pas la vidéo plus rapide ni plus fluide.
3. **Risque majeur de régressions :**
   - L'application actuelle a résolu des dizaines de cas limites (formats d'URL exotiques, dates XMLTV corrompues, crashs de drivers GPU, gestion des flux réseau instables). Réécrire 100k lignes de zéro réintroduirait inévitablement des bugs de jeunesse.

###  La Solution Idéale : L'Approche Hybride (Python UI + Rust Core via PyO3)
Conserver l'intégralité de l'interface graphique PyQt6 et le lecteur MPV en Python, et **déléguer les goulets d'étranglement de calcul et de traitement de données à une extension native Rust compilée (`.pyd`) via PyO3 / Maturin**.

---

## 3. Cartographie des 5 Fonctionnalités Idéales pour Rust

Voici les 5 composants identifiés dans le code de `E:\prog-ia\IPTV` qui apporteront un gain de performance spectaculaire s'ils sont portés en Rust :

| Composant | Fichier source actuel | Goulot d'étranglement en Python | Solution Rust recommandée | Gain mesurable attendu |
| :--- | :--- | :--- | :--- | :--- |
| **1. Parseur & Décompresseur EPG XMLTV** | `core/epg_manager.py` | `gzip.decompress` en mémoire + `xml.etree.ElementTree.iterparse` + parsing regex des dates ISO. Bloque l'UI ou prend 30-60s sur un fichier de 300 Mo. | Décompression streaming `flate2` + parseur XML événementiel zéro-copie `quick-xml` + parser de date direct. | **x10 à x20 plus rapide** (2-3s au lieu de 45s). RAM divisée par 5. |
| **2. Parseur M3U / M3U8 géant** | `core/m3u_parser.py` | Regex sur chaque ligne (`ATTR_REGEX`, `EXTINF_REGEX`), création de 200k dataclasses Python. Lenteur sur les listes de 500k chaînes. | Tokenizer Rust zéro allocation sur `&str` / tranches mémoire, traitement multi-cœurs avec `rayon`. | **x15 à x30 plus rapide** (importation en 300ms au lieu de 15s). |
| **3. Moteur de Recherche Floue (Fuzzy Search)** | `core/database.py` (requêtes `LIKE %...%`) | `WHERE name LIKE '%...%'` oblige SQLite à scanner 150k lignes à chaque lettre tapée (Full Table Scan). | Index mémoire en Rust avec trigrammes / Levenshtein (crates `nucleo` ou `fuzzy-matcher`). | **Recherche instantanée (< 1 ms)** avec tolérance aux fautes de frappe et accents. |
| **4. Téléchargeur VOD Multi-connexions** | `core/download_manager.py` | `requests.get(stream=True)` séquentiel sur 1 seule connexion HTTP. Vitesse bridée par les serveurs IPTV à 1-2 Mo/s. | Téléchargement parallèle par segments HTTP (`Range: bytes=...`) avec `tokio` + `reqwest` et écriture fichier `sparse`. | **Téléchargements 3x à 5x plus rapides**, saturant la bande passante réelle. |
| **5. Traitement d'Images & Cache de Logos** | `core/image_loader.py` | Décodage et redimensionnement à la volée sur le CPU Python/Qt provoquant des micro-saccades en défilement. | Décodeur multithreadé SIMD (crate `image`) avec mise en cache optimisée. | Défilement 60/144 FPS parfaitement fluide sans à-coups visuels. |

---

## 4. Spécifications pour l'Implémentation Hybride (PyO3 + Maturin)

Si l'utilisateur décide de démarrer la mise en œuvre de ces modules Rust accélérés, voici la feuille de route technique standardisée :

### A. Outils requis
- Rust toolchain (`rustc`, `cargo`) sous Windows.
- `maturin` (`pip install maturin`) pour compiler les crates Rust directement en packages / modules Python (`.pyd`).

### B. Structure recommandée du projet Rust (`E:\prog-ia\IPTV rust`)
```text
E:\prog-ia\IPTV rust/
├── Cargo.toml
├── pyproject.toml
└── src/
    ├── lib.rs            # Point d'entrée PyO3 (enregistre les fonctions pour Python)
    ├── epg_parser.rs     # Parser XMLTV ultra-rapide (quick-xml, flate2)
    ├── m3u_parser.rs     # Parser M3U zéro-copie
    ├── fuzzy_search.rs   # Index de recherche floue en mémoire (nucleo/fuzzy-matcher)
    └── downloader.rs     # Moteur de téléchargement multi-parts (tokio/reqwest)
```

### C. Dépendances recommandées (`Cargo.toml`)
```toml
[package]
name = "iptv_core_rs"
version = "0.1.0"
edition = "2021"

[lib]
name = "iptv_core_rs"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.21", features = ["extension-module"] }
quick-xml = { version = "0.36", features = ["serialize"] }
flate2 = "1.0"
rayon = "1.10"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
regex = "1.10"
chrono = "0.4"
tokio = { version = "1", features = ["full"], optional = true }
reqwest = { version = "0.12", features = ["stream"], optional = true }
nucleo = "0.5"
```

### D. Exemple de liaison Python transparente
Dans le code Python de `E:\prog-ia\IPTV` :
```python
# Dans core/epg_manager.py ou m3u_parser.py
try:
    import iptv_core_rs
    USE_RUST_CORE = True
except ImportError:
    USE_RUST_CORE = False

def parse_m3u(file_path):
    if USE_RUST_CORE:
        # Appelle directement la bibliothèque Rust compilée
        return iptv_core_rs.parse_m3u_file(file_path)
    # Repli automatique sur le code Python existant
    return fallback_python_m3u_parse(file_path)
```
*Avantage absolu :* Si le binaire Rust est présent, les performances explosent ; s'il n'est pas présent, l'application continue de fonctionner sans aucun problème.

---

## 5. Directives pour l'Agent Repreneur

1. **Priorité Utilisateur :** L'application Python actuelle est à 98% terminée. Si l'utilisateur demande des corrections de bugs ou petites fonctionnalités sur IPTV Hub, **travailler directement dans `E:\prog-ia\IPTV` sur le code Python**.
2. **Ne jamais tenter de refaire toute l'interface PyQt en Rust**, sauf demande formelle et insistante de l'utilisateur après lui avoir rappelé le coût et les limites expliqués ci-dessus.
3. **Si l'utilisateur demande d'optimiser l'importation ou la recherche :** Suivre le plan hybride ci-dessus en développant la crate `iptv_core_rs` dans `E:\prog-ia\IPTV rust` et en compilant avec `maturin develop`.
