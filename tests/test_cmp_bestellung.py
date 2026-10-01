"""Punkt 7 (2026-10-01): CMP-Bestellung aus dem Campagnolo-Portal (Rasterausdruck).

Der rechnerische Kern (`baue_positionen`) wird mit gebauten Wörtern geprüft, ohne OCR.
Mit dem echten Beleg nur über eine lokale Umgebungsvariable (Regel 1: Belege
bleiben ausserhalb des Repos): `CMP_BESTELLUNG_PDF=/pfad/CMP_Nachbest.pdf`.
"""

import os
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.parsers.cmp_bestellung import (
    artikelnummer,
    baue_positionen,
    farbcode,
    preisspalten,
    titel_lesen,
)


def w(x, y, text, breite=20):
    return (x, y, x + breite, y + 8, text, 90.0, 0, 0)


SPALTEN = [(294.0, "50"), (318.0, "52"), (342.0, "54"), (366.0, "56")]


def kasten(zeilen, ek=("13.00",) * 4, vk=("29.90",) * 4, titel="33N6677 : MAN T-SHIRT - [2026P] - 100%PL"):
    code, _, rest = titel.partition(" ")
    return {
        "page": 1,
        "titel": [w(64, 287, code), w(98, 288, ":", 3), w(103, 287, rest.lstrip(": "), 150)],
        "columns": SPALTEN,
        "zeilen": zeilen,
        "ek": list(ek),
        "vk": list(vk),
    }


def zeile(code, name, mengen, gesamt, betrag):
    return {"farbe": [w(80, 312, code, 20), w(80, 323, "[2026P]", 30), w(80, 332, name, 40)], "mengen": mengen, "gesamt": gesamt, "betrag": betrag}


def test_positionen_aus_einem_kasten():
    items, warnungen, (stueck, betrag) = baue_positionen(
        [kasten([zeile("P753", "CORDA", ["2", "2", "2", "2"], "8", "10400")])]
    )
    assert warnungen == []
    assert [(i["size"], i["quantity"]) for i in items] == [("50", "2"), ("52", "2"), ("54", "2"), ("56", "2")]
    first = items[0]
    assert (first["brand"], first["supplier_article_no"], first["article_no"]) == ("CMP", "33N6677", "33N6677 P753")
    assert (first["description"], first["color"], first["ek"], first["uvp"]) == ("MAN T-SHIRT", "CORDA", "13.00", "29.90")
    assert first["warnings"] == [] and first["ean"] == ""
    assert (stueck, betrag) == (8, Decimal("104.00"))


def test_gegenrechnung_meldet_falsche_menge_und_betrag():
    items, _, _ = baue_positionen([kasten([zeile("P753", "CORDA", ["2", None, "2", "2"], "8", "10400")])])
    assert any("ergeben 6" in m for m in items[0]["warnings"])  # 6 statt 8
    assert any("78" in m for m in items[0]["warnings"])  # Betrag 6 × 13 = 78 statt 104


def test_unsichere_spalten_und_fehlender_preis_sperren():
    k = kasten([zeile("P753", "CORDA", ["2", "2", "2", "2"], "8", "10400")])
    k["columns"] = [(c, None) for c, _ in SPALTEN]
    items, warnungen, _ = baue_positionen([k])
    assert items == [] and warnungen  # Grössen nicht lesbar: gemeldet statt geraten
    items, _, _ = baue_positionen([kasten([zeile("P753", "CORDA", ["2", "2", "2", "2"], "8", "10400")], vk=(None,) * 4)])
    assert all(i["warnings"] for i in items)


def test_artikelnummer_korrigiert_ocr_verwechslungen():
    assert artikelnummer("3685807") == "36S5807"  # S als 8 gelesen
    assert artikelnummer("3277177") == "32T7177"  # T als 7 gelesen
    assert artikelnummer("33N6677") == "33N6677"
    assert titel_lesen([w(64, 287, "3685807"), w(98, 288, ":", 3), w(103, 287, "MAN TECH SHIRT - [2026P] - 97%PL", 150)])["korrigiert"] is True
    assert titel_lesen([w(64, 287, "33N6677"), w(98, 288, ":", 3), w(103, 287, "MAN T-SHIRT", 60)])["korrigiert"] is False
    assert titel_lesen([w(64, 287, "Lieferadresse:")]) is None


@pytest.mark.parametrize(
    "roh,erwartet",
    [
        ("91UR", ("91UR", False)),
        ("P753", ("P753", False)),
        ("972V", ("97ZV", True)),  # Z als 2 gelesen
        ("1U743", ("U743", True)),  # Rest vom Vorschaubild davor
        ("Uu901", ("U901", True)),
        ("382ZV", (None, False)),  # zwei mögliche Codes: nicht raten
        ("AB", (None, False)),
    ],
)
def test_farbcode(roh, erwartet):
    assert farbcode(roh) == erwartet


def test_preisspalten_aus_der_preiszeile():
    woerter = [w(52, 388, "Preise", 20), w(285, 388, "13,00", 17), w(309, 388, "13,00|13,00", 40), w(518, 388, "104,00", 20)]
    assert [round(c) for c in preisspalten(woerter)] == [294, 318, 340]  # das verklebte Paar wird geteilt


PDF = os.environ.get("CMP_BESTELLUNG_PDF")


@pytest.mark.skipif(not PDF or not Path(PDF).is_file(), reason="CMP_BESTELLUNG_PDF nicht gesetzt (Beleg bleibt lokal)")
def test_echter_beleg_wird_erkannt_und_gegengerechnet():
    from app.services.parsers import parse_with_parser, read_and_detect

    document, parser = read_and_detect(Path(PDF).read_bytes())
    ergebnis = parse_with_parser(parser, document)
    assert ergebnis["document_type"] == "bestellung" and ergebnis["invoice_number"] == "22065"
    assert ergebnis["parser_key"] == "cmp"
    # Alles, was nicht sicher gelesen ist, steht als Warnung da; nichts wird still falsch.
    assert sum(int(i["quantity"]) for i in ergebnis["items"]) >= 150
    assert all(i["unit"] == "Stk" and i["brand"] == "CMP" for i in ergebnis["items"])
