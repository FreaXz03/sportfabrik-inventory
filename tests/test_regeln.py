"""Harte Regeln als kleine Tabellen-Tests: EAN-Prüfziffer und interne EAN,
Strichcode, Reduktionsuhr, FEDAS-Vorschlag, Lieferantencodes, Lieferadresse,
Passwörter und vollständige Übersetzungen.

Alles andere prüfen die Ablauf-Tests (tests/test_ablauf_*.py).
"""

import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import neue_datenbank
from sqlalchemy import select
from testbelege import POSITIONEN, kopf, rechnung_pdf

from app.core.fedas import suggest_kategorie
from app.core.i18n import DEFAULT_LANGUAGE, LANGUAGES, translate
from app.core.lagerorte import LAGERORTE_SEED
from app.core.lieferanten import ETIKETT_CODES, LIEFERANTEN_SEED, etikett_code
from app.core.models import Artikel, Bestand, Lagerort
from app.core.security import hash_password, verify_password
from app.services.barcode import BarcodeNichtDruckbar, druckbare_nummer, strichmuster
from app.services.ean import EanError, interne_ean, ist_intern, pruefe_nachgetragene_ean, pruefziffer_stimmt
from app.services.importer import import_invoice
from app.services.lieferadresse import LagerortAdresse, erkenne_lagerort
from app.services.reduktion import letzter_wareneingang, monate_seit, stufe

ROOT = Path(__file__).resolve().parents[1]

# --- EAN (Regel 5, D10) ---------------------------------------------------

GUELTIG = ["5901234123457", "4006381333931", "96385074", "012345678905"]


@pytest.mark.parametrize("ean", GUELTIG)
def test_gueltige_ean(ean):
    assert pruefziffer_stimmt(ean)
    assert pruefe_nachgetragene_ean(f"  {ean} ") == ean
    assert strichmuster(ean)


@pytest.mark.parametrize("ean", ["", "abcdefgh", "12345", "5901234123458", "4006381333930"])
def test_nachgetragene_ean_wird_streng_geprueft(ean):
    """Getippt wird von Hand - ein Zahlendreher bliebe sonst für immer."""
    with pytest.raises(EanError):
        pruefe_nachgetragene_ean(ean)


def test_interne_ean_ist_gueltig_eindeutig_und_im_hausbereich():
    """EAN-13 im GS1-Bereich 20–29 mit korrekter Prüfziffer (Regel 5)."""
    nummern = [interne_ean(varianten_id) for varianten_id in (1, 7, 42, 999999)]
    assert len(set(nummern)) == 4
    for ean in nummern:
        assert len(ean) == 13 and ean[0] == "2" and pruefziffer_stimmt(ean) and ist_intern(ean)
    assert not ist_intern("4006381333931")


def test_strichcode_nur_fuer_druckbare_nummern():
    muster = strichmuster("5901234123457")
    assert len(muster) == 95 and muster.startswith("101") and muster[45:50] == "01010"
    assert druckbare_nummer("012345678905") == "0012345678905"  # UPC als EAN-13
    for code in ("20000000000175", "5901234123458", "", None):
        assert druckbare_nummer(code) is None
        with pytest.raises(BarcodeNichtDruckbar):
            strichmuster(code)


# --- Reduktionsuhr (Regel 6) ----------------------------------------------


@pytest.mark.parametrize(
    "eingang,erwartet",
    [
        (date(2026, 9, 21), 0),
        (date(2025, 3, 22), 0),  # einen Tag zu jung für 18 Monate
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


def test_nachlieferung_startet_die_uhr_neu_nur_in_derselben_filiale():
    """Regel 6: ab letztem Wareneingang derselben Artikelnummer in dieser
    Filiale; eine Nachlieferung (auch eine andere Variante) startet neu."""
    sessions = neue_datenbank()
    with sessions() as session:
        codes = {lo.code: lo.id for lo in session.scalars(select(Lagerort))}

    def liefern(nummer, datum, lagerort, rows):
        pdf = rechnung_pdf(header_lines=kopf(nummer=nummer, datum=datum), rows=rows)
        import_invoice(pdf, "b.pdf", hashlib.sha256(pdf).hexdigest(), sessions, codes[lagerort])

    liefern("9000000001", "05.02.2024", "SF1", POSITIONEN)
    liefern("9000000002", "05.03.2026", "SF1", POSITIONEN[1:2])  # nur Grösse L nach
    liefern("9000000003", "05.09.2026", "SF2", POSITIONEN[:1])
    liefern("9000000004", "05.01.2020", "GEWA", POSITIONEN[:1])  # extern: kein Datum
    with sessions() as session:
        polo = session.scalar(select(Artikel.id).where(Artikel.lieferanten_artikelnr == "A1"))
        schuh = session.scalar(select(Artikel.id).where(Artikel.lieferanten_artikelnr == "B2"))
        assert letzter_wareneingang(session, polo, codes["SF1"]) == date(2026, 3, 5)
        assert letzter_wareneingang(session, schuh, codes["SF1"]) == date(2024, 2, 5)
        assert letzter_wareneingang(session, polo, codes["SF2"]) == date(2026, 9, 5)
        assert letzter_wareneingang(session, polo, codes["SF3"]) is None
        assert letzter_wareneingang(session, polo, codes["GEWA"]) is None
        # Ältestes Eingangsdatum je Filiale bleibt beim ersten Eingang.
        aeltestes = {
            (b.lagerort_id, b.menge): b.aeltestes_eingangsdatum for b in session.scalars(select(Bestand))
        }
        assert aeltestes[(codes["SF1"], Decimal("5"))] == date(2024, 2, 5)
        assert aeltestes[(codes["SF1"], Decimal("6"))] == date(2024, 2, 5)
        assert aeltestes[(codes["GEWA"], Decimal("5"))] is None


def test_lagerorte_mit_richtigen_codes_und_nur_filialen_verkaufen():
    """F13: SF1 Volketswil, SF2 Conthey, SF3 Regensdorf, SF4 Hägendorf;
    GEWA, VEBO und Dietikon ohne Verkauf (Regel 6 hängt an `verkauf`)."""
    sessions = neue_datenbank()
    with sessions() as session:
        lagerorte = {lo.code: (lo.ort or lo.name, lo.verkauf) for lo in session.scalars(select(Lagerort))}
    assert {code: ort for code, (ort, _) in lagerorte.items() if code.startswith("SF")} == {
        "SF1": "Volketswil", "SF2": "Conthey", "SF3": "Regensdorf", "SF4": "Hägendorf"
    }
    assert {code for code, (_, verkauf) in lagerorte.items() if not verkauf} == {"GEWA", "VEBO", "DIETIKON"}


# --- FEDAS und Lieferantengruppen -----------------------------------------


@pytest.mark.parametrize(
    "fedas_code,erwartet",
    [
        # Bestätigte Zuordnung vom 24.09.2026 (FEDAS-Liste, Erlebnisbereich →
        # Kassen-Sportbereich).
        ("124100", ("Hartware", "Tennis")),
        ("224100", ("Textil", "Tennis")),
        ("324100", ("Schuhe", "Tennis")),
        ("232000", ("Textil", "Fussball")),
        ("201700", ("Textil", "Winter")),  # Ski Alpin
        ("311000", ("Schuhe", "Winter")),  # Eisstock / Curling
        ("214370", ("Textil", "Outdoor")),  # Freizeit / Mode Winter
        ("264000", ("Textil", "Outdoor")),  # Bergsport / Wandern
        ("215000", ("Textil", "Baden")),
        ("121000", ("Hartware", "Baden")),  # Kajak / Kanu
        ("278000", ("Textil", "Indoor")),  # Fitness
        ("182000", ("Hartware", "Indoor")),  # Kampfsport
        ("335000", ("Schuhe", "Indoor")),  # Handball
        ("346000", ("Schuhe", "Running")),
        ("356000", ("Schuhe", "Running")),  # Triathlon
        ("362700", ("Schuhe", "Rollsport")),  # Funwheel
        ("260000", ("Textil", "Velo")),  # Bike-Bekleidung
        ("160200", ("Hartware", "Velo")),  # Lenker: Zubehör, kein Velo
        ("149000", ("Hartware", "Freizeit")),  # Golf
        ("171000", ("Hartware", "Freizeit")),  # Reiten
        ("275000", ("Textil", "Freizeit")),
        ("100010", ("Hartware", "Freizeit")),  # Multisport
        # Ganze Fahrräder und Anhänger sind die Hauptgruppe Velo, Sportnahrung
        # ist Food - beide ohne Sportbereich.
        ("160010", ("Velo", None)),
        ("160080", ("Velo", None)),
        ("100201", ("Food", None)),
        # Kids lässt sich aus FEDAS nicht ableiten (kein Alter im Code).
        (None, None),
        ("12", None),
        ("999999", None),  # unbekannte Produktart
        ("199999", None),  # unbekannter Erlebnisbereich
    ],
)
def test_fedas_vorschlag(fedas_code, erwartet):
    assert suggest_kategorie(fedas_code) == erwartet


def test_fedas_vorschlag_passt_zu_den_kassenkategorien():
    """Jeder Vorschlag muss eine Kategorie der Kasse sein (Regel 8), und alle
    54 Erlebnisbereiche der FEDAS-Liste sind zugeordnet."""
    from app.core.fedas import SPORTBEREICH_NACH_ERLEBNISBEREICH
    from app.services.kategorien import kategorie_vorschlag

    assert len(SPORTBEREICH_NACH_ERLEBNISBEREICH) == 54
    sessions = neue_datenbank()
    with sessions() as session:
        for code in ("160010", "100201", "214370", "282000"):
            kategorie = kategorie_vorschlag(session, code)
            assert kategorie is not None, code
            assert (kategorie.hauptgruppe, kategorie.sportbereich) == suggest_kategorie(code)


def test_lieferantencodes_fuers_etikett():
    """Anforderungen vom 23.09.2026: 111/555/333/999/444."""
    assert {typ: etikett_code(typ) for typ in ETIKETT_CODES} == {
        "intersport": "111",
        "ecom": "555",
        "extern": "333",
        "drittanbieter": "999",
        "intern": "444",
    }
    assert etikett_code(None) is None and etikett_code("unbekannt") is None
    intern = {e["name"] for e in LIEFERANTEN_SEED if e["typ"] == "intern"}
    assert intern == {"Nike", "adidas", "The North Face"}
    assert {e["typ"] for e in LIEFERANTEN_SEED} == set(ETIKETT_CODES)


# --- Lieferadresse (D19) --------------------------------------------------

LAGERORTE = [
    LagerortAdresse(id=i + 1, code=e["code"], name=e["name"], strasse=e["strasse"], plz=e["plz"], ort=e["ort"])
    for i, e in enumerate(LAGERORTE_SEED)
]
VOLLADRESSEN = [
    (f"Lieferadresse: Sport Fabrik AG, {e['strasse']}, {e['plz']} {e['ort']}", e["code"])
    for e in LAGERORTE_SEED
    if e["plz"] or e["ort"]
]


@pytest.mark.parametrize(
    "text,erwartet",
    VOLLADRESSEN
    + [
        # Lieferadresse schlägt Rechnungsadresse.
        ("Rechnungsadresse: Industriestrasse 21, 8604 Volketswil\n"
         "Lieferadresse: Route Cantonale 7, 1964 Conthey", "SF2"),
        ("Sport Fabrik AG, 8604 Volketswil\nWarenempfänger: Sportfabrik, 8105 Regensdorf", "SF3"),
        ("Lieferadresse Sportfabrik Haegendorf", "SF4"),
        ("Lieferung an VEBO", "VEBO"),
        ("Lieferung an GEWA, externes Lager", "GEWA"),
        ("Lieferadresse 3322", "GEWA"),
        # Nicht raten.
        ("Sport Fabrik, 8604 Volketswil ... Filiale Conthey 1964", None),
        ("Lieferung ab Lager, Ware folgt", None),
        ("Lieferadresse Industriestrasse", None),  # SF1 und SF4
        ("Rechnung 386040 Volketswilerstrasse", None),
        ("Lieferschein Nr. 4711", None),
        ("", None),
    ],
)
def test_lagerort_aus_der_lieferadresse(text, erwartet):
    treffer = erkenne_lagerort(text, LAGERORTE)
    assert (treffer.lagerort.code if treffer else None) == erwartet


# --- Passwörter -----------------------------------------------------------


def test_passwoerter_gesalzen_und_geprueft():
    gespeichert = hash_password("geheim123")
    assert verify_password("geheim123", gespeichert)
    assert not verify_password("falsch", gespeichert)
    assert hash_password("geheim123") != gespeichert
    assert not verify_password("geheim123", "kaputt")
    assert not verify_password("geheim123", "md5$1$abc$def")


# --- Übersetzungen (Regel 7) ----------------------------------------------


def _katalog(sprache):
    return json.loads((ROOT / "app" / "static" / "i18n" / f"{sprache}.json").read_text("utf-8"))


@pytest.mark.parametrize("sprache", [s for s in LANGUAGES if s != DEFAULT_LANGUAGE])
def test_uebersetzungen_vollstaendig_mit_gleichen_platzhaltern(sprache):
    """Gleiche Keys in DE/FR/EN, gleiche Platzhalter - sonst bricht
    translate() ausgerechnet beim Anzeigen einer Fehlermeldung ab."""
    deutsch, andere = _katalog(DEFAULT_LANGUAGE), _katalog(sprache)
    assert sorted(andere) == sorted(deutsch)
    platzhalter = lambda text: set(re.findall(r"\{([^{}]*)\}", text))  # noqa: E731
    assert {k for k, text in deutsch.items() if platzhalter(text) != platzhalter(andere[k])} == set()
    assert translate("gibt.es.nicht", sprache) == "gibt.es.nicht"
