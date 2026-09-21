"""INTERSPORT-Layout (Rechnungen von INTERSPORT Schweiz AG, inkl.
ECOM-Retouren - gleiches Layout, siehe projekt-kontext.md Abschnitt 6,
Punkt 7).

Erstes Modul der Parser-Registry (`app/services/parsers/__init__.py`) und
damit die Vorlage für weitere Lieferanten-Layouts in Phase E. Die
Schnittstelle, die jedes Layout-Modul erfüllt:

| Name              | Bedeutung                                              |
|-------------------|--------------------------------------------------------|
| `KEY`             | Wert von `lieferanten.parser_key` (Lieferanten-Zuordnung) |
| `LIEFERANT_NAME`  | Name des Lieferanten in den Seed-Daten (nur Anzeige)   |
| `detect(doc)`     | Punktzahl, wenn das Layout passt, sonst `None`          |
| `parse(doc, lang)`| Positionen als Vorschau-Daten (schreibt nichts)         |
| `dates(doc, lang)`| Dokument-/Belegdatum für den Import                     |

Der Parser selbst trifft bei Unklarheiten keine Annahmen: jede unsichere
Zeile bekommt eine Warnung, die den Import sperrt, bis sie geprüft oder
korrigiert wurde.
"""

from collections import Counter
from decimal import InvalidOperation
from datetime import datetime
import re

from .base import (
    Document,
    DocumentParseError,
    collapsed,
    decimal_value,
    joined,
    lines,
)
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "intersport"
LIEFERANT_NAME = "INTERSPORT Schweiz AG"

# Spaltentitel der Positionstabelle. Diese Kombination ist die eigentliche
# Layout-Signatur: sie entscheidet, ob dieses Modul zuständig ist (detect)
# und wo die Spalten liegen (parse).
HEADER_WORDS = frozenset(
    {"Marke", "FEDAS", "EAN", "Bezeichnung", "Menge", "Einheit", "UVP", "Preis"}
)

# Feste deutsche Textanker im Layout (unabhängig von der UI-Sprache, Regel 7):
# die Rechnungsnummer und die beiden Datumsfelder.
INVOICE_NUMBER_PATTERN = re.compile(r"Rechnung\s+Nr\.\s*(\d+)")

# A short "Preise inkl. MwSt."-style disclaimer note prints right above the
# item table on this INTERSPORT paper-invoice layout (a "Lieferschein"
# enclosed in the package rather than the standard emailed PDF, which does
# not appear to carry it - see docs/architektur.md). It sits inside the
# table's row range but is not an item, so it would otherwise show up as an
# "unassigned line" warning on every single page of every invoice of this
# type - not a real problem, but with the all-or-nothing warning policy it
# would permanently block importing this whole class of invoice. Recognised
# exactly (not as a loose keyword match) so it never masks a genuine
# unrecognised line elsewhere in the table.
_IGNORABLE_ROWS = {"mwst", "inkl mwst"}


def _header_rows(rows):
    """Alle Zeilen, die die komplette Tabellen-Kopfzeile enthalten."""
    return [r for r in rows if HEADER_WORDS <= {w[4] for w in r}]


def detect(document: Document) -> int | None:
    """Punktzahl (höher = sicherer), wenn dieses Layout passt, sonst `None`.

    Pflichtmerkmal ist die Positionstabelle mit ihrer Kopfzeile - auf einer
    eingescannten Rechnung ist der Firmenname (Logo) nicht immer als Text
    lesbar, die Tabelle aber schon. Der Firmenname zählt darum nur als
    zusätzliche Bestätigung, damit ein fremdes Layout mit zufällig ähnlicher
    Kopfzeile nicht gleich gewinnt.
    """
    if not any(_header_rows(lines(page.words)) for page in document.pages):
        return None
    score = 2
    text = document.text.upper()
    if "INTERSPORT" in text:
        score += 1
    if INVOICE_NUMBER_PATTERN.search(document.text):
        score += 1
    return score


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    """Alle Positionen als Vorschau-Daten: Bezeichner als Text, Beträge als
    exakte Dezimal-Zeichenketten. Keine Datenbankzugriffe, keine stille
    Entdoppelung. Unsichere Zeilen bleiben mit Warnung in der Vorschau.
    """
    items, warnings, counts = [], [], []
    invoice_number = None
    for page in document.pages:
        match = INVOICE_NUMBER_PATTERN.search(page.text)
        if match:
            if invoice_number and invoice_number != match[1]:
                raise DocumentParseError(
                    translate("errors.parser.mixed_invoice_numbers", language)
                )
            invoice_number = match[1]
        rows = lines(page.words)
        headers = _header_rows(rows)
        if len(headers) != 1:
            # Das Layout passt grundsätzlich (sonst hätte die Erkennung in
            # __init__.py dieses Modul nicht gewählt), aber diese Seite
            # weicht ab - z. B. ein Scan mit unlesbarer Kopfzeile.
            hint = translate(
                "errors.parser.hint_ocr" if page.ocr_used else "errors.parser.hint_other_layout",
                language,
            )
            raise DocumentParseError(
                translate(
                    "errors.parser.missing_table_header",
                    language,
                    page=page.number,
                    hint=hint,
                )
            )
        header = headers[0]
        h = {w[4]: w for w in header}
        # Left-aligned text columns; numeric columns are bounded by the
        # preceding header's right edge to accommodate right alignment.
        lief = next((w[0] for w in header if w[4] == "Lief."), None)
        arts = [w[0] for w in header if w[4] == "Art."]
        if lief is None or len(arts) != 2:
            raise DocumentParseError(
                translate("errors.parser.article_columns_not_detected", language)
            )
        # Marke has no column to its left, so its start gets extra left
        # margin (unlike the others, widening it can't bleed into a
        # neighbouring column): a leading quote character in the brand
        # name (e.g. a quoted "Giro") gets its own, wider OCR bounding
        # box than the letter after it, which can otherwise push the
        # word's left edge past a tight 3pt margin and drop it entirely.
        bounds = [
            h["Marke"][0] - 15,
            h["FEDAS"][0] - 3,
            lief - 3,
            arts[-1] - 3,
            h["EAN"][0] - 3,
            h["Bezeichnung"][0] - 3,
            h["Menge"][0] - 3,
            h["Menge"][2] + 3,
            h["Einheit"][2] + 3,
            h["UVP"][2] + 3,
        ]
        top = max(w[3] for w in header)
        stop = min(
            [
                w[1]
                for w in page.words
                if w[1] > top
                and (
                    w[4] in {"Rechnungsrabatt", "INTERSPORT", "MWST", "MWST-Betrag"}
                    or w[4] == "Total"
                )
            ]
            or [page.height - 50]
        )
        body = [
            r for r in rows if top < r[0][1] < stop and max(w[3] - w[1] for w in r) > 3
        ]
        current = None
        page_items = []
        for row in body:
            cells = [
                joined([w for w in row if bounds[i] <= w[0] < bounds[i + 1]])
                for i in range(9)
            ]
            # Detect even malformed/missing EANs through independent ID columns.
            anchor = bool(cells[3] or cells[4] or (cells[1] and cells[2]))
            if anchor:
                current = dict(
                    brand=cells[0],
                    fedas_code=cells[1],
                    supplier_article_no=cells[2],
                    article_no=cells[3],
                    ean=cells[4],
                    description=cells[5],
                    quantity=cells[6],
                    unit=cells[7],
                    uvp=cells[8],
                    page=page.number,
                    source_y=round(row[0][1], 2),
                    description_lines=[cells[5]],
                    raw_lines=[joined(row)],
                    warnings=[],
                )
                page_items.append(current)
            elif current:
                current["raw_lines"].append(joined(row))
                if cells[0]:
                    current["brand"] += " " + cells[0]
                # Continuation text may extend into otherwise empty numeric columns.
                continuation = joined([w for w in row if bounds[5] <= w[0]])
                if continuation:
                    current["description_lines"].append(continuation)
            else:
                row_text = joined(row)
                if " ".join(collapsed(w[4]) for w in row) not in _IGNORABLE_ROWS:
                    warnings.append(
                        translate(
                            "errors.parser.unassigned_row",
                            language,
                            page=page.number,
                            row_text=row_text,
                        )
                    )
        for item in page_items:
            item["ocr_used"] = page.ocr_used
            desc = item["description_lines"]
            variant_index = next(
                (i for i, s in enumerate(desc) if i > 0 and "(" in s), None
            )
            item.update(color=None, size=None, variant_raw=None)
            if variant_index is not None:
                variant = " ".join(desc[variant_index:])
                item["variant_raw"] = variant
                m = re.fullmatch(r"(.*?)\((.*)\)\s*/\s*(.+)", variant)
                if m:
                    item["color"] = m[2].strip()
                    item["size"] = m[3].strip()
                    item["color_label"] = m[1].strip() or None
                else:
                    item["warnings"].append(
                        translate("errors.parser.color_size_ambiguous", language)
                    )
                desc = desc[:variant_index]
            item["description"] = re.sub(r"-\s+", "-", " ".join(desc))
            for key in (
                "brand",
                "supplier_article_no",
                "article_no",
                "ean",
                "description",
                "quantity",
                "unit",
                "uvp",
            ):
                if not item[key]:
                    item["warnings"].append(
                        translate(
                            "errors.parser.required_field_missing",
                            language,
                            field=translate(f"fields.{key}", language),
                        )
                    )
            if not re.fullmatch(r"\d{8}|\d{12,14}", item["ean"]):
                item["warnings"].append(
                    translate("errors.parser.ean_unexpected_format", language)
                )
            for key in ("quantity", "uvp"):
                try:
                    item[key] = decimal_value(item[key])
                except (ValueError, InvalidOperation):
                    item["warnings"].append(
                        translate(
                            "errors.parser.invalid_value",
                            language,
                            field=translate(f"fields.{key}", language),
                            value=item[key],
                        )
                    )
                    item[key] = None
            item["row_number"] = len(items) + 1
            items.append(item)
        counts.append(len(page_items))
        if not page_items:
            warnings.append(
                translate(
                    "errors.parser.no_positions_on_page", language, page=page.number
                )
            )
    if not items:
        raise DocumentParseError(
            translate("errors.parser.no_positions_detected", language)
        )
    duplicates = {
        ean: count
        for ean, count in Counter(i["ean"] for i in items if i["ean"]).items()
        if count > 1
    }
    return dict(
        # Dieses Layout kommt bisher nur als Rechnung vor (die Belegnummer
        # steht als „Rechnung Nr." im Dokument). Ohne diesen Anker bleibt der
        # Typ offen - der Import weist das Dokument dann ohnehin ab, weil die
        # Belegnummer fehlt.
        document_type="rechnung" if invoice_number else None,
        invoice_number=invoice_number,
        pages=document.page_count,
        item_count=len(items),
        page_item_counts=counts,
        items=items,
        duplicate_eans=duplicates,
        warnings=warnings,
        rows_with_warnings=sum(bool(i["warnings"]) for i in items),
        preview_only=True,
        ocr_used=document.ocr_used,
        ocr_pages=document.ocr_pages,
    )


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    """Rechnungs- und Belegdatum aus dem Kopfbereich.

    „Rechnungsdatum"/„Belegdatum" sind feste Textanker im INTERSPORT-Layout
    (immer Deutsch, unabhängig von der UI-Sprache) - nur die Fehlermeldung bei
    fehlendem/mehrdeutigem Datum wird übersetzt. Alle Seiten werden
    durchsucht, nicht nur die erste: bei einem Scan stehen die Seiten nicht
    immer in der Reihenfolge des digitalen Exports (der Kopfblock mit diesen
    Daten kann auf einer späteren Seite landen).
    """
    result = {}
    for label, key in [
        ("Rechnungsdatum", "invoice_date"),
        ("Belegdatum", "document_date"),
    ]:
        anchors = [
            (page.words, w) for page in document.pages for w in page.words if w[4] == label
        ]
        if len(anchors) != 1:
            raise DocumentParseError(
                translate(f"errors.importer.{key}_not_unique", language)
            )
        words, anchor = anchors[0]
        candidates = [
            w[4]
            for w in words
            if w[0] > anchor[2]
            and abs(w[1] - anchor[1]) < 2
            and re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", w[4])
        ]
        if len(candidates) != 1:
            raise DocumentParseError(
                translate(f"errors.importer.{key}_missing_or_ambiguous", language)
            )
        try:
            result[key] = datetime.strptime(candidates[0], "%d.%m.%Y").date()
        except ValueError as exc:
            raise DocumentParseError(
                translate(f"errors.importer.{key}_invalid", language)
            ) from exc
    return result
