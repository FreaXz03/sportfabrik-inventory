"""Layout- und Lieferanten-Erkennung (app/services/parsers/__init__.py).

Phase B, „Lieferanten-Erkennung": welches Parser-Modul ist für ein
hochgeladenes Dokument zuständig? Die Tests bauen ihre PDFs selbst mit
PyMuPDF und brauchen darum - im Gegensatz zu tests/test_parser_intersport.py -
keine echte Lieferantenrechnung.
"""

import pymupdf
import pytest

from app.core.i18n import LANGUAGES, translate
from app.services.parsers import (
    PARSERS,
    UnknownLayoutError,
    detect_parser,
    intersport,
    parse_document,
    parse_with_parser,
    read_and_detect,
    read_document,
)

HEADER_LINE = "Marke FEDAS Lief. Art. Art. EAN Bezeichnung Menge Einheit UVP Preis"

# Spalten-x-Positionen für eine vollständige Mini-Rechnung im INTERSPORT-
# Layout. Weit genug auseinander, dass keine Spalte in die nächste läuft
# (der Parser ordnet jedes Wort über seine linke Kante einer Spalte zu).
COLUMNS = [
    ("Marke", 30),
    ("FEDAS", 120),
    ("Lief.", 210),
    ("Art.", 300),
    ("Art.", 390),
    ("EAN", 470),
    ("Bezeichnung", 570),
    ("Menge", 680),
    ("Einheit", 740),
    ("UVP", 820),
    ("Preis", 890),
]
POSITION = [
    "Nike",
    "224100",
    "A1",
    "9988770010",
    "4006632041234",
    "Poloshirt",
    "5",
    "Stk",
    "49.90",
    "30.00",
]
# Kopfzeile: Lief. und die erste Art.-Spalte gehören beim Auslesen zusammen
# (Lieferanten-Artikelnummer), darum hat die Position eine Spalte weniger.
POSITION_COLUMNS = [x for _, x in COLUMNS if x != 300]


def _text_pdf(*lines_of_text: str) -> bytes:
    """Einseitige PDF mit Textebene - eine Zeile je Argument."""
    with pymupdf.open() as document:
        page = document.new_page()
        for index, text in enumerate(lines_of_text):
            page.insert_text((30, 40 + index * 20), text)
        return document.tobytes()


def _invoice_pdf(*, header_lines=(), rows=(POSITION,)) -> bytes:
    """Einseitige PDF im INTERSPORT-Layout: Kopfzeilen (frei), darunter die
    Positionstabelle mit Kopfzeile und einer Zeile je Eintrag in `rows`
    (Werte in der Reihenfolge von POSITION)."""
    with pymupdf.open() as document:
        page = document.new_page(width=1000, height=800)
        for index, line in enumerate(header_lines):
            for x, text in line:
                page.insert_text((x, 40 + index * 20), text)
        for label, x in COLUMNS:
            page.insert_text((x, 200), label)
        for index, row in enumerate(rows):
            for x, value in zip(POSITION_COLUMNS, row):
                if value:
                    page.insert_text((x, 240 + index * 20), value)
        return document.tobytes()


def _document(*lines_of_text: str):
    return read_document(_text_pdf(*lines_of_text))


# --- Schnittstellenvertrag -------------------------------------------------


@pytest.mark.parametrize("parser", PARSERS, ids=lambda p: p.KEY)
def test_every_registered_parser_fulfils_the_interface(parser):
    """Ein neues Layout-Modul muss alles mitbringen, was Registry und Import
    davon erwarten (siehe app/services/parsers/intersport.py)."""
    assert isinstance(parser.KEY, str) and parser.KEY
    assert isinstance(parser.LIEFERANT_NAME, str) and parser.LIEFERANT_NAME
    assert callable(parser.detect) and callable(parser.parse) and callable(parser.dates)


def test_parser_keys_are_unique():
    assert len({p.KEY for p in PARSERS}) == len(PARSERS)


def test_parser_key_has_a_matching_supplier_seed():
    """`parser_key` verbindet Parser-Modul und Lieferanten-Stammdaten - ohne
    passenden Seed-Eintrag bricht der Import mit „Kein Lieferant" ab."""
    from app.core.lieferanten import LIEFERANTEN_SEED

    seeded = {row["parser_key"]: row["name"] for row in LIEFERANTEN_SEED}
    for parser in PARSERS:
        assert seeded.get(parser.KEY) == parser.LIEFERANT_NAME


# --- Erkennung ------------------------------------------------------------


def test_intersport_layout_is_detected():
    document = _document("INTERSPORT Schweiz AG", "Rechnung Nr. 9001759392", HEADER_LINE)
    assert detect_parser(document) is intersport


def test_table_header_alone_is_enough():
    """Auf einem Scan ist der Firmenname (Logo) nicht immer als Text lesbar -
    die Positionstabelle ist das tragende Merkmal."""
    assert detect_parser(_document(HEADER_LINE)) is intersport


def test_supplier_name_alone_is_not_enough():
    """Nur der Name irgendwo im Text macht noch kein bekanntes Layout: ohne
    Positionstabelle kann der Parser nichts auslesen."""
    with pytest.raises(UnknownLayoutError):
        detect_parser(_document("INTERSPORT Schweiz AG", "Rechnung Nr. 4711"))


def test_unknown_layout_names_the_consequence():
    """Ein fremdes Layout (Alpina, CMP, externer Händler ...) kann ohne KI
    nicht automatisch gelesen werden - die Meldung sagt das und verweist auf
    das Weitergeben des Beispiels (projekt-kontext.md Abschnitt 6, Punkt 1)."""
    with pytest.raises(UnknownLayoutError) as error:
        parse_document(_text_pdf("Alpina Auftragsbestätigung 160165", "Pos Artikel Menge"))
    assert str(error.value) == translate("errors.parser.unknown_layout", hint="")


@pytest.mark.parametrize("language", LANGUAGES)
def test_unknown_layout_message_is_translated(language):
    with pytest.raises(UnknownLayoutError) as error:
        parse_document(_text_pdf("Ein fremdes Dokument"), language)
    assert str(error.value) == translate(
        "errors.parser.unknown_layout", language, hint=""
    )


def test_higher_score_wins(monkeypatch):
    """Zwei passende Layouts: das mit der höheren Punktzahl gewinnt - so
    verdrängt ein spezifischer Parser einen allgemeineren."""

    class Generic:
        KEY = "generic"
        LIEFERANT_NAME = "Allgemeines Layout"
        detect = staticmethod(lambda document: 1)
        parse = staticmethod(lambda document, language="de": {})
        dates = staticmethod(lambda document, language="de": {})

    monkeypatch.setattr("app.services.parsers.PARSERS", (Generic, intersport))
    assert detect_parser(_document(HEADER_LINE)) is intersport


def test_ambiguous_detection_is_an_error_instead_of_a_coin_toss(monkeypatch):
    """Gleichstand heisst: die Erkennung weiss es nicht. Dann lieber eine
    klare Meldung als ein zufällig gewählter Lieferant."""

    class Twin:
        KEY = "zwilling"
        LIEFERANT_NAME = "Zwilling AG"
        detect = staticmethod(lambda document: 4)
        parse = staticmethod(lambda document, language="de": {})
        dates = staticmethod(lambda document, language="de": {})

    monkeypatch.setattr("app.services.parsers.PARSERS", (Twin, intersport))
    with pytest.raises(UnknownLayoutError) as error:
        detect_parser(_document(HEADER_LINE, "INTERSPORT", "Rechnung Nr. 1"))
    assert "Zwilling AG" in str(error.value)
    assert intersport.LIEFERANT_NAME in str(error.value)


# --- Ergebnis der Erkennung ----------------------------------------------


def test_parse_document_reports_supplier_and_document_type():
    result = parse_document(
        _invoice_pdf(
            header_lines=[
                [(30, "INTERSPORT"), (200, "Schweiz"), (300, "AG")],
                [(30, "Rechnung"), (130, "Nr."), (200, "9001759392")],
            ]
        )
    )
    assert result["parser_key"] == intersport.KEY
    assert result["supplier_name"] == intersport.LIEFERANT_NAME
    assert result["document_type"] == "rechnung"
    assert result["invoice_number"] == "9001759392"
    assert result["item_count"] == 1
    assert result["warnings"] == []
    assert result["rows_with_warnings"] == 0
    item = result["items"][0]
    assert item["brand"] == "Nike"
    assert item["fedas_code"] == "224100"
    assert item["supplier_article_no"] == "A1"
    assert item["ean"] == "4006632041234"
    assert item["uvp"] == "49.90"


def test_document_type_stays_open_without_the_invoice_anchor():
    """Ohne „Rechnung Nr." ist der Typ offen - der Import weist das Dokument
    dann ohnehin ab (fehlende Belegnummer), statt einen Typ zu raten."""
    result = parse_document(_invoice_pdf())
    assert result["document_type"] is None
    assert result["invoice_number"] is None
    assert result["item_count"] == 1


# --- Einmal lesen ---------------------------------------------------------


def test_document_is_read_once_for_detection_positions_and_dates(monkeypatch):
    """Erkennung, Positionen und Datumsfelder arbeiten auf demselben
    eingelesenen Dokument (genau wie im Import, app/services/importer.py):
    sonst läuft bei einem Scan die Texterkennung mehrfach über dieselben
    Seiten - im Ladennetz spürbar."""
    from app.services.parsers import base

    read_pages = []
    original = base.read_page

    def counting_read_page(page, number, language="de"):
        read_pages.append(number)
        return original(page, number, language)

    monkeypatch.setattr(base, "read_page", counting_read_page)
    pdf = _invoice_pdf(
        header_lines=[
            [(30, "INTERSPORT"), (200, "Schweiz"), (300, "AG")],
            [(30, "Rechnung"), (130, "Nr."), (200, "9001759392")],
            [(30, "Rechnungsdatum"), (200, "05.08.2026")],
            [(30, "Belegdatum"), (200, "04.08.2026")],
        ]
    )
    document, parser = read_and_detect(pdf)
    parsed = parse_with_parser(parser, document)
    dates = parser.dates(document)

    assert read_pages == [1]
    assert parsed["invoice_number"] == "9001759392"
    assert str(dates["invoice_date"]) == "2026-08-05"
    assert str(dates["document_date"]) == "2026-08-04"
