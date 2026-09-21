"""Gemeinsame Bausteine aller Lieferanten-Parser (Phase B).

Jedes Layout liegt als eigenes Modul in diesem Paket (siehe CLAUDE.md,
„Technik & Konventionen") und wird in `__init__.py` registriert. Hier stehen
nur die Teile, die alle Layouts brauchen:

* `read_document()` liest eine PDF **einmal** komplett ein - Wörter samt
  Koordinaten je Seite, bei Seiten ohne Textebene per OCR (`app/services/
  ocr.py`, Regel 1: alles lokal). Erkennung, Positionen und Datumsfelder
  arbeiten danach alle auf demselben `Document`, ohne die Datei erneut zu
  öffnen oder ein zweites Mal durch die Texterkennung zu schicken.
* `lines()`/`joined()`/`decimal_value()` - die wiederkehrenden Muster aus
  projekt-kontext.md Abschnitt 6 (Tabelle mit Kopfzeile, Wortkoordinaten zu
  Zeilen gruppieren, Zahlen in Schweizer Schreibweise).

Kein Parser schreibt in die Datenbank und keiner trifft bei Unklarheiten
stille Annahmen - unsichere Zeilen bekommen eine Warnung, die den Import
sperrt, bis sie geprüft wurde.
"""

from dataclasses import dataclass
from decimal import Decimal
import re

import pymupdf

from .. import ocr
from ...core.i18n import DEFAULT_LANGUAGE, translate


class DocumentParseError(ValueError):
    """Das Dokument lässt sich nicht (sicher) lesen - Upload abweisen."""


@dataclass(frozen=True)
class Page:
    """Eine eingelesene Seite. `words` hat genau das Format von PyMuPDFs
    `page.get_text("words")` - auch dann, wenn die Wörter per OCR entstanden
    sind (siehe app/services/ocr.py), damit die Layout-Erkennung nicht
    wissen muss, woher sie kommen."""

    number: int  # 1-basiert, wie in Meldungen an die Benutzer
    words: list
    text: str
    height: float
    ocr_used: bool


@dataclass(frozen=True)
class Document:
    """Eine komplett eingelesene PDF. Wird von der Erkennung und vom
    zuständigen Parser gemeinsam genutzt (einmal lesen, einmal OCR)."""

    pages: list[Page]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    @property
    def ocr_used(self) -> bool:
        return any(page.ocr_used for page in self.pages)

    @property
    def ocr_pages(self) -> list[int]:
        return [page.number for page in self.pages if page.ocr_used]


def decimal_value(text):
    value = re.sub(r"[\s'’]", "", text).replace(",", ".")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        raise ValueError(f"Ungültige Zahl: {text!r}")
    return format(Decimal(value), "f")


def lines(words):
    """Wörter (Koordinaten) zu Zeilen gruppieren: alles, was höchstens 2
    Punkte voneinander abweicht, gehört zur selben Zeile."""
    result = []
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        if not result or abs(result[-1][0][1] - word[1]) > 2:
            result.append([])
        result[-1].append(word)
    return [sorted(row, key=lambda w: w[0]) for row in result]


def joined(words):
    return " ".join(w[4] for w in words).strip()


def collapsed(word):
    """Lower-case a word, drop a trailing period and collapse consecutive
    duplicate letters - normalises the OCR spelling jitter seen on a short,
    recurring printed note ("MwSt." also read back as "Mwst." or "MwsSt.",
    a doubled letter) so it can be matched against a known, exact phrase."""
    word = word.lower().rstrip(".")
    result = []
    for ch in word:
        if not result or result[-1] != ch:
            result.append(ch)
    return "".join(result)


def read_page(page, number: int, language: str = DEFAULT_LANGUAGE) -> Page:
    """Eine Seite einlesen - mit OCR-Rückfall, wenn sie keine Textebene hat
    (eingescannte Papierrechnung, siehe docs/architektur.md)."""
    words = page.get_text("words")
    if words:
        return Page(
            number=number,
            words=words,
            text=page.get_text(),
            height=page.rect.height,
            ocr_used=False,
        )
    try:
        result = ocr.ocr_page(page, language=language)
    except ocr.OcrUnavailableError as exc:
        raise DocumentParseError(str(exc)) from exc
    return Page(
        number=number,
        words=result["words"],
        text=result["text"],
        height=result["height"],
        ocr_used=True,
    )


def read_document(pdf_data: bytes, language: str = DEFAULT_LANGUAGE) -> Document:
    """PDF einmal komplett einlesen (inkl. OCR-Rückfall je Seite) und wieder
    schliessen. Danach braucht kein Parser die Datei mehr."""
    try:
        document = pymupdf.open(stream=pdf_data, filetype="pdf")
    except Exception as exc:
        raise DocumentParseError(
            translate("errors.parser.unreadable_pdf", language)
        ) from exc
    with document:
        if document.needs_pass:
            raise DocumentParseError(
                translate("errors.parser.password_protected", language)
            )
        if not 1 <= len(document) <= 200:
            raise DocumentParseError(translate("errors.parser.page_count_limit", language))
        pages = [
            read_page(page, index + 1, language)
            for index, page in enumerate(document)
        ]
    return Document(pages=pages)
