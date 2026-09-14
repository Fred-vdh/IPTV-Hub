<p align="center">
  <img src="assets/logo.png" width="128" height="128" alt="IPTV Hub Logo">
</p>

<h1 align="center">IPTV Hub</h1>

<p align="center">
  <b>Lecteur IPTV & VOD moderne, rapide et élégant pour Windows et Linux.</b><br>
  <i>Inspiré par le design et l'ergonomie d'IPTVnator, propulsé nativement par PyQt6 et libmpv.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.1.4-blue.svg?style=flat-square" alt="Version 2.1.4">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-brightgreen.svg?style=flat-square" alt="Plateformes">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GUI-PyQt6-green.svg?style=flat-square" alt="PyQt6">
  <img src="https://img.shields.io/badge/player-libmpv-orange.svg?style=flat-square" alt="libmpv">
  <img src="https://img.shields.io/badge/license-MIT-lightgrey.svg?style=flat-square" alt="Licence">
</p>

---

## 🌟 Présentation & Inspiration

**IPTV Hub** est un lecteur multimédia de nouvelle génération conçu pour offrir une expérience de visionnage télévisuelle et de vidéo à la demande (VOD) fluide, réactive et hautement personnalisable.

> 💡 **Inspiration** : Le projet s'inspire directement de l'esthétique épurée, sombre et intuitive d’**[IPTVnator](https://github.com/4viur/iptvnator)**.  
> Contrairement aux lecteurs basés sur Electron ou Chromium, **IPTV Hub** a été développé en **Python 3 et Qt6**, avec un moteur de décodage matériel direct s'appuyant sur **`libmpv`** et **OpenGL**. Il en résulte une consommation de mémoire minimale, des temps de démarrage instantanés et une fluidité totale de lecture jusqu'en 4K 60fps.

---

## 📦 Téléchargements (Releases v2.1.4)

Vous pouvez télécharger la version adaptée à votre système directement depuis la section **[Releases](https://github.com/Fred-vdh/IPTV-Hub/releases/latest)** :

| Système | Format | Description | Lien |
| :--- | :--- | :--- | :--- |
| **Windows 10 / 11** | **Installateur (`.exe`)** | Assistant d'installation complet (raccourcis bureau, menu Démarrer, DLLs incluses) | 📥 [**Télécharger l'installateur Windows**](https://github.com/Fred-vdh/IPTV-Hub/releases/download/v2.1.4/IPTV_Hub_Setup.exe) |
| **Windows 10 / 11** | **Version Portable (`.zip`)** | Prêt à l'emploi sans installation (décompressez et lancez `IPTV_Hub.exe`) | 📥 [**Télécharger la version Portable**](https://github.com/Fred-vdh/IPTV-Hub/releases/download/v2.1.4/IPTV_Hub_Portable_Win64.zip) |
| **Linux** (Toutes distributions) | **Paquet d'installation (`.tar.gz`)** | Installation automatique avec intégration bureau XDG et raccourci dans vos applications | 📥 [**Télécharger le paquet Linux**](https://github.com/Fred-vdh/IPTV-Hub/releases/download/v2.1.4/IPTV_Hub_Linux.tar.gz) |
| **Linux** (Autonome) | **Fichier AppImage** | Exécutable tout-en-un sans installation requise (double-clic direct) | 📥 [**Télécharger l'AppImage**](https://github.com/Fred-vdh/IPTV-Hub/releases/download/v2.1.4/IPTV_Hub-x86_64.AppImage) |

---

## ✨ Fonctionnalités Principales

### 📺 Télévision en Direct (Live TV)
- **Gestion des flux** : Prise en charge complète des protocoles HLS (`.m3u8`), MPEG-TS (`.ts`), RTMP et HTTP(S).
- **Navigation par catégories** : Arborescence intuitive des groupes de chaînes avec compteur et logos dynamiques.
- **Guide Électronique des Programmes (EPG)** : Affichage du programme en cours et du programme suivant en temps réel.
- **Grille EPG interactive** : Vue chronologique complète avec curseur d'avancement horaire.

### 🎬 Vidéo à la Demande (Films & Séries)
- **Métadonnées et enrichissement TMDB** : Récupération automatique des affiches officielles, synopsis, casting, notes et dates de sortie.
- **Filmographie des artistes** : Cliquez sur un acteur ou un réalisateur pour explorer l'ensemble de ses films disponibles dans votre playlist !
- **Gestion intelligente des séries** : Sélecteur clair des saisons et épisodes, reprise automatique de lecture et enchaînement automatique de l'épisode suivant (*Auto-Play*).
- **Indicateurs de progression** : Suivi précis du temps visionné par épisode et par film.

### ⏪ Replay TV (Catchup)
- Visionnage en différé des programmes passés jusqu'à 7 jours en arrière sur les chaînes compatibles (Xtream Catchup & Flussonic).
- Timeline visuelle intuitive pour sauter directement au début de votre émission.

### 🚀 Performance & Moteur Vidéo
- **Moteur libmpv natif** : Accélération matérielle GPU (DirectX, Vulkan, VA-API, VDPAU, NVDEC).
- **Contrôles audio et sous-titres** : Sélection instantanée des pistes audio multilingues et des sous-titres intégrés ou externes.
- **OSD élégant et discret** : Barre de commandes épurée et interactive avec molette de volume et raccourcis clavier rapides.

### 🗂️ Gestion des Playlists & Sécurité
- **Multi-fournisseurs** : Prise en charge des API **Xtream Codes** (URL, utilisateur, mot de passe) et des fichiers/liens **M3U/M3U8**.
- **Gestionnaire de catégories** : Masquage facile des bouquets de chaînes indésirables ou redondants.
- **Favoris et Historique** : Système d'étoiles rapide et historique des derniers programmes regardés.
- **Confidentialité totale** : Aucune donnée de vos listes de lecture ne transite par des serveurs tiers ; la base de données SQLite reste 100% locale à votre machine.

---

## 🛠️ Guide d'Installation

### 🪟 Sous Windows

#### Méthode 1 : Installateur classique
1. Téléchargez [`IPTV_Hub_Setup.exe`](https://github.com/Fred-vdh/IPTV-Hub/releases/download/v2.1.4/IPTV_Hub_Setup.exe).
2. Lancez l'exécutable et suivez l'assistant d'installation (disponible en français et en anglais).
3. L'application est installée et accessible depuis votre Bureau et votre menu Démarrer.

#### Méthode 2 : Version Portable
1. Téléchargez [`IPTV_Hub_Portable_Win64.zip`](https://github.com/Fred-vdh/IPTV-Hub/releases/download/v2.1.4/IPTV_Hub_Portable_Win64.zip).
2. Décompressez l'archive où vous le souhaitez (disque dur, clé USB).
3. Double-cliquez sur `IPTV_Hub.exe` pour démarrer directement !

---

### 🐧 Sous Linux (Ubuntu, Debian, Linux Mint, Zorin OS, Fedora, Arch...)

#### Méthode 1 : Installateur automatique (Recommandé)
1. Téléchargez [`IPTV_Hub_Linux.tar.gz`](https://github.com/Fred-vdh/IPTV-Hub/releases/download/v2.1.4/IPTV_Hub_Linux.tar.gz).
2. Ouvrez un terminal dans le dossier et lancez :
   ```bash
   tar -xzf IPTV_Hub_Linux.tar.gz
   cd IPTV_Hub_Linux
   ./install.sh
   ```
3. L'application s'intègre automatiquement dans votre menu d'applications et déploie son raccourci sur votre Bureau !

*(Astuce sous Ubuntu/Debian/Zorin OS : installez les dépendances système en une ligne : `sudo apt install -y python3-venv python3-pip libmpv-dev libmpv2`)*

#### Méthode 2 : AppImage (Sans installation)
1. Téléchargez [`IPTV_Hub-x86_64.AppImage`](https://github.com/Fred-vdh/IPTV-Hub/releases/download/v2.1.4/IPTV_Hub-x86_64.AppImage).
2. Rendez le fichier exécutable :
   ```bash
   chmod +x IPTV_Hub-x86_64.AppImage
   ```
3. Double-cliquez dessus pour lancer IPTV Hub !

---

## 💻 Développement & Exécution depuis les sources

Pour les développeurs souhaitant modifier ou contribuer au projet :

```bash
# 1. Cloner le dépôt
git clone https://github.com/Fred-vdh/IPTV-Hub.git
cd IPTV-Hub

# 2. Créer et activer un environnement virtuel
python -m venv venv
# Sous Windows :
.\venv\Scripts\activate
# Sous Linux :
source venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'application
python main.py
```

---

## 🤝 Remerciements & Crédits

- **[IPTVnator](https://github.com/4viur/iptvnator)** par [4viur](https://github.com/4viur) pour l'inspiration de l'interface utilisateur sombre et fonctionnelle.
- **[mpv.io](https://mpv.io)** pour l'extraordinaire moteur de décodage et de rendu vidéo.
- **[The Movie Database (TMDB)](https://www.themoviedb.org)** pour les métadonnées cinématographiques et affiches.
- **[Qt Project](https://www.qt.io)** pour le framework d'interface graphique PyQt6.

---

<p align="center">
  Fait avec passion pour une expérience IPTV moderne et sans compromis.
</p>
