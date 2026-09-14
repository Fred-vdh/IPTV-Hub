"""
Dialogue moderne de Filmographie d'un Artiste (Acteur / Réalisateur).
Affiche les informations biographiques de l'artiste depuis TMDB et répertorie séparément
les Films et les Séries disponibles dans la bibliothèque IPTV de l'utilisateur.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QProgressBar, QLineEdit, QApplication,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPixmap

from core.models import Channel
from core.database import Database
from core.image_loader import ImageLoader
from core.tmdb_client import (
    search_person,
    search_persons_list,
    get_person_details_and_credits,
    match_artist_credits_with_library
)
from ui.icons import get_icon
from ui.widgets.rounded_poster import RoundedPosterLabel
from core.i18n import tr


class ArtistSuggestionsWorker(QThread):
    """Worker d'arrière-plan pour récupérer les suggestions d'artistes en temps réel."""
    suggestions_ready = pyqtSignal(list, str)  # (results, query)

    def __init__(self, query: str, language: str = "fr-FR", parent=None):
        super().__init__(parent)
        self.query = query
        self.language = language

    def run(self):
        try:
            results = search_persons_list(self.query, language=self.language, limit=8)
            self.suggestions_ready.emit(results, self.query)
        except Exception:
            self.suggestions_ready.emit([], self.query)


class ArtistSearchWorker(QThread):
    """Thread d'arrière-plan pour rechercher l'artiste sur TMDB et croiser sa filmographie avec la base locale."""
    data_ready = pyqtSignal(dict, dict)  # (person_details, matched_results)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        artist_name: str,
        db: Database,
        playlist_id: Optional[int] = None,
        language: str = "fr-FR",
        person_id: Optional[int] = None,
        parent=None
    ):
        super().__init__(parent)
        self.artist_name = artist_name
        self.db = db
        self.playlist_id = playlist_id
        self.language = language
        self.person_id = person_id

    def run(self):
        try:
            if self.person_id:
                p_id = self.person_id
                details = get_person_details_and_credits(p_id, language=self.language)
            else:
                # 1. Recherche de la personne sur TMDB dans la langue préférée
                person = search_person(self.artist_name, language=self.language)
                if not person or not person.get("id"):
                    # Fallback : recherche dans la liste des correspondances
                    candidates = search_persons_list(self.artist_name, language=self.language, limit=3)
                    if candidates and candidates[0].get("id"):
                        person = candidates[0]
                    else:
                        self.error_occurred.emit(tr("Aucune information trouvée pour '{artist_name}' sur TMDB.", artist_name=self.artist_name))
                        return

                p_id = person["id"]
                details = get_person_details_and_credits(p_id, language=self.language)

            # 2. Récupérer les films et séries de la bibliothèque locale depuis SQLite
            movies = self.db.get_channels(
                playlist_id=self.playlist_id,
                stream_type="movie",
                only_enabled=True,
                limit=100000,
            )
            series = self.db.get_channels(
                playlist_id=self.playlist_id,
                stream_type="series",
                only_enabled=True,
                limit=100000,
            )
            vod_series = movies + series

            # 3. Croisement de la filmographie
            matched = match_artist_credits_with_library(details, vod_series)

            self.data_ready.emit(details, matched)
        except Exception as e:
            self.error_occurred.emit(str(e))


# ==============================================================================
# CONFIGURATION DES DIMENSIONS DE LA FICHE ARTISTE & AFFICHES (FACILE À AJUSTER)
# Pour revenir aux dimensions initiales :
#   DIALOG_DEFAULT_WIDTH = 920, DIALOG_DEFAULT_HEIGHT = 680
#   DIALOG_MIN_WIDTH = 780, DIALOG_MIN_HEIGHT = 520
#   CARD_WIDTH = 140, CARD_HEIGHT = 265, POSTER_WIDTH = 128, POSTER_HEIGHT = 205
# ==============================================================================
DIALOG_DEFAULT_WIDTH = 1080
DIALOG_DEFAULT_HEIGHT = 800
DIALOG_MIN_WIDTH = 880
DIALOG_MIN_HEIGHT = 620

CARD_WIDTH = 172
CARD_HEIGHT = 320
POSTER_WIDTH = 160
POSTER_HEIGHT = 240
# ==============================================================================


class ArtistMediaCard(QFrame):
    """Carte d'affiche élégante pour un film ou une série de l'artiste."""
    clicked = pyqtSignal(Channel)

    CARD_WIDTH = CARD_WIDTH
    CARD_HEIGHT = CARD_HEIGHT
    POSTER_WIDTH = POSTER_WIDTH
    POSTER_HEIGHT = POSTER_HEIGHT

    def __init__(self, item: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self.channel: Channel = item["channel"]
        self.role: str = item.get("role", "")
        self.year: str = item.get("year", "")
        self.rating: str = item.get("rating", "")

        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("artistMediaCard")
        self.setStyleSheet("""
            QFrame#artistMediaCard {
                background-color: #161f30;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QFrame#artistMediaCard:hover {
                background-color: #1e293b;
                border-color: #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 8)
        layout.setSpacing(4)

        # 1. Affiche (même dimension 160 x 240 que le reste de l'application)
        self.poster = RoundedPosterLabel(
            radius=6,
            border_color="#334155",
            bg_color="#0f172a",
            fallback_icon="movie" if self.channel.stream_type in ("movie", "vod") else "live_tv",
            parent=self
        )
        self.poster.setFixedSize(self.POSTER_WIDTH, self.POSTER_HEIGHT)
        layout.addWidget(self.poster, alignment=Qt.AlignmentFlag.AlignCenter)

        # 2. Titre du film ou de la série (plus de place pour le texte)
        self.title_label = QLabel(self.channel.name)
        self.title_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 600; line-height: 1.2;")
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(36)
        self.title_label.setToolTip(self.channel.name)
        layout.addWidget(self.title_label)

        # 3. Rôle / Personnage
        role_txt = tr("Rôle : {role}", role=self.role) if self.role and self.role != "Rôle non spécifié" else ""
        if not role_txt and self.year:
            role_txt = tr("Année : {year}", year=self.year)
        self.role_label = QLabel(role_txt)
        self.role_label.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500;")
        self.role_label.setWordWrap(True)
        self.role_label.setMaximumHeight(28)
        self.role_label.setToolTip(role_txt)
        layout.addWidget(self.role_label)

        layout.addStretch(1)

        self._load_poster()

    def _load_poster(self):
        url = self.channel.logo_url
        if not url and self.item.get("poster_path"):
            p_path = self.item["poster_path"]
            url = f"https://image.tmdb.org/t/p/w300{p_path}"

        if url:
            cached = ImageLoader.instance().get_cached_image(url)
            if cached:
                self.poster.setPixmap(cached)
            else:
                ImageLoader.instance().image_loaded.connect(self._on_image_loaded)
                ImageLoader.instance().request_image(url)

    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        target_url = self.channel.logo_url
        if not target_url and self.item.get("poster_path"):
            target_url = f"https://image.tmdb.org/t/p/w300{self.item['poster_path']}"
        if url == target_url:
            self.poster.setPixmap(pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.channel)
        super().mousePressEvent(event)


class ArtistFilmographyDialog(QDialog):
    """
    Dialogue complet présentant la filmographie d'un acteur ou réalisateur,
    avec répartition nette entre Films et Séries.
    """
    movie_selected = pyqtSignal(Channel)
    series_selected = pyqtSignal(Channel)

    def __init__(
        self,
        artist_name: str,
        db: Database,
        playlist_id: Optional[int] = None,
        language: str = "fr-FR",
        person_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.artist_name = artist_name.strip()
        self.person_id = person_id
        self.db = db
        self.playlist_id = playlist_id
        self.language = language
        self._worker: Optional[ArtistSearchWorker] = None
        self._profile_img_url: Optional[str] = None

        self.setWindowTitle(tr("Filmographie — {name}", name=self.artist_name))
        self.resize(DIALOG_DEFAULT_WIDTH, DIALOG_DEFAULT_HEIGHT)
        self.setMinimumSize(DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d121d;
                border: 1px solid #334155;
                border-radius: 12px;
                color: #f8fafc;
            }
        """)

        self._init_ui()
        self._start_search()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(16)

        # 1. En-tête avec profil de l'artiste
        self.header_card = QFrame()
        self.header_card.setStyleSheet("""
            QFrame {
                background-color: #161f30;
                border: 1px solid #1e293b;
                border-radius: 12px;
            }
        """)
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(18)

        # Photo de profil de l'artiste (Rounded)
        self.profile_photo = RoundedPosterLabel(
            radius=10,
            border_color="#3b82f6",
            bg_color="#0f172a",
            fallback_icon="person",
            parent=self.header_card
        )
        self.profile_photo.setFixedSize(130, 185)
        header_layout.addWidget(self.profile_photo)

        # Textes de l'en-tête
        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(6)

        self.name_label = QLabel(self.artist_name)
        self.name_label.setStyleSheet("color: #ffffff; font-size: 24px; font-weight: 700; background: transparent;")
        info_vbox.addWidget(self.name_label)

        self.dept_label = QLabel(tr("Recherche des informations sur TMDB..."))
        self.dept_label.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: 600; background: transparent;")
        info_vbox.addWidget(self.dept_label)

        # Zone fluide pour la biographie (plus d'espace et défilement si texte long)
        bio_scroll = QScrollArea()
        bio_scroll.setWidgetResizable(True)
        bio_scroll.setFrameShape(QFrame.Shape.NoFrame)
        bio_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(15, 23, 42, 0.4);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
        """)
        bio_scroll.setFixedHeight(115)

        self.bio_label = QLabel("")
        self.bio_label.setStyleSheet("color: #94a3b8; font-size: 12.5px; line-height: 1.45; background: transparent;")
        self.bio_label.setWordWrap(True)
        self.bio_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        bio_scroll.setWidget(self.bio_label)
        info_vbox.addWidget(bio_scroll)

        header_layout.addLayout(info_vbox, stretch=1)

        # Bouton fermer
        btn_close = QPushButton()
        btn_close.setIcon(get_icon("close", color="#94a3b8"))
        btn_close.setIconSize(QSize(18, 18))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedSize(32, 32)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                border-color: #dc2626;
            }
        """)
        btn_close.clicked.connect(self.accept)
        header_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignTop)

        root_layout.addWidget(self.header_card)

        # 2. Barre de chargement / statut
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 2px;
            }
        """)
        root_layout.addWidget(self.progress_bar)

        self.status_label = QLabel(tr("Recherche des titres disponibles dans votre abonnement IPTV..."))
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-style: italic;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(self.status_label)

        # 3. Zone principale défilante pour les sections
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #0d121d;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #1e293b;
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #334155;
            }
            QScrollBar:horizontal {
                background: #0d121d;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #1e293b;
                border-radius: 4px;
                min-width: 24px;
            }
        """)

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 16)
        self.content_layout.setSpacing(24)

        self.scroll_area.setWidget(self.content_widget)
        root_layout.addWidget(self.scroll_area, stretch=1)

    def _start_search(self):
        self._worker = ArtistSearchWorker(
            self.artist_name,
            self.db,
            self.playlist_id,
            language=self.language,
            person_id=self.person_id,
            parent=self,
        )
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_error(self, err_msg: str):
        self.progress_bar.hide()
        self.status_label.setText(tr("Information : {err_msg}", err_msg=err_msg))
        self.status_label.setStyleSheet("color: #f87171; font-size: 13px;")

    def _on_data_ready(self, details: Dict[str, Any], matched: Dict[str, List[Dict[str, Any]]]):
        self.progress_bar.hide()
        self.status_label.hide()

        # 1. Mettre à jour l'en-tête de l'artiste avec son nom complet officiel TMDB
        full_name = details.get("name")
        if full_name:
            self.artist_name = full_name
            self.name_label.setText(full_name)
            self.setWindowTitle(tr("Filmographie — {name}", name=full_name))

        p_path = details.get("profile_path")
        if p_path:
            self._profile_img_url = f"https://image.tmdb.org/t/p/w300{p_path}"
            cached = ImageLoader.instance().get_cached_image(self._profile_img_url)
            if cached:
                self.profile_photo.setPixmap(cached)
            else:
                self._disconnect_profile_loader()
                ImageLoader.instance().image_loaded.connect(self._on_profile_loaded)
                ImageLoader.instance().request_image_priority(self._profile_img_url)

        dept = details.get("known_for_department", "")
        dept_fr = tr("Acteur / Actrice") if dept == "Acting" else (tr("Réalisateur") if dept == "Directing" else dept)
        
        b_day = details.get("birthday", "")
        place = details.get("place_of_birth", "")
        sub_info = [dept_fr] if dept_fr else []
        if b_day:
            try:
                b_date = datetime.strptime(b_day, "%Y-%m-%d")
                age = (datetime.now() - b_date).days // 365
                sub_info.append(tr("{age} ans ({b_date})", age=age, b_date=b_date.strftime('%d/%m/%Y')))
            except Exception:
                sub_info.append(b_day)
        if place:
            sub_info.append(place)

        self.dept_label.setText(" · ".join(sub_info))

        bio = details.get("biography", "").strip()
        if bio:
            self.bio_label.setText(bio)
            self.bio_label.setToolTip(bio)

        # 2. Peupler les sections
        movies = matched.get("movies", [])
        series = matched.get("series", [])
        directed = matched.get("directed", [])

        has_any = bool(movies or series or directed)
        if not has_any:
            empty_lbl = QLabel(tr("Aucun film ni série avec {artist_name} n'a été trouvé dans votre abonnement.", artist_name=self.artist_name))
            empty_lbl.setStyleSheet("color: #94a3b8; font-size: 14px; padding: 40px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(empty_lbl)
            return

        # Section Films (Acteur)
        if movies:
            self._add_section(
                title=tr("🎬 Films disponibles ({count})", count=len(movies)),
                items=movies,
                is_movie=True
            )

        # Section Séries (Acteur)
        if series:
            self._add_section(
                title=tr("📺 Séries disponibles ({count})", count=len(series)),
                items=series,
                is_movie=False
            )

        # Section Réalisateur
        if directed:
            self._add_section(
                title=tr("🎥 En tant que Réalisateur ({count})", count=len(directed)),
                items=directed,
                is_movie=None
            )

    def _on_profile_loaded(self, url: str, pixmap: QPixmap):
        if self._profile_img_url and url == self._profile_img_url:
            self.profile_photo.setPixmap(pixmap)

    def _add_section(self, title: str, items: List[Dict[str, Any]], is_movie: Optional[bool]):
        sec_widget = QWidget()
        sec_layout = QVBoxLayout(sec_widget)
        sec_layout.setContentsMargins(0, 0, 0, 0)
        sec_layout.setSpacing(8)

        # Ligne d'en-tête de section avec titre et flèches de navigation
        sec_header = QWidget()
        sec_header_layout = QHBoxLayout(sec_header)
        sec_header_layout.setContentsMargins(0, 0, 0, 0)
        sec_header_layout.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #f8fafc; font-size: 16px; font-weight: 700;")
        sec_header_layout.addWidget(title_lbl)
        sec_header_layout.addStretch(1)

        # Boutons précédent / suivant pour le défilement du carrousel
        btn_prev = QPushButton()
        btn_prev.setIcon(get_icon("chevron_left", color="#94a3b8"))
        btn_prev.setIconSize(QSize(18, 18))
        btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_prev.setFixedSize(30, 30)
        btn_prev.setToolTip(tr("Défiler vers la gauche"))
        btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #161f30;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #2563eb;
            }
        """)

        btn_next = QPushButton()
        btn_next.setIcon(get_icon("chevron_right", color="#94a3b8"))
        btn_next.setIconSize(QSize(18, 18))
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.setFixedSize(30, 30)
        btn_next.setToolTip(tr("Défiler vers la droite"))
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #161f30;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #2563eb;
            }
        """)

        sec_header_layout.addWidget(btn_prev)
        sec_header_layout.addWidget(btn_next)
        sec_layout.addWidget(sec_header)

        # ScrollArea horizontale pour les affiches
        h_scroll = QScrollArea()
        h_scroll.setWidgetResizable(True)
        h_scroll.setFrameShape(QFrame.Shape.NoFrame)
        h_scroll.setFixedHeight(ArtistMediaCard.CARD_HEIGHT + 24)
        h_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Défilement fluide au clic sur les flèches
        step = (ArtistMediaCard.CARD_WIDTH + 12) * 3

        def scroll_carousel(delta: int):
            bar = h_scroll.horizontalScrollBar()
            target = max(bar.minimum(), min(bar.maximum(), bar.value() + delta))
            anim = QPropertyAnimation(bar, b"value", parent=bar)
            anim.setDuration(260)
            anim.setStartValue(bar.value())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            bar._active_anim = anim

        btn_prev.clicked.connect(lambda: scroll_carousel(-step))
        btn_next.clicked.connect(lambda: scroll_carousel(step))

        # Masquer les boutons si tout tient dans la vue (<= 4 éléments)
        if len(items) <= 4:
            btn_prev.hide()
            btn_next.hide()

        cards_container = QWidget()
        cards_container.setStyleSheet("background: transparent;")
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        for it in items:
            card = ArtistMediaCard(it, parent=cards_container)
            card.clicked.connect(lambda ch: self._on_card_clicked(ch, is_movie))
            cards_layout.addWidget(card)

        cards_layout.addStretch(1)
        h_scroll.setWidget(cards_container)
        sec_layout.addWidget(h_scroll)

        self.content_layout.addWidget(sec_widget)

    def _on_card_clicked(self, channel: Channel, is_movie: Optional[bool]):
        self.accept()
        st = getattr(channel, "stream_type", "")
        if st in ("movie", "vod") or is_movie is True:
            self.movie_selected.emit(channel)
        else:
            self.series_selected.emit(channel)

    def _disconnect_profile_loader(self):
        try:
            ImageLoader.instance().image_loaded.disconnect(self._on_profile_loaded)
        except (TypeError, RuntimeError):
            pass

    def accept(self):
        self._disconnect_profile_loader()
        super().accept()

    def reject(self):
        self._disconnect_profile_loader()
        super().reject()

    def closeEvent(self, event):
        self._disconnect_profile_loader()
        super().closeEvent(event)


class ArtistSuggestionItemWidget(QWidget):
    """Ligne de suggestion visuelle avec photo, nom complet officiel et œuvres phares."""

    def __init__(self, person: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.person = person
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 8, 4)
        layout.setSpacing(10)

        # Photo de profil miniature
        self.photo_lbl = RoundedPosterLabel(
            radius=16,
            border_color="#334155",
            bg_color="#0f172a",
            fallback_icon="person",
            parent=self
        )
        self.photo_lbl.setFixedSize(32, 32)
        p_path = person.get("profile_path")
        if p_path:
            img_url = f"https://image.tmdb.org/t/p/w185{p_path}"
            cached = ImageLoader.instance().get_cached_image(img_url)
            if cached:
                self.photo_lbl.setPixmap(cached)
            else:
                self._target_url = img_url
                ImageLoader.instance().image_loaded.connect(self._on_img_loaded)
                ImageLoader.instance().request_image(img_url)
        layout.addWidget(self.photo_lbl)

        # Textes (Nom complet en gras + Métier et films connus)
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)

        name_lbl = QLabel(person.get("name", ""))
        name_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700; background: transparent;")
        text_vbox.addWidget(name_lbl)

        dept = person.get("known_for_department", "")
        dept_fr = "Acteur" if dept == "Acting" else ("Réalisateur" if dept == "Directing" else dept)
        known_items = [
            x.get("title") or x.get("name")
            for x in person.get("known_for", [])
            if (x.get("title") or x.get("name"))
        ]
        sub_text = dept_fr
        if known_items:
            sub_text += f" · {', '.join(known_items[:3])}"

        sub_lbl = QLabel(sub_text)
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent;")
        text_vbox.addWidget(sub_lbl)

        layout.addLayout(text_vbox, stretch=1)

        # Chevron discret
        chev = QLabel()
        chev.setPixmap(get_icon("chevron_right", color="#64748b").pixmap(16, 16))
        layout.addWidget(chev)

    def _on_img_loaded(self, url: str, pixmap: QPixmap):
        if getattr(self, "_target_url", None) and url == self._target_url:
            self.photo_lbl.setPixmap(pixmap)


class ArtistSearchPromptDialog(QDialog):
    """
    Dialogue élégant et 100% utilisable à la souris pour rechercher un acteur ou réalisateur.
    Intègre une liste de suggestions TMDB en temps réel se réduisant au fil de la frappe.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        initial_text: str = "",
        language: str = "fr-FR"
    ):
        super().__init__(parent)
        self.language = language
        self._selected_person: Optional[Dict[str, Any]] = None
        self._worker: Optional[ArtistSuggestionsWorker] = None

        self.setWindowTitle(tr("Rechercher un acteur ou réalisateur"))
        self.setFixedSize(540, 440)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d121d;
                border: 1px solid #334155;
                border-radius: 12px;
                color: #f8fafc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # En-tête : Icône + Titre + Bouton fermer (souris)
        header = QHBoxLayout()
        header.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon("person", color="#38bdf8").pixmap(20, 20))
        header.addWidget(icon_lbl)

        title_lbl = QLabel(tr("Rechercher un Acteur ou Réalisateur"))
        title_lbl.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 700;")
        header.addWidget(title_lbl)
        header.addStretch()

        btn_close = QPushButton()
        btn_close.setIcon(get_icon("close", color="#94a3b8"))
        btn_close.setIconSize(QSize(16, 16))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                border-color: #dc2626;
            }
        """)
        btn_close.clicked.connect(self.reject)
        header.addWidget(btn_close)
        layout.addLayout(header)

        sub_lbl = QLabel(tr("Tapez le prénom ou le nom : les suggestions s'affinent en temps réel. Cliquez sur un artiste pour voir sa filmographie."))
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        sub_lbl.setWordWrap(True)
        layout.addWidget(sub_lbl)

        # Ligne de saisie avec champ + bouton Coller (souris)
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(tr("Ex : Charlie, Tom, Christopher, Drew..."))
        self.input_edit.setText(initial_text)
        self.input_edit.setClearButtonEnabled(True)
        self.input_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #60a5fa;
                background-color: #1a2333;
            }
        """)
        self.input_edit.returnPressed.connect(self._on_search_clicked)
        input_row.addWidget(self.input_edit, stretch=1)

        # Bouton "Coller" à la souris pour faciliter l'usage 100% souris
        btn_paste = QPushButton(tr("Coller"))
        btn_paste.setIcon(get_icon("content_copy", color="#94a3b8"))
        btn_paste.setIconSize(QSize(14, 14))
        btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_paste.setToolTip(tr("Coller depuis le presse-papier (clic souris)"))
        btn_paste.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        btn_paste.clicked.connect(self._paste_clipboard)
        input_row.addWidget(btn_paste)

        layout.addLayout(input_row)

        # Zone centrale : Suggestions discrètes en temps réel
        self.empty_hint_lbl = QLabel(tr("Tapez au moins 2 lettres pour afficher les suggestions..."))
        self.empty_hint_lbl.setStyleSheet("color: #64748b; font-size: 12px; padding: 20px;")
        self.empty_hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_hint_lbl)

        self.suggestions_list = QListWidget()
        self.suggestions_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.suggestions_list.setStyleSheet("""
            QListWidget {
                background-color: #131926;
                border: 1px solid #1e293b;
                border-radius: 8px;
                outline: none;
                padding: 4px;
            }
            QListWidget::item {
                background-color: #161f30;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 2px;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
                border-color: #3b82f6;
            }
            QListWidget::item:selected {
                background-color: #2563eb;
                border-color: #60a5fa;
            }
            QScrollBar:vertical {
                background: rgba(15, 23, 42, 0.4);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 3px;
                min-height: 20px;
            }
        """)
        self.suggestions_list.itemClicked.connect(self._on_item_clicked)
        self.suggestions_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.suggestions_list.hide()
        layout.addWidget(self.suggestions_list, stretch=1)

        # Boutons d'action inférieurs (100% souris)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_cancel = QPushButton(tr("Annuler"))
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f1f5f9;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self.btn_submit = QPushButton(tr(" Afficher la filmographie"))
        self.btn_submit.setIcon(get_icon("search", color="#ffffff"))
        self.btn_submit.setIconSize(QSize(14, 14))
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
        """)
        self.btn_submit.clicked.connect(self._on_search_clicked)
        btn_row.addWidget(self.btn_submit)

        layout.addLayout(btn_row)

        # Timer pour debouncing temps réel (200ms)
        self._search_timer = QTimer(self)
        self._search_timer.setInterval(200)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._fetch_suggestions)
        self.input_edit.textChanged.connect(self._on_text_changed)

        if initial_text.strip():
            self._fetch_suggestions()

    def _on_text_changed(self, text: str):
        self._selected_person = None
        self.btn_submit.setText(tr(" Afficher la filmographie"))
        self._search_timer.start()

    def _fetch_suggestions(self):
        query = self.input_edit.text().strip()
        if len(query) < 2:
            self.suggestions_list.clear()
            self.suggestions_list.hide()
            self.empty_hint_lbl.setText(tr("Tapez au moins 2 lettres pour afficher les suggestions..."))
            self.empty_hint_lbl.show()
            return

        if self._worker and self._worker.isRunning():
            self._worker.terminate()

        self.empty_hint_lbl.setText(tr("Recherche des artistes correspondants..."))
        self.empty_hint_lbl.show()

        self._worker = ArtistSuggestionsWorker(query, language=self.language, parent=self)
        self._worker.suggestions_ready.connect(self._on_suggestions_ready)
        self._worker.start()

    def _on_suggestions_ready(self, results: list, query: str):
        current_text = self.input_edit.text().strip()
        if query != current_text:
            return

        self.suggestions_list.clear()
        if not results:
            self.empty_hint_lbl.setText(tr('Aucun artiste trouvé pour "{query}".', query=query))
            self.empty_hint_lbl.show()
            self.suggestions_list.hide()
            return

        self.empty_hint_lbl.hide()
        self.suggestions_list.show()

        for p in results:
            item = QListWidgetItem(self.suggestions_list)
            item.setSizeHint(QSize(0, 48))
            widget = ArtistSuggestionItemWidget(p, parent=self.suggestions_list)
            self.suggestions_list.setItemWidget(item, widget)

    def _on_item_clicked(self, item: QListWidgetItem):
        widget = self.suggestions_list.itemWidget(item)
        if widget and hasattr(widget, "person"):
            self._selected_person = widget.person
            name = widget.person.get("name", "")
            if name:
                self.input_edit.blockSignals(True)
                self.input_edit.setText(name)
                self.input_edit.blockSignals(False)
                self.btn_submit.setText(tr(" Afficher la filmographie de {name}", name=name))

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._on_item_clicked(item)
        self.accept()

    def _paste_clipboard(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            text = clipboard.text().strip()
            if text:
                self.input_edit.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def _on_search_clicked(self):
        if not self._selected_person and self.suggestions_list.count() > 0:
            first_item = self.suggestions_list.item(0)
            widget = self.suggestions_list.itemWidget(first_item)
            if widget and hasattr(widget, "person"):
                self._selected_person = widget.person
        text = self.input_edit.text().strip()
        if text or self._selected_person:
            self.accept()

    def get_artist_name(self) -> str:
        if self._selected_person and self._selected_person.get("name"):
            return self._selected_person["name"]
        return self.input_edit.text().strip()

    def get_person_id(self) -> Optional[int]:
        if self._selected_person:
            return self._selected_person.get("id")
        return None

    def _stop_worker(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(1000)

    def closeEvent(self, event):
        self._stop_worker()
        super().closeEvent(event)

    def reject(self):
        self._stop_worker()
        super().reject()

    def accept(self):
        self._stop_worker()
        super().accept()



