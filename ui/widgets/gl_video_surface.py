"""
Surface de rendu vidéo basée sur QOpenGLWidget et l'API de rendu OpenGL de libmpv
(mpv_render_context).

Avantages par rapport au rendu natif (wid) :
  * La vidéo est composée par Qt dans le QOpenGLWidget : l'OSD (contrôles, overlays)
    est un simple widget enfant qui s'affiche proprement par-dessus la vidéo.
  * Aucune fenêtre native séparée, aucun artefact de compositing (DWM, z-order).
  * Coins arrondis, effets visuels Qt et transitions possibles sur la vidéo.

Contraintes :
  * Toutes les opérations de rendu doivent se faire avec le contexte OpenGL
    'current'. QOpenGLWidget garantit cela dans initializeGL()/paintGL()/
    resizeGL() et via makeCurrent().
  * Le callback de mise à jour de libmpv est appelé depuis un thread interne à
    libmpv : il ne doit pas manipuler OpenGL ni l'UI. On se contente donc
    d'invalider le widget via un signal Qt (thread-safe) qui déclenche un repaint.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QOpenGLContext
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from core.mpv_render import MPVOpenGLRenderContext


class GLVideoSurface(QOpenGLWidget):
    """
    Widget OpenGL affichant la vidéo rendue par libmpv.

    Il faut lui fournir le handle brut mpv (mpv_handle*) après l'initialisation
    de libmpv. Le contexte de rendu est créé à ce moment-là (le contexte OpenGL
    de Qt étant déjà validé).
    """

    # Émis depuis le thread de libmpv -> traité dans le thread GUI (queued).
    _redraw_requested = pyqtSignal()

    def __init__(self, parent: Optional[QOpenGLWidget] = None):
        super().__init__(parent)
        self.setObjectName("videoSurface")
        self.setStyleSheet("background-color: #000000;")
        # WA_OpaquePaintEvent : le widget peint TOUTE sa surface (la vidéo), donc
        # Qt ne doit pas effacer le fond au préalable. Sans cet attribut, chaque
        # recomposition (ex. affichage/masquage de l'OSD) présente une frame de
        # fond noir avant que paintGL ne re-rende la vidéo -> flash noir.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._render_ctx: Optional[MPVOpenGLRenderContext] = None
        self._mpv_handle: Optional[int] = None
        self._gl_context: Optional[QOpenGLContext] = None
        self._gl_ready: bool = False
        self._has_frame: bool = False
        self._is_rendering_active: bool = False

        # Le callback de libmpv (thread interne) est relayé vers le thread GUI
        # via un signal Qt en file d'attente (thread-safe).
        self._redraw_requested.connect(self._on_redraw_requested, Qt.ConnectionType.QueuedConnection)

        # Repaint périodique tant que la lecture est active : garantit que chaque
        # composition du widget redessine la dernière frame vidéo (évite les
        # flashs noirs intermittents).
        self._fallback_timer = QTimer(self)
        self._fallback_timer.setInterval(33)  # ~30 fps
        self._fallback_timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------ setup

    def set_mpv_handle(self, mpv_handle: int):
        """
        Associe le handle brut mpv (mpv.MPV().handle) à cette surface et crée le
        contexte de rendu OpenGL de libmpv.

        À appeler une fois la vidéo prête à être rendue. Si le contexte OpenGL
        n'est pas encore initialisé (before initializeGL), l'opération est
        différée au prochain initializeGL().
        """
        self._mpv_handle = int(mpv_handle) if mpv_handle else None
        if self._gl_ready and self._mpv_handle:
            self._create_render_context()

    def _create_render_context(self):
        if self._render_ctx is not None or not self._mpv_handle:
            return

        def _get_proc_address(name) -> int:
            ctx = QOpenGLContext.currentContext()
            if ctx is None:
                return 0
            # QOpenGLContext.getProcAddress exige un QByteArray/bytes, pas une str.
            if isinstance(name, str):
                name_bytes = name.encode("ascii")
            else:
                name_bytes = bytes(name)
            try:
                fn = ctx.getProcAddress(name_bytes)
                return int(fn) if fn is not None else 0
            except Exception:
                return 0

        self.makeCurrent()
        try:
            self._gl_context = QOpenGLContext.currentContext()
            self._render_ctx = MPVOpenGLRenderContext(self._mpv_handle, _get_proc_address)
            self._render_ctx.update_callback = self._on_mpv_update
        except Exception as e:
            print(f"[GLVideoSurface] Echec de creation du contexte de rendu OpenGL libmpv : {e}")
            self._render_ctx = None
        finally:
            self.doneCurrent()

    # -------------------------------------------------------- OpenGL callbacks

    def initializeGL(self):
        self._gl_ready = True
        curr_ctx = QOpenGLContext.currentContext()
        # Si le widget a été déplacé dans un autre conteneur (ex: détachement film -> série),
        # Qt a recréé un nouveau contexte OpenGL. On doit libérer l'ancien contexte MPV
        # et le recréer pour ce nouveau contexte OpenGL afin d'éviter tout conflit / saccade.
        if self._render_ctx is not None and self._gl_context != curr_ctx:
            try:
                self._render_ctx.free()
            except Exception:
                pass
            self._render_ctx = None

        self._gl_context = curr_ctx
        self._create_render_context()

    def paintGL(self):
        ctx = self._render_ctx
        if ctx is None:
            # Pas encore de contexte de rendu : fond noir.
            return

        ratio = self.devicePixelRatioF() or 1.0
        w = max(1, int(self.width() * ratio))
        h = max(1, int(self.height() * ratio))
        fbo_id = int(self.defaultFramebufferObject())

        # IMPORTANT : dans paintGL(), le contexte OpenGL de Qt est DÉJÀ current.
        # Il ne faut PAS appeler makeCurrent()/doneCurrent() ici, sous peine de
        # perturber l'état du contexte géré par Qt (voire de provoquer un crash
        # natif dans libmpv / le pilote).
        try:
            # Rien à rendre si aucun média n'est actif et qu'on n'a jamais eu de frame.
            if not self._is_rendering_active and not self._has_frame:
                return
            # Signal à libmpv qu'on va consommer la frame courante.
            ctx.update()
            # On rend SYSTÉMATIQUEMENT la dernière frame connue de libmpv : Qt
            # efface le framebuffer au début de paintGL, il faut donc re-rendre la
            # frame à chaque composition pour éviter les flashs noirs.
            #
            # flip_y=True : l'axe Y d'OpenGL est inversé par rapport à l'image ;
            # sans cela, la vidéo s'affiche retournée verticalement (haut <-> bas).
            if ctx.render(fbo_id, w, h, flip_y=True):
                self._has_frame = True
        except Exception as e:
            print(f"[GLVideoSurface] erreur paintGL : {e}")

    def resizeGL(self, w: int, h: int):
        # Rien de spécial : paintGL lit les dimensions courantes.
        pass

    def mousePressEvent(self, event):
        event.accept()
        super().mousePressEvent(event)

    # -------------------------------------------------------- rendu / redraw

    def set_rendering_active(self, active: bool):
        """Active/désactive le rendu vidéo (mis à False à l'arrêt de la lecture)."""
        self._is_rendering_active = bool(active)
        self._has_frame = False
        if active:
            self._fallback_timer.start()
        else:
            self._fallback_timer.stop()
            self.update()

    def _on_mpv_update(self):
        """Callback appelé par libmpv (thread interne). On notifie le thread GUI."""
        self._redraw_requested.emit()

    def _on_redraw_requested(self):
        self.update()

    def _tick(self):
        """Repaint périodique tant que le rendu est actif.

        On repeint systématiquement (même sans nouvelle frame) afin que chaque
        composition du widget redessine la dernière frame vidéo : c'est ce qui
        évite les flashs noirs intermittents pendant la lecture.
        """
        if self._is_rendering_active and self._render_ctx is not None:
            self.update()

    # ------------------------------------------------------------- clean up

    def cleanup_render_context(self):
        self._fallback_timer.stop()
        if self._render_ctx is not None:
            self.makeCurrent()
            try:
                self._render_ctx.free()
            except Exception as e:
                print(f"[GLVideoSurface] erreur de nettoyage : {e}")
            finally:
                self.doneCurrent()
                self._render_ctx = None
        self._mpv_handle = None
        self._gl_context = None
        self._has_frame = False
        self._is_rendering_active = False
