"""
Contrôleur de lecture vidéo basé sur libmpv et intégré avec les signaux PyQt6.
"""

import collections
import functools
import re
import threading
import time
from typing import Optional, Dict, Any, Tuple, Set, List, Deque
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from core.mpv_setup import setup_mpv_environment

# Initialisation du dossier des DLLs pour libmpv
setup_mpv_environment()
import mpv  # noqa: E402


LANGUAGE_GROUPS: Dict[str, Tuple[List[str], Set[str]]] = {
    "fra": (
        ["fre", "fra", "fr"],
        {"fra", "fre", "fr", "french", "français", "francais", "vf", "vff", "vfq", "truefrench", "subforced"}
    ),
    "eng": (
        ["eng", "en"],
        {"eng", "en", "english", "anglais", "vo", "vost", "vostfr"}
    ),
    "spa": (
        ["spa", "es"],
        {"spa", "es", "spanish", "espagnol", "espanol", "castellano"}
    ),
    "ger": (
        ["ger", "deu", "de"],
        {"ger", "deu", "de", "german", "allemand", "deutsch"}
    ),
    "ita": (
        ["ita", "it"],
        {"ita", "it", "italian", "italien", "italiano"}
    ),
    "por": (
        ["por", "pt"],
        {"por", "pt", "portuguese", "portugais", "portugues"}
    ),
    "ara": (
        ["ara", "ar"],
        {"ara", "ar", "arabic", "arabe"}
    ),
}

FORCED_SUBTITLE_PATTERNS: List[str] = [
    r"\bforced\b",
    r"\bforce\b",
    r"\bforcé\b",
    r"\bforcée\b",
    r"\bforcés\b",
    r"\bforces\b",
    r"subforced",
    r"sub[-_]?force",
]


def is_track_forced(track: Optional[Dict[str, Any]]) -> bool:
    """Détecte si une piste de sous-titres est de type 'forcé'."""
    if not track or not isinstance(track, dict):
        return False
    if track.get("forced") is True:
        return True
    title = str(track.get("title") or "").lower()
    lang = str(track.get("lang") or "").lower()
    combined = f"{title} {lang}"
    for pat in FORCED_SUBTITLE_PATTERNS:
        if re.search(pat, combined):
            return True
    return False


def get_track_lang_family(track: Optional[Dict[str, Any]]) -> Optional[str]:
    """Identifie la famille linguistique canonique d'une piste ('fra', 'eng', etc.)."""
    if not track or not isinstance(track, dict):
        return None
    lang = str(track.get("lang") or "").lower().strip()
    title = str(track.get("title") or "").lower().strip()

    # 1. Correspondance directe sur le code de langue
    for family, (iso_list, kw_set) in LANGUAGE_GROUPS.items():
        if lang in kw_set or any(lang.startswith(iso) for iso in iso_list):
            return family

    # 2. Recherche par mots-clés dans le titre
    for family, (iso_list, kw_set) in LANGUAGE_GROUPS.items():
        for kw in kw_set:
            if len(kw) <= 2:
                if re.search(rf"\b{re.escape(kw)}\b", title):
                    return family
            else:
                if kw in title:
                    return family

    return lang if lang else None


def parse_subtitle_preference(pref: str) -> Tuple[str, bool]:
    """Extrait le code de langue de base et le statut 'forcé' d'une préférence de sous-titre."""
    pref = str(pref or "").strip()
    if not pref or pref == "off":
        return ("off", False)
    is_forced = False
    if ":forced" in pref:
        base = pref.replace(":forced", "").strip()
        is_forced = True
    elif "forced" in pref.lower():
        is_forced = True
        base = re.sub(r"(?i)[-_:]?subforced|[-_:]?forced", "", pref).strip()
        if not base:
            base = "fra"
    else:
        base = pref
    return (base, is_forced)



def _mpv_callback_in_qt_thread(method):
    """Déporte dans le thread Qt toute notification émise par libmpv.

    Les handlers enregistrés via ``mpv.observe_property`` sont appelés depuis le
    thread interne de libmpv (MPVEventHandlerThread). Or leur corps manipule des
    QTimer, émet des signaux Qt et lit/écrit des propriétés libmpv de façon
    synchrone. Exécuté dans ce thread, cela provoque des « access violation »
    (crash natif 0xC0000005, sans trace) : typiquement au moment de l'enchaînement
    vers l'épisode suivant ou à l'arrêt de la lecture, quand libmpv envoie une
    rafale d'événements (track-list, aid, sid, paused-for-cache, eof...).

    On replanifie donc systématiquement le traitement dans le thread Qt du
    contrôleur (file d'attente vidée par un QTimer, l'ordre des notifications est
    préservé). Si l'appel provient déjà de ce thread (tests unitaires, appel
    direct), il est exécuté immédiatement afin de conserver un comportement
    synchrone.
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        # Comparaison d'identifiants de threads PURS PYTHON : pas d'appel à
        # QThread.currentThread() ici. Ce dernier, invoqué depuis un thread que Qt
        # ne connaît pas, force Qt à fabriquer un QThread « adopté » à chaque
        # notification ; on évite ainsi toute interaction Qt hors du thread GUI.
        qt_thread_id = getattr(self, "_qt_thread_id", None)
        if qt_thread_id is not None and threading.get_ident() != qt_thread_id:
            self._queue_gui_call(lambda: method(self, *args, **kwargs))
            return None
        return method(self, *args, **kwargs)

    return wrapper


class PlayerController(QObject):
    # Signaux Qt pour notifier l'interface
    state_changed = pyqtSignal(str)          # 'playing', 'paused', 'stopped', 'buffering'
    time_changed = pyqtSignal(float)         # Position actuelle en secondes
    duration_changed = pyqtSignal(float)     # Durée totale
    playback_finished = pyqtSignal()         # Fin de lecture atteinte (fin de fichier)
    volume_changed = pyqtSignal(int)         # 0 - 100
    mute_changed = pyqtSignal(bool)          # True / False
    tracks_changed = pyqtSignal(list)        # Liste des pistes audio / sous-titres
    chapters_changed = pyqtSignal(list)      # Liste des chapitres [{'title': ..., 'time': ...}]
    error_occurred = pyqtSignal(str)         # Message d'erreur
    aspect_ratio_changed = pyqtSignal(str)   # '16:9', '4:3', etc.
    audio_preference_changed = pyqtSignal(str)      # 'fra', 'eng', etc.
    subtitle_preference_changed = pyqtSignal(str, bool)  # 'fra', True/False

    # File d'exécution des callbacks libmpv (voir _queue_gui_call) : remplie depuis
    # le thread de libmpv, vidée par un QTimer dans le thread Qt. Aucune API Qt
    # n'est appelée depuis le thread de libmpv.
    _qt_thread_id: Optional[int] = None

    _is_stopping: bool = False
    _stream_has_started: bool = False
    _eof_reported: bool = False
    _is_vod: bool = False
    _current_url: str = ""
    _player: Any = None

    def __init__(
        self,
        wid: Optional[int] = None,
        initial_volume: int = 80,
        preferred_audio_lang: str = "fre,fra,fr,French,français",
        preferred_subtitle_lang: str = "off",
        subtitles_enabled: bool = False,
        render_mode: bool = False,
        initial_hwdec: str = "auto",
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self._init_gui_dispatch()
        self._wid = wid
        # En mode "render API" (OpenGL), libmpv ne dessine pas dans une fenêtre
        # native : c'est le widget OpenGL qui rend les frames via mpv_render_context.
        self._render_mode = render_mode
        self._hwdec_mode = initial_hwdec or "auto"
        self._initial_volume = initial_volume
        self._preferred_audio_lang = preferred_audio_lang
        self._preferred_subtitle_lang = preferred_subtitle_lang
        self._subtitles_enabled = subtitles_enabled and (preferred_subtitle_lang != "off")
        base_sub, is_forced = parse_subtitle_preference(preferred_subtitle_lang)
        self._preferred_subtitle_forced = is_forced
        self._is_muted = False
        self._current_url = ""
        self._is_vod = False
        self._stream_has_started = False
        self._current_state = "stopped"
        self._player: Optional[mpv.MPV] = None
        # Empêche d'émettre plusieurs fois playback_finished pour un même média
        # (la propriété eof-reached peut être notifiée plusieurs fois).
        self._eof_reported = False
        self._is_stopping = False

        self._last_progress_monotonic: float = 0.0
        self._stall_start_monotonic: Optional[float] = None
        self._is_user_paused: bool = False

        self._stream_watchdog = QTimer(self)
        self._stream_watchdog.setInterval(12000)  # 12 secondes pour les flux lents/distants
        self._stream_watchdog.setSingleShot(True)
        self._stream_watchdog.timeout.connect(self._on_stream_watchdog_timeout)

        self._stall_monitor = QTimer(self)
        self._stall_monitor.setInterval(1000)  # 1 seconde de cadence de surveillance
        self._stall_monitor.timeout.connect(self._on_stall_monitor_tick)

        self._init_mpv()

    def _init_gui_dispatch(self) -> None:
        """Câble la file d'exécution Qt des callbacks libmpv (voir _queue_gui_call).

        Les closures issues des callbacks libmpv sont exécutées dans le thread Qt
        du contrôleur ; elles sont ignorées dès que cleanup() a libéré le lecteur.

        Aucune API Qt n'est appelée depuis le thread de libmpv : les observers
        remplissent une file protégée par un verrou, et un QTimer du thread Qt la
        vide. On évite ainsi le signal inter-threads (et l'appel à
        QThread.currentThread() depuis un thread étranger à Qt, qui oblige Qt à
        fabriquer un QThread « adopté » à chaque notification).
        """
        self._qt_thread_id = threading.get_ident()
        self._gui_calls_closed = False
        self._gui_calls: Deque[Any] = collections.deque()
        self._gui_calls_lock = threading.Lock()
        # 15 ms (~66 fps) : les notifications de propriétés libmpv (time-pos, track-list,
        # aid, sid, paused-for-cache...) restent perçues comme instantanées sans surcharger le thread Qt.
        self._gui_pump = QTimer(self)
        self._gui_pump.setInterval(15)
        self._gui_pump.timeout.connect(self._drain_gui_calls)
        self._gui_pump.start()

    def _queue_gui_call(self, fn) -> None:
        """Replanifie une closure libmpv dans le thread Qt du contrôleur."""
        if getattr(self, "_gui_calls_closed", False):
            return
        queue = getattr(self, "_gui_calls", None)
        if queue is None:
            # Contrôleur Qt incomplet (tests) : exécution immédiate pour ne rien
            # perdre. Ce cas ne peut pas concerner un lecteur libmpv réel, qui
            # passe obligatoirement par __init__ et _init_gui_dispatch().
            fn()
            return
        with self._gui_calls_lock:
            queue.append(fn)

    def _drain_gui_calls(self, max_calls: int = 64) -> int:
        """Exécute dans le thread Qt les closures en attente (appelé par QTimer).

        :param max_calls: nombre maximal de closures traitées par passage, afin
            qu'une rafale d'événements libmpv ne bloque pas l'interface.
        :return: nombre de closures exécutées (utilisé par les tests).
        """
        if getattr(self, "_gui_calls_closed", False):
            queue = getattr(self, "_gui_calls", None)
            if queue is not None:
                with self._gui_calls_lock:
                    queue.clear()
            return 0

        executed = 0
        while executed < max_calls:
            with self._gui_calls_lock:
                if not self._gui_calls:
                    break
                fn = self._gui_calls.popleft()
            try:
                fn()
            except Exception as exc:
                print(f"[PlayerController] Erreur dans un callback libmpv différé : {exc}")
            executed += 1
        return executed

    @property
    def is_in_gui_thread(self) -> bool:
        """True si l'appelant est dans le thread Qt d'appartenance du contrôleur."""
        owner = getattr(self, "_qt_thread_id", None)
        if owner is None:
            return True
        return threading.get_ident() == owner

    def _get_player_prop(self, key: str, default: Any = None) -> Any:
        """Récupère une propriété MPV de façon sécurisée (compatible MPV réel et Mock de test)."""
        if not self._player:
            return default
        try:
            if hasattr(self._player, "get_property"):
                val = self._player.get_property(key)
                return val if val is not None else default
            if isinstance(self._player, dict):
                return self._player.get(key, default)
            return getattr(self._player, key, default)
        except Exception:
            return default

    def _get_synchronized_track_list(self, raw_tracks: Optional[list] = None) -> list:
        """Retourne la liste des pistes avec l'attribut 'selected' synchronisé sur l'état effectif de MPV."""
        if raw_tracks is None and self._player:
            try:
                if hasattr(self._player, "get_property"):
                    raw_tracks = self._player.get_property("track-list") or []
                elif isinstance(self._player, dict):
                    raw_tracks = self._player.get("track-list") or []
            except Exception:
                raw_tracks = []
        if not raw_tracks:
            return []

        curr_sid = self._get_player_prop("sid")
        curr_aid = self._get_player_prop("aid")

        synced = []
        for t in raw_tracks:
            if not isinstance(t, dict):
                continue
            t_copy = dict(t)
            t_type = t_copy.get("type")
            t_id = t_copy.get("id")

            if t_type == "sub":
                if not self._subtitles_enabled or self._preferred_subtitle_lang == "off" or curr_sid in (None, False, "no", 0, "0"):
                    t_copy["selected"] = False
                else:
                    t_copy["selected"] = (curr_sid == t_id or str(curr_sid) == str(t_id))
            elif t_type == "audio":
                if curr_aid not in (None, False, "no", 0, "0"):
                    t_copy["selected"] = (curr_aid == t_id or str(curr_aid) == str(t_id))

            synced.append(t_copy)
        return synced

    @property
    def mpv_handle(self) -> Optional[int]:
        """Retourne le handle brut mpv_handle* (nécessaire à l'API de rendu OpenGL).

        python-mpv expose ``MPV.handle`` comme un objet ``mpv.MpvHandle`` (sous-classe
        de ``ctypes.c_void_p``). L'adresse C brute s'obtient via son attribut
        ``.value`` (et non via ``int(handle)`` qui lève une exception).
        """
        if self._player is None:
            return None
        try:
            handle = self._player.handle
        except Exception:
            return None
        if handle is None:
            return None
        # MpvHandle est un ctypes.c_void_p : l'adresse est dans .value
        value = getattr(handle, "value", None)
        if value is None:
            return None
        try:
            return int(value)
        except Exception:
            return None

    def _set_state(self, new_state: str):
        """Émet state_changed UNIQUEMENT en cas de transition d'état réelle."""
        if self._current_state != new_state:
            self._current_state = new_state
            self.state_changed.emit(new_state)

    def _init_mpv(self):
        """Instancie et configure libmpv avec des options optimisées pour l'IPTV."""
        try:
            # En rendu OpenGL (mpv_render_context), 'auto' peut tenter d'utiliser un interop
            # direct DirectX-OpenGL fragile sur certains pilotes (perte de trames de référence).
            # 'auto-safe' garantit un transfert mémoire vidéo sécurisé (d3d11va-copy / nvdec-copy).
            hwdec_val = self._hwdec_mode or "no"
            if self._render_mode and hwdec_val.lower() == "auto":
                hwdec_val = "no"

            pref_sub_base, _ = parse_subtitle_preference(self._preferred_subtitle_lang)
            family_sub = get_track_lang_family({"lang": pref_sub_base, "title": pref_sub_base}) or pref_sub_base
            if family_sub in LANGUAGE_GROUPS:
                slang_init = ",".join(LANGUAGE_GROUPS[family_sub][0])
            else:
                slang_init = family_sub or "fre,fra,fr"

            family_aud = get_track_lang_family({"lang": self._preferred_audio_lang, "title": self._preferred_audio_lang}) or self._preferred_audio_lang
            if family_aud in LANGUAGE_GROUPS:
                alang_init = ",".join(LANGUAGE_GROUPS[family_aud][0])
            else:
                alang_init = self._preferred_audio_lang or "fre,fra,fr"

            mpv_kwargs: Dict[str, Any] = {
                "input_default_bindings": False,
                "input_vo_keyboard": False,
                "osc": False,                     # Désactive l'OSD interne de MPV au profit de nos contrôles Qt
                "keep_open": "yes",
                "idle": "yes",
                "hwdec": hwdec_val,               # auto-safe garantit un décodage matériel fiable et stable avec OpenGL
                "hr_seek": "yes",                 # Recherche haute précision : recalcule toujours les I-frames (pas de bandes noires)
                "hr_seek_framedrop": "no",        # Évite absolument la corruption de macroblocs / carrés noirs pendant les sauts
                "keepaspect": "yes",
                "autofit": "100%x100%",
                "video-unscaled": "no",
                "video-align-x": 0,
                "video-align-y": 0,
                "volume": max(0, min(100, self._initial_volume)),
                "alang": alang_init,
                "sid": "auto" if (self._subtitles_enabled and self._preferred_subtitle_lang != "off") else "no",
                "slang": slang_init if (self._subtitles_enabled and self._preferred_subtitle_lang != "off") else "no",
                "demuxer_max_bytes": 64 * 1024 * 1024,   # 64MB buffer pour VOD HD/4K fluide
                "demuxer_max_back_bytes": 16 * 1024 * 1024,
                "demuxer_readahead_secs": 20,
                "cache": "yes",
                "cache_secs": 20,
                "network_timeout": 15,
                "ytdl": "yes",
                "log_handler": self._on_mpv_log
            }

            if self._render_mode:
                # Rendu via l'API OpenGL de libmpv : pas de sortie vidéo native.
                # libmpv ne doit PAS créer de fenêtre ; le rendu se fait dans le
                # FBO du QOpenGLWidget via mpv_render_context.
                mpv_kwargs["vo"] = "libmpv"
                mpv_kwargs["gpu_api"] = "opengl"
            else:
                # Rendu natif classique dans une fenêtre (HWND) fournie par Qt.
                mpv_kwargs["vo"] = "gpu"
                mpv_kwargs["gpu_context"] = "auto"
                mpv_kwargs["force_window"] = "immediate"
                if self._wid:
                    mpv_kwargs["wid"] = str(int(self._wid))

            self._player = mpv.MPV(**mpv_kwargs)

            # Enregistrement des observateurs de propriétés MPV
            self._player.observe_property("time-pos", self._on_time_pos)
            self._player.observe_property("playback-time", self._on_playback_time)
            self._player.observe_property("video-format", self._on_media_format)
            self._player.observe_property("audio-codec-name", self._on_media_format)
            self._player.observe_property("duration", self._on_duration)
            self._player.observe_property("pause", self._on_pause_changed)
            self._player.observe_property("core-idle", self._on_idle_changed)
            self._player.observe_property("eof-reached", self._on_eof_reached)
            self._player.observe_property("volume", self._on_volume_changed)
            self._player.observe_property("mute", self._on_mute_changed)
            self._player.observe_property("track-list", self._on_track_list)
            self._player.observe_property("chapter-list", self._on_chapter_list)
            self._player.observe_property("sid", self._on_sid_changed)
            self._player.observe_property("aid", self._on_aid_changed)
            self._player.observe_property("paused-for-cache", self._on_paused_for_cache)

        except Exception as e:
            self.error_occurred.emit(f"Erreur d'initialisation MPV : {e}")

        self._last_time_pos_emit = 0.0

    def _on_mpv_log(self, log_level, component, message):
        # Uniquement logging / debug, pas de signal d'erreur basé sur des logs non fatals
        if log_level in ("error", "fatal"):
            print(f"[MPV][{component}] {message.strip()}")

    @_mpv_callback_in_qt_thread
    def _on_playback_time(self, name, value):
        if value is not None and float(value) >= 0:
            self._stream_has_started = True
            if self._stream_watchdog.isActive():
                self._stream_watchdog.stop()
            self._last_progress_monotonic = time.monotonic()
            self._stall_start_monotonic = None
            if not self._is_user_paused:
                self._set_state("playing")

    @_mpv_callback_in_qt_thread
    def _on_media_format(self, name, value):
        if value:
            self._stream_has_started = True
            if self._stream_watchdog.isActive():
                self._stream_watchdog.stop()
            self._last_progress_monotonic = time.monotonic()
            if not self._is_user_paused:
                self._set_state("playing")

    @_mpv_callback_in_qt_thread
    def _on_paused_for_cache(self, name, value):
        """Notifié par MPV lorsque le cache réseau s'épuise ou se reconstitue."""
        if not self._current_url or not self._player:
            return
        if value:
            # MPV est en attente du buffer réseau -> afficher l'animation de chargement
            if self._current_state != "paused" and not self._is_user_paused:
                if self._stall_start_monotonic is None:
                    self._stall_start_monotonic = time.monotonic()
                self._set_state("buffering")
        else:
            # Le cache réseau est reconstitué -> reprise immédiate
            if self._current_state == "buffering" and not self._is_user_paused:
                self._stall_start_monotonic = None
                self._last_progress_monotonic = time.monotonic()
                self._set_state("playing")

    def _on_stall_monitor_tick(self):
        """Surveille continuellement la progression du flux et détecte les gels réseau."""
        if not self._player or not self._current_url or not self._stream_has_started:
            return
        if self._is_user_paused or self._current_state in ("paused", "stopped", "error"):
            return

        now = time.monotonic()
        elapsed_since_progress = now - self._last_progress_monotonic

        if self._current_state == "playing":
            # Si aucune frame n'a progressé depuis au moins 2.8 secondes (freeze / réseau ralenti)
            if elapsed_since_progress >= 2.8:
                self._stall_start_monotonic = now
                self._set_state("buffering")
        elif self._current_state == "buffering":
            # Si le flux est en buffering continu
            if self._stall_start_monotonic is not None:
                stall_duration = now - self._stall_start_monotonic
                # Si le gel persiste au-delà de 12 secondes, déclarer le flux indisponible
                if stall_duration >= 12.0:
                    self._stall_monitor.stop()
                    self._set_state("error")
                    self.error_occurred.emit("Flux indisponible")

    def _on_stream_watchdog_timeout(self):
        if not self._player or not self._current_url:
            return

        # Vérification si MPV est effectivement en cours de lecture
        is_active = False
        try:
            v_fmt = self._player.get_property("video-format")
            a_codec = self._player.get_property("audio-codec-name")
            p_time = self._player.get_property("playback-time")
            idle = self._player.get_property("idle-active")
            core_idle = self._player.get_property("core-idle")
            tracks = self._player.get_property("track-list") or []
            has_track = any(t.get("selected") or t.get("type") in ("video", "audio") for t in tracks if isinstance(t, dict))
            if v_fmt or a_codec or (p_time is not None and p_time > 0) or has_track or (idle is False) or (core_idle is False):
                is_active = True
        except Exception:
            pass

        if is_active:
            self._stream_has_started = True
            self._last_progress_monotonic = time.monotonic()
            self._stall_start_monotonic = None
            if not self._is_user_paused:
                self._set_state("playing")
        else:
            self._set_state("error")
            self.error_occurred.emit("Flux indisponible")

    # Observateurs MPV -> Émission de signaux Qt sécurisés multi-thread
    @_mpv_callback_in_qt_thread
    def _on_time_pos(self, name, value):
        if getattr(self, "_is_stopping", False):
            return
        if value is not None:
            val = float(value)
            self._stream_has_started = True
            if self._stream_watchdog.isActive():
                self._stream_watchdog.stop()
            self._last_progress_monotonic = time.monotonic()
            self._stall_start_monotonic = None
            if not self._is_user_paused:
                self._set_state("playing")
            if abs(val - self._last_time_pos_emit) >= 0.25:  # Max 4 notifications/seconde
                self._last_time_pos_emit = val
                self.time_changed.emit(val)

    @_mpv_callback_in_qt_thread
    def _on_duration(self, name, value):
        if getattr(self, "_is_stopping", False):
            return
        if value is not None and value > 0:
            self._is_vod = True
            self.duration_changed.emit(float(value))
        else:
            self._is_vod = False
            self.duration_changed.emit(0.0)

    @_mpv_callback_in_qt_thread
    def _on_pause_changed(self, name, value):
        if value is not None:
            if value:
                self._is_user_paused = True
                self._stall_start_monotonic = None
                self._set_state("paused")
            else:
                self._is_user_paused = False
                self._stream_has_started = True
                self._last_progress_monotonic = time.monotonic()
                self._stall_start_monotonic = None
                self._set_state("playing")

    @_mpv_callback_in_qt_thread
    def _on_idle_changed(self, name, value):
        if value and not self._current_url:
            self._set_state("stopped")

    @_mpv_callback_in_qt_thread
    def _on_eof_reached(self, name, value):
        """Fin de fichier atteinte (valable uniquement pour les contenus à durée finie).

        Les flux en direct (live) n'atteignent jamais l'EOF ; cet événement ne
        concerne donc que les films, séries et replays. On émet UNE seule fois
        ``playback_finished`` par média afin que l'UI puisse, par exemple,
        enchaîner sur l'épisode suivant d'une série.
        """
        if not value:
            self._eof_reported = False
            return
        if not self._is_vod or not self._current_url or self.__dict__.get("_is_stopping", False):
            return
        if not self._stream_has_started:
            return
        if self._eof_reported:
            return

        # Protection anti-faux-EOF : vérifier qu'on était bien en fin de média
        # Si on est à moins de 85% de la vidéo, ce n'est PAS un EOF naturel (ex: arrêt utilisateur ou coupure)
        try:
            pos = float(self._player.time_pos or 0.0) if self._player else 0.0
            dur = float(self._player.duration or 0.0) if self._player else 0.0
            if dur > 60 and pos < (dur * 0.85) and (dur - pos) > 60:
                return
        except Exception:
            pass

        self._eof_reported = True
        self.playback_finished.emit()

    @_mpv_callback_in_qt_thread
    def _on_volume_changed(self, name, value):
        if value is not None:
            self.volume_changed.emit(int(value))

    @_mpv_callback_in_qt_thread
    def _on_mute_changed(self, name, value):
        if value is not None:
            self._is_muted = bool(value)
            self.mute_changed.emit(self._is_muted)

    @_mpv_callback_in_qt_thread
    def _on_sid_changed(self, name, value):
        if self._player and not getattr(self, "_is_stopping", False):
            self.tracks_changed.emit(self._get_synchronized_track_list())

    @_mpv_callback_in_qt_thread
    def _on_aid_changed(self, name, value):
        if self._player and not getattr(self, "_is_stopping", False):
            self.tracks_changed.emit(self._get_synchronized_track_list())

    @_mpv_callback_in_qt_thread
    def _on_track_list(self, name, value):
        if value is not None and isinstance(value, list):
            has_tracks = any(t.get("type") in ("video", "audio") for t in value if isinstance(t, dict))
            if has_tracks:
                self._stream_has_started = True
                if self._stream_watchdog.isActive():
                    self._stream_watchdog.stop()
                self._set_state("playing")
            self._auto_select_preferred_audio(value)
            self._auto_select_preferred_subtitles(value)
            synced_tracks = self._get_synchronized_track_list(value)
            self.tracks_changed.emit(synced_tracks)

    @_mpv_callback_in_qt_thread
    def _on_chapter_list(self, name, value):
        chapters = []
        if isinstance(value, list):
            for c in value:
                if isinstance(c, dict) and "time" in c and c["time"] is not None:
                    chapters.append({
                        "title": str(c.get("title") or "").strip(),
                        "time": float(c["time"])
                    })
        self.chapters_changed.emit(chapters)

    def get_chapters(self) -> list:
        if not self._player:
            return []
        try:
            raw = getattr(self._player, "chapter_list", None)
            if raw is None and hasattr(self._player, "__getitem__"):
                try:
                    raw = self._player["chapter-list"]
                except Exception:
                    pass
            if isinstance(raw, list):
                return [{
                    "title": str(c.get("title") or "").strip(),
                    "time": float(c.get("time", 0.0))
                } for c in raw if isinstance(c, dict) and "time" in c and c["time"] is not None]
        except Exception:
            pass
        return []

    def _auto_select_preferred_audio(self, tracks: list):
        """Sélectionne intelligemment la piste audio correspondant à la langue préférée."""
        if not self._preferred_audio_lang or not self._player:
            return

        audio_tracks = [t for t in tracks if t.get("type") == "audio"]
        if len(audio_tracks) <= 1:
            return

        raw_tokens = [tok.strip().lower() for tok in self._preferred_audio_lang.split(",") if tok.strip()]
        if not raw_tokens:
            return

        expanded_keywords = set(raw_tokens)
        for family, (iso_list, kw_set) in LANGUAGE_GROUPS.items():
            if any(k in expanded_keywords for k in kw_set) or any(k in expanded_keywords for k in iso_list):
                expanded_keywords.update(kw_set)

        best_track = None
        best_score = 0

        for t in audio_tracks:
            score = 0
            t_lang = str(t.get("lang") or "").lower().strip()
            t_title = str(t.get("title") or "").lower().strip()
            t_family = get_track_lang_family(t)

            # 1. Famille linguistique et code ISO
            if t_family and any(k in expanded_keywords for k in LANGUAGE_GROUPS.get(t_family, ([], set()))[1]):
                score += 12
            elif t_lang in expanded_keywords:
                score += 10
            elif any(t_lang.startswith(k) for k in expanded_keywords if len(k) >= 2):
                score += 8

            # 2. Titre de la piste
            for kw in expanded_keywords:
                if len(kw) <= 2:
                    if re.search(rf"\b{re.escape(kw)}\b", t_title):
                        score += 7
                else:
                    if kw in t_title:
                        score += 7

            if score > best_score:
                best_score = score
                best_track = t

        if best_track and best_score > 0:
            target_id = best_track.get("id")
            try:
                current_aid = self._get_player_prop("aid")
                if current_aid != target_id:
                    self._player["aid"] = target_id
            except Exception as e:
                print(f"[PlayerController] Auto audio select error: {e}")
            for t in tracks:
                if t.get("type") == "audio":
                    t["selected"] = (t.get("id") == target_id)

    def _auto_select_preferred_subtitles(self, tracks: list):
        """Applique la préférence utilisateur pour les sous-titres avec prise en charge complète du statut forcé."""
        if not self._player:
            return

        # Cas 1 : Sous-titres désactivés par l'utilisateur -> forcer la désactivation
        if not self._subtitles_enabled or self._preferred_subtitle_lang == "off":
            try:
                curr_sid = self._get_player_prop("sid")
                if curr_sid and curr_sid != "no":
                    self._player["sid"] = "no"
            except Exception:
                pass
            for t in tracks:
                if t.get("type") == "sub":
                    t["selected"] = False
            return

        # Cas 2 : Sous-titres activés
        sub_tracks = [t for t in tracks if t.get("type") == "sub"]
        if not sub_tracks:
            return

        pref_base, want_forced = parse_subtitle_preference(self._preferred_subtitle_lang)
        if pref_base == "auto":
            try:
                curr_sid = self._get_player_prop("sid")
                if not curr_sid or curr_sid == "no":
                    self._player["sid"] = sub_tracks[0].get("id", 1)
            except Exception:
                pass
            return

        target_family = get_track_lang_family({"lang": pref_base, "title": pref_base}) or pref_base.lower()

        expanded_keywords = set()
        if target_family in LANGUAGE_GROUPS:
            expanded_keywords.update(LANGUAGE_GROUPS[target_family][1])
        else:
            raw_tokens = [tok.strip().lower() for tok in pref_base.split(",") if tok.strip()]
            expanded_keywords.update(raw_tokens)
            for fam, (iso_list, kw_set) in LANGUAGE_GROUPS.items():
                if any(k in expanded_keywords for k in kw_set) or any(k in expanded_keywords for k in iso_list):
                    expanded_keywords.update(kw_set)

        best_track = None
        best_score = -1

        for t in sub_tracks:
            score = 0
            t_family = get_track_lang_family(t)
            t_forced = is_track_forced(t)
            t_lang = str(t.get("lang") or "").lower().strip()
            t_title = str(t.get("title") or "").lower().strip()

            is_same_lang = False
            if t_family and t_family == target_family:
                is_same_lang = True
            elif t_lang in expanded_keywords:
                is_same_lang = True
            elif any(t_lang.startswith(k) for k in expanded_keywords if len(k) >= 2):
                is_same_lang = True
            else:
                for kw in expanded_keywords:
                    if len(kw) <= 2:
                        if re.search(rf"\b{re.escape(kw)}\b", t_title):
                            is_same_lang = True
                            break
                    else:
                        if kw in t_title:
                            is_same_lang = True
                            break

            if is_same_lang:
                if want_forced:
                    if t_forced:
                        score = 100  # Parfaite adéquation : langue cible + forcé
                    else:
                        score = 40   # Fallback langue cible complète
                else:
                    if not t_forced:
                        score = 100  # Parfaite adéquation : langue cible + complet
                    else:
                        score = 25   # Fallback langue cible forcée
            else:
                if want_forced and t_forced:
                    score = 5
                else:
                    score = 0

            if score > best_score:
                best_score = score
                best_track = t

        target_track = best_track if (best_track and best_score > 0) else None
        if target_track:
            target_id = target_track.get("id")
            try:
                curr_sid = self._get_player_prop("sid")
                if curr_sid != target_id:
                    self._player["sid"] = target_id
            except Exception:
                pass
            for t in tracks:
                if t.get("type") == "sub":
                    t["selected"] = (t.get("id") == target_id)
        else:
            try:
                curr_sid = self._get_player_prop("sid")
                if curr_sid and curr_sid != "no":
                    self._player["sid"] = "no"
            except Exception:
                pass
            for t in tracks:
                if t.get("type") == "sub":
                    t["selected"] = False

    # ------------------ CONTRÔLES PUBLICS ------------------

    def set_window_handle(self, wid: int):
        """Attache un nouveau handle de fenêtre Qt (no-op en mode render API OpenGL)."""
        self._wid = wid
        if self._render_mode:
            # En rendu OpenGL, libmpv ne possède pas de fenêtre : rien à faire.
            return
        if self._player:
            try:
                self._player["wid"] = str(int(wid))
            except Exception as e:
                print(f"Erreur changement wid: {e}")

    def play(self, url: str, start_time: float = 0.0, user_agent: Optional[str] = None, http_referrer: Optional[str] = None, extra_headers: Optional[Dict[str, str]] = None):
        """Lance la lecture d'un flux ou fichier vidéo avec position de départ optionnelle."""
        if not self._player or not url:
            return

        self._is_stopping = False

        if self._current_url and self._player:
            try:
                self._player.command("stop")
            except Exception:
                pass

        self._current_url = url
        self._stream_has_started = False
        self._eof_reported = False
        self._is_vod = False
        self._is_user_paused = False
        self._last_progress_monotonic = time.monotonic()
        self._stall_start_monotonic = None
        self._stream_watchdog.start()
        self._stall_monitor.start()
        self.chapters_changed.emit([])
        self._set_state("buffering")

        try:
            # Position de démarrage (reprise de lecture)
            if start_time > 0:
                self._player["start"] = f"+{start_time:.1f}"
            else:
                self._player["start"] = "none"

            # Configuration des en-têtes HTTP
            if user_agent:
                self._player["user-agent"] = user_agent

            headers_list = []
            if http_referrer:
                headers_list.append(f"Referer: {http_referrer}")
            if extra_headers:
                for k, v in extra_headers.items():
                    headers_list.append(f"{k}: {v}")

            if headers_list:
                self._player["http-header-fields"] = ",".join(headers_list)
            else:
                self._player["http-header-fields"] = ""

            # Libération immédiate de la bande passante réseau pour le flux vidéo
            try:
                from core.image_loader import ImageLoader
                ImageLoader.instance().cancel_pending()
            except Exception:
                pass

            # Lancement de la lecture
            self._player.play(url)
            self._player.pause = False
            if not self._subtitles_enabled or self._preferred_subtitle_lang == "off":
                try:
                    self._player["sid"] = "no"
                except Exception:
                    pass
            else:
                pref_base, want_forced = parse_subtitle_preference(self._preferred_subtitle_lang)
                family = get_track_lang_family({"lang": pref_base, "title": pref_base}) or pref_base
                if family in LANGUAGE_GROUPS:
                    slang_val = ",".join(LANGUAGE_GROUPS[family][0])
                else:
                    slang_val = family or "fre,fra,fr"
                try:
                    self._player["slang"] = slang_val
                    self._player["sid"] = "auto"
                except Exception:
                    pass

        except Exception as e:
            if self._stream_watchdog.isActive():
                self._stream_watchdog.stop()
            if self._stall_monitor.isActive():
                self._stall_monitor.stop()
            self.error_occurred.emit(f"Erreur de lecture : {e}")
            self._set_state("error")

    def pause(self):
        self._is_user_paused = True
        self._stall_start_monotonic = None
        if self._player:
            self._player.pause = True

    def resume(self):
        self._is_user_paused = False
        self._last_progress_monotonic = time.monotonic()
        self._stall_start_monotonic = None
        if self._player:
            self._player.pause = False

    def toggle_pause(self):
        if self._player:
            if self._player.pause:
                self.resume()
            else:
                self.pause()

    def stop(self):
        self._is_stopping = True
        gui_lock = getattr(self, "_gui_calls_lock", None)
        if gui_lock:
            with gui_lock:
                if hasattr(self, "_gui_calls"):
                    self._gui_calls.clear()
        if self._stream_watchdog.isActive():
            self._stream_watchdog.stop()
        if self._stall_monitor.isActive():
            self._stall_monitor.stop()
        self._stream_has_started = False
        self._eof_reported = True
        self._is_vod = False
        self._stall_start_monotonic = None
        self._is_user_paused = False
        if self._player:
            try:
                self._player.command("stop")
                self._player["start"] = "none"
                self._player["http-header-fields"] = ""
                self._current_url = ""
                self._set_state("stopped")
                self.time_changed.emit(0.0)
                self.duration_changed.emit(0.0)
                self.chapters_changed.emit([])
            except Exception:
                pass

    def seek(self, seconds: float, relative: bool = False):
        self._eof_reported = False
        self._last_progress_monotonic = time.monotonic()
        self._stall_start_monotonic = None
        if self._player:
            try:
                if relative:
                    self._player.seek(seconds, "relative")
                else:
                    self._player.seek(seconds, "absolute")
            except Exception as e:
                print(f"Seek error: {e}")

    def set_volume(self, volume: int):
        """Définit le volume (0 à 100)."""
        if self._player:
            vol = max(0, min(100, volume))
            self._player.volume = vol

    def set_mute(self, muted: bool):
        if self._player:
            self._player.mute = muted

    def toggle_mute(self):
        if self._player:
            self.set_mute(not self._is_muted)

    def set_aspect_ratio(self, ratio: str):
        """Définit le format d'image ('-1' pour auto/désactivé, '16:9', '4:3', etc.)."""
        if self._player:
            try:
                self._player["video-aspect-override"] = ratio
                self.aspect_ratio_changed.emit(ratio)
            except Exception as e:
                print(f"Aspect ratio error: {e}")

    def set_audio_track(self, track_id: int):
        """Bascule sur une piste audio spécifique et mémorise la langue si disponible."""
        if self._player:
            try:
                self._player["aid"] = track_id
                tracks = self._get_player_prop("track-list") or []
                chosen_track = None
                for t in tracks:
                    if t.get("type") == "audio" and t.get("id") == track_id:
                        chosen_track = t
                        break
                if chosen_track:
                    family = get_track_lang_family(chosen_track) or chosen_track.get("lang") or chosen_track.get("title") or ""
                    if family:
                        if family in LANGUAGE_GROUPS:
                            alang_val = ",".join(LANGUAGE_GROUPS[family][0])
                        else:
                            alang_val = family
                        self._preferred_audio_lang = alang_val
                        try:
                            self._player["alang"] = alang_val
                        except Exception:
                            pass
                        self.audio_preference_changed.emit(alang_val)
                self.tracks_changed.emit(self._get_synchronized_track_list())
            except Exception as e:
                print(f"Audio track error: {e}")

    def set_preferred_audio_lang(self, lang_str: str):
        """Définit la préférence globale de langue audio et met à jour MPV."""
        self._preferred_audio_lang = lang_str
        if self._player:
            try:
                family = get_track_lang_family({"lang": lang_str, "title": lang_str}) or lang_str
                if family in LANGUAGE_GROUPS:
                    alang_val = ",".join(LANGUAGE_GROUPS[family][0])
                else:
                    alang_val = lang_str or "fre,fra,fr"
                self._player["alang"] = alang_val
            except Exception:
                pass

    def set_subtitle_track(self, track_id: int):
        """Bascule sur une piste de sous-titres spécifique (0 pour désactiver)."""
        if self._player:
            try:
                if track_id > 0:
                    self._player["sid"] = track_id
                    self._subtitles_enabled = True
                    tracks = self._get_player_prop("track-list") or []
                    chosen_track = None
                    for t in tracks:
                        if t.get("type") == "sub" and t.get("id") == track_id:
                            chosen_track = t
                            break

                    is_forced = is_track_forced(chosen_track) if chosen_track else False
                    family = get_track_lang_family(chosen_track) if chosen_track else None
                    if not family and chosen_track:
                        family = chosen_track.get("lang") or chosen_track.get("title") or "fra"
                    if not family:
                        family = "fra"

                    self._preferred_subtitle_forced = is_forced
                    if is_forced:
                        self._preferred_subtitle_lang = f"{family}:forced"
                    else:
                        self._preferred_subtitle_lang = family

                    if family in LANGUAGE_GROUPS:
                        slang_val = ",".join(LANGUAGE_GROUPS[family][0])
                    else:
                        slang_val = family
                    try:
                        self._player["slang"] = slang_val
                    except Exception:
                        pass
                    self.subtitle_preference_changed.emit(self._preferred_subtitle_lang, True)
                else:
                    self._player["sid"] = "no"
                    self._subtitles_enabled = False
                    self._preferred_subtitle_lang = "off"
                    self._preferred_subtitle_forced = False
                    try:
                        self._player["slang"] = "no"
                    except Exception:
                        pass
                    self.subtitle_preference_changed.emit("off", False)

                self.tracks_changed.emit(self._get_synchronized_track_list())
            except Exception as e:
                print(f"Subtitle track error: {e}")

    def set_preferred_subtitle_lang(self, lang_str: str, enabled: bool = True):
        """Définit la préférence globale de sous-titres et met à jour MPV."""
        self._preferred_subtitle_lang = lang_str or "off"
        self._subtitles_enabled = enabled and (self._preferred_subtitle_lang != "off")
        base_lang, is_forced = parse_subtitle_preference(self._preferred_subtitle_lang)
        self._preferred_subtitle_forced = is_forced
        if self._player:
            try:
                if not self._subtitles_enabled:
                    self._player["sid"] = "no"
                    self._player["slang"] = "no"
                else:
                    family = get_track_lang_family({"lang": base_lang, "title": base_lang}) or base_lang
                    if family in LANGUAGE_GROUPS:
                        slang_val = ",".join(LANGUAGE_GROUPS[family][0])
                    else:
                        slang_val = family or "fre,fra,fr"
                    self._player["slang"] = slang_val
            except Exception:
                pass

    def set_hwdec(self, hwdec: str):
        """Définit le mode d'accélération matérielle ('auto', 'd3d11va', 'nvdec', 'no')."""
        self._hwdec_mode = hwdec or "auto"
        if self._player:
            try:
                target_hwdec = self._hwdec_mode
                if self._render_mode and target_hwdec.lower() == "auto":
                    target_hwdec = "no"
                self._player["hwdec"] = target_hwdec
            except Exception as e:
                print(f"HWDec error: {e}")

    def set_deinterlace(self, enable: bool):
        """Active ou désactive le désentrelacement."""
        if self._player:
            try:
                self._player["deinterlace"] = "yes" if enable else "no"
            except Exception as e:
                print(f"Deinterlace error: {e}")

    @property
    def is_playing(self) -> bool:
        """Retourne True si un média est en cours de lecture ou en pause (session active)."""
        return self._current_state in ("playing", "paused", "buffering") and bool(self._current_url)

    def cleanup(self):
        """Libère les ressources MPV à la fermeture."""
        # Aucune closure libmpv en attente ne doit s'exécuter sur un lecteur détruit.
        self._gui_calls_closed = True
        pump = getattr(self, "_gui_pump", None)
        if pump is not None:
            try:
                pump.stop()
            except Exception:
                pass
        queue = getattr(self, "_gui_calls", None)
        if queue is not None:
            with self._gui_calls_lock:
                queue.clear()
        if hasattr(self, "_stream_watchdog") and self._stream_watchdog.isActive():
            self._stream_watchdog.stop()
        if hasattr(self, "_stall_monitor") and self._stall_monitor.isActive():
            self._stall_monitor.stop()
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
            try:
                self._player.terminate()
            except Exception:
                pass
            self._player = None
