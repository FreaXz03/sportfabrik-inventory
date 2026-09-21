"""Kompletter Weg einer Rechnung: PDF → Layout-/Lieferanten-Erkennung →
Positionen → Datenbank (app/services/parsers/ + app/services/importer.py).

Die Rechnung wird selbst gebaut (siehe tests/test_parser_registry.py), darum
läuft dieser Test ohne die Originalrechnung aus INTERSPORT_TEST_PDF - anders
als tests/test_importer.py, das denselben Weg mit dem echten 21-seitigen
Dokument prüft. Die übrigen Import-Tests (test_importer_fedas.py,
test_lagerbewegungen.py) ersetzen den Parser durch eine Attrappe und würden
eine Lücke zwischen Parser-Ergebnis und Import gar nicht sehen.
"""

import hashlib
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from test_parser_registry import _invoice_pdf, _text_pdf

from app.core.kategorien import seed_kategorien
from app.core.lagerorte import seed_lagerorte
from app.core.lieferanten import seed_lieferanten
from app.core.models import (
    Artikel,
    Base,
    Bestand,
    Dokument,
    Kategorie,
    Lagerbewegung,
    Lagerort,
    Lieferant,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from app.routers.auth import get_language, require_chef_api, require_chef_page
from app.routers.preview import router
from app.services import importer
from app.services.importer import ImportRejected, import_invoice
from app.services.parsers import UnknownLayoutError, intersport

KOPFZEILEN = [
    [(30, "INTERSPORT"), (200, "Schweiz"), (300, "AG")],
    [(30, "Rechnung"), (130, "Nr."), (200, "9001759392")],
    [(30, "Rechnungsdatum"), (200, "05.08.2026")],
    [(30, "Belegdatum"), (200, "04.08.2026")],
]
# Zwei Varianten desselben Artikels (gleiche Lieferanten-Artikelnummer A1,
# verschiedene EAN) plus ein zweiter Artikel - FEDAS 224100 = Textil × Tennis,
# 324100 = Schuhe × Tennis (siehe app/core/fedas.py).
POSITIONEN = [
    ["Nike", "224100", "A1", "9988770010", "4006632041234", "Poloshirt", "5", "Stk", "49.90", "30.00"],
    ["Nike", "224100", "A1", "9988770011", "4006632041241", "Poloshirt", "3", "Stk", "49.90", "30.00"],
    ["Nike", "324100", "B2", "9988770012", "4006632041258", "Laufschuh", "2", "Stk", "129.00", "80.00"],
]


@pytest.fixture
def rechnung():
    return _invoice_pdf(header_lines=KOPFZEILEN, rows=POSITIONEN)


@pytest.fixture
def sessions():
    # StaticPool + check_same_thread=False, weil der TestClient den Endpunkt in
    # einem anderen Thread aufruft als der Test selbst (wie tests/test_i18n.py).
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as session:
        seed_lagerorte(session)
        seed_lieferanten(session)
        seed_kategorien(session)
        session.commit()
    yield factory
    engine.dispose()


def _sf1(sessions):
    with sessions() as session:
        return session.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))


def test_import_writes_supplier_document_type_and_stock(rechnung, sessions):
    lagerort_id = _sf1(sessions)
    result = import_invoice(
        rechnung,
        "rechnung.pdf",
        hashlib.sha256(rechnung).hexdigest(),
        sessions,
        lagerort_id,
    )
    assert result["invoice_number"] == "9001759392"
    assert result["item_count"] == 3
    assert result["new_products"] == 3

    with sessions() as session:
        dokument = session.scalar(select(Dokument))
        lieferant = session.get(Lieferant, dokument.lieferant_id)
        # Lieferant und Dokumenttyp kommen aus dem Dokument, nicht aus einer
        # Konstante im Importer.
        assert lieferant.parser_key == intersport.KEY
        assert lieferant.name == intersport.LIEFERANT_NAME
        assert dokument.typ == "rechnung"
        assert str(dokument.dokumentdatum) == "2026-08-05"
        assert str(dokument.belegdatum) == "2026-08-04"
        assert dokument.lagerort_id == lagerort_id

        wareneingang = session.scalar(select(Wareneingang))
        assert wareneingang.status == "eingetroffen"
        assert str(wareneingang.eingangsdatum) == "2026-08-05"
        assert session.scalar(select(func.count()).select_from(WareneingangPosition)) == 3

        # Gleiche Marke + Lieferanten-Artikelnummer = ein Artikel mit zwei
        # Varianten (Regel 4/5).
        assert session.scalar(select(func.count()).select_from(Artikel)) == 2
        assert session.scalar(select(func.count()).select_from(Variante)) == 3
        artikel = session.scalars(
            select(Artikel).order_by(Artikel.lieferanten_artikelnr)
        ).all()
        assert [a.lieferanten_artikelnr for a in artikel] == ["A1", "B2"]
        kategorien = [session.get(Kategorie, a.kategorie_id) for a in artikel]
        assert [(k.hauptgruppe, k.sportbereich) for k in kategorien] == [
            ("Textil", "Tennis"),
            ("Schuhe", "Tennis"),
        ]

        # Regel 2: Bestand nur über Lagerbewegungen.
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 3
        assert {str(b.menge) for b in session.scalars(select(Bestand)).all()} == {
            "5.00",
            "3.00",
            "2.00",
        }


def test_same_file_is_not_imported_twice(rechnung, sessions):
    lagerort_id = _sf1(sessions)
    digest = hashlib.sha256(rechnung).hexdigest()
    import_invoice(rechnung, "rechnung.pdf", digest, sessions, lagerort_id)
    with pytest.raises(ImportRejected, match="bereits importiert"):
        import_invoice(rechnung, "noch-einmal.pdf", digest, sessions, lagerort_id)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Dokument)) == 1


def test_unknown_layout_is_not_imported(sessions):
    """Ein fremdes Layout landet nie halb in der Datenbank - der Import
    bricht schon bei der Erkennung ab (der Upload-Endpunkt meldet 409, siehe
    app/routers/preview.py)."""
    fremd = _text_pdf("Alpina AG", "Auftragsbestätigung 160165", "Pos Artikel Menge")
    with pytest.raises(UnknownLayoutError, match="noch nicht"):
        import_invoice(
            fremd,
            "alpina.pdf",
            hashlib.sha256(fremd).hexdigest(),
            sessions,
            _sf1(sessions),
        )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Dokument)) == 0


def test_import_rejects_a_document_without_a_recognised_type(
    rechnung, sessions, monkeypatch
):
    """Ohne erkannten Dokumenttyp wird nicht gebucht: sonst landete Ware als
    „Rechnung" im Bestand, die vielleicht erst bestätigt (Regel 3) ist."""
    original = importer.parse_with_parser

    def without_type(parser, document, language="de"):
        return {**original(parser, document, language), "document_type": None}

    monkeypatch.setattr(importer, "parse_with_parser", without_type)
    with pytest.raises(ImportRejected, match="Dokumenttyp"):
        import_invoice(
            rechnung,
            "rechnung.pdf",
            hashlib.sha256(rechnung).hexdigest(),
            sessions,
            _sf1(sessions),
        )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Dokument)) == 0


def _client():
    app = FastAPI()
    app.include_router(router)
    # Diese Tests prüfen den Upload-Weg, nicht die Rechte (siehe test_auth.py).
    app.dependency_overrides[require_chef_api] = lambda: None
    app.dependency_overrides[require_chef_page] = lambda: None
    app.dependency_overrides[get_language] = lambda: "de"
    return TestClient(app)


def test_preview_endpoint_reports_the_detected_supplier(rechnung):
    response = _client().post(
        "/upload-preview", files={"file": ("rechnung.pdf", rechnung, "application/pdf")}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parser_key"] == intersport.KEY
    assert body["supplier_name"] == intersport.LIEFERANT_NAME
    assert body["document_type"] == "rechnung"
    assert body["item_count"] == 3
    assert body["rows_with_warnings"] == 0


def test_preview_endpoint_rejects_an_unknown_layout():
    fremd = _text_pdf("CMP Bestellung 22065", "Grösse 92 104 116 128")
    response = _client().post(
        "/upload-preview", files={"file": ("cmp.pdf", fremd, "application/pdf")}
    )
    assert response.status_code == 422
    assert "noch nicht" in response.json()["detail"]


# --- Belegnummer nur je Lieferant eindeutig (Teilaufgabe B2) ---------------


class _ZweitesLayout:
    """Zweites Lieferanten-Layout nur für diese Tests: erkennt sich am
    Firmennamen und liest die Tabelle mit dem INTERSPORT-Parser (dasselbe
    Tabellenlayout - hier geht es nur um zwei *Lieferanten*, nicht um ein
    zweites Tabellenformat). Die hohe Punktzahl lässt es gegen INTERSPORT
    gewinnen, siehe app/services/parsers/__init__.py."""

    KEY = "testhandel"
    LIEFERANT_NAME = "Test Handel AG"

    @staticmethod
    def detect(document):
        # Wie die echten Parser über den Firmennamen, und wie dort mit \s+:
        # zwischen weit auseinanderliegenden Wörtern steht im PDF-Text nicht
        # zwingend genau ein Leerzeichen.
        return 9 if re.search(r"TEST\s+HANDEL", document.text, re.I) else None

    parse = staticmethod(intersport.parse)
    dates = staticmethod(intersport.dates)


@pytest.fixture
def zweiter_lieferant(sessions, monkeypatch):
    """Registriert das zweite Layout und legt den passenden Lieferanten an."""
    monkeypatch.setattr(
        "app.services.parsers.PARSERS", (intersport, _ZweitesLayout)
    )
    with sessions() as session:
        session.add(
            Lieferant(
                name=_ZweitesLayout.LIEFERANT_NAME,
                typ="drittanbieter",
                parser_key=_ZweitesLayout.KEY,
            )
        )
        session.commit()
    # Gleiche Belegnummer wie `rechnung`, anderer Lieferant.
    return _invoice_pdf(
        header_lines=[[(30, "TEST HANDEL AG")]] + KOPFZEILEN[1:],
        rows=POSITIONEN[:1],
    )


def _import(pdf, sessions, lagerort_id, filename="rechnung.pdf"):
    return import_invoice(
        pdf, filename, hashlib.sha256(pdf).hexdigest(), sessions, lagerort_id
    )


def test_two_suppliers_may_use_the_same_document_number(
    rechnung, zweiter_lieferant, sessions
):
    """Belegnummern sind Lieferantensache: dass INTERSPORT die Nummer schon
    verwendet hat, darf die Rechnung eines anderen Lieferanten nicht blocken."""
    lagerort_id = _sf1(sessions)
    _import(rechnung, sessions, lagerort_id)
    _import(zweiter_lieferant, sessions, lagerort_id, "test-handel.pdf")
    with sessions() as session:
        dokumente = session.scalars(select(Dokument).order_by(Dokument.id)).all()
        assert [d.dokumentnummer for d in dokumente] == ["9001759392", "9001759392"]
        assert len({d.lieferant_id for d in dokumente}) == 2
        assert [
            session.get(Lieferant, d.lieferant_id).parser_key for d in dokumente
        ] == [intersport.KEY, _ZweitesLayout.KEY]


def test_same_number_from_the_same_supplier_is_still_rejected(rechnung, sessions):
    """Andere Datei, gleiche Belegnummer beim selben Lieferanten: das ist
    dieselbe Rechnung, nur neu exportiert."""
    lagerort_id = _sf1(sessions)
    _import(rechnung, sessions, lagerort_id)
    nochmal = _invoice_pdf(header_lines=KOPFZEILEN, rows=POSITIONEN[:1])
    assert hashlib.sha256(nochmal).hexdigest() != hashlib.sha256(rechnung).hexdigest()
    with pytest.raises(ImportRejected, match="bereits importiert"):
        _import(nochmal, sessions, lagerort_id, "nochmal.pdf")
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Dokument)) == 1


def test_database_enforces_the_pair_as_well(rechnung, sessions):
    """Die Prüfung im Importer ist die verständliche Meldung, der
    Datenbank-Constraint der Rückfall (z. B. bei zwei gleichzeitigen
    Importen) - siehe UniqueConstraint in app/core/models.py."""
    lagerort_id = _sf1(sessions)
    _import(rechnung, sessions, lagerort_id)
    with sessions() as session:
        vorhanden = session.scalar(select(Dokument))
        session.add(
            Dokument(
                lieferant_id=vorhanden.lieferant_id,
                lagerort_id=lagerort_id,
                typ="rechnung",
                dokumentnummer=vorhanden.dokumentnummer,
                datei_hash="anderer-hash",
                hochgeladen_am=vorhanden.hochgeladen_am,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_import_status_needs_the_supplier_for_a_number_match(
    rechnung, zweiter_lieferant, sessions, monkeypatch
):
    """Die Stapel-Warteschlange überspringt schon importierte Dateien über
    diesen Endpunkt - er darf die Rechnung eines anderen Lieferanten mit
    derselben Nummer nicht als „schon importiert" melden."""
    import app.core.database as database

    lagerort_id = _sf1(sessions)
    _import(rechnung, sessions, lagerort_id)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    client = _client()

    def status(**params):
        return client.get("/invoice-import-status", params=params).json()

    importiert = status(
        file_hash="unbekannt", invoice_number="9001759392", parser_key=intersport.KEY
    )
    assert importiert["imported"] is True and importiert["invoice_id"]
    assert status(
        file_hash="unbekannt",
        invoice_number="9001759392",
        parser_key=_ZweitesLayout.KEY,
    ) == {"imported": False, "invoice_id": None}
    # Ohne Lieferant zählt nur die Datei selbst.
    assert status(file_hash="unbekannt", invoice_number="9001759392") == {
        "imported": False,
        "invoice_id": None,
    }
    assert status(file_hash=hashlib.sha256(rechnung).hexdigest())["imported"] is True
