"""Interner Bestellplan (Excel-Ausdruck „Bestellung Winter HW26 SF1 - SF4"):
Layout-Erkennung, Positionen je Filiale und Import.

Das PDF wird selbst gebaut (echte Belege gehören nie ins Repo, Regel 1). Spalten-x
folgen dem echten Ausdruck.
"""

import hashlib

import pymupdf
import pytest
from conftest import neue_datenbank
from sqlalchemy import func, select

from app.core.models import Bestand, Lagerbewegung, Lagerort, Wareneingang
from app.services.importer import ImportRejected, import_invoice
from app.services.parsers import bestellplan, detect_parser, parse_document, read_document

KOPF = [
    (161, "Art"), (402, "SF1"), (451, "SF2"), (500, "SF3"), (549, "SF4"), (594, "Total"),
    (670, "EP"), (685, "Total"), (792, "VP"), (808, "Total"), (922, "VP-30%"),
    (1006, "Liefertermin"), (1157, "Filiale"), (1220, "GEWA"), (1287, "VEBO"),
]
SPALTEN_X = [297, 346, 405, 454, 503, 552, 602, 672, 792, 920, 1012, 1169]
# Name, VP, EP, SF1-SF4, Total, EP Total, VP Total, VP-30%, Liefertermin, X
ABSCHNITT = [
    ("Head Edge 7 W HV R102mm", "335.00", "103.00", "20", "18", "16", "18", "72",
     "7416.00", "24120.00", "16884.00", "15.09.2026", "X"),
    # nur SF2 bekommt Ware
    ("Tecnica Mach 1 LV 130 TD2 98mm", "650.00", "260.00", "0", "12", "0", "0", "12",
     "3120.00", "7800.00", "5460.00", "15.09.2026", "X"),
]


def plan(zeilen=ABSCHNITT, gesamt_ep="10536.00") -> bytes:
    with pymupdf.open() as doc:
        seite = doc.new_page(width=1684, height=1190)
        seite.insert_text((53, 60), "Bestellung Winter HW26 SF1 - SF4", fontsize=11)
        for x, text in KOPF:
            seite.insert_text((x, 79), text, fontsize=9)
        seite.insert_text((125, 97), "Skischuhe Lady", fontsize=9)
        seite.insert_text((306, 97), "VP", fontsize=9)
        seite.insert_text((356, 97), "EP", fontsize=9)
        y = 120
        for z in zeilen:
            seite.insert_text((76, y), z[0], fontsize=9)
            for x, text in zip(SPALTEN_X, z[1:]):
                seite.insert_text((x, y), text, fontsize=9)
            y += 22
        seite.insert_text((132, y), "Total pro Grösse", fontsize=9)
        summen = [sum(int(z[3 + i]) for z in zeilen) for i in range(4)]
        for x, text in zip((402, 451, 500, 549, 599), [*map(str, summen), str(sum(summen))]):
            seite.insert_text((x, y), text, fontsize=9)
        for x, text in ((645, "CHF"), (671, gesamt_ep), (762, "CHF"), (788, "32160.00"),
                        (891, "CHF"), (917, "22344.00")):
            seite.insert_text((x, y + 30), text, fontsize=9)
        return doc.tobytes()


def test_erkennt_layout_und_liest_eine_position_je_filiale():
    pdf = plan()
    assert detect_parser(read_document(pdf)) is bestellplan
    ergebnis = parse_document(pdf)
    assert ergebnis["parser_key"] == "bestellplan"
    assert ergebnis["document_type"] == "bestellung"
    # 4 Filialen für Head, nur SF2 für Tecnica (Menge 0 = keine Position)
    assert [(i["lagerort_code"], i["quantity"]) for i in ergebnis["items"]] == [
        ("SF1", "20"), ("SF2", "18"), ("SF3", "16"), ("SF4", "18"), ("SF2", "12"),
    ]
    erste = ergebnis["items"][0]
    assert erste["brand"] == "Head"
    assert erste["description"] == "Head Edge 7 W HV R102mm"
    assert erste["supplier_article_no"] == "Head Edge 7 W HV R102mm"
    assert erste["size"] == "ONESIZE"
    assert erste["uvp"] == "335.00"
    assert erste["ek"] == "103.00"
    assert erste["unit"] == "Stk"
    assert erste["ean"] == ""
    assert ergebnis["rows_with_warnings"] == 0
    assert ergebnis["warnings"] == []
    assert ergebnis["invoice_number"].startswith("Bestellung Winter HW26-")
    assert parse_document(pdf)["invoice_number"] == ergebnis["invoice_number"]


def test_summe_pro_zeile_und_gesamtwert_werden_gegengerechnet():
    # Gesamtwert im Fuss stimmt nicht mit der Summe der Zeilen
    ergebnis = parse_document(plan(gesamt_ep="999.00"))
    assert any("999.00" in w for w in ergebnis["warnings"])
    # Zeilensumme (Total) stimmt nicht mit SF1-SF4
    kaputt = [ABSCHNITT[0][:7] + ("73",) + ABSCHNITT[0][8:], ABSCHNITT[1]]
    ergebnis = parse_document(plan(kaputt))
    assert ergebnis["warnings"]


def test_fremdes_layout_wird_nicht_erkannt():
    pdf = plan()
    kopf = [k for k in KOPF if k[1] not in ("GEWA", "VEBO")]
    with pymupdf.open() as doc:
        seite = doc.new_page(width=1684, height=1190)
        for x, text in kopf:
            seite.insert_text((x, 79), text, fontsize=9)
        assert bestellplan.detect(read_document(doc.tobytes())) is None
    assert bestellplan.detect(read_document(pdf)) == 5


def test_import_bucht_je_filiale_eine_erwartete_lieferung_ohne_bestand():
    sessions = neue_datenbank()
    with sessions() as session:
        sf1 = session.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
    pdf = plan()
    import_invoice(pdf, "plan.pdf", hashlib.sha256(pdf).hexdigest(), sessions, sf1)
    with sessions() as session:
        eingaenge = session.execute(
            select(Lagerort.code, Wareneingang.status)
            .join(Wareneingang, Wareneingang.lagerort_id == Lagerort.id)
            .order_by(Lagerort.code)
        ).all()
        assert eingaenge == [
            ("SF1", "erwartet"), ("SF2", "erwartet"), ("SF3", "erwartet"), ("SF4", "erwartet"),
        ]
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 0
        assert session.scalar(select(func.coalesce(func.sum(Bestand.menge), 0))) == 0
    with pytest.raises(ImportRejected):
        import_invoice(pdf, "nochmal.pdf", hashlib.sha256(pdf).hexdigest(), sessions, sf1)
