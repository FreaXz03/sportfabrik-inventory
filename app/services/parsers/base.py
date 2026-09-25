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


# --- Gemeinsamer Abschluss für die Layouts ab Phase E ----------------------
#
# Das INTERSPORT-Modul prüft seine Positionen selbst (älter, eigene Sonder-
# fälle). Die übrigen Layouts liefern Rohwerte und lassen sie hier einheitlich
# prüfen, damit jede Position dieselben Regeln durchläuft.

PFLICHTFELDER = ("brand", "supplier_article_no", "description", "quantity", "unit", "uvp")
TYP_WORTE = {
    "Auftragsbestätigung": "auftragsbestaetigung",
    "Lieferschein": "lieferschein",
    "Rechnung": "rechnung",
}
DATUM = re.compile(r"\b(\d{2})[./](\d{2})[./](\d{4}|\d{2})\b")


def datum(text: str):
    """Erstes Datum im Text (TT.MM.JJJJ, TT/MM/JJJJ oder TT.MM.JJ) oder None."""
    from datetime import date

    treffer = DATUM.search(text or "")
    if not treffer:
        return None
    tag, monat, jahr = treffer.groups()
    jahr = int(jahr) + (2000 if len(jahr) == 2 else 0)
    try:
        return date(jahr, int(monat), int(tag))
    except ValueError:
        return None


def pruefe_position(item: dict, language: str = DEFAULT_LANGUAGE) -> dict:
    """Pflichtfelder, EAN (Regel 5: fehlend = Hinweis, unleserlich = Warnung)
    und Zahlen einer Position prüfen. EK ist nie Pflicht (Regel 10)."""
    item.setdefault("warnings", [])
    item.setdefault("hints", [])
    item.setdefault("ean", "")
    for key in PFLICHTFELDER:
        if not item.get(key):
            item["warnings"].append(
                translate(
                    "errors.parser.required_field_missing",
                    language,
                    field=translate(f"fields.{key}", language),
                )
            )
    if not item["ean"]:
        item["hints"].append(translate("hints.parser.ean_missing", language))
    elif not re.fullmatch(r"\d{8}|\d{12,14}", item["ean"]):
        item["warnings"].append(translate("errors.parser.ean_unexpected_format", language))
    for key in ("quantity", "uvp", "ek"):
        wert = item.get(key)
        if not wert:
            item[key] = None
            continue
        try:
            item[key] = decimal_value(wert)
        except ValueError:
            item[key] = None
            if key != "ek":
                item["warnings"].append(
                    translate(
                        "errors.parser.invalid_value",
                        language,
                        field=translate(f"fields.{key}", language),
                        value=wert,
                    )
                )
    return item


def ergebnis(
    document: Document,
    items: list,
    warnings: list,
    document_type: str | None,
    nummer: str | None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Vorschau-Ergebnis im selben Format wie das INTERSPORT-Modul."""
    if not items:
        raise DocumentParseError(translate("errors.parser.no_positions_detected", language))
    for index, item in enumerate(items, start=1):
        item["row_number"] = index
        item.setdefault("ocr_used", document.ocr_used)
    zaehler = {}
    for item in items:
        zaehler[item.get("page", 1)] = zaehler.get(item.get("page", 1), 0) + 1
    eans = {}
    for item in items:
        if item["ean"]:
            eans[item["ean"]] = eans.get(item["ean"], 0) + 1
    return dict(
        document_type=document_type,
        invoice_number=nummer,
        pages=document.page_count,
        item_count=len(items),
        page_item_counts=[zaehler.get(seite.number, 0) for seite in document.pages],
        items=items,
        duplicate_eans={ean: anzahl for ean, anzahl in eans.items() if anzahl > 1},
        warnings=warnings,
        rows_with_warnings=sum(bool(i["warnings"]) for i in items),
        rows_with_hints=sum(bool(i["hints"]) for i in items),
        preview_only=True,
        ocr_used=document.ocr_used,
        ocr_pages=document.ocr_pages,
        lieferant_typ=None,
    )


def gleiche_summe(soll, positionen, language: str = DEFAULT_LANGUAGE) -> list:
    """Warnung, wenn die Stücksumme der Positionen nicht der Summe entspricht,
    die der Beleg selbst ausweist (sonst ist eine Zeile verloren gegangen)."""
    ist = sum((Decimal(p["quantity"]) for p in positionen if p.get("quantity")), Decimal(0))
    if soll is None or Decimal(soll) == ist:
        return []
    return [translate("errors.parser.total_mismatch", language, summe=ist.normalize(), beleg=soll)]
