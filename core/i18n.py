"""
Module central d'internationalisation (i18n) pour IPTV Hub.
Supporte le Français ('fr'), l'Anglais ('en'), l'Espagnol ('es') et l'Allemand ('de')
avec basculement dynamique sans redémarrage requis et fallback transparent sur le texte d'origine.
"""

from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal


# Dictionnaires de traductions
# Clé : texte source (souvent en français ou identifiant logique)
# Valeur : dictionnaire des traductions {"fr": "...", "en": "...", "es": "...", "de": "..."}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "IPTV Hub": {
        "fr": "IPTV Hub",
        "en": "IPTV Hub",
        "es": "IPTV Hub",
        "de": "IPTV Hub",
    },
    "Liste :": {
        "fr": "Liste :",
        "en": "Playlist:",
        "es": "Lista:",
        "de": "Wiedergabeliste:",
    },
    "Rafraîchir les chaînes de la liste active": {
        "fr": "Rafraîchir les chaînes de la liste active",
        "en": "Refresh channels of active playlist",
        "es": "Actualizar los canales de la lista activa",
        "de": "Kanäle der aktiven Wiedergabeliste aktualisieren",
    },
    "Ajouter une liste de lecture": {
        "fr": "Ajouter une liste de lecture",
        "en": "Add a playlist",
        "es": "Añadir una lista de reproducción",
        "de": "Wiedergabeliste hinzufügen",
    },
    "Rechercher sur le tableau de bord...": {
        "fr": "Rechercher sur le tableau de bord...",
        "en": "Search on dashboard...",
        "es": "Buscar en el panel de control...",
        "de": "Auf dem Dashboard suchen...",
    },
    "Favoris | Filtrer cette section...": {
        "fr": "Favoris | Filtrer cette section...",
        "en": "Favorites | Filter this section...",
        "es": "Favoritos | Filtrar esta sección...",
        "de": "Favoriten | Diesen Bereich filtern...",
    },
    "Rechercher dans l'historique...": {
        "fr": "Rechercher dans l'historique...",
        "en": "Search in history...",
        "es": "Buscar en el historial...",
        "de": "Im Verlauf suchen...",
    },
    "Rechercher une chaîne en direct...": {
        "fr": "Rechercher une chaîne en direct...",
        "en": "Search live TV channel...",
        "es": "Buscar un canal en vivo...",
        "de": "Live-TV-Kanal suchen...",
    },
    "Rechercher un film (VOD)...": {
        "fr": "Rechercher un film (VOD)...",
        "en": "Search a movie (VOD)...",
        "es": "Buscar una película (VOD)...",
        "de": "Film (VOD) suchen...",
    },
    "Rechercher une série...": {
        "fr": "Rechercher une série...",
        "en": "Search a series...",
        "es": "Buscar una serie...",
        "de": "Serie suchen...",
    },
    "Rechercher parmi les récents ajouts...": {
        "fr": "Rechercher parmi les récents ajouts...",
        "en": "Search among recent additions...",
        "es": "Buscar entre los recién añadidos...",
        "de": "In den neuesten Einträgen suchen...",
    },
    "Rechercher dans le guide TV...": {
        "fr": "Rechercher dans le guide TV...",
        "en": "Search in TV guide...",
        "es": "Buscar en la guía de TV...",
        "de": "Im EPG-Programmführer suchen...",
    },
    "Rechercher dans le Replay...": {
        "fr": "Rechercher dans le Replay...",
        "en": "Search in Replay...",
        "es": "Buscar en el Replay...",
        "de": "In Replay suchen...",
    },
    "Rechercher...": {
        "fr": "Rechercher...",
        "en": "Search...",
        "es": "Buscar...",
        "de": "Suchen...",
    },
    "Réduire": {
        "fr": "Réduire",
        "en": "Minimize",
        "es": "Minimizar",
        "de": "Minimieren",
    },
    "Agrandir / Restaurer": {
        "fr": "Agrandir / Restaurer",
        "en": "Maximize / Restore",
        "es": "Maximizar / Restaurar",
        "de": "Maximieren / Wiederherstellen",
    },
    "Fermer": {
        "fr": "Fermer",
        "en": "Close",
        "es": "Cerrar",
        "de": "Schließen",
    },
    "Tableau de bord": {
        "fr": "Tableau de bord",
        "en": "Dashboard",
        "es": "Panel de control",
        "de": "Dashboard",
    },
    "Favoris globaux": {
        "fr": "Favoris globaux",
        "en": "Global favorites",
        "es": "Favoritos globales",
        "de": "Globale Favoriten",
    },
    "Récemment regardé": {
        "fr": "Récemment regardé",
        "en": "Recently watched",
        "es": "Visto recientemente",
        "de": "Kürzlich angesehen",
    },
    "Guide des programmes (EPG)": {
        "fr": "Guide des programmes (EPG)",
        "en": "TV Guide (EPG)",
        "es": "Guía de programas (EPG)",
        "de": "Programmführer (EPG)",
    },
    "TV Replay (Rattrapage)": {
        "fr": "TV Replay (Rattrapage)",
        "en": "TV Replay (Catchup)",
        "es": "TV Replay (Catch-up)",
        "de": "TV-Replay (Catch-up)",
    },
    "TV en direct": {
        "fr": "TV en direct",
        "en": "Live TV",
        "es": "TV en vivo",
        "de": "Live-TV",
    },
    "Films (VOD)": {
        "fr": "Films (VOD)",
        "en": "Movies (VOD)",
        "es": "Películas (VOD)",
        "de": "Filme (VOD)",
    },
    "Séries": {
        "fr": "Séries",
        "en": "Series",
        "es": "Series",
        "de": "Serien",
    },
    "Récemment ajoutés (TV, VOD, Séries)": {
        "fr": "Récemment ajoutés (TV, VOD, Séries)",
        "en": "Recently added (TV, VOD, Series)",
        "es": "Recién añadidos (TV, VOD, Series)",
        "de": "Kürzlich hinzugefügt (TV, VOD, Serien)",
    },
    "Gérer les listes de lecture": {
        "fr": "Gérer les listes de lecture",
        "en": "Manage playlists",
        "es": "Gestionar listas de reproducción",
        "de": "Wiedergabelisten verwalten",
    },
    "Paramètres de l'application": {
        "fr": "Paramètres de l'application",
        "en": "Application settings",
        "es": "Configuración de la aplicación",
        "de": "Anwendungseinstellungen",
    },
    "CATÉGORIES": {
        "fr": "CATÉGORIES",
        "en": "CATEGORIES",
        "es": "CATEGORÍAS",
        "de": "KATEGORIEN",
    },
    "Toutes les catégories": {
        "fr": "Toutes les catégories",
        "en": "All categories",
        "es": "Todas las categorías",
        "de": "Alle Kategorien",
    },
    "Toutes les chaînes": {
        "fr": "Toutes les chaînes",
        "en": "All channels",
        "es": "Todos los canales",
        "de": "Alle Kanäle",
    },
    "Rechercher dans cette catégorie...": {
        "fr": "Rechercher dans cette catégorie...",
        "en": "Search in this category...",
        "es": "Buscar en esta categoría...",
        "de": "In dieser Kategorie suchen...",
    },
    "Chercher dans cette catégorie": {
        "fr": "Chercher dans cette catégorie",
        "en": "Search in this category",
        "es": "Buscar en esta categoría",
        "de": "In dieser Kategorie suchen",
    },
    "Rechercher dans cette catégorie": {
        "fr": "Rechercher dans cette catégorie",
        "en": "Search in this category",
        "es": "Buscar en esta categoría",
        "de": "In dieser Kategorie suchen",
    },
    "Masquer / Afficher les catégories": {
        "fr": "Masquer / Afficher les catégories",
        "en": "Hide / Show categories",
        "es": "Ocultar / Mostrar categorías",
        "de": "Kategorien ausblenden / einblenden",
    },
    "Afficher les catégories": {
        "fr": "Afficher les catégories",
        "en": "Show categories",
        "es": "Mostrar categorías",
        "de": "Kategorien einblenden",
    },
    "Masquer les catégories": {
        "fr": "Masquer les catégories",
        "en": "Hide categories",
        "es": "Ocultar categorías",
        "de": "Kategorien ausblenden",
    },
    "Toutes": {
        "fr": "Toutes",
        "en": "All",
        "es": "Todas",
        "de": "Alle",
    },
    "Filtrer les catégories...": {
        "fr": "Filtrer les catégories...",
        "en": "Filter categories...",
        "es": "Filtrar categorías...",
        "de": "Kategorien filtern...",
    },
    "Filtrer les chaînes...": {
        "fr": "Filtrer les chaînes...",
        "en": "Filter channels...",
        "es": "Filtrar canales...",
        "de": "Kanäle filtern...",
    },
    "Gérer les catégories": {
        "fr": "Gérer les catégories",
        "en": "Manage Categories",
        "es": "Gestionar categorías",
        "de": "Kategorien verwalten",
    },
    "CHAÎNES": {
        "fr": "CHAÎNES",
        "en": "CHANNELS",
        "es": "CANALES",
        "de": "KANÄLE",
    },
    "Aucune chaîne": {
        "fr": "Aucune chaîne",
        "en": "No channels",
        "es": "Ningún canal",
        "de": "Kein Kanal",
    },
    "Aucune catégorie": {
        "fr": "Aucune catégorie",
        "en": "No category",
        "es": "Ninguna categoría",
        "de": "Keine Kategorie",
    },
    "chaîne": {
        "fr": "chaîne",
        "en": "channel",
        "es": "canal",
        "de": "Kanal",
    },
    "chaînes": {
        "fr": "chaînes",
        "en": "channels",
        "es": "canales",
        "de": "Kanäle",
    },
    "film": {
        "fr": "film",
        "en": "movie",
        "es": "película",
        "de": "Film",
    },
    "films": {
        "fr": "films",
        "en": "movies",
        "es": "películas",
        "de": "Filme",
    },
    "série": {
        "fr": "série",
        "en": "series",
        "es": "serie",
        "de": "Serie",
    },
    "séries": {
        "fr": "séries",
        "en": "series",
        "es": "series",
        "de": "Serien",
    },
    "Ajouter aux favoris": {
        "fr": "Ajouter aux favoris",
        "en": "Add to favorites",
        "es": "Añadir a favoritos",
        "de": "Zu Favoriten hinzufügen",
    },
    "Retirer des favoris": {
        "fr": "Retirer des favoris",
        "en": "Remove from favorites",
        "es": "Quitar de favoritos",
        "de": "Aus Favoriten entfernen",
    },
    "Masquer la chaîne": {
        "fr": "Masquer la chaîne",
        "en": "Hide channel",
        "es": "Ocultar canal",
        "de": "Kanal ausblenden",
    },
    "Copier l'URL du flux": {
        "fr": "Copier l'URL du flux",
        "en": "Copy stream URL",
        "es": "Copiar URL de la transmisión",
        "de": "Stream-URL kopieren",
    },
    "Ordre original": {
        "fr": "Ordre original",
        "en": "Original order",
        "es": "Orden original",
        "de": "Originalreihenfolge",
    },
    "Par défaut (Serveur)": {
        "fr": "Par défaut (Serveur)",
        "en": "Default (Server)",
        "es": "Predeterminado (Servidor)",
        "de": "Standard (Server)",
    },
    "Nom (A-Z)": {
        "fr": "Nom (A-Z)",
        "en": "Name (A-Z)",
        "es": "Nombre (A-Z)",
        "de": "Name (A-Z)",
    },
    "Nom (Z-A)": {
        "fr": "Nom (Z-A)",
        "en": "Name (Z-A)",
        "es": "Nombre (Z-A)",
        "de": "Name (Z-A)",
    },
    "Nombre de chaînes (Décroissant)": {
        "fr": "Nombre de chaînes (Décroissant)",
        "en": "Channel count (Descending)",
        "es": "Número de canales (Descendente)",
        "de": "Kanalanzahl (Absteigend)",
    },
    "Nombre d'éléments (Décroissant)": {
        "fr": "Nombre d'éléments (Décroissant)",
        "en": "Item count (Descending)",
        "es": "Número de elementos (Descendente)",
        "de": "Elementanzahl (Absteigend)",
    },
    "Plus récents d'abord": {
        "fr": "Plus récents d'abord",
        "en": "Most recent first",
        "es": "Más recientes primero",
        "de": "Neueste zuerst",
    },
    "Mieux notés": {
        "fr": "Mieux notés",
        "en": "Top rated",
        "es": "Mejor valorados",
        "de": "Bestbewertet",
    },
    "Année (Plus récent)": {
        "fr": "Année (Plus récent)",
        "en": "Year (Newest)",
        "es": "Año (Más reciente)",
        "de": "Jahr (Neueste)",
    },
    "Année (Plus ancien)": {
        "fr": "Année (Plus ancien)",
        "en": "Year (Oldest)",
        "es": "Año (Más antiguo)",
        "de": "Jahr (Älteste)",
    },
    "Trier par :": {
        "fr": "Trier par :",
        "en": "Sort by:",
        "es": "Ordenar por:",
        "de": "Sortieren nach:",
    },
    "TOUS LES FILMS": {
        "fr": "TOUS LES FILMS",
        "en": "ALL MOVIES",
        "es": "TODAS LAS PELÍCULAS",
        "de": "ALLE FILME",
    },
    "TOUTES LES SÉRIES": {
        "fr": "TOUTES LES SÉRIES",
        "en": "ALL SERIES",
        "es": "TODAS LAS SERIES",
        "de": "ALLE SERIEN",
    },
    "Affiner les résultats": {
        "fr": "Affiner les résultats",
        "en": "Refine results",
        "es": "Filtrar resultados",
        "de": "Ergebnisse verfeinern",
    },
    "Recherche par artiste": {
        "fr": "Recherche par artiste",
        "en": "Search by artist",
        "es": "Búsqueda por artista",
        "de": "Künstlersuche",
    },
    "Filmographie": {
        "fr": "Filmographie",
        "en": "Filmography",
        "es": "Filmografía",
        "de": "Filmografie",
    },
    "Acteur ou Réalisateur...": {
        "fr": "Acteur ou Réalisateur...",
        "en": "Actor or Director...",
        "es": "Actor o Director...",
        "de": "Schauspieler oder Regisseur...",
    },
    "Chargement...": {
        "fr": "Chargement...",
        "en": "Loading...",
        "es": "Cargando...",
        "de": "Laden...",
    },
    "Aucun résultat": {
        "fr": "Aucun résultat",
        "en": "No results",
        "es": "Sin resultados",
        "de": "Keine Ergebnisse",
    },
    "Aucun film trouvé": {
        "fr": "Aucun film trouvé",
        "en": "No movies found",
        "es": "No se encontraron películas",
        "de": "Keine Filme gefunden",
    },
    "Aucune série trouvée": {
        "fr": "Aucune série trouvée",
        "en": "No series found",
        "es": "No se encontraron series",
        "de": "Keine Serien gefunden",
    },
    "Page précédente": {
        "fr": "Page précédente",
        "en": "Previous page",
        "es": "Página anterior",
        "de": "Vorherige Seite",
    },
    "Page suivante": {
        "fr": "Page suivante",
        "en": "Next page",
        "es": "Página siguiente",
        "de": "Nächste Seite",
    },
    "Page {current} sur {total}": {
        "fr": "Page {current} sur {total}",
        "en": "Page {current} of {total}",
        "es": "Página {current} de {total}",
        "de": "Seite {current} von {total}",
    },
    "Lecture": {
        "fr": "Lecture",
        "en": "Play",
        "es": "Reproducir",
        "de": "Abspielen",
    },
    "Reprendre": {
        "fr": "Reprendre",
        "en": "Resume",
        "es": "Reanudar",
        "de": "Fortsetzen",
    },
    "Bande-annonce": {
        "fr": "Bande-annonce",
        "en": "Trailer",
        "es": "Tráiler",
        "de": "Trailer",
    },
    "Synopsis": {
        "fr": "Synopsis",
        "en": "Synopsis",
        "es": "Sinopsis",
        "de": "Handlung",
    },
    "Distribution": {
        "fr": "Distribution",
        "en": "Cast",
        "es": "Reparto",
        "de": "Besetzung",
    },
    "Réalisateur": {
        "fr": "Réalisateur",
        "en": "Director",
        "es": "Director",
        "de": "Regie",
    },
    "Genre": {
        "fr": "Genre",
        "en": "Genre",
        "es": "Género",
        "de": "Genre",
    },
    "Durée": {
        "fr": "Durée",
        "en": "Duration",
        "es": "Duración",
        "de": "Dauer",
    },
    "Année": {
        "fr": "Année",
        "en": "Year",
        "es": "Año",
        "de": "Jahr",
    },
    "Saisons et Épisodes": {
        "fr": "Saisons et Épisodes",
        "en": "Seasons and Episodes",
        "es": "Temporadas y Episodios",
        "de": "Staffeln und Folgen",
    },
    "Saison": {
        "fr": "Saison",
        "en": "Season",
        "es": "Temporada",
        "de": "Staffel",
    },
    "Épisode": {
        "fr": "Épisode",
        "en": "Episode",
        "es": "Episodio",
        "de": "Folge",
    },
    "Épisodes": {
        "fr": "Épisodes",
        "en": "Episodes",
        "es": "Episodios",
        "de": "Folgen",
    },
    "Retour": {
        "fr": "Retour",
        "en": "Back",
        "es": "Volver",
        "de": "Zurück",
    },
    "Retour à la liste": {
        "fr": "Retour à la liste",
        "en": "Back to list",
        "es": "Volver a la lista",
        "de": "Zurück zur Liste",
    },
    "Marquer comme vu": {
        "fr": "Marquer comme vu",
        "en": "Mark as watched",
        "es": "Marcar como visto",
        "de": "Als gesehen markieren",
    },
    "Marquer comme non vu": {
        "fr": "Marquer comme non vu",
        "en": "Mark as unwatched",
        "es": "Marcar como no visto",
        "de": "Als ungesehen markieren",
    },
    "Bienvenue sur IPTV Hub": {
        "fr": "Bienvenue sur IPTV Hub",
        "en": "Welcome to IPTV Hub",
        "es": "Bienvenido a IPTV Hub",
        "de": "Willkommen bei IPTV Hub",
    },
    "Reprendre la lecture": {
        "fr": "Reprendre la lecture",
        "en": "Continue Watching",
        "es": "Continuar viendo",
        "de": "Wiedergabe fortsetzen",
    },
    "Chaînes favorites": {
        "fr": "Chaînes favorites",
        "en": "Favorite Channels",
        "es": "Canales favoritos",
        "de": "Lieblingskanäle",
    },
    "Films récemment ajoutés": {
        "fr": "Films récemment ajoutés",
        "en": "Recently added movies",
        "es": "Películas añadidas recientemente",
        "de": "Kürzlich hinzugefügte Filme",
    },
    "Séries récemment ajoutées": {
        "fr": "Séries récemment ajoutées",
        "en": "Recently added series",
        "es": "Series añadidas recientemente",
        "de": "Kürzlich hinzugefügte Serien",
    },
    "Statistiques de la liste": {
        "fr": "Statistiques de la liste",
        "en": "Playlist Statistics",
        "es": "Estadísticas de la lista",
        "de": "Wiedergabelisten-Statistiken",
    },
    "Chaînes TV": {
        "fr": "Chaînes TV",
        "en": "Live TV",
        "es": "Canales de TV",
        "de": "TV-Sender",
    },
    "Films": {
        "fr": "Films",
        "en": "Movies",
        "es": "Películas",
        "de": "Filme",
    },
    "Voir tout": {
        "fr": "Voir tout",
        "en": "See all",
        "es": "Ver todo",
        "de": "Alle ansehen",
    },
    "Guide des programmes": {
        "fr": "Guide des programmes",
        "en": "TV Guide",
        "es": "Guía de programas",
        "de": "TV-Programm",
    },
    "Aujourd'hui": {
        "fr": "Aujourd'hui",
        "en": "Today",
        "es": "Hoy",
        "de": "Heute",
    },
    "Hier": {
        "fr": "Hier",
        "en": "Yesterday",
        "es": "Ayer",
        "de": "Gestern",
    },
    "Demain": {
        "fr": "Demain",
        "en": "Tomorrow",
        "es": "Mañana",
        "de": "Morgen",
    },
    "En direct maintenant": {
        "fr": "En direct maintenant",
        "en": "Live now",
        "es": "En vivo ahora",
        "de": "Jetzt live",
    },
    "Aucun guide des programmes disponible": {
        "fr": "Aucun guide des programmes disponible",
        "en": "No TV guide data available",
        "es": "No hay guía de programas disponible",
        "de": "Kein TV-Programm verfügbar",
    },
    "Chargement du guide TV...": {
        "fr": "Chargement du guide TV...",
        "en": "Loading TV guide...",
        "es": "Cargando guía de TV...",
        "de": "TV-Programm wird geladen...",
    },
    "Rattrapage TV (Replay 7 jours)": {
        "fr": "Rattrapage TV (Replay 7 jours)",
        "en": "TV Catchup (7 days replay)",
        "es": "Puesta al día TV (Replay 7 días)",
        "de": "TV-Catchup (7 Tage Replay)",
    },
    "Sélectionnez une chaîne avec l'icône Replay pour voir les émissions disponibles": {
        "fr": "Sélectionnez une chaîne avec l'icône Replay pour voir les émissions disponibles",
        "en": "Select a channel with Replay icon to view available broadcasts",
        "es": "Seleccione un canal con el icono Replay para ver los programas disponibles",
        "de": "Wählen Sie einen Kanal mit Replay-Symbol, um verfügbare Sendungen zu sehen",
    },
    "Vos Favoris": {
        "fr": "Vos Favoris",
        "en": "Your Favorites",
        "es": "Sus Favoritos",
        "de": "Ihre Favoriten",
    },
    "Historique de lecture": {
        "fr": "Historique de lecture",
        "en": "Watch History",
        "es": "Historial de reproducción",
        "de": "Wiedergabeverlauf",
    },
    "Récemment ajoutés": {
        "fr": "Récemment ajoutés",
        "en": "Recently Added",
        "es": "Añadidos recientemente",
        "de": "Kürzlich hinzugefügt",
    },
    "Effacer l'historique": {
        "fr": "Effacer l'historique",
        "en": "Clear history",
        "es": "Borrar historial",
        "de": "Verlauf löschen",
    },
    "Aucun élément récent": {
        "fr": "Aucun élément récent",
        "en": "No recent items",
        "es": "Ningún elemento reciente",
        "de": "Keine aktuellen Einträge",
    },
    "Aucun favori enregistré": {
        "fr": "Aucun favori enregistré",
        "en": "No favorites saved",
        "es": "No hay favoritos guardados",
        "de": "Keine Favoriten gespeichert",
    },
    "Paramètres": {
        "fr": "Paramètres",
        "en": "Settings",
        "es": "Configuración",
        "de": "Einstellungen",
    },
    "Général & Interface": {
        "fr": "Général & Interface",
        "en": "General & Interface",
        "es": "General e Interfaz",
        "de": "Allgemein & Oberfläche",
    },
    "Lecteur Vidéo": {
        "fr": "Lecteur Vidéo",
        "en": "Video Player",
        "es": "Reproductor de vídeo",
        "de": "Videoplayer",
    },
    "Réseau & Flux": {
        "fr": "Réseau & Flux",
        "en": "Network & Streams",
        "es": "Red y Transmisiones",
        "de": "Netzwerk & Streams",
    },
    "Guide EPG": {
        "fr": "Guide EPG",
        "en": "EPG Guide",
        "es": "Guía EPG",
        "de": "EPG-Guide",
    },
    "Données & Stockage": {
        "fr": "Données & Stockage",
        "en": "Data & Storage",
        "es": "Datos y Almacenamiento",
        "de": "Daten & Speicher",
    },
    "Sauvegarde & Fichiers": {
        "fr": "Sauvegarde & Fichiers",
        "en": "Backup & Files",
        "es": "Copia de seguridad y Archivos",
        "de": "Sicherung & Dateien",
    },
    "À propos": {
        "fr": "À propos",
        "en": "About",
        "es": "Acerca de",
        "de": "Über",
    },
    "Fermer les paramètres": {
        "fr": "Fermer les paramètres",
        "en": "Close settings",
        "es": "Cerrar configuración",
        "de": "Einstellungen schließen",
    },
    "Enregistrer les paramètres": {
        "fr": "Enregistrer les paramètres",
        "en": "Save settings",
        "es": "Guardar configuración",
        "de": "Einstellungen speichern",
    },
    "Paramètres enregistrés": {
        "fr": "Paramètres enregistrés",
        "en": "Settings saved",
        "es": "Configuración guardada",
        "de": "Einstellungen gespeichert",
    },
    "Les modifications ont été enregistrées avec succès.": {
        "fr": "Les modifications ont été enregistrées avec succès.",
        "en": "Changes have been saved successfully.",
        "es": "Los cambios se han guardado con éxito.",
        "de": "Die Änderungen wurden erfolgreich gespeichert.",
    },
    "Général & Apparence": {
        "fr": "Général & Apparence",
        "en": "General & Appearance",
        "es": "General y Apariencia",
        "de": "Allgemein & Erscheinungsbild",
    },
    "Personnalisez l'affichage, le comportement au démarrage et l'interface utilisateur.": {
        "fr": "Personnalisez l'affichage, le comportement au démarrage et l'interface utilisateur.",
        "en": "Customize display, startup behavior and user interface.",
        "es": "Personalice la visualización, el comportamiento al inicio y la interfaz.",
        "de": "Passen Sie Anzeige, Startverhalten und Benutzeroberfläche an.",
    },
    "Langue de l'application :": {
        "fr": "Langue de l'application :",
        "en": "Application Language:",
        "es": "Idioma de la aplicación:",
        "de": "Sprache der Anwendung:",
    },
    "Thème de l'interface :": {
        "fr": "Thème de l'interface :",
        "en": "Interface Theme:",
        "es": "Tema de la interfaz:",
        "de": "Oberflächendesign:",
    },
    "Gris foncé bleuté (Par défaut)": {
        "fr": "Gris foncé bleuté (Par défaut)",
        "en": "Bluish Dark Grey (Default)",
        "es": "Gris oscuro azulado (Predeterminado)",
        "de": "Dunkelgrau-bläulich (Standard)",
    },
    "Sombre moderne": {
        "fr": "Sombre moderne",
        "en": "Modern Dark",
        "es": "Oscuro moderno",
        "de": "Modernes Dunkel",
    },
    "Langue audio préférée (Films & Séries) :": {
        "fr": "Langue audio préférée (Films & Séries) :",
        "en": "Preferred Audio Language (Movies & Series):",
        "es": "Idioma de audio preferido (Películas y Series):",
        "de": "Bevorzugte Audiosprache (Filme & Serien):",
    },
    "Sous-titres automatiques :": {
        "fr": "Sous-titres automatiques :",
        "en": "Automatic subtitles:",
        "es": "Subtítulos automáticos:",
        "de": "Automatische Untertitel:",
    },
    "Langue des sous-titres :": {
        "fr": "Langue des sous-titres :",
        "en": "Subtitles language:",
        "es": "Idioma de los subtítulos:",
        "de": "Untertitelsprache:",
    },
    "Désactivés": {
        "fr": "Désactivés",
        "en": "Disabled",
        "es": "Desactivados",
        "de": "Deaktiviert",
    },
    "Activés": {
        "fr": "Activés",
        "en": "Enabled",
        "es": "Activados",
        "de": "Aktiviert",
    },
    "Lecture automatique de l'épisode suivant :": {
        "fr": "Lecture automatique de l'épisode suivant :",
        "en": "Auto-play next episode:",
        "es": "Reproducción automática del siguiente episodio:",
        "de": "Automatische Wiedergabe der nächsten Folge:",
    },
    "Activer l'enchaînement automatique des épisodes de séries": {
        "fr": "Activer l'enchaînement automatique des épisodes de séries",
        "en": "Enable auto-playing next episode of series",
        "es": "Activar la reproducción continua de episodios de series",
        "de": "Automatische Wiedergabe der nächsten Serienfolge aktivieren",
    },
    "Afficher la date d'ajout sur les affiches (VOD & Séries) :": {
        "fr": "Afficher la date d'ajout sur les affiches (VOD & Séries) :",
        "en": "Show added date badge on posters (VOD & Series):",
        "es": "Mostrar fecha de adición en portadas (VOD y Series):",
        "de": "Hinzugefügt-Datum auf Postern anzeigen (VOD & Serien):",
    },
    "Afficher le badge de date de sortie/ajout sur les jaquettes": {
        "fr": "Afficher le badge de date de sortie/ajout sur les jaquettes",
        "en": "Show release/added date badge on poster cards",
        "es": "Mostrar insignia de fecha de estreno/adición en las portadas",
        "de": "Veröffentlichungs-/Hinzugefügt-Badge auf Covern anzeigen",
    },
    "Moteur de rendu MPV": {
        "fr": "Moteur de rendu MPV",
        "en": "MPV Rendering Engine",
        "es": "Motor de renderizado MPV",
        "de": "MPV-Rendering-Engine",
    },
    "Configurez le décodage matériel et le traitement d'image du lecteur multimédia.": {
        "fr": "Configurez le décodage matériel et le traitement d'image du lecteur multimédia.",
        "en": "Configure hardware decoding and image processing for the media player.",
        "es": "Configure la decodificación por hardware y el procesamiento de imagen.",
        "de": "Konfigurieren Sie Hardware-Dekodierung und Bildverarbeitung des Mediaplayers.",
    },
    "Accélération matérielle (hwdec) :": {
        "fr": "Accélération matérielle (hwdec) :",
        "en": "Hardware acceleration (hwdec):",
        "es": "Aceleración por hardware (hwdec):",
        "de": "Hardware-Beschleunigung (hwdec):",
    },
    "Automatique (Recommandé)": {
        "fr": "Automatique (Recommandé)",
        "en": "Automatic (Recommended)",
        "es": "Automático (Recomendado)",
        "de": "Automatisch (Empfohlen)",
    },
    "Direct3D 11 (Windows)": {
        "fr": "Direct3D 11 (Windows)",
        "en": "Direct3D 11 (Windows)",
        "es": "Direct3D 11 (Windows)",
        "de": "Direct3D 11 (Windows)",
    },
    "NVIDIA NVDEC": {
        "fr": "NVIDIA NVDEC",
        "en": "NVIDIA NVDEC",
        "es": "NVIDIA NVDEC",
        "de": "NVIDIA NVDEC",
    },
    "VA-API (Linux)": {
        "fr": "VA-API (Linux)",
        "en": "VA-API (Linux)",
        "es": "VA-API (Linux)",
        "de": "VA-API (Linux)",
    },
    "Désactivée (CPU uniquement)": {
        "fr": "Désactivée (CPU uniquement)",
        "en": "Disabled (CPU only)",
        "es": "Desactivada (solo CPU)",
        "de": "Deaktiviert (nur CPU)",
    },
    "Désentrelacement matériel :": {
        "fr": "Désentrelacement matériel :",
        "en": "Hardware deinterlacing:",
        "es": "Desentrelazado por hardware:",
        "de": "Hardware-Deinterlacing:",
    },
    "Activer le désentrelacement (flux TV 1080i entrelacés)": {
        "fr": "Activer le désentrelacement (flux TV 1080i entrelacés)",
        "en": "Enable deinterlacing (for interlaced 1080i TV streams)",
        "es": "Activar desentrelazado (para transmisiones de TV 1080i entrelazadas)",
        "de": "Deinterlacing aktivieren (für interlaced 1080i-TV-Streams)",
    },
    "Format d'image par défaut (Aspect Ratio) :": {
        "fr": "Format d'image par défaut (Aspect Ratio) :",
        "en": "Default Aspect Ratio:",
        "es": "Relación de aspecto predeterminada:",
        "de": "Standard-Seitenverhältnis:",
    },
    "Automatique (Original)": {
        "fr": "Automatique (Original)",
        "en": "Automatic (Original)",
        "es": "Automático (Original)",
        "de": "Automatisch (Original)",
    },
    "Taille du tampon réseau :": {
        "fr": "Taille du tampon réseau :",
        "en": "Network Buffer Size:",
        "es": "Tamaño del búfer de red:",
        "de": "Netzwerkpuffergröße:",
    },
    "Volume initial au démarrage :": {
        "fr": "Volume initial au démarrage :",
        "en": "Initial volume on startup:",
        "es": "Volumen inicial al inicio:",
        "de": "Anfangslautstärke beim Start:",
    },
    "Réseau & En-têtes HTTP": {
        "fr": "Réseau & En-têtes HTTP",
        "en": "Network & HTTP Headers",
        "es": "Red y encabezados HTTP",
        "de": "Netzwerk & HTTP-Header",
    },
    "Personnalisez l'agent utilisateur (User-Agent) et les délais d'attente de connexion.": {
        "fr": "Personnalisez l'agent utilisateur (User-Agent) et les délais d'attente de connexion.",
        "en": "Customize User-Agent and connection timeout settings.",
        "es": "Personalice el User-Agent y los tiempos de espera de conexión.",
        "de": "Passen Sie User-Agent und Verbindungs-Timeouts an.",
    },
    "User-Agent par défaut :": {
        "fr": "User-Agent par défaut :",
        "en": "Default User-Agent:",
        "es": "User-Agent predeterminado:",
        "de": "Standard-User-Agent:",
    },
    "Guide des Programmes (EPG)": {
        "fr": "Guide des Programmes (EPG)",
        "en": "Electronic Program Guide (EPG)",
        "es": "Guía de programas (EPG)",
        "de": "Elektronischer Programmführer (EPG)",
    },
    "Gestion du téléchargement et de la mise à jour des programmes XMLTV.": {
        "fr": "Gestion du téléchargement et de la mise à jour des programmes XMLTV.",
        "en": "Management of XMLTV program downloads and updates.",
        "es": "Gestión de descargas y actualizaciones de programas XMLTV.",
        "de": "Verwaltung von Downloads und Aktualisierungen der XMLTV-Programme.",
    },
    "Mise à jour automatique :": {
        "fr": "Mise à jour automatique :",
        "en": "Automatic updates:",
        "es": "Actualización automática:",
        "de": "Automatische Aktualisierung:",
    },
    "Mettre à jour l'EPG au démarrage de l'application": {
        "fr": "Mettre à jour l'EPG au démarrage de l'application",
        "en": "Update EPG on application startup",
        "es": "Actualizar EPG al iniciar la aplicación",
        "de": "EPG beim Anwendungsstart aktualisieren",
    },
    "Fréquence de rafraîchissement :": {
        "fr": "Fréquence de rafraîchissement :",
        "en": "Refresh frequency:",
        "es": "Frecuencia de actualización:",
        "de": "Aktualisierungshäufigkeit:",
    },
    "Toutes les 6 heures": {
        "fr": "Toutes les 6 heures",
        "en": "Every 6 hours",
        "es": "Cada 6 horas",
        "de": "Alle 6 Stunden",
    },
    "Toutes les 12 heures": {
        "fr": "Toutes les 12 heures",
        "en": "Every 12 hours",
        "es": "Cada 12 horas",
        "de": "Alle 12 Stunden",
    },
    "Toutes les 24 heures": {
        "fr": "Toutes les 24 heures",
        "en": "Every 24 hours",
        "es": "Cada 24 horas",
        "de": "Alle 24 Stunden",
    },
    "Toutes les 48 heures": {
        "fr": "Toutes les 48 heures",
        "en": "Every 48 hours",
        "es": "Cada 48 horas",
        "de": "Alle 48 Stunden",
    },
    "Hebdomadaire (7 jours)": {
        "fr": "Hebdomadaire (7 jours)",
        "en": "Weekly (7 days)",
        "es": "Semanal (7 días)",
        "de": "Wöchentlich (7 Tage)",
    },
    "Mettre à jour l'EPG maintenant": {
        "fr": "Mettre à jour l'EPG maintenant",
        "en": "Update EPG now",
        "es": "Actualizar EPG ahora",
        "de": "EPG jetzt aktualisieren",
    },
    "Vider le cache EPG": {
        "fr": "Vider le cache EPG",
        "en": "Clear EPG cache",
        "es": "Vaciar caché de EPG",
        "de": "EPG-Cache leeren",
    },
    "Données & Cache": {
        "fr": "Données & Cache",
        "en": "Data & Cache",
        "es": "Datos y caché",
        "de": "Daten & Cache",
    },
    "Gérez l'espace disque utilisé par les logos, les vignettes et la base de données.": {
        "fr": "Gérez l'espace disque utilisé par les logos, les vignettes et la base de données.",
        "en": "Manage disk space used by logos, thumbnails and database.",
        "es": "Gestione el espacio en disco utilizado por logotipos, miniaturas y base de datos.",
        "de": "Verwalten Sie den Speicherplatz für Logos, Miniaturbilder und Datenbank.",
    },
    "Mise en cache des logos :": {
        "fr": "Mise en cache des logos :",
        "en": "Logo caching:",
        "es": "Almacenamiento en caché de logotipos:",
        "de": "Logo-Caching:",
    },
    "Sauvegarder les logos de chaînes sur le disque": {
        "fr": "Sauvegarder les logos de chaînes sur le disque",
        "en": "Save channel logos locally to disk",
        "es": "Guardar logotipos de canales en el disco",
        "de": "Senderlogos lokal auf der Festplatte speichern",
    },
    "Vider le cache des logos": {
        "fr": "Vider le cache des logos",
        "en": "Clear logos cache",
        "es": "Vaciar caché de logotipos",
        "de": "Logo-Cache leeren",
    },
    "Optimiser la base de données": {
        "fr": "Optimiser la base de données",
        "en": "Optimize database",
        "es": "Optimizar base de datos",
        "de": "Datenbank optimieren",
    },
    "Réinitialiser l'application": {
        "fr": "Réinitialiser l'application",
        "en": "Reset application",
        "es": "Restablecer la aplicación",
        "de": "Anwendung zurücksetzen",
    },
    "Synchronisation & Sauvegarde": {
        "fr": "Synchronisation & Sauvegarde",
        "en": "Sync & Backup",
        "es": "Sincronización y copia de seguridad",
        "de": "Synchronisierung & Sicherung",
    },
    "Synchronisez vos paramètres, favoris et listes avec un dossier cloud (Dropbox, Drive, etc.).": {
        "fr": "Synchronisez vos paramètres, favoris et listes avec un dossier cloud (Dropbox, Drive, etc.).",
        "en": "Sync your settings, favorites and playlists with a cloud folder (Dropbox, Drive, etc.).",
        "es": "Sincronice sus ajustes, favoritos y listas con una carpeta en la nube (Dropbox, Drive, etc.).",
        "de": "Synchronisieren Sie Einstellungen, Favoriten und Listen mit einem Cloud-Ordner (Dropbox, Drive usw.).",
    },
    "Synchronisation automatique :": {
        "fr": "Synchronisation automatique :",
        "en": "Automatic sync:",
        "es": "Sincronización automática:",
        "de": "Automatische Synchronisierung:",
    },
    "Activer la synchronisation avec un dossier externe": {
        "fr": "Activer la synchronisation avec un dossier externe",
        "en": "Enable synchronization with an external folder",
        "es": "Activar sincronización con carpeta externa",
        "de": "Synchronisierung mit externem Ordner aktivieren",
    },
    "Dossier de synchronisation :": {
        "fr": "Dossier de synchronisation :",
        "en": "Sync folder:",
        "es": "Carpeta de sincronización:",
        "de": "Synchronisierungsordner:",
    },
    "Parcourir...": {
        "fr": "Parcourir...",
        "en": "Browse...",
        "es": "Examinar...",
        "de": "Durchsuchen...",
    },
    "Exporter la sauvegarde": {
        "fr": "Exporter la sauvegarde",
        "en": "Export backup",
        "es": "Exportar copia de seguridad",
        "de": "Sicherung exportieren",
    },
    "Importer une sauvegarde": {
        "fr": "Importer une sauvegarde",
        "en": "Import backup",
        "es": "Importar copia de seguridad",
        "de": "Sicherung importieren",
    },
    "À propos de IPTV Hub": {
        "fr": "À propos de IPTV Hub",
        "en": "About IPTV Hub",
        "es": "Acerca de IPTV Hub",
        "de": "Über IPTV Hub",
    },
    "Lecteur IPTV et VOD moderne, performant et élégant pour Windows & Linux.": {
        "fr": "Lecteur IPTV et VOD moderne, performant et élégant pour Windows & Linux.",
        "en": "Modern, fast and elegant IPTV and VOD player for Windows & Linux.",
        "es": "Reproductor de IPTV y VOD moderno, potente y elegante para Windows y Linux.",
        "de": "Moderner, leistungsstarker und eleganter IPTV- und VOD-Player für Windows & Linux.",
    },
    "Version": {
        "fr": "Version",
        "en": "Version",
        "es": "Versión",
        "de": "Version",
    },
    "Licence": {
        "fr": "Licence",
        "en": "License",
        "es": "Licencia",
        "de": "Lizenz",
    },
    "Auteur": {
        "fr": "Auteur",
        "en": "Author",
        "es": "Autor",
        "de": "Autor",
    },
    "Dépôt GitHub": {
        "fr": "Dépôt GitHub",
        "en": "GitHub Repository",
        "es": "Repositorio GitHub",
        "de": "GitHub-Repository",
    },
    "Ajouter une liste": {
        "fr": "Ajouter une liste",
        "en": "Add a playlist",
        "es": "Añadir una lista",
        "de": "Wiedergabeliste hinzufügen",
    },
    "Nom de la liste :": {
        "fr": "Nom de la liste :",
        "en": "Playlist name:",
        "es": "Nombre de la lista:",
        "de": "Name der Liste:",
    },
    "Type de liste :": {
        "fr": "Type de liste :",
        "en": "Playlist type:",
        "es": "Tipo de lista:",
        "de": "Typ der Liste:",
    },
    "Fichier ou URL M3U": {
        "fr": "Fichier ou URL M3U",
        "en": "M3U File or URL",
        "es": "Archivo o URL M3U",
        "de": "M3U-Datei oder URL",
    },
    "API Xtream Codes": {
        "fr": "API Xtream Codes",
        "en": "Xtream Codes API",
        "es": "API Xtream Codes",
        "de": "Xtream Codes API",
    },
    "URL ou Chemin :": {
        "fr": "URL ou Chemin :",
        "en": "URL or Path:",
        "es": "URL o ruta:",
        "de": "URL oder Pfad:",
    },
    "Serveur (URL) :": {
        "fr": "Serveur (URL) :",
        "en": "Server (URL):",
        "es": "Servidor (URL):",
        "de": "Server (URL):",
    },
    "Nom d'utilisateur :": {
        "fr": "Nom d'utilisateur :",
        "en": "Username:",
        "es": "Nombre de usuario:",
        "de": "Benutzername:",
    },
    "Mot de passe :": {
        "fr": "Mot de passe :",
        "en": "Password:",
        "es": "Contraseña:",
        "de": "Passwort:",
    },
    "URL EPG personnalisée (optionnel) :": {
        "fr": "URL EPG personnalisée (optionnel) :",
        "en": "Custom EPG URL (optional):",
        "es": "URL EPG personalizada (opcional):",
        "de": "Benutzerdefinierte EPG-URL (optional):",
    },
    "Annuler": {
        "fr": "Annuler",
        "en": "Cancel",
        "es": "Cancelar",
        "de": "Abbrechen",
    },
    "Ajouter": {
        "fr": "Ajouter",
        "en": "Add",
        "es": "Añadir",
        "de": "Hinzufügen",
    },
    "Enregistrer": {
        "fr": "Enregistrer",
        "en": "Save",
        "es": "Guardar",
        "de": "Speichern",
    },
    "Supprimer": {
        "fr": "Supprimer",
        "en": "Delete",
        "es": "Eliminar",
        "de": "Löschen",
    },
    "Modifier": {
        "fr": "Modifier",
        "en": "Edit",
        "es": "Modificar",
        "de": "Bearbeiten",
    },
    "Actualiser": {
        "fr": "Actualiser",
        "en": "Refresh",
        "es": "Actualizar",
        "de": "Aktualisieren",
    },
    "Fermer la fenêtre": {
        "fr": "Fermer la fenêtre",
        "en": "Close window",
        "es": "Cerrar ventana",
        "de": "Fenster schließen",
    },
    "Gestion des listes de lecture": {
        "fr": "Gestion des listes de lecture",
        "en": "Manage Playlists",
        "es": "Gestión de listas de reproducción",
        "de": "Wiedergabelisten-Verwaltung",
    },
    "Êtes-vous sûr de vouloir supprimer cette liste ?": {
        "fr": "Êtes-vous sûr de vouloir supprimer cette liste ?",
        "en": "Are you sure you want to delete this playlist?",
        "es": "¿Está seguro de que desea eliminar esta lista?",
        "de": "Sind Sie sicher, dass Sie diese Wiedergabeliste löschen möchten?",
    },
    "Confirmation": {
        "fr": "Confirmation",
        "en": "Confirmation",
        "es": "Confirmación",
        "de": "Bestätigung",
    },
    "Oui": {
        "fr": "Oui",
        "en": "Yes",
        "es": "Sí",
        "de": "Ja",
    },
    "Non": {
        "fr": "Non",
        "en": "No",
        "es": "No",
        "de": "Nein",
    },
    "Filmographie de {artist}": {
        "fr": "Filmographie de {artist}",
        "en": "Filmography of {artist}",
        "es": "Filmografía de {artist}",
        "de": "Filmografie von {artist}",
    },
    "Aucun titre trouvé pour cet artiste.": {
        "fr": "Aucun titre trouvé pour cet artiste.",
        "en": "No titles found for this artist.",
        "es": "No se encontraron títulos para este artista.",
        "de": "Keine Titel für diesen Künstler gefunden.",
    },
    "Films ({count})": {
        "fr": "Films ({count})",
        "en": "Movies ({count})",
        "es": "Películas ({count})",
        "de": "Filme ({count})",
    },
    "Séries ({count})": {
        "fr": "Séries ({count})",
        "en": "Series ({count})",
        "es": "Series ({count})",
        "de": "Serien ({count})",
    },
    "Récemment ajoutés sur {name}": {
        "fr": "Récemment ajoutés sur {name}",
        "en": "Recently added on {name}",
        "es": "Añadidos recientemente en {name}",
        "de": "Kürzlich hinzugefügt auf {name}",
    },
    "Parcourir tous les films >": {
        "fr": "Parcourir tous les films >",
        "en": "Browse all movies >",
        "es": "Explorar todas las películas >",
        "de": "Alle Filme durchsuchen >",
    },
    "Parcourir toutes les séries >": {
        "fr": "Parcourir toutes les séries >",
        "en": "Browse all series >",
        "es": "Explorar todas las series >",
        "de": "Alle Serien durchsuchen >",
    },
    "Parcourir toute la TV en direct >": {
        "fr": "Parcourir toute la TV en direct >",
        "en": "Browse all live TV >",
        "es": "Explorar toda la TV en vivo >",
        "de": "Gesamtes Live-TV durchsuchen >",
    },
    "Cette liste de lecture": {
        "fr": "Cette liste de lecture",
        "en": "This playlist",
        "es": "Esta lista de reproducción",
        "de": "Diese Wiedergabeliste",
    },
    "  Cette liste de lecture": {
        "fr": "  Cette liste de lecture",
        "en": "  This playlist",
        "es": "  Esta lista de reproducción",
        "de": "  Diese Wiedergabeliste",
    },
    "Toutes les listes de lecture": {
        "fr": "Toutes les listes de lecture",
        "en": "All playlists",
        "es": "Todas las listas de reproducción",
        "de": "Alle Wiedergabelisten",
    },
    "  Toutes les listes de lecture": {
        "fr": "  Toutes les listes de lecture",
        "en": "  All playlists",
        "es": "  Todas las listas de reproducción",
        "de": "  Alle Wiedergabelisten",
    },
    "Récemment regardés": {
        "fr": "Récemment regardés",
        "en": "Recently Watched",
        "es": "Vistos recientemente",
        "de": "Kürzlich angesehen",
    },
    "Vider tous les favoris affichés": {
        "fr": "Vider tous les favoris affichés",
        "en": "Clear all displayed favorites",
        "es": "Vaciar todos los favoritos mostrados",
        "de": "Alle angezeigten Favoriten leeren",
    },
    "Aujourd'hui, {time}": {
        "fr": "Aujourd'hui, {time}",
        "en": "Today, {time}",
        "es": "Hoy, {time}",
        "de": "Heute, {time}",
    },
    "Hier, {time}": {
        "fr": "Hier, {time}",
        "en": "Yesterday, {time}",
        "es": "Ayer, {time}",
        "de": "Gestern, {time}",
    },
    "Aller à maintenant": {
        "fr": "Aller à maintenant",
        "en": "Go to Now",
        "es": "Ir a ahora",
        "de": "Zu Jetzt springen",
    },
    " Aller à maintenant": {
        "fr": " Aller à maintenant",
        "en": " Go to Now",
        "es": " Ir a ahora",
        "de": " Zu Jetzt springen",
    },
    "🕒 Maintenant": {
        "fr": "🕒 Maintenant",
        "en": "🕒 Now",
        "es": "🕒 Ahora",
        "de": "🕒 Jetzt",
    },
    "Centrer la frise sur l'heure actuelle": {
        "fr": "Centrer la frise sur l'heure actuelle",
        "en": "Center timeline on current time",
        "es": "Centrar la línea temporal en la hora actual",
        "de": "Zeitleiste auf aktuelle Uhrzeit zentrieren",
    },
    "Rechercher une chaîne...": {
        "fr": "Rechercher une chaîne...",
        "en": "Search a channel...",
        "es": "Buscar un canal...",
        "de": "Kanal suchen...",
    },
    "Gérer et filtrer les catégories et chaînes": {
        "fr": "Gérer et filtrer les catégories et chaînes",
        "en": "Manage and filter categories and channels",
        "es": "Gestionar y filtrar categorías y canales",
        "de": "Kategorien und Kanäle verwalten und filtern",
    },
    "Zoomer la frise temporelle": {
        "fr": "Zoomer la frise temporelle",
        "en": "Zoom in timeline",
        "es": "Acercar zoom de la línea temporal",
        "de": "Zeitleiste vergrößern",
    },
    "Dézoomer la frise temporelle": {
        "fr": "Dézoomer la frise temporelle",
        "en": "Zoom out timeline",
        "es": "Alejar zoom de la línea temporal",
        "de": "Zeitleiste verkleinern",
    },
    "Sélectionnez une émission": {
        "fr": "Sélectionnez une émission",
        "en": "Select a show",
        "es": "Seleccione un programa",
        "de": "Wählen Sie eine Sendung aus",
    },
    "Aucun programme sélectionné": {
        "fr": "Aucun programme sélectionné",
        "en": "No program selected",
        "es": "Ningún programa seleccionado",
        "de": "Keine Sendung ausgewählt",
    },
    "Cliquez sur un programme dans la grille ci-dessous pour voir ses détails ou double-cliquez pour regarder la chaîne.": {
        "fr": "Cliquez sur un programme dans la grille ci-dessous pour voir ses détails ou double-cliquez pour regarder la chaîne.",
        "en": "Click on a show in the grid below to view details or double-click to watch the channel.",
        "es": "Haga clic en un programa en la cuadrícula para ver detalles o doble clic para ver el canal.",
        "de": "Klicken Sie auf eine Sendung in der Übersicht für Details oder doppelklicken Sie, um den Kanal anzusehen.",
    },
    "Cliquez sur un programme dans la grille ci-dessous pour voir ses détails.": {
        "fr": "Cliquez sur un programme dans la grille ci-dessous pour voir ses détails.",
        "en": "Click on a show in the grid below to view its details.",
        "es": "Haga clic en un programa en la cuadrícula para ver sus detalles.",
        "de": "Klicken Sie auf eine Sendung in der Übersicht, um Details anzuzeigen.",
    },
    "Regarder la chaîne": {
        "fr": "Regarder la chaîne",
        "en": "Watch channel",
        "es": "Ver canal",
        "de": "Kanal ansehen",
    },
    " Regarder la chaîne": {
        "fr": " Regarder la chaîne",
        "en": " Watch channel",
        "es": " Ver canal",
        "de": " Kanal ansehen",
    },
    "EN DIRECT": {
        "fr": "EN DIRECT",
        "en": "LIVE",
        "es": "EN DIRECTO",
        "de": "LIVE",
    },
    "Durée : {dur}": {
        "fr": "Durée : {dur}",
        "en": "Duration: {dur}",
        "es": "Duración: {dur}",
        "de": "Dauer: {dur}",
    },
    "Guide indisponible": {
        "fr": "Guide indisponible",
        "en": "Guide unavailable",
        "es": "Guía no disponible",
        "de": "Programmführer nicht verfügbar",
    },
    "Aucune information de programme EPG trouvée pour {channel}.": {
        "fr": "Aucune information de programme EPG trouvée pour {channel}.",
        "en": "No EPG program information found for {channel}.",
        "es": "No se encontró información EPG para {channel}.",
        "de": "Keine EPG-Programminformationen für {channel} gefunden.",
    },
    "Aucun synopsis détaillé n'est fourni pour cette émission.": {
        "fr": "Aucun synopsis détaillé n'est fourni pour cette émission.",
        "en": "No detailed synopsis is provided for this show.",
        "es": "No hay sinopsis detallada disponible para este programa.",
        "de": "Für diese Sendung ist keine detaillierte Beschreibung verfügbar.",
    },
    "ℹ Programme uniquement. Ce fournisseur expose l'historique mais pas le catch-up.": {
        "fr": "ℹ Programme uniquement. Ce fournisseur expose l'historique mais pas le catch-up.",
        "en": "ℹ Schedule only. This provider exposes history but not catch-up playback.",
        "es": "ℹ Solo programación. Este proveedor ofrece historial pero no catch-up.",
        "de": "ℹ Nur Programmübersicht. Dieser Anbieter stellt den Verlauf, aber kein Replay bereit.",
    },
    "Revoyez vos émissions préférées des 7 derniers jours sur les chaînes compatibles.": {
        "fr": "Revoyez vos émissions préférées des 7 derniers jours sur les chaînes compatibles.",
        "en": "Watch your favorite shows from the last 7 days on supported channels.",
        "es": "Vuelva a ver sus programas favoritos de los últimos 7 días en canales compatibles.",
        "de": "Sehen Sie Ihre Lieblingssendungen der letzten 7 Tage auf kompatiblen Sendern.",
    },
    "0 chaîne compatible Replay": {
        "fr": "0 chaîne compatible Replay",
        "en": "0 replay-compatible channel",
        "es": "0 canales compatibles con Replay",
        "de": "0 Replay-kompatible Kanäle",
    },
    "{count} chaînes compatibles Replay": {
        "fr": "{count} chaînes compatibles Replay",
        "en": "{count} replay-compatible channels",
        "es": "{count} canales compatibles con Replay",
        "de": "{count} Replay-kompatible Kanäle",
    },
    "{count} chaîne compatible": {
        "fr": "{count} chaîne compatible",
        "en": "{count} compatible channel",
        "es": "{count} canal compatible",
        "de": "{count} kompatibler Kanal",
    },
    "{count} chaînes compatibles": {
        "fr": "{count} chaînes compatibles",
        "en": "{count} compatible channels",
        "es": "{count} canales compatibles",
        "de": "{count} kompatible Kanäle",
    },
    "Sélectionnez une chaîne pour voir les programmes": {
        "fr": "Sélectionnez une chaîne pour voir les programmes",
        "en": "Select a channel to view programs",
        "es": "Seleccione un canal para ver los programas",
        "de": "Wählen Sie einen Kanal, um Sendungen anzuzeigen",
    },
    "Programmes : {name}": {
        "fr": "Programmes : {name}",
        "en": "Programs: {name}",
        "es": "Programas: {name}",
        "de": "Sendungen: {name}",
    },
    "Aucune chaîne avec Replay disponible.": {
        "fr": "Aucune chaîne avec Replay disponible.",
        "en": "No channels with Replay available.",
        "es": "No hay canales con Replay disponible.",
        "de": "Keine Kanäle mit Replay verfügbar.",
    },
    "Chargement du guide...": {
        "fr": "Chargement du guide...",
        "en": "Loading guide...",
        "es": "Cargando guía...",
        "de": "Programmführer wird geladen...",
    },
    "Replay disponible uniquement sur les flux Xtream.": {
        "fr": "Replay disponible uniquement sur les flux Xtream.",
        "en": "Replay available only on Xtream streams.",
        "es": "Replay disponible únicamente en transmisiones Xtream.",
        "de": "Replay ist nur bei Xtream-Streams verfügbar.",
    },
    "Impossible de charger les programmes d'archive.": {
        "fr": "Impossible de charger les programmes d'archive.",
        "en": "Unable to load archive programs.",
        "es": "No se pueden cargar los programas de archivo.",
        "de": "Archivprogramme konnten nicht geladen werden.",
    },
    "Aucun programme répertorié pour cette chaîne.": {
        "fr": "Aucun programme répertorié pour cette chaîne.",
        "en": "No programs listed for this channel.",
        "es": "No hay programas listados para este canal.",
        "de": "Keine Sendungen für diesen Kanal aufgeführt.",
    },
    "0 programme": {
        "fr": "0 programme",
        "en": "0 program",
        "es": "0 programas",
        "de": "0 Sendungen",
    },
    "{count} programme": {
        "fr": "{count} programme",
        "en": "{count} program",
        "es": "{count} programa",
        "de": "{count} Sendung",
    },
    "{count} programmes": {
        "fr": "{count} programmes",
        "en": "{count} programs",
        "es": "{count} programas",
        "de": "{count} Sendungen",
    },
    "Aucun programme trouvé pour le {date}.": {
        "fr": "Aucun programme trouvé pour le {date}.",
        "en": "No programs found for {date}.",
        "es": "No se encontraron programas para el {date}.",
        "de": "Keine Sendungen für den {date} gefunden.",
    },
    "0 émission trouvée": {
        "fr": "0 émission trouvée",
        "en": "0 show found",
        "es": "0 programas encontrados",
        "de": "0 Sendungen gefunden",
    },
    "{count} émission(s) trouvée(s)": {
        "fr": "{count} émission(s) trouvée(s)",
        "en": "{count} show(s) found",
        "es": "{count} programa(s) encontrado(s)",
        "de": "{count} Sendung(en) gefunden",
    },
    "Revoir": {
        "fr": "Revoir",
        "en": "Watch",
        "es": "Repetir",
        "de": "Wiederholen",
    },
    " Revoir": {
        "fr": " Revoir",
        "en": " Watch",
        "es": " Repetir",
        "de": " Wiederholen",
    },
    "À venir": {
        "fr": "À venir",
        "en": "Upcoming",
        "es": "Próximamente",
        "de": "Demnächst",
    },
    "Sans titre": {
        "fr": "Sans titre",
        "en": "Untitled",
        "es": "Sin título",
        "de": "Ohne Titel",
    },
    "Aucun élément récent dans {category}.": {
        "fr": "Aucun élément récent dans {category}.",
        "en": "No recent items in {category}.",
        "es": "No hay elementos recientes en {category}.",
        "de": "Keine aktuellen Einträge in {category}.",
    },
    "Catégories en direct": {
        "fr": "Catégories en direct",
        "en": "Live Categories",
        "es": "Categorías en vivo",
        "de": "Live-Kategorien",
    },
    "Catégories de films": {
        "fr": "Catégories de films",
        "en": "Movie Categories",
        "es": "Categorías de películas",
        "de": "Film-Kategorien",
    },
    "Catégories Séries": {
        "fr": "Catégories Séries",
        "en": "Series Categories",
        "es": "Categorías de series",
        "de": "Serien-Kategorien",
    },
    "Catégories Favoris": {
        "fr": "Catégories Favoris",
        "en": "Favorite Categories",
        "es": "Categorías de favoritos",
        "de": "Favoriten-Kategorien",
    },
    "Rechercher une catégorie": {
        "fr": "Rechercher une catégorie",
        "en": "Search a category",
        "es": "Buscar una categoría",
        "de": "Kategorie suchen",
    },
    "Gérer et filtrer les catégories": {
        "fr": "Gérer et filtrer les catégories",
        "en": "Manage and filter categories",
        "es": "Gestionar y filtrar categorías",
        "de": "Kategorien verwalten und filtern",
    },
    "Tout sélectionner": {
        "fr": "Tout sélectionner",
        "en": "Select all",
        "es": "Seleccionar todo",
        "de": "Alles auswählen",
    },
    " Tout sélectionner": {
        "fr": " Tout sélectionner",
        "en": " Select all",
        "es": " Seleccionar todo",
        "de": " Alles auswählen",
    },
    "Tout désélectionner": {
        "fr": "Tout désélectionner",
        "en": "Deselect all",
        "es": "Deseleccionar todo",
        "de": "Alles abwählen",
    },
    " Tout désélectionner": {
        "fr": " Tout désélectionner",
        "en": " Deselect all",
        "es": " Deseleccionar todo",
        "de": " Alles abwählen",
    },
    "Rechercher des catégories ou des chaînes...": {
        "fr": "Rechercher des catégories ou des chaînes...",
        "en": "Search categories or channels...",
        "es": "Buscar categorías o canales...",
        "de": "Kategorien oder Kanäle suchen...",
    },
    "Sélectionnées: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} groupes)": {
        "fr": "Sélectionnées: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} groupes)",
        "en": "Selected: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} groups)",
        "es": "Seleccionadas: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} grupos)",
        "de": "Ausgewählt: <b style='color:#38bdf8;'>{selected}</b> / {total}  ({sel_groups} / {tot_groups} Gruppen)",
    },
    "Sélectionnées: 0 / 0 (0 / 0 groupes)": {
        "fr": "Sélectionnées: 0 / 0 (0 / 0 groupes)",
        "en": "Selected: 0 / 0 (0 / 0 groups)",
        "es": "Seleccionadas: 0 / 0 (0 / 0 grupos)",
        "de": "Ausgewählt: 0 / 0 (0 / 0 Gruppen)",
    },
    "Listes de lecture enregistrées": {
        "fr": "Listes de lecture enregistrées",
        "en": "Saved playlists",
        "es": "Listas de reproducción guardadas",
        "de": "Gespeicherte Wiedergabelisten",
    },
    "Synchronisation de '{name}' en cours...": {
        "fr": "Synchronisation de '{name}' en cours...",
        "en": "Syncing '{name}'...",
        "es": "Sincronizando '{name}'...",
        "de": "Synchronisiere '{name}'...",
    },
    "Synchronisation réussie !": {
        "fr": "Synchronisation réussie !",
        "en": "Sync successful!",
        "es": "¡Sincronización exitosa!",
        "de": "Synchronisierung erfolgreich!",
    },
    "Erreur de synchronisation": {
        "fr": "Erreur de synchronisation",
        "en": "Sync error",
        "es": "Error de sincronización",
        "de": "Synchronisierungsfehler",
    },
    "Impossible de synchroniser la liste :\n{error}": {
        "fr": "Impossible de synchroniser la liste :\n{error}",
        "en": "Unable to sync playlist:\n{error}",
        "es": "No se pudo sincronizar la lista:\n{error}",
        "de": "Wiedergabeliste konnte nicht synchronisiert werden:\n{error}",
    },
    "Confirmer la suppression": {
        "fr": "Confirmer la suppression",
        "en": "Confirm deletion",
        "es": "Confirmar eliminación",
        "de": "Löschen bestätigen",
    },
    "Êtes-vous sûr de vouloir supprimer cette liste de lecture et toutes ses chaînes de SQLite ?": {
        "fr": "Êtes-vous sûr de vouloir supprimer cette liste de lecture et toutes ses chaînes de SQLite ?",
        "en": "Are you sure you want to delete this playlist and all its channels from SQLite?",
        "es": "¿Está seguro de que desea eliminar esta lista de reproducción y todos sus canales de SQLite?",
        "de": "Sind Sie sicher, dass Sie diese Wiedergabeliste und alle zugehörigen Kanäle aus SQLite löschen möchten?",
    },
    "Inactif": {
        "fr": "Inactif",
        "en": "Inactive",
        "es": "Inactivo",
        "de": "Inaktiv",
    },
    "Écrans : {active} / {max}": {
        "fr": "Écrans : {active} / {max}",
        "en": "Screens: {active} / {max}",
        "es": "Pantallas: {active} / {max}",
        "de": "Bildschirme: {active} / {max}",
    },
    "Expiration : {date}": {
        "fr": "Expiration : {date}",
        "en": "Expiration: {date}",
        "es": "Vencimiento: {date}",
        "de": "Ablauf: {date}",
    },
    " Ajouter une liste": {
        "fr": " Ajouter une liste",
        "en": " Add a playlist",
        "es": " Añadir una lista",
        "de": " Wiedergabeliste hinzufügen",
    },
    " Fermer": {
        "fr": " Fermer",
        "en": " Close",
        "es": " Cerrar",
        "de": " Schließen",
    },
    " Recharger": {
        "fr": " Recharger",
        "en": " Reload",
        "es": " Recargar",
        "de": " Neu laden",
    },
    " Modifier": {
        "fr": " Modifier",
        "en": " Edit",
        "es": " Modificar",
        "de": " Bearbeiten",
    },
    " Supprimer": {
        "fr": " Supprimer",
        "en": " Delete",
        "es": " Eliminar",
        "de": " Löschen",
    },
    "Recharger et synchroniser les flux depuis le serveur": {
        "fr": "Recharger et synchroniser les flux depuis le serveur",
        "en": "Reload and sync streams from server",
        "es": "Recargar y sincronizar transmisiones desde el servidor",
        "de": "Streams vom Server neu laden und synchronisieren",
    },
    "Modifier les identifiants ou l'URL de cette liste": {
        "fr": "Modifier les identifiants ou l'URL de cette liste",
        "en": "Edit credentials or URL of this playlist",
        "es": "Modificar credenciales o URL de esta lista",
        "de": "Zugangsdaten oder URL dieser Wiedergabeliste bearbeiten",
    },
    "Supprimer cette liste de lecture et ses chaînes de SQLite": {
        "fr": "Supprimer cette liste de lecture et ses chaînes de SQLite",
        "en": "Delete this playlist and its channels from SQLite",
        "es": "Eliminar esta lista de reproducción y sus canales de SQLite",
        "de": "Diese Wiedergabeliste und deren Kanäle aus SQLite löschen",
    },
    "Source : {source}": {
        "fr": "Source : {source}",
        "en": "Source: {source}",
        "es": "Fuente: {source}",
        "de": "Quelle: {source}",
    },
    "chaînes TV": {
        "fr": "chaînes TV",
        "en": "TV channels",
        "es": "canales de TV",
        "de": "TV-Sender",
    },
    "Statut": {
        "fr": "Statut",
        "en": "Status",
        "es": "Estado",
        "de": "Status",
    },
    "Statut : {status}": {
        "fr": "Statut : {status}",
        "en": "Status: {status}",
        "es": "Estado: {status}",
        "de": "Status: {status}",
    },
    "Expiration": {
        "fr": "Expiration",
        "en": "Expiration",
        "es": "Expiración",
        "de": "Ablauf",
    },
    "Expire : {date}": {
        "fr": "Expire : {date}",
        "en": "Expires: {date}",
        "es": "Vence: {date}",
        "de": "Läuft ab: {date}",
    },
    "Connexions": {
        "fr": "Connexions",
        "en": "Connections",
        "es": "Conexiones",
        "de": "Verbindungen",
    },
    "Connexions : {active}/{max}": {
        "fr": "Connexions : {active}/{max}",
        "en": "Connections: {active}/{max}",
        "es": "Conexiones: {active}/{max}",
        "de": "Verbindungen: {active}/{max}",
    },
    "Illimitée": {
        "fr": "Illimitée",
        "en": "Unlimited",
        "es": "Ilimitada",
        "de": "Unbegrenzt",
    },
    "Expiré": {
        "fr": "Expiré",
        "en": "Expired",
        "es": "Expirado",
        "de": "Abgelaufen",
    },
    "Expiré ({date})": {
        "fr": "Expiré ({date})",
        "en": "Expired ({date})",
        "es": "Expirado ({date})",
        "de": "Abgelaufen ({date})",
    },
    "{days} j restants": {
        "fr": "{days} j restants",
        "en": "{days} d remaining",
        "es": "Quedan {days} d",
        "de": "Noch {days} T.",
    },
    "Inconnue": {
        "fr": "Inconnue",
        "en": "Unknown",
        "es": "Desconocida",
        "de": "Unbekannt",
    },
    "Inconnu": {
        "fr": "Inconnu",
        "en": "Unknown",
        "es": "Desconocido",
        "de": "Unbekannt",
    },
    "Actif": {
        "fr": "Actif",
        "en": "Active",
        "es": "Activo",
        "de": "Aktiv",
    },
    "Aucune liste de lecture enregistrée dans la base SQLite.\nCliquez sur 'Ajouter une liste' pour importer vos chaînes Xtream ou M3U.": {
        "fr": "Aucune liste de lecture enregistrée dans la base SQLite.\nCliquez sur 'Ajouter une liste' pour importer vos chaînes Xtream ou M3U.",
        "en": "No playlists saved in SQLite database.\nClick 'Add a playlist' to import your Xtream or M3U channels.",
        "es": "No hay listas de reproducción guardadas en SQLite.\nHaga clic en 'Añadir una lista' para importar sus canales Xtream o M3U.",
        "de": "Keine Wiedergabelisten in SQLite gespeichert.\nKlicken Sie auf 'Wiedergabeliste hinzufügen', um Ihre Xtream- oder M3U-Kanäle zu importieren.",
    },
    "FICHE DU FILM": {
        "fr": "FICHE DU FILM",
        "en": "MOVIE DETAILS",
        "es": "DETALLES DE LA PELÍCULA",
        "de": "FILMINFORMATIONEN",
    },
    "FICHE DE LA SÉRIE": {
        "fr": "FICHE DE LA SÉRIE",
        "en": "SERIES DETAILS",
        "es": "DETALLES DE LA SERIE",
        "de": "SERIENINFORMATIONEN",
    },
    "Retour à la galerie de films": {
        "fr": "Retour à la galerie de films",
        "en": "Back to movie gallery",
        "es": "Volver a la galería de películas",
        "de": "Zurück zur Filmgalerie",
    },
    "Retour à la galerie de séries": {
        "fr": "Retour à la galerie de séries",
        "en": "Back to series gallery",
        "es": "Volver a la galería de series",
        "de": "Zurück zur Seriengalerie",
    },
    "Titre du film": {
        "fr": "Titre du film",
        "en": "Movie Title",
        "es": "Título de la película",
        "de": "Filmtitel",
    },
    "Titre de la série": {
        "fr": "Titre de la série",
        "en": "Series Title",
        "es": "Título de la serie",
        "de": "Serientitel",
    },
    "Chargement des informations...": {
        "fr": "Chargement des informations...",
        "en": "Loading information...",
        "es": "Cargando información...",
        "de": "Informationen werden geladen...",
    },
    "Aucun résumé disponible pour ce film.": {
        "fr": "Aucun résumé disponible pour ce film.",
        "en": "No plot summary available for this movie.",
        "es": "No hay sinopsis disponible para esta película.",
        "de": "Keine Handlungsbeschreibung für diesen Film verfügbar.",
    },
    "Aucune description disponible.": {
        "fr": "Aucune description disponible.",
        "en": "No description available.",
        "es": "No hay descripción disponible.",
        "de": "Keine Beschreibung verfügbar.",
    },
    "Prêt pour le streaming en haute définition.": {
        "fr": "Prêt pour le streaming en haute définition.",
        "en": "Ready for high definition streaming.",
        "es": "Listo para transmisión en alta definición.",
        "de": "Bereit für Streaming in High Definition.",
    },
    "Regarder le film": {
        "fr": "Regarder le film",
        "en": "Watch movie",
        "es": "Ver película",
        "de": "Film ansehen",
    },
    "  Regarder le film": {
        "fr": "  Regarder le film",
        "en": "  Watch movie",
        "es": "  Ver película",
        "de": "  Film ansehen",
    },
    "Lancer la lecture": {
        "fr": "Lancer la lecture",
        "en": "Play",
        "es": "Iniciar reproducción",
        "de": "Wiedergabe starten",
    },
    "  Lancer la lecture": {
        "fr": "  Lancer la lecture",
        "en": "  Start watching",
        "es": "  Iniciar reproducción",
        "de": "  Wiedergabe starten",
    },
    "Reprendre l'épisode": {
        "fr": "Reprendre l'épisode",
        "en": "Resume episode",
        "es": "Reanudar episodio",
        "de": "Folge fortsetzen",
    },
    "  Reprendre l'épisode": {
        "fr": "  Reprendre l'épisode",
        "en": "  Resume episode",
        "es": "  Reanudar episodio",
        "de": "  Folge fortsetzen",
    },
    "Du début": {
        "fr": "Du début",
        "en": "From beginning",
        "es": "Desde el principio",
        "de": "Von Anfang an",
    },
    "  Du début": {
        "fr": "  Du début",
        "en": "  From beginning",
        "es": "  Desde el principio",
        "de": "  Von Anfang an",
    },
    "Annuler reprise": {
        "fr": "Annuler reprise",
        "en": "Clear progress",
        "es": "Borrar progreso",
        "de": "Fortschritt löschen",
    },
    "  Annuler reprise": {
        "fr": "  Annuler reprise",
        "en": "  Clear resume",
        "es": "  Borrar progreso",
        "de": "  Fortschritt löschen",
    },
    "  Ajouter aux favoris": {
        "fr": "  Ajouter aux favoris",
        "en": "  Add to favorites",
        "es": "  Añadir a favoritos",
        "de": "  Zu Favoriten hinzufügen",
    },
    "  Retirer des favoris": {
        "fr": "  Retirer des favoris",
        "en": "  Remove from favorites",
        "es": "  Quitar de favoritos",
        "de": "  Aus Favoriten entfernen",
    },
    "Télécharger": {
        "fr": "Télécharger",
        "en": "Download",
        "es": "Descargar",
        "de": "Herunterladen",
    },
    "  Télécharger": {
        "fr": "  Télécharger",
        "en": "  Download",
        "es": "  Descargar",
        "de": "  Herunterladen",
    },
    "Téléchargement...": {
        "fr": "Téléchargement...",
        "en": "Downloading...",
        "es": "Descargando...",
        "de": "Herunterladen...",
    },
    "  Téléchargement...": {
        "fr": "  Téléchargement...",
        "en": "  Downloading...",
        "es": "  Descargando...",
        "de": "  Wird heruntergeladen...",
    },
    "✓ Téléchargé": {
        "fr": "✓ Téléchargé",
        "en": "✓ Downloaded",
        "es": "✓ Descargado",
        "de": "✓ Heruntergeladen",
    },
    "  ✓ Téléchargé": {
        "fr": "  ✓ Téléchargé",
        "en": "  ✓ Downloaded",
        "es": "  ✓ Descargado",
        "de": "  ✓ Heruntergeladen",
    },
    "Genre :": {
        "fr": "Genre :",
        "en": "Genre:",
        "es": "Género:",
        "de": "Genre:",
    },
    "Durée :": {
        "fr": "Durée :",
        "en": "Duration:",
        "es": "Duración:",
        "de": "Dauer:",
    },
    "Réalisateur :": {
        "fr": "Réalisateur :",
        "en": "Director:",
        "es": "Director:",
        "de": "Regie:",
    },
    "Acteurs :": {
        "fr": "Acteurs :",
        "en": "Cast:",
        "es": "Actores:",
        "de": "Darsteller:",
    },
    "Distribution :": {
        "fr": "Distribution :",
        "en": "Cast:",
        "es": "Reparto:",
        "de": "Besetzung:",
    },
    "Synopsis :": {
        "fr": "Synopsis :",
        "en": "Synopsis:",
        "es": "Sinopsis:",
        "de": "Handlung:",
    },
    "Saisons et épisodes": {
        "fr": "Saisons et épisodes",
        "en": "Seasons and episodes",
        "es": "Temporadas y episodios",
        "de": "Staffeln und Folgen",
    },
    "Saison {num}": {
        "fr": "Saison {num}",
        "en": "Season {num}",
        "es": "Temporada {num}",
        "de": "Staffel {num}",
    },
    "Épisode {num}": {
        "fr": "Épisode {num}",
        "en": "Episode {num}",
        "es": "Episodio {num}",
        "de": "Folge {num}",
    },
    "Bande-annonce du film": {
        "fr": "Bande-annonce du film",
        "en": "Movie trailer",
        "es": "Tráiler de la película",
        "de": "Filmtrailer",
    },
    "Bande-annonce de la série": {
        "fr": "Bande-annonce de la série",
        "en": "Series Trailer",
        "es": "Tráiler de la serie",
        "de": "Serientrailer",
    },
    "Bande-annonce d'origine": {
        "fr": "Bande-annonce d'origine",
        "en": "Original trailer",
        "es": "Tráiler original",
        "de": "Original-Trailer",
    },
    "Regarder sur YouTube": {
        "fr": "Regarder sur YouTube",
        "en": "Watch on YouTube",
        "es": "Ver en YouTube",
        "de": "Auf YouTube ansehen",
    },
    "Cliquer pour regarder la bande-annonce dans l'application": {
        "fr": "Cliquer pour regarder la bande-annonce dans l'application",
        "en": "Click to watch trailer inside application",
        "es": "Haga clic para ver el tráiler en la aplicación",
        "de": "Klicken, um den Trailer in der Anwendung anzusehen",
    },
    "Ouvrir la bande-annonce sur YouTube dans le navigateur": {
        "fr": "Ouvrir la bande-annonce sur YouTube dans le navigateur",
        "en": "Open trailer on YouTube in external browser",
        "es": "Abrir el tráiler en YouTube en el navegador",
        "de": "Trailer auf YouTube im Browser öffnen",
    },
    "Tout marquer comme vu": {
        "fr": "Tout marquer comme vu",
        "en": "Mark all as watched",
        "es": "Marcar todo como visto",
        "de": "Alles als gesehen markieren",
    },
    "Réinitialiser la saison": {
        "fr": "Réinitialiser la saison",
        "en": "Reset season",
        "es": "Restablecer temporada",
        "de": "Staffel zurücksetzen",
    },
    "Artiste": {
        "fr": "Artiste",
        "en": "Artist",
        "es": "Artista",
        "de": "Künstler",
    },
    " Artiste": {
        "fr": " Artiste",
        "en": " Artist",
        "es": " Artista",
        "de": " Künstler",
    },
    "Rechercher un acteur ou réalisateur (expérimental)": {
        "fr": "Rechercher un acteur ou réalisateur (expérimental)",
        "en": "Search an actor or director (experimental)",
        "es": "Buscar un actor o director (experimental)",
        "de": "Schauspieler oder Regisseur suchen (experimentell)",
    },
    "Voir la filmographie": {
        "fr": "Voir la filmographie",
        "en": "View filmography",
        "es": "Ver filmografía",
        "de": "Filmografie ansehen",
    },
    " Voir la filmographie": {
        "fr": " Voir la filmographie",
        "en": " View filmography",
        "es": " Ver filmografía",
        "de": " Filmografie ansehen",
    },
    "Rechercher \"{query}\" parmi les artistes": {
        "fr": "Rechercher \"{query}\" parmi les artistes",
        "en": "Search \"{query}\" among artists",
        "es": "Buscar \"{query}\" entre artistas",
        "de": "\"{query}\" unter Künstlern suchen",
    },
    " Rechercher \"{query}\" parmi les artistes": {
        "fr": " Rechercher \"{query}\" parmi les artistes",
        "en": " Search \"{query}\" among artists",
        "es": " Buscar \"{query}\" entre artistas",
        "de": " \"{query}\" unter Künstlern suchen",
    },
    "Filmographie de l'artiste": {
        "fr": "Filmographie de l'artiste",
        "en": "Artist filmography",
        "es": "Filmografía del artista",
        "de": "Filmografie des Künstlers",
    },
    "Recherche des informations sur TMDB...": {
        "fr": "Recherche des informations sur TMDB...",
        "en": "Searching TMDB for information...",
        "es": "Buscando información en TMDB...",
        "de": "Informationen auf TMDB werden gesucht...",
    },
    "Recherche des titres disponibles dans votre abonnement IPTV...": {
        "fr": "Recherche des titres disponibles dans votre abonnement IPTV...",
        "en": "Searching available titles in your IPTV library...",
        "es": "Buscando títulos disponibles en su suscripción IPTV...",
        "de": "Verfügbare Titel in Ihrem IPTV-Abonnement werden gesucht...",
    },
    "Films disponibles ({count})": {
        "fr": "Films disponibles ({count})",
        "en": "Available Movies ({count})",
        "es": "Películas disponibles ({count})",
        "de": "Verfügbare Filme ({count})",
    },
    "Séries disponibles ({count})": {
        "fr": "Séries disponibles ({count})",
        "en": "Available Series ({count})",
        "es": "Series disponibles ({count})",
        "de": "Verfügbare Serien ({count})",
    },
    "Aucun titre disponible trouvé dans votre bibliothèque IPTV.": {
        "fr": "Aucun titre disponible trouvé dans votre bibliothèque IPTV.",
        "en": "No available titles found in your IPTV library.",
        "es": "No se encontraron títulos disponibles en su biblioteca IPTV.",
        "de": "Keine verfügbaren Titel in Ihrer IPTV-Bibliothek gefunden.",
    },
    "Aucune information trouvée pour '{name}' sur TMDB.": {
        "fr": "Aucune information trouvée pour '{name}' sur TMDB.",
        "en": "No information found for '{name}' on TMDB.",
        "es": "No se encontró información para '{name}' en TMDB.",
        "de": "Keine Informationen für '{name}' auf TMDB gefunden.",
    },
    "Masquage auto de l'OSD :": {
        "fr": "Masquage auto de l'OSD :",
        "en": "Auto-hide OSD:",
        "es": "Ocultación automática del OSD:",
        "de": "Automatisches Ausblenden des OSD:",
    },
    "{n} secondes": {
        "fr": "{n} secondes",
        "en": "{n} seconds",
        "es": "{n} segundos",
        "de": "{n} Sekunden",
    },
    "Afficher la date d'ajout sur les affiches (VOD & Séries)": {
        "fr": "Afficher la date d'ajout sur les affiches (VOD & Séries)",
        "en": "Show addition date on posters (VOD & Series)",
        "es": "Mostrar fecha de adición en los pósteres (VOD y series)",
        "de": "Hinzufügedatum auf Postern anzeigen (VOD & Serien)",
    },
    "Affiche un discret badge en bas à droite indiquant la date d'ajout du film ou de la série": {
        "fr": "Affiche un discret badge en bas à droite indiquant la date d'ajout du film ou de la série",
        "en": "Displays a discreet badge at bottom right showing the movie or series addition date",
        "es": "Muestra una insignia discreta abajo a la derecha con la fecha de adición de la película o serie",
        "de": "Zeigt unten rechts ein dezentes Abzeichen mit dem Hinzufügedatum des Films oder der Serie",
    },
    "Afficher la vignette de la chaîne dans la liste en direct": {
        "fr": "Afficher la vignette de la chaîne dans la liste en direct",
        "en": "Show channel thumbnail in live list",
        "es": "Mostrar miniatura del canal en la lista en vivo",
        "de": "Sender-Miniaturbild in der Live-Liste anzeigen",
    },
    "Lecteur Vidéo & Rendu": {
        "fr": "Lecteur Vidéo & Rendu",
        "en": "Video Player & Rendering",
        "es": "Reproductor de vídeo y renderizado",
        "de": "Videoplayer & Rendering",
    },
    "Configurez le moteur de lecture libmpv, l'accélération matérielle et le comportement vidéo.": {
        "fr": "Configurez le moteur de lecture libmpv, l'accélération matérielle et le comportement vidéo.",
        "en": "Configure libmpv playback engine, hardware acceleration and video behavior.",
        "es": "Configure el motor libmpv, la aceleración por hardware y el comportamiento del vídeo.",
        "de": "Konfigurieren Sie libmpv-Wiedergabe, Hardwarebeschleunigung und Videoverhalten.",
    },
    "Accélération matérielle :": {
        "fr": "Accélération matérielle :",
        "en": "Hardware Acceleration:",
        "es": "Aceleración por hardware:",
        "de": "Hardwarebeschleunigung:",
    },
    "Désactivée (Logicielle)": {
        "fr": "Désactivée (Logicielle)",
        "en": "Disabled (Software)",
        "es": "Desactivada (software)",
        "de": "Deaktiviert (Software)",
    },
    "Direct3D 11 (d3d11va)": {
        "fr": "Direct3D 11 (d3d11va)",
        "en": "Direct3D 11 (d3d11va)",
        "es": "Direct3D 11 (d3d11va)",
        "de": "Direct3D 11 (d3d11va)",
    },
    "Format des sous-titres :": {
        "fr": "Format des sous-titres :",
        "en": "Subtitles Format:",
        "es": "Formato de subtítulos:",
        "de": "Untertitelformat:",
    },
    "Enchaîner automatiquement sur l'épisode suivant (Séries)": {
        "fr": "Enchaîner automatiquement sur l'épisode suivant (Séries)",
        "en": "Automatically play next episode (Series)",
        "es": "Reproducir automáticamente siguiente episodio (Series)",
        "de": "Nächste Folge automatisch abspielen (Serien)",
    },
    "Passe immédiatement à l'épisode suivant lorsque le fichier en cours atteint sa fin": {
        "fr": "Passe immédiatement à l'épisode suivant lorsque le fichier en cours atteint sa fin",
        "en": "Immediately advances to next episode when the current episode ends",
        "es": "Pasa de inmediato al siguiente episodio cuando finaliza el actual",
        "de": "Wechselt sofort zur nächsten Folge, wenn die aktuelle endet",
    },
    "Reprendre automatiquement la lecture où vous l'avez laissée": {
        "fr": "Reprendre automatiquement la lecture où vous l'avez laissée",
        "en": "Automatically resume playback where you left off",
        "es": "Reanudar automáticamente la reproducción donde la dejó",
        "de": "Wiedergabe automatisch dort fortsetzen, wo Sie aufgehört haben",
    },
    "Réseau & Performance": {
        "fr": "Réseau & Performance",
        "en": "Network & Performance",
        "es": "Red y rendimiento",
        "de": "Netzwerk & Leistung",
    },
    "Optimisez le streaming, la mémoire tampon et la stabilité de votre connexion.": {
        "fr": "Optimisez le streaming, la mémoire tampon et la stabilité de votre connexion.",
        "en": "Optimize streaming, buffer size and connection stability.",
        "es": "Optimice la transmisión, el búfer y la estabilidad de la conexión.",
        "de": "Optimieren Sie Streaming, Puffergröße und Verbindungsstabilität.",
    },
    "Délai d'attente réseau (Timeout) :": {
        "fr": "Délai d'attente réseau (Timeout) :",
        "en": "Network Timeout:",
        "es": "Tiempo de espera de red (Timeout):",
        "de": "Netzwerk-Timeout:",
    },
    "Agent utilisateur (User-Agent HTTP) :": {
        "fr": "Agent utilisateur (User-Agent HTTP) :",
        "en": "User-Agent (HTTP User-Agent):",
        "es": "Agente de usuario (User-Agent HTTP):",
        "de": "Benutzer-Agent (HTTP User-Agent):",
    },
    "Guide TV & EPG": {
        "fr": "Guide TV & EPG",
        "en": "TV Guide & EPG",
        "es": "Guía TV y EPG",
        "de": "TV-Programm & EPG",
    },
    "Gérez la synchronisation, les sources XMLTV et la fréquence d'actualisation des programmes.": {
        "fr": "Gérez la synchronisation, les sources XMLTV et la fréquence d'actualisation des programmes.",
        "en": "Manage synchronization, XMLTV sources and program refresh interval.",
        "es": "Gestione la sincronización, fuentes XMLTV y la frecuencia de actualización.",
        "de": "Verwalten Sie Synchronisierung, XMLTV-Quellen und Aktualisierungshäufigkeit.",
    },
    "Fréquence de rafraîchissement de l'EPG :": {
        "fr": "Fréquence de rafraîchissement de l'EPG :",
        "en": "EPG Refresh Interval:",
        "es": "Frecuencia de actualización de EPG:",
        "de": "EPG-Aktualisierungshäufigkeit:",
    },
    "Au démarrage de l'application uniquement": {
        "fr": "Au démarrage de l'application uniquement",
        "en": "At application startup only",
        "es": "Solo al iniciar la aplicación",
        "de": "Nur beim Anwendungsstart",
    },
    "Activer le décalage horaire automatique de l'EPG": {
        "fr": "Activer le décalage horaire automatique de l'EPG",
        "en": "Enable automatic EPG timezone offset",
        "es": "Activar ajuste automático de zona horaria de EPG",
        "de": "Automatische EPG-Zeitzonenverschiebung aktivieren",
    },
    "Stockage & Cache": {
        "fr": "Stockage & Cache",
        "en": "Storage & Cache",
        "es": "Almacenamiento y caché",
        "de": "Speicher & Cache",
    },
    "Gérez l'espace disque, le cache des logos et les données hors-ligne.": {
        "fr": "Gérez l'espace disque, le cache des logos et les données hors-ligne.",
        "en": "Manage disk space, logo cache and offline data.",
        "es": "Gestione el espacio en disco, la caché de logotipos y datos sin conexión.",
        "de": "Verwalten Sie Speicherplatz, Logo-Cache und Offlinedaten.",
    },
    "Vider le cache d'images": {
        "fr": "Vider le cache d'images",
        "en": "Clear image cache",
        "es": "Vaciar caché de imágenes",
        "de": "Bild-Cache leeren",
    },
    "Répertoire des téléchargements :": {
        "fr": "Répertoire des téléchargements :",
        "en": "Download Directory:",
        "es": "Directorio de descargas:",
        "de": "Download-Verzeichnis:",
    },
    "Exportez et importez vos préférences, vos listes et votre historique de lecture.": {
        "fr": "Exportez et importez vos préférences, vos listes et votre historique de lecture.",
        "en": "Export and import your preferences, playlists and watch history.",
        "es": "Exporte e importe sus preferencias, listas e historial de visualización.",
        "de": "Exportieren und importieren Sie Einstellungen, Listen und Wiedergabeverlauf.",
    },
    "Exporter la base de données...": {
        "fr": "Exporter la base de données...",
        "en": "Export database...",
        "es": "Exportar base de datos...",
        "de": "Datenbank exportieren...",
    },
    "Restaurer une sauvegarde...": {
        "fr": "Restaurer une sauvegarde...",
        "en": "Restore backup...",
        "es": "Restaurar copia de seguridad...",
        "de": "Sicherung wiederherstellen...",
    },
    "Informations sur IPTV Hub et licence.": {
        "fr": "Informations sur IPTV Hub et licence.",
        "en": "Information about IPTV Hub and license.",
        "es": "Información sobre IPTV Hub y licencia.",
        "de": "Informationen über IPTV Hub und Lizenz.",
    },
    "Lecteur multimédia moderne, élégant et ultra-rapide pour flux IPTV Xtream Codes et M3U.": {
        "fr": "Lecteur multimédia moderne, élégant et ultra-rapide pour flux IPTV Xtream Codes et M3U.",
        "en": "Modern, elegant and ultra-fast multimedia player for IPTV Xtream Codes and M3U streams.",
        "es": "Reproductor multimedia moderno, elegante y ultrarrápido para transmisiones Xtream Codes y M3U.",
        "de": "Moderner, eleganter und ultraschneller Multimedia-Player für IPTV Xtream Codes und M3U Streams.",
    },
    "Version installée :": {
        "fr": "Version installée :",
        "en": "Installed Version:",
        "es": "Versión instalada:",
        "de": "Installierte Version:",
    },
    "Moteur vidéo :": {
        "fr": "Moteur vidéo :",
        "en": "Video Engine:",
        "es": "Motor de vídeo:",
        "de": "Video-Engine:",
    },
    " Enregistrer les paramètres": {
        "fr": " Enregistrer les paramètres",
        "en": " Save settings",
        "es": " Guardar ajustes",
        "de": " Einstellungen speichern",
    },
    "Paramètres enregistrés avec succès !": {
        "fr": "Paramètres enregistrés avec succès !",
        "en": "Settings saved successfully!",
        "es": "¡Ajustes guardados con éxito!",
        "de": "Einstellungen erfolgreich gespeichert!",
    },
    "Moteur de Lecture libmpv": {
        "fr": "Moteur de Lecture libmpv",
        "en": "libmpv Playback Engine",
        "es": "Motor de reproducción libmpv",
        "de": "libmpv-Wiedergabe-Engine",
    },
    "Options matérielles de décodage et de fluidité pour les flux HD/4K.": {
        "fr": "Options matérielles de décodage et de fluidité pour les flux HD/4K.",
        "en": "Hardware decoding and smoothness options for HD/4K streams.",
        "es": "Opciones de decodificación por hardware y fluidez para transmisiones HD/4K.",
        "de": "Hardware-Dekodierungs- und Wiedergabeoptionen für HD/4K-Streams.",
    },
    "Réseau & Streaming": {
        "fr": "Réseau & Streaming",
        "en": "Network & Streaming",
        "es": "Red y Streaming",
        "de": "Netzwerk & Streaming",
    },
    "Paramètres de connexion aux serveurs IPTV et entêtes HTTP.": {
        "fr": "Paramètres de connexion aux serveurs IPTV et entêtes HTTP.",
        "en": "IPTV server connection settings and HTTP headers.",
        "es": "Ajustes de conexión a servidores IPTV y cabeceras HTTP.",
        "de": "Verbindungseinstellungen zu IPTV-Servern und HTTP-Headern.",
    },
    "Guide Électronique des Programmes (EPG)": {
        "fr": "Guide Électronique des Programmes (EPG)",
        "en": "Electronic Program Guide (EPG)",
        "es": "Guía Electrónica de Programas (EPG)",
        "de": "Elektronischer Programmführer (EPG)",
    },
    "Fréquence de synchronisation et décalage horaire pour les programmes TV.": {
        "fr": "Fréquence de synchronisation et décalage horaire pour les programmes TV.",
        "en": "Sync frequency and timezone offset for TV programs.",
        "es": "Frecuencia de sincronización y desfase horario para los programas de TV.",
        "de": "Synchronisationsintervall und Zeitverschiebung für das TV-Programm.",
    },
    "Données, Téléchargements & Cache": {
        "fr": "Données, Téléchargements & Cache",
        "en": "Data, Downloads & Cache",
        "es": "Datos, Descargas y Caché",
        "de": "Daten, Downloads & Cache",
    },
    "Configuration du dossier de téléchargement des films VOD et gestion du cache local.": {
        "fr": "Configuration du dossier de téléchargement des films VOD et gestion du cache local.",
        "en": "Configuration of VOD download directory and local cache management.",
        "es": "Configuración de la carpeta de descargas de películas VOD y gestión de la caché local.",
        "de": "Konfiguration des VOD-Download-Ordners und lokale Cache-Verwaltung.",
    },
    "Sauvegarde & Configuration": {
        "fr": "Sauvegarde & Configuration",
        "en": "Backup & Configuration",
        "es": "Copia de seguridad y Configuración",
        "de": "Sicherung & Konfiguration",
    },
    "Enregistrez ou restaurez votre configuration complète sous forme de fichier. Vous pouvez facilement transférer ce fichier via une clé USB ou un dossier partagé vers un autre PC ou vers votre version Android TV.": {
        "fr": "Enregistrez ou restaurez votre configuration complète sous forme de fichier. Vous pouvez facilement transférer ce fichier via une clé USB ou un dossier partagé vers un autre PC ou vers votre version Android TV.",
        "en": "Save or restore your complete configuration as a file. Easily transfer this file via USB drive or shared folder to another PC or Android TV.",
        "es": "Guarde o restaure su configuración completa en un archivo. Puede transferir fácilmente este archivo a través de una memoria USB o carpeta compartida a otra PC o a su Android TV.",
        "de": "Speichern oder stellen Sie Ihre vollständige Konfiguration als Datei wieder her. Sie können diese Datei bequem per USB-Stick oder Freigabeordner auf einen anderen PC oder Ihr Android TV übertragen.",
    },
    "À propos d'IPTV Hub": {
        "fr": "À propos d'IPTV Hub",
        "en": "About IPTV Hub",
        "es": "Acerca de IPTV Hub",
        "de": "Über IPTV Hub",
    },
    "Lecteur multimédia moderne pour flux IPTV, Xtream Codes, VOD et Séries.": {
        "fr": "Lecteur multimédia moderne pour flux IPTV, Xtream Codes, VOD et Séries.",
        "en": "Modern multimedia player for IPTV, Xtream Codes, VOD and Series.",
        "es": "Reproductor multimedia moderno para transmisiones IPTV, Xtream Codes, VOD y Series.",
        "de": "Moderner Mediaplayer für IPTV-Streams, Xtream Codes, VOD und Serien.",
    },
    "Délai de masquage des contrôles vidéo :": {
        "fr": "Délai de masquage des contrôles vidéo :",
        "en": "Video controls auto-hide delay:",
        "es": "Tiempo de ocultación de controles de vídeo:",
        "de": "Ausblendverzögerung der Videosteuerung:",
    },
    "secondes": {
        "fr": "secondes",
        "en": "seconds",
        "es": "segundos",
        "de": "Sekunden",
    },
    " Reprendre automatiquement la dernière chaîne au lancement": {
        "fr": " Reprendre automatiquement la dernière chaîne au lancement",
        "en": " Automatically resume last channel on startup",
        "es": " Reanudar automáticamente el último canal al iniciar",
        "de": " Letzten Kanal beim Start automatisch fortsetzen",
    },
    " Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)": {
        "fr": " Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)",
        "en": " Automatically play next episode when current episode finishes (Series)",
        "es": " Reproducir automáticamente el siguiente episodio al terminar (Series)",
        "de": " Bei Episodenende automatisch die nächste Folge abspielen (Serien)",
    },
    "Décodage matériel (HW Accel) :": {
        "fr": "Décodage matériel (HW Accel) :",
        "en": "Hardware Decoding (HW Accel):",
        "es": "Decodificación por hardware (HW Accel):",
        "de": "Hardware-Dekodierung (HW-Beschl.):",
    },
    "Désentrelacement vidéo :": {
        "fr": "Désentrelacement vidéo :",
        "en": "Video Deinterlacing:",
        "es": "Desentrelazado de vídeo:",
        "de": "Video-Deinterlacing:",
    },
    "Taille du cache de préchargement :": {
        "fr": "Taille du cache de préchargement :",
        "en": "Preload Buffer Cache Size:",
        "es": "Tamaño de la caché de precarga:",
        "de": "Größe des Preload-Zwischenspeichers:",
    },
    "Mo": {
        "fr": "Mo",
        "en": "MB",
        "es": "MB",
        "de": "MB",
    },
    "User-Agent HTTP par défaut :": {
        "fr": "User-Agent HTTP par défaut :",
        "en": "Default HTTP User-Agent:",
        "es": "User-Agent HTTP predeterminado:",
        "de": "Standard-HTTP-User-Agent:",
    },
    "Ex: VLC/3.0.18 LibVLC/3.0.18 ou Mozilla/5.0...": {
        "fr": "Ex: VLC/3.0.18 LibVLC/3.0.18 ou Mozilla/5.0...",
        "en": "Ex: VLC/3.0.18 LibVLC/3.0.18 or Mozilla/5.0...",
        "es": "Ej: VLC/3.0.18 LibVLC/3.0.18 o Mozilla/5.0...",
        "de": "Z.B.: VLC/3.0.18 LibVLC/3.0.18 oder Mozilla/5.0...",
    },
    " Reconnexion automatique en cas de coupure de flux": {
        "fr": " Reconnexion automatique en cas de coupure de flux",
        "en": " Automatically reconnect on stream interruption",
        "es": " Reconexión automática en caso de corte del flujo",
        "de": " Automatische Wiederverbindung bei Stream-Unterbrechung",
    },
    "Intervalle d'actualisation automatique :": {
        "fr": "Intervalle d'actualisation automatique :",
        "en": "Automatic Refresh Interval:",
        "es": "Intervalo de actualización automática:",
        "de": "Intervall für automatische Aktualisierung:",
    },
    "heures": {
        "fr": "heures",
        "en": "hours",
        "es": "horas",
        "de": "Stunden",
    },
    "Décalage horaire EPG :": {
        "fr": "Décalage horaire EPG :",
        "en": "EPG Timezone Offset:",
        "es": "Desfase horario EPG:",
        "de": "EPG-Zeitverschiebung:",
    },
    "Dossier de téléchargement des vidéos & films VOD :": {
        "fr": "Dossier de téléchargement des vidéos & films VOD :",
        "en": "Download Directory for VOD Videos & Movies:",
        "es": "Carpeta de descarga de vídeos y películas VOD:",
        "de": "Download-Ordner für VOD-Filme & Videos:",
    },
    " Parcourir...": {
        "fr": " Parcourir...",
        "en": " Browse...",
        "es": " Examinar...",
        "de": " Durchsuchen...",
    },
    "  Vider le cache des logos de chaînes": {
        "fr": "  Vider le cache des logos de chaînes",
        "en": "  Clear channel logo cache",
        "es": "  Vaciar caché de logotipos de canales",
        "de": "  Kanal-Logo-Cache leeren",
    },
    "💾 Enregistrer la configuration (Sauvegarde)": {
        "fr": "💾 Enregistrer la configuration (Sauvegarde)",
        "en": "💾 Save Configuration (Backup)",
        "es": "💾 Guardar la configuración (Copia de seguridad)",
        "de": "💾 Konfiguration speichern (Sicherung)",
    },
    "Exporte vos listes de lecture, comptes/serveurs, favoris, historique de visionnage, chaînes masquées et reprises de lecture dans un fichier JSON compact (~150 Ko).<br><i>(Les chaînes brutes et affiches ne sont pas incluses pour garantir un fichier léger et rapide).</i>": {
        "fr": "Exporte vos listes de lecture, comptes/serveurs, favoris, historique de visionnage, chaînes masquées et reprises de lecture dans un fichier JSON compact (~150 Ko).<br><i>(Les chaînes brutes et affiches ne sont pas incluses pour garantir un fichier léger et rapide).</i>",
        "en": "Exports your playlists, accounts/servers, favorites, watch history, hidden channels and resume points in a compact JSON file (~150 KB).<br><i>(Raw streams and posters are excluded to ensure a lightweight file).</i>",
        "es": "Exporta sus listas de reproducción, cuentas/servidores, favoritos, historial de reproducción, canales ocultos y reanudaciones en un archivo JSON compacto (~150 KB).<br><i>(Los canales y portadas no están incluidos para garantizar un archivo ligero y rápido).</i>",
        "de": "Exportiert Ihre Wiedergabelisten, Konten/Server, Favoriten, Wiedergabeverlauf, ausgeblendete Kanäle und Fortsetzungsdaten in eine kompakte JSON-Datei (~150 KB).<br><i>(Rohe Kanaldaten und Cover sind nicht enthalten, um eine schlanke und schnelle Datei zu gewährleisten).</i>",
    },
    "  Enregistrer la configuration sous...": {
        "fr": "  Enregistrer la configuration sous...",
        "en": "  Save configuration as...",
        "es": "  Guardar configuración como...",
        "de": "  Konfiguration speichern unter...",
    },
    "📂 Charger une configuration (Restauration)": {
        "fr": "📂 Charger une configuration (Restauration)",
        "en": "📂 Load Configuration (Restore)",
        "es": "📂 Cargar una configuración (Restauración)",
        "de": "📂 Konfiguration laden (Wiederherstellung)",
    },
    "Charge un fichier de configuration précédemment sauvegardé. Le système fusionne intelligemment vos listes, cumule vos favoris et applique les reprises de lecture les plus récentes sans écraser vos données locales.": {
        "fr": "Charge un fichier de configuration précédemment sauvegardé. Le système fusionne intelligemment vos listes, cumule vos favoris et applique les reprises de lecture les plus récentes sans écraser vos données locales.",
        "en": "Loads a previously saved configuration file. The system intelligently merges playlists, accumulates favorites and applies the latest resume positions without overwriting local data.",
        "es": "Carga un archivo de configuración previamente guardado. El sistema fusiona inteligentemente sus listas, acumula sus favoritos y aplica las reanudaciones más recientes sin sobrescribir sus datos locales.",
        "de": "Lädt eine zuvor gespeicherte Konfigurationsdatei. Das System führt Ihre Listen intelligent zusammen, bündelt Favoriten und wendet die neuesten Wiedergabefortsetzungen an, ohne lokale Daten zu überschreiben.",
    },
    "  Charger un fichier de configuration...": {
        "fr": "  Charger un fichier de configuration...",
        "en": "  Load configuration file...",
        "es": "  Cargar archivo de configuración...",
        "de": "  Konfigurationsdatei laden...",
    },
    "Version :": {
        "fr": "Version :",
        "en": "Version:",
        "es": "Versión:",
        "de": "Version:",
    },
    "Édition Complète": {
        "fr": "Édition Complète",
        "en": "Full Edition",
        "es": "Edición Completa",
        "de": "Vollversion",
    },
    "Moteur de rendu :": {
        "fr": "Moteur de rendu :",
        "en": "Rendering Engine:",
        "es": "Motor de renderizado:",
        "de": "Rendering-Engine:",
    },
    "Framework UI :": {
        "fr": "Framework UI :",
        "en": "UI Framework:",
        "es": "Framework UI:",
        "de": "UI-Framework:",
    },
    "Raccourcis clés :": {
        "fr": "Raccourcis clés :",
        "en": "Key Shortcuts:",
        "es": "Atajos principales:",
        "de": "Wichtige Tastenkürzel:",
    },
    "Plein écran": {
        "fr": "Plein écran",
        "en": "Fullscreen",
        "es": "Pantalla completa",
        "de": "Vollbild",
    },
    "Pause": {
        "fr": "Pause",
        "en": "Pause",
        "es": "Pausa",
        "de": "Pause",
    },
    "Recul/Avance 10s": {
        "fr": "Recul/Avance 10s",
        "en": "Rewind/Forward 10s",
        "es": "Retroceso/Avance 10s",
        "de": "10s Vor/Zurück",
    },
    "Espace": {
        "fr": "Espace",
        "en": "Space",
        "es": "Espacio",
        "de": "Leertaste",
    },
    "Base SQLite :": {
        "fr": "Base SQLite :",
        "en": "SQLite Database:",
        "es": "Base de datos SQLite:",
        "de": "SQLite-Datenbank:",
    },
    "Filmographie — {name}": {
        "fr": "Filmographie — {name}",
        "en": "Filmography — {name}",
        "es": "Filmografía — {name}",
        "de": "Filmografie — {name}",
    },
    "Aucune information trouvée pour '{artist_name}' sur TMDB.": {
        "fr": "Aucune information trouvée pour '{artist_name}' sur TMDB.",
        "en": "No information found for '{artist_name}' on TMDB.",
        "es": "No se encontró información para '{artist_name}' en TMDB.",
        "de": "Keine Informationen für '{artist_name}' auf TMDB gefunden.",
    },
    "Information : {err_msg}": {
        "fr": "Information : {err_msg}",
        "en": "Information: {err_msg}",
        "es": "Información: {err_msg}",
        "de": "Information: {err_msg}",
    },
    "Acteur / Actrice": {
        "fr": "Acteur / Actrice",
        "en": "Actor / Actress",
        "es": "Actor / Actriz",
        "de": "Schauspieler / Schauspielerin",
    },
    "{age} ans ({b_date})": {
        "fr": "{age} ans ({b_date})",
        "en": "{age} years old ({b_date})",
        "es": "{age} años ({b_date})",
        "de": "{age} Jahre alt ({b_date})",
    },
    "Aucun film ni série avec {artist_name} n'a été trouvé dans votre abonnement.": {
        "fr": "Aucun film ni série avec {artist_name} n'a été trouvé dans votre abonnement.",
        "en": "No movie or series featuring {artist_name} was found in your library.",
        "es": "No se encontraron películas ni series con {artist_name} en su suscripción.",
        "de": "Keine Filme oder Serien mit {artist_name} in Ihrem Abonnement gefunden.",
    },
    "🎬 Films disponibles ({count})": {
        "fr": "🎬 Films disponibles ({count})",
        "en": "🎬 Available Movies ({count})",
        "es": "🎬 Películas disponibles ({count})",
        "de": "🎬 Verfügbare Filme ({count})",
    },
    "📺 Séries disponibles ({count})": {
        "fr": "📺 Séries disponibles ({count})",
        "en": "📺 Available Series ({count})",
        "es": "📺 Series disponibles ({count})",
        "de": "📺 Verfügbare Serien ({count})",
    },
    "🎥 En tant que Réalisateur ({count})": {
        "fr": "🎥 En tant que Réalisateur ({count})",
        "en": "🎥 As Director ({count})",
        "es": "🎥 Como director ({count})",
        "de": "🎥 Als Regisseur ({count})",
    },
    "Défiler vers la gauche": {
        "fr": "Défiler vers la gauche",
        "en": "Scroll left",
        "es": "Desplazar a la izquierda",
        "de": "Nach links scrollen",
    },
    "Défiler vers la droite": {
        "fr": "Défiler vers la droite",
        "en": "Scroll right",
        "es": "Desplazar a la derecha",
        "de": "Nach rechts scrollen",
    },
    "Rôle : {role}": {
        "fr": "Rôle : {role}",
        "en": "Role: {role}",
        "es": "Rol: {role}",
        "de": "Rolle: {role}",
    },
    "Année : {year}": {
        "fr": "Année : {year}",
        "en": "Year: {year}",
        "es": "Año: {year}",
        "de": "Jahr: {year}",
    },
    "Rechercher un acteur ou réalisateur": {
        "fr": "Rechercher un acteur ou réalisateur",
        "en": "Search an actor or director",
        "es": "Buscar un actor o director",
        "de": "Schauspieler oder Regisseur suchen",
    },
    "Rechercher un Acteur ou Réalisateur": {
        "fr": "Rechercher un Acteur ou Réalisateur",
        "en": "Search an Actor or Director",
        "es": "Buscar un Actor o Director",
        "de": "Schauspieler oder Regisseur suchen",
    },
    "Tapez le prénom ou le nom : les suggestions s'affinent en temps réel. Cliquez sur un artiste pour voir sa filmographie.": {
        "fr": "Tapez le prénom ou le nom : les suggestions s'affinent en temps réel. Cliquez sur un artiste pour voir sa filmographie.",
        "en": "Type first or last name: suggestions refine in real time. Click an artist to view their filmography.",
        "es": "Escriba el nombre o apellido: las sugerencias se actualizan en tiempo real. Haga clic en un artista para ver su filmografía.",
        "de": "Geben Sie Vor- oder Nachnamen ein: Vorschläge werden in Echtzeit verfeinert. Klicken Sie auf einen Künstler für seine Filmografie.",
    },
    "Ex : Charlie, Tom, Christopher, Drew...": {
        "fr": "Ex : Charlie, Tom, Christopher, Drew...",
        "en": "e.g. Charlie, Tom, Christopher, Drew...",
        "es": "Ej.: Charlie, Tom, Christopher, Drew...",
        "de": "Z.B.: Charlie, Tom, Christopher, Drew...",
    },
    "Coller": {
        "fr": "Coller",
        "en": "Paste",
        "es": "Pegar",
        "de": "Einfügen",
    },
    "Coller depuis le presse-papier (clic souris)": {
        "fr": "Coller depuis le presse-papier (clic souris)",
        "en": "Paste from clipboard (mouse click)",
        "es": "Pegar desde el portapapeles (clic del ratón)",
        "de": "Aus der Zwischenablage einfügen (Mausklick)",
    },
    "Tapez au moins 2 lettres pour afficher les suggestions...": {
        "fr": "Tapez au moins 2 lettres pour afficher les suggestions...",
        "en": "Type at least 2 letters to view suggestions...",
        "es": "Escriba al menos 2 letras para mostrar sugerencias...",
        "de": "Geben Sie mindestens 2 Buchstaben ein, um Vorschläge anzuzeigen...",
    },
    "Recherche des artistes correspondants...": {
        "fr": "Recherche des artistes correspondants...",
        "en": "Searching matching artists...",
        "es": "Buscando artistas coincidentes...",
        "de": "Passende Künstler werden gesucht...",
    },
    "Aucun artiste trouvé pour \"{query}\".": {
        "fr": "Aucun artiste trouvé pour \"{query}\".",
        "en": "No artist found for \"{query}\".",
        "es": "No se encontraron artistas para \"{query}\".",
        "de": "Keine Künstler für \"{query}\" gefunden.",
    },
    "Afficher la filmographie": {
        "fr": "Afficher la filmographie",
        "en": "Show filmography",
        "es": "Mostrar filmografía",
        "de": "Filmografie anzeigen",
    },
    "Afficher la filmographie de {name}": {
        "fr": "Afficher la filmographie de {name}",
        "en": "Show filmography of {name}",
        "es": "Mostrar filmografía de {name}",
        "de": "Filmografie von {name} anzeigen",
    },
    "Reprendre à {time}": {
        "fr": "Reprendre à {time}",
        "en": "Resume at {time}",
        "es": "Reanudar a las {time}",
        "de": "Fortsetzen bei {time}",
    },
    "Lire la bande-annonce": {
        "fr": "Lire la bande-annonce",
        "en": "Play trailer",
        "es": "Reproducir tráiler",
        "de": "Trailer abspielen",
    },
    "Ouvrir sur YouTube": {
        "fr": "Ouvrir sur YouTube",
        "en": "Open on YouTube",
        "es": "Abrir en YouTube",
        "de": "Auf YouTube öffnen",
    },
    "Avis des spectateurs": {
        "fr": "Avis des spectateurs",
        "en": "User Reviews",
        "es": "Opiniones de espectadores",
        "de": "Zuschauerbewertungen",
    },
    "Lecture en cours...": {
        "fr": "Lecture en cours...",
        "en": "Playing now...",
        "es": "Reproduciendo...",
        "de": "Wiedergabe läuft...",
    },
    "Recommencer la série": {
        "fr": "Recommencer la série",
        "en": "Restart series",
        "es": "Reiniciar la serie",
        "de": "Serie neu starten",
    },
    "Reprendre : S{s:02d}E{e:02d} ({title})": {
        "fr": "Reprendre : S{s:02d}E{e:02d} ({title})",
        "en": "Resume: S{s:02d}E{e:02d} ({title})",
        "es": "Reanudar: T{s:02d}E{e:02d} ({title})",
        "de": "Fortsetzen: S{s:02d}E{e:02d} ({title})",
    },
    "Aucun épisode disponible dans cette saison.": {
        "fr": "Aucun épisode disponible dans cette saison.",
        "en": "No episodes available in this season.",
        "es": "No hay episodios disponibles en esta temporada.",
        "de": "Keine Folgen in dieser Staffel verfügbar.",
    },
    "Chargement des saisons et épisodes...": {
        "fr": "Chargement des saisons et épisodes...",
        "en": "Loading seasons and episodes...",
        "es": "Cargando temporadas y episodios...",
        "de": "Staffeln und Folgen werden geladen...",
    },
    "Favoris": {
        "fr": "Favoris",
        "en": "Favorites",
        "es": "Favoritos",
        "de": "Favoriten",
    },
    "Tous": {
        "fr": "Tous",
        "en": "All",
        "es": "Todos",
        "de": "Alle",
    },
    "la liste": {
        "fr": "la liste",
        "en": "the playlist",
        "es": "la lista",
        "de": "die Liste",
    },
    "Ma liste de lecture": {
        "fr": "Ma liste de lecture",
        "en": "My playlist",
        "es": "Mi lista de reproducción",
        "de": "Meine Wiedergabeliste",
    },
    "ma liste de lecture": {
        "fr": "ma liste de lecture",
        "en": "my playlist",
        "es": "mi lista de reproducción",
        "de": "meine Wiedergabeliste",
    },
    "Film": {
        "fr": "Film",
        "en": "Movie",
        "es": "Película",
        "de": "Film",
    },
    "Série": {
        "fr": "Série",
        "en": "Series",
        "es": "Serie",
        "de": "Serie",
    },
    "Replay": {
        "fr": "Replay",
        "en": "Replay",
        "es": "Replay",
        "de": "Replay",
    },
    "Il reste {hours} h {mins:02d} min": {
        "fr": "Il reste {hours} h {mins:02d} min",
        "en": "{hours}h {mins:02d}m left",
        "es": "Quedan {hours} h {mins:02d} min",
        "de": "Noch {hours} Std. {mins:02d} Min.",
    },
    "Il reste {hours} h {mins} min": {
        "fr": "Il reste {hours} h {mins} min",
        "en": "{hours}h {mins}m left",
        "es": "Quedan {hours} h {mins} min",
        "de": "Noch {hours} Std. {mins} Min.",
    },
    "Il reste {mins} min": {
        "fr": "Il reste {mins} min",
        "en": "{mins} min left",
        "es": "Quedan {mins} min",
        "de": "Noch {mins} Min.",
    },
    "Il reste {time}": {
        "fr": "Il reste {time}",
        "en": "{time} left",
        "es": "Queda {time}",
        "de": "Noch {time}",
    },
    "{pct}% regardé": {
        "fr": "{pct} % regardé",
        "en": "{pct}% watched",
        "es": "{pct}% visto",
        "de": "{pct}% gesehen",
    },
    "{pct} % regardé": {
        "fr": "{pct} % regardé",
        "en": "{pct}% watched",
        "es": "{pct} % visto",
        "de": "{pct} % gesehen",
    },
    "Reprendre le Replay": {
        "fr": "Reprendre le Replay",
        "en": "Resume Replay",
        "es": "Reanudar Replay",
        "de": "Replay fortsetzen",
    },
    "  Reprendre le Replay": {
        "fr": "  Reprendre le Replay",
        "en": "  Resume Replay",
        "es": "  Reanudar Replay",
        "de": "  Replay fortsetzen",
    },
    "Lancer l'épisode suivant": {
        "fr": "Lancer l'épisode suivant",
        "en": "Play next episode",
        "es": "Reproducir siguiente episodio",
        "de": "Nächste Folge abspielen",
    },
    "  Lancer l'épisode suivant": {
        "fr": "  Lancer l'épisode suivant",
        "en": "  Play next episode",
        "es": "  Reproducir siguiente episodio",
        "de": "  Nächste Folge abspielen",
    },
    "Voir la série": {
        "fr": "Voir la série",
        "en": "View series",
        "es": "Ver serie",
        "de": "Serie ansehen",
    },
    "  Voir la série": {
        "fr": "  Voir la série",
        "en": "  View series",
        "es": "  Ver serie",
        "de": "  Serie ansehen",
    },
    "Épisode suivant disponible": {
        "fr": "Épisode suivant disponible",
        "en": "Next episode available",
        "es": "Siguiente episodio disponible",
        "de": "Nächste Folge verfügbar",
    },
    "Série à reprendre": {
        "fr": "Série à reprendre",
        "en": "Series in progress",
        "es": "Serie en curso",
        "de": "Serie fortsetzen",
    },
    "Recently watched live TV": {
        "fr": "TV en direct récemment regardée",
        "en": "Recently watched live TV",
        "es": "TV en vivo vista recientemente",
        "de": "Kürzlich angesehenes Live-TV",
    },
    "TV en direct récemment regardée": {
        "fr": "TV en direct récemment regardée",
        "en": "Recently watched live TV",
        "es": "TV en vivo vista recientemente",
        "de": "Kürzlich gesehene Live-Sender",
    },
    "Favorite movies & series": {
        "fr": "Films & Séries favoris",
        "en": "Favorite movies & series",
        "es": "Películas y series favoritas",
        "de": "Lieblingsfilme & -serien",
    },
    "Films & Séries favoris": {
        "fr": "Films & Séries favoris",
        "en": "Favorite movies & series",
        "es": "Películas y series favoritas",
        "de": "Lieblingsfilme & -serien",
    },
    "Voir tout >": {
        "fr": "Voir tout >",
        "en": "See all >",
        "es": "Ver todo >",
        "de": "Alle ansehen >",
    },
    "Voir les {count} >": {
        "fr": "Voir les {count} >",
        "en": "See all {count} >",
        "es": "Ver los {count} >",
        "de": "Alle {count} ansehen >",
    },
    "Affiche": {
        "fr": "Affiche",
        "en": "Poster",
        "es": "Póster",
        "de": "Poster",
    },
    "Direct": {
        "fr": "Direct",
        "en": "Live",
        "es": "En vivo",
        "de": "Live",
    },
    "Aucune liste de lecture": {
        "fr": "Aucune liste de lecture",
        "en": "No playlist",
        "es": "Ninguna lista de reproducción",
        "de": "Keine Wiedergabeliste",
    },
    "Guide des programmes EPG": {
        "fr": "Guide des programmes EPG",
        "en": "TV Guide EPG",
        "es": "Guía de programas EPG",
        "de": "EPG-Programmführer",
    },
    "Épisode précédent": {
        "fr": "Épisode précédent",
        "en": "Previous episode",
        "es": "Episodio anterior",
        "de": "Vorherige Folge",
    },
    "Épisode suivant": {
        "fr": "Épisode suivant",
        "en": "Next episode",
        "es": "Episodio siguiente",
        "de": "Nächste Folge",
    },
    "Trier : Ordre du serveur (Original)": {
        "fr": "Trier : Ordre du serveur (Original)",
        "en": "Sort: Server order (Original)",
        "es": "Ordenar: Orden del servidor (Original)",
        "de": "Sortieren: Serverreihenfolge (Original)",
    },
    "Trier : Date d'ajout (plus récents...)": {
        "fr": "Trier : Date d'ajout (plus récents...)",
        "en": "Sort: Date added (Newest first)",
        "es": "Ordenar: Fecha de adición (más recientes...)",
        "de": "Sortieren: Hinzugefügt am (Neueste zuerst)",
    },
    "Trier : Titre (A à Z)": {
        "fr": "Trier : Titre (A à Z)",
        "en": "Sort: Title (A to Z)",
        "es": "Ordenar: Título (A a Z)",
        "de": "Sortieren: Titel (A bis Z)",
    },
    "Trier : Titre (Z à A)": {
        "fr": "Trier : Titre (Z à A)",
        "en": "Sort: Title (Z to A)",
        "es": "Ordenar: Título (Z a A)",
        "de": "Sortieren: Titel (Z bis A)",
    },
    "Trier : Note (plus haute)": {
        "fr": "Trier : Note (plus haute)",
        "en": "Sort: Rating (Highest)",
        "es": "Ordenar: Calificación (más alta)",
        "de": "Sortieren: Bewertung (Höchste)",
    },
    "Trier : Année (plus récente)": {
        "fr": "Trier : Année (plus récente)",
        "en": "Sort: Year (Newest)",
        "es": "Ordenar: Año (más reciente)",
        "de": "Sortieren: Jahr (Neueste)",
    },
    "0 films": {
        "fr": "0 films",
        "en": "0 movies",
        "es": "0 películas",
        "de": "0 Filme",
    },
    "0 séries": {
        "fr": "0 séries",
        "en": "0 series",
        "es": "0 series",
        "de": "0 Serien",
    },
    "40 premiers résultats sur {total}": {
        "fr": "40 premiers résultats sur {total}",
        "en": "First 40 results out of {total}",
        "es": "Primeros 40 resultados de {total}",
        "de": "Erste 40 Ergebnisse von {total}",
    },
    "auto (Recommandé)": {
        "fr": "auto (Recommandé)",
        "en": "auto (Recommended)",
        "es": "auto (Recomendado)",
        "de": "auto (Empfohlen)",
    },
    "yes (Toujours activé)": {
        "fr": "yes (Toujours activé)",
        "en": "yes (Always enabled)",
        "es": "yes (Siempre activado)",
        "de": "yes (Immer aktiviert)",
    },
    "no (Désactivé)": {
        "fr": "no (Désactivé)",
        "en": "no (Disabled)",
        "es": "no (Desactivado)",
        "de": "no (Deaktiviert)",
    },
    "Recommandé": {
        "fr": "Recommandé",
        "en": "Recommended",
        "es": "Recomendado",
        "de": "Empfohlen",
    },
    "Toujours activé": {
        "fr": "Toujours activé",
        "en": "Always enabled",
        "es": "Siempre activado",
        "de": "Immer aktiviert",
    },
    "Désactivé": {
        "fr": "Désactivé",
        "en": "Disabled",
        "es": "Desactivado",
        "de": "Deaktiviert",
    },
    "Reprendre automatiquement la dernière chaîne au lancement": {
        "fr": "Reprendre automatiquement la dernière chaîne au lancement",
        "en": "Automatically resume last channel on startup",
        "es": "Reanudar automáticamente el último canal al iniciar",
        "de": "Beim Starten automatisch den letzten Kanal fortsetzen",
    },
    "Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)": {
        "fr": "Enchaîner automatiquement sur l'épisode suivant à la fin d'un épisode (Séries)",
        "en": "Automatically play next episode when current episode finishes (Series)",
        "es": "Reproducir automáticamente el siguiente episodio al finalizar uno (Series)",
        "de": "Am Ende einer Folge automatisch die nächste Folge abspielen (Serien)",
    },
    "Reconnexion automatique en cas de coupure de flux": {
        "fr": "Reconnexion automatique en cas de coupure de flux",
        "en": "Automatic reconnection if stream drops",
        "es": "Reconexión automática en caso de corte del flujo",
        "de": "Automatische Wiederverbindung bei Stream-Unterbrechung",
    },
    "Vider le cache des logos de chaînes": {
        "fr": "Vider le cache des logos de chaînes",
        "en": "Clear channel logo cache",
        "es": "Vaciar la caché de logotipos de canales",
        "de": "Logo-Cache der Kanäle leeren",
    },
    "Enregistrer la configuration sous...": {
        "fr": "Enregistrer la configuration sous...",
        "en": "Save configuration as...",
        "es": "Guardar configuración como...",
        "de": "Konfiguration speichern unter...",
    },
    "Charger un fichier de configuration...": {
        "fr": "Charger un fichier de configuration...",
        "en": "Load configuration file...",
        "es": "Cargar un archivo de configuración...",
        "de": "Konfigurationsdatei laden...",
    },
    "Enregistrer la configuration (Sauvegarde)": {
        "fr": "Enregistrer la configuration (Sauvegarde)",
        "en": "Save Configuration (Backup)",
        "es": "Guardar configuración (Copia de seguridad)",
        "de": "Konfiguration speichern (Sicherung)",
    },
    "Charger une configuration (Restauration)": {
        "fr": "Charger une configuration (Restauration)",
        "en": "Load Configuration (Restore)",
        "es": "Cargar configuración (Restauración)",
        "de": "Konfiguration laden (Wiederherstellung)",
    },
}

# Clés sans espaces au début/fin pour correspondances tolérantes
STRIPPED_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    key.strip(): trans for key, trans in TRANSLATIONS.items()
}


class I18nManager(QObject):
    """Gestionnaire central de la langue et des traductions de l'application."""

    language_changed = pyqtSignal(str)

    SUPPORTED_LANGUAGES = {
        "fr": "Français",
        "en": "English",
        "es": "Español",
        "de": "Deutsch",
    }

    _instance: Optional["I18nManager"] = None

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
        Gère de manière tolérante les éventuels espaces préfixes ou suffixes.
        """
        if not text:
            return ""

        # 1. Recherche directe exacte
        translations = TRANSLATIONS.get(text)
        if translations:
            translated = translations.get(self._current_language) or translations.get("fr", text)
        else:
            # 2. Recherche avec tolérance sur les espaces
            stripped = text.strip()
            translations = STRIPPED_TRANSLATIONS.get(stripped)
            if translations:
                raw_trans = translations.get(self._current_language) or translations.get("fr", stripped)
                leading = len(text) - len(text.lstrip(" "))
                trailing = len(text) - len(text.rstrip(" "))
                translated = f"{' ' * leading}{raw_trans.strip()}{' ' * trailing}"
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
# Utilitaires de dates localisées (FR / EN / ES / DE)
# -----------------------------------------------------------------------------

WEEKDAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

WEEKDAYS_SHORT_FR = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]
WEEKDAYS_SHORT_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAYS_SHORT_ES = ["Lun.", "Mar.", "Mié.", "Jue.", "Vie.", "Sáb.", "Dom."]
WEEKDAYS_SHORT_DE = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]

MONTHS_SHORT_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MONTHS_SHORT_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_SHORT_ES = ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sept.", "oct.", "nov.", "dic."]
MONTHS_SHORT_DE = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."]


def get_locale_weekday(weekday_idx: int, short: bool = False) -> str:
    """Retourne le nom du jour de la semaine (0 = Lundi/Monday) dans la langue active."""
    lang = I18nManager.instance().current_language
    idx = max(0, min(6, weekday_idx))
    if lang == "en":
        return WEEKDAYS_SHORT_EN[idx] if short else WEEKDAYS_EN[idx]
    elif lang == "es":
        return WEEKDAYS_SHORT_ES[idx] if short else WEEKDAYS_ES[idx]
    elif lang == "de":
        return WEEKDAYS_SHORT_DE[idx] if short else WEEKDAYS_DE[idx]
    return WEEKDAYS_SHORT_FR[idx] if short else WEEKDAYS_FR[idx]


def get_locale_month(month_1_based: int, short: bool = True) -> str:
    """Retourne le nom du mois (1 = Janvier/January) dans la langue active."""
    lang = I18nManager.instance().current_language
    idx = max(0, min(11, month_1_based - 1))
    if lang == "en":
        return MONTHS_SHORT_EN[idx] if short else MONTHS_EN[idx]
    elif lang == "es":
        return MONTHS_SHORT_ES[idx] if short else MONTHS_ES[idx]
    elif lang == "de":
        return MONTHS_SHORT_DE[idx] if short else MONTHS_DE[idx]
    return MONTHS_SHORT_FR[idx] if short else MONTHS_FR[idx]


def format_locale_date(dt, date_format: str = "short") -> str:
    """
    Formate une date datetime selon la langue active :
    - 'short' : '15/09/2026' (FR/ES), '09/15/2026' (EN), '15.09.2026' (DE)
    - 'friendly' : '15 sept., 22:30' (FR/ES), 'Sep 15, 22:30' (EN), '15. Sept., 22:30' (DE)
    """
    if not dt:
        return ""
    lang = I18nManager.instance().current_language
    if date_format == "short":
        if lang == "en":
            return dt.strftime("%m/%d/%Y")
        elif lang == "de":
            return dt.strftime("%d.%m.%Y")
        return dt.strftime("%d/%m/%Y")
    elif date_format == "friendly":
        m_str = get_locale_month(dt.month, short=True)
        if lang == "en":
            return f"{m_str} {dt.day}, {dt.hour:02d}:{dt.minute:02d}"
        elif lang == "de":
            return f"{dt.day}. {m_str}, {dt.hour:02d}:{dt.minute:02d}"
        return f"{dt.day} {m_str}, {dt.hour:02d}:{dt.minute:02d}"
    return dt.strftime("%d/%m/%Y")
