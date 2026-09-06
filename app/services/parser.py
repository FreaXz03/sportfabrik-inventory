"""Preview-only parser for the text-based INTERSPORT invoice table."""
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
import argparse
import json
import re

import pymupdf

from . import ocr


class InvoiceParseError(ValueError):
    pass


def decimal_value(text):
    value = re.sub(r"[\s'’]", "", text).replace(",", ".")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        raise ValueError(f"Ungültige Zahl: {text!r}")
    return format(Decimal(value), "f")


def lines(words):
    result = []
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        if not result or abs(result[-1][0][1] - word[1]) > 2:
            result.append([])
        result[-1].append(word)
    return [sorted(row, key=lambda w: w[0]) for row in result]


def joined(words):
    return " ".join(w[4] for w in words).strip()


def page_content(page):
    """Return (words, text, height, ocr_used) for a page.

    Falls back to OCR when a page has no extractable text at all - a paper
    invoice that was scanned instead of received digitally. OCR-derived
    words are shaped exactly like PyMuPDF's own word tuples (see ocr.py) so
    everything below this function is unaware of where the words came from.
    """
    words = page.get_text("words")
    if words:
        return words, page.get_text(), page.rect.height, False
    try:
        result = ocr.ocr_page(page)
    except ocr.OcrUnavailableError as exc:
        raise InvoiceParseError(str(exc)) from exc
    return result['words'], result['text'], result['height'], True


def parse_invoice(pdf_data: bytes) -> dict:
    """Return all occurrences, identifiers as text and exact decimals as strings.

    No database imports, file writes or silent deduplication. Uncertain rows
    remain in the preview with warnings. Unknown layouts fail explicitly.
    Pages without a text layer (scanned paper invoices) are read via OCR
    (see ocr.py); such pages are listed in the returned ocr_pages field so
    callers can prompt for extra-careful review - OCR is not 100% reliable.
    """
    try:
        document = pymupdf.open(stream=pdf_data, filetype="pdf")
    except Exception as exc:
        raise InvoiceParseError("Die Datei ist keine lesbare PDF-Datei.") from exc
    with document:
        if document.needs_pass:
            raise InvoiceParseError("Passwortgeschützte PDFs werden nicht unterstützt.")
        if not 1 <= len(document) <= 200:
            raise InvoiceParseError("Erlaubt sind 1 bis 200 Seiten.")
        items, warnings, counts, ocr_pages = [], [], [], []
        invoice_number = None
        for page_index, page in enumerate(document):
            words, text, page_height, page_ocr_used = page_content(page)
            if page_ocr_used:
                ocr_pages.append(page_index + 1)
            match = re.search(r"Rechnung\s+Nr\.\s*(\d+)", text)
            if match:
                if invoice_number and invoice_number != match[1]:
                    raise InvoiceParseError("Das PDF enthält unterschiedliche Rechnungsnummern.")
                invoice_number = match[1]
            rows = lines(words)
            headers = [r for r in rows if {"Marke", "FEDAS", "EAN", "Bezeichnung", "Menge", "Einheit", "UVP", "Preis"} <= {w[4] for w in r}]
            if len(headers) != 1:
                hint = " (Scan per OCR gelesen; bitte Bildqualität/Ausrichtung prüfen)" if page_ocr_used else " (Scan/anderes Layout)"
                raise InvoiceParseError(f"Seite {page_index + 1}: INTERSPORT-Tabellenkopf fehlt oder ist mehrdeutig{hint}.")
            header = headers[0]
            h = {w[4]: w for w in header}
            # Left-aligned text columns; numeric columns are bounded by the
            # preceding header's right edge to accommodate right alignment.
            lief = next((w[0] for w in header if w[4] == "Lief."), None)
            arts = [w[0] for w in header if w[4] == "Art."]
            if lief is None or len(arts) != 2:
                raise InvoiceParseError("Artikelspalten konnten nicht erkannt werden.")
            bounds = [h['Marke'][0]-3, h['FEDAS'][0]-3, lief-3, arts[-1]-3,
                      h['EAN'][0]-3, h['Bezeichnung'][0]-3,
                      h['Menge'][0]-3, h['Menge'][2]+3,
                      h['Einheit'][2]+3, h['UVP'][2]+3]
            top = max(w[3] for w in header)
            stop = min([w[1] for w in words if w[1] > top and
                        (w[4] in {"Rechnungsrabatt", "INTERSPORT", "MWST", "MWST-Betrag"}
                         or w[4] == "Total" )] or [page_height-50])
            body = [r for r in rows if top < r[0][1] < stop and max(w[3]-w[1] for w in r) > 3]
            current = None
            page_items = []
            for row in body:
                cells = [joined([w for w in row if bounds[i] <= w[0] < bounds[i+1]]) for i in range(9)]
                # Detect even malformed/missing EANs through independent ID columns.
                anchor = bool(cells[3] or cells[4] or (cells[1] and cells[2]))
                if anchor:
                    current = dict(brand=cells[0], supplier_article_no=cells[2], article_no=cells[3],
                                   ean=cells[4], description=cells[5], quantity=cells[6], unit=cells[7], uvp=cells[8],
                                   page=page_index+1, source_y=round(row[0][1], 2),
                                   description_lines=[cells[5]], raw_lines=[joined(row)], warnings=[])
                    page_items.append(current)
                elif current:
                    current['raw_lines'].append(joined(row))
                    if cells[0]:
                        current['brand'] += ' ' + cells[0]
                    # Continuation text may extend into otherwise empty numeric columns.
                    continuation = joined([w for w in row if bounds[5] <= w[0]])
                    if continuation:
                        current['description_lines'].append(continuation)
                else:
                    warnings.append(f"Seite {page_index+1}: nicht zugeordnete Zeile: {joined(row)}")
            for item in page_items:
                item['ocr_used'] = page_ocr_used
                desc = item['description_lines']
                variant_index = next((i for i, s in enumerate(desc) if i > 0 and '(' in s), None)
                item.update(color=None, size=None, variant_raw=None)
                if variant_index is not None:
                    variant = ' '.join(desc[variant_index:])
                    item['variant_raw'] = variant
                    m = re.fullmatch(r"(.*?)\((.*)\)\s*/\s*(.+)", variant)
                    if m:
                        item['color'] = m[2].strip()
                        item['size'] = m[3].strip()
                        item['color_label'] = m[1].strip() or None
                    else:
                        item['warnings'].append('Farbe/Grösse nicht eindeutig erkannt; Originaltext beachten.')
                    desc = desc[:variant_index]
                item['description'] = re.sub(r"-\s+", "-", ' '.join(desc))
                for key in ('brand', 'supplier_article_no', 'article_no', 'ean', 'description', 'quantity', 'unit', 'uvp'):
                    if not item[key]:
                        item['warnings'].append(f'Pflichtfeld fehlt: {key}')
                if not re.fullmatch(r"\d{8}|\d{12,14}", item['ean']):
                    item['warnings'].append('EAN hat ein unerwartetes Format.')
                for key in ('quantity', 'uvp'):
                    try:
                        item[key] = decimal_value(item[key])
                    except (ValueError, InvalidOperation):
                        item['warnings'].append(f'Ungültiger Wert für {key}: {item[key]!r}')
                        item[key] = None
                item['row_number'] = len(items)+1
                items.append(item)
            counts.append(len(page_items))
            if not page_items:
                warnings.append(f'Seite {page_index+1}: keine Positionen erkannt.')
        if not items:
            raise InvoiceParseError('Keine Rechnungspositionen erkannt.')
        duplicates = {ean: count for ean, count in Counter(i['ean'] for i in items if i['ean']).items() if count > 1}
        return dict(invoice_number=invoice_number, pages=len(document), item_count=len(items),
                    page_item_counts=counts, items=items, duplicate_eans=duplicates,
                    warnings=warnings, rows_with_warnings=sum(bool(i['warnings']) for i in items),
                    preview_only=True, ocr_used=bool(ocr_pages), ocr_pages=ocr_pages)


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description='INTERSPORT-PDF als JSON-Vorschau auslesen')
    cli.add_argument('pdf', type=Path)
    cli.add_argument('--output', type=Path)
    args = cli.parse_args()
    result = json.dumps(parse_invoice(args.pdf.read_bytes()), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result)
