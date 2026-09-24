"""Parser: Layout- und Lieferanten-Erkennung, INTERSPORT-Layout, Texterkennung
für Scans (Regel 1: alles lokal, unbekanntes Layout wird gemeldet statt
geraten).

Die meisten Tests bauen ihre Belege selbst (tests/testbelege.py). Echte
Belege liegen nie im Repo: die Tests dafür lesen die Datei aus einer
Umgebungsvariable und werden ohne sie übersprungen.
"""

import hashlib
import os
import shutil
from pathlib import Path

import pymupdf
import pytest
from conftest import CHEF, neue_datenbank
from sqlalchemy import func, select
from testbelege import POSITIONEN, rechnung_pdf, text_pdf

from app.core.i18n import LANGUAGES, translate
from app.core.lieferanten import LIEFERANTEN_SEED
from app.core.models import Lagerort, Variante
from app.services import ocr
from app.services.importer import ImportRejected, import_invoice
from app.services.parsers import (
    PARSERS,
    DocumentParseError,
    UnknownLayoutError,
    decimal_value,
    detect_parser,
    intersport,
    parse_document,
    parse_with_parser,
    read_and_detect,
    read_document,
)

KOPFZEILE = "Marke FEDAS Lief. Art. Art. EAN Bezeichnung Menge Einheit UVP Preis"


# --- Schnittstelle und Erkennung ------------------------------------------


@pytest.mark.parametrize("parser", PARSERS, ids=lambda p: p.KEY)
def test_jeder_parser_erfuellt_die_schnittstelle(parser):
    """Ein neues Layout-Modul braucht KEY, LIEFERANT_NAME, detect, parse und
    dates - und einen Lieferanten mit passendem parser_key in den Stammdaten."""
    assert parser.KEY and parser.LIEFERANT_NAME
    assert callable(parser.detect) and callable(parser.parse) and callable(parser.dates)
    seeded = {row["parser_key"]: row["name"] for row in LIEFERANTEN_SEED}
    assert seeded.get(parser.KEY) == parser.LIEFERANT_NAME
    assert len({p.KEY for p in PARSERS}) == len(PARSERS)


def test_erkennung_braucht_die_positionstabelle():
    lesen = lambda *zeilen: read_document(text_pdf(*zeilen))  # noqa: E731
    assert detect_parser(lesen("INTERSPORT Schweiz AG", "Rechnung Nr. 9001759392", KOPFZEILE)) is intersport
    # Auf einem Scan ist das Logo nicht immer lesbar - die Tabelle genügt.
    assert detect_parser(lesen(KOPFZEILE)) is intersport
    # Nur der Name ohne Tabelle ist kein bekanntes Layout.
    with pytest.raises(UnknownLayoutError):
        detect_parser(lesen("INTERSPORT Schweiz AG", "Rechnung Nr. 4711"))


@pytest.mark.parametrize("sprache", LANGUAGES)
def test_unbekanntes_layout_wird_gemeldet(sprache):
    with pytest.raises(UnknownLayoutError) as fehler:
        parse_document(text_pdf("Alpina Auftragsbestätigung 160165", "Pos Artikel Menge"), sprache)
    assert str(fehler.value) == translate("errors.parser.unknown_layout", sprache, hint="")


def test_gleichstand_ist_ein_fehler_statt_eines_muenzwurfs(monkeypatch):
    class Zwilling:
        KEY = "zwilling"
        LIEFERANT_NAME = "Zwilling AG"
        detect = staticmethod(lambda document: 4)
        parse = staticmethod(lambda document, language="de": {})
        dates = staticmethod(lambda document, language="de": {})

    monkeypatch.setattr("app.services.parsers.PARSERS", (Zwilling, intersport))
    with pytest.raises(UnknownLayoutError) as fehler:
        detect_parser(read_document(text_pdf(KOPFZEILE, "INTERSPORT", "Rechnung Nr. 1")))
    assert "Zwilling AG" in str(fehler.value) and intersport.LIEFERANT_NAME in str(fehler.value)


# --- INTERSPORT-Layout ----------------------------------------------------


def test_intersport_rechnung_wird_vollstaendig_gelesen(monkeypatch):
    """Positionen, Belegnummer, Typ und Daten aus einem einzigen Lesedurchgang
    (bei Scans liefe die Texterkennung sonst mehrfach über dieselbe Seite)."""
    from app.services.parsers import base

    gelesen = []
    original = base.read_page
    monkeypatch.setattr(
        base, "read_page", lambda page, nummer, language="de": gelesen.append(nummer) or original(page, nummer, language)
    )
    document, parser = read_and_detect(rechnung_pdf())
    ergebnis = parse_with_parser(parser, document)
    daten = parser.dates(document)
    assert gelesen == [1]
    assert ergebnis["supplier_name"] == intersport.LIEFERANT_NAME
    assert ergebnis["document_type"] == "rechnung"
    assert ergebnis["invoice_number"] == "9001759392"
    assert ergebnis["item_count"] == 3 and ergebnis["warnings"] == []
    position = ergebnis["items"][0]
    assert (position["brand"], position["fedas_code"], position["supplier_article_no"]) == ("Nike", "224100", "A1")
    assert (position["ean"], position["quantity"], position["uvp"]) == ("4006632041234", "5", "49.90")
    assert str(daten["invoice_date"]) == "2026-08-05"
    assert str(daten["document_date"]) == "2026-08-04"


def test_fehlende_ean_ist_nur_ein_hinweis():
    """Regel 5: ohne EAN importierbar, mit Hinweis statt Warnung."""
    zeilen = [POSITIONEN[0][:4] + [""] + POSITIONEN[0][5:]]
    ergebnis = parse_document(rechnung_pdf(rows=zeilen))
    assert ergebnis["items"][0]["ean"] == ""
    assert ergebnis["items"][0]["hints"] == [translate("hints.parser.ean_missing")]
    assert ergebnis["rows_with_warnings"] == 0


def test_ohne_belegnummer_bleibt_der_typ_offen():
    ergebnis = parse_document(rechnung_pdf(header_lines=[]))
    assert ergebnis["document_type"] is None and ergebnis["invoice_number"] is None


@pytest.mark.parametrize(("wert", "erwartet"), [("1’234.50", "1234.50"), ("-2", "-2"), ("1,5", "1.5")])
def test_zahlen_aus_belegen(wert, erwartet):
    assert decimal_value(wert) == erwartet


def test_kaputte_oder_zu_grosse_datei(welt, monkeypatch):
    welt.anmelden(CHEF)
    for daten in (b"", b"not a pdf", b"%PDF-broken"):
        with pytest.raises(DocumentParseError):
            parse_document(daten)
        antwort = welt.client.post("/upload-preview", files={"file": ("x.pdf", daten)})
        assert antwort.status_code == 422
    monkeypatch.setattr("app.routers.preview.MAX_UPLOAD_BYTES", 4)
    assert welt.client.post("/upload-preview", files={"file": ("x.pdf", b"12345")}).status_code == 413


# --- Texterkennung für Scans ----------------------------------------------


def test_seite_mit_textebene_braucht_keine_texterkennung(monkeypatch):
    def nicht_aufrufen(*args, **kwargs):
        raise AssertionError("OCR für eine Seite mit Textebene")

    monkeypatch.setattr(ocr, "ocr_page", nicht_aufrufen)
    assert parse_document(rechnung_pdf())["ocr_used"] is False


def test_fehlende_texterkennung_wird_klar_gemeldet(monkeypatch):
    monkeypatch.setattr(ocr, "pytesseract", None)
    monkeypatch.setattr(ocr, "Image", None)
    with pytest.raises(ocr.OcrUnavailableError, match="Texterkennung"):
        ocr.ocr_page(page=None)


def test_tesseract_woerter_werden_zu_zeilen():
    """Tesseract-Boxen schwanken je Wort um ein paar Pixel; Wörter derselben
    Zeile müssen trotzdem dieselbe Höhe bekommen, Rauschen fällt weg."""
    zeilen = [(1, 100, ["Marke", "=", "EAN"]), (2, 250, ["Nike", "4006632041234"])]
    daten = {k: [] for k in ("text", "block_num", "par_num", "line_num", "left", "top", "width", "height", "word_num")}
    for zeile, oben, woerter in zeilen:
        for index, wort in enumerate(woerter):
            for schluessel, wert in (
                ("text", wort), ("block_num", 1), ("par_num", 1), ("line_num", zeile),
                ("left", 50 + index * 200), ("top", oben + (2 if index % 2 else -2)),
                ("width", len(wort) * 18), ("height", 30 + (3 if index % 2 else 0)), ("word_num", index + 1),
            ):
                daten[schluessel].append(wert)
    woerter = ocr._grouped_words(daten)
    assert [w[4] for w in woerter] == ["Marke", "EAN", "Nike", "4006632041234"]
    assert len({round(w[1], 6) for w in woerter[:2]}) == 1
    assert woerter[0][1] == pytest.approx(98 * 72 / ocr.OCR_DPI, abs=1)
    assert woerter[0][1] != woerter[2][1]
    assert ocr._clean_word("|Stk") == "Stk" and ocr._clean_word("Air-Max") == "Air-Max"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract ist nicht installiert")
def test_gescannte_rechnung_wird_gelesen():
    """Seite ohne Textebene: gerendert, per Texterkennung gelesen."""
    with pymupdf.open(stream=rechnung_pdf(), filetype="pdf") as quelle:
        bild = quelle[0].get_pixmap(dpi=ocr.OCR_DPI).tobytes("png")
        with pymupdf.open() as scan:
            seite = scan.new_page(width=quelle[0].rect.width, height=quelle[0].rect.height)
            seite.insert_image(seite.rect, stream=bild)
            ergebnis = parse_document(scan.tobytes())
    assert ergebnis["ocr_used"] is True
    assert ergebnis["invoice_number"] == "9001759392"
    assert [p["ean"] for p in ergebnis["items"]] == [p[4] for p in POSITIONEN]


# --- Echte Belege (nur lokal) ---------------------------------------------


@pytest.fixture
def intersport_original():
    pfad = os.environ.get("INTERSPORT_TEST_PDF")
    if not pfad:
        pytest.skip("INTERSPORT_TEST_PDF auf die Originalrechnung setzen")
    return Path(pfad).read_bytes()


def test_intersport_originalrechnung(intersport_original):
    """Die 21-seitige Rechnung 9001759392: alle 217 Positionen, ohne Warnung,
    Import einmal und nicht zweimal."""
    ergebnis = parse_document(intersport_original)
    assert ergebnis["pages"] == 21 and ergebnis["item_count"] == 217
    assert ergebnis["page_item_counts"] == [7] + [11] * 19 + [1]
    assert ergebnis["warnings"] == [] and ergebnis["rows_with_warnings"] == 0
    assert ergebnis["items"][7]["brand"] == "Red Bull Spect Eyewear"
    assert ergebnis["items"][4]["size"] == "S 51-55 CM"
    assert ergebnis["duplicate_eans"]["0725882069647"] == 4

    sessions = neue_datenbank()
    with sessions() as session:
        sf1 = session.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
    digest = hashlib.sha256(intersport_original).hexdigest()
    importiert = import_invoice(intersport_original, "r.pdf", digest, sessions, sf1)
    assert importiert["item_count"] == 217 and importiert["new_products"] == 203
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Variante)) == 203
    with pytest.raises(ImportRejected):
        import_invoice(intersport_original, "anders.pdf", digest, sessions, sf1)
