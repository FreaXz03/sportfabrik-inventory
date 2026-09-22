"""Bestand ansehen (Phase C, Teilaufgabe C2).

Geprüft wird die Leseschicht: Filter je Lagerort, Suche, Zeilen ohne Bestand,
die Kennzahlen und der Weg über die API samt Rechten. Gebucht wird hier nichts
- der Bestand entsteht über `lagerbewegungen` (Regel 2), siehe
tests/test_lagerbewegungen.py.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.database as database
from app.core.database import Base, get_session
from app.core.lagerorte import seed_lagerorte
from app.core.models import (
    Artikel,
    Bestand,
    BenutzerLagerort,
    Lagerort,
    User,
    Variante,
)
from app.main import app
from app.services.bestand import liste_bestand


@pytest.fixture
def daten():
    """Zwei Artikel, drei Bestandszeilen: SF1, SF3 und die GEWA (ohne Datum)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        seed_lagerorte(session)
        session.flush()
        codes = {lo.code: lo.id for lo in session.scalars(select(Lagerort)).all()}

        polo = Artikel(marke="Nike", lieferanten_artikelnr="A1", bezeichnung="Poloshirt")
        jacke = Artikel(marke="CMP", lieferanten_artikelnr="B2", bezeichnung="Regenjacke")
        session.add_all([polo, jacke])
        session.flush()
        weiss = Variante(artikel_id=polo.id, farbe="Weiss", groesse="M", ean="4006632041234")
        blau = Variante(artikel_id=jacke.id, farbe="Blau", groesse="152")
        session.add_all([weiss, blau])
        session.flush()
        session.add_all(
            [
                Bestand(
                    varianten_id=weiss.id,
                    lagerort_id=codes["SF1"],
                    menge=Decimal("5"),
                    aeltestes_eingangsdatum=date(2026, 3, 1),
                ),
                Bestand(
                    varianten_id=weiss.id,
                    lagerort_id=codes["SF3"],
                    menge=Decimal("2"),
                    aeltestes_eingangsdatum=date(2026, 8, 20),
                ),
                # Regel 6/D13: an einem Standort ohne Verkauf gibt es kein
                # Eingangsdatum - die Uhr startet erst in einer Filiale.
                Bestand(
                    varianten_id=blau.id,
                    lagerort_id=codes["GEWA"],
                    menge=Decimal("12"),
                    aeltestes_eingangsdatum=None,
                ),
                # Ausverkauft: bleibt als Zeile stehen, wird aber normalerweise
                # nicht gezeigt.
                Bestand(
                    varianten_id=blau.id,
                    lagerort_id=codes["SF1"],
                    menge=Decimal("0"),
                    aeltestes_eingangsdatum=date(2025, 1, 15),
                ),
            ]
        )
        mitarbeiter = User(
            kassennummer="910141", name="Anna", role="mitarbeiter", password_hash=None
        )
        session.add(mitarbeiter)
        session.flush()
        session.add(
            BenutzerLagerort(
                user_id=mitarbeiter.id, lagerort_id=codes["SF1"], ist_primaer=True
            )
        )
    yield sessions, codes
    engine.dispose()


# --- Leseschicht ----------------------------------------------------------


def test_bestand_ueber_alle_lagerorte(daten):
    sessions, _ = daten
    with sessions() as session:
        ergebnis = liste_bestand(session)
    assert ergebnis["total"] == 3  # die Zeile mit Menge 0 fehlt
    assert ergebnis["summe"] == "19.00"
    assert [zeile["lagerort"]["code"] for zeile in ergebnis["zeilen"]] == [
        "GEWA",
        "SF1",
        "SF3",
    ]


def test_filter_nach_lagerort(daten):
    sessions, codes = daten
    with sessions() as session:
        ergebnis = liste_bestand(session, lagerort_id=codes["SF3"])
    assert ergebnis["total"] == 1
    assert ergebnis["zeilen"][0]["menge"] == "2.00"
    assert ergebnis["zeilen"][0]["aeltestes_eingangsdatum"] == "2026-08-20"


def test_ware_am_externen_standort_hat_kein_eingangsdatum(daten):
    sessions, codes = daten
    with sessions() as session:
        ergebnis = liste_bestand(session, lagerort_id=codes["GEWA"])
    zeile = ergebnis["zeilen"][0]
    assert zeile["aeltestes_eingangsdatum"] is None
    assert zeile["lagerort"]["verkauf"] is False


def test_ausverkaufte_zeile_nur_auf_wunsch(daten):
    sessions, codes = daten
    with sessions() as session:
        ohne = liste_bestand(session, lagerort_id=codes["SF1"])
        mit = liste_bestand(session, lagerort_id=codes["SF1"], nur_vorhanden=False)
    assert ohne["total"] == 1
    assert mit["total"] == 2
    assert [zeile["menge"] for zeile in mit["zeilen"]] == ["0.00", "5.00"]


def test_negativer_bestand_bleibt_sichtbar(daten):
    """Ein negativer Bestand ist möglich (bestätigt 22.09.2026) und muss
    gerade dann in der Liste stehen, nicht herausgefiltert werden."""
    sessions, codes = daten
    with sessions.begin() as session:
        bestand = session.scalars(
            select(Bestand).where(Bestand.lagerort_id == codes["SF1"])
        ).all()
        bestand[0].menge = Decimal("-3")
    with sessions() as session:
        ergebnis = liste_bestand(session, lagerort_id=codes["SF1"])
    assert "-3.00" in [zeile["menge"] for zeile in ergebnis["zeilen"]]


@pytest.mark.parametrize("suche", ["nike", "Poloshirt", "A1", "4006632041234"])
def test_suche_findet_ueber_marke_bezeichnung_nummer_und_ean(daten, suche):
    sessions, _ = daten
    with sessions() as session:
        ergebnis = liste_bestand(session, suche=suche)
    assert ergebnis["total"] == 2  # dieselbe Variante in SF1 und SF3
    assert {zeile["marke"] for zeile in ergebnis["zeilen"]} == {"Nike"}


def test_seitenweise_abfrage(daten):
    sessions, _ = daten
    with sessions() as session:
        erste = liste_bestand(session, limit=2)
        zweite = liste_bestand(session, limit=2, offset=2)
    assert erste["hat_mehr"] is True
    assert len(erste["zeilen"]) == 2
    assert zweite["hat_mehr"] is False
    assert len(zweite["zeilen"]) == 1
    assert zweite["total"] == 3


# --- API ------------------------------------------------------------------


@pytest.fixture
def client(daten, monkeypatch):
    sessions, codes = daten

    def override_get_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(database, "SessionLocal", sessions)
    with TestClient(app) as test_client:
        test_client.post("/login", data={"kassennummer": "910141"})
        yield test_client, sessions, codes
    app.dependency_overrides.clear()


def test_api_zeigt_standardmaessig_die_aktive_filiale(client):
    test_client, _, codes = client
    body = test_client.get("/api/bestand").json()
    assert body["gewaehlt"] == codes["SF1"]
    assert body["total"] == 1
    assert [lagerort["code"] for lagerort in body["lagerorte"]][:4] == [
        "SF1",
        "SF2",
        "SF3",
        "SF4",
    ]


def test_api_zeigt_auf_wunsch_eine_fremde_filiale(client):
    """Bestätigt am 22.09.2026: Mitarbeiter dürfen alle Filialen **lesen**,
    auch die, zu denen sie nicht wechseln können."""
    test_client, _, codes = client
    body = test_client.get(f"/api/bestand?lagerort_id={codes['SF3']}").json()
    assert body["gewaehlt"] == codes["SF3"]
    assert body["total"] == 1


def test_api_kennt_alle_filialen_zusammen(client):
    test_client, _, _ = client
    body = test_client.get("/api/bestand?alle=true").json()
    assert body["gewaehlt"] is None
    assert body["total"] == 3
    assert body["summe"] == "19.00"


def test_api_weist_eine_unbekannte_filiale_ab(client):
    test_client, _, _ = client
    antwort = test_client.get("/api/bestand?lagerort_id=9999")
    assert antwort.status_code == 404


def test_api_verlangt_eine_anmeldung(client):
    test_client, _, _ = client
    test_client.post("/logout")
    assert test_client.get("/api/bestand").status_code == 401


def test_seite_verlangt_eine_anmeldung(client):
    test_client, _, _ = client
    test_client.post("/logout")
    antwort = test_client.get("/bestand", follow_redirects=False)
    assert antwort.status_code in (302, 303, 307)
    assert "/login" in antwort.headers["location"]
