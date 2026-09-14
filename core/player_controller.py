"""
Contrôleur de lecture vidéo basé sur libmpv et intégré avec les signaux PyQt6.
"""

from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from core.mpv_setup import setup_mpv_environment

# Initialisation du dossier des DLLs pour libmpv
setup_mpv_environment()
import mpv  # noqa: E402


class PlayerController(QObject):
    # Signaux Qt pour notifier l'interface
    state_changed = pyqtSignal(str)          # 'playing', 'paused', 'stopped', 'buffering'
    time_changed = pyqtSignal(float)         # Position actuelle en secondes
    duration_changed = pyqtSignal(float)     # Durée totale
    playback_finished = pyqtSignal()         # Fin de lecture atteinte (fin de fichier)
    volume_changed = pyqtSignal(int)         # 0 - 100
    mute_changed = pyqtSignal(bool)          # True / False
    tracks_changed = pyqtSignal(list)        # Liste des pistes audio / sous-titres
    error_occurred = pyqtSignal(str)         # Message d'erreur
    aspect_ratio_changed = pyqtSignal(str)   # '16:9', '4:3', etc.
    audio_preference_changed = pyqtSignal(str)      # 'fra', 'eng', etc.
    subtitle_preference_changed = pyqtSignal(str, bool)  # 'fra', True/False

    def __init__(
        self,
        wid: Optional[int] = None,
        initial_volume: int = 80,
        preferred_audio_lang: str = "fre,fra,fr,French,français",
        preferred_subtitle_lang: str = "off",
        subtitles_enabled: bool = False,
        render_mode: bool = False,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self._wid = wid
        # En mode "render API" (OpenGL), libmpv ne dessine pas dans une fenêtre
        # native : c'est le widget OpenGL qui rend les frames via mpv_render_context.
        self._render_mode = render_mode
        self._initial_volume = initial_volume
        self._preferred_audio_lang = preferred_audio_lang
        self._preferred_subtitle_lang = preferred_subtitle_lang
        self._subtitles_enabled = subtitles_enabled and (preferred_subtitle_lang != "off")
        self._is_muted = False
        self._current_url = ""
        self._is_vod = False
        self._stream_has_started = False
        self._current_state = "stopped"
        self._player: Optional[mpv.MPV] = None
        # Empêche d'émettre plusieurs fois playback_finished pour un même média
        # (la propriété eof-reached peut être notifiée plusieurs fois).
        self._eof_reported = False

        self._stream_watchdog = QTimer(self)
        self._stream_watchdog.setInterval(12000)  # 12 secondes pour les flux lents/distants
        self._stream_watchdog.setSingleShot(True)
        self._stream_watchdog.timeout.connect(self._on_stream_watchdog_timeout)

        self._init_mpv()

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
            mpv_kwargs: Dict[str, Any] = {
                "input_default_bindings": False,
                "input_vo_keyboard": False,
                "osc": False,                     # Désactive l'OSD interne de MPV au profit de nos contrôles Qt
                "keep_open": "yes",
                "idle": "yes",
                "hwdec": "auto-safe",             # auto-safe garantit un décodage matériel fiable et stable avec OpenGL
                "keepaspect": "yes",
                "autofit": "100%x100%",
                "video-unscaled": "no",
                "video-align-x": 0,
                "video-align-y": 0,
                "volume": max(0, min(100, self._initial_volume)),
                "alang": self._preferred_audio_lang or "fre,fra,fr",
                "sid": "auto" if (self._subtitles_enabled and self._preferred_subtitle_lang != "off") else "no",
                "slang": self._preferred_subtitle_lang if (self._subtitles_enabled and self._preferred_subtitle_lang != "off") else "no",
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

        except Exception as e:
            self.error_occurred.emit(f"Erreur d'initialisation MPV : {e}")

        self._last_time_pos_emit = 0.0

    def _on_mpv_log(self, log_level, component, message):
        # Uniquement logging / debug, pas de signal d'erreur basé sur des logs non fatals
        if log_level in ("error", "fatal"):
            print(f"[MPV][{component}] {message.strip()}")

    def _on_playback_time(self, name, value):
        if value is not None and float(value) >= 0:
            self._stream_has_started = True
            if self._stream_watchdog.isActive():
                self._stream_watchdog.stop()
            self._set_state("playing")

    def _on_media_format(self, name, value):
        if value:
            self._stream_has_started = True
            if self._stream_watchdog.isActive():
                self._stream_watchdog.stop()
            self._set_state("playing")

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
            self._set_state("playing")
        else:
            self._set_state("error")
            self.error_occurred.emit("Flux indisponible")

    # Observateurs MPV -> Émission de signaux Qt sécurisés multi-thread
    def _on_time_pos(self, name, value):
        if value is not None:
            val = float(value)
            self._stream_has_started = True
            if self._stream_watchdog.isActive():
                self._stream_watchdog.stop()
            self._set_state("playing")
            if abs(val - self._last_time_pos_emit) >= 0.25:  # Max 4 notifications/seconde
                self._last_time_pos_emit = val
                self.time_changed.emit(val)

    def _on_duration(self, name, value):
        if value is not None and value > 0:
            self._is_vod = True
            self.duration_changed.emit(float(value))
        else:
            self._is_vod = False
            self.duration_changed.emit(0.0)

    def _on_pause_changed(self, name, value):
        if value is not None:
            if value:
                self._set_state("paused")
            else:
                self._stream_has_started = True
                self._set_state("playing")

    def _on_idle_changed(self, name, value):
        if value and not self._current_url:
            self._set_state("stopped")

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
        if not self._is_vod or not self._current_url:
            return
        if self._eof_reported:
            return
        self._eof_reported = True
        self.playback_finished.emit()

    def _on_volume_changed(self, name, value):
        if value is not None:
            self.volume_changed.emit(int(value))

    def _on_mute_changed(self, name, value):
        if value is not None:
            self._is_muted = bool(value)
            self.mute_changed.emit(self._is_muted)

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
            self.tracks_changed.emit(value)

    def _auto_select_preferred_audio(self, tracks: list):
        """Sélectionne intelligemment la piste audio correspondant à la langue préférée."""
        if not self._preferred_audio_lang or not self._player:
            return

        audio_tracks = [t for t in tracks if t.get("type") == "audio"]
        if len(audio_tracks) <= 1:
            return

        # Construction des mots-clés de recherche
        raw_tokens = [tok.strip().lower() for tok in self._preferred_audio_lang.split(",") if tok.strip()]
        if not raw_tokens:
            return

        # Expansion des équivalences linguistiques
        expanded_keywords = set(raw_tokens)
        french_keys = {"fra", "fre", "fr", "french", "français", "francais", "vf", "vff", "vfq", "truefrench"}
        english_keys = {"eng", "en", "english", "anglais", "vo", "vost", "vostfr"}
        spanish_keys = {"spa", "es", "spanish", "espagnol", "espanol", "castellano"}
        german_keys = {"ger", "deu", "de", "german", "allemand", "deutsch"}
        italian_keys = {"ita", "it", "italian", "italien", "italiano"}
        portuguese_keys = {"por", "pt", "portuguese", "portugais", "portugues"}
        arabic_keys = {"ara", "ar", "arabic", "arabe"}

        for group in (french_keys, english_keys, spanish_keys, german_keys, italian_keys, portuguese_keys, arabic_keys):
            if any(k in expanded_keywords for k in group):
                expanded_keywords.update(group)

        # Recherche de la meilleure piste
        best_track = None
        best_score = 0
        import re

        for t in audio_tracks:
            score = 0
            t_lang = (t.get("lang") or "").lower().strip()
            t_title = (t.get("title") or "").lower().strip()

            # 1. Correspondance sur le code ISO / langue (priorité absolue)
            if t_lang in expanded_keywords:
                score += 10
            elif any(t_lang.startswith(k) for k in expanded_keywords if len(k) >= 2):
                score += 8

            # 2. Correspondance dans le titre de la piste (ex: "French AC3", "VFF", etc.)
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

        if best_track and best_score > 0 and not best_track.get("selected"):
            try:
                target_id = best_track.get("id")
                current_aid = self._player.get_property("aid")
                if current_aid != target_id:
                    self._player["aid"] = target_id
            except Exception as e:
                print(f"[PlayerController] Auto audio select error: {e}")

    def _auto_select_preferred_subtitles(self, tracks: list):
        """Applique la préférence utilisateur pour les sous-titres de manière stricte et persistante."""
        if not self._player:
            return

        # Cas 1 : Sous-titres désactivés par l'utilisateur -> forcer la désactivation
        if not self._subtitles_enabled or self._preferred_subtitle_lang == "off":
            try:
                curr_sid = self._player.get_property("sid")
                if curr_sid and curr_sid != "no":
                    self._player["sid"] = "no"
            except Exception:
                pass
            return

        # Cas 2 : Sous-titres activés par l'utilisateur
        sub_tracks = [t for t in tracks if t.get("type") == "sub"]
        if not sub_tracks:
            return

        pref_lang = (self._preferred_subtitle_lang or "auto").strip().lower()
        if pref_lang == "auto":
            try:
                curr_sid = self._player.get_property("sid")
                if not curr_sid or curr_sid == "no":
                    self._player["sid"] = sub_tracks[0].get("id", 1)
            except Exception:
                pass
            return

        raw_tokens = [tok.strip().lower() for tok in pref_lang.split(",") if tok.strip()]
        expanded_keywords = set(raw_tokens)
        french_keys = {"fra", "fre", "fr", "french", "français", "francais", "vf", "vff", "vfq", "truefrench"}
        english_keys = {"eng", "en", "english", "anglais", "vo", "vost", "vostfr"}
        spanish_keys = {"spa", "es", "spanish", "espagnol", "espanol", "castellano"}
        german_keys = {"ger", "deu", "de", "german", "allemand", "deutsch"}
        italian_keys = {"ita", "it", "italian", "italien", "italiano"}
        portuguese_keys = {"por", "pt", "portuguese", "portugais", "portugues"}
        arabic_keys = {"ara", "ar", "arabic", "arabe"}

        for group in (french_keys, english_keys, spanish_keys, german_keys, italian_keys, portuguese_keys, arabic_keys):
            if any(k in expanded_keywords for k in group):
                expanded_keywords.update(group)

        import re
        best_track = None
        best_score = 0

        for t in sub_tracks:
            score = 0
            t_lang = (t.get("lang") or "").lower().strip()
            t_title = (t.get("title") or "").lower().strip()

            if t_lang in expanded_keywords:
                score += 10
            elif any(t_lang.startswith(k) for k in expanded_keywords if len(k) >= 2):
                score += 8

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

        target_track = best_track or sub_tracks[0]
        if target_track:
            try:
                target_id = target_track.get("id")
                curr_sid = self._player.get_property("sid")
                if curr_sid != target_id:
                    self._player["sid"] = target_id
            except Exception:
                pass

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

        self._current_url = url
        self._stream_has_started = False
        self._eof_reported = False
        self._stream_watchdog.start()
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

        except Exception as e:
            if self._stream_watchdog.isActive():
                self._stream_watchdog.stop()
            self.error_occurred.emit(f"Erreur de lecture : {e}")
            self._set_state("error")

    def pause(self):
        if self._player:
            self._player.pause = True

    def resume(self):
        if self._player:
            self._player.pause = False

    def toggle_pause(self):
        if self._player:
            self._player.pause = not self._player.pause

    def stop(self):
        if self._stream_watchdog.isActive():
            self._stream_watchdog.stop()
        self._stream_has_started = False
        self._eof_reported = False
        if self._player:
            try:
                self._player.command("stop")
                self._player["start"] = "none"
                self._player["http-header-fields"] = ""
                self._current_url = ""
                self._set_state("stopped")
                self.time_changed.emit(0.0)
                self.duration_changed.emit(0.0)
            except Exception:
                pass

    def seek(self, seconds: float, relative: bool = False):
        self._eof_reported = False
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
                tracks = self._player["track-list"] or []
                for t in tracks:
                    if t.get("type") == "audio" and t.get("id") == track_id:
                        lang = t.get("lang") or t.get("title") or ""
                        if lang:
                            self._preferred_audio_lang = lang
                            self._player["alang"] = lang
                            self.audio_preference_changed.emit(lang)
                        break
            except Exception as e:
                print(f"Audio track error: {e}")

    def set_preferred_audio_lang(self, lang_str: str):
        """Définit la préférence globale de langue audio et met à jour MPV."""
        self._preferred_audio_lang = lang_str
        if self._player:
            try:
                self._player["alang"] = lang_str or "fre,fra,fr"
            except Exception:
                pass

    def set_subtitle_track(self, track_id: int):
        """Bascule sur une piste de sous-titres spécifique (0 pour désactiver)."""
        if self._player:
            try:
                if track_id > 0:
                    self._player["sid"] = track_id
                    self._subtitles_enabled = True
                    tracks = self._player["track-list"] or []
                    lang = ""
                    for t in tracks:
                        if t.get("type") == "sub" and t.get("id") == track_id:
                            lang = t.get("lang") or t.get("title") or ""
                            break
                    self._preferred_subtitle_lang = lang or "auto"
                    try:
                        self._player["slang"] = self._preferred_subtitle_lang
                    except Exception:
                        pass
                    self.subtitle_preference_changed.emit(self._preferred_subtitle_lang, True)
                else:
                    self._player["sid"] = "no"
                    self._subtitles_enabled = False
                    self._preferred_subtitle_lang = "off"
                    try:
                        self._player["slang"] = "no"
                    except Exception:
                        pass
                    self.subtitle_preference_changed.emit("off", False)
            except Exception as e:
                print(f"Subtitle track error: {e}")

    def set_preferred_subtitle_lang(self, lang_str: str, enabled: bool = True):
        """Définit la préférence globale de sous-titres et met à jour MPV."""
        self._preferred_subtitle_lang = lang_str or "off"
        self._subtitles_enabled = enabled and (self._preferred_subtitle_lang != "off")
        if self._player:
            try:
                if not self._subtitles_enabled:
                    self._player["sid"] = "no"
                    self._player["slang"] = "no"
                else:
                    self._player["slang"] = self._preferred_subtitle_lang
            except Exception:
                pass

    def set_hwdec(self, hwdec: str):
        """Définit le mode d'accélération matérielle ('auto', 'd3d11va', 'nvdec', 'no')."""
        if self._player:
            try:
                self._player["hwdec"] = hwdec
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
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
            try:
                self._player.command("quit", "0")
            except Exception:
                pass
            try:
                self._player.terminate()
            except Exception:
                pass
            self._player = None
