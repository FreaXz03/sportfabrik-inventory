"""Umlagerung (Phase C, Teilaufgabe C4).

Geprüft werden die Datumsregeln: externer Standort → Filiale setzt das
Eingangsdatum und startet die Uhr (D13), Filiale → Filiale behält das Datum
und lässt die Uhr des Ziels in Ruhe (D17, F10) - ausser das Ziel hatte den
Artikel nie (F11). Dazu: beide Seiten sind Zeilen in `lagerbewegungen`
(Regel 2), zu wenig Bestand an der Quelle warnt und bucht trotzdem, und eine
fehlerhafte Umlagerung bucht gar nichts.
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
from app.core.models import (
    Artikel,
    BenutzerLagerort,
    Bestand,
    Lagerbewegung,
    Lagerort,
    User,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from app.main import app
from app.services.reduktion import letzter_wareneingang
from app.services.umlagerung import UmlagerungRejected, umlagern

HEUTE = date.today()


@pytest.fixture
def daten():
    """Poloshirt M und L (ein Artikel): 10 Stück M an der GEWA ohne Datum,
    4 Stück M in SF1 seit 01.03.2026. SF2 hatte das Poloshirt schon einmal
    (Wareneingang 10.01.2025), SF3 noch nie."""
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
        m = Variante(artikel_id=polo.id, farbe="Weiss", groesse="M", ean="4006381333931")
        l = Variante(artikel_id=polo.id, farbe="Weiss", groesse="L")
        session.add_all([m, l])
        session.flush()
        session.add_all(
            [
                Bestand(varianten_id=m.id, lagerort_id=codes["GEWA"], menge=Decimal("10")),
                Bestand(varianten_id=l.id, lagerort_id=codes["GEWA"], menge=Decimal("3")),
                Bestand(
                    varianten_id=m.id,
                    lagerort_id=codes["SF1"],
                    menge=Decimal("4"),
                    aeltestes_eingangsdatum=date(2026, 3, 1),
                ),
                Bestand(
                    varianten_id=m.id,
                    lagerort_id=codes["SF2"],
                    menge=Decimal("0"),
                    aeltestes_eingangsdatum=date(2025, 1, 10),
                ),
            ]
        )
        eingang = Wareneingang(
            lagerort_id=codes["SF2"], status="eingetroffen", eingangsdatum=date(2025, 1, 10)
        )
        session.add(eingang)
        session.flush()
        session.add(
            WareneingangPosition(
                wareneingang_id=eingang.id,
                varianten_id=m.id,
                menge=Decimal("1"),
                menge_eingetroffen=Decimal("1"),
            )
        )
        anna = User(kassennummer="910141", name="Anna", role="mitarbeiter", password_hash=None)
        session.add(anna)
        session.flush()
        session.add(
            BenutzerLagerort(user_id=anna.id, lagerort_id=codes["SF1"], ist_primaer=True)
        )
        ids = {"m": m.id, "l": l.id, "artikel": polo.id}
    yield sessions, codes, ids
    engine.dispose()


def _bestand(sessions, varianten_id, lagerort_id):
    with sessions() as session:
        return session.get(Bestand, (varianten_id, lagerort_id))


def _uhr(sessions, artikel_id, lagerort_id):
    with sessions() as session:
        return letzter_wareneingang(session, artikel_id, lagerort_id)


def _pos(varianten_id, menge="1"):
    return {"varianten_id": varianten_id, "menge": menge}


# --- Datumsregeln ---------------------------------------------------------


def test_extern_nach_filiale_setzt_datum_und_startet_uhr(daten):
    """D13: erst in der Filiale beginnt die Lagerdauer."""
    sessions, codes, ids = daten
    ergebnis = umlagern(
        sessions, quelle_id=codes["GEWA"], ziel_id=codes["SF3"], positionen=[_pos(ids["m"], "6")]
    )
    assert ergebnis["positionen"][0]["uhr_start"] == HEUTE.isoformat()
    assert _bestand(sessions, ids["m"], codes["GEWA"]).menge == Decimal("4")
    ziel = _bestand(sessions, ids["m"], codes["SF3"])
    assert ziel.menge == Decimal("6")
    assert ziel.aeltestes_eingangsdatum == HEUTE
    assert _uhr(sessions, ids["artikel"], codes["SF3"]) == HEUTE


def test_extern_nach_filiale_rueckwirkend(daten):
    sessions, codes, ids = daten
    frueher = date(2026, 9, 1)
    umlagern(
        sessions,
        quelle_id=codes["GEWA"],
        ziel_id=codes["SF3"],
        positionen=[_pos(ids["m"])],
        eingangsdatum=frueher,
    )
    assert _bestand(sessions, ids["m"], codes["SF3"]).aeltestes_eingangsdatum == frueher
    assert _uhr(sessions, ids["artikel"], codes["SF3"]) == frueher


def test_extern_nach_filiale_ist_eine_nachlieferung(daten):
    """Kannte die Filiale den Artikel schon, startet die Ankunft aus der GEWA
    die Uhr neu - wie jede Nachlieferung (Regel 6)."""
    sessions, codes, ids = daten
    umlagern(sessions, quelle_id=codes["GEWA"], ziel_id=codes["SF2"], positionen=[_pos(ids["m"])])
    assert _uhr(sessions, ids["artikel"], codes["SF2"]) == HEUTE
    # Das älteste Datum im Bestand bleibt aber das alte.
    assert _bestand(sessions, ids["m"], codes["SF2"]).aeltestes_eingangsdatum == date(2025, 1, 10)


def test_eingangsdatum_in_der_zukunft_wird_abgelehnt(daten):
    sessions, codes, ids = daten
    with pytest.raises(UmlagerungRejected):
        umlagern(
            sessions,
            quelle_id=codes["GEWA"],
            ziel_id=codes["SF3"],
            positionen=[_pos(ids["m"])],
            eingangsdatum=HEUTE + timedelta(days=1),
        )


def test_filiale_nach_filiale_laesst_die_uhr_des_ziels_in_ruhe(daten):
    """F10: SF2 kennt das Poloshirt - die Uhr läuft ab dem 10.01.2025 weiter,
    die Ware wird dort mitreduziert."""
    sessions, codes, ids = daten
    ergebnis = umlagern(
        sessions, quelle_id=codes["SF1"], ziel_id=codes["SF2"], positionen=[_pos(ids["m"], "2")]
    )
    assert ergebnis["positionen"][0]["uhr_start"] is None
    assert _uhr(sessions, ids["artikel"], codes["SF2"]) == date(2025, 1, 10)
    assert _bestand(sessions, ids["m"], codes["SF2"]).menge == Decimal("2")


def test_filiale_nach_filiale_verjuengt_nichts(daten):
    """D17: die Ware behält ihr Datum - auch im Bestand des Ziels."""
    sessions, codes, ids = daten
    umlagern(sessions, quelle_id=codes["SF1"], ziel_id=codes["SF3"], positionen=[_pos(ids["m"])])
    assert _bestand(sessions, ids["m"], codes["SF3"]).aeltestes_eingangsdatum == date(2026, 3, 1)


def test_filiale_ohne_bisherigen_eingang_startet_uhr_ab_eintreffen(daten):
    """F11 (23.09.2026): SF3 hatte das Poloshirt nie - die Uhr startet heute."""
    sessions, codes, ids = daten
    ergebnis = umlagern(
        sessions, quelle_id=codes["SF1"], ziel_id=codes["SF3"], positionen=[_pos(ids["m"])]
    )
    assert ergebnis["positionen"][0]["uhr_start"] == HEUTE.isoformat()
    assert _uhr(sessions, ids["artikel"], codes["SF3"]) == HEUTE


def test_f11_gilt_je_artikel_nicht_je_variante(daten):
    """Zwei Grössen desselben Artikels in einer Umlagerung: beide starten die
    Uhr, nicht nur die erste."""
    sessions, codes, ids = daten
    umlagern(
        sessions,
        quelle_id=codes["SF1"],
        ziel_id=codes["SF3"],
        positionen=[_pos(ids["m"]), _pos(ids["l"])],
    )
    with sessions() as session:
        daten_ziel = session.scalars(
            select(Lagerbewegung.eingangsdatum).where(
                Lagerbewegung.lagerort_id == codes["SF3"]
            )
        ).all()
    assert daten_ziel == [HEUTE, HEUTE]


def test_nach_externem_standort_kein_datum(daten):
    """Regel 6: an einem Standort ohne Verkauf läuft keine Uhr."""
    sessions, codes, ids = daten
    ergebnis = umlagern(
        sessions, quelle_id=codes["SF1"], ziel_id=codes["DIETIKON"], positionen=[_pos(ids["m"])]
    )
    assert ergebnis["positionen"][0]["uhr_start"] is None
    ziel = _bestand(sessions, ids["m"], codes["DIETIKON"])
    assert ziel.menge == Decimal("1")
    assert ziel.aeltestes_eingangsdatum is None


# --- Buchung --------------------------------------------------------------


def test_beide_seiten_sind_umlagerungs_bewegungen(daten):
    sessions, codes, ids = daten
    umlagern(
        sessions,
        quelle_id=codes["GEWA"],
        ziel_id=codes["SF1"],
        positionen=[_pos(ids["m"], "3")],
        benutzer={"kassennummer": "910141", "name": "Anna"},
    )
    with sessions() as session:
        bewegungen = session.scalars(
            select(Lagerbewegung).order_by(Lagerbewegung.id)
        ).all()
    assert [(b.typ, b.menge, b.grund) for b in bewegungen] == [
        ("umlagerung", Decimal("-3"), "nach:SF1"),
        ("umlagerung", Decimal("3"), "von:GEWA"),
    ]
    assert {b.benutzer_name for b in bewegungen} == {"Anna"}
    # Die Quelle startet nie eine Uhr.
    assert bewegungen[0].eingangsdatum is None


def test_mehrfach_gescannt_wird_zusammengezaehlt(daten):
    sessions, codes, ids = daten
    ergebnis = umlagern(
        sessions,
        quelle_id=codes["GEWA"],
        ziel_id=codes["SF1"],
        positionen=[_pos(ids["m"]), _pos(ids["m"]), _pos(ids["m"])],
    )
    assert ergebnis["stueck"] == "3.00"
    assert len(ergebnis["positionen"]) == 1
    assert _bestand(sessions, ids["m"], codes["SF1"]).menge == Decimal("7")


def test_zu_wenig_bestand_an_der_quelle_warnt_und_bucht(daten):
    sessions, codes, ids = daten
    ergebnis = umlagern(
        sessions, quelle_id=codes["SF1"], ziel_id=codes["SF3"], positionen=[_pos(ids["m"], "6")]
    )
    assert len(ergebnis["fehlbestand"]) == 1
    assert _bestand(sessions, ids["m"], codes["SF1"]).menge == Decimal("-2")
    assert _bestand(sessions, ids["m"], codes["SF3"]).menge == Decimal("6")


@pytest.mark.parametrize(
    "positionen",
    [
        [],
        [{"varianten_id": 1, "menge": "0"}],
        [{"varianten_id": 1, "menge": "-1"}],
        [{"varianten_id": 1, "menge": "1.001"}],
        [{"varianten_id": 1, "menge": "abc"}],
        [{"menge": "1"}],
    ],
)
def test_ungueltige_positionen_buchen_nichts(daten, positionen):
    sessions, codes, _ = daten
    with pytest.raises(UmlagerungRejected):
        umlagern(sessions, quelle_id=codes["GEWA"], ziel_id=codes["SF1"], positionen=positionen)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 0


def test_unbekannte_variante_bucht_gar_nichts(daten):
    """Ganz oder gar nicht: eine falsche Position hält die ganze Umlagerung auf."""
    sessions, codes, ids = daten
    with pytest.raises(UmlagerungRejected):
        umlagern(
            sessions,
            quelle_id=codes["GEWA"],
            ziel_id=codes["SF1"],
            positionen=[_pos(ids["m"]), _pos(9999)],
        )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 0
    assert _bestand(sessions, ids["m"], codes["GEWA"]).menge == Decimal("10")


def test_quelle_gleich_ziel_wird_abgelehnt(daten):
    sessions, codes, ids = daten
    with pytest.raises(UmlagerungRejected):
        umlagern(sessions, quelle_id=codes["SF1"], ziel_id=codes["SF1"], positionen=[_pos(ids["m"])])


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


def test_api_stammdaten_schlaegt_die_aktive_filiale_als_ziel_vor(client):
    test_client, _, codes, _ = client
    body = test_client.get("/api/umlagerung/stammdaten").json()
    assert body["ziel_aktiv"] == codes["SF1"]
    assert {lo["code"] for lo in body["quellen"]} >= {"GEWA", "VEBO", "DIETIKON", "SF2"}
    assert body["heute"] == HEUTE.isoformat()


def test_api_mitarbeiter_empfaengt_in_der_aktiven_filiale(client):
    """F5: die empfangende Filiale bucht - ohne Ziel gilt die aktive."""
    test_client, sessions, codes, ids = client
    antwort = test_client.post(
        "/api/umlagerung",
        json={"quelle_id": codes["GEWA"], "positionen": [{"varianten_id": ids["m"], "menge": "2"}]},
    )
    assert antwort.status_code == 200
    assert antwort.json()["ziel"]["code"] == "SF1"
    assert _bestand(sessions, ids["m"], codes["SF1"]).menge == Decimal("6")


def test_api_meldet_fehler(client):
    test_client, _, codes, ids = client
    antwort = test_client.post(
        "/api/umlagerung",
        json={"quelle_id": codes["SF1"], "positionen": [{"varianten_id": ids["m"], "menge": "1"}]},
    )
    assert antwort.status_code == 409
    antwort = test_client.post(
        "/api/umlagerung",
        json={
            "quelle_id": codes["GEWA"],
            "eingangsdatum": "kein-datum",
            "positionen": [{"varianten_id": ids["m"], "menge": "1"}],
        },
    )
    assert antwort.status_code == 422


def test_api_verlangt_eine_anmeldung(client):
    test_client, _, codes, ids = client
    test_client.post("/logout")
    assert test_client.post(
        "/api/umlagerung",
        json={"quelle_id": codes["GEWA"], "positionen": [{"varianten_id": ids["m"], "menge": "1"}]},
    ).status_code == 401
