"""Interne EAN und Etikett (Phase B, Teilaufgabe B7 — Regel 5, D10, D14,
D24, D25).

Drei Ebenen: die reine Rechnerei (Prüfziffer, Strichmuster, Reduktionsstufe),
das zusammengesetzte Etikett als PDF und der Weg über die API, den die
Oberfläche geht.
"""

from datetime import date, timedelta
from decimal import Decimal

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.database as database
from app.core.database import Base, get_session
from app.core.i18n import translate
from app.core.lagerorte import seed_lagerorte
from app.core.lieferanten import seed_lieferanten
from app.core.models import (
    Artikel,
    BenutzerLagerort,
    Lagerort,
    Lieferant,
    User,
    Variante,
    Wareneingang,
)
from app.main import app
from app.services.barcode import (
    G_CODES,
    L_CODES,
    R_CODES,
    BarcodeNichtDruckbar,
    druckbare_nummer,
    strichmuster,
)
from app.services.ean import (
    EanError,
    EanNichtGefunden,
    interne_ean,
    ist_intern,
    pruefe_nachgetragene_ean,
    pruefziffer,
    pruefziffer_stimmt,
    setze_ean,
)
from app.services.etikett import (
    STANDARD_GROESSE,
    Etikett,
    EtikettError,
    etiketten_pdf,
    sammle_etikett,
)
from app.services.manuelle_erfassung import erfasse_wareneingang
from app.services.reduktion import letzter_wareneingang, monate_seit, stufe

BENUTZER = {"kassennummer": "910141", "name": "Anna"}

# Echte, gültige Nummern zum Gegenrechnen.
GUELTIG = ["5901234123457", "4006381333931", "96385074", "012345678905"]


# --- Prüfziffer und interne EAN (Regel 5, D10) ----------------------------


@pytest.mark.parametrize("ean", GUELTIG)
def test_pruefziffer_bekannter_nummern(ean):
    assert pruefziffer_stimmt(ean)
    assert pruefziffer(ean[:-1]) == int(ean[-1])


@pytest.mark.parametrize(
    "ean", ["5901234123458", "4006381333930", "96385075", "", "keine-zahl", "123"]
)
def test_falsche_pruefziffer_wird_erkannt(ean):
    assert not pruefziffer_stimmt(ean)


@pytest.mark.parametrize("varianten_id", [1, 7, 42, 999999])
def test_interne_ean_ist_gueltig_und_im_hausbereich(varianten_id):
    """D10: EAN-13 im GS1-Bereich 20-29 mit korrekter Prüfziffer."""
    ean = interne_ean(varianten_id)
    assert len(ean) == 13
    assert ean.startswith("20")
    assert pruefziffer_stimmt(ean)
    assert ist_intern(ean)
    # Dieselbe Variante bekommt immer dieselbe Nummer.
    assert interne_ean(varianten_id) == ean


def test_interne_eans_verschiedener_varianten_unterscheiden_sich():
    assert len({interne_ean(i) for i in range(1, 200)}) == 199


def test_hersteller_ean_gilt_nicht_als_intern():
    assert not ist_intern("4006381333931")


@pytest.mark.parametrize(
    "ean", ["", "   ", "abcdefgh", "12345", "5901234123458", "4006381333930"]
)
def test_nachgetragene_ean_wird_streng_geprueft(ean):
    """Anders als beim Import (dort steht die Nummer im Dokument) wird hier
    bewusst getippt - ein Zahlendreher bliebe sonst für immer im Stamm."""
    with pytest.raises(EanError):
        pruefe_nachgetragene_ean(ean)


@pytest.mark.parametrize("ean", GUELTIG)
def test_gueltige_nachgetragene_ean_kommt_zurueck(ean):
    assert pruefe_nachgetragene_ean(f"  {ean} ") == ean


# --- Strichmuster ---------------------------------------------------------


def test_codetabellen_haengen_zusammen():
    """Selbsttest der Tabellen: rechts ist das Gegenteil von links, die
    gerade Parität ist die rechte Tabelle rückwärts."""
    for ziffer, links in L_CODES.items():
        assert len(links) == 7
        assert R_CODES[ziffer] == "".join("1" if z == "0" else "0" for z in links)
        assert G_CODES[ziffer] == R_CODES[ziffer][::-1]


def test_ean13_strichmuster_hat_die_normstruktur():
    muster = strichmuster("5901234123457")
    assert len(muster) == 95
    assert muster.startswith("101") and muster.endswith("101")
    assert muster[45:50] == "01010"  # Trennzeichen in der Mitte
    # Erste Ziffer 5 → Parität ABBAAB; die 9 steht also in der linken Tabelle.
    assert muster[3:10] == L_CODES["9"]
    assert muster[10:17] == G_CODES["0"]


def test_ean8_strichmuster():
    muster = strichmuster("96385074")
    assert len(muster) == 67
    assert muster[3:10] == L_CODES["9"]
    assert muster[-10:-3] == R_CODES["4"]


def test_upc_wird_als_ean13_gedruckt():
    assert druckbare_nummer("012345678905") == "0012345678905"
    assert len(strichmuster("012345678905")) == 95


@pytest.mark.parametrize(
    "code", ["20000000000175", "5901234123458", "abcdefghijklm", "", None]
)
def test_nicht_druckbare_nummern(code):
    """EAN-14 (Umkarton) ist ITF-14, keine EAN - und eine falsche Prüfziffer
    ergäbe einen Strichcode, den keine Kasse annimmt."""
    with pytest.raises(BarcodeNichtDruckbar):
        strichmuster(code)
    assert druckbare_nummer(code) is None


# --- Reduktionsstufe (Regel 6) --------------------------------------------


@pytest.mark.parametrize(
    "eingang,erwartet",
    [
        (date(2026, 9, 21), 0),
        (date(2025, 3, 22), 0),   # einen Tag zu jung für 18 Monate
        (date(2025, 3, 21), 50),  # genau 18 Monate
        (date(2023, 9, 22), 50),  # einen Tag zu jung für 36 Monate
        (date(2023, 9, 21), 70),  # genau 36 Monate
        (None, 0),
    ],
)
def test_reduktionsstufe(eingang, erwartet):
    assert stufe(eingang, date(2026, 9, 21)) == erwartet


def test_monate_seit_zaehlt_volle_monate():
    assert monate_seit(date(2026, 1, 31), date(2026, 2, 28)) == 0
    assert monate_seit(date(2026, 1, 15), date(2026, 2, 15)) == 1
    assert monate_seit(date(2026, 9, 21), date(2026, 9, 1)) == 0


# --- Daten für die Datenbank-Tests ----------------------------------------


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


def erfasse(sessions, codes, lagerort="SF1", eingangsdatum=None, **felder):
    """Eine Position von Hand erfassen (Teilaufgabe B6) - so entstehen
    Artikel, Variante, Preis und Wareneingang in einem Rutsch."""
    position = {
        "marke": "Nike",
        "bezeichnung": "Poloshirt Court",
        "menge": "3",
        "uvp": "39.90",
        **felder,
    }
    return erfasse_wareneingang(
        [position],
        sessions,
        lagerort_id=codes[lagerort],
        benutzer=BENUTZER,
        eingangsdatum=eingangsdatum,
    )


def _varianten_id(sessions):
    with sessions() as session:
        return session.scalars(select(Variante.id).order_by(Variante.id)).first()


# --- Letzter Wareneingang je Filiale (Regel 6) ----------------------------


def test_letzter_wareneingang_nimmt_das_spaeteste_datum_dieser_filiale(daten):
    sessions, codes = daten
    alt = date.today() - timedelta(days=400)
    neu = date.today() - timedelta(days=30)
    erfasse(sessions, codes, lieferanten_artikelnr="A1", eingangsdatum=alt)
    erfasse(sessions, codes, lieferanten_artikelnr="A1", eingangsdatum=neu)
    # Andere Filiale und Lager ohne Verkauf dürfen die Uhr nicht beeinflussen.
    erfasse(sessions, codes, lagerort="SF2", lieferanten_artikelnr="A1")
    erfasse(sessions, codes, lagerort="GEWA", lieferanten_artikelnr="A1")
    with sessions() as session:
        artikel_id = session.scalars(select(Artikel.id)).first()
        assert letzter_wareneingang(session, artikel_id, codes["SF1"]) == neu
        assert letzter_wareneingang(session, artikel_id, codes["GEWA"]) is None
        assert letzter_wareneingang(session, artikel_id, codes["SF3"]) is None


def test_nachlieferung_startet_die_uhr_neu(daten):
    """Regel 6: eine Nachlieferung derselben Artikelnummer setzt die
    Lagerdauer in dieser Filiale zurück."""
    sessions, codes = daten
    erfasse(
        sessions,
        codes,
        lieferanten_artikelnr="A1",
        eingangsdatum=date.today() - timedelta(days=1200),
    )
    with sessions() as session:
        artikel_id = session.scalars(select(Artikel.id)).first()
        assert stufe(letzter_wareneingang(session, artikel_id, codes["SF1"])) == 70
    erfasse(sessions, codes, lieferanten_artikelnr="A1")
    with sessions() as session:
        assert stufe(letzter_wareneingang(session, artikel_id, codes["SF1"])) == 0


# --- Etikett zusammenstellen (D25) ----------------------------------------


def test_etikett_enthaelt_die_vier_pflichtangaben(daten):
    sessions, codes = daten
    with sessions() as session:
        lieferant_id = session.scalar(select(Lieferant.id))
    erfasse_wareneingang(
        [
            {
                "marke": "Nike",
                "bezeichnung": "Poloshirt Court",
                "menge": "3",
                "uvp": "39.90",
                "farbe": "Weiss",
                "groesse": "M",
                "ean": "4006381333931",
            }
        ],
        sessions,
        lagerort_id=codes["SF1"],
        benutzer=BENUTZER,
        eingangsdatum=date(2024, 5, 4),
        lieferant_id=lieferant_id,
    )
    with sessions() as session:
        etikett = sammle_etikett(
            session, _varianten_id(sessions), codes["SF1"], heute=date(2026, 9, 21)
        )
    assert etikett.jahrgang == 2024                     # Jahrgang (D25)
    assert etikett.lieferant == "INTERSPORT Schweiz AG"  # Lieferant (D25)
    assert etikett.uvp == Decimal("39.90")              # UVP (D25)
    assert etikett.reduktion == 50                      # Reduktionsstufe (D25)
    assert (etikett.marke, etikett.groesse, etikett.ean) == ("Nike", "M", "4006381333931")


def test_etikett_nimmt_den_neuesten_preis(daten):
    sessions, codes = daten
    erfasse(sessions, codes, ean="4006381333931", uvp="39.90",
            eingangsdatum=date.today() - timedelta(days=60))
    erfasse(sessions, codes, ean="4006381333931", uvp="29.90")
    with sessions() as session:
        assert sammle_etikett(session, _varianten_id(sessions), codes["SF1"]).uvp == Decimal("29.90")


def test_reduktion_von_hand_schlaegt_den_vorschlag(daten):
    """D25 nennt auch 30 % - das ist eine Entscheidung des Ladens, keine
    Zeitregel, und muss sich deshalb mitgeben lassen."""
    sessions, codes = daten
    erfasse(sessions, codes, eingangsdatum=date.today() - timedelta(days=1200))
    with sessions() as session:
        varianten_id = _varianten_id(sessions)
        assert sammle_etikett(session, varianten_id, codes["SF1"]).reduktion == 70
        assert sammle_etikett(session, varianten_id, codes["SF1"], reduktion=30).reduktion == 30
        assert sammle_etikett(session, varianten_id, codes["SF1"], reduktion=0).reduktion == 0


def test_ohne_filiale_kein_jahrgang_und_keine_reduktion(daten):
    sessions, codes = daten
    erfasse(sessions, codes, eingangsdatum=date.today() - timedelta(days=1200))
    with sessions() as session:
        etikett = sammle_etikett(session, _varianten_id(sessions))
    assert etikett.jahrgang is None and etikett.reduktion == 0


def test_unbekannte_variante(daten):
    sessions, _ = daten
    with sessions() as session:
        with pytest.raises(EtikettError):
            sammle_etikett(session, 999999)


# --- Etikett als PDF (D14) ------------------------------------------------


def _text(pdf: bytes, seite: int = 0) -> str:
    return pymupdf.open("pdf", pdf)[seite].get_text()


def test_pdf_hat_etikettengroesse_und_inhalt():
    pdf = etiketten_pdf(
        [
            Etikett(
                marke="Nike",
                bezeichnung="Poloshirt Court",
                farbe="Weiss",
                groesse="M",
                lieferant="INTERSPORT Schweiz AG",
                uvp=Decimal("39.90"),
                jahrgang=2024,
                reduktion=50,
                ean="2000000000077",
                ean_intern=True,
            )
        ]
    )
    assert pdf.startswith(b"%PDF")
    seite = pymupdf.open("pdf", pdf)[0]
    # 50 × 30 mm in PDF-Punkten (1 mm = 72/25.4 pt).
    assert round(seite.rect.width, 1) == 141.7
    assert round(seite.rect.height, 1) == 85.0
    text = seite.get_text()
    for erwartet in ("Nike", "2024", "INTERSPORT Schweiz AG", "CHF 39.90", "-50%", "2000000000077"):
        assert erwartet in text


def test_anzahl_ergibt_mehrere_seiten():
    pdf = etiketten_pdf([Etikett(marke="Nike", uvp=Decimal("10.00"), anzahl=3)])
    assert pymupdf.open("pdf", pdf).page_count == 3


def test_ohne_ean_steht_der_hinweis_auf_dem_etikett():
    pdf = etiketten_pdf([Etikett(marke="Nike", hinweis="ohne EAN")])
    assert "ohne EAN" in _text(pdf)


def test_nicht_druckbare_ean_kommt_wenigstens_als_zahl_aufs_etikett():
    pdf = etiketten_pdf([Etikett(marke="Nike", ean="20000000000175")])
    assert "20000000000175" in _text(pdf)


def test_zu_lange_bezeichnung_wird_gekuerzt():
    pdf = etiketten_pdf([Etikett(marke="Nike", bezeichnung="X" * 200)])
    assert "..." in _text(pdf)


def test_andere_etikettengroesse():
    pdf = etiketten_pdf([Etikett(marke="Nike")], "100x50")
    seite = pymupdf.open("pdf", pdf)[0]
    assert round(seite.rect.width) == 283 and round(seite.rect.height) == 142


@pytest.mark.parametrize(
    "etiketten,groesse",
    [([], STANDARD_GROESSE), ([Etikett(marke="Nike")], "17x4"),
     ([Etikett(marke="Nike", anzahl=100)] * 6, STANDARD_GROESSE)],
)
def test_unmoegliche_druckauftraege(etiketten, groesse):
    with pytest.raises(EtikettError):
        etiketten_pdf(etiketten, groesse)


# --- EAN setzen (D24) -----------------------------------------------------


def test_interne_ean_wird_gesetzt_und_markiert(daten):
    sessions, codes = daten
    erfasse(sessions, codes)
    varianten_id = _varianten_id(sessions)
    ergebnis = setze_ean(varianten_id, sessions, generieren=True)
    assert ergebnis["ean"] == interne_ean(varianten_id)
    assert ergebnis["ean_intern"] is True
    with sessions() as session:
        variante = session.get(Variante, varianten_id)
        assert variante.ean == ergebnis["ean"] and variante.ean_intern


def test_vorhandene_ean_wird_nie_ueberschrieben(daten):
    """Regel 4: der Artikelstamm bleibt - und eine gedruckte Nummer klebt
    bereits auf der Ware."""
    sessions, codes = daten
    erfasse(sessions, codes, ean="4006381333931")
    varianten_id = _varianten_id(sessions)
    with pytest.raises(EanError):
        setze_ean(varianten_id, sessions, generieren=True)
    with pytest.raises(EanError):
        setze_ean(varianten_id, sessions, ean="5901234123457")


def test_ean_nachtragen(daten):
    sessions, codes = daten
    erfasse(sessions, codes)
    ergebnis = setze_ean(_varianten_id(sessions), sessions, ean="5901234123457")
    assert ergebnis == {
        "varianten_id": _varianten_id(sessions),
        "ean": "5901234123457",
        "ean_intern": False,
    }


def test_ean_einer_anderen_variante_wird_abgelehnt(daten):
    sessions, codes = daten
    erfasse(sessions, codes, ean="4006381333931")
    erfasse(sessions, codes, bezeichnung="Zweiter Artikel")
    with sessions() as session:
        ohne_ean = session.scalars(
            select(Variante.id).where(Variante.ean.is_(None))
        ).one()
    with pytest.raises(EanError):
        setze_ean(ohne_ean, sessions, ean="4006381333931")


def test_unbekannte_variante_beim_setzen(daten):
    sessions, _ = daten
    with pytest.raises(EanNichtGefunden):
        setze_ean(999999, sessions, generieren=True)


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


def test_api_mitarbeiter_erzeugt_interne_ean(client):
    """Regel 9/D21: Ware scannbar machen ist Lagerarbeit, kein Dokument."""
    test_client, sessions, codes = client
    erfasse(sessions, codes)
    varianten_id = _varianten_id(sessions)
    antwort = test_client.post(
        f"/api/varianten/{varianten_id}/ean", json={"generieren": True}
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["ean"] == interne_ean(varianten_id)
    # Zweimal geht nicht.
    assert test_client.post(
        f"/api/varianten/{varianten_id}/ean", json={"generieren": True}
    ).status_code == 409


def test_api_ean_nachtragen_und_pruefziffer(client):
    test_client, sessions, codes = client
    erfasse(sessions, codes)
    varianten_id = _varianten_id(sessions)
    falsch = test_client.post(
        f"/api/varianten/{varianten_id}/ean", json={"ean": "5901234123458"}
    )
    assert falsch.status_code == 409
    gut = test_client.post(
        f"/api/varianten/{varianten_id}/ean", json={"ean": "5901234123457"}
    )
    assert gut.status_code == 200 and gut.json()["ean_intern"] is False


def test_api_unbekannte_variante(client):
    test_client, _, _ = client
    assert test_client.post("/api/varianten/999999/ean", json={"generieren": True}).status_code == 404
    antwort = test_client.get("/api/varianten/999999/etikett")
    assert antwort.status_code == 404
    # Regel 7: auch Fehlermeldungen kommen in der Sprache des Kontos.
    assert antwort.json()["detail"] == translate(
        "errors.etikett.variante_not_found", "de", id=999999
    )
    test_client.post("/api/language", json={"language": "fr"})
    franzoesisch = test_client.get("/api/varianten/999999/etikett")
    assert franzoesisch.json()["detail"] == translate(
        "errors.etikett.variante_not_found", "fr", id=999999
    )


def test_api_etikett_daten(client):
    test_client, sessions, codes = client
    erfasse(sessions, codes, ean="4006381333931",
            eingangsdatum=date.today() - timedelta(days=1200))
    daten = test_client.get(f"/api/varianten/{_varianten_id(sessions)}/etikett").json()
    assert daten["marke"] == "Nike"
    assert daten["uvp"] == "39.90"          # Text, nie float
    assert daten["reduktion"] == 70
    assert daten["jahrgang"] == (date.today() - timedelta(days=1200)).year
    assert daten["barcode"] is True
    assert daten["lagerort"]["code"] == "SF1"
    assert STANDARD_GROESSE in daten["groessen"]


def test_api_etikett_pdf(client):
    test_client, sessions, codes = client
    erfasse(sessions, codes, ean="4006381333931")
    antwort = test_client.get(
        f"/api/varianten/{_varianten_id(sessions)}/etikett.pdf?anzahl=2"
    )
    assert antwort.status_code == 200
    assert antwort.headers["content-type"] == "application/pdf"
    assert antwort.content.startswith(b"%PDF")
    assert pymupdf.open("pdf", antwort.content).page_count == 2


def test_api_etikett_pdf_prueft_groesse_und_reduktion(client):
    test_client, sessions, codes = client
    erfasse(sessions, codes)
    basis = f"/api/varianten/{_varianten_id(sessions)}/etikett.pdf"
    assert test_client.get(basis + "?groesse=17x4").status_code == 422
    assert test_client.get(basis + "?reduktion=42").status_code == 422
    assert test_client.get(basis + "?reduktion=30").status_code == 200


def test_api_etiketten_eines_wareneingangs(client):
    """Der Weg nach der manuellen Erfassung: erfassen, dann auszeichnen."""
    test_client, sessions, codes = client
    ergebnis = erfasse_wareneingang(
        [
            {"marke": "Nike", "bezeichnung": "Poloshirt", "menge": "3", "uvp": "39.90"},
            {"marke": "Nike", "bezeichnung": "Socken", "menge": "2", "uvp": "14.90"},
        ],
        sessions,
        lagerort_id=codes["SF1"],
        benutzer=BENUTZER,
    )
    pfad = f"/api/wareneingaenge/{ergebnis['wareneingang_id']}/etiketten.pdf"
    je_stueck = test_client.get(pfad)
    assert je_stueck.status_code == 200
    assert pymupdf.open("pdf", je_stueck.content).page_count == 5  # 3 + 2 Stück
    je_position = test_client.get(pfad + "?je_stueck=false")
    assert pymupdf.open("pdf", je_position.content).page_count == 2


def test_api_etiketten_eines_erwarteten_wareneingangs(client):
    """Was noch nicht da ist, wird nicht ausgezeichnet (Regel 3)."""
    test_client, sessions, codes = client
    with sessions.begin() as session:
        wareneingang = Wareneingang(
            dokument_id=None, lagerort_id=codes["SF1"], status="erwartet"
        )
        session.add(wareneingang)
        session.flush()
        wareneingang_id = wareneingang.id
    assert test_client.get(
        f"/api/wareneingaenge/{wareneingang_id}/etiketten.pdf"
    ).status_code == 404
    assert test_client.get("/api/wareneingaenge/999999/etiketten.pdf").status_code == 404


def test_api_braucht_eine_anmeldung(client):
    test_client, sessions, codes = client
    erfasse(sessions, codes)
    varianten_id = _varianten_id(sessions)
    test_client.post("/logout")
    assert test_client.get(f"/api/varianten/{varianten_id}/etikett").status_code == 401
    assert test_client.get(f"/api/varianten/{varianten_id}/etikett.pdf").status_code == 401
    assert test_client.post(
        f"/api/varianten/{varianten_id}/ean", json={"generieren": True}
    ).status_code == 401
