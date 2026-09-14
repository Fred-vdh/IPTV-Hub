"""
Wrapper ctypes minimal et autonome de l'API de rendu OpenGL de libmpv
(mpv_render_context / render.h + render_gl.h).

Permet de dessiner la vidéo MPV directement dans le framebuffer d'un contexte
OpenGL, sans créer de fenêtre native séparée. Conçu pour s'intégrer avec un
QOpenGLWidget Qt (ou toute autre surface GL).

L'API est documentée dans :
    lib/include/mpv/render.h
    lib/include/mpv/render_gl.h

Notes importantes :
  * MPV_RENDER_PARAM_ADVANCED_CONTROL n'est PAS activé (comportement par défaut
    sûr) : le callback de mise à jour est facultatif et `mpv_render_context_update()`
    n'est pas obligatoire après chaque callback. Cela évite la nécessité de gérer
    un thread de rendu dédié et les risques de deadlock associés.
  * Toutes les fonctions mpv_render_* doivent être appelées avec le MÊME contexte
    OpenGL "current" que celui utilisé lors de mpv_render_context_create().
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import (
    CFUNCTYPE,
    POINTER,
    Structure,
    byref,
    c_char_p,
    c_int,
    c_uint64,
    c_void_p,
    cast,
)
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Chargement de libmpv
# ---------------------------------------------------------------------------

import ctypes.util


def _get_lib_names() -> list[str]:
    """Retourne la liste des noms possibles pour la bibliothèque libmpv selon le système d'exploitation."""
    if sys.platform == "win32":
        return ["libmpv-2.dll", "mpv-2.dll", "libmpv-1.dll", "mpv-1.dll"]
    if sys.platform == "darwin":
        names = ["libmpv.2.dylib", "libmpv.dylib", "libmpv.1.dylib"]
    else:
        # Linux & BSD
        names = ["libmpv.so.2", "libmpv.so.1", "libmpv.so"]

    # Tentative avec ctypes.util.find_library pour trouver le chemin système
    found = ctypes.util.find_library("mpv")
    if found and found not in names:
        names.insert(0, found)
    return names


def _load_libmpv() -> ctypes.CDLL:
    """Charge libmpv en privilégiant le dossier ./lib local, puis les chemins système."""
    lib_names = _get_lib_names()
    candidates = []

    # 1. Dossier "lib" du projet (ou bundle PyInstaller)
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "lib")
            candidates.append(Path(meipass))
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "lib")
        candidates.append(exe_dir)
    else:
        candidates.append(Path(__file__).resolve().parent.parent / "lib")

    for folder in candidates:
        if not folder or not folder.exists():
            continue
        for name in lib_names:
            candidate = folder / name
            if candidate.exists():
                try:
                    return ctypes.CDLL(str(candidate))
                except OSError:
                    continue

    # 2. Fallback : laisser le loader dynamique système résoudre
    for name in lib_names:
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue

    raise RuntimeError(
        "libmpv introuvable sur votre système.\n"
        "Sous Windows : vérifiez la présence de 'libmpv-2.dll' dans le dossier 'lib'.\n"
        "Sous Linux : installez libmpv avec 'sudo apt install libmpv2 libmpv-dev' (Ubuntu/Debian) "
        "ou 'sudo pacman -S mpv' (Arch) ou 'sudo dnf install mpv-libs-devel' (Fedora)."
    )


_libmpv = _load_libmpv()


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# mpv_render_param_type
MPV_RENDER_PARAM_INVALID = 0
MPV_RENDER_PARAM_API_TYPE = 1
MPV_RENDER_PARAM_OPENGL_INIT_PARAMS = 2
MPV_RENDER_PARAM_OPENGL_FBO = 3
MPV_RENDER_PARAM_FLIP_Y = 4
MPV_RENDER_PARAM_DEPTH = 5
MPV_RENDER_PARAM_ADVANCED_CONTROL = 10

MPV_RENDER_API_TYPE_OPENGL = b"opengl"

# mpv_render_update_flag
MPV_RENDER_UPDATE_FRAME = 1 << 0

# Codes d'erreur libmpv (échantillon utile)
MPV_ERROR_SUCCESS = 0
MPV_ERROR_UNSUPPORTED = -12
MPV_ERROR_NOT_IMPLEMENTED = -13
MPV_ERROR_INVALID_PARAMETER = -7

ERROR_MESSAGES = {
    MPV_ERROR_UNSUPPORTED: "OpenGL non supporté (version/extension manquante).",
    MPV_ERROR_NOT_IMPLEMENTED: "Backend de rendu non implémenté dans cette libmpv.",
    MPV_ERROR_INVALID_PARAMETER: "Paramètre de rendu invalide.",
}


# ---------------------------------------------------------------------------
# Structures C
# ---------------------------------------------------------------------------

class mpv_render_param(Structure):
    _fields_ = [("type", c_int), ("data", c_void_p)]


# void *(*get_proc_address)(void *ctx, const char *name)
GET_PROC_ADDRESS_FN = CFUNCTYPE(c_void_p, c_void_p, c_char_p)


class mpv_opengl_init_params(Structure):
    # NB : cette version de l'en-tête ne contient QUE ces 2 champs.
    _fields_ = [
        ("get_proc_address", GET_PROC_ADDRESS_FN),
        ("get_proc_address_ctx", c_void_p),
    ]


class mpv_opengl_fbo(Structure):
    _fields_ = [
        ("fbo", c_int),
        ("w", c_int),
        ("h", c_int),
        ("internal_format", c_int),
    ]


# void (*mpv_render_update_fn)(void *cb_ctx)
RENDER_UPDATE_FN = CFUNCTYPE(None, c_void_p)


# ---------------------------------------------------------------------------
# Prototypes des fonctions
# ---------------------------------------------------------------------------

def _prototype(name: str, argtypes, restype):
    fn = getattr(_libmpv, name)
    fn.argtypes = argtypes
    fn.restype = restype
    return fn


# Handle opaque mpv_handle* : on récupère le handle brut via mpv.MPV().handle
_mpv_render_context_create = _prototype(
    "mpv_render_context_create",
    [POINTER(c_void_p), c_void_p, POINTER(mpv_render_param)],
    c_int,
)
_mpv_render_context_set_update_callback = _prototype(
    "mpv_render_context_set_update_callback",
    [c_void_p, RENDER_UPDATE_FN, c_void_p],
    None,
)
_mpv_render_context_update = _prototype(
    "mpv_render_context_update",
    [c_void_p],
    c_uint64,
)
_mpv_render_context_render = _prototype(
    "mpv_render_context_render",
    [c_void_p, POINTER(mpv_render_param)],
    c_int,
)
_mpv_render_context_report_swap = _prototype(
    "mpv_render_context_report_swap",
    [c_void_p],
    None,
)
_mpv_render_context_free = _prototype(
    "mpv_render_context_free",
    [c_void_p],
    None,
)


# ---------------------------------------------------------------------------
# Contexte de rendu
# ---------------------------------------------------------------------------

class MPVOpenGLRenderContext:
    """
    Encapsule un mpv_render_context pour le backend OpenGL.

    Cycle de vie typique (dans un QOpenGLWidget) :

        # initializeGL (contexte GL current)
        self.render_ctx = MPVOpenGLRenderContext(mpv_handle, get_proc_address)
        self.render_ctx.update_callback = self._on_mpv_needs_redraw

        # paintGL (contexte GL current)
        if self.render_ctx.update():
            self.render_ctx.render(fbo_id, width, height, flip_y=False)

        # avant destruction / terminate
        self.render_ctx.free()
    """

    def __init__(
        self,
        mpv_handle: int,
        get_proc_address: Callable[[str], int],
        advanced_control: bool = False,
    ):
        """
        :param mpv_handle: handle brut mpv_handle* (mpv.MPV().handle).
        :param get_proc_address: fonction qui prend un nom de fonction GL (str)
                                 et renvoie son adresse (int). En général
                                 QOpenGLContext.currentContext().getProcAddress.
        :param advanced_control: active MPV_RENDER_PARAM_ADVANCED_CONTROL
                                 (déconseillé sauf maîtrise du threading).
        """
        self._handle: Optional[c_void_p] = None
        self._ctx = mpv_handle
        self._advanced = advanced_control

        # On garde des références fortes sur les objets ctypes exposés à MPV.
        self._get_proc_address_cb = self._make_proc_address_cb(get_proc_address)
        self._update_cb: Optional[RENDER_UPDATE_FN] = None
        self._on_update: Optional[Callable[[], None]] = None

        self._create_context()

    # -- construction --------------------------------------------------------

    @staticmethod
    def _make_proc_address_cb(fn: Callable[[str], int]) -> GET_PROC_ADDRESS_FN:
        def _cb(_ctx, name):  # noqa: ANN001
            try:
                return int(fn(name.decode("utf-8")))
            except Exception:
                return 0

        return GET_PROC_ADDRESS_FN(_cb)

    def _create_context(self):
        gl_init = mpv_opengl_init_params()
        gl_init.get_proc_address = self._get_proc_address_cb
        gl_init.get_proc_address_ctx = None

        adv = c_int(1 if self._advanced else 0)

        params = (mpv_render_param * 4)()
        params[0].type = MPV_RENDER_PARAM_API_TYPE
        params[0].data = cast(c_char_p(MPV_RENDER_API_TYPE_OPENGL), c_void_p)
        params[1].type = MPV_RENDER_PARAM_OPENGL_INIT_PARAMS
        params[1].data = cast(byref(gl_init), c_void_p)
        if self._advanced:
            params[2].type = MPV_RENDER_PARAM_ADVANCED_CONTROL
            params[2].data = cast(byref(adv), c_void_p)
            params[3].type = MPV_RENDER_PARAM_INVALID
            params[3].data = None
        else:
            params[2].type = MPV_RENDER_PARAM_INVALID
            params[2].data = None

        handle = c_void_p()
        ret = _mpv_render_context_create(byref(handle), c_void_p(self._ctx), params)
        if ret < 0:
            msg = ERROR_MESSAGES.get(ret, f"code {ret}")
            raise RuntimeError(f"mpv_render_context_create a échoué : {msg}")

        self._handle = handle

    # -- callback de mise à jour --------------------------------------------

    @property
    def update_callback(self) -> Optional[Callable[[], None]]:
        return self._on_update

    @update_callback.setter
    def update_callback(self, fn: Optional[Callable[[], None]]):
        """
        Enregistre un callback SANS ARGUMENT appelé par MPV depuis son thread
        interne quand une nouvelle frame est prête.

        ATTENTION : ce callback est appelé depuis un thread libmpv. Il ne doit
        PAS appeler d'API MPV, et pour Qt, il ne doit pas manipuler l'UI
        directement. Utilisez un signal Qt (thread-safe) ou postez un événement.
        """
        self._on_update = fn

        def _dispatch(_userdata):  # noqa: ANN001
            cb = self._on_update
            if cb is not None:
                cb()

        self._update_cb = RENDER_UPDATE_FN(_dispatch)
        _mpv_render_context_set_update_callback(
            self._handle, self._update_cb, None
        )

    # -- rendu ---------------------------------------------------------------

    def update(self) -> bool:
        """Appelle mpv_render_context_update(). Retourne True si une frame doit
        être rendue (MPV_RENDER_UPDATE_FRAME)."""
        if not self._handle:
            return False
        return bool(_mpv_render_context_update(self._handle) & MPV_RENDER_UPDATE_FRAME)

    def render(
        self,
        fbo_id: int,
        width: int,
        height: int,
        flip_y: bool = False,
        internal_format: int = 0,
    ) -> bool:
        """
        Rend la frame courante dans le FBO cible. Le contexte OpenGL
        correspondant DOIT être 'current' dans le thread appelant.
        """
        if not self._handle:
            return False

        fbo = mpv_opengl_fbo()
        fbo.fbo = int(fbo_id)
        fbo.w = int(width)
        fbo.h = int(height)
        fbo.internal_format = int(internal_format)

        flip = c_int(1 if flip_y else 0)

        params = (mpv_render_param * 3)()
        params[0].type = MPV_RENDER_PARAM_OPENGL_FBO
        params[0].data = cast(byref(fbo), c_void_p)
        params[1].type = MPV_RENDER_PARAM_FLIP_Y
        params[1].data = cast(byref(flip), c_void_p)
        params[2].type = MPV_RENDER_PARAM_INVALID
        params[2].data = None

        ret = _mpv_render_context_render(self._handle, params)
        return ret >= 0

    def report_swap(self):
        if self._handle:
            _mpv_render_context_report_swap(self._handle)

    # -- destruction ---------------------------------------------------------

    def free(self):
        if self._handle:
            # On retire le callback avant de libérer pour éviter tout appel tardif.
            self._update_cb = None
            self._on_update = None
            try:
                _mpv_render_context_free(self._handle)
            finally:
                self._handle = None

    def __del__(self):
        try:
            self.free()
        except Exception:
            pass
