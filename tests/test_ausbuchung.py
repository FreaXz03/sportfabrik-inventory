"""Ausbuchen per Scan (Phase C, Teilaufgabe C3).

Geprüft werden die Antworten vom 22./23.09.2026: ein Scan = ein Stück (F15),
Gründe gemäss F14 (Verkauf als eigener Typ), negativer Bestand wird gewarnt
und trotzdem gebucht (F9), und jede Änderung ist eine Zeile in
`lagerbewegungen` (Regel 2) - auch das Rückgängigmachen.
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
from app.services.ausbuchung import AusbuchungRejected, ausbuchen, storniere

EAN = "4006632041234"


@pytest.fixture
def daten():
    """Ein Poloshirt mit EAN (2 Stück in SF1), eine Jacke ohne EAN (1 Stück
    in SF1) und eine Mitarbeiterin mit SF1 als Filiale."""
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
        weiss = Variante(artikel_id=polo.id, farbe="Weiss", groesse="M", ean=EAN)
        blau = Variante(artikel_id=jacke.id, farbe="Blau", groesse="152")
        session.add_all([weiss, blau])
        session.flush()
        session.add_all(
            [
                Bestand(
                    varianten_id=weiss.id,
                    lagerort_id=codes["SF1"],
                    menge=Decimal("2"),
                    aeltestes_eingangsdatum=date(2026, 3, 1),
                ),
                Bestand(
                    varianten_id=blau.id,
                    lagerort_id=codes["SF1"],
                    menge=Decimal("1"),
                    aeltestes_eingangsdatum=date(2026, 5, 1),
                ),
            ]
        )
        anna = User(kassennummer="910141", name="Anna", role="mitarbeiter", password_hash=None)
        session.add(anna)
        session.flush()
        session.add(
            BenutzerLagerort(user_id=anna.id, lagerort_id=codes["SF1"], ist_primaer=True)
        )
        ids = {"weiss": weiss.id, "blau": blau.id}
    yield sessions, codes, ids
    engine.dispose()


BENUTZER = {"kassennummer": "910141", "name": "Anna"}


def _bestand(sessions, varianten_id, lagerort_id):
    with sessions() as session:
        bestand = session.get(Bestand, (varianten_id, lagerort_id))
        return None if bestand is None else bestand.menge


# --- Service --------------------------------------------------------------


def test_ein_scan_bucht_genau_ein_stueck_als_verkauf(daten):
    sessions, codes, ids = daten
    ergebnis = ausbuchen(
        sessions, lagerort_id=codes["SF1"], grund="verkauf", ean=EAN, benutzer=BENUTZER
    )
    assert ergebnis["bestand_vorher"] == "2.00"
    assert ergebnis["bestand_nachher"] == "1.00"
    assert ergebnis["bestand_reicht_nicht"] is False
    assert ergebnis["typ"] == "verkauf"
    with sessions() as session:
        bewegung = session.get(Lagerbewegung, ergebnis["bewegung_id"])
        assert bewegung.menge == Decimal("-1")
        assert bewegung.grund == "verkauf"
        assert bewegung.benutzer_name == "Anna"
    assert _bestand(sessions, ids["weiss"], codes["SF1"]) == Decimal("1")


def test_zweimal_scannen_heisst_zwei_stueck(daten):
    sessions, codes, ids = daten
    for _ in range(2):
        ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", ean=EAN)
    assert _bestand(sessions, ids["weiss"], codes["SF1"]) == Decimal("0")


@pytest.mark.parametrize("grund", ["defekt", "diebstahl", "eigenbedarf", "retoure"])
def test_andere_gruende_sind_ausbuchungen(daten, grund):
    sessions, codes, _ = daten
    ergebnis = ausbuchen(sessions, lagerort_id=codes["SF1"], grund=grund, ean=EAN)
    assert ergebnis["typ"] == "ausbuchung"
    assert ergebnis["grund"] == grund


def test_sonstiges_verlangt_freien_text(daten):
    sessions, codes, _ = daten
    with pytest.raises(AusbuchungRejected):
        ausbuchen(sessions, lagerort_id=codes["SF1"], grund="sonstiges", ean=EAN)
    ergebnis = ausbuchen(
        sessions,
        lagerort_id=codes["SF1"],
        grund="sonstiges",
        freitext="Musterteil für Schaufenster",
        ean=EAN,
    )
    assert ergebnis["grund"] == "sonstiges: Musterteil für Schaufenster"


def test_unbekannter_grund_bucht_nichts(daten):
    sessions, codes, ids = daten
    with pytest.raises(AusbuchungRejected):
        ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verschenkt", ean=EAN)
    assert _bestand(sessions, ids["weiss"], codes["SF1"]) == Decimal("2")


def test_unbekannte_ean_bucht_nichts(daten):
    sessions, codes, _ = daten
    with pytest.raises(AusbuchungRejected, match="7612345678900"):
        ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", ean="7612345678900")
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 0


def test_variante_ohne_ean_ueber_ihre_id(daten):
    """Regel 5: Varianten ohne EAN lassen sich nicht scannen, müssen sich aber
    trotzdem ausbuchen lassen - über den Knopf in der Bestandsansicht."""
    sessions, codes, ids = daten
    ergebnis = ausbuchen(
        sessions, lagerort_id=codes["SF1"], grund="test", varianten_id=ids["blau"]
    )
    assert ergebnis["bestand_nachher"] == "0.00"
    assert ergebnis["grund"] == "test"


def test_genau_ean_oder_variante(daten):
    sessions, codes, ids = daten
    with pytest.raises(AusbuchungRejected):
        ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf")
    with pytest.raises(AusbuchungRejected):
        ausbuchen(
            sessions,
            lagerort_id=codes["SF1"],
            grund="verkauf",
            ean=EAN,
            varianten_id=ids["weiss"],
        )


def test_zu_wenig_bestand_warnt_und_bucht_trotzdem(daten):
    """F9 (22.09.2026): wie an der Kasse - warnen, aber buchen."""
    sessions, codes, ids = daten
    ergebnis = ausbuchen(
        sessions, lagerort_id=codes["SF1"], grund="test", varianten_id=ids["blau"]
    )
    assert ergebnis["bestand_reicht_nicht"] is False
    ergebnis = ausbuchen(
        sessions, lagerort_id=codes["SF1"], grund="test", varianten_id=ids["blau"]
    )
    assert ergebnis["bestand_reicht_nicht"] is True
    assert ergebnis["bestand_nachher"] == "-1.00"


def test_ausbuchen_ohne_bestandszeile_legt_negativen_bestand_an(daten):
    sessions, codes, ids = daten
    ergebnis = ausbuchen(sessions, lagerort_id=codes["SF3"], grund="verkauf", ean=EAN)
    assert ergebnis["bestand_reicht_nicht"] is True
    with sessions() as session:
        bestand = session.get(Bestand, (ids["weiss"], codes["SF3"]))
        assert bestand.menge == Decimal("-1")
        # Ein Abgang ist kein Wareneingang - kein Datum.
        assert bestand.aeltestes_eingangsdatum is None


def test_eingangsdatum_bleibt_beim_ausbuchen(daten):
    sessions, codes, ids = daten
    ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", ean=EAN)
    ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", ean=EAN)
    with sessions() as session:
        bestand = session.get(Bestand, (ids["weiss"], codes["SF1"]))
        assert bestand.aeltestes_eingangsdatum == date(2026, 3, 1)


def test_bestand_ist_summe_der_bewegungen(daten):
    """Regel 2: der mitgeführte Bestand ändert sich genau um die Summe der
    neuen Journalzeilen."""
    sessions, codes, ids = daten
    ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", ean=EAN)
    erste = ausbuchen(sessions, lagerort_id=codes["SF1"], grund="defekt", ean=EAN)
    storniere(sessions, erste["bewegung_id"])
    with sessions() as session:
        summe = session.scalar(
            select(func.sum(Lagerbewegung.menge)).where(
                Lagerbewegung.varianten_id == ids["weiss"],
                Lagerbewegung.lagerort_id == codes["SF1"],
            )
        )
    assert summe == Decimal("-1")
    assert _bestand(sessions, ids["weiss"], codes["SF1"]) == Decimal("2") + summe


# --- Rückgängig -----------------------------------------------------------


def test_rueckgaengig_ist_eine_gegenbuchung(daten):
    sessions, codes, ids = daten
    ergebnis = ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", ean=EAN)
    storno = storniere(sessions, ergebnis["bewegung_id"], BENUTZER)
    assert storno["typ"] == "korrektur"
    assert storno["grund"] == f"storno:{ergebnis['bewegung_id']}"
    assert storno["bestand_nachher"] == "2.00"
    with sessions() as session:
        # Nichts gelöscht: Ausbuchung und Gegenbuchung stehen beide im Journal.
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 2


def test_rueckgaengig_nur_einmal(daten):
    sessions, codes, _ = daten
    ergebnis = ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", ean=EAN)
    storniere(sessions, ergebnis["bewegung_id"])
    with pytest.raises(AusbuchungRejected):
        storniere(sessions, ergebnis["bewegung_id"])


def test_rueckgaengig_nicht_fuer_andere_bewegungen(daten):
    sessions, codes, _ = daten
    ergebnis = ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", ean=EAN)
    storno = storniere(sessions, ergebnis["bewegung_id"])
    with pytest.raises(AusbuchungRejected):
        storniere(sessions, storno["bewegung_id"])
    with pytest.raises(AusbuchungRejected):
        storniere(sessions, 9999)


# --- API ------------------------------------------------------------------


@pytest.fixture
def client(daten, monkeypatch):
    sessions, codes, ids = daten

    def override_get_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(database, "SessionLocal", sessions)
    with TestClient(app) as test_client:
        test_client.post("/login", data={"kassennummer": "910141"})
        yield test_client, sessions, codes, ids
    app.dependency_overrides.clear()


def test_api_stammdaten(client):
    test_client, _, codes, _ = client
    body = test_client.get("/api/ausbuchen/stammdaten").json()
    assert body["lagerort_aktiv"] == codes["SF1"]
    assert body["gruende"][0] == "verkauf"
    assert "test" not in body["gruende"]


def test_api_mitarbeiter_bucht_in_der_aktiven_filiale(client):
    test_client, sessions, codes, ids = client
    antwort = test_client.post("/api/ausbuchen", json={"ean": EAN, "grund": "verkauf"})
    assert antwort.status_code == 200
    assert antwort.json()["lagerort"]["code"] == "SF1"
    assert _bestand(sessions, ids["weiss"], codes["SF1"]) == Decimal("1")


def test_api_testknopf_bucht_in_der_zeile_der_bestandsansicht(client):
    test_client, sessions, codes, ids = client
    antwort = test_client.post(
        "/api/ausbuchen",
        json={"varianten_id": ids["blau"], "lagerort_id": codes["SF1"], "grund": "test"},
    )
    assert antwort.status_code == 200
    assert antwort.json()["bestand_nachher"] == "0.00"


def test_api_meldet_fehler_verstaendlich(client):
    test_client, _, _, _ = client
    antwort = test_client.post(
        "/api/ausbuchen", json={"ean": "7612345678900", "grund": "verkauf"}
    )
    assert antwort.status_code == 409
    assert "7612345678900" in antwort.json()["detail"]


def test_api_storno(client):
    test_client, sessions, codes, ids = client
    gebucht = test_client.post("/api/ausbuchen", json={"ean": EAN, "grund": "verkauf"}).json()
    antwort = test_client.post(f"/api/ausbuchen/{gebucht['bewegung_id']}/storno")
    assert antwort.status_code == 200
    assert _bestand(sessions, ids["weiss"], codes["SF1"]) == Decimal("2")
    assert test_client.post(
        f"/api/ausbuchen/{gebucht['bewegung_id']}/storno"
    ).status_code == 409


def test_api_verlangt_eine_anmeldung(client):
    test_client, _, _, _ = client
    test_client.post("/logout")
    assert test_client.post(
        "/api/ausbuchen", json={"ean": EAN, "grund": "verkauf"}
    ).status_code == 401
    assert test_client.get("/ausbuchen", follow_redirects=False).status_code in (302, 303, 307)
