"""Tests für den OCR-Fallback (app/services/ocr.py) für eingescannte
Papierrechnungen ohne Textebene.

Die reine Wort-Aufbereitung (Rauschen entfernen, Tesseract-Zeilen zu
PyMuPDF-kompatiblen Wort-Tupeln normalisieren) wird deterministisch mit
handgebauten Tesseract-Rohdaten getestet, ganz ohne echtes Tesseract.

test_ocr_fallback_end_to_end baut zusätzlich eine echte, aber synthetische
Scan-Seite (per PIL gezeichneter Text, ohne Textebene) und lässt sie durch
den kompletten parse_invoice-Pfad laufen. Dieser Test braucht ein
installiertes Tesseract und wird andernfalls übersprungen (z. B. auf einem
Windows-Entwicklungsrechner ohne lokale Tesseract-Installation - siehe
SERVER-SETUP.md)."""

from pathlib import Path
import shutil

import pymupdf
import pytest

from app.services import ocr
from app.services.parser import InvoiceParseError, parse_invoice

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


def test_clean_word_strips_leading_and_trailing_noise():
    assert ocr._clean_word("_Marke_") == "Marke"
    assert ocr._clean_word("|Stk") == "Stk"
    assert ocr._clean_word("12,99=") == "12,99"
    assert ocr._clean_word("normal") == "normal"


def test_clean_word_does_not_touch_noise_in_the_middle():
    # Ein Bindestrich in der Wortmitte (z.B. "Air-Max") ist kein Scan-Rauschen.
    assert ocr._clean_word("Air-Max") == "Air-Max"


def _tesseract_row(
    words, block=1, par=1, line=1, top=100, height=30, gap=20, left_start=50
):
    """Baut ein Fragment eines pytesseract image_to_data(output_type=DICT)
    Ergebnisses für eine einzelne Textzeile: gleiche (block, par, line), aber
    mit der für Tesseract typischen Boxen-Jitter zwischen einzelnen Wörtern
    (leicht unterschiedliche top/height je Wort)."""
    data = {
        "text": [],
        "block_num": [],
        "par_num": [],
        "line_num": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "word_num": [],
    }
    left = left_start
    for i, word in enumerate(words):
        width = len(word) * 18
        data["text"].append(word)
        data["block_num"].append(block)
        data["par_num"].append(par)
        data["line_num"].append(line)
        data["left"].append(left)
        data["width"].append(width)
        # Jitter: jedes Wort schwankt um ein paar Pixel in top/height.
        data["top"].append(top + (2 if i % 2 else -2))
        data["height"].append(height + (3 if i % 2 else 0))
        data["word_num"].append(i + 1)
        left += width + gap
    return data


def _merge(*rows):
    merged = {
        "text": [],
        "block_num": [],
        "par_num": [],
        "line_num": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "word_num": [],
    }
    for row in rows:
        for key in merged:
            merged[key].extend(row[key])
    return merged


def test_grouped_words_normalises_y_per_tesseract_line():
    data = _tesseract_row(["Marke", "EAN", "Menge"], top=100)
    words = ocr._grouped_words(data)
    assert [w[4] for w in words] == ["Marke", "EAN", "Menge"]
    # Trotz Jitter in den Rohdaten (top +-2, height +0/+3) teilen sich alle
    # Wörter derselben Tesseract-Zeile dieselbe y0/y1 - sonst reisst
    # parser.lines() (Toleranz 2pt) die Kopfzeile fälschlich auseinander.
    y0s = {round(w[1], 6) for w in words}
    y1s = {round(w[3], 6) for w in words}
    assert len(y0s) == 1 and len(y1s) == 1


def test_grouped_words_converts_pixels_to_points():
    ocr_top = 600
    data = {
        "text": ["Test"],
        "block_num": [1],
        "par_num": [1],
        "line_num": [1],
        "left": [300],
        "top": [ocr_top],
        "width": [len("Test") * 18],
        "height": [30],
        "word_num": [1],
    }
    words = ocr._grouped_words(data)
    x0, y0, x1, y1, word, *_rest = words[0]
    scale = 72 / ocr.OCR_DPI
    assert word == "Test"
    assert x0 == pytest.approx(300 * scale)
    assert y0 == pytest.approx(ocr_top * scale)
    assert x1 == pytest.approx((300 + len("Test") * 18) * scale)
    assert y1 == pytest.approx((ocr_top + 30) * scale)


def test_grouped_words_drops_punctuation_only_noise():
    # Ein einzelner Fleck/Tabellenrand, den Tesseract als "=" oder ";"
    # misliest, darf keine leere Zeile als "Position" vortäuschen.
    data = _tesseract_row(["Marke", "=", ";", "__"])
    words = ocr._grouped_words(data)
    assert [w[4] for w in words] == ["Marke"]


def test_grouped_words_keeps_separate_lines_separate():
    header = _tesseract_row(["Marke", "EAN"], line=1, top=100)
    body = _tesseract_row(["Nike", "4006632041234"], line=2, top=250)
    words = ocr._grouped_words(_merge(header, body))
    header_y = {round(w[1], 3) for w in words if w[4] in ("Marke", "EAN")}
    body_y = {round(w[1], 3) for w in words if w[4] in ("Nike", "4006632041234")}
    assert len(header_y) == 1 and len(body_y) == 1
    assert header_y != body_y


def test_ocr_page_raises_when_pytesseract_missing(monkeypatch):
    monkeypatch.setattr(ocr, "pytesseract", None)
    monkeypatch.setattr(ocr, "Image", None)
    with pytest.raises(ocr.OcrUnavailableError, match="Texterkennung"):
        ocr.ocr_page(page=None)


def test_ocr_page_raises_when_tesseract_binary_missing(monkeypatch):
    # pytesseract/Pillow sind installiert, aber die tesseract-Programmdatei
    # selbst fehlt (z.B. lokal unter Windows ohne Installer) - pytesseract
    # meldet das über TesseractNotFoundError bei jedem Aufruf, der das
    # externe Programm tatsächlich braucht.
    from PIL import Image as PILImage

    class FakeTesseractNotFoundError(Exception):
        pass

    class FakePytesseract:
        TesseractNotFoundError = FakeTesseractNotFoundError

        @staticmethod
        def image_to_osd(*a, **k):
            # Wird von render_upright_image() abgefangen (rotate=0) - die
            # Ausrichtungserkennung darf den ganzen Versuch nicht abbrechen.
            raise FakeTesseractNotFoundError("tesseract is not installed")

        @staticmethod
        def image_to_data(*a, **k):
            raise FakeTesseractNotFoundError("tesseract is not installed")

    class FakePage:
        def get_pixmap(self, dpi):
            class Pix:
                width = height = 10
                samples = b"\x00" * (10 * 10 * 3)

            return Pix()

    monkeypatch.setattr(ocr, "pytesseract", FakePytesseract)
    monkeypatch.setattr(ocr, "Image", PILImage)
    with pytest.raises(ocr.OcrUnavailableError, match="Texterkennung"):
        ocr.ocr_page(FakePage())


def _draw_scanned_invoice_pdf():
    """Baut eine einseitige PDF ohne Textebene: eine Rasterbild-Seite mit
    einer per PIL gezeichneten Mini-Rechnungstabelle im INTERSPORT-Layout
    (eine Kopfzeile, eine Position). Simuliert eine per Scanner eingelesene
    Papierrechnung - der einzige Unterschied zu einem echten Scan ist die
    fehlende Papier-/Scanner-Unschärfe, was den Test robust gegen
    Tesseract-Versionsunterschiede macht, ohne die OCR-Fallback-Pfade zu
    verfälschen (die Seite hat wie ein echter Scan keine Textebene)."""
    from PIL import Image, ImageDraw, ImageFont

    font_path = next(
        (
            p
            for p in [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "C:/Windows/Fonts/consola.ttf",
                "/System/Library/Fonts/Menlo.ttc",
            ]
            if Path(p).exists()
        ),
        None,
    )
    if font_path is None:
        pytest.skip("Keine passende Monospace-Schriftart für den Test gefunden")
    font = ImageFont.truetype(font_path, 26)

    column_order = [
        "Marke",
        "FEDAS",
        "Lief.",
        "Art.1",
        "Art.2",
        "EAN",
        "Bezeichnung",
        "Menge",
        "Einheit",
        "UVP",
        "Preis",
    ]
    header_text = {
        label: ("Art." if label.startswith("Art.") else label) for label in column_order
    }
    row = {
        "Marke": "Nike",
        "Lief.": "12345",
        "Art.2": "9988770010",
        "EAN": "4006632041234",
        "Bezeichnung": "Laufschuh Air Zoom",
        "Menge": "24",
        "Einheit": "Stk",
        "UVP": "129,99",
    }

    # Spalten-x-Positionen aus den tatsächlichen (gemessenen) Textbreiten
    # ableiten statt zu raten, damit keine Spalte in die nächste hineinläuft -
    # unabhängig von Schriftgrösse/-metriken der jeweils verfügbaren Schriftart.
    scratch = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    margin = 90
    columns = {}
    x = 60
    for label in column_order:
        columns[label] = x
        widest = max(
            scratch.textlength(header_text[label], font=font),
            scratch.textlength(row.get(label, ""), font=font),
        )
        x += widest + margin
    width, height = int(x) + 100, 900

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    draw.text((60, 40), "Rechnung Nr. 555000", font=font, fill="black")

    header_y = 180
    for label, x in columns.items():
        draw.text((x, header_y), header_text[label], font=font, fill="black")

    data_y = 300
    for label, text in row.items():
        draw.text((columns[label], data_y), text, font=font, fill="black")

    doc = pymupdf.open()
    scale = 72 / ocr.OCR_DPI
    page = doc.new_page(width=width * scale, height=height * scale)
    import io

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    page.insert_image(page.rect, stream=buf.getvalue())
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.skipif(
    not TESSERACT_AVAILABLE,
    reason="Tesseract OCR ist auf diesem Rechner nicht installiert",
)
def test_ocr_fallback_end_to_end():
    pdf_bytes = _draw_scanned_invoice_pdf()
    result = parse_invoice(pdf_bytes)

    assert result["ocr_used"] is True
    assert result["ocr_pages"] == [1]
    assert result["invoice_number"] == "555000"
    assert result["item_count"] == 1
    item = result["items"][0]
    assert item["ocr_used"] is True
    assert item["brand"] == "Nike"
    assert item["supplier_article_no"] == "12345"
    assert item["article_no"] == "9988770010"
    assert item["ean"] == "4006632041234"
    assert item["description"] == "Laufschuh Air Zoom"
    assert item["quantity"] == "24"
    assert item["unit"] == "Stk"
    assert item["uvp"] == "129.99"
    assert item["warnings"] == []


def test_native_text_page_does_not_use_ocr(monkeypatch):
    # Gegenprobe: eine ganz normale, digital erzeugte PDF-Seite mit Textebene
    # darf niemals den (viel langsameren, ungenaueren) OCR-Pfad auslösen -
    # unabhängig davon, ob auf diesem Rechner überhaupt Tesseract installiert
    # ist. Kein gültiges INTERSPORT-Layout, das ist hier unerheblich: es geht
    # nur darum, dass page_content() den vorhandenen Textlayer nutzt statt OCR.
    def fail_if_called(page, dpi=ocr.OCR_DPI):
        raise AssertionError("OCR wurde für eine Seite mit Textebene aufgerufen")

    monkeypatch.setattr(ocr, "ocr_page", fail_if_called)

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((40, 40), "Hallo Welt")
    pdf_bytes = doc.tobytes()
    doc.close()

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as check:
        assert check[0].get_text("words")  # Textebene vorhanden.

    with pytest.raises(InvoiceParseError, match="Tabellenkopf"):
        parse_invoice(pdf_bytes)
