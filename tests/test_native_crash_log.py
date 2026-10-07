"""
Tests du journal de fautes natives (``core/native_crash_log.py``).

Pourquoi ces tests existent
---------------------------
L'application s'appuyait sur ``faulthandler.enable()``. Sur Windows, ce dernier
vide les piles Python de *tous* les threads à **chaque** exception SEH ; or
libmpv en lève en permanence (``0xE24C4A02``) pendant ses appels d'API
(``mpv_wait_event``, ``mpv_get_property``, ``mpv_set_property``...). Le vidage
lisait alors des trames incohérentes (``File ???, line 500 in ???``) puis
finissait par violer l'accès **dans python313.dll**, au cœur du code d'affichage
des traces de CPython : journal d'événements Windows du 05/10/2026, code
``0xc0000005`` aux décalages 0x2B62DC / 0x2B62EF / 0x2B62F3 (et ce pour les deux
builds comme pour les deux scénarios utilisateur : « +10 s » répété, passage à
l'épisode suivant).

Ces tests verrouillent le comportement du remplaçant :

* une exception bénigne n'écrit qu'une ligne, **sans jamais vider les trames
  Python** ;
* une exception mortelle écrit la ligne **et** une trace Python complète ;
* chaque ligne nomme le module fautif (``module+0x…``) ;
* le nombre de lignes par code est borné : le journal reste exploitable ;
* le gestionnaire ne modifie jamais le déroulement de l'exception.
"""

import ctypes
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.native_crash_log import (  # noqa: E402
    EXCEPTION_CONTINUE_SEARCH,
    FATAL_EXCEPTION_CODES,
    MAX_REPORTED_LINES_PER_CODE,
    NativeCrashLogger,
    _ExceptionPointers,
    _ExceptionRecord,
    describe_exception_code,
    format_exception_line,
    install_native_crash_log,
    is_fatal_exception_code,
    resolve_module,
)

#: Exception levée en boucle par libmpv pendant ses appels d'API.
LIBMPV_INTERNAL_CODE = 0xE24C4A02
ACCESS_VIOLATION_CODE = 0xC0000005
STACK_OVERFLOW_CODE = 0xC00000FD

FATAL_MARKER = "trace Python complète"


def _make_exception_pointers(code, address=0, information=None):
    """Fabrique un EXCEPTION_POINTERS tel que Windows le passe au VEH."""
    record = _ExceptionRecord()
    record.ExceptionCode = code
    record.ExceptionFlags = 0
    record.ExceptionRecord = ctypes.POINTER(_ExceptionRecord)()
    record.ExceptionAddress = ctypes.c_void_p(address)
    parameters = list(information or [])
    record.NumberParameters = len(parameters)
    for index, value in enumerate(parameters):
        record.ExceptionInformation[index] = value
    pointers = _ExceptionPointers()
    pointers.ExceptionRecord = ctypes.pointer(record)
    pointers.ContextRecord = None
    # Le record doit survivre au retour (pointeur brut) : on le renvoie.
    return record, ctypes.pointer(pointers)


class TestExceptionCodeDescription(unittest.TestCase):
    def test_libmpv_internal_code_is_described_and_not_fatal(self):
        self.assertIn("libmpv", describe_exception_code(LIBMPV_INTERNAL_CODE))
        self.assertFalse(is_fatal_exception_code(LIBMPV_INTERNAL_CODE))

    def test_access_violation_is_fatal_and_described(self):
        self.assertTrue(is_fatal_exception_code(ACCESS_VIOLATION_CODE))
        self.assertEqual(
            describe_exception_code(ACCESS_VIOLATION_CODE), "ACCESS_VIOLATION"
        )

    def test_unknown_code_is_not_fatal(self):
        self.assertFalse(is_fatal_exception_code(0x12345678))
        self.assertEqual(describe_exception_code(0x12345678), "inconnu")

    def test_every_declared_fatal_code_is_reported_as_fatal(self):
        for code in FATAL_EXCEPTION_CODES:
            self.assertTrue(is_fatal_exception_code(code), hex(code))


class TestModuleResolution(unittest.TestCase):
    def test_resolve_module_names_the_owning_dll(self):
        kernel32 = ctypes.WinDLL("kernel32")
        address = ctypes.cast(kernel32.GetModuleHandleW, ctypes.c_void_p).value
        resolved = resolve_module(address)
        self.assertTrue(
            resolved.lower().startswith("kernel32.dll+0x"),
            f"résolution inattendue : {resolved}",
        )

    def test_resolve_module_tolerates_zero_address(self):
        self.assertEqual(resolve_module(0), "?")


class TestExceptionLineFormat(unittest.TestCase):
    def test_line_contains_time_thread_code_and_module(self):
        line = format_exception_line(
            ACCESS_VIOLATION_CODE,
            address=0,
            thread_id=0x2B20,
            access="écriture",
            access_address=0xDEADBEEF,
            total=3,
            timestamp="2026-10-05 19:48:32",
        )
        self.assertIn("2026-10-05 19:48:32", line)
        self.assertIn("thread 0x2b20", line)
        self.assertIn("0xC0000005", line)
        self.assertIn("ACCESS_VIOLATION", line)
        self.assertIn("accès écriture", line)
        self.assertIn("cible 0xdeadbeef", line)
        self.assertIn("occurrence n°3", line)
        self.assertTrue(line.endswith("\n"))


class TestVectoredHandlerBehaviour(unittest.TestCase):
    """Le gestionnaire journalise, sans jamais toucher aux trames Python."""

    def _logger(self):
        """Journal sur un VRAI fichier : le vidage Python exige un descripteur."""
        handle = tempfile.NamedTemporaryFile(
            "w+", encoding="utf-8", suffix=".log", delete=False
        )

        def _cleanup():
            try:
                handle.close()
            except Exception:
                pass
            try:
                os.unlink(handle.name)
            except Exception:
                pass

        self.addCleanup(_cleanup)
        logger = NativeCrashLogger(handle)
        self.addCleanup(logger.close)
        return logger, handle

    @staticmethod
    def _read(handle) -> str:
        handle.flush()
        return Path(handle.name).read_text(encoding="utf-8")

    def test_benign_exception_writes_one_line_without_python_traceback(self):
        logger, handle = self._logger()
        record, pointers = _make_exception_pointers(LIBMPV_INTERNAL_CODE)
        with patch("sys.stderr", io.StringIO()):
            result = logger._on_exception(pointers)
        del record

        output = self._read(handle)
        self.assertEqual(result, EXCEPTION_CONTINUE_SEARCH)
        self.assertIn("0xE24C4A02", output)
        self.assertIn("libmpv", output)
        self.assertNotIn(FATAL_MARKER, output)
        self.assertEqual(output.count("\n"), 1, "une exception bénigne = une ligne")

    def test_benign_exception_is_rate_limited(self):
        logger, handle = self._logger()
        occurrences = MAX_REPORTED_LINES_PER_CODE + 25
        with patch("sys.stderr", io.StringIO()):
            for _ in range(occurrences):
                record, pointers = _make_exception_pointers(LIBMPV_INTERNAL_CODE)
                logger._on_exception(pointers)
                del record

        self.assertEqual(
            self._read(handle).count("\n"), MAX_REPORTED_LINES_PER_CODE
        )
        self.assertEqual(logger.counts[LIBMPV_INTERNAL_CODE], occurrences)

    def test_access_violation_writes_line_and_python_traceback(self):
        logger, handle = self._logger()
        record, pointers = _make_exception_pointers(
            ACCESS_VIOLATION_CODE, information=[1, 0x11223344]
        )
        with patch("sys.stderr", io.StringIO()):
            logger._on_exception(pointers)
        del record

        output = self._read(handle)
        self.assertIn("ACCESS_VIOLATION", output)
        self.assertIn("accès écriture", output)
        self.assertIn("cible 0x11223344", output)
        self.assertIn(FATAL_MARKER, output)
        # La trace Python produite est bien celle du test en cours.
        self.assertIn("test_access_violation_writes_line_and_python_traceback", output)

    def test_fatal_code_is_never_rate_limited(self):
        logger, handle = self._logger()
        with patch("sys.stderr", io.StringIO()):
            for _ in range(3):
                record, pointers = _make_exception_pointers(STACK_OVERFLOW_CODE)
                logger._on_exception(pointers)
                del record

        self.assertEqual(self._read(handle).count(FATAL_MARKER), 3)

    def test_handler_survives_malformed_exception_pointers(self):
        """Un journal ne doit JAMAIS faire tomber l'application."""
        logger, handle = self._logger()
        pointers = ctypes.pointer(_ExceptionPointers())  # ExceptionRecord NULL
        with patch("sys.stderr", io.StringIO()):
            result = logger._on_exception(pointers)

        self.assertEqual(result, EXCEPTION_CONTINUE_SEARCH)
        self.assertEqual(self._read(handle), "")


@unittest.skipUnless(sys.platform == "win32", "VEH disponible sous Windows uniquement")
class TestInstallation(unittest.TestCase):
    def test_install_creates_log_dir_and_can_be_closed_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "sous-dossier", "errors.log")
            logger = install_native_crash_log(log_path)
            self.assertIsNotNone(logger)
            self.assertTrue(logger.installed)
            self.addCleanup(logger.close)

            logger.close()
            self.assertFalse(logger.installed)
            logger.close()  # idempotent

            content = Path(log_path).read_text(encoding="utf-8")
            self.assertIn("surveillance des fautes natives", content)


if __name__ == "__main__":
    unittest.main()

