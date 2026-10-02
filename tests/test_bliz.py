"""Bliz-Preisliste/Bestellformular (Excel-Ausdruck): Layout-Erkennung und Positionen.

Das PDF wird selbst gebaut (echte Belege gehören nie ins Repo, Regel 1). Spalten-x
und Kopfzeile folgen dem echten Formular.
"""

import hashlib
from datetime import date

import pymupdf
import pytest
from conftest import neue_datenbank
from sqlalchemy import func, select

from app.core.models import Bestand, Lagerbewegung, Lagerort, Variante
from app.services.importer import ImportRejected, import_invoice
from app.services.parsers import bliz, detect_parser, parse_document, read_document

KOPF = [
    (22, "QTY"), (46, "VALUE"), (79, "MATERIAL"), (114, "GRID"), (124, "VALUE"), (160, "STYLE"),
    (173, "NAME"), (230, "FRAME"), (294, "LENS"), (305, "COLOR"), (363, "VLT"), (414, "Filter"),
    (425, "Category"), (462, "MATERIAL"), (496, "UPC"), (524, "WHLS"), (557, "RRP"),
]
# qty, Artikel, Farbcode, Variante, Name, Rahmen, Linse, VLT, Kategorie, Material, UPC, WHLS, RRP
ZEILEN = [
    ("0", "0ZG8002", "13", "00", "RAVE", "MATTE BLUE", "BROWN W BLUE MULTI", "13%", "CAT.3", "INJECTED", "8056262462416", "52.28", "120.00"),
    ("0", "0ZG8002", "19", "00", "RAVE", "MATTE WHITE", "N-O-N-ORANGE&BLUE", "45%", "CAT.1", "INJECTED", "8056262462591", "64.04", "146.00"),
    ("0", "0ZK8504", "12", "00", "PIXIE", "MATTE PINK", "ORANGE", "34%", "CAT.2", "INJECTED", "8056262463468", "17.04", "39.00"),
]


def formular(zeilen=ZEILEN, kopf=KOPF) -> bytes:
    with pymupdf.open() as doc:
        seite = doc.new_page(width=595, height=842)
        seite.insert_text((17, 60), "Currency CHF")
        for x, text in kopf:
            seite.insert_text((x, 101), text, fontsize=3)
        for i, z in enumerate(zeilen):
            y = 112 + i * 6
            xs = [51, 83, 120, 126, 168, 228, 289, 364, 423, 464, 489, 526, 556]
            for x, text in zip(xs, z):
                # Preise stehen in der Excel-Vorlage 1 pt höher als der Rest der Zeile.
                seite.insert_text((x, y - (1 if x >= 526 else 0)), text, fontsize=3)
        return doc.tobytes()


def test_erkennt_layout_und_liest_positionen():
    pdf = formular()
    assert detect_parser(read_document(pdf)) is bliz
    ergebnis = parse_document(pdf)
    assert ergebnis["parser_key"] == "bliz"
    assert ergebnis["item_count"] == 3
    erste = ergebnis["items"][0]
    assert erste["brand"] == "Bliz"
    assert erste["supplier_article_no"] == "0ZG8002"
    assert erste["article_no"] == "0ZG8002 13 00"
    assert erste["description"] == "RAVE"
    assert erste["color"] == "MATTE BLUE / BROWN W BLUE MULTI"
    assert erste["size"] == "ONESIZE"
    assert erste["ean"] == "8056262462416"
    assert erste["ek"] == "52.28"
    assert erste["uvp"] == "120.00"
    assert erste["unit"] == "Stk"
    assert erste["quantity"] == "0"
    assert ergebnis["items"][2]["color"] == "MATTE PINK / ORANGE"
    assert ergebnis["rows_with_warnings"] == 0


def test_formular_bekommt_belegnummer_und_heutiges_datum():
    # Das Formular trägt weder Nummer noch Datum: beides wird erzeugt (02.10.2026).
    pdf = formular()
    ergebnis = parse_document(pdf)
    heute = date.today()
    assert ergebnis["document_type"] == "bestellung"
    assert ergebnis["invoice_number"].startswith("BLIZ-" + heute.strftime("%Y%m%d") + "-")
    assert parse_document(pdf)["invoice_number"] == ergebnis["invoice_number"]
    assert bliz.dates(read_document(pdf)) == {"invoice_date": heute, "document_date": heute}


def test_import_legt_artikel_an_aber_bucht_keinen_bestand():
    sessions = neue_datenbank()
    with sessions() as session:
        sf1 = session.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
    pdf = formular()
    importiert = import_invoice(pdf, "bliz.pdf", hashlib.sha256(pdf).hexdigest(), sessions, sf1)
    assert importiert["item_count"] == 3
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Variante)) == 3
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 0
        assert session.scalar(select(func.coalesce(func.sum(Bestand.menge), 0))) == 0
    with pytest.raises(ImportRejected):
        import_invoice(pdf, "nochmal.pdf", hashlib.sha256(pdf).hexdigest(), sessions, sf1)


def test_zeile_ohne_ean_gibt_hinweis_und_falsche_ean_warnung():
    zeilen = [ZEILEN[0][:10] + ("", "52.28", "120.00"), ZEILEN[1][:10] + ("123", "64.04", "146.00")]
    ergebnis = parse_document(formular(zeilen))
    assert ergebnis["items"][0]["hints"] and not ergebnis["items"][0]["warnings"]
    assert ergebnis["items"][1]["warnings"]


def test_fremdes_layout_wird_nicht_erkannt():
    pdf = formular(kopf=[k for k in KOPF if k[1] not in ("WHLS", "RRP")])
    assert bliz.detect(read_document(pdf)) is None
