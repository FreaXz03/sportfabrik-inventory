"""Gescannter Columbia-Katalog: Import nach ausdrücklicher Prüfung (06.10.2026).

OCR-Warnungen sperren den Import sonst immer. Der Parser setzt
`import_nach_pruefung`; erst dann genügt die Bestätigung "alle Positionen geprüft".
"""

import hashlib

import pytest
from conftest import neue_datenbank
from sqlalchemy import func, select
from testbelege import kopf, rechnung_pdf

from app.core.models import Lagerort, Variante
from app.services import importer
from app.services.importer import ImportRejected, import_invoice


def _mit_warnungen(monkeypatch, pruefung):
    original = importer.parse_with_parser

    def parse(*args, **kwargs):
        result = original(*args, **kwargs)
        result["warnings"] = ["Gescannter Katalog: am Original prüfen"]
        result["items"][0]["warnings"] = ["Unsichere OCR"]
        result["rows_with_warnings"] = 1
        if pruefung:
            result["import_nach_pruefung"] = True
        return result

    monkeypatch.setattr(importer, "parse_with_parser", parse)


def _importieren():
    sessions = neue_datenbank()
    with sessions() as session:
        sf1 = session.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
    pdf = rechnung_pdf(header_lines=kopf(nummer="1000000077"))
    digest = hashlib.sha256(pdf).hexdigest()
    return sessions, lambda: import_invoice(pdf, "scan.pdf", digest, sessions, sf1)


def test_ocr_warnungen_sperren_import_ohne_pruefmarke(monkeypatch):
    _mit_warnungen(monkeypatch, pruefung=False)
    _, importieren = _importieren()
    with pytest.raises(ImportRejected):
        importieren()


def test_scan_mit_pruefmarke_wird_importiert(monkeypatch):
    _mit_warnungen(monkeypatch, pruefung=True)
    sessions, importieren = _importieren()
    assert importieren()["item_count"] > 0
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Variante)) > 0
