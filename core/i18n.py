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
