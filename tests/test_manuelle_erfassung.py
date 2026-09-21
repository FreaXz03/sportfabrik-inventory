"""Manuelle Erfassung: Ware ohne Beleg direkt einbuchen (Phase B, Teilaufgabe
B6 — D23, D27, Regel 2/3/5/6/9/10).

Geprüft wird beides: der Dienst selbst (Pflichtfelder, Artikel- und
Varianten-Regeln, Bestand, Eingangsdatum) und der Weg über die API, den die
Oberfläche geht - inklusive der Rechte (Mitarbeiter dürfen erfassen, D21).
"""

from datetime import date, timedelta
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
    Lagerbewegung,
    Lagerort,
    Lieferant,
    Preis,
    User,
    Variante,
    Wareneingang,
    WareneingangPosition,
    WareneingangPositionQuelle,
)
from app.main import app
from app.services.manuelle_erfassung import (
    GRUND,
    ErfassungRejected,
    erfasse_wareneingang,
    variante_per_ean,
)

BENUTZER = {"kassennummer": "910141", "name": "Anna"}


def position(**overrides) -> dict:
    """Eine vollständige Position; einzelne Felder werden überschrieben."""
    return {
        "marke": "Nike",
        "bezeichnung": "Poloshirt Court",
        "menge": "3",
        "uvp": "39.90",
        **overrides,
    }


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


def erfasse(sessions, codes, positionen, lagerort="SF1", **kwargs):
    return erfasse_wareneingang(
        positionen,
        sessions,
        lagerort_id=codes[lagerort],
        benutzer=BENUTZER,
        **kwargs,
    )


def _bestand(sessions, lagerort_id) -> list[Bestand]:
    with sessions() as session:
        return session.scalars(
            select(Bestand).where(Bestand.lagerort_id == lagerort_id)
        ).all()


# --- Pflichtfelder (D23) ---------------------------------------------------


@pytest.mark.parametrize("feld", ["marke", "bezeichnung", "menge", "uvp"])
def test_pflichtfeld_fehlt(daten, feld):
    """D23: Marke, Bezeichnung, Menge und UVP sind Pflicht - sonst nichts."""
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position(**{feld: ""})])
    assert _bestand(sessions, codes["SF1"]) == []


def test_alles_optionale_darf_fehlen(daten):
    """Ohne EAN, Farbe, Grösse, Einheit, Artikelnummer, EK und Lieferant -
    genau der Fall „Ware ohne Papiere" (Regel 5, Regel 10, D23)."""
    sessions, codes = daten
    ergebnis = erfasse(sessions, codes, [position()])
    assert ergebnis["positionen"] == 1
    assert ergebnis["neue_varianten"] == 1
    with sessions() as session:
        artikel = session.scalars(select(Artikel)).one()
        assert artikel.lieferant_id is None
        variante = session.scalars(select(Variante)).one()
        assert variante.ean is None
        assert variante.ean_intern is False
        preis = session.scalars(select(Preis)).one()
        assert preis.uvp == Decimal("39.90")
        assert preis.ek is None
        assert preis.dokument_id is None


def test_leere_liste_wird_abgelehnt(daten):
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [])


def test_zu_viele_positionen_werden_abgelehnt(daten):
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position() for _ in range(201)])


def test_unbekanntes_feld_wird_abgelehnt(daten):
    """Serverseitig validieren: Client-Werten wird nie vertraut."""
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position(bestand="999")])


@pytest.mark.parametrize("menge", ["0", "-2", "abc", "1.005", ""])
def test_unplausible_menge_wird_abgelehnt(daten, menge):
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position(menge=menge)])


def test_negativer_preis_wird_abgelehnt(daten):
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position(uvp="-1.00")])


def test_zu_langes_feld_wird_abgelehnt(daten):
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position(marke="N" * 101)])


def test_komma_als_dezimaltrennzeichen(daten):
    """Im Laden wird „39,90" getippt - das muss durchgehen."""
    sessions, codes = daten
    erfasse(sessions, codes, [position(menge="2", uvp="39,90", ek="19,95")])
    with sessions() as session:
        preis = session.scalars(select(Preis)).one()
        assert (preis.uvp, preis.ek) == (Decimal("39.90"), Decimal("19.95"))
        assert session.scalars(select(Bestand.menge)).one() == Decimal("2")


def test_eine_falsche_position_bucht_nichts(daten):
    """Alles oder nichts: eine Transaktion für den ganzen Wareneingang."""
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position(), position(uvp="")])
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Wareneingang)) == 0
        assert session.scalar(select(func.count()).select_from(Variante)) == 0


# --- Bestand, Bewegung, Beleglosigkeit (Regel 2, D27) ----------------------


def test_erfassung_bucht_bestand_und_bewegung_ohne_beleg(daten):
    sessions, codes = daten
    ergebnis = erfasse(sessions, codes, [position(menge="3")])
    with sessions() as session:
        wareneingang = session.scalars(select(Wareneingang)).one()
        # D27: kein Dokument, trotzdem ein vollwertiger Wareneingang.
        assert wareneingang.dokument_id is None
        assert wareneingang.status == "eingetroffen"
        assert wareneingang.lagerort_id == codes["SF1"]
        assert wareneingang.id == ergebnis["wareneingang_id"]

        posten = session.scalars(select(WareneingangPosition)).one()
        assert posten.menge == Decimal("3")
        # Ware ist da: erwartete und eingetroffene Menge sind gleich (D22).
        assert posten.menge_eingetroffen == Decimal("3")

        bewegung = session.scalars(select(Lagerbewegung)).one()
        assert bewegung.typ == "zugang"
        assert bewegung.menge == Decimal("3")
        assert bewegung.grund == GRUND
        assert bewegung.benutzer_kassennummer == "910141"
        assert bewegung.wareneingang_position_id == posten.id

        bestand = session.scalars(select(Bestand)).one()
        assert bestand.menge == Decimal("3")
        assert bestand.aeltestes_eingangsdatum == date.today()


def test_zweite_erfassung_erhoeht_denselben_bestand(daten):
    """Gleiche Marke, gleiche Artikelnummer, gleiche Farbe/Grösse → dieselbe
    Variante (Regel 5, Schlüssel ohne EAN)."""
    sessions, codes = daten
    erfasse(
        sessions,
        codes,
        [position(menge="3", lieferanten_artikelnr="A1", farbe="Weiss", groesse="M")],
    )
    erfasse(
        sessions,
        codes,
        [position(menge="2", lieferanten_artikelnr="A1", farbe="Weiss", groesse="M")],
    )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Variante)) == 1
        assert session.scalars(select(Bestand.menge)).one() == Decimal("5")
        assert session.scalar(select(func.count()).select_from(Wareneingang)) == 2


def test_andere_groesse_ist_eine_eigene_variante(daten):
    sessions, codes = daten
    erfasse(
        sessions,
        codes,
        [
            position(lieferanten_artikelnr="A1", farbe="Weiss", groesse="M"),
            position(lieferanten_artikelnr="A1", farbe="Weiss", groesse="L"),
        ],
    )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Artikel)) == 1
        assert session.scalar(select(func.count()).select_from(Variante)) == 2


def test_ohne_artikelnummer_bleibt_jede_erfassung_ein_eigener_artikel(daten):
    """Ohne Lieferanten-Artikelnummer lässt sich nicht sagen, ob zwei Zeilen
    dasselbe Modell meinen (siehe app/services/artikel.py)."""
    sessions, codes = daten
    erfasse(sessions, codes, [position()])
    erfasse(sessions, codes, [position()])
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Artikel)) == 2


def test_bestand_wird_pro_filiale_gefuehrt(daten):
    """Regel 4: Artikelstamm filialübergreifend, Bestand filialbezogen."""
    sessions, codes = daten
    erfasse(
        sessions, codes, [position(menge="3", ean="4006632041234")], lagerort="SF1"
    )
    erfasse(
        sessions, codes, [position(menge="1", ean="4006632041234")], lagerort="SF2"
    )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Variante)) == 1
        bestaende = {
            b.lagerort_id: b.menge for b in session.scalars(select(Bestand)).all()
        }
    assert bestaende == {codes["SF1"]: Decimal("3"), codes["SF2"]: Decimal("1")}


# --- EAN (Regel 5) ---------------------------------------------------------


def test_neue_ean_wird_uebernommen(daten):
    sessions, codes = daten
    erfasse(sessions, codes, [position(ean="4006632041234")])
    with sessions() as session:
        variante = session.scalars(select(Variante)).one()
        assert variante.ean == "4006632041234"
        assert variante.ean_intern is False


def test_bekannte_ean_wird_wiederverwendet(daten):
    """Die EAN gewinnt: der bestehende Artikelstamm wird nicht überschrieben."""
    sessions, codes = daten
    erfasse(
        sessions,
        codes,
        [position(marke="Nike", bezeichnung="Poloshirt Court", ean="4006632041234")],
    )
    ergebnis = erfasse(
        sessions,
        codes,
        [position(marke="Nike", bezeichnung="Falsch getippt", ean="4006632041234")],
    )
    assert (ergebnis["neue_varianten"], ergebnis["bekannte_varianten"]) == (0, 1)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Variante)) == 1
        artikel = session.scalars(select(Artikel)).one()
        assert artikel.bezeichnung == "Poloshirt Court"
        assert session.scalars(select(Bestand.menge)).one() == Decimal("6")


@pytest.mark.parametrize("ean", ["1234", "abcdefgh", "12345678901", "4006632041234X"])
def test_ungueltige_ean_wird_abgelehnt(daten, ean):
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position(ean=ean)])


def test_zweimal_dieselbe_ean_in_einer_erfassung(daten):
    """Zweimal gescannt (z.B. zwei Kartons) - eine Variante, zwei Positionen."""
    sessions, codes = daten
    erfasse(
        sessions,
        codes,
        [position(menge="2", ean="4006632041234"), position(menge="1", ean="4006632041234")],
    )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Variante)) == 1
        assert session.scalar(select(func.count()).select_from(WareneingangPosition)) == 2
        assert session.scalars(select(Bestand.menge)).one() == Decimal("3")


# --- Eingangsdatum (Regel 6, D13) -----------------------------------------


def test_lager_ohne_verkauf_bekommt_kein_eingangsdatum(daten):
    """Regel 6: Ware an die GEWA startet die Reduktionsuhr noch nicht."""
    sessions, codes = daten
    ergebnis = erfasse(sessions, codes, [position()], lagerort="GEWA")
    assert ergebnis["eingangsdatum"] is None
    with sessions() as session:
        assert session.scalars(select(Wareneingang.eingangsdatum)).one() is None
        assert session.scalars(select(Bestand.aeltestes_eingangsdatum)).one() is None
        # „Gesehen" wurde die Ware trotzdem - das ist keine Lagerdauer.
        assert session.scalars(select(Variante.first_seen)).one() == date.today()


def test_rueckwirkendes_eingangsdatum(daten):
    sessions, codes = daten
    gestern = date.today() - timedelta(days=1)
    ergebnis = erfasse(sessions, codes, [position()], eingangsdatum=gestern)
    assert ergebnis["eingangsdatum"] == gestern.isoformat()
    with sessions() as session:
        assert session.scalars(select(Bestand.aeltestes_eingangsdatum)).one() == gestern
        assert session.scalars(select(Variante.first_seen)).one() == gestern


def test_datum_in_der_zukunft_wird_abgelehnt(daten):
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(
            sessions,
            codes,
            [position()],
            eingangsdatum=date.today() + timedelta(days=1),
        )


# --- Lieferant (optional, D23) --------------------------------------------


def test_lieferant_wird_am_artikel_gespeichert(daten):
    sessions, codes = daten
    with sessions() as session:
        lieferant_id = session.scalar(select(Lieferant.id))
    erfasse(
        sessions, codes, [position(lieferanten_artikelnr="A1")], lieferant_id=lieferant_id
    )
    # Zweite Erfassung mit demselben Lieferanten findet den Artikel wieder.
    erfasse(
        sessions, codes, [position(lieferanten_artikelnr="A1")], lieferant_id=lieferant_id
    )
    with sessions() as session:
        artikel = session.scalars(select(Artikel)).one()
        assert artikel.lieferant_id == lieferant_id


def test_artikel_ohne_lieferant_und_mit_lieferant_bleiben_getrennt(daten):
    sessions, codes = daten
    with sessions() as session:
        lieferant_id = session.scalar(select(Lieferant.id))
    erfasse(sessions, codes, [position(lieferanten_artikelnr="A1")])
    erfasse(
        sessions, codes, [position(lieferanten_artikelnr="A1")], lieferant_id=lieferant_id
    )
    with sessions() as session:
        lieferanten = sorted(
            (a.lieferant_id or 0) for a in session.scalars(select(Artikel)).all()
        )
    assert lieferanten == [0, lieferant_id]


def test_unbekannter_lieferant_wird_abgelehnt(daten):
    sessions, codes = daten
    with pytest.raises(ErfassungRejected):
        erfasse(sessions, codes, [position()], lieferant_id=999999)


def test_unbekannter_lagerort_wird_abgelehnt(daten):
    sessions, _ = daten
    with pytest.raises(ErfassungRejected):
        erfasse_wareneingang(
            [position()], sessions, lagerort_id=999999, benutzer=BENUTZER
        )


# --- Preis und Audit ------------------------------------------------------


def test_ek_wird_gespeichert_wenn_vorhanden(daten):
    """Regel 10: EK optional - aber wenn er da ist, wird er behalten."""
    sessions, codes = daten
    erfasse(sessions, codes, [position(ek="19.95")])
    with sessions() as session:
        preis = session.scalars(select(Preis)).one()
        assert preis.ek == Decimal("19.95")
        posten = session.scalars(select(WareneingangPosition)).one()
        assert posten.ek == Decimal("19.95")


def test_eingabe_wird_als_quelle_protokolliert(daten):
    """Audit wie beim Import: was wurde eingetippt, von wem."""
    sessions, codes = daten
    erfasse(sessions, codes, [position(menge="3", einheit="Stk")])
    with sessions() as session:
        quelle = session.scalars(select(WareneingangPositionQuelle)).one()
    assert quelle.data["quelle"] == GRUND
    assert quelle.data["erfasst_von"] == BENUTZER
    assert quelle.data["eingabe"]["marke"] == "Nike"
    assert quelle.data["eingabe"]["menge"] == "3"
    assert quelle.data["eingabe"]["einheit"] == "Stk"


# --- EAN-Nachschlag für den Scanner ---------------------------------------


def test_nachschlag_findet_bekannte_ean(daten):
    sessions, codes = daten
    erfasse(
        sessions,
        codes,
        [
            position(
                ean="4006632041234",
                farbe="Weiss",
                groesse="M",
                einheit="Stk",
                ek="19.95",
                lieferanten_artikelnr="A1",
            )
        ],
    )
    with sessions() as session:
        treffer = variante_per_ean(session, "4006632041234")
    assert treffer["marke"] == "Nike"
    assert treffer["bezeichnung"] == "Poloshirt Court"
    assert (treffer["farbe"], treffer["groesse"]) == ("Weiss", "M")
    assert treffer["einheit"] == "Stk"
    assert treffer["uvp"] == "39.90"
    assert treffer["ek"] == "19.95"
    assert treffer["lieferanten_artikelnr"] == "A1"
    assert treffer["lieferant"] is None


def test_nachschlag_meldet_unbekannte_ean(daten):
    sessions, _ = daten
    with sessions() as session:
        assert variante_per_ean(session, "4006632041234") is None


@pytest.mark.parametrize("ean", ["", "   ", "12345", "keine-ean"])
def test_nachschlag_prueft_die_eingabe(daten, ean):
    sessions, _ = daten
    with sessions() as session:
        with pytest.raises(ErfassungRejected):
            variante_per_ean(session, ean)


def test_nachschlag_nimmt_den_neuesten_preis(daten):
    sessions, codes = daten
    erfasse(
        sessions,
        codes,
        [position(ean="4006632041234", uvp="39.90")],
        eingangsdatum=date.today() - timedelta(days=30),
    )
    erfasse(sessions, codes, [position(ean="4006632041234", uvp="44.90")])
    with sessions() as session:
        assert variante_per_ean(session, "4006632041234")["uvp"] == "44.90"


# --- API (die Oberfläche geht diesen Weg) ---------------------------------


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


def test_api_stammdaten_liefert_lagerorte_und_lieferanten(client):
    test_client, _, codes = client
    daten = test_client.get("/api/erfassen/stammdaten").json()
    assert [eintrag["code"] for eintrag in daten["lagerorte"]][0] == "SF1"
    # D26: buchbar sind alle Lagerorte - eigene zuerst.
    assert {eintrag["code"] for eintrag in daten["lagerorte"]} == {
        "SF1",
        "SF2",
        "SF3",
        "SF4",
        "GEWA",
        "VEBO",
        "DIETIKON",
    }
    assert daten["lagerort_aktiv"] == codes["SF1"]
    assert daten["lieferanten"][0]["name"] == "INTERSPORT Schweiz AG"
    assert daten["heute"] == date.today().isoformat()


def test_api_mitarbeiter_darf_erfassen(client):
    """Regel 9/D21: Erfassen ist Lagerarbeit - kein Dokument, also erlaubt."""
    test_client, sessions, codes = client
    antwort = test_client.post(
        "/api/erfassen",
        json={
            "positionen": [position(menge="4", ean="4006632041234")],
            "lagerort_id": codes["SF1"],
        },
    )
    assert antwort.status_code == 200, antwort.text
    ergebnis = antwort.json()
    assert ergebnis["positionen"] == 1
    assert ergebnis["lagerort"]["code"] == "SF1"
    assert ergebnis["eingangsdatum"] == date.today().isoformat()
    with sessions() as session:
        assert session.scalars(select(Bestand.menge)).one() == Decimal("4")
        bewegung = session.scalars(select(Lagerbewegung)).one()
        assert bewegung.benutzer_name == "Anna"


def test_api_bucht_auch_auf_die_gewa(client):
    """D26/D11: die GEWA hat kein eigenes Personal - eine Direktlieferung
    dorthin muss von der Filiale aus erfassbar sein."""
    test_client, sessions, codes = client
    antwort = test_client.post(
        "/api/erfassen",
        json={"positionen": [position()], "lagerort_id": codes["GEWA"]},
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["eingangsdatum"] is None


def test_api_lehnt_unbekannten_lagerort_ab(client):
    test_client, _, _ = client
    antwort = test_client.post(
        "/api/erfassen", json={"positionen": [position()], "lagerort_id": 999999}
    )
    assert antwort.status_code == 403


def test_api_meldet_fehlende_pflichtfelder(client):
    test_client, sessions, codes = client
    antwort = test_client.post(
        "/api/erfassen",
        json={"positionen": [position(uvp="")], "lagerort_id": codes["SF1"]},
    )
    assert antwort.status_code == 409
    assert "UVP" in antwort.json()["detail"]
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Wareneingang)) == 0


def test_api_lehnt_unbekannte_felder_ab(client):
    test_client, _, codes = client
    antwort = test_client.post(
        "/api/erfassen",
        json={
            "positionen": [dict(position(), bestand="999")],
            "lagerort_id": codes["SF1"],
        },
    )
    assert antwort.status_code == 422


def test_api_meldet_ein_falsches_datum(client):
    test_client, _, codes = client
    antwort = test_client.post(
        "/api/erfassen",
        json={
            "positionen": [position()],
            "lagerort_id": codes["SF1"],
            "eingangsdatum": "kein-datum",
        },
    )
    assert antwort.status_code == 422


def test_api_variante_nachschlag(client):
    test_client, _, codes = client
    test_client.post(
        "/api/erfassen",
        json={
            "positionen": [position(ean="4006632041234")],
            "lagerort_id": codes["SF1"],
        },
    )
    treffer = test_client.get("/api/erfassen/variante?ean=4006632041234").json()
    assert treffer["gefunden"] is True
    assert treffer["variante"]["bezeichnung"] == "Poloshirt Court"

    unbekannt = test_client.get("/api/erfassen/variante?ean=4006632049999").json()
    assert unbekannt == {"gefunden": False, "variante": None}

    assert test_client.get("/api/erfassen/variante?ean=123").status_code == 422


def test_api_und_seite_brauchen_eine_anmeldung(client):
    test_client, _, _ = client
    test_client.post("/logout")
    assert test_client.get("/api/erfassen/stammdaten").status_code == 401
    assert test_client.get("/api/erfassen/variante?ean=4006632041234").status_code == 401
    assert test_client.post("/api/erfassen", json={"positionen": []}).status_code == 401
    seite = test_client.get("/erfassen", follow_redirects=False)
    assert seite.status_code == 303
    assert seite.headers["location"] == "/login?next=/erfassen"


def test_seite_wird_angemeldet_ausgeliefert(client):
    test_client, _, _ = client
    antwort = test_client.get("/erfassen")
    assert antwort.status_code == 200
    assert 'id="ean"' in antwort.text
