"""Stabilität bei mehreren gleichzeitigen Benutzern: OCR-Begrenzung und DB-Einstellungen."""

import threading
import time

from app.core import database
from app.services import parsers


def test_dokumente_lesen_hoechstens_zwei_gleichzeitig(monkeypatch):
    """Ein langer Scan darf nicht alle Server-Threads und die CPU belegen."""
    laufend = 0
    hoechstens = 0
    zaehler_lock = threading.Lock()

    def langsam_lesen(pdf_data, language):
        nonlocal laufend, hoechstens
        with zaehler_lock:
            laufend += 1
            hoechstens = max(hoechstens, laufend)
        time.sleep(0.1)
        with zaehler_lock:
            laufend -= 1
        raise parsers.UnknownLayoutError("test")

    monkeypatch.setattr(parsers, "read_document", langsam_lesen)

    def hochladen():
        try:
            parsers.parse_document(b"%PDF")
        except parsers.UnknownLayoutError:
            pass

    threads = [threading.Thread(target=hochladen) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert hoechstens == parsers.MAX_PARALLELE_DOKUMENTE == 2


def test_postgres_verbindungen_mit_zeitlimits():
    argumente = database.engine_argumente("postgresql+psycopg://u:p@h/db")
    assert argumente["pool_size"] >= 5
    assert argumente["pool_timeout"] <= 30
    optionen = argumente["connect_args"]["options"]
    assert "statement_timeout" in optionen
    assert "idle_in_transaction_session_timeout" in optionen
    assert "lock_timeout" in optionen


def test_sqlite_ohne_postgres_optionen():
    assert "connect_args" not in database.engine_argumente("sqlite://")
