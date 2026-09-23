"""Korrekturen (Phase C, Teilaufgabe C5).

Geprüft werden die Antworten vom 23.09.2026: eingegeben wird die gezählte
Menge, gebucht die Differenz (`typ = korrektur`, Regel 2); stimmt der Bestand
schon, entsteht keine Zeile; Gründe gemäss Vorschlag; alle Rollen dürfen.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.database as database
from app.core.database import Base, get_session
from app.core.lagerorte import seed_lagerorte
from app.core.models import (
    Artikel,
    BenutzerLagerort,
    Bestand,
    Lagerbewegung,
    Lagerort,
    User,
    Variante,
)
from app.main import app
from app.services.korrektur import KorrekturRejected, korrigieren


@pytest.fixture
def daten():
    """Poloshirt: 9 Stück in SF1 seit 01.03.2026; Mitarbeiterin Anna in SF1."""
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
        session.add(polo)
        session.flush()
        m = Variante(artikel_id=polo.id, farbe="Weiss", groesse="M")
        session.add(m)
        session.flush()
        session.add(
            Bestand(
                varianten_id=m.id,
                lagerort_id=codes["SF1"],
                menge=Decimal("9"),
                aeltestes_eingangsdatum=date(2026, 3, 1),
            )
        )
        anna = User(kassennummer="910141", name="Anna", role="mitarbeiter", password_hash=None)
        session.add(anna)
        session.flush()
        session.add(
            BenutzerLagerort(user_id=anna.id, lagerort_id=codes["SF1"], ist_primaer=True)
        )
        variante_id = m.id
    yield sessions, codes, variante_id
    engine.dispose()


def _bestand(sessions, varianten_id, lagerort_id):
    with sessions() as session:
        return session.get(Bestand, (varianten_id, lagerort_id))


def _anzahl_bewegungen(sessions):
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(Lagerbewegung))


def test_gezaehlte_menge_bucht_die_differenz(daten):
    sessions, codes, vid = daten
    ergebnis = korrigieren(
        sessions,
        lagerort_id=codes["SF1"],
        varianten_id=vid,
        gezaehlt="7",
        grund="inventur",
        benutzer={"kassennummer": "910141", "name": "Anna"},
    )
    assert ergebnis["gebucht"] is True
    assert ergebnis["differenz"] == "-2.00"
    assert ergebnis["bestand_vorher"] == "9.00"
    assert ergebnis["bestand_nachher"] == "7.00"
    with sessions() as session:
        bewegung = session.get(Lagerbewegung, ergebnis["bewegung_id"])
        assert (bewegung.typ, bewegung.menge, bewegung.grund) == (
            "korrektur",
            Decimal("-2"),
            "inventur",
        )
        assert bewegung.benutzer_name == "Anna"
    assert _bestand(sessions, vid, codes["SF1"]).menge == Decimal("7")


def test_mehr_gezaehlt_bucht_plus(daten):
    sessions, codes, vid = daten
    ergebnis = korrigieren(
        sessions, lagerort_id=codes["SF1"], varianten_id=vid, gezaehlt="12", grund="gefunden"
    )
    assert ergebnis["differenz"] == "3.00"
    assert _bestand(sessions, vid, codes["SF1"]).menge == Decimal("12")


def test_stimmt_schon_bucht_nichts(daten):
    sessions, codes, vid = daten
    ergebnis = korrigieren(
        sessions, lagerort_id=codes["SF1"], varianten_id=vid, gezaehlt="9", grund="inventur"
    )
    assert ergebnis["gebucht"] is False
    assert ergebnis["bewegung_id"] is None
    assert _anzahl_bewegungen(sessions) == 0


def test_null_gezaehlt_leert_den_bestand(daten):
    sessions, codes, vid = daten
    korrigieren(
        sessions, lagerort_id=codes["SF1"], varianten_id=vid, gezaehlt="0", grund="inventur"
    )
    assert _bestand(sessions, vid, codes["SF1"]).menge == Decimal("0")


def test_negativer_bestand_wird_auf_die_zaehlung_gebracht(daten):
    """Gerade der Fall, für den C5 da ist: nach Verkäufen ohne erfassten
    Zugang steht der Bestand im Minus."""
    sessions, codes, vid = daten
    with sessions.begin() as session:
        session.get(Bestand, (vid, codes["SF1"])).menge = Decimal("-2")
    ergebnis = korrigieren(
        sessions, lagerort_id=codes["SF1"], varianten_id=vid, gezaehlt="3", grund="inventur"
    )
    assert ergebnis["differenz"] == "5.00"


def test_ohne_bestandszeile_entsteht_eine(daten):
    sessions, codes, vid = daten
    korrigieren(
        sessions, lagerort_id=codes["SF2"], varianten_id=vid, gezaehlt="2", grund="gefunden"
    )
    bestand = _bestand(sessions, vid, codes["SF2"])
    assert bestand.menge == Decimal("2")
    # Eine Korrektur ist kein Wareneingang.
    assert bestand.aeltestes_eingangsdatum is None


def test_eingangsdatum_bleibt(daten):
    sessions, codes, vid = daten
    korrigieren(
        sessions, lagerort_id=codes["SF1"], varianten_id=vid, gezaehlt="20", grund="gefunden"
    )
    assert _bestand(sessions, vid, codes["SF1"]).aeltestes_eingangsdatum == date(2026, 3, 1)


def test_sonstiges_braucht_text(daten):
    sessions, codes, vid = daten
    with pytest.raises(KorrekturRejected):
        korrigieren(
            sessions, lagerort_id=codes["SF1"], varianten_id=vid, gezaehlt="7", grund="sonstiges"
        )
    ergebnis = korrigieren(
        sessions,
        lagerort_id=codes["SF1"],
        varianten_id=vid,
        gezaehlt="7",
        grund="sonstiges",
        freitext="Schaufenster",
    )
    assert ergebnis["grund"] == "sonstiges: Schaufenster"


@pytest.mark.parametrize("gezaehlt", ["-1", "abc", "1.001", "", "NaN", "1e9"])
def test_ungueltige_menge_bucht_nichts(daten, gezaehlt):
    sessions, codes, vid = daten
    with pytest.raises(KorrekturRejected):
        korrigieren(
            sessions, lagerort_id=codes["SF1"], varianten_id=vid, gezaehlt=gezaehlt, grund="inventur"
        )
    assert _anzahl_bewegungen(sessions) == 0


def test_unbekannter_grund_und_variante(daten):
    sessions, codes, vid = daten
    with pytest.raises(KorrekturRejected):
        korrigieren(
            sessions, lagerort_id=codes["SF1"], varianten_id=vid, gezaehlt="7", grund="verkauf"
        )
    with pytest.raises(KorrekturRejected):
        korrigieren(
            sessions, lagerort_id=codes["SF1"], varianten_id=9999, gezaehlt="7", grund="inventur"
        )
    assert _anzahl_bewegungen(sessions) == 0


# --- API ------------------------------------------------------------------


@pytest.fixture
def client(daten, monkeypatch):
    sessions, codes, vid = daten

    def override_get_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(database, "SessionLocal", sessions)
    with TestClient(app) as test_client:
        test_client.post("/login", data={"kassennummer": "910141"})
        yield test_client, sessions, codes, vid
    app.dependency_overrides.clear()


def test_api_gruende(client):
    test_client, _, _, _ = client
    assert test_client.get("/api/korrektur/gruende").json()["gruende"] == [
        "inventur",
        "falsch_gebucht",
        "gefunden",
        "sonstiges",
    ]


def test_api_mitarbeiter_darf_korrigieren(client):
    """Regel 9 (bestätigt 23.09.2026): alle Rollen."""
    test_client, sessions, codes, vid = client
    antwort = test_client.post(
        "/api/korrektur",
        json={"varianten_id": vid, "lagerort_id": codes["SF1"], "gezaehlt": "5", "grund": "inventur"},
    )
    assert antwort.status_code == 200
    assert antwort.json()["differenz"] == "-4.00"
    assert _bestand(sessions, vid, codes["SF1"]).menge == Decimal("5")


def test_api_meldet_fehler(client):
    test_client, _, codes, vid = client
    antwort = test_client.post(
        "/api/korrektur",
        json={"varianten_id": vid, "lagerort_id": codes["SF1"], "gezaehlt": "-3", "grund": "inventur"},
    )
    assert antwort.status_code == 409


def test_api_verlangt_eine_anmeldung(client):
    test_client, _, codes, vid = client
    test_client.post("/logout")
    assert test_client.post(
        "/api/korrektur",
        json={"varianten_id": vid, "lagerort_id": codes["SF1"], "gezaehlt": "5", "grund": "inventur"},
    ).status_code == 401
