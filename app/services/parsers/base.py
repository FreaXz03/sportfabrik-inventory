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
from ...core.i18n import DEFAULT_LANGUAGE, template, translate


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
    # Die Original-PDF, nur für Layouts, die eine unbrauchbare Textebene selbst
    # per OCR neu lesen (cmp_bestellung). Alle anderen Parser ignorieren sie.
    pdf_data: bytes | None = None

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


def _text_laeuft_aufwaerts(page) -> bool:
    """Läuft fast aller Text von unten nach oben (Richtung (0, -1)) auf einer
    ungedrehten Seite? Einzelne senkrechte Randtexte zählen nicht."""
    if page.rotation:
        return False
    aufwaerts = waagrecht = 0
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            dx, dy = line["dir"]
            if round(dx) == 0 and round(dy) == -1:
                aufwaerts += 1
            else:
                waagrecht += 1
    return aufwaerts >= 4 * waagrecht and aufwaerts > 0


def read_page(page, number: int, language: str = DEFAULT_LANGUAGE) -> Page:
    """Eine Seite einlesen - mit OCR-Rückfall, wenn sie keine Textebene hat
    (eingescannte Papierrechnung, siehe docs/architektur.md)."""
    words = page.get_text("words")
    if words:
        height = page.rect.height
        if not _text_laeuft_aufwaerts(page):
            text = page.get_text()
        else:
            # Querformat-Seite gedreht auf ein Hochformat-Blatt gelegt (die
            # Seitendrehung bleibt 0, nur der Text läuft von unten nach oben).
            # Wörter zurückdrehen, damit Zeilen und Spalten wie gewohnt liegen;
            # den Text daraus neu zusammensetzen (get_text() liefert ihn hier
            # in falscher Reihenfolge).
            words = [
                (height - y1, x0, height - y0, x1, *rest)
                for x0, y0, x1, y1, *rest in words
            ]
            height = page.rect.width
            text = "\n".join(joined(row) for row in lines(words))
        return Page(
            number=number,
            words=words,
            text=text,
            height=height,
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
    return Document(pages=pages, pdf_data=pdf_data)


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
        # Die Vorschau zeigt je Position den Originaltext; jeder Parser liefert ihn, hier die Absicherung.
        item.setdefault("raw_lines", [])
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


# --- Gegenrechnung für Layouts mit Rasterlesung (cmp_bestellung) -----------------
#
# Jede Position trägt `check`: `{"key", "gesamt", "betrag", "nr_unsicher"}` der
# Farbzeile, aus der sie stammt. Die Warnungen werden **immer aus den aktuellen
# Werten neu gebildet** - nach dem Lesen und nach jeder Korrektur in der Vorschau
# (`app/services/corrections.py`). So verschwindet eine Warnung, sobald die Zahlen
# aufgehen (Menge korrigiert oder fehlende Grösse ergänzt), und eine unsicher
# gelesene Artikelnummer bleibt, bis sie geändert wird.

GEGENRECHNUNG_KEYS = (
    "errors.parser.total_mismatch",
    "errors.parser.amount_mismatch",
    "errors.parser.code_unsure",
)


def _praefixe(language: str) -> tuple:
    return tuple(template(key, language).split("{", 1)[0] for key in GEGENRECHNUNG_KEYS)


def _dez(wert):
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(wert))
    except (InvalidOperation, ValueError):
        return None


def _betrag_text(wert) -> str:
    return format(wert, ".2f")


def gegenrechnung_zeilen(items: list, language: str = DEFAULT_LANGUAGE) -> None:
    """Warnungen der Farbzeilen (Menge ↔ Gesamtmenge, Menge × EK ↔ Betrag,
    unsichere Artikelnummer) aus den aktuellen Werten neu setzen."""
    praefixe = _praefixe(language)
    gruppen: dict = {}
    for item in items:
        if item.get("check"):
            item["warnings"] = [w for w in item["warnings"] if not w.startswith(praefixe)]
            gruppen.setdefault(item["check"]["key"], []).append(item)
    for gruppe in gruppen.values():
        check = gruppe[0]["check"]
        mengen = [_dez(i.get("quantity")) for i in gruppe]
        eks = [_dez(i.get("ek")) for i in gruppe]
        neu = []
        if None not in mengen:
            ist = sum(mengen)
            if check.get("gesamt") is not None and ist != check["gesamt"]:
                neu.append(translate("errors.parser.total_mismatch", language, summe=format(ist.normalize(), "f"), beleg=check["gesamt"]))
            if None not in eks:
                betrag = sum(m * e for m, e in zip(mengen, eks))
                soll = _dez(check["betrag"]) if check.get("betrag") is not None else None
                if soll is None or betrag != soll:
                    neu.append(
                        translate("errors.parser.amount_mismatch", language, summe=_betrag_text(betrag), beleg=_betrag_text(soll) if soll is not None else "-")
                    )
        for item in gruppe:
            warnungen = list(neu)
            if check.get("nr_unsicher") and item.get("article_no") == check["nr_unsicher"]:
                warnungen.append(translate("errors.parser.code_unsure", language, nr=check["nr_unsicher"]))
            item["warnings"].extend(warnungen)


def gegenrechnung_dokument(items: list, totals: dict | None, language: str = DEFAULT_LANGUAGE) -> list[str]:
    """Warnungen der Belegsumme („Menge: 159 Produkte, 3 505,30 CHF") gegen die Positionen.
    `totals` = `{"stueck": int, "betrag": "3505.30"}` oder `None`, wenn die Summe nicht lesbar war."""
    gezaehlt = [i for i in items if i.get("check")]
    mengen = [_dez(i.get("quantity")) for i in gezaehlt]
    if None in mengen:
        return []
    stueck = sum(mengen)
    if totals is None:
        return [translate("errors.parser.total_mismatch", language, summe=format(stueck.normalize(), "f"), beleg="-")]
    warnungen = []
    if stueck != totals["stueck"]:
        warnungen.append(translate("errors.parser.total_mismatch", language, summe=format(stueck.normalize(), "f"), beleg=totals["stueck"]))
    eks = [_dez(i.get("ek")) for i in gezaehlt]
    if None not in eks:
        betrag = sum(m * e for m, e in zip(mengen, eks))
        if betrag != _dez(totals["betrag"]):
            warnungen.append(translate("errors.parser.amount_mismatch", language, summe=_betrag_text(betrag), beleg=_betrag_text(_dez(totals["betrag"]))))
    return warnungen


def ohne_gegenrechnung(warnungen: list, language: str = DEFAULT_LANGUAGE) -> list:
    """Belegwarnungen ohne die der Gegenrechnung (werden neu gebildet)."""
    praefixe = _praefixe(language)
    return [w for w in warnungen if not w.startswith(praefixe)]
