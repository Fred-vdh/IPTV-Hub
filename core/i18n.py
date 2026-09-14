"""
Module central d'internationalisation (i18n) pour IPTV Hub.
Supporte le Français ('fr') et l'Anglais ('en') avec basculement dynamique
sans redémarrage requis et fallback transparent sur le texte d'origine.
"""

from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal


# Dictionnaires de traductions
# Clé : texte source (souvent en français ou identifiant logique)
# Valeur : dictionnaire des traductions {"fr": "...", "en": "..."}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ---------------------------------------------------------
    # Barre de titre & Contrôles globaux
    # ---------------------------------------------------------
    "IPTV Hub": {
        "fr": "IPTV Hub",
        "en": "IPTV Hub",
    },
    "Liste :": {
        "fr": "Liste :",
        "en": "Playlist:",
    },
    "Rafraîchir les chaînes de la liste active": {
        "fr": "Rafraîchir les chaînes de la liste active",
        "en": "Refresh channels of active playlist",
    },
    "Ajouter une liste de lecture": {
        "fr": "Ajouter une liste de lecture",
        "en": "Add a playlist",
    },
    "Rechercher sur le tableau de bord...": {
        "fr": "Rechercher sur le tableau de bord...",
        "en": "Search on dashboard...",
    },
    "Favoris | Filtrer cette section...": {
        "fr": "Favoris | Filtrer cette section...",
        "en": "Favorites | Filter this section...",
    },
    "Rechercher dans l'historique...": {
        "fr": "Rechercher dans l'historique...",
        "en": "Search in history...",
    },
    "Rechercher une chaîne en direct...": {
        "fr": "Rechercher une chaîne en direct...",
        "en": "Search live TV channel...",
    },
    "Rechercher un film (VOD)...": {
        "fr": "Rechercher un film (VOD)...",
        "en": "Search a movie (VOD)...",
    },
    "Rechercher une série...": {
        "fr": "Rechercher une série...",
        "en": "Search a series...",
    },
    "Rechercher parmi les récents ajouts...": {
        "fr": "Rechercher parmi les récents ajouts...",
        "en": "Search among recent additions...",
    },
    "Rechercher dans le guide TV...": {
        "fr": "Rechercher dans le guide TV...",
        "en": "Search in TV guide...",
    },
    "Rechercher dans le Replay...": {
        "fr": "Rechercher dans le Replay...",
        "en": "Search in Replay...",
    },
    "Rechercher...": {
        "fr": "Rechercher...",
        "en": "Search...",
    },
    "Réduire": {
        "fr": "Réduire",
        "en": "Minimize",
    },
    "Agrandir / Restaurer": {
        "fr": "Agrandir / Restaurer",
        "en": "Maximize / Restore",
    },
    "Fermer": {
        "fr": "Fermer",
        "en": "Close",
    },

    # ---------------------------------------------------------
    # Barre latérale (Sidebar)
    # ---------------------------------------------------------
    "Tableau de bord": {
        "fr": "Tableau de bord",
        "en": "Dashboard",
    },
    "Favoris globaux": {
        "fr": "Favoris globaux",
        "en": "Global favorites",
    },
    "Récemment regardé": {
        "fr": "Récemment regardé",
        "en": "Recently watched",
    },
    "Guide des programmes (EPG)": {
        "fr": "Guide des programmes (EPG)",
        "en": "TV Guide (EPG)",
    },
    "TV Replay (Rattrapage)": {
        "fr": "TV Replay (Rattrapage)",
        "en": "TV Replay (Catchup)",
    },
    "TV en direct": {
        "fr": "TV en direct",
        "en": "Live TV",
    },
    "Films (VOD)": {
        "fr": "Films (VOD)",
        "en": "Movies (VOD)",
    },
    "Séries": {
        "fr": "Séries",
        "en": "Series",
    },
    "Récemment ajoutés (TV, VOD, Séries)": {
        "fr": "Récemment ajoutés (TV, VOD, Séries)",
        "en": "Recently added (TV, VOD, Series)",
    },
    "Gérer les listes de lecture": {
        "fr": "Gérer les listes de lecture",
        "en": "Manage playlists",
    },
    "Paramètres de l'application": {
        "fr": "Paramètres de l'application",
        "en": "Application settings",
    },

    # ---------------------------------------------------------
    # Panneau des catégories & Liste des chaînes
    # ---------------------------------------------------------
    "CATÉGORIES": {
        "fr": "CATÉGORIES",
        "en": "CATEGORIES",
    },
    "Toutes les catégories": {
        "fr": "Toutes les catégories",
        "en": "All categories",
    },
    "Toutes": {
        "fr": "Toutes",
        "en": "All",
    },
    "Filtrer les catégories...": {
        "fr": "Filtrer les catégories...",
        "en": "Filter categories...",
    },
    "Filtrer les chaînes...": {
        "fr": "Filtrer les chaînes...",
        "en": "Filter channels...",
    },
    "Gérer les catégories": {
        "fr": "Gérer les catégories",
        "en": "Manage categories",
    },
    "CHAÎNES": {
        "fr": "CHAÎNES",
        "en": "CHANNELS",
    },
    "Aucune chaîne": {
        "fr": "Aucune chaîne",
        "en": "No channels",
    },
    "Aucune catégorie": {
        "fr": "Aucune catégorie",
        "en": "No category",
    },
    "chaîne": {
        "fr": "chaîne",
        "en": "channel",
    },
    "chaînes": {
        "fr": "chaînes",
        "en": "channels",
    },
    "film": {
        "fr": "film",
        "en": "movie",
    },
    "films": {
        "fr": "films",
        "en": "movies",
    },
    "série": {
        "fr": "série",
        "en": "series",
    },
    "séries": {
        "fr": "séries",
        "en": "series",
    },
    "Ajouter aux favoris": {
        "fr": "Ajouter aux favoris",
        "en": "Add to favorites",
    },
    "Retirer des favoris": {
        "fr": "Retirer des favoris",
        "en": "Remove from favorites",
    },
    "Masquer la chaîne": {
        "fr": "Masquer la chaîne",
        "en": "Hide channel",
    },
    "Copier l'URL du flux": {
        "fr": "Copier l'URL du flux",
        "en": "Copy stream URL",
    },

    # ---------------------------------------------------------
    # Options de tri des catégories et listes
    # ---------------------------------------------------------
    "Ordre original": {
        "fr": "Ordre original",
        "en": "Original order",
    },
    "Par défaut (Serveur)": {
        "fr": "Par défaut (Serveur)",
        "en": "Default (Server)",
    },
    "Nom (A-Z)": {
        "fr": "Nom (A-Z)",
        "en": "Name (A-Z)",
    },
    "Nom (Z-A)": {
        "fr": "Nom (Z-A)",
        "en": "Name (Z-A)",
    },
    "Nombre de chaînes (Décroissant)": {
        "fr": "Nombre de chaînes (Décroissant)",
        "en": "Channel count (Descending)",
    },
    "Nombre d'éléments (Décroissant)": {
        "fr": "Nombre d'éléments (Décroissant)",
        "en": "Item count (Descending)",
    },
    "Plus récents d'abord": {
        "fr": "Plus récents d'abord",
        "en": "Most recent first",
    },
    "Mieux notés": {
        "fr": "Mieux notés",
        "en": "Top rated",
    },
    "Année (Plus récent)": {
        "fr": "Année (Plus récent)",
        "en": "Year (Newest)",
    },
    "Année (Plus ancien)": {
        "fr": "Année (Plus ancien)",
        "en": "Year (Oldest)",
    },
    "Trier par :": {
        "fr": "Trier par :",
        "en": "Sort by:",
    },

    # ---------------------------------------------------------
    # Galeries VOD & Séries
    # ---------------------------------------------------------
    "TOUS LES FILMS": {
        "fr": "TOUS LES FILMS",
        "en": "ALL MOVIES",
    },
    "TOUTES LES SÉRIES": {
        "fr": "TOUTES LES SÉRIES",
        "en": "ALL SERIES",
    },
    "Affiner les résultats": {
        "fr": "Affiner les résultats",
        "en": "Refine results",
    },
    "Recherche par artiste": {
        "fr": "Recherche par artiste",
        "en": "Search by artist",
    },
    "Filmographie": {
        "fr": "Filmographie",
        "en": "Filmography",
    },
    "Acteur ou Réalisateur...": {
        "fr": "Acteur ou Réalisateur...",
        "en": "Actor or Director...",
    },
    "Chargement...": {
        "fr": "Chargement...",
        "en": "Loading...",
    },
    "Aucun résultat": {
        "fr": "Aucun résultat",
        "en": "No results",
    },
    "Aucun film trouvé": {
        "fr": "Aucun film trouvé",
        "en": "No movies found",
    },
    "Aucune série trouvée": {
        "fr": "Aucune série trouvée",
        "en": "No series found",
    },
    "Page précédente": {
        "fr": "Page précédente",
        "en": "Previous page",
    },
    "Page suivante": {
        "fr": "Page suivante",
        "en": "Next page",
    },
    "Page {current} sur {total}": {
        "fr": "Page {current} sur {total}",
        "en": "Page {current} of {total}",
    },

    # ---------------------------------------------------------
    # Fiches Détaillées (Films et Séries)
    # ---------------------------------------------------------
    "Lecture": {
        "fr": "Lecture",
        "en": "Play",
    },
    "Reprendre": {
        "fr": "Reprendre",
        "en": "Resume",
    },
    "Bande-annonce": {
        "fr": "Bande-annonce",
        "en": "Trailer",
    },
    "Synopsis": {
        "fr": "Synopsis",
        "en": "Synopsis",
    },
    "Distribution": {
        "fr": "Distribution",
        "en": "Cast",
    },
    "Réalisateur": {
        "fr": "Réalisateur",
        "en": "Director",
    },
    "Genre": {
        "fr": "Genre",
        "en": "Genre",
    },
    "Durée": {
        "fr": "Durée",
        "en": "Duration",
    },
    "Année": {
        "fr": "Année",
        "en": "Year",
    },
    "Saisons et Épisodes": {
        "fr": "Saisons et Épisodes",
        "en": "Seasons and Episodes",
    },
    "Saison": {
        "fr": "Saison",
        "en": "Season",
    },
    "Épisode": {
        "fr": "Épisode",
        "en": "Episode",
    },
    "Épisodes": {
        "fr": "Épisodes",
        "en": "Episodes",
    },
    "Retour": {
        "fr": "Retour",
        "en": "Back",
    },
    "Retour à la liste": {
        "fr": "Retour à la liste",
        "en": "Back to list",
    },
    "Marquer comme vu": {
        "fr": "Marquer comme vu",
        "en": "Mark as watched",
    },
    "Marquer comme non vu": {
        "fr": "Marquer comme non vu",
        "en": "Mark as unwatched",
    },

    # ---------------------------------------------------------
    # Tableau de bord (Dashboard)
    # ---------------------------------------------------------
    "Bienvenue sur IPTV Hub": {
        "fr": "Bienvenue sur IPTV Hub",
        "en": "Welcome to IPTV Hub",
    },
    "Reprendre la lecture": {
        "fr": "Reprendre la lecture",
        "en": "Continue Watching",
    },
    "Chaînes favorites": {
        "fr": "Chaînes favorites",
        "en": "Favorite Channels",
    },
    "Films récemment ajoutés": {
        "fr": "Films récemment ajoutés",
        "en": "Recently Added Movies",
    },
    "Séries récemment ajoutées": {
        "fr": "Séries récemment ajoutées",
        "en": "Recently Added Series",
    },
    "Statistiques de la liste": {
        "fr": "Statistiques de la liste",
        "en": "Playlist Statistics",
    },
    "Chaînes TV": {
        "fr": "Chaînes TV",
        "en": "Live TV",
    },
    "Films": {
        "fr": "Films",
        "en": "Movies",
    },
    "Voir tout": {
        "fr": "Voir tout",
        "en": "View all",
    },

    # ---------------------------------------------------------
    # Guide des programmes (EPG) & Replay
    # ---------------------------------------------------------
    "Guide des programmes": {
        "fr": "Guide des programmes",
        "en": "TV Guide",
    },
    "Aujourd'hui": {
        "fr": "Aujourd'hui",
        "en": "Today",
    },
    "Hier": {
        "fr": "Hier",
        "en": "Yesterday",
    },
    "Demain": {
        "fr": "Demain",
        "en": "Tomorrow",
    },
    "En direct maintenant": {
        "fr": "En direct maintenant",
        "en": "Live now",
    },
    "Aucun guide des programmes disponible": {
        "fr": "Aucun guide des programmes disponible",
        "en": "No TV guide data available",
    },
    "Chargement du guide TV...": {
        "fr": "Chargement du guide TV...",
        "en": "Loading TV guide...",
    },
    "Rattrapage TV (Replay 7 jours)": {
        "fr": "Rattrapage TV (Replay 7 jours)",
        "en": "TV Catchup (7 days replay)",
    },
    "Sélectionnez une chaîne avec l'icône Replay pour voir les émissions disponibles": {
        "fr": "Sélectionnez une chaîne avec l'icône Replay pour voir les émissions disponibles",
        "en": "Select a channel with Replay icon to view available broadcasts",
    },

    # ---------------------------------------------------------
    # Favoris, Historique, Récents
    # ---------------------------------------------------------
    "Vos Favoris": {
        "fr": "Vos Favoris",
        "en": "Your Favorites",
    },
    "Historique de lecture": {
        "fr": "Historique de lecture",
        "en": "Watch History",
    },
    "Récemment ajoutés": {
        "fr": "Récemment ajoutés",
        "en": "Recently Added",
    },
    "Effacer l'historique": {
        "fr": "Effacer l'historique",
        "en": "Clear history",
    },
    "Aucun élément récent": {
        "fr": "Aucun élément récent",
        "en": "No recent items",
    },
    "Aucun favori enregistré": {
        "fr": "Aucun favori enregistré",
        "en": "No favorites saved",
    },

    # ---------------------------------------------------------
    # Paramètres (SettingsView)
    # ---------------------------------------------------------
    "Paramètres": {
        "fr": "Paramètres",
        "en": "Settings",
    },
    "Général & Interface": {
        "fr": "Général & Interface",
        "en": "General & Interface",
    },
    "Lecteur Vidéo": {
        "fr": "Lecteur Vidéo",
        "en": "Video Player",
    },
    "Réseau & Flux": {
        "fr": "Réseau & Flux",
        "en": "Network & Streams",
    },
    "Guide EPG": {
        "fr": "Guide EPG",
        "en": "EPG Guide",
    },
    "Données & Stockage": {
        "fr": "Données & Stockage",
        "en": "Data & Storage",
    },
    "Sauvegarde & Fichiers": {
        "fr": "Sauvegarde & Fichiers",
        "en": "Backup & Files",
    },
    "À propos": {
        "fr": "À propos",
        "en": "About",
    },
    "Fermer les paramètres": {
        "fr": "Fermer les paramètres",
        "en": "Close settings",
    },
    "Enregistrer les paramètres": {
        "fr": "Enregistrer les paramètres",
        "en": "Save settings",
    },
    "Paramètres enregistrés": {
        "fr": "Paramètres enregistrés",
        "en": "Settings saved",
    },
    "Les modifications ont été enregistrées avec succès.": {
        "fr": "Les modifications ont été enregistrées avec succès.",
        "en": "Changes have been saved successfully.",
    },

    # Onglet Général
    "Général & Apparence": {
        "fr": "Général & Apparence",
        "en": "General & Appearance",
    },
    "Personnalisez l'affichage, le comportement au démarrage et l'interface utilisateur.": {
        "fr": "Personnalisez l'affichage, le comportement au démarrage et l'interface utilisateur.",
        "en": "Customize display, startup behavior and user interface.",
    },
    "Langue de l'application :": {
        "fr": "Langue de l'application :",
        "en": "Application language:",
    },
    "Thème de l'interface :": {
        "fr": "Thème de l'interface :",
        "en": "Interface theme:",
    },
    "Gris foncé bleuté (Par défaut)": {
        "fr": "Gris foncé bleuté (Par défaut)",
        "en": "Bluish Dark Grey (Default)",
    },
    "Sombre moderne": {
        "fr": "Sombre moderne",
        "en": "Modern Dark",
    },
    "Langue audio préférée (Films & Séries) :": {
        "fr": "Langue audio préférée (Films & Séries) :",
        "en": "Preferred audio language (Movies & Series):",
    },
    "Sous-titres automatiques :": {
        "fr": "Sous-titres automatiques :",
        "en": "Automatic subtitles:",
    },
    "Langue des sous-titres :": {
        "fr": "Langue des sous-titres :",
        "en": "Subtitles language:",
    },
    "Désactivés": {
        "fr": "Désactivés",
        "en": "Disabled",
    },
    "Activés": {
        "fr": "Activés",
        "en": "Enabled",
    },
    "Lecture automatique de l'épisode suivant :": {
        "fr": "Lecture automatique de l'épisode suivant :",
        "en": "Auto-play next episode:",
    },
    "Activer l'enchaînement automatique des épisodes de séries": {
        "fr": "Activer l'enchaînement automatique des épisodes de séries",
        "en": "Enable auto-playing next episode of series",
    },
    "Afficher la date d'ajout sur les affiches (VOD & Séries) :": {
        "fr": "Afficher la date d'ajout sur les affiches (VOD & Séries) :",
        "en": "Show added date badge on posters (VOD & Series):",
    },
    "Afficher le badge de date de sortie/ajout sur les jaquettes": {
        "fr": "Afficher le badge de date de sortie/ajout sur les jaquettes",
        "en": "Show release/added date badge on poster cards",
    },

    # Onglet Lecteur Vidéo
    "Moteur de rendu MPV": {
        "fr": "Moteur de rendu MPV",
        "en": "MPV Rendering Engine",
    },
    "Configurez le décodage matériel et le traitement d'image du lecteur multimédia.": {
        "fr": "Configurez le décodage matériel et le traitement d'image du lecteur multimédia.",
        "en": "Configure hardware decoding and image processing for the media player.",
    },
    "Accélération matérielle (hwdec) :": {
        "fr": "Accélération matérielle (hwdec) :",
        "en": "Hardware acceleration (hwdec):",
    },
    "Automatique (Recommandé)": {
        "fr": "Automatique (Recommandé)",
        "en": "Automatic (Recommended)",
    },
    "Direct3D 11 (Windows)": {
        "fr": "Direct3D 11 (Windows)",
        "en": "Direct3D 11 (Windows)",
    },
    "NVIDIA NVDEC": {
        "fr": "NVIDIA NVDEC",
        "en": "NVIDIA NVDEC",
    },
    "VA-API (Linux)": {
        "fr": "VA-API (Linux)",
        "en": "VA-API (Linux)",
    },
    "Désactivée (CPU uniquement)": {
        "fr": "Désactivée (CPU uniquement)",
        "en": "Disabled (CPU only)",
    },
    "Désentrelacement matériel :": {
        "fr": "Désentrelacement matériel :",
        "en": "Hardware deinterlacing:",
    },
    "Activer le désentrelacement (flux TV 1080i entrelacés)": {
        "fr": "Activer le désentrelacement (flux TV 1080i entrelacés)",
        "en": "Enable deinterlacing (for interlaced 1080i TV streams)",
    },
    "Format d'image par défaut (Aspect Ratio) :": {
        "fr": "Format d'image par défaut (Aspect Ratio) :",
        "en": "Default Aspect Ratio:",
    },
    "Automatique (Original)": {
        "fr": "Automatique (Original)",
        "en": "Automatic (Original)",
    },
    "Taille du tampon réseau :": {
        "fr": "Taille du tampon réseau :",
        "en": "Network buffer size:",
    },
    "Volume initial au démarrage :": {
        "fr": "Volume initial au démarrage :",
        "en": "Initial volume on startup:",
    },

    # Onglet Réseau & Flux
    "Réseau & En-têtes HTTP": {
        "fr": "Réseau & En-têtes HTTP",
        "en": "Network & HTTP Headers",
    },
    "Personnalisez l'agent utilisateur (User-Agent) et les délais d'attente de connexion.": {
        "fr": "Personnalisez l'agent utilisateur (User-Agent) et les délais d'attente de connexion.",
        "en": "Customize User-Agent and connection timeout settings.",
    },
    "User-Agent par défaut :": {
        "fr": "User-Agent par défaut :",
        "en": "Default User-Agent:",
    },

    # Onglet Guide EPG
    "Guide des Programmes (EPG)": {
        "fr": "Guide des Programmes (EPG)",
        "en": "Electronic Program Guide (EPG)",
    },
    "Gestion du téléchargement et de la mise à jour des programmes XMLTV.": {
        "fr": "Gestion du téléchargement et de la mise à jour des programmes XMLTV.",
        "en": "Management of XMLTV program downloads and updates.",
    },
    "Mise à jour automatique :": {
        "fr": "Mise à jour automatique :",
        "en": "Automatic updates:",
    },
    "Mettre à jour l'EPG au démarrage de l'application": {
        "fr": "Mettre à jour l'EPG au démarrage de l'application",
        "en": "Update EPG on application startup",
    },
    "Fréquence de rafraîchissement :": {
        "fr": "Fréquence de rafraîchissement :",
        "en": "Refresh frequency:",
    },
    "Toutes les 6 heures": {
        "fr": "Toutes les 6 heures",
        "en": "Every 6 hours",
    },
    "Toutes les 12 heures": {
        "fr": "Toutes les 12 heures",
        "en": "Every 12 hours",
    },
    "Toutes les 24 heures": {
        "fr": "Toutes les 24 heures",
        "en": "Every 24 hours",
    },
    "Toutes les 48 heures": {
        "fr": "Toutes les 48 heures",
        "en": "Every 48 hours",
    },
    "Hebdomadaire (7 jours)": {
        "fr": "Hebdomadaire (7 jours)",
        "en": "Weekly (7 days)",
    },
    "Mettre à jour l'EPG maintenant": {
        "fr": "Mettre à jour l'EPG maintenant",
        "en": "Update EPG now",
    },
    "Vider le cache EPG": {
        "fr": "Vider le cache EPG",
        "en": "Clear EPG cache",
    },

    # Onglet Données & Stockage
    "Données & Cache": {
        "fr": "Données & Cache",
        "en": "Data & Cache",
    },
    "Gérez l'espace disque utilisé par les logos, les vignettes et la base de données.": {
        "fr": "Gérez l'espace disque utilisé par les logos, les vignettes et la base de données.",
        "en": "Manage disk space used by logos, thumbnails and database.",
    },
    "Mise en cache des logos :": {
        "fr": "Mise en cache des logos :",
        "en": "Logo caching:",
    },
    "Sauvegarder les logos de chaînes sur le disque": {
        "fr": "Sauvegarder les logos de chaînes sur le disque",
        "en": "Save channel logos locally to disk",
    },
    "Vider le cache des logos": {
        "fr": "Vider le cache des logos",
        "en": "Clear logos cache",
    },
    "Optimiser la base de données": {
        "fr": "Optimiser la base de données",
        "en": "Optimize database",
    },
    "Réinitialiser l'application": {
        "fr": "Réinitialiser l'application",
        "en": "Reset application",
    },

    # Onglet Sauvegarde & Synchronisation
    "Synchronisation & Sauvegarde": {
        "fr": "Synchronisation & Sauvegarde",
        "en": "Sync & Backup",
    },
    "Synchronisez vos paramètres, favoris et listes avec un dossier cloud (Dropbox, Drive, etc.).": {
        "fr": "Synchronisez vos paramètres, favoris et listes avec un dossier cloud (Dropbox, Drive, etc.).",
        "en": "Sync your settings, favorites and playlists with a cloud folder (Dropbox, Drive, etc.).",
    },
    "Synchronisation automatique :": {
        "fr": "Synchronisation automatique :",
        "en": "Automatic sync:",
    },
    "Activer la synchronisation avec un dossier externe": {
        "fr": "Activer la synchronisation avec un dossier externe",
        "en": "Enable synchronization with an external folder",
    },
    "Dossier de synchronisation :": {
        "fr": "Dossier de synchronisation :",
        "en": "Sync folder:",
    },
    "Parcourir...": {
        "fr": "Parcourir...",
        "en": "Browse...",
    },
    "Exporter la sauvegarde": {
        "fr": "Exporter la sauvegarde",
        "en": "Export backup",
    },
    "Importer une sauvegarde": {
        "fr": "Importer une sauvegarde",
        "en": "Import backup",
    },

    # Onglet À propos
    "À propos de IPTV Hub": {
        "fr": "À propos de IPTV Hub",
        "en": "About IPTV Hub",
    },
    "Lecteur IPTV et VOD moderne, performant et élégant pour Windows & Linux.": {
        "fr": "Lecteur IPTV et VOD moderne, performant et élégant pour Windows & Linux.",
        "en": "Modern, fast and elegant IPTV and VOD player for Windows & Linux.",
    },
    "Version": {
        "fr": "Version",
        "en": "Version",
    },
    "Licence": {
        "fr": "Licence",
        "en": "License",
    },
    "Auteur": {
        "fr": "Auteur",
        "en": "Author",
    },
    "Dépôt GitHub": {
        "fr": "Dépôt GitHub",
        "en": "GitHub Repository",
    },

    # ---------------------------------------------------------
    # Dialogues (Ajout de liste, Gestion des listes, Artiste)
    # ---------------------------------------------------------
    "Ajouter une liste": {
        "fr": "Ajouter une liste",
        "en": "Add Playlist",
    },
    "Nom de la liste :": {
        "fr": "Nom de la liste :",
        "en": "Playlist name:",
    },
    "Type de liste :": {
        "fr": "Type de liste :",
        "en": "Playlist type:",
    },
    "Fichier ou URL M3U": {
        "fr": "Fichier ou URL M3U",
        "en": "M3U File or URL",
    },
    "API Xtream Codes": {
        "fr": "API Xtream Codes",
        "en": "Xtream Codes API",
    },
    "URL ou Chemin :": {
        "fr": "URL ou Chemin :",
        "en": "URL or Path:",
    },
    "Serveur (URL) :": {
        "fr": "Serveur (URL) :",
        "en": "Server (URL):",
    },
    "Nom d'utilisateur :": {
        "fr": "Nom d'utilisateur :",
        "en": "Username:",
    },
    "Mot de passe :": {
        "fr": "Mot de passe :",
        "en": "Password:",
    },
    "URL EPG personnalisée (optionnel) :": {
        "fr": "URL EPG personnalisée (optionnel) :",
        "en": "Custom EPG URL (optional):",
    },
    "Annuler": {
        "fr": "Annuler",
        "en": "Cancel",
    },
    "Ajouter": {
        "fr": "Ajouter",
        "en": "Add",
    },
    "Enregistrer": {
        "fr": "Enregistrer",
        "en": "Save",
    },
    "Supprimer": {
        "fr": "Supprimer",
        "en": "Delete",
    },
    "Modifier": {
        "fr": "Modifier",
        "en": "Edit",
    },
    "Actualiser": {
        "fr": "Actualiser",
        "en": "Refresh",
    },
    "Fermer la fenêtre": {
        "fr": "Fermer la fenêtre",
        "en": "Close window",
    },
    "Gestion des listes de lecture": {
        "fr": "Gestion des listes de lecture",
        "en": "Playlist Management",
    },
    "Êtes-vous sûr de vouloir supprimer cette liste ?": {
        "fr": "Êtes-vous sûr de vouloir supprimer cette liste ?",
        "en": "Are you sure you want to delete this playlist?",
    },
    "Confirmation": {
        "fr": "Confirmation",
        "en": "Confirmation",
    },
    "Oui": {
        "fr": "Oui",
        "en": "Yes",
    },
    "Non": {
        "fr": "Non",
        "en": "No",
    },
    "Filmographie de {artist}": {
        "fr": "Filmographie de {artist}",
        "en": "Filmography of {artist}",
    },
    "Aucun titre trouvé pour cet artiste.": {
        "fr": "Aucun titre trouvé pour cet artiste.",
        "en": "No titles found for this artist.",
    },
    "Films ({count})": {
        "fr": "Films ({count})",
        "en": "Movies ({count})",
    },
    "Séries ({count})": {
        "fr": "Séries ({count})",
        "en": "Series ({count})",
    },

    # ---------------------------------------------------------
    # Tableau de bord & Récemment ajoutés
    # ---------------------------------------------------------
    "Récemment ajoutés sur {name}": {
        "fr": "Récemment ajoutés sur {name}",
        "en": "Recently added on {name}",
    },
    "Récemment ajoutés": {
        "fr": "Récemment ajoutés",
        "en": "Recently Added",
    },
    "Films récemment ajoutés": {
        "fr": "Films récemment ajoutés",
        "en": "Recently Added Movies",
    },
    "Séries récemment ajoutées": {
        "fr": "Séries récemment ajoutées",
        "en": "Recently Added Series",
    },
    "Parcourir tous les films >": {
        "fr": "Parcourir tous les films >",
        "en": "Browse all movies >",
    },
    "Parcourir toutes les séries >": {
        "fr": "Parcourir toutes les séries >",
        "en": "Browse all series >",
    },
    "Parcourir toute la TV en direct >": {
        "fr": "Parcourir toute la TV en direct >",
        "en": "Browse all live TV >",
    },

    # ---------------------------------------------------------
    # Favoris & Récemment regardés
    # ---------------------------------------------------------
    "Cette liste de lecture": {
        "fr": "Cette liste de lecture",
        "en": "This playlist",
    },
    "  Cette liste de lecture": {
        "fr": "  Cette liste de lecture",
        "en": "  This playlist",
    },
    "Toutes les listes de lecture": {
        "fr": "Toutes les listes de lecture",
        "en": "All playlists",
    },
    "  Toutes les listes de lecture": {
        "fr": "  Toutes les listes de lecture",
        "en": "  All playlists",
    },
    "Récemment regardés": {
        "fr": "Récemment regardés",
        "en": "Recently Watched",
    },
    "Vider tous les favoris affichés": {
        "fr": "Vider tous les favoris affichés",
        "en": "Clear all displayed favorites",
    },

    # ---------------------------------------------------------
    # Dates relatives et jours
    # ---------------------------------------------------------
    "Aujourd'hui": {
        "fr": "Aujourd'hui",
        "en": "Today",
    },
    "Hier": {
        "fr": "Hier",
        "en": "Yesterday",
    },
    "Demain": {
        "fr": "Demain",
        "en": "Tomorrow",
    },
    "Aujourd'hui, {time}": {
        "fr": "Aujourd'hui, {time}",
        "en": "Today, {time}",
    },
    "Hier, {time}": {
        "fr": "Hier, {time}",
        "en": "Yesterday, {time}",
    },

    # ---------------------------------------------------------
    # Guide des programmes (EPG)
    # ---------------------------------------------------------
    "Guide des Programmes (EPG)": {
        "fr": "Guide des Programmes (EPG)",
        "en": "Electronic Program Guide (EPG)",
    },
    "Guide des programmes": {
        "fr": "Guide des programmes",
        "en": "TV Guide",
    },
    "Aller à maintenant": {
        "fr": "Aller à maintenant",
        "en": "Go to Now",
    },
    " Aller à maintenant": {
        "fr": " Aller à maintenant",
        "en": " Go to Now",
    },
    "🕒 Maintenant": {
        "fr": "🕒 Maintenant",
        "en": "🕒 Now",
    },
    "Centrer la frise sur l'heure actuelle": {
        "fr": "Centrer la frise sur l'heure actuelle",
        "en": "Center timeline on current time",
    },
    "Rechercher une chaîne...": {
        "fr": "Rechercher une chaîne...",
        "en": "Search a channel...",
    },
    "Gérer et filtrer les catégories et chaînes": {
        "fr": "Gérer et filtrer les catégories et chaînes",
        "en": "Manage and filter categories and channels",
    },
    "Zoomer la frise temporelle": {
        "fr": "Zoomer la frise temporelle",
        "en": "Zoom in timeline",
    },
    "Dézoomer la frise temporelle": {
        "fr": "Dézoomer la frise temporelle",
        "en": "Zoom out timeline",
    },
    "CHAÎNES": {
        "fr": "CHAÎNES",
        "en": "CHANNELS",
    },
    "Sélectionnez une émission": {
        "fr": "Sélectionnez une émission",
        "en": "Select a show",
    },
    "Aucun programme sélectionné": {
        "fr": "Aucun programme sélectionné",
        "en": "No program selected",
    },
    "Cliquez sur un programme dans la grille ci-dessous pour voir ses détails ou double-cliquez pour regarder la chaîne.": {
        "fr": "Cliquez sur un programme dans la grille ci-dessous pour voir ses détails ou double-cliquez pour regarder la chaîne.",
        "en": "Click on a show in the grid below to view details or double-click to watch the channel.",
    },
    "Cliquez sur un programme dans la grille ci-dessous pour voir ses détails.": {
        "fr": "Cliquez sur un programme dans la grille ci-dessous pour voir ses détails.",
        "en": "Click on a show in the grid below to view its details.",
    },
    "Regarder la chaîne": {
        "fr": "Regarder la chaîne",
        "en": "Watch channel",
    },
    " Regarder la chaîne": {
        "fr": " Regarder la chaîne",
        "en": " Watch channel",
    },
    "EN DIRECT": {
        "fr": "EN DIRECT",
        "en": "LIVE",
    },
    "Durée : {dur}": {
        "fr": "Durée : {dur}",
        "en": "Duration: {dur}",
    },
    "Guide indisponible": {
        "fr": "Guide indisponible",
        "en": "Guide unavailable",
    },
    "Aucune information de programme EPG trouvée pour {channel}.": {
        "fr": "Aucune information de programme EPG trouvée pour {channel}.",
        "en": "No EPG program information found for {channel}.",
    },
    "Aucun synopsis détaillé n'est fourni pour cette émission.": {
        "fr": "Aucun synopsis détaillé n'est fourni pour cette émission.",
        "en": "No detailed synopsis is provided for this show.",
    },
    "ℹ Programme uniquement. Ce fournisseur expose l'historique mais pas le catch-up.": {
        "fr": "ℹ Programme uniquement. Ce fournisseur expose l'historique mais pas le catch-up.",
        "en": "ℹ Schedule only. This provider exposes history but not catch-up playback.",
    },

    # ---------------------------------------------------------
    # Section Replay
    # ---------------------------------------------------------
    "Revoyez vos émissions préférées des 7 derniers jours sur les chaînes compatibles.": {
        "fr": "Revoyez vos émissions préférées des 7 derniers jours sur les chaînes compatibles.",
        "en": "Watch your favorite shows from the last 7 days on supported channels.",
    },
    "0 chaîne compatible Replay": {
        "fr": "0 chaîne compatible Replay",
        "en": "0 replay-compatible channel",
    },
    "{count} chaînes compatibles Replay": {
        "fr": "{count} chaînes compatibles Replay",
        "en": "{count} replay-compatible channels",
    },
    "{count} chaîne compatible": {
        "fr": "{count} chaîne compatible",
        "en": "{count} compatible channel",
    },
    "{count} chaînes compatibles": {
        "fr": "{count} chaînes compatibles",
        "en": "{count} compatible channels",
    },
    "Filtrer les chaînes...": {
        "fr": "Filtrer les chaînes...",
        "en": "Filter channels...",
    },
    "Sélectionnez une chaîne pour voir les programmes": {
        "fr": "Sélectionnez une chaîne pour voir les programmes",
        "en": "Select a channel to view programs",
    },
    "Programmes : {name}": {
        "fr": "Programmes : {name}",
        "en": "Programs: {name}",
    },
    "Aucune chaîne avec Replay disponible.": {
        "fr": "Aucune chaîne avec Replay disponible.",
        "en": "No channels with Replay available.",
    },
    "Chargement du guide...": {
        "fr": "Chargement du guide...",
        "en": "Loading guide...",
    },
    "Replay disponible uniquement sur les flux Xtream.": {
        "fr": "Replay disponible uniquement sur les flux Xtream.",
        "en": "Replay available only on Xtream streams.",
    },
    "Impossible de charger les programmes d'archive.": {
        "fr": "Impossible de charger les programmes d'archive.",
        "en": "Unable to load archive programs.",
    },
    "Aucun programme répertorié pour cette chaîne.": {
        "fr": "Aucun programme répertorié pour cette chaîne.",
        "en": "No programs listed for this channel.",
    },
    "0 programme": {
        "fr": "0 programme",
        "en": "0 program",
    },
    "{count} programme": {
        "fr": "{count} programme",
        "en": "{count} program",
    },
    "{count} programmes": {
        "fr": "{count} programmes",
        "en": "{count} programs",
    },
    "Aucun programme trouvé pour le {date}.": {
        "fr": "Aucun programme trouvé pour le {date}.",
        "en": "No programs found for {date}.",
    },
    "0 émission trouvée": {
        "fr": "0 émission trouvée",
        "en": "0 show found",
    },
    "{count} émission(s) trouvée(s)": {
        "fr": "{count} émission(s) trouvée(s)",
        "en": "{count} show(s) found",
    },
    "Revoir": {
        "fr": "Revoir",
        "en": "Watch",
    },
    " Revoir": {
        "fr": " Revoir",
        "en": " Watch",
    },
    "À venir": {
        "fr": "À venir",
        "en": "Upcoming",
    },
    "Sans titre": {
        "fr": "Sans titre",
        "en": "Untitled",
    },

    # ---------------------------------------------------------
    # Récemment ajoutés (Recently Added)
    # ---------------------------------------------------------
    "Récemment ajoutés": {
        "fr": "Récemment ajoutés",
        "en": "Recently Added",
    },
    "Films récemment ajoutés": {
        "fr": "Films récemment ajoutés",
        "en": "Recently added movies",
    },
    "Séries récemment ajoutées": {
        "fr": "Séries récemment ajoutées",
        "en": "Recently added series",
    },
    "Parcourir tous les films >": {
        "fr": "Parcourir tous les films >",
        "en": "Browse all movies >",
    },
    "Parcourir toutes les séries >": {
        "fr": "Parcourir toutes les séries >",
        "en": "Browse all series >",
    },
    "Parcourir toute la TV en direct >": {
        "fr": "Parcourir toute la TV en direct >",
        "en": "Browse all live TV >",
    },
    "Aucun élément récent dans {category}.": {
        "fr": "Aucun élément récent dans {category}.",
        "en": "No recent items in {category}.",
    },

    # ---------------------------------------------------------
    # Panneau des Catégories & Titres Live / Films / Séries
    # ---------------------------------------------------------
    "Catégories en direct": {
        "fr": "Catégories en direct",
        "en": "Live Categories",
    },
    "Catégories de films": {
        "fr": "Catégories de films",
        "en": "Movie Categories",
    },
    "Catégories Séries": {
        "fr": "Catégories Séries",
        "en": "Series Categories",
    },
    "Catégories Favoris": {
        "fr": "Catégories Favoris",
        "en": "Favorite Categories",
    },
    "Rechercher une catégorie": {
        "fr": "Rechercher une catégorie",
        "en": "Search a category",
    },
    "Gérer et filtrer les catégories": {
        "fr": "Gérer et filtrer les catégories",
        "en": "Manage and filter categories",
    },
    "Gérer les catégories": {
        "fr": "Gérer les catégories",
        "en": "Manage Categories",
    },
    "Tout sélectionner": {
        "fr": "Tout sélectionner",
        "en": "Select all",
    },
    " Tout sélectionner": {
        "fr": " Tout sélectionner",
        "en": " Select all",
    },
    "Tout désélectionner": {
        "fr": "Tout désélectionner",
        "en": "Deselect all",
    },
    " Tout désélectionner": {
        "fr": " Tout désélectionner",
        "en": " Deselect all",
    },
    "Rechercher des catégories ou des chaînes...": {
        "fr": "Rechercher des catégories ou des chaînes...",
        "en": "Search categories or channels...",
    },
    "Sélectionnées: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} groupes)": {
        "fr": "Sélectionnées: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} groupes)",
        "en": "Selected: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} groups)",
    },
    "Sélectionnées: 0 / 0 (0 / 0 groupes)": {
        "fr": "Sélectionnées: 0 / 0 (0 / 0 groupes)",
        "en": "Selected: 0 / 0 (0 / 0 groups)",
    },

    # ---------------------------------------------------------
    # Gestion des listes de lecture
    # ---------------------------------------------------------
    "Gestion des listes de lecture": {
        "fr": "Gestion des listes de lecture",
        "en": "Manage Playlists",
    },
    "Listes de lecture enregistrées": {
        "fr": "Listes de lecture enregistrées",
        "en": "Saved playlists",
    },
    "Synchronisation de '{name}' en cours...": {
        "fr": "Synchronisation de '{name}' en cours...",
        "en": "Syncing '{name}'...",
    },
    "Synchronisation réussie !": {
        "fr": "Synchronisation réussie !",
        "en": "Sync successful!",
    },
    "Erreur de synchronisation": {
        "fr": "Erreur de synchronisation",
        "en": "Sync error",
    },
    "Impossible de synchroniser la liste :\n{error}": {
        "fr": "Impossible de synchroniser la liste :\n{error}",
        "en": "Unable to sync playlist:\n{error}",
    },
    "Confirmer la suppression": {
        "fr": "Confirmer la suppression",
        "en": "Confirm deletion",
    },
    "Êtes-vous sûr de vouloir supprimer cette liste de lecture et toutes ses chaînes de SQLite ?": {
        "fr": "Êtes-vous sûr de vouloir supprimer cette liste de lecture et toutes ses chaînes de SQLite ?",
        "en": "Are you sure you want to delete this playlist and all its channels from SQLite?",
    },
    "Inactif": {
        "fr": "Inactif",
        "en": "Inactive",
    },
    "Écrans : {active} / {max}": {
        "fr": "Écrans : {active} / {max}",
        "en": "Screens: {active} / {max}",
    },
    "Expiration : {date}": {
        "fr": "Expiration : {date}",
        "en": "Expiration: {date}",
    },
    "Ajouter une liste": {
        "fr": "Ajouter une liste",
        "en": "Add a playlist",
    },
    " Ajouter une liste": {
        "fr": " Ajouter une liste",
        "en": " Add a playlist",
    },
    "Fermer": {
        "fr": "Fermer",
        "en": "Close",
    },
    " Fermer": {
        "fr": " Fermer",
        "en": " Close",
    },
    " Recharger": {
        "fr": " Recharger",
        "en": " Reload",
    },
    " Modifier": {
        "fr": " Modifier",
        "en": " Edit",
    },
    " Supprimer": {
        "fr": " Supprimer",
        "en": " Delete",
    },
    "Recharger et synchroniser les flux depuis le serveur": {
        "fr": "Recharger et synchroniser les flux depuis le serveur",
        "en": "Reload and sync streams from server",
    },
    "Modifier les identifiants ou l'URL de cette liste": {
        "fr": "Modifier les identifiants ou l'URL de cette liste",
        "en": "Edit credentials or URL of this playlist",
    },
    "Supprimer cette liste de lecture et ses chaînes de SQLite": {
        "fr": "Supprimer cette liste de lecture et ses chaînes de SQLite",
        "en": "Delete this playlist and its channels from SQLite",
    },
    "Source : {source}": {
        "fr": "Source : {source}",
        "en": "Source: {source}",
    },
    "chaînes TV": {
        "fr": "chaînes TV",
        "en": "TV channels",
    },
    "films": {
        "fr": "films",
        "en": "movies",
    },
    "séries": {
        "fr": "séries",
        "en": "series",
    },
    "chaînes": {
        "fr": "chaînes",
        "en": "channels",
    },
    "Statut": {
        "fr": "Statut",
        "en": "Status",
    },
    "Statut : {status}": {
        "fr": "Statut : {status}",
        "en": "Status: {status}",
    },
    "Expiration": {
        "fr": "Expiration",
        "en": "Expiration",
    },
    "Expire : {date}": {
        "fr": "Expire : {date}",
        "en": "Expires: {date}",
    },
    "Connexions": {
        "fr": "Connexions",
        "en": "Connections",
    },
    "Connexions : {active}/{max}": {
        "fr": "Connexions : {active}/{max}",
        "en": "Connections: {active}/{max}",
    },
    "Illimitée": {
        "fr": "Illimitée",
        "en": "Unlimited",
    },
    "Expiré": {
        "fr": "Expiré",
        "en": "Expired",
    },
    "Expiré ({date})": {
        "fr": "Expiré ({date})",
        "en": "Expired ({date})",
    },
    "{days} j restants": {
        "fr": "{days} j restants",
        "en": "{days} d remaining",
    },
    "Inconnue": {
        "fr": "Inconnue",
        "en": "Unknown",
    },
    "Inconnu": {
        "fr": "Inconnu",
        "en": "Unknown",
    },
    "Actif": {
        "fr": "Actif",
        "en": "Active",
    },
    "Aucune liste de lecture enregistrée dans la base SQLite.\nCliquez sur 'Ajouter une liste' pour importer vos chaînes Xtream ou M3U.": {
        "fr": "Aucune liste de lecture enregistrée dans la base SQLite.\nCliquez sur 'Ajouter une liste' pour importer vos chaînes Xtream ou M3U.",
        "en": "No playlists saved in SQLite database.\nClick 'Add a playlist' to import your Xtream or M3U channels.",
    },

    # ---------------------------------------------------------
    # Fiches détaillées Films & Séries
    # ---------------------------------------------------------
    "FICHE DU FILM": {
        "fr": "FICHE DU FILM",
        "en": "MOVIE DETAILS",
    },
    "FICHE DE LA SÉRIE": {
        "fr": "FICHE DE LA SÉRIE",
        "en": "SERIES DETAILS",
    },
    "Retour à la galerie de films": {
        "fr": "Retour à la galerie de films",
        "en": "Back to movie gallery",
    },
    "Retour à la galerie de séries": {
        "fr": "Retour à la galerie de séries",
        "en": "Back to series gallery",
    },
    "Titre du film": {
        "fr": "Titre du film",
        "en": "Movie Title",
    },
    "Titre de la série": {
        "fr": "Titre de la série",
        "en": "Series Title",
    },
    "Chargement des informations...": {
        "fr": "Chargement des informations...",
        "en": "Loading information...",
    },
    "Aucun résumé disponible pour ce film.": {
        "fr": "Aucun résumé disponible pour ce film.",
        "en": "No synopsis available for this movie.",
    },
    "Aucune description disponible.": {
        "fr": "Aucune description disponible.",
        "en": "No description available.",
    },
    "Prêt pour le streaming en haute définition.": {
        "fr": "Prêt pour le streaming en haute définition.",
        "en": "Ready for high definition streaming.",
    },
    "Regarder le film": {
        "fr": "Regarder le film",
        "en": "Watch movie",
    },
    "  Regarder le film": {
        "fr": "  Regarder le film",
        "en": "  Watch movie",
    },
    "Lancer la lecture": {
        "fr": "Lancer la lecture",
        "en": "Start watching",
    },
    "  Lancer la lecture": {
        "fr": "  Lancer la lecture",
        "en": "  Start watching",
    },
    "Reprendre l'épisode": {
        "fr": "Reprendre l'épisode",
        "en": "Resume episode",
    },
    "  Reprendre l'épisode": {
        "fr": "  Reprendre l'épisode",
        "en": "  Resume episode",
    },
    "Du début": {
        "fr": "Du début",
        "en": "From beginning",
    },
    "  Du début": {
        "fr": "  Du début",
        "en": "  From beginning",
    },
    "Annuler reprise": {
        "fr": "Annuler reprise",
        "en": "Clear resume",
    },
    "  Annuler reprise": {
        "fr": "  Annuler reprise",
        "en": "  Clear resume",
    },
    "Ajouter aux favoris": {
        "fr": "Ajouter aux favoris",
        "en": "Add to favorites",
    },
    "  Ajouter aux favoris": {
        "fr": "  Ajouter aux favoris",
        "en": "  Add to favorites",
    },
    "Retirer des favoris": {
        "fr": "Retirer des favoris",
        "en": "Remove from favorites",
    },
    "  Retirer des favoris": {
        "fr": "  Retirer des favoris",
        "en": "  Remove from favorites",
    },
    "Télécharger": {
        "fr": "Télécharger",
        "en": "Download",
    },
    "  Télécharger": {
        "fr": "  Télécharger",
        "en": "  Download",
    },
    "Téléchargement...": {
        "fr": "Téléchargement...",
        "en": "Downloading...",
    },
    "  Téléchargement...": {
        "fr": "  Téléchargement...",
        "en": "  Downloading...",
    },
    "✓ Téléchargé": {
        "fr": "✓ Téléchargé",
        "en": "✓ Downloaded",
    },
    "  ✓ Téléchargé": {
        "fr": "  ✓ Téléchargé",
        "en": "  ✓ Downloaded",
    },
    "Genre :": {
        "fr": "Genre :",
        "en": "Genre:",
    },
    "Durée :": {
        "fr": "Durée :",
        "en": "Duration:",
    },
    "Réalisateur :": {
        "fr": "Réalisateur :",
        "en": "Director:",
    },
    "Acteurs :": {
        "fr": "Acteurs :",
        "en": "Actors:",
    },
    "Distribution :": {
        "fr": "Distribution :",
        "en": "Cast:",
    },
    "Synopsis :": {
        "fr": "Synopsis :",
        "en": "Synopsis:",
    },
    "Saisons et épisodes": {
        "fr": "Saisons et épisodes",
        "en": "Seasons and episodes",
    },
    "Saison {num}": {
        "fr": "Saison {num}",
        "en": "Season {num}",
    },
    "Épisode {num}": {
        "fr": "Épisode {num}",
        "en": "Episode {num}",
    },
    "Bande-annonce": {
        "fr": "Bande-annonce",
        "en": "Trailer",
    },
    "Bande-annonce du film": {
        "fr": "Bande-annonce du film",
        "en": "Movie trailer",
    },
    "Bande-annonce de la série": {
        "fr": "Bande-annonce de la série",
        "en": "Series trailer",
    },
    "Bande-annonce d'origine": {
        "fr": "Bande-annonce d'origine",
        "en": "Original trailer",
    },
    "Regarder sur YouTube": {
        "fr": "Regarder sur YouTube",
        "en": "Watch on YouTube",
    },
    "Cliquer pour regarder la bande-annonce dans l'application": {
        "fr": "Cliquer pour regarder la bande-annonce dans l'application",
        "en": "Click to watch trailer inside application",
    },
    "Ouvrir la bande-annonce sur YouTube dans le navigateur": {
        "fr": "Ouvrir la bande-annonce sur YouTube dans le navigateur",
        "en": "Open trailer on YouTube in external browser",
    },
    "Tout marquer comme vu": {
        "fr": "Tout marquer comme vu",
        "en": "Mark all as watched",
    },
    "Réinitialiser la saison": {
        "fr": "Réinitialiser la saison",
        "en": "Reset season",
    },

    # ---------------------------------------------------------
    # Recherche & Filmographie d'artiste
    # ---------------------------------------------------------
    "Artiste": {
        "fr": "Artiste",
        "en": "Artist",
    },
    " Artiste": {
        "fr": " Artiste",
        "en": " Artist",
    },
    "Rechercher un acteur ou réalisateur (expérimental)": {
        "fr": "Rechercher un acteur ou réalisateur (expérimental)",
        "en": "Search an actor or director (experimental)",
    },
    "Voir la filmographie": {
        "fr": "Voir la filmographie",
        "en": "View filmography",
    },
    " Voir la filmographie": {
        "fr": " Voir la filmographie",
        "en": " View filmography",
    },
    "Rechercher \"{query}\" parmi les artistes": {
        "fr": "Rechercher \"{query}\" parmi les artistes",
        "en": "Search \"{query}\" among artists",
    },
    " Rechercher \"{query}\" parmi les artistes": {
        "fr": " Rechercher \"{query}\" parmi les artistes",
        "en": " Search \"{query}\" among artists",
    },
    "Filmographie de l'artiste": {
        "fr": "Filmographie de l'artiste",
        "en": "Artist filmography",
    },
    "Recherche des informations sur TMDB...": {
        "fr": "Recherche des informations sur TMDB...",
        "en": "Searching information on TMDB...",
    },
    "Recherche des titres disponibles dans votre abonnement IPTV...": {
        "fr": "Recherche des titres disponibles dans votre abonnement IPTV...",
        "en": "Searching available titles in your IPTV subscription...",
    },
    "Films disponibles ({count})": {
        "fr": "Films disponibles ({count})",
        "en": "Available Movies ({count})",
    },
    "Séries disponibles ({count})": {
        "fr": "Séries disponibles ({count})",
        "en": "Available Series ({count})",
    },
    "Aucun titre disponible trouvé dans votre bibliothèque IPTV.": {
        "fr": "Aucun titre disponible trouvé dans votre bibliothèque IPTV.",
        "en": "No available titles found in your IPTV library.",
    },
    "Aucune information trouvée pour '{name}' sur TMDB.": {
        "fr": "Aucune information trouvée pour '{name}' sur TMDB.",
        "en": "No information found for '{name}' on TMDB.",
    },

    # ---------------------------------------------------------
    # Paramètres - Cartes & Options intérieures
    # ---------------------------------------------------------
    "Général & Apparence": {
        "fr": "Général & Apparence",
        "en": "General & Appearance",
    },
    "Personnalisez l'affichage, le comportement au démarrage et l'interface utilisateur.": {
        "fr": "Personnalisez l'affichage, le comportement au démarrage et l'interface utilisateur.",
        "en": "Customize display, startup behavior and user interface.",
    },
    "Langue de l'application :": {
        "fr": "Langue de l'application :",
        "en": "Application Language:",
    },
    "Thème de l'interface :": {
        "fr": "Thème de l'interface :",
        "en": "Interface Theme:",
    },
    "Gris foncé bleuté (Par défaut)": {
        "fr": "Gris foncé bleuté (Par défaut)",
        "en": "Bluish Dark Grey (Default)",
    },
    "Sombre moderne": {
        "fr": "Sombre moderne",
        "en": "Modern Dark",
    },
    "Langue audio préférée (Films & Séries) :": {
        "fr": "Langue audio préférée (Films & Séries) :",
        "en": "Preferred Audio Language (Movies & Series):",
    },
    "Masquage auto de l'OSD :": {
        "fr": "Masquage auto de l'OSD :",
        "en": "Auto-hide OSD:",
    },
    "{n} secondes": {
        "fr": "{n} secondes",
        "en": "{n} seconds",
    },
    "Afficher la date d'ajout sur les affiches (VOD & Séries)": {
        "fr": "Afficher la date d'ajout sur les affiches (VOD & Séries)",
        "en": "Show addition date on posters (VOD & Series)",
    },
    "Affiche un discret badge en bas à droite indiquant la date d'ajout du film ou de la série": {
        "fr": "Affiche un discret badge en bas à droite indiquant la date d'ajout du film ou de la série",
        "en": "Displays a discreet badge at bottom right showing the movie or series addition date",
    },
    "Afficher la vignette de la chaîne dans la liste en direct": {
        "fr": "Afficher la vignette de la chaîne dans la liste en direct",
        "en": "Show channel thumbnail in live list",
    },
    "Lecteur Vidéo & Rendu": {
        "fr": "Lecteur Vidéo & Rendu",
        "en": "Video Player & Rendering",
    },
    "Configurez le moteur de lecture libmpv, l'accélération matérielle et le comportement vidéo.": {
        "fr": "Configurez le moteur de lecture libmpv, l'accélération matérielle et le comportement vidéo.",
        "en": "Configure libmpv playback engine, hardware acceleration and video behavior.",
    },
    "Accélération matérielle :": {
        "fr": "Accélération matérielle :",
        "en": "Hardware Acceleration:",
    },
    "Automatique (Recommandé)": {
        "fr": "Automatique (Recommandé)",
        "en": "Automatic (Recommended)",
    },
    "Désactivée (Logicielle)": {
        "fr": "Désactivée (Logicielle)",
        "en": "Disabled (Software)",
    },
    "Direct3D 11 (d3d11va)": {
        "fr": "Direct3D 11 (d3d11va)",
        "en": "Direct3D 11 (d3d11va)",
    },
    "Format des sous-titres :": {
        "fr": "Format des sous-titres :",
        "en": "Subtitles Format:",
    },
    "Enchaîner automatiquement sur l'épisode suivant (Séries)": {
        "fr": "Enchaîner automatiquement sur l'épisode suivant (Séries)",
        "en": "Automatically play next episode (Series)",
    },
    "Passe immédiatement à l'épisode suivant lorsque le fichier en cours atteint sa fin": {
        "fr": "Passe immédiatement à l'épisode suivant lorsque le fichier en cours atteint sa fin",
        "en": "Immediately advances to next episode when the current episode ends",
    },
    "Reprendre automatiquement la lecture où vous l'avez laissée": {
        "fr": "Reprendre automatiquement la lecture où vous l'avez laissée",
        "en": "Automatically resume playback where you left off",
    },
    "Réseau & Performance": {
        "fr": "Réseau & Performance",
        "en": "Network & Performance",
    },
    "Optimisez le streaming, la mémoire tampon et la stabilité de votre connexion.": {
        "fr": "Optimisez le streaming, la mémoire tampon et la stabilité de votre connexion.",
        "en": "Optimize streaming, buffer size and connection stability.",
    },
    "Taille du tampon réseau :": {
        "fr": "Taille du tampon réseau :",
        "en": "Network Buffer Size:",
    },
    "Délai d'attente réseau (Timeout) :": {
        "fr": "Délai d'attente réseau (Timeout) :",
        "en": "Network Timeout:",
    },
    "Agent utilisateur (User-Agent HTTP) :": {
        "fr": "Agent utilisateur (User-Agent HTTP) :",
        "en": "User-Agent (HTTP User-Agent):",
    },
    "Guide TV & EPG": {
        "fr": "Guide TV & EPG",
        "en": "TV Guide & EPG",
    },
    "Gérez la synchronisation, les sources XMLTV et la fréquence d'actualisation des programmes.": {
        "fr": "Gérez la synchronisation, les sources XMLTV et la fréquence d'actualisation des programmes.",
        "en": "Manage synchronization, XMLTV sources and program refresh interval.",
    },
    "Fréquence de rafraîchissement de l'EPG :": {
        "fr": "Fréquence de rafraîchissement de l'EPG :",
        "en": "EPG Refresh Interval:",
    },
    "Toutes les 6 heures": {
        "fr": "Toutes les 6 heures",
        "en": "Every 6 hours",
    },
    "Toutes les 12 heures": {
        "fr": "Toutes les 12 heures",
        "en": "Every 12 hours",
    },
    "Toutes les 24 heures": {
        "fr": "Toutes les 24 heures",
        "en": "Every 24 hours",
    },
    "Au démarrage de l'application uniquement": {
        "fr": "Au démarrage de l'application uniquement",
        "en": "At application startup only",
    },
    "Activer le décalage horaire automatique de l'EPG": {
        "fr": "Activer le décalage horaire automatique de l'EPG",
        "en": "Enable automatic EPG timezone offset",
    },
    "Stockage & Cache": {
        "fr": "Stockage & Cache",
        "en": "Storage & Cache",
    },
    "Gérez l'espace disque, le cache des logos et les données hors-ligne.": {
        "fr": "Gérez l'espace disque, le cache des logos et les données hors-ligne.",
        "en": "Manage disk space, logo cache and offline data.",
    },
    "Vider le cache d'images": {
        "fr": "Vider le cache d'images",
        "en": "Clear image cache",
    },
    "Répertoire des téléchargements :": {
        "fr": "Répertoire des téléchargements :",
        "en": "Download Directory:",
    },
    "Parcourir...": {
        "fr": "Parcourir...",
        "en": "Browse...",
    },
    "Sauvegarde & Fichiers": {
        "fr": "Sauvegarde & Fichiers",
        "en": "Backup & Files",
    },
    "Exportez et importez vos préférences, vos listes et votre historique de lecture.": {
        "fr": "Exportez et importez vos préférences, vos listes et votre historique de lecture.",
        "en": "Export and import your preferences, playlists and watch history.",
    },
    "Exporter la base de données...": {
        "fr": "Exporter la base de données...",
        "en": "Export database...",
    },
    "Restaurer une sauvegarde...": {
        "fr": "Restaurer une sauvegarde...",
        "en": "Restore backup...",
    },
    "À propos": {
        "fr": "À propos",
        "en": "About",
    },
    "Informations sur IPTV Hub et licence.": {
        "fr": "Informations sur IPTV Hub et licence.",
        "en": "Information about IPTV Hub and license.",
    },
    "Lecteur multimédia moderne, élégant et ultra-rapide pour flux IPTV Xtream Codes et M3U.": {
        "fr": "Lecteur multimédia moderne, élégant et ultra-rapide pour flux IPTV Xtream Codes et M3U.",
        "en": "Modern, elegant and ultra-fast multimedia player for IPTV Xtream Codes and M3U streams.",
    },
    "Version installée :": {
        "fr": "Version installée :",
        "en": "Installed Version:",
    },
    "Moteur vidéo :": {
        "fr": "Moteur vidéo :",
        "en": "Video Engine:",
    },
    "Enregistrer les paramètres": {
        "fr": "Enregistrer les paramètres",
        "en": "Save settings",
    },
    " Enregistrer les paramètres": {
        "fr": " Enregistrer les paramètres",
        "en": " Save settings",
    },
    "Paramètres enregistrés avec succès !": {
        "fr": "Paramètres enregistrés avec succès !",
        "en": "Settings saved successfully!",
    },
    "Moteur de Lecture libmpv": {
        "fr": "Moteur de Lecture libmpv",
        "en": "libmpv Playback Engine",
    },
    "Options matérielles de décodage et de fluidité pour les flux HD/4K.": {
        "fr": "Options matérielles de décodage et de fluidité pour les flux HD/4K.",
        "en": "Hardware decoding and smoothness options for HD/4K streams.",
    },
    "Réseau & Streaming": {
        "fr": "Réseau & Streaming",
        "en": "Network & Streaming",
    },
    "Paramètres de connexion aux serveurs IPTV et entêtes HTTP.": {
        "fr": "Paramètres de connexion aux serveurs IPTV et entêtes HTTP.",
        "en": "IPTV server connection settings and HTTP headers.",
    },
    "Guide Électronique des Programmes (EPG)": {
        "fr": "Guide Électronique des Programmes (EPG)",
        "en": "Electronic Program Guide (EPG)",
    },
    "Fréquence de synchronisation et décalage horaire pour les programmes TV.": {
        "fr": "Fréquence de synchronisation et décalage horaire pour les programmes TV.",
        "en": "Sync frequency and timezone offset for TV programs.",
    },
    "Données, Téléchargements & Cache": {
        "fr": "Données, Téléchargements & Cache",
        "en": "Data, Downloads & Cache",
    },
    "Configuration du dossier de téléchargement des films VOD et gestion du cache local.": {
        "fr": "Configuration du dossier de téléchargement des films VOD et gestion du cache local.",
        "en": "Configuration of VOD download directory and local cache management.",
    },
    "Sauvegarde & Configuration": {
        "fr": "Sauvegarde & Configuration",
        "en": "Backup & Configuration",
    },
    "Enregistrez ou restaurez votre configuration complète sous forme de fichier. Vous pouvez facilement transférer ce fichier via une clé USB ou un dossier partagé vers un autre PC ou vers votre version Android TV.": {
        "fr": "Enregistrez ou restaurez votre configuration complète sous forme de fichier. Vous pouvez facilement transférer ce fichier via une clé USB ou un dossier partagé vers un autre PC ou vers votre version Android TV.",
        "en": "Save or restore your complete configuration as a file. Easily transfer this file via USB drive or shared folder to another PC or Android TV.",
    },
    "À propos d'IPTV Hub": {
        "fr": "À propos d'IPTV Hub",
        "en": "About IPTV Hub",
    },
    "Lecteur multimédia moderne pour flux IPTV, Xtream Codes, VOD et Séries.": {
        "fr": "Lecteur multimédia moderne pour flux IPTV, Xtream Codes, VOD et Séries.",
        "en": "Modern multimedia player for IPTV, Xtream Codes, VOD and Series.",
    },
    "Délai de masquage des contrôles vidéo :": {
        "fr": "Délai de masquage des contrôles vidéo :",
        "en": "Video controls auto-hide delay:",
    },
    "secondes": {
        "fr": "secondes",
        "en": "seconds",
    },
    " Reprendre automatiquement la dernière chaîne au lancement": {
        "fr": " Reprendre automatiquement la dernière chaîne au lancement",
        "en": " Automatically resume last channel on startup",
    },
    " Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)": {
        "fr": " Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)",
        "en": " Automatically play next episode when current episode finishes (Series)",
    },
    "Décodage matériel (HW Accel) :": {
        "fr": "Décodage matériel (HW Accel) :",
        "en": "Hardware Decoding (HW Accel):",
    },
    "Désentrelacement vidéo :": {
        "fr": "Désentrelacement vidéo :",
        "en": "Video Deinterlacing:",
    },
    "Taille du cache de préchargement :": {
        "fr": "Taille du cache de préchargement :",
        "en": "Preload Buffer Cache Size:",
    },
    "Mo": {
        "fr": "Mo",
        "en": "MB",
    },
    "User-Agent HTTP par défaut :": {
        "fr": "User-Agent HTTP par défaut :",
        "en": "Default HTTP User-Agent:",
    },
    "Ex: VLC/3.0.18 LibVLC/3.0.18 ou Mozilla/5.0...": {
        "fr": "Ex: VLC/3.0.18 LibVLC/3.0.18 ou Mozilla/5.0...",
        "en": "Ex: VLC/3.0.18 LibVLC/3.0.18 or Mozilla/5.0...",
    },
    " Reconnexion automatique en cas de coupure de flux": {
        "fr": " Reconnexion automatique en cas de coupure de flux",
        "en": " Automatically reconnect on stream interruption",
    },
    "Intervalle d'actualisation automatique :": {
        "fr": "Intervalle d'actualisation automatique :",
        "en": "Automatic Refresh Interval:",
    },
    "heures": {
        "fr": "heures",
        "en": "hours",
    },
    "Décalage horaire EPG :": {
        "fr": "Décalage horaire EPG :",
        "en": "EPG Timezone Offset:",
    },
    "Dossier de téléchargement des vidéos & films VOD :": {
        "fr": "Dossier de téléchargement des vidéos & films VOD :",
        "en": "Download Directory for VOD Videos & Movies:",
    },
    " Parcourir...": {
        "fr": " Parcourir...",
        "en": " Browse...",
    },
    "  Vider le cache des logos de chaînes": {
        "fr": "  Vider le cache des logos de chaînes",
        "en": "  Clear channel logo cache",
    },
    "💾 Enregistrer la configuration (Sauvegarde)": {
        "fr": "💾 Enregistrer la configuration (Sauvegarde)",
        "en": "💾 Save Configuration (Backup)",
    },
    "Exporte vos listes de lecture, comptes/serveurs, favoris, historique de visionnage, chaînes masquées et reprises de lecture dans un fichier JSON compact (~150 Ko).<br><i>(Les chaînes brutes et affiches ne sont pas incluses pour garantir un fichier léger et rapide).</i>": {
        "fr": "Exporte vos listes de lecture, comptes/serveurs, favoris, historique de visionnage, chaînes masquées et reprises de lecture dans un fichier JSON compact (~150 Ko).<br><i>(Les chaînes brutes et affiches ne sont pas incluses pour garantir un fichier léger et rapide).</i>",
        "en": "Exports your playlists, accounts/servers, favorites, watch history, hidden channels and resume points in a compact JSON file (~150 KB).<br><i>(Raw streams and posters are excluded to ensure a lightweight file).</i>",
    },
    "  Enregistrer la configuration sous...": {
        "fr": "  Enregistrer la configuration sous...",
        "en": "  Save configuration as...",
    },
    "📂 Charger une configuration (Restauration)": {
        "fr": "📂 Charger une configuration (Restauration)",
        "en": "📂 Load Configuration (Restore)",
    },
    "Charge un fichier de configuration précédemment sauvegardé. Le système fusionne intelligemment vos listes, cumule vos favoris et applique les reprises de lecture les plus récentes sans écraser vos données locales.": {
        "fr": "Charge un fichier de configuration précédemment sauvegardé. Le système fusionne intelligemment vos listes, cumule vos favoris et applique les reprises de lecture les plus récentes sans écraser vos données locales.",
        "en": "Loads a previously saved configuration file. The system intelligently merges playlists, accumulates favorites and applies the latest resume positions without overwriting local data.",
    },
    "  Charger un fichier de configuration...": {
        "fr": "  Charger un fichier de configuration...",
        "en": "  Load configuration file...",
    },
    "Version :": {
        "fr": "Version :",
        "en": "Version:",
    },
    "Édition Complète": {
        "fr": "Édition Complète",
        "en": "Full Edition",
    },
    "Moteur de rendu :": {
        "fr": "Moteur de rendu :",
        "en": "Rendering Engine:",
    },
    "Framework UI :": {
        "fr": "Framework UI :",
        "en": "UI Framework:",
    },
    "Raccourcis clés :": {
        "fr": "Raccourcis clés :",
        "en": "Key Shortcuts:",
    },
    "Plein écran": {
        "fr": "Plein écran",
        "en": "Fullscreen",
    },
    "Pause": {
        "fr": "Pause",
        "en": "Pause",
    },
    "Recul/Avance 10s": {
        "fr": "Recul/Avance 10s",
        "en": "Rewind/Forward 10s",
    },
    "Espace": {
        "fr": "Espace",
        "en": "Space",
    },
    "Base SQLite :": {
        "fr": "Base SQLite :",
        "en": "SQLite Database:",
    },

    # ---------------------------------------------------------
    # Dialogue Artiste & Recherche d'artiste
    # ---------------------------------------------------------
    "Filmographie — {name}": {
        "fr": "Filmographie — {name}",
        "en": "Filmography — {name}",
    },
    "Recherche des informations sur TMDB...": {
        "fr": "Recherche des informations sur TMDB...",
        "en": "Searching TMDB for information...",
    },
    "Recherche des titres disponibles dans votre abonnement IPTV...": {
        "fr": "Recherche des titres disponibles dans votre abonnement IPTV...",
        "en": "Searching available titles in your IPTV library...",
    },
    "Aucune information trouvée pour '{artist_name}' sur TMDB.": {
        "fr": "Aucune information trouvée pour '{artist_name}' sur TMDB.",
        "en": "No information found for '{artist_name}' on TMDB.",
    },
    "Information : {err_msg}": {
        "fr": "Information : {err_msg}",
        "en": "Information: {err_msg}",
    },
    "Acteur / Actrice": {
        "fr": "Acteur / Actrice",
        "en": "Actor / Actress",
    },
    "{age} ans ({b_date})": {
        "fr": "{age} ans ({b_date})",
        "en": "{age} years old ({b_date})",
    },
    "Aucun film ni série avec {artist_name} n'a été trouvé dans votre abonnement.": {
        "fr": "Aucun film ni série avec {artist_name} n'a été trouvé dans votre abonnement.",
        "en": "No movie or series featuring {artist_name} was found in your library.",
    },
    "🎬 Films disponibles ({count})": {
        "fr": "🎬 Films disponibles ({count})",
        "en": "🎬 Available Movies ({count})",
    },
    "📺 Séries disponibles ({count})": {
        "fr": "📺 Séries disponibles ({count})",
        "en": "📺 Available Series ({count})",
    },
    "🎥 En tant que Réalisateur ({count})": {
        "fr": "🎥 En tant que Réalisateur ({count})",
        "en": "🎥 As Director ({count})",
    },
    "Défiler vers la gauche": {
        "fr": "Défiler vers la gauche",
        "en": "Scroll left",
    },
    "Défiler vers la droite": {
        "fr": "Défiler vers la droite",
        "en": "Scroll right",
    },
    "Rôle : {role}": {
        "fr": "Rôle : {role}",
        "en": "Role: {role}",
    },
    "Année : {year}": {
        "fr": "Année : {year}",
        "en": "Year: {year}",
    },
    "Rechercher un acteur ou réalisateur": {
        "fr": "Rechercher un acteur ou réalisateur",
        "en": "Search an actor or director",
    },
    "Rechercher un Acteur ou Réalisateur": {
        "fr": "Rechercher un Acteur ou Réalisateur",
        "en": "Search an Actor or Director",
    },
    "Tapez le prénom ou le nom : les suggestions s'affinent en temps réel. Cliquez sur un artiste pour voir sa filmographie.": {
        "fr": "Tapez le prénom ou le nom : les suggestions s'affinent en temps réel. Cliquez sur un artiste pour voir sa filmographie.",
        "en": "Type first or last name: suggestions refine in real time. Click an artist to view their filmography.",
    },
    "Ex : Charlie, Tom, Christopher, Drew...": {
        "fr": "Ex : Charlie, Tom, Christopher, Drew...",
        "en": "e.g. Charlie, Tom, Christopher, Drew...",
    },
    "Coller": {
        "fr": "Coller",
        "en": "Paste",
    },
    "Coller depuis le presse-papier (clic souris)": {
        "fr": "Coller depuis le presse-papier (clic souris)",
        "en": "Paste from clipboard (mouse click)",
    },
    "Tapez au moins 2 lettres pour afficher les suggestions...": {
        "fr": "Tapez au moins 2 lettres pour afficher les suggestions...",
        "en": "Type at least 2 letters to view suggestions...",
    },
    "Recherche des artistes correspondants...": {
        "fr": "Recherche des artistes correspondants...",
        "en": "Searching matching artists...",
    },
    'Aucun artiste trouvé pour "{query}".': {
        "fr": 'Aucun artiste trouvé pour "{query}".',
        "en": 'No artist found for "{query}".',
    },
    "Afficher la filmographie": {
        "fr": "Afficher la filmographie",
        "en": "Show filmography",
    },
    "Afficher la filmographie de {name}": {
        "fr": "Afficher la filmographie de {name}",
        "en": "Show filmography of {name}",
    },

    # ---------------------------------------------------------
    # Fiches détaillées Films et Séries
    # ---------------------------------------------------------
    "FICHE DU FILM": {
        "fr": "FICHE DU FILM",
        "en": "MOVIE DETAILS",
    },
    "Retour à la galerie de films": {
        "fr": "Retour à la galerie de films",
        "en": "Back to movie gallery",
    },
    "Regarder le film": {
        "fr": "Regarder le film",
        "en": "Watch movie",
    },
    "Reprendre à {time}": {
        "fr": "Reprendre à {time}",
        "en": "Resume at {time}",
    },
    "Du début": {
        "fr": "Du début",
        "en": "From beginning",
    },
    "Annuler reprise": {
        "fr": "Annuler reprise",
        "en": "Clear progress",
    },
    "Ajouter aux favoris": {
        "fr": "Ajouter aux favoris",
        "en": "Add to favorites",
    },
    "Retirer des favoris": {
        "fr": "Retirer des favoris",
        "en": "Remove from favorites",
    },
    "Télécharger": {
        "fr": "Télécharger",
        "en": "Download",
    },
    "Téléchargement...": {
        "fr": "Téléchargement...",
        "en": "Downloading...",
    },
    "✓ Téléchargé": {
        "fr": "✓ Téléchargé",
        "en": "✓ Downloaded",
    },
    "Bande-annonce": {
        "fr": "Bande-annonce",
        "en": "Trailer",
    },
    "Lire la bande-annonce": {
        "fr": "Lire la bande-annonce",
        "en": "Play trailer",
    },
    "Ouvrir sur YouTube": {
        "fr": "Ouvrir sur YouTube",
        "en": "Open on YouTube",
    },
    "Avis des spectateurs": {
        "fr": "Avis des spectateurs",
        "en": "User Reviews",
    },
    "Genre :": {
        "fr": "Genre :",
        "en": "Genre:",
    },
    "Durée :": {
        "fr": "Durée :",
        "en": "Duration:",
    },
    "Réalisateur :": {
        "fr": "Réalisateur :",
        "en": "Director:",
    },
    "Acteurs :": {
        "fr": "Acteurs :",
        "en": "Cast:",
    },
    "Synopsis :": {
        "fr": "Synopsis :",
        "en": "Synopsis:",
    },
    "Aucun résumé disponible pour ce film.": {
        "fr": "Aucun résumé disponible pour ce film.",
        "en": "No plot summary available for this movie.",
    },
    "FICHE DE LA SÉRIE": {
        "fr": "FICHE DE LA SÉRIE",
        "en": "SERIES DETAILS",
    },
    "Retour à la galerie de séries": {
        "fr": "Retour à la galerie de séries",
        "en": "Back to series gallery",
    },
    "Saisons et épisodes": {
        "fr": "Saisons et épisodes",
        "en": "Seasons and episodes",
    },
    "Bande-annonce de la série": {
        "fr": "Bande-annonce de la série",
        "en": "Series Trailer",
    },
    "Distribution :": {
        "fr": "Distribution :",
        "en": "Cast:",
    },
    "Lancer la lecture": {
        "fr": "Lancer la lecture",
        "en": "Play",
    },
    "Lecture en cours...": {
        "fr": "Lecture en cours...",
        "en": "Playing now...",
    },
    "Recommencer la série": {
        "fr": "Recommencer la série",
        "en": "Restart series",
    },
    "Reprendre : S{s:02d}E{e:02d} ({title})": {
        "fr": "Reprendre : S{s:02d}E{e:02d} ({title})",
        "en": "Resume: S{s:02d}E{e:02d} ({title})",
    },
    "Saison {num}": {
        "fr": "Saison {num}",
        "en": "Season {num}",
    },
    "Épisode {num}": {
        "fr": "Épisode {num}",
        "en": "Episode {num}",
    },
    "Aucun épisode disponible dans cette saison.": {
        "fr": "Aucun épisode disponible dans cette saison.",
        "en": "No episodes available in this season.",
    },
    "Chargement des saisons et épisodes...": {
        "fr": "Chargement des saisons et épisodes...",
        "en": "Loading seasons and episodes...",
    },
    "Favoris": {
        "fr": "Favoris",
        "en": "Favorites",
    },
    "Tous": {
        "fr": "Tous",
        "en": "All",
    },
    "la liste": {
        "fr": "la liste",
        "en": "the playlist",
    },
    "Liste :": {
        "fr": "Liste :",
        "en": "Playlist:",
    },
    "Ma liste de lecture": {
        "fr": "Ma liste de lecture",
        "en": "My playlist",
    },
    "ma liste de lecture": {
        "fr": "ma liste de lecture",
        "en": "my playlist",
    },
    "Film": {
        "fr": "Film",
        "en": "Movie",
    },
    "Série": {
        "fr": "Série",
        "en": "Series",
    },
    "Replay": {
        "fr": "Replay",
        "en": "Replay",
    },
    "Il reste {hours} h {mins:02d} min": {
        "fr": "Il reste {hours} h {mins:02d} min",
        "en": "{hours}h {mins:02d}m left",
    },
    "Il reste {hours} h {mins} min": {
        "fr": "Il reste {hours} h {mins} min",
        "en": "{hours}h {mins}m left",
    },
    "Il reste {mins} min": {
        "fr": "Il reste {mins} min",
        "en": "{mins} min left",
    },
    "Il reste {time}": {
        "fr": "Il reste {time}",
        "en": "{time} left",
    },
    "{pct}% regardé": {
        "fr": "{pct} % regardé",
        "en": "{pct}% watched",
    },
    "{pct} % regardé": {
        "fr": "{pct} % regardé",
        "en": "{pct}% watched",
    },
    "Reprendre le Replay": {
        "fr": "Reprendre le Replay",
        "en": "Resume Replay",
    },
    "  Reprendre le Replay": {
        "fr": "  Reprendre le Replay",
        "en": "  Resume Replay",
    },
    "Lancer l'épisode suivant": {
        "fr": "Lancer l'épisode suivant",
        "en": "Play next episode",
    },
    "  Lancer l'épisode suivant": {
        "fr": "  Lancer l'épisode suivant",
        "en": "  Play next episode",
    },
    "Voir la série": {
        "fr": "Voir la série",
        "en": "View series",
    },
    "  Voir la série": {
        "fr": "  Voir la série",
        "en": "  View series",
    },
    "Épisode suivant disponible": {
        "fr": "Épisode suivant disponible",
        "en": "Next episode available",
    },
    "Série à reprendre": {
        "fr": "Série à reprendre",
        "en": "Series in progress",
    },
    "Recently watched live TV": {
        "fr": "TV en direct récemment regardée",
        "en": "Recently watched live TV",
    },
    "TV en direct récemment regardée": {
        "fr": "TV en direct récemment regardée",
        "en": "Recently watched live TV",
    },
    "Favorite movies & series": {
        "fr": "Films & Séries favoris",
        "en": "Favorite movies & series",
    },
    "Films & Séries favoris": {
        "fr": "Films & Séries favoris",
        "en": "Favorite movies & series",
    },
    "Voir tout >": {
        "fr": "Voir tout >",
        "en": "See all >",
    },
    "Voir tout": {
        "fr": "Voir tout",
        "en": "See all",
    },
    "Voir les {count} >": {
        "fr": "Voir les {count} >",
        "en": "See all {count} >",
    },
    "Affiche": {
        "fr": "Affiche",
        "en": "Poster",
    },
    "Direct": {
        "fr": "Direct",
        "en": "Live",
    },
    "Aucune liste de lecture": {
        "fr": "Aucune liste de lecture",
        "en": "No playlist",
    },
}


class I18nManager(QObject):
    """
    Gestionnaire centralisé d'internationalisation (Singleton).
    Émet le signal `language_changed(str)` lors d'un changement de langue.
    """
    language_changed = pyqtSignal(str)

    _instance: Optional["I18nManager"] = None

    SUPPORTED_LANGUAGES = {
        "fr": "Français",
        "en": "English",
    }

    def __init__(self):
        super().__init__()
        self._current_language = "fr"

    @classmethod
    def instance(cls) -> "I18nManager":
        if cls._instance is not None:
            try:
                cls._instance.objectName()
            except RuntimeError:
                cls._instance = None
        if cls._instance is None:
            cls._instance = I18nManager()
        return cls._instance

    @property
    def current_language(self) -> str:
        return self._current_language

    def set_language(self, lang_code: str):
        """Définit la langue courante et émet language_changed si différente."""
        if not lang_code or lang_code not in self.SUPPORTED_LANGUAGES:
            lang_code = "fr"

        if self._current_language != lang_code:
            self._current_language = lang_code
            self.language_changed.emit(self._current_language)

    def translate(self, text: str, **kwargs: Any) -> str:
        """
        Traduit le texte demandé dans la langue courante.
        Si la chaîne n'a pas de traduction pour la langue courante,
        renvoie la traduction en français si existante, ou la clé source originale.
        Supporte les arguments dynamiques kwargs sous forme de {cle}.
        """
        if not text:
            return ""

        translations = TRANSLATIONS.get(text)
        if translations:
            translated = translations.get(self._current_language)
            if not translated:
                translated = translations.get("fr", text)
        else:
            translated = text

        if kwargs:
            try:
                return translated.format(**kwargs)
            except Exception:
                return translated

        return translated


def tr(text: str, **kwargs: Any) -> str:
    """Raccourci global de traduction."""
    return I18nManager.instance().translate(text, **kwargs)


# -----------------------------------------------------------------------------
# Utilitaires de dates localisées (FR / EN)
# -----------------------------------------------------------------------------

WEEKDAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

WEEKDAYS_SHORT_FR = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]
WEEKDAYS_SHORT_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

MONTHS_SHORT_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MONTHS_SHORT_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_locale_weekday(weekday_idx: int, short: bool = False) -> str:
    """Retourne le nom du jour de la semaine (0 = Lundi/Monday) dans la langue active."""
    lang = I18nManager.instance().current_language
    idx = max(0, min(6, weekday_idx))
    if lang == "en":
        return WEEKDAYS_SHORT_EN[idx] if short else WEEKDAYS_EN[idx]
    return WEEKDAYS_SHORT_FR[idx] if short else WEEKDAYS_FR[idx]


def get_locale_month(month_1_based: int, short: bool = True) -> str:
    """Retourne le nom du mois (1 = Janvier/January) dans la langue active."""
    lang = I18nManager.instance().current_language
    idx = max(0, min(11, month_1_based - 1))
    if lang == "en":
        return MONTHS_SHORT_EN[idx] if short else MONTHS_EN[idx]
    return MONTHS_SHORT_FR[idx] if short else MONTHS_FR[idx]


def format_locale_date(dt, date_format: str = "short") -> str:
    """
    Formate une date datetime selon la langue active :
    - 'short' : '14/09/2026' (FR) ou '09/14/2026' (EN)
    - 'friendly' : '14 sept., 22:30' (FR) ou 'Sep 14, 22:30' (EN)
    """
    if not dt:
        return ""
    lang = I18nManager.instance().current_language
    if date_format == "short":
        if lang == "en":
            return dt.strftime("%m/%d/%Y")
        return dt.strftime("%d/%m/%Y")
    elif date_format == "friendly":
        m_str = get_locale_month(dt.month, short=True)
        if lang == "en":
            return f"{m_str} {dt.day}, {dt.hour:02d}:{dt.minute:02d}"
        return f"{dt.day} {m_str}, {dt.hour:02d}:{dt.minute:02d}"
    return dt.strftime("%d/%m/%Y")


