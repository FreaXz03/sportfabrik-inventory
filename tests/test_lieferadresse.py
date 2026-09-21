"""Lagerort aus der Lieferadresse erkennen (app/services/lieferadresse.py,
Phase B Teilaufgabe B4 — D19).

Reine Textlogik, darum ohne Datenbank und ohne PDF: die Adressen kommen aus
den echten Seed-Daten (`app/core/lagerorte.py`), damit die Tests dieselben
Werte prüfen wie der Betrieb.
"""

import pytest

from app.core.lagerorte import LAGERORTE_SEED
from app.services.lieferadresse import (
    LagerortAdresse,
    erkenne_lagerort,
    lieferadress_abschnitte,
)

LAGERORTE = [
    LagerortAdresse(
        id=index + 1,
        code=eintrag["code"],
        name=eintrag["name"],
        strasse=eintrag["strasse"],
        plz=eintrag["plz"],
        ort=eintrag["ort"],
    )
    for index, eintrag in enumerate(LAGERORTE_SEED)
]


def code(text):
    treffer = erkenne_lagerort(text, LAGERORTE)
    return treffer.lagerort.code if treffer else None


# --- Volladresse je Lagerort ----------------------------------------------


# VEBO hat (noch) keine Adresse in den Seed-Daten und wird deshalb hier
# ausgelassen - erkannt wird es über seinen Namen, siehe weiter unten.
MIT_ADRESSE = [e for e in LAGERORTE_SEED if e["plz"] or e["ort"]]


@pytest.mark.parametrize(
    "eintrag", MIT_ADRESSE, ids=[e["code"] for e in MIT_ADRESSE]
)
def test_every_lagerort_is_recognised_by_its_own_address(eintrag):
    text = (
        f"Lieferadresse: Sport Fabrik AG, {eintrag['strasse']}, "
        f"{eintrag['plz']} {eintrag['ort']}"
    )
    assert code(text) == eintrag["code"]


# --- Lieferadresse schlägt Rechnungsadresse ------------------------------


def test_delivery_address_wins_over_the_billing_address():
    """Der Fall aus projekt-kontext.md Abschnitt 6: Rechnung an Volketswil,
    Lieferadresse Conthey. Gebucht werden muss Conthey."""
    text = (
        "Rechnungsadresse: Sport Fabrik AG, Industriestrasse 21, 8604 Volketswil\n"
        "Lieferadresse: Sport Fabrik AG, Route Cantonale 7, 1964 Conthey"
    )
    treffer = erkenne_lagerort(text, LAGERORTE)
    assert treffer.lagerort.code == "SF4"
    assert treffer.aus_lieferadresse is True


@pytest.mark.parametrize(
    "anker",
    ["Lieferadresse", "Lieferanschrift", "Lieferung an", "Warenempfänger", "Ship to"],
)
def test_common_delivery_anchors_are_understood(anker):
    text = f"Sport Fabrik AG, 8604 Volketswil\n{anker}: Sportfabrik, 8105 Regensdorf"
    assert code(text) == "SF2"


def test_lieferschein_is_not_mistaken_for_a_delivery_anchor():
    """„Lieferschein" fängt gleich an wie „Lieferadresse" - darf aber kein
    Anker sein, sonst würde die Rechnungsadresse danach als Lieferadresse
    gelesen."""
    assert lieferadress_abschnitte("Lieferschein Nr. 4711 zu 8604 Volketswil") == []


# --- Nicht raten ----------------------------------------------------------


def test_two_equally_plausible_addresses_give_no_suggestion():
    """Beide Orte gleich stark und kein Anker: dann lieber kein Vorschlag als
    ein falscher (der Import bleibt bei der aktiven Filiale)."""
    text = "Sport Fabrik, 8604 Volketswil ... Filiale Conthey 1964"
    assert erkenne_lagerort(text, LAGERORTE) is None


def test_document_without_any_address():
    assert erkenne_lagerort("Rechnung Nr. 9001759392 über 12 Stück", LAGERORTE) is None


def test_empty_input():
    assert erkenne_lagerort("", LAGERORTE) is None
    assert erkenne_lagerort("8604 Volketswil", []) is None


# --- Schreibweisen --------------------------------------------------------


@pytest.mark.parametrize("schreibweise", ["Hägendorf", "Haegendorf", "HÄGENDORF", "hägendorf"])
def test_umlauts_written_either_way(schreibweise):
    """Belege schreiben Umlaute mal als „ä", mal als „ae" (die Sportfabrik
    selbst benutzt haegendorf@sportfabrik.ch)."""
    assert code(f"Lieferadresse Sportfabrik {schreibweise}") == "SF3"


def test_vebo_is_recognised_by_its_name_alone():
    """VEBO ist die zweite Verarbeitungsstelle und hat in den Seed-Daten noch
    keine Adresse - der Name muss deshalb allein genügen."""
    assert code("Lieferung an VEBO") == "VEBO"


def test_generic_word_in_a_lagerort_name_is_not_a_match():
    """„Lager Dietikon" darf nicht dazu führen, dass jeder Beleg, auf dem das
    Wort „Lager" steht, dort gebucht wird - nur unterscheidende Wörter zählen
    (siehe _kennwort). Über den Ortsnamen wird Dietikon trotzdem gefunden."""
    assert code("Lieferung ab Lager, Ware folgt") is None
    assert code("Lieferadresse: Sport Fabrik AG, Dietikon") == "DIETIKON"


def test_gewa_is_recognised_by_its_name_alone():
    """Auf der CMP-Auftragsbestätigung steht als Ziel nur „GEWA" - ohne
    Adresse (projekt-kontext.md Abschnitt 6)."""
    assert code("Lieferung an GEWA, externes Lager") == "GEWA"


def test_postcode_alone_is_enough():
    assert code("Lieferadresse 3322") == "GEWA"


def test_street_alone_is_not_enough_to_separate_sf1_and_sf3():
    """„Industriestrasse" kommt bei SF1 und SF3 vor - ohne PLZ oder Ort bleibt
    es offen."""
    assert erkenne_lagerort("Lieferadresse Industriestrasse", LAGERORTE) is None


def test_neighbouring_words_do_not_count_as_a_match():
    """Kein Treffer mitten in einem längeren Wort oder einer längeren Zahl -
    sonst würde z. B. eine Belegnummer als Postleitzahl gelesen."""
    assert erkenne_lagerort("Rechnung 386040 Volketswilerstrasse", LAGERORTE) is None


def test_matched_features_are_reported():
    treffer = erkenne_lagerort(
        "Lieferadresse: Althardstrasse 10, 8105 Regensdorf", LAGERORTE
    )
    assert treffer.merkmale == ("plz", "ort", "strasse")
