"""Erwartet → eingetroffen: Bestand entsteht erst bei bestätigter Ankunft
(Phase B, Teilaufgabe B5 — Regel 3, D6, D21, D22).

Die erwarteten Wareneingänge legen die Tests direkt an: die Parser-Registry
erkennt bisher nur Rechnungen, eine echte Auftragsbestätigung gibt es also noch
nicht (die Layouts folgen in Phase E). Der Weg Rechnung → sofort gebucht wird
in tests/test_import_end_to_end.py geprüft.
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
from app.core.lieferanten import seed_lieferanten
from app.core.models import (
    Artikel,
    Bestand,
    BenutzerLagerort,
    Dokument,
    Lagerbewegung,
    Lagerort,
    Lieferant,
    User,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from app.main import app
from app.services.wareneingang import (
    AnkunftRejected,
    bestaetige_ankunft,
    liste_erwartete,
    zaehle_erwartete,
)

DOKUMENTDATUM = date(2026, 8, 5)


@pytest.fixture
def daten():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        seed_lagerorte(session)
        seed_lieferanten(session)
        session.flush()
        codes = {lo.code: lo.id for lo in session.scalars(select(Lagerort)).all()}
        lieferant_id = session.scalar(select(Lieferant.id))
        artikel = Artikel(
            lieferant_id=lieferant_id,
            marke="Nike",
            lieferanten_artikelnr="A1",
            bezeichnung="Poloshirt",
        )
        session.add(artikel)
        session.flush()
        varianten = [
            Variante(artikel_id=artikel.id, farbe="Weiss", groesse=groesse, ean=ean)
            for groesse, ean in [("M", "4006632041234"), ("L", "4006632041241")]
        ]
        session.add_all(varianten)
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


def _erwarteter_wareneingang(sessions, codes, lagerort="SF1", mengen=(5, 3)):
    """Auftragsbestätigung mit zwei Positionen, noch nichts eingetroffen."""
    return _erwarteter_wareneingang_mit_nummer(
        sessions, codes, "AB-160165", lagerort, mengen
    )


def _erwarteter_wareneingang_mit_nummer(
    sessions, codes, nummer, lagerort="SF1", mengen=(5, 3)
):
    with sessions.begin() as session:
        lieferant_id = session.scalar(select(Lieferant.id))
        dokument = Dokument(
            lieferant_id=lieferant_id,
            lagerort_id=codes[lagerort],
            typ="auftragsbestaetigung",
            dokumentnummer=nummer,
            dokumentdatum=DOKUMENTDATUM,
            belegdatum=DOKUMENTDATUM,
        )
        session.add(dokument)
        session.flush()
        wareneingang = Wareneingang(
            dokument_id=dokument.id,
            lagerort_id=codes[lagerort],
            status="erwartet",
            eingangsdatum=None,
        )
        session.add(wareneingang)
        session.flush()
        varianten = session.scalars(select(Variante).order_by(Variante.id)).all()
        positionen = [
            WareneingangPosition(
                wareneingang_id=wareneingang.id,
                varianten_id=variante.id,
                menge=Decimal(anzahl),
                menge_eingetroffen=Decimal(0),
                einheit="Stk",
                uvp=Decimal("49.90"),
            )
            for variante, anzahl in zip(varianten, mengen)
        ]
        session.add_all(positionen)
        session.flush()
        return wareneingang.id, [position.id for position in positionen]


# --- Erwartet heisst: noch kein Bestand -----------------------------------


def test_expected_delivery_books_no_stock(daten):
    sessions, codes = daten
    _erwarteter_wareneingang(sessions, codes)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 0
        assert session.scalar(select(func.count()).select_from(Bestand)) == 0
        assert session.scalar(select(Wareneingang)).eingangsdatum is None
        assert zaehle_erwartete(session) == 1


def test_list_shows_open_quantities(daten):
    sessions, codes = daten
    _erwarteter_wareneingang(sessions, codes)
    with sessions() as session:
        offen = liste_erwartete(session, codes["SF1"])
    assert len(offen) == 1
    assert offen[0]["dokument"]["typ"] == "auftragsbestaetigung"
    assert offen[0]["lagerort"]["code"] == "SF1"
    assert [p["menge_offen"] for p in offen[0]["positionen"]] == ["5.00", "3.00"]


def test_list_is_filtered_by_lagerort(daten):
    sessions, codes = daten
    _erwarteter_wareneingang(sessions, codes, lagerort="SF1")
    with sessions() as session:
        assert liste_erwartete(session, codes["SF2"]) == []
        assert len(liste_erwartete(session)) == 1  # ohne Filter: alle Filialen


# --- Ankunft bestätigen ---------------------------------------------------


def test_full_arrival_books_stock_and_closes_the_receipt(daten):
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    ergebnis = bestaetige_ankunft(
        wareneingang_id,
        {positionen[0]: "5", positionen[1]: "3"},
        sessions,
        {"kassennummer": "910141", "name": "Anna"},
        date(2026, 8, 7),
    )
    assert ergebnis["status"] == "eingetroffen"
    assert ergebnis["offene_positionen"] == 0
    with sessions() as session:
        bewegungen = session.scalars(select(Lagerbewegung)).all()
        assert [b.typ for b in bewegungen] == ["zugang", "zugang"]
        assert [str(b.menge) for b in bewegungen] == ["5.00", "3.00"]
        assert {b.benutzer_name for b in bewegungen} == {"Anna"}
        assert {str(b.menge) for b in session.scalars(select(Bestand)).all()} == {
            "5.00",
            "3.00",
        }
        wareneingang = session.get(Wareneingang, wareneingang_id)
        assert str(wareneingang.eingangsdatum) == "2026-08-07"
        # „Erste Lieferung" zählt ab jetzt - vorher war es nur angekündigt.
        assert {str(v.first_seen) for v in session.scalars(select(Variante)).all()} == {
            str(DOKUMENTDATUM)
        }


def test_partial_arrival_keeps_the_rest_open(daten):
    """D22: Kommt weniger an, bleibt die Restmenge offen."""
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    ergebnis = bestaetige_ankunft(wareneingang_id, {positionen[0]: "2"}, sessions)
    assert ergebnis["status"] == "erwartet"
    assert ergebnis["offene_positionen"] == 2
    with sessions() as session:
        offen = liste_erwartete(session, codes["SF1"])[0]["positionen"]
        assert [p["menge_eingetroffen"] for p in offen] == ["2.00", "0.00"]
        assert [p["menge_offen"] for p in offen] == ["3.00", "3.00"]
        assert str(session.scalar(select(func.sum(Bestand.menge)))) == "2.00"


def test_a_later_delivery_closes_the_receipt(daten):
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    bestaetige_ankunft(wareneingang_id, {positionen[0]: "2"}, sessions)
    ergebnis = bestaetige_ankunft(
        wareneingang_id, {positionen[0]: "3", positionen[1]: "3"}, sessions
    )
    assert ergebnis["status"] == "eingetroffen"
    with sessions() as session:
        # Drei Zugänge (2 + 3 + 3), Bestand stimmt trotzdem.
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 3
        assert str(session.scalar(select(func.sum(Bestand.menge)))) == "8.00"
        assert zaehle_erwartete(session) == 0


def test_arrival_date_stays_empty_for_a_warehouse_without_sales(daten):
    """Regel 6/D13: Ware in der GEWA bekommt kein Eingangsdatum."""
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes, "GEWA")
    bestaetige_ankunft(
        wareneingang_id, {positionen[0]: "5", positionen[1]: "3"}, sessions, None, date.today()
    )
    with sessions() as session:
        assert session.get(Wareneingang, wareneingang_id).eingangsdatum is None
        assert all(
            bestand.aeltestes_eingangsdatum is None
            for bestand in session.scalars(select(Bestand)).all()
        )


def test_arrival_date_defaults_to_today(daten):
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    bestaetige_ankunft(wareneingang_id, {positionen[0]: "5"}, sessions)
    with sessions() as session:
        assert session.get(Wareneingang, wareneingang_id).eingangsdatum == date.today()


# --- Abweisungen ----------------------------------------------------------


def test_confirming_twice_is_refused(daten):
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    bestaetige_ankunft(
        wareneingang_id, {positionen[0]: "5", positionen[1]: "3"}, sessions
    )
    with pytest.raises(AnkunftRejected, match="bereits"):
        bestaetige_ankunft(wareneingang_id, {positionen[0]: "1"}, sessions)


@pytest.mark.parametrize("menge", ["-1", "abc", "1.005"])
def test_implausible_quantities_book_nothing(daten, menge):
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    with pytest.raises(AnkunftRejected):
        bestaetige_ankunft(wareneingang_id, {positionen[0]: menge}, sessions)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 0


def test_a_position_of_another_receipt_is_refused(daten):
    """Positions-Ids kommen aus dem Browser - es muss geprüft werden, dass sie
    zu genau dieser Lieferung gehören."""
    sessions, codes = daten
    erster, _ = _erwarteter_wareneingang(sessions, codes)
    with sessions.begin() as session:
        # Zweite Lieferung mit eigener Position (andere Belegnummer).
        session.execute(
            Dokument.__table__.update()
            .where(Dokument.id == session.scalar(select(func.max(Dokument.id))))
            .values(dokumentnummer="AB-160165")
        )
    zweiter, fremde_positionen = _erwarteter_wareneingang_mit_nummer(
        sessions, codes, "AB-999999"
    )
    with pytest.raises(AnkunftRejected, match="Unbekannte Position"):
        bestaetige_ankunft(erster, {fremde_positionen[0]: "1"}, sessions)


def test_an_unknown_receipt_is_refused(daten):
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    with pytest.raises(AnkunftRejected, match="nicht gefunden"):
        bestaetige_ankunft(wareneingang_id + 99, {positionen[0]: "1"}, sessions)


def test_nothing_entered_is_refused(daten):
    sessions, codes = daten
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    with pytest.raises(AnkunftRejected, match="mindestens eine Menge"):
        bestaetige_ankunft(wareneingang_id, {positionen[0]: "0"}, sessions)


# --- Über die API, mit Anmeldung als Mitarbeiter (D21) --------------------


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


def test_employee_sees_and_confirms_deliveries(client):
    """D21: Ankunft bestätigen ist Lagerarbeit - Mitarbeiter dürfen das,
    obwohl sie keine Dokumente hochladen dürfen (Regel 9)."""
    test_client, sessions, codes = client
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)

    liste = test_client.get("/api/wareneingaenge").json()
    assert liste["lagerort"]["code"] == "SF1"
    assert len(liste["wareneingaenge"]) == 1

    antwort = test_client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft",
        json={
            "mengen": {str(positionen[0]): "5", str(positionen[1]): "3"},
            "eingangsdatum": "2026-08-07",
        },
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["status"] == "eingetroffen"
    assert test_client.get("/api/wareneingaenge").json()["wareneingaenge"] == []


def test_api_reports_a_bad_date(client):
    test_client, sessions, codes = client
    wareneingang_id, positionen = _erwarteter_wareneingang(sessions, codes)
    antwort = test_client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft",
        json={"mengen": {str(positionen[0]): "1"}, "eingangsdatum": "kein-datum"},
    )
    assert antwort.status_code == 422


def test_api_requires_a_login(client):
    test_client, _, _ = client
    test_client.post("/logout")
    assert test_client.get("/api/wareneingaenge").status_code == 401
