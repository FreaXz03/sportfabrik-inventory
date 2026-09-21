"""Ziel-Lagerort eines Wareneingangs: Vorschlag aus der Lieferadresse und
serverseitige Rechteprüfung (Phase B, Teilaufgabe B4 — D19/D20).

Läuft über die echte App mit Anmeldung, damit auch der Rechteweg geprüft wird
(`require_chef_api`, `resolve_wareneingang_lagerort`) - nicht über
ausgeschaltete Dependencies. Die Rechnung wird selbst gebaut (siehe
tests/test_parser_registry.py).
"""

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from test_parser_registry import POSITION, _invoice_pdf

import app.core.database as database
from app.core.database import Base, get_session
from app.core.kategorien import seed_kategorien
from app.core.lagerorte import seed_lagerorte
from app.core.lieferanten import seed_lieferanten
from app.core.models import (
    BenutzerLagerort,
    Bestand,
    Dokument,
    Lagerort,
    User,
    Wareneingang,
)
from app.core.security import hash_password
from app.main import app

KOPF = [
    [(30, "INTERSPORT Schweiz AG")],
    [(30, "Rechnung"), (130, "Nr."), (200, "9001759392")],
    [(30, "Rechnungsdatum"), (200, "05.08.2026")],
    [(30, "Belegdatum"), (200, "04.08.2026")],
]
# Rechnungsadresse Volketswil (SF1), Lieferadresse Conthey (SF4) - der Fall aus
# projekt-kontext.md Abschnitt 6 beim externen Händler.
LIEFERADRESSE_CONTHEY = [
    [(30, "Rechnungsadresse: Sport Fabrik AG, Industriestrasse 21, 8604 Volketswil")],
    [(30, "Lieferadresse: Sport Fabrik AG, Route Cantonale 7, 1964 Conthey")],
]


@pytest.fixture
def umgebung(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        seed_lagerorte(session)
        seed_lieferanten(session)
        seed_kategorien(session)
        session.flush()
        codes = {
            lagerort.code: lagerort.id
            for lagerort in session.scalars(select(Lagerort)).all()
        }
        for kassennummer, code in [("910001", "SF1"), ("910002", "SF2")]:
            chef = User(
                kassennummer=kassennummer,
                name=f"Chef {code}",
                role="chef",
                password_hash=hash_password("geheim123"),
            )
            session.add(chef)
            session.flush()
            session.add(
                BenutzerLagerort(
                    user_id=chef.id, lagerort_id=codes[code], ist_primaer=True
                )
            )

    def override_get_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    # Der Import läuft im Threadpool mit eigener Session-Fabrik.
    monkeypatch.setattr(database, "SessionLocal", sessions)
    with TestClient(app) as client:
        client.post("/login", data={"kassennummer": "910001", "password": "geheim123"})
        yield client, sessions, codes
    app.dependency_overrides.clear()
    engine.dispose()


def _upload(client, pdf):
    return client.post(
        "/upload-preview", files={"file": ("rechnung.pdf", pdf, "application/pdf")}
    )


def _import(client, pdf, **felder):
    daten = {
        "expected_hash": hashlib.sha256(pdf).hexdigest(),
        "confirmed": "true",
        **felder,
    }
    return client.post(
        "/import-invoice",
        files={"file": ("rechnung.pdf", pdf, "application/pdf")},
        data=daten,
    )


# --- Vorschau -------------------------------------------------------------


def test_preview_suggests_the_lagerort_from_the_delivery_address(umgebung):
    client, _, codes = umgebung
    pdf = _invoice_pdf(header_lines=KOPF + LIEFERADRESSE_CONTHEY)
    body = _upload(client, pdf).json()
    vorschlag = body["lagerort_suggestion"]
    assert vorschlag["code"] == "SF4"
    assert vorschlag["id"] == codes["SF4"]
    assert vorschlag["from_delivery_address"] is True
    assert "plz" in vorschlag["matched"]
    # Die aktive Filiale bleibt daneben sichtbar - der Vorschlag entscheidet
    # nichts (D19).
    assert body["lagerort_active"]["code"] == "SF1"


def test_preview_without_a_delivery_address_makes_no_suggestion(umgebung):
    client, _, _ = umgebung
    body = _upload(client, _invoice_pdf(header_lines=KOPF)).json()
    assert body["lagerort_suggestion"] is None
    assert body["lagerort_active"]["code"] == "SF1"


def test_preview_offers_every_lagerort_with_the_own_branch_first(umgebung):
    """Das Ziel bestimmt der Beleg (D19/D20), nicht die aktive Filiale: auch
    eine Lieferung an eine andere Filiale oder an einen externen Standort muss
    buchbar sein. Die eigene Filiale steht vorn, weil sie der Normalfall ist,
    die externen Standorte hinten."""
    client, _, _ = umgebung
    body = _upload(client, _invoice_pdf(header_lines=KOPF)).json()
    assert [o["code"] for o in body["lagerort_options"]] == [
        "SF1",
        "SF2",
        "SF3",
        "SF4",
        "GEWA",
        "VEBO",
        "DIETIKON",
    ]


# --- Import ---------------------------------------------------------------


def test_import_books_to_the_chosen_lagerort(umgebung):
    client, sessions, codes = umgebung
    pdf = _invoice_pdf(header_lines=KOPF + LIEFERADRESSE_CONTHEY)
    antwort = _import(client, pdf, lagerort_id=str(codes["SF4"]))
    assert antwort.status_code == 200, antwort.text
    with sessions() as session:
        dokument = session.scalar(select(Dokument))
        assert dokument.lagerort_id == codes["SF4"]
        assert session.scalar(select(Wareneingang)).lagerort_id == codes["SF4"]


def test_import_without_a_choice_uses_the_active_branch(umgebung):
    """Der Vorschlag ist nur ein Vorschlag (D19): schickt die Oberfläche keinen
    Lagerort mit, bleibt es bei der aktiven Filiale - auch wenn das Dokument
    eine andere Lieferadresse trägt."""
    client, sessions, codes = umgebung
    pdf = _invoice_pdf(header_lines=KOPF + LIEFERADRESSE_CONTHEY)
    assert _import(client, pdf).status_code == 200
    with sessions() as session:
        assert session.scalar(select(Dokument)).lagerort_id == codes["SF1"]


def test_import_to_the_external_warehouse_gets_no_arrival_date(umgebung):
    """Regel 6/D13: Ware an ein Lager ohne Verkauf bekommt noch kein
    Eingangsdatum - die Reduktionsuhr startet erst in der Filiale."""
    client, sessions, codes = umgebung
    pdf = _invoice_pdf(header_lines=KOPF, rows=[POSITION])
    assert _import(client, pdf, lagerort_id=str(codes["GEWA"])).status_code == 200
    with sessions() as session:
        wareneingang = session.scalar(select(Wareneingang))
        assert wareneingang.lagerort_id == codes["GEWA"]
        assert wareneingang.eingangsdatum is None
        assert session.scalar(select(Bestand)).aeltestes_eingangsdatum is None


def test_import_with_an_unknown_lagerort_is_refused(umgebung):
    """Serverseitig geprüft: der Browser könnte jede Id schicken."""
    client, sessions, _ = umgebung
    pdf = _invoice_pdf(header_lines=KOPF)
    assert _import(client, pdf, lagerort_id="9999").status_code == 403
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Dokument)) == 0
