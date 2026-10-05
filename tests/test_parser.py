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
from datetime import date
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest
from conftest import CHEF, neue_datenbank
from sqlalchemy import func, select
from testbelege import POSITIONEN, QUINTET_BLOECKE, auftragsbestaetigung_pdf, quintet_pdf, rechnung_pdf, text_pdf

from app.core.i18n import LANGUAGES, translate
from app.core.lieferanten import LIEFERANTEN_SEED
from app.core.models import Lagerort, Lieferant, Variante, Wareneingang, WareneingangPosition
from app.services import ocr
from app.services.importer import ImportRejected, import_invoice
from app.services.lagerorte import lade_adressen
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


def _rechnung_mit_folgeseite(*, mit_total: bool) -> bytes:
    """Rechnung, deren Positionen auf Seite 1 enden; Seite 2 trägt nur noch
    MWST-Zusammenfassung, AGB und Fusszeile (keine Positionstabelle)."""
    with pymupdf.open(stream=rechnung_pdf()) as document:
        if mit_total:
            document[0].insert_text((30, 360), "Total CHF inkl. MwSt. 400.00")
        seite = document.new_page(width=1000, height=800)
        for index, text in enumerate(
            ["Rechnung Nr. 9001759392", "MWST ID MWST % MWST Basis MWST-Betrag", "Total 400.00 32.40"]
        ):
            seite.insert_text((30, 40 + index * 20), text)
        return document.tobytes()


def test_folgeseite_ohne_positionen_nach_dem_total_wird_uebersprungen():
    ergebnis = parse_document(_rechnung_mit_folgeseite(mit_total=True))
    assert ergebnis["item_count"] == 3 and ergebnis["warnings"] == []
    assert ergebnis["page_item_counts"] == [3, 0]


def test_intersport_auftragsbestaetigung_wird_gelesen():
    """INTERSPORT-AB (z. B. The North Face): ohne EAN, „EP" statt „Preis",
    Farbe/Grösse in der ersten Bezeichnungszeile, umbrechend."""
    document, parser = read_and_detect(auftragsbestaetigung_pdf())
    ergebnis = parse_with_parser(parser, document)
    assert parser is intersport
    assert ergebnis["document_type"] == "auftragsbestaetigung"
    assert ergebnis["invoice_number"] == "900-VA0212349"
    assert ergebnis["warnings"] == [] and ergebnis["rows_with_warnings"] == 0
    erste, zweite = ergebnis["items"]
    assert (erste["brand"], erste["supplier_article_no"], erste["article_no"]) == (
        "The North Face", "NF0A52SA", "186391.084"
    )
    assert erste["description"] == "BASE CAMP DUFFEL - M"
    assert (erste["color"], erste.get("size_original", erste["size"])) == (
        "Summit Gold-TNF Black-N", "ONESIZE"
    )
    assert (erste["quantity"], erste["uvp"], erste["ek"], erste["ean"]) == ("2", "170.00", "82.95", "")
    assert zweite["color"] == "Summit Navy-TNF Black-N" and zweite["quantity"] == "1"
    daten = parser.dates(document)
    assert str(daten["invoice_date"]) == str(daten["document_date"]) == "2026-07-15"


def test_auftragsbestaetigung_ohne_titel_nimmt_die_shop_auftragsnummer():
    document, parser = read_and_detect(auftragsbestaetigung_pdf(titel=False))
    ergebnis = parse_with_parser(parser, document)
    assert ergebnis["document_type"] == "auftragsbestaetigung"
    assert ergebnis["invoice_number"] == "678235_1"
    assert str(parser.dates(document)["invoice_date"]) == "2026-07-15"


def test_quer_gedrehter_text_wird_wie_normaler_gelesen():
    """Manche PDFs legen die Querformat-Seite gedreht auf ein Hochformat-Blatt
    (Text läuft von unten nach oben, Seitendrehung trotzdem 0)."""
    with pymupdf.open(stream=auftragsbestaetigung_pdf()) as quelle, pymupdf.open() as gedreht:
        seite = gedreht.new_page(width=800, height=1200)
        seite.show_pdf_page(seite.rect, quelle, 0, rotate=90)
        pdf = gedreht.tobytes()
    document, parser = read_and_detect(pdf)
    ergebnis = parse_with_parser(parser, document)
    assert ergebnis["warnings"] == [] and ergebnis["item_count"] == 2
    assert str(parser.dates(document)["invoice_date"]) == "2026-07-15"
    assert ergebnis["items"][0]["supplier_article_no"] == "NF0A52SA"
    assert ergebnis["items"][1]["color"] == "Summit Navy-TNF Black-N"


# --- Quintet 24 (Bestellinformation The North Face) -------------------------


def test_quintet_bestellung_wird_je_groesse_gelesen():
    document, parser = read_and_detect(quintet_pdf())
    ergebnis = parse_with_parser(parser, document)
    assert parser.KEY == "quintet" and ergebnis["supplier_name"] == "The North Face"
    assert (ergebnis["document_type"], ergebnis["invoice_number"]) == ("bestellung", "603515")
    assert str(parser.dates(document)["invoice_date"]) == "2025-12-15"
    assert ergebnis["warnings"] == [] and ergebnis["rows_with_warnings"] == 0
    zeilen = [
        (
            i["supplier_article_no"], i["article_no"], i["description"], i["color"],
            i.get("size_original", i["size"]), i["quantity"], i["ek"], i["uvp"],
        )
        for i in ergebnis["items"]
    ]
    assert zeilen == [
        ("NF0A8BX1", "356343", "M COMBAL SOFTSHELL 2.0", "TNF BLACK", "S", "1", "60.50", "130.00"),
        ("NF0A8BX1", "356343", "M COMBAL SOFTSHELL 2.0", "TNF BLACK", "M", "2", "60.50", "130.00"),
        ("NF0A8J4S", "394034", "M RILA FULL ZIP FLEECE JACKET", "ANTHRACITE GREY/TNF BLA", "XLREGULAR", "1", "1048.85", "2100.00"),
        ("NF0A8J4S", "394034", "M RILA FULL ZIP FLEECE JACKET", "ANTHRACITE GREY/TNF BLA", "36Regular", "2", "1048.85", "2100.00"),
    ]
    assert all(i["brand"] == "The North Face" and i["ean"] == "" for i in ergebnis["items"])


def test_quintet_mengen_die_nicht_aufgehen_sperren_den_import():
    falsch = [dict(QUINTET_BLOECKE[0], total=("4", "60,50", "242,00"))]
    ergebnis = parse_document(quintet_pdf(falsch, wert=("4", "242,00")))
    assert ergebnis["rows_with_warnings"] == 2
    falscher_wert = parse_document(quintet_pdf(wert=("7", "3.328,05")))
    assert len(falscher_wert["warnings"]) == 1


def test_quintet_ohne_the_north_face_ist_unbekannt():
    """Der Lieferant hängt an der Marke; andere Marken werden nicht geraten."""
    with pytest.raises(UnknownLayoutError):
        detect_parser(read_document(text_pdf("Lieferantartikel Nr. X1", "Bestellinformation aus Quintet 24")))


def test_seite_ohne_tabellenkopf_vor_dem_total_bleibt_ein_fehler():
    """Ohne Total ist offen, ob auf Seite 2 Positionen fehlen (z. B. Scan)."""
    with pytest.raises(DocumentParseError) as fehler:
        parse_document(_rechnung_mit_folgeseite(mit_total=False))
    assert "2" in str(fehler.value)


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
    # Referenz „SCH-SF ret.Ecom": eine ECOM-Retoure (Code 555), mit EK.
    assert ergebnis["lieferant_typ"] == "ecom"
    assert ergebnis["items"][0]["ek"] == "37.15"

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


# --- Beispielbelege der Lieferanten (nur lokal, Freigabe 24.09.2026) ------
#
# BELEGE_DIR zeigt auf den Ordner mit den Originalen (bei Fabian der Ordner
# „Anhänge" im Obsidian-Vault). Erwartet sind die Werte, die im Beleg stehen;
# „menge" ist die Summe aller Stück, wie sie der Beleg selbst ausweist.

AB = "auftragsbestaetigung"
BELEGE = {
    # Papierrechnung ohne Textebene (Texterkennung). „Preis" ist hier brutto,
    # der Rabatt steht unten als Rechnungsrabatt - darum kein EK je Position.
    # Gegenprobe: Warenwert 10'835.40 - Rabatt 6'501.24 = Total 4'334.15.
    "9001665373 SF 1.pdf": dict(
        lieferant="INTERSPORT Schweiz AG", typ="rechnung", nummer="9001665373",
        datum=date(2025, 12, 19), belegdatum=date(2025, 12, 18), status="eingetroffen", gruppe="intersport",
        lagerort="SF1", positionen=31, menge="41", ocr=True,
        erste=dict(brand="Giro", fedas_code="101921", ean="196178062282", description="Tor Spherical Helmet",
                   color="matte dark shark", size="M 55.5-59 CM", quantity="1", uvp="300.00", ek=None),
    ),
    "SF1 Volketswil-1.pdf": dict(
        lieferant="ALPINA SPORTS Schweiz AG", typ=AB, nummer="160165", datum=date(2026, 9, 7),
        lagerort="SF1", positionen=10, menge="31", artikel={"A9801", "A9802", "A9809"},
        erste=dict(brand="Alpina", supplier_article_no="A9801", article_no="A9801132", description="TAUNUS",
                   color="burro-brown matt", size="52-56", quantity="4", unit="Stück", uvp="89.90", ek="22.50", ean=""),
    ),
    # Referenz SF3 Regensdorf, geliefert wird aber nach Volketswil (D19: der
    # Vorschlag folgt der Lieferadresse und bleibt änderbar).
    "SF3 Regensdorf.pdf": dict(
        lieferant="ALPINA SPORTS Schweiz AG", typ=AB, nummer="160166", datum=date(2026, 9, 7),
        lagerort="SF1", positionen=10, menge="30", artikel={"A9801", "A9802", "A9809"},
    ),
    "CS-12809663_AB_SF1 1.pdf": dict(
        lieferant="CHRIS sports AG", typ=AB, nummer="CS-12809663", datum=date(2026, 4, 22),
        lagerort="SF1", positionen=22, menge="152",
        erste=dict(brand="Giro", supplier_article_no="3605000007", description="Seasonal Merino Sock",
                   color="black/lime breakdown", size="S", ean="768686495908", unit="Paar",
                   quantity="9", uvp="13.00", ek="3.90"),
    ),
    "CS-12809656_AB_SF1 1.pdf": dict(
        lieferant="CHRIS sports AG", typ=AB, nummer="CS-12809656", datum=date(2026, 4, 22),
        lagerort="SF1", positionen=32, menge="188",
    ),
    "AB-AW26 SPORT-FABRIK VOLKETSWIL BOYS OUTDOOR_BILD 2.pdf": dict(
        lieferant="CMP (F.lli Campagnolo S.p.A.)", typ=AB, nummer="2026A-F30-246", datum=date(2025, 12, 9),
        lagerort="GEWA", menge="660",
        erste=dict(brand="CMP", supplier_article_no="30A1494", description="KID LONG PANT",
                   color="OLIVE ANTRACITE", size="98", quantity="4", unit="Stk", uvp="69.90", ek="31.75", ean=""),
    ),
    "AB-AW26 SPORT-FABRIK VOLKETSWIL GIRLS OUTDOOR_BILD 2.pdf": dict(
        lieferant="CMP (F.lli Campagnolo S.p.A.)", typ=AB, nummer="2026A-F30-245", datum=date(2025, 12, 9),
        lagerort="GEWA", menge="572",
    ),
    "AB-AW26 SPORT-FABRIK VOLKETSWIL DAMEN OUTDOOR_BILD 2.pdf": dict(
        lieferant="CMP (F.lli Campagnolo S.p.A.)", typ=AB, nummer="2026A-F30-247", datum=date(2025, 12, 9),
        lagerort="GEWA", menge="1280",
    ),
    "AB-AW26 SPORT-FABRIK VOLKETSWIL HERREN OUTDOOR_BILD 2.pdf": dict(
        lieferant="CMP (F.lli Campagnolo S.p.A.)", typ=AB, nummer="2026A-F30-248", datum=date(2025, 12, 9),
        lagerort="GEWA", menge="928",
    ),
    "AB-AW26 SPORT-FABRIK VOLKETSWIL DAMEN HERREN GIRLS BOYS RAINWEAR_BILD 2.pdf": dict(
        lieferant="CMP (F.lli Campagnolo S.p.A.)", typ=AB, nummer="2026A-F30-249", datum=date(2025, 12, 9),
        lagerort="GEWA", menge="1908",
    ),
}


def _beleg(name):
    ordner = os.environ.get("BELEGE_DIR")
    if not ordner or not (Path(ordner) / name).exists():
        pytest.skip("BELEGE_DIR auf den Ordner mit den Beispielbelegen setzen")
    return (Path(ordner) / name).read_bytes()


@pytest.mark.parametrize("name", BELEGE, ids=lambda n: n[:24])
def test_beispielbeleg_wird_gelesen_und_importiert(name):
    soll = BELEGE[name]
    pdf = _beleg(name)
    sessions = neue_datenbank()
    with sessions() as session:
        lagerorte = lade_adressen(session)
    ergebnis = parse_document(pdf, lagerorte=lagerorte)
    assert ergebnis["supplier_name"] == soll["lieferant"]
    assert (ergebnis["document_type"], ergebnis["invoice_number"]) == (soll["typ"], soll["nummer"])
    assert ergebnis["warnings"] == [] and ergebnis["rows_with_warnings"] == 0, (
        ergebnis["warnings"], [i["warnings"] for i in ergebnis["items"] if i["warnings"]][:3]
    )
    assert ergebnis["lagerort_suggestion"]["code"] == soll["lagerort"]
    assert format(sum(Decimal(i["quantity"]) for i in ergebnis["items"]).normalize(), "f") == soll["menge"]
    if "positionen" in soll:
        assert ergebnis["item_count"] == soll["positionen"]
    if "artikel" in soll:
        assert {i["supplier_article_no"] for i in ergebnis["items"]} == soll["artikel"]
    for feld, wert in soll.get("erste", {}).items():
        assert ergebnis["items"][0][feld] == wert, feld
    document, parser = read_and_detect(pdf)
    assert parser.dates(document) == {
        "invoice_date": soll["datum"], "document_date": soll.get("belegdatum", soll["datum"])
    }
    assert ergebnis["ocr_used"] is soll.get("ocr", False)

    # Import: Auftragsbestätigung = erwartete Ware, noch kein Bestand (Regel 3);
    # eine Rechnung bucht sofort.
    with sessions() as session:
        ziel = session.scalar(select(Lagerort.id).where(Lagerort.code == soll["lagerort"]))
    import_invoice(pdf, name, hashlib.sha256(pdf).hexdigest(), sessions, ziel)
    with sessions() as session:
        wareneingang = session.scalar(select(Wareneingang))
        assert wareneingang.status == soll.get("status", "erwartet")
        erwartet = session.scalar(select(func.sum(WareneingangPosition.menge)))
        assert format(erwartet.normalize(), "f") == soll["menge"]
        lieferant = session.scalar(select(Lieferant).where(Lieferant.name == soll["lieferant"]))
        # Alpina, Chris Sports, CMP: Code 999 (Fabian, 24.09.2026).
        assert lieferant.typ == soll.get("gruppe", "drittanbieter")


def test_rechnungsrabatt_wird_gegengerechnet():
    """Warenwert - Rechnungsrabatt muss das Total ergeben (Schutz gegen falsch
    gelesene Zahlen, besonders bei Scans); sonst sperrt eine Warnung."""
    gut = rechnung_pdf(rows=POSITIONEN[:1])  # 5 × Preis 30.00 = 150.00
    assert parse_document(gut)["warnings"] == []
    with pymupdf.open(stream=gut, filetype="pdf") as pdf:
        seite = pdf[0]
        seite.insert_text((30, 600), "Rechnungsrabatt 60% - 90.00")
        seite.insert_text((30, 620), "Total CHF inkl. MwSt. 60.00")
        richtig = pdf.tobytes()
    ergebnis = parse_document(richtig)
    assert ergebnis["warnings"] == [] and ergebnis["items"][0]["ek"] is None
    with pymupdf.open(stream=gut, filetype="pdf") as pdf:
        pdf[0].insert_text((30, 600), "Rechnungsrabatt 60% - 90.00")
        pdf[0].insert_text((30, 620), "Total CHF inkl. MwSt. 59.00")
        falsch = pdf.tobytes()
    assert parse_document(falsch)["warnings"]


def test_bolle_rechnung_ohne_uvp_wird_nicht_gelesen():
    """Die Bollé-Rechnung (FaGu) nennt nur den Einkaufspreis, keinen UVP -
    damit lässt sich nichts auszeichnen; sie bleibt aussen vor (24.09.2026)."""
    with pytest.raises(UnknownLayoutError):
        parse_document(_beleg("FaGu00072586-1.pdf"))


# --- Columbia (Auftragsempfangsbestätigung) ------------------------------------


def _columbia_pdf(menge="4", betrag="45,40", zwischensumme="45,40"):
    return text_pdf(
        "Columbia Sportswear International SARL", "Auftragsempfangsbestätigung",
        "Auftrags- Nr.:", "63029341", "Bestelldatum:", "17.08.2026",
        "Gesamt", "Menge", "Preis", "Rabatt %", "Nettopreis / Stück", "Gesamtbetrag",
        "2118541845", "AO3772845 Zero Rules Light SS Grap-Super Sonic, Sc",
        "Größe", "Stückzahl", "-S-", "1 ", "-M-", "0 ", "-XL-", "3 ",
        menge, "22,70 ", "50,00 ", "11,35 ", betrag,
        "Gesamtmenge", f"  {menge} ", "Zwischensumme", f"  {zwischensumme} ",
    )


def test_columbia_auftragsbestaetigung_wird_je_groesse_gelesen():
    document, parser = read_and_detect(_columbia_pdf())
    ergebnis = parse_with_parser(parser, document)
    assert parser.KEY == "columbia" and ergebnis["supplier_name"] == "Columbia"
    assert (ergebnis["document_type"], ergebnis["invoice_number"]) == ("auftragsbestaetigung", "63029341")
    assert str(parser.dates(document)["invoice_date"]) == "2026-08-17"
    assert ergebnis["warnings"] == []
    zeilen = [
        (i["supplier_article_no"], i["article_no"], i["description"], i["color"], i["size"], i["quantity"], i["ek"])
        for i in ergebnis["items"]
    ]
    # Menge 0 (Grösse M) ergibt keine Position; die UVP fehlt im Beleg und wird gemeldet.
    assert zeilen == [
        ("AO3772845", "2118541845", "Zero Rules Light SS Grap", "Super Sonic, Sc", "S", "1", "11.35"),
        ("AO3772845", "2118541845", "Zero Rules Light SS Grap", "Super Sonic, Sc", "XL", "3", "11.35"),
    ]
    assert all(i["uvp"] is None and len(i["warnings"]) == 1 for i in ergebnis["items"])


def test_columbia_summen_die_nicht_aufgehen_werden_gemeldet():
    falsch = parse_document(_columbia_pdf(zwischensumme="50,00"))
    assert len(falsch["warnings"]) == 1
    falsche_zeile = parse_document(_columbia_pdf(betrag="40,00"))
    assert all(len(i["warnings"]) == 2 for i in falsche_zeile["items"])


# --- Gonso (Elastic-Auftrag von ws4sports) -------------------------------------


def _gonso_pdf(einheiten="7", gesamt="445.20"):
    """Ein Block wie im echten Beleg: der Name steht links zwischen
    Tabellenkopf und „Stilnr.:", die Mengen stehen unter ihren Grössen; die
    Grösse M hat keine Menge."""
    with pymupdf.open() as document:
        page = document.new_page()
        for y, x, text in (
            (40, 30, "Elastic-Auftrag # - 28941"), (52, 30, "Auftragsdatum - 06/01/2026"),
            (64, 30, "Einheiten gesamt"), (76, 30, einheiten), (88, 30, "Einzelhandelspreis"),
            (100, 30, "Gesamtbetrag"), (112, 30, f"CHF{gesamt}"),
        ):
            page.insert_text((x, y), text)
        for y, x, text in (
            (170, 263, "Einzelhandel"), (170, 329, "Großhandel"), (170, 447, "Menge"), (170, 554, "Gesamtkosten"),
            (173, 105, '"Sitivo Tight M"'),
            (182, 267, "CHF139.90"), (182, 340, "CHF63.60"), (182, 420, "7"), (182, 470, "CHF445.20"),
            (182, 530, "/"), (182, 540, "CHF979.30"),
            (185, 105, "Stilnr.: 3000402"), (195, 105, 'Farbname: "oak ash"'), (205, 105, "Farbcode: M19018"),
            (210, 244, "Größe/Menge"),
            (222, 250, "S"), (222, 262, "-"), (222, 270, "Normal"),
            (222, 310, "M"), (222, 322, "-"), (222, 330, "Normal"),
            (222, 370, "L"), (222, 382, "-"), (222, 390, "Normal"),
            (222, 430, "XL"), (222, 452, "-"), (222, 462, "Normal"),
            (234, 266, "1"), (234, 386, "2"), (234, 458, "4"),
            (700, 30, "Seite - 1"), (712, 30, "Powered by Elastic"),
        ):
            page.insert_text((x, y), text)
        return document.tobytes()


def test_gonso_auftrag_wird_je_groesse_gelesen():
    document, parser = read_and_detect(_gonso_pdf())
    ergebnis = parse_with_parser(parser, document)
    assert parser.KEY == "gonso" and ergebnis["supplier_name"] == "Gonso"
    assert (ergebnis["document_type"], ergebnis["invoice_number"]) == ("bestellung", "28941")
    assert str(parser.dates(document)["invoice_date"]) == "2026-01-06"
    assert ergebnis["warnings"] == []
    zeilen = [
        (i["supplier_article_no"], i["article_no"], i["description"], i["color"], i["size"], i["quantity"], i["ek"], i["uvp"])
        for i in ergebnis["items"]
    ]
    # Mengen stehen unter ihrer Grösse (x-Position); M hat keine Menge → keine Position.
    assert zeilen == [
        ("3000402", "M19018", "Sitivo Tight M", "oak ash", "S", "1", "63.60", "139.90"),
        ("3000402", "M19018", "Sitivo Tight M", "oak ash", "L", "2", "63.60", "139.90"),
        ("3000402", "M19018", "Sitivo Tight M", "oak ash", "XL", "4", "63.60", "139.90"),
    ]


def test_gonso_summen_die_nicht_aufgehen_werden_gemeldet():
    falsch = parse_document(_gonso_pdf(einheiten="9"))
    assert len(falsch["warnings"]) == 1


# --- Columbia Linesheet (Saisonkatalog ohne Mengen) -----------------------------


def _linesheet_pdf(index_stil="2088363", msrp="165.00"):
    """Titelseite, eine Modellseite (zwei Farben in einem 61-pt-Raster, die
    zweite mit umbrochenem Namen; Grössen XS-XL) und der Stil-Index."""
    with pymupdf.open() as document:
        titel = document.new_page()
        for y, text in ((40, "CHE | F26"), (60, "SPORT-FABRIK"), (80, "OUTDOOR"), (100, "F26"), (120, "Created 12/17/2025 9:01 PST")):
            titel.insert_text((30, y), text)
        seite = document.new_page()
        for x, y, text in (
            (30, 20, "LAKE 22 II DOWN JACKET"), (30, 50, "2088363"), (30, 70, "FEATURES"), (30, 90, "Heat Seal"),
            (142, 180, "348"), (203, 180, "125"),
            (142, 190, "Safari"), (203, 190, "Sea Salt,"), (203, 200, "Dark Stone"),
            (346, 220, msrp), (410, 220, "MSRP"),
            (142, 230, "XS"), (170, 230, "S"), (190, 230, "M"), (210, 230, "L"), (230, 230, "XL"),
            (346, 240, "78.60"), (410, 240, "BASE"),
        ):
            seite.insert_text((x, y), text)
        ende = document.new_page()
        for y, text in ((40, "Columbia Sportswear International SaRL"), (60, "STYLE NUMBER INDEX"), (80, f"{index_stil}........ 1")):
            ende.insert_text((30, y), text)
        return document.tobytes()


def test_columbia_linesheet_wird_je_farbe_und_groesse_gelesen():
    document, parser = read_and_detect(_linesheet_pdf())
    ergebnis = parse_with_parser(parser, document)
    assert parser.KEY == "columbia" and ergebnis["supplier_name"] == "Columbia"
    assert ergebnis["document_type"] == "bestellung"
    assert ergebnis["invoice_number"].startswith("COLUMBIA-F26-OUTDOOR-")
    assert str(parser.dates(document)["invoice_date"]) == "2025-12-17"
    assert ergebnis["warnings"] == []
    zeilen = {(i["article_no"], i["color"], i["size"]) for i in ergebnis["items"]}
    assert zeilen == {(f"2088363{code}", farbe, groesse) for code, farbe in (("348", "Safari"), ("125", "Sea Salt, Dark Stone")) for groesse in ("XS", "S", "M", "L", "XL")}
    # Keine Menge im Dokument: Menge 0 (legt Artikel an, bucht nichts); MSRP = UVP, BASE = EK.
    assert {(i["quantity"], i["uvp"], i["ek"]) for i in ergebnis["items"]} == {("0", "165.00", "78.60")}


def test_columbia_linesheet_meldet_abweichenden_stil_index():
    ergebnis = parse_document(_linesheet_pdf(index_stil="2088999"))
    assert len(ergebnis["warnings"]) == 1


def test_columbia_linesheet_praeparierte_seite_wird_begrenzt_gemeldet():
    """Resource guard: a page with thousands of 3-digit words is reported, not crunched."""
    with pymupdf.open() as document:
        titel = document.new_page()
        titel.insert_text((30, 40), "CHE | F26 OUTDOOR Created 12/17/2025")
        seite = document.new_page()
        seite.insert_text((30, 50), "2088363")
        for index in range(300):
            seite.insert_text((142 + (index % 6) * 60, 80 + (index // 6) * 2), "123")
        seite.insert_text((346, 700), "165.00")
        seite.insert_text((410, 700), "MSRP")
        seite.insert_text((346, 720), "78.60")
        seite.insert_text((410, 720), "BASE")
        seite.insert_text((142, 710), "XS S M")
        ende = document.new_page()
        for y, text in ((40, "Columbia Sportswear International SaRL"), (60, "STYLE NUMBER INDEX"), (80, "2088363........ 1")):
            ende.insert_text((30, y), text)
        pdf = document.tobytes()
    with pytest.raises(DocumentParseError):
        parse_document(pdf)


def test_columbia_linesheet_zu_viele_varianten_je_farbe_werden_gemeldet():
    """Resource guard: sizes x lengths must stay small; the model is reported, not expanded."""
    with pymupdf.open() as document:
        titel = document.new_page()
        titel.insert_text((30, 40), "CHE | F26 OUTDOOR Created 12/17/2025")
        seite = document.new_page()
        seite.insert_text((30, 50), "2088363")
        seite.insert_text((142, 180), "348")
        seite.insert_text((142, 190), "Safari")
        seite.insert_text((346, 220), "165.00")
        seite.insert_text((410, 220), "MSRP")
        seite.insert_text((346, 240), "78.60")
        seite.insert_text((410, 240), "BASE")
        # Tiny font so that many sizes and lengths fit into the size column.
        seite.insert_text((142, 230), " ".join(str(n) for n in range(20, 45)) + " \u25b2 " + " ".join(f"{n}" for n in range(1, 26)), fontsize=3)
        ende = document.new_page()
        for y, text in ((40, "Columbia Sportswear International SaRL"), (60, "STYLE NUMBER INDEX"), (80, "2088363........ 1")):
            ende.insert_text((30, y), text)
        pdf = document.tobytes()
    with pytest.raises(DocumentParseError):
        parse_document(pdf)

# --- Columbia: gescannte Linesheets ----------------------------------------


def _scan_block(**changes):
    block = dict(stil="1234567", titel="TEST JACKET", seite=2,
                 farben=[("010", "Black"), ("125", "Sea Salt")],
                 groessen=["XS", "S", "M"], laengen=[], uvp="120.00", ek="60.00",
                 roh=["1234567 XS S M 120.00 MSRP 60.00 BASE"], unsicher=False)
    return {**block, **changes}


def test_columbia_scan_positionen_und_fehlende_bloecke(monkeypatch):
    from app.services.parsers import columbia_scan
    from app.services.parsers.base import Document, Page
    native = read_document(_linesheet_pdf())
    scan = Document([Page(p.number, p.words, p.text, p.height, True) for p in native.pages])
    monkeypatch.setattr(columbia_scan, "lesen", lambda document, language: dict(
        bloecke=[_scan_block(), _scan_block(stil="7654321", groessen=[])],
        index={"1234567", "7654321"}, kopf="CHE F26 OUTDOOR Created 12/17/2025",
    ))
    parser = detect_parser(scan)
    result = parse_with_parser(parser, scan, "en")
    assert result["document_type"] == "bestellung"
    assert result["item_count"] == 6
    assert {i["quantity"] for i in result["items"]} == {"0"}
    assert {i["ek"] for i in result["items"]} == {"60.00"}
    assert result["warnings"] and any("7654321" in w for w in result["warnings"])
    assert parser.dates(scan)["document_date"] == date(2025, 12, 17)


def test_columbia_scan_groessen_werden_nicht_erfunden():
    from app.services.parsers.columbia_scan import groessen
    assert groessen("XS SMLXL") == (["XS", "S", "M", "L", "XL"], True)
    assert groessen("7-15") == (["7-15"], True)
    assert groessen("XS ? XL") == ([], True)
    assert groessen("O/S") == (["O/S"], False)
    assert groessen("XS XS") == ([], True)


def test_columbia_scan_unsichere_zahlen_und_index():
    from app.services.parsers.columbia_scan import auswerten
    document = read_document(_linesheet_pdf())
    result = auswerten(document, dict(bloecke=[_scan_block(uvp=None, ek=None)],
        index=set(), kopf="F26 OUTDOOR"), "en")
    assert result["item_count"] == 6
    assert all(i["uvp"] is None and i["ek"] is None and i["warnings"] for i in result["items"])
    assert any("index" in w.lower() for w in result["warnings"])


@pytest.mark.skipif(not os.environ.get("COLUMBIA_SCAN_DIR"), reason="Local Columbia scans not supplied")
def test_columbia_scans_lokal():
    folder = Path(os.environ["COLUMBIA_SCAN_DIR"])
    files = sorted(folder.glob("*.pdf"))
    assert len(files) == 4
    for path in files:
        document, parser = read_and_detect(path.read_bytes())
        result = parse_with_parser(parser, document)
        assert parser.KEY == "columbia" and result["document_type"] == "bestellung"
        assert result["item_count"] > 0 and result["ocr_used"]
        assert all(i["quantity"] == "0" for i in result["items"])
        assert result["warnings"]  # OCR bleibt prüfpflichtig.
        assert parser.dates(document)["document_date"].year == 2025


def test_columbia_scan_preise_farben_und_laengen_aus_ocr_woertern():
    from app.services.parsers.columbia_scan import _farben, _preis, laengen
    def wort(x, y, text, confidence=95):
        return (x, y, x + 15, y + 4, text, confidence, 0, 0)
    preise = [wort(335, 240, "120,00"), wort(375, 240, "MSRP"),
              wort(335, 249, "60.00"), wort(375, 249, "BASE")]
    assert _preis(preise, "MSRP") == "120.00"
    assert _preis(preise, "BASE") == "60.00"
    assert _preis(preise + [wort(350, 240, "130.00")], "MSRP") is None
    assert _preis([wort(335, 240, "12O.OO"), wort(375, 240, "MSRP")], "MSRP") is None
    assert _preis([wort(335, 240, "120.00", 30), wort(375, 240, "MSRP")], "MSRP") is None
    assert _farben([wort(150, 220, "010"), wort(150, 226, "Black"),
                    wort(250, 220, "125"), wort(250, 226, "Sea"), wort(275, 226, "Salt"),
                    wort(330, 220, "999", 20)]) == [("010", "Black"), ("125", "Sea Salt")]
    assert laengen("A S R L") == (["S", "R", "L"], False)
    assert laengen("A 25in / 63.5cm") == ([], False)
    assert laengen("A ? R") == ([], True)


def test_columbia_scan_unbekanntes_layout_und_datum(monkeypatch):
    from app.services.parsers import columbia_scan
    from app.services.parsers.base import Document, Page
    document = read_document(text_pdf("Columbia", "Invoice", "MSRP", "BASE"))
    scan = Document([Page(p.number, p.words, p.text, p.height, True) for p in document.pages])
    assert not columbia_scan.erkenne(scan)
    with pytest.raises(UnknownLayoutError):
        detect_parser(scan)
    for kopf in ("F26", "Created 02/31/2025"):
        monkeypatch.setattr(columbia_scan, "lesen", lambda *args: {"kopf": kopf})
        with pytest.raises(DocumentParseError):
            columbia_scan.dates(scan)


def test_columbia_scan_fehlender_anker_wird_gemeldet(monkeypatch):
    from app.services.parsers.columbia_scan import _raster
    from app.services import ocr_raster
    def kein_ausschnitt(*args, **kwargs):
        pytest.fail("Invalid anchor must not reach raster rendering")
    monkeypatch.setattr(ocr_raster, "_ausschnitt", kein_ausschnitt)
    result = _raster(_linesheet_pdf(), ((2, "modell", (("?", -100, ""),)),))
    assert result["bloecke"][0]["fehler"] is True
