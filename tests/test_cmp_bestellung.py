"""Punkt 7 (2026-10-01): CMP-Bestellung aus dem Campagnolo-Portal (Rasterausdruck).

Der rechnerische Kern (`baue_positionen`) wird mit gebauten Wörtern geprüft, ohne OCR.
Mit dem echten Beleg nur über eine lokale Umgebungsvariable (Regel 1: Belege
bleiben ausserhalb des Repos): `CMP_BESTELLUNG_PDF=/pfad/CMP_Nachbest.pdf`.
"""

import os
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.corrections import CorrectionError, apply_corrections
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
    # Die Vorschau-Tabelle liest `raw_lines` jeder Position; fehlt es, bleibt die Tabelle leer.
    assert all(isinstance(i["raw_lines"], list) and i["raw_lines"] for i in items)
    assert (stueck, betrag) == (8, Decimal("104.00"))


def test_farbname_ohne_rahmenreste():
    items, _, _ = baue_positionen(
        [kasten([zeile("91UR", "/ANTRACITE-", ["2", "1", None, None], "3", "3900")])]
    )
    assert items[0]["color"] == "ANTRACITE-"


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


def _vorschau(zeilen, stueck, betrag):
    """Was die Vorschau dem Browser gibt: Positionen samt Gegenrechnung wie nach parse()."""
    from app.services.parsers.base import gegenrechnung_dokument

    items, warnungen, (ist_stueck, ist_betrag) = baue_positionen([kasten(zeilen)])
    for nummer, item in enumerate(items, start=1):  # wie ergebnis() sie vergibt
        item["row_number"] = nummer
    totals = {"stueck": stueck, "betrag": betrag}
    warnungen += gegenrechnung_dokument(items, totals)
    return {"items": items, "warnings": warnungen, "check_totals": totals, "invoice_number": "22065", "document_type": "bestellung"}


def test_fehlende_groesse_laesst_sich_ergaenzen_und_loest_die_warnungen():
    # Beleg: 4 × 2 Stück à 13.00 = 104.00; gelesen wurden nur 3 Grössen.
    vorschau = _vorschau([zeile("P753", "CORDA", ["2", "2", "2", None], "8", "10400")], 8, "104.00")
    assert vorschau["warnings"] and all(i["warnings"] for i in vorschau["items"])
    ergebnis = apply_corrections(vorschau, {"_added": [{"from_row": 1, "size": "56", "quantity": "2"}]}, None, "de")
    assert ergebnis["rows_with_warnings"] == 0 and ergebnis["warnings"] == []
    neu = ergebnis["items"][-1]
    assert (neu["size"], neu["quantity"], neu["ek"], neu["uvp"], neu["article_no"]) == ("56", "2", "13.00", "29.90", "33N6677 P753")
    assert neu["manual_added"] is True and neu["added_from"] == 1 and neu["row_number"] == 4
    assert ergebnis["item_count"] == 4


def test_falsche_menge_korrigieren_loest_die_warnung():
    vorschau = _vorschau([zeile("P753", "CORDA", ["2", "2", "2", "1"], "8", "10400")], 8, "104.00")
    assert vorschau["rows_with_warnings"] if "rows_with_warnings" in vorschau else all(i["warnings"] for i in vorschau["items"])
    ergebnis = apply_corrections(vorschau, {"4": {"quantity": "2"}}, None, "de")
    assert ergebnis["rows_with_warnings"] == 0 and ergebnis["warnings"] == []


def test_ergaenzen_ist_nicht_beliebig():
    vorschau = _vorschau([zeile("P753", "CORDA", ["2", "2", "2", None], "8", "10400")], 8, "104.00")
    for falsch in (
        [{"from_row": 99, "size": "56", "quantity": "2"}],  # Quellzeile gibt es nicht
        [{"from_row": 1, "size": "", "quantity": "2"}],  # ohne Grösse
        [{"from_row": 1, "size": "56", "quantity": "2", "ek": "0.01"}],  # Preise nicht frei wählbar
        "kein liste",
        [{"from_row": 1, "size": "56", "quantity": "2"}] * 80,  # zu viele
    ):
        with pytest.raises(CorrectionError):
            apply_corrections(vorschau, {"_added": falsch}, None, "de")
    # Nur Positionen mit Gegenrechnung (dieser Parser) lassen sich ergänzen.
    vorschau["items"][0].pop("check")
    with pytest.raises(CorrectionError):
        apply_corrections(vorschau, {"_added": [{"from_row": 1, "size": "56", "quantity": "2"}]}, None, "de")


def test_unsicherer_farbcode_bleibt_bis_er_geaendert_wird():
    vorschau = _vorschau([zeile("382ZV", "PETROLEUM", ["2", "2", "2", "2"], "8", "10400")], 8, "104.00")
    assert any("382ZV" in w for w in vorschau["items"][0]["warnings"])
    unveraendert = apply_corrections(vorschau, {}, None, "de")
    assert unveraendert["rows_with_warnings"] == 4  # eine Prüfung allein ändert nichts
    korrigiert = apply_corrections(vorschau, {str(i["row_number"]): {"article_no": "33N6677 38ZV"} for i in vorschau["items"]}, None, "de")
    assert korrigiert["rows_with_warnings"] == 0


PDF = os.environ.get("CMP_BESTELLUNG_PDF")


@pytest.mark.skipif(not PDF or not Path(PDF).is_file(), reason="CMP_BESTELLUNG_PDF nicht gesetzt (Beleg bleibt lokal)")
def test_echter_beleg_wird_erkannt_und_gegengerechnet():
    from app.services.parsers import parse_with_parser, read_and_detect

    document, parser = read_and_detect(Path(PDF).read_bytes())
    ergebnis = parse_with_parser(parser, document)
    assert ergebnis["document_type"] == "bestellung" and ergebnis["invoice_number"] == "22065"
    # Das Belegdatum braucht der Import (wie bei jedem Layout): „Bestellt am: 15/08/2026".
    from datetime import date

    assert parser.dates(document)["document_date"] == date(2026, 8, 15)
    assert ergebnis["parser_key"] == "cmp"
    # Alles, was nicht sicher gelesen ist, steht als Warnung da; nichts wird still falsch.
    assert sum(int(i["quantity"]) for i in ergebnis["items"]) >= 150
    assert all(i["unit"] == "Stk" and i["brand"] == "CMP" for i in ergebnis["items"])
