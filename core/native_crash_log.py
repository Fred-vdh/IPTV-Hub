"""
Journalisation des fautes natives Windows sans parcourir les trames Python.

Pourquoi ce module existe
-------------------------
``faulthandler.enable()`` installe sur Windows un gestionnaire d'exceptions
vectorisé (VEH) qui, à **chaque** exception SEH, vide les piles Python de *tous*
les threads via ``_Py_DumpTracebackThreads()``. Or libmpv -- la bibliothèque de
lecture utilisée par l'application -- lève en interne, sans conséquence et en
permanence, des exceptions SEH (code ``0xE24C4A02``) pendant ses appels d'API
(``mpv_wait_event``, ``mpv_get_property``, ``mpv_set_property``...).

Il en résultait deux problèmes observés en production :

1. Le journal ``iptv_errors.log`` devenait illisible : des dizaines de vidages
   par seconde, écrits simultanément par plusieurs threads, s'entremêlaient.
2. Le vidage lui-même était instable. ``_Py_DumpTracebackThreads()`` parcourt la
   liste des ``PyThreadState`` de l'interpréteur sans se protéger des threads
   qui naissent ou meurent au même instant (threads Qt, threads ``threading``,
   états temporaires fabriqués par les callbacks ctypes). Il lisait donc des
   trames incohérentes (``File ???, line 500 in ???``) puis finissait par violer
   l'accès **dans le code d'affichage des traces de CPython**.

   C'est exactement le crash constaté : journal d'événements Windows, module
   fautif ``python313.dll``, code ``0xc0000005``, décalages 0x2B62DC..0x2B62F3 --
   à l'intérieur de la plage de ``Python/traceback.c`` (juste après l'export
   ``_Py_DisplaySourceLine``), et ce **quelle que soit** l'action de
   l'utilisateur (appuis répétés sur « +10 s », passage à l'épisode suivant...).

Ce que fait ce module à la place
--------------------------------
* Il installe son propre VEH qui note **chaque** exception en une ligne (heure,
  thread, code, adresse fautive, module + décalage), **sans parcourir aucune
  trame Python** : impossible de crasher dans le journal.
* Il ne déclenche un vidage Python complet (``faulthandler.dump_traceback``) que
  pour les codes réellement mortels (violation d'accès, corruption de tas,
  débordement de pile, fast-fail...), c'est-à-dire quand la trace détaillée est
  utile et que le processus est de toute façon condamné.
* Il limite le bruit : chaque code bénin n'est écrit que quelques fois, puis
  résumé périodiquement.

Sur les systèmes non Windows, le module se contente d'activer ``faulthandler`` :
les signaux POSIX ne sont levés que pour une faute réelle, il n'y a donc aucun
des problèmes ci-dessus.
"""

from __future__ import annotations

import ctypes
import faulthandler
import os
import sys
import threading
from ctypes import wintypes
from datetime import datetime
from typing import Any, Dict, Optional

# --------------------------------------------------------------------------- #
# Classification des codes d'exception Windows
# --------------------------------------------------------------------------- #

#: Codes qui condamnent le processus : on capture une trace Python complète avant
#: que Windows ne termine le programme.
FATAL_EXCEPTION_CODES: Dict[int, str] = {
    0xC0000005: "ACCESS_VIOLATION",
    0xC0000006: "IN_PAGE_ERROR",
    0xC0000008: "INVALID_HANDLE",
    0xC000001D: "ILLEGAL_INSTRUCTION",
    0xC0000025: "NONCONTINUABLE_EXCEPTION",
    0xC000008C: "ARRAY_BOUNDS_EXCEEDED",
    0xC0000094: "INT_DIVIDE_BY_ZERO",
    0xC0000096: "PRIVILEGED_INSTRUCTION",
    0xC00000FD: "STACK_OVERFLOW",
    0xC0000374: "HEAP_CORRUPTION",
    0xC0000409: "STACK_BUFFER_OVERRUN",
    0xC0000602: "FAIL_FAST_EXCEPTION",
}

#: Codes non fatals, levés puis rattrapés en interne par les bibliothèques.
#: 0xE24C4A02 est notifié par libmpv pendant ses appels d'API : le nommer évite
#: de faire croire à une panne de l'application.
BENIGN_EXCEPTION_CODES: Dict[int, str] = {
    0xE24C4A02: "libmpv (levée et rattrapée en interne)",
    0xE06D7363: "exception C++ MSVC (rattrapée)",
    0x40010006: "OutputDebugString",
    0x406D1388: "renommage de thread",
    0x80000003: "point d'arrêt",
    0xE0434352: "exception .NET (rattrapée)",
}

#: Modes d'accès d'une violation d'accès (EXCEPTION_RECORD.ExceptionInformation[0]).
ACCESS_VIOLATION_OPERATIONS: Dict[int, str] = {
    0: "lecture",
    1: "écriture",
    8: "exécution",
}

#: Une exception bénigne n'est écrite en clair que MAX_REPORTED_LINES_PER_CODE
#: fois ; ensuite seule une ligne de synthèse est produite tous les SUMMARY_EVERY
#: occurrences (le journal reste exploitable).
MAX_REPORTED_LINES_PER_CODE = 5
SUMMARY_EVERY = 200

EXCEPTION_CONTINUE_SEARCH = 0

GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT = 0x00000002
GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS = 0x00000004


# --------------------------------------------------------------------------- #
# Structures Win32
# --------------------------------------------------------------------------- #

class _ExceptionRecord(ctypes.Structure):
    """EXCEPTION_RECORD (winnt.h)."""


_ExceptionRecord._fields_ = [
    ("ExceptionCode", wintypes.DWORD),
    ("ExceptionFlags", wintypes.DWORD),
    ("ExceptionRecord", ctypes.POINTER(_ExceptionRecord)),
    ("ExceptionAddress", ctypes.c_void_p),
    ("NumberParameters", wintypes.DWORD),
    ("ExceptionInformation", ctypes.c_size_t * 15),
]


class _ExceptionPointers(ctypes.Structure):
    """EXCEPTION_POINTERS (winnt.h)."""

    _fields_ = [
        ("ExceptionRecord", ctypes.POINTER(_ExceptionRecord)),
        ("ContextRecord", ctypes.c_void_p),
    ]


_VECTORED_HANDLER = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(_ExceptionPointers))

# --------------------------------------------------------------------------- #
# Localisation du module fautif
# --------------------------------------------------------------------------- #

def resolve_module(address: int) -> str:
    """Retourne ``"nom_module+0xoffset"`` pour une adresse de code, ou ``"?"``.

    N'utilise que des appels Win32 : aucune lecture des structures internes de
    CPython (contrairement au vidage de faulthandler qui parcourt les trames).
    """
    if not address:
        return "?"
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        module = wintypes.HMODULE()
        ok = kernel32.GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS
            | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            ctypes.c_void_p(address),
            ctypes.byref(module),
        )
        if not ok or not module.value:
            return "?"
        buffer = ctypes.create_unicode_buffer(1024)
        length = kernel32.GetModuleFileNameW(module, buffer, len(buffer))
        if not length:
            return "?"
        base = ctypes.cast(module, ctypes.c_void_p).value or 0
        name = os.path.basename(buffer.value) or "?"
        return f"{name}+0x{address - base:x}"
    except Exception:
        return "?"


def describe_exception_code(code: int) -> str:
    """Nom lisible d'un code d'exception Windows."""
    code &= 0xFFFFFFFF
    if code in FATAL_EXCEPTION_CODES:
        return FATAL_EXCEPTION_CODES[code]
    if code in BENIGN_EXCEPTION_CODES:
        return BENIGN_EXCEPTION_CODES[code]
    return "inconnu"


def is_fatal_exception_code(code: int) -> bool:
    """True si le code d'exception condamne le processus."""
    return (code & 0xFFFFFFFF) in FATAL_EXCEPTION_CODES


def format_exception_line(
    code: int,
    address: int,
    thread_id: int,
    access: Optional[str] = None,
    access_address: Optional[int] = None,
    total: int = 1,
    timestamp: Optional[str] = None,
) -> str:
    """Formate une ligne de journal (une exception = une ligne)."""
    parts = [
        timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        f"thread 0x{thread_id:x}",
        f"exception 0x{code & 0xFFFFFFFF:08X} ({describe_exception_code(code)})",
        f"adresse {resolve_module(address)}",
    ]
    if access is not None:
        parts.append(f"accès {access}")
    if access_address:
        parts.append(f"cible 0x{access_address:x}")
    if total > 1:
        parts.append(f"occurrence n°{total}")
    return " | ".join(parts) + "\n"

# --------------------------------------------------------------------------- #
# Journal
# --------------------------------------------------------------------------- #

class NativeCrashLogger:
    """VEH minimaliste : journalise sans jamais parcourir les trames Python."""

    def __init__(
        self,
        stream: Any,
        dump_all_threads: bool = True,
        owns_stream: bool = False,
    ):
        self._stream = stream
        self._dump_all_threads = dump_all_threads
        #: True si le flux a été ouvert par ce module (il doit alors le refermer).
        self._owns_stream = owns_stream
        self._counts: Dict[int, int] = {}
        self._handler: Optional[Any] = None
        self._handle: int = 0
        self._closed = False

    # -- cycle de vie ------------------------------------------------------

    @property
    def installed(self) -> bool:
        return bool(self._handle)

    @property
    def counts(self) -> Dict[int, int]:
        """Nombre d'exceptions vues, par code (diagnostic / tests)."""
        return dict(self._counts)

    def install(self) -> "NativeCrashLogger":
        """Enregistre le gestionnaire d'exceptions vectorisé (Windows uniquement)."""
        if sys.platform != "win32":
            return self
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.AddVectoredExceptionHandler.argtypes = [
                wintypes.ULONG,
                _VECTORED_HANDLER,
            ]
            kernel32.AddVectoredExceptionHandler.restype = ctypes.c_void_p
            self._handler = _VECTORED_HANDLER(self._on_exception)
            self._handle = kernel32.AddVectoredExceptionHandler(1, self._handler) or 0
        except Exception:
            self._handle = 0
        return self

    def close(self) -> None:
        """Retire le gestionnaire (fin de vie de l'application / tests)."""
        if self._closed:
            return
        self._closed = True
        if sys.platform == "win32" and self._handle:
            try:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.RemoveVectoredExceptionHandler.argtypes = [ctypes.c_void_p]
                kernel32.RemoveVectoredExceptionHandler.restype = wintypes.ULONG
                kernel32.RemoveVectoredExceptionHandler(ctypes.c_void_p(self._handle))
            except Exception:
                pass
        self._handle = 0
        self._handler = None
        try:
            self._stream.flush()
        except Exception:
            pass
        if self._owns_stream:
            try:
                self._stream.close()
            except Exception:
                pass

    # -- écriture ----------------------------------------------------------

    def _write(self, text: str) -> None:
        try:
            self._stream.write(text)
            self._stream.flush()
        except Exception:
            pass
        try:
            if sys.stderr is not None:
                sys.stderr.write(text)
        except Exception:
            pass

    def log_session_start(self) -> None:
        self._write(
            f"\n===== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} : surveillance "
            f"des fautes natives (VEH, processus {os.getpid()}) =====\n"
        )

    # -- gestionnaire ------------------------------------------------------

    def _on_exception(self, info_ptr) -> int:
        """Appelé par Windows pour chaque exception SEH. Ne lève jamais."""
        try:
            record = info_ptr.contents.ExceptionRecord.contents
            code = int(record.ExceptionCode) & 0xFFFFFFFF
            address = int(record.ExceptionAddress or 0)
            access = None
            access_address = None
            if code == 0xC0000005 and record.NumberParameters >= 2:
                operation = int(record.ExceptionInformation[0])
                access = ACCESS_VIOLATION_OPERATIONS.get(operation, str(operation))
                access_address = int(record.ExceptionInformation[1])

            total = self._counts.get(code, 0) + 1
            self._counts[code] = total

            if is_fatal_exception_code(code):
                self._write(
                    format_exception_line(
                        code, address, threading.get_ident(), access, access_address, total
                    )
                )
                self._dump_python_traceback(code)
            elif total <= MAX_REPORTED_LINES_PER_CODE or total % SUMMARY_EVERY == 0:
                self._write(
                    format_exception_line(
                        code, address, threading.get_ident(), access, access_address, total
                    )
                )
        except Exception:
            # Un journal de crash ne doit jamais faire tomber l'application.
            pass
        # On n'intercepte rien : le mécanisme normal de Windows se poursuit.
        return EXCEPTION_CONTINUE_SEARCH

    def _dump_python_traceback(self, code: int) -> None:
        """Vidage Python complet, réservé aux fautes réellement mortelles.

        ``faulthandler.dump_traceback`` écrit via le descripteur du flux : celui-ci
        doit donc être un vrai fichier (c'est le cas en production, où l'on partage
        le flux de ``iptv_errors.log``).
        """
        try:
            self._write(f"----- trace Python complète (code 0x{code:08X}) -----\n")
            self._stream.flush()
            faulthandler.dump_traceback(
                file=self._stream,
                all_threads=self._dump_all_threads,
            )
            self._stream.flush()
            self._write("----- fin de trace -----\n")
        except Exception as exc:
            try:
                self._stream.write(f"(trace Python indisponible : {exc})\n")
                self._stream.flush()
            except Exception:
                pass

_LOGGER: Optional[NativeCrashLogger] = None


def install_native_crash_log(
    log_path: Optional[str] = None,
    stream: Any = None,
    dump_all_threads: bool = True,
) -> Optional[NativeCrashLogger]:
    """Remplace ``faulthandler.enable()`` par une surveillance sûre des fautes.

    :param log_path: fichier de journal ouvert en ajout si ``stream`` est absent.
    :param stream: flux déjà ouvert (partagé avec le reste du journal d'erreurs).
    :param dump_all_threads: transmis à ``faulthandler.dump_traceback``, pour les
        fautes mortelles uniquement.
    :return: l'instance installée, ou ``None`` si la mise en place a échoué.
    """
    global _LOGGER

    if sys.platform != "win32":
        # POSIX : les signaux ne sont émis que pour une vraie faute, le vidage de
        # faulthandler n'y a donc pas les défauts décrits en tête de module.
        try:
            faulthandler.enable(file=stream, all_threads=dump_all_threads)
        except Exception:
            pass
        return None

    if stream is None:
        if not log_path:
            return None
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            stream = open(log_path, "a", encoding="utf-8", buffering=1)
            owns_stream = True
        except Exception:
            return None
    else:
        owns_stream = False

    if _LOGGER is not None:
        _LOGGER.close()

    logger = NativeCrashLogger(
        stream, dump_all_threads=dump_all_threads, owns_stream=owns_stream
    )
    logger.install()
    if logger.installed:
        logger.log_session_start()
        _LOGGER = logger
    return logger


def last_session_counts() -> Dict[int, int]:
    """Nombre d'occurrences par code depuis l'installation (tests / diagnostics)."""
    if _LOGGER is None:
        return {}
    return _LOGGER.counts



