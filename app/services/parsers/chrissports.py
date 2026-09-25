"""CHRIS-SPORTS-Layout (Auftragsbestätigungen von CHRIS sports AG, Phase E).

Die Tabelle („Pos. Artikel Nr. Beschreibung EAN-Code Einheit Menge Preis
Rabatt Betrag Liefertermin") hat je Artikel eine Kopfzeile und darunter je
Farbe/Grösse eine Zeile:

    1  3605000007  Giro Cycling - Seasonal Merino Sock
                   black/lime breakdown,S  768686495908  Paar  9  13.00  70%  35.10  22.04.2026

D12: „Preis" ist bei Chris Sports der **UVP**; der Einkaufspreis ist der
Betrag geteilt durch die Menge (bei 70 % Rabatt also 30 % des UVP). Die
Beschreibung beginnt mit Marke und Sparte („Giro Cycling - ..."); die Sparte
fällt weg, damit die Marke zur Kasse passt. Unter der Tabelle steht „Total
Menge" - stimmt die Summe der Zeilen nicht, bekommt das Dokument eine Warnung.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .base import (
    Document,
    DocumentParseError,
    TYP_WORTE,
    decimal_value,
    ergebnis,
    gleiche_summe,
    joined,
    lines,
    pruefe_position,
)
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "chrissports"
LIEFERANT_NAME = "CHRIS sports AG"

ARTIKEL = re.compile(r"^\d+ (\d{10}) (.+)$")
VARIANTE = re.compile(
    r"^(?P<variante>.+?) (?:(?P<ean>\d{8,14}) )?(?P<einheit>\S+) (?P<menge>\d+) "
    r"(?P<preis>[\d’'.]+) (?P<rabatt>\d+(?:\.\d+)?)% (?P<betrag>[\d’'.]+) \d{2}\.\d{2}\.\d{4}$"
)
NUMMER = re.compile(r"\b(CS-\d+)\b")
TOTAL = re.compile(r"Total Menge (\d+)")
# Fusszeile und Seitenübertrag gehören nicht zur Tabelle.
KEINE_POSITION = re.compile(r"^(CHRIS sports AG \||Telefon \+|CHE-\d|Übertrag )")
# Sparten hinter der Marke („Giro Cycling", „Giro Snow").
SPARTEN = {"Cycling", "Snow", "Bike", "Outdoor", "Running", "Ski"}


def detect(document: Document) -> int | None:
    text = document.text
    if "CHRIS sports AG" not in text or "EAN-Code" not in text:
        return None
    return 4


def _marke_und_bezeichnung(text: str) -> tuple[str, str]:
    if " - " not in text:
        return "", text
    links, rechts = text.split(" - ", 1)
    worte = links.split()
    while len(worte) > 1 and worte[-1] in SPARTEN:
        worte.pop()
    return " ".join(worte), rechts.strip()


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    items, warnings = [], []
    nummer = NUMMER.search(document.text)
    typ = next((code for wort, code in TYP_WORTE.items() if wort in document.text), None)
    total = None
    artikel = None
    for page in document.pages:
        in_tabelle = False
        for zeile in lines(page.words):
            text = joined(zeile).replace("’", "'")
            if "EAN-Code" in text:
                in_tabelle = True
                continue
            if not in_tabelle:
                continue
            if KEINE_POSITION.match(text):
                continue
            summe = TOTAL.match(text)
            if summe:
                total = summe[1]
                break
            kopf = ARTIKEL.match(text)
            if kopf:
                marke, bezeichnung = _marke_und_bezeichnung(kopf[2])
                artikel = dict(supplier_article_no=kopf[1], brand=marke, description=bezeichnung)
                continue
            position = VARIANTE.match(text)
            if position and artikel:
                farbe, _, groesse = position["variante"].rpartition(",")
                item = dict(
                    **artikel,
                    color=farbe.strip() or None,
                    size=groesse.strip() or None,
                    ean=position["ean"] or "",
                    unit=position["einheit"],
                    quantity=position["menge"],
                    uvp=position["preis"],
                    page=page.number,
                    raw_lines=[text],
                )
                try:
                    menge = Decimal(position["menge"])
                    item["ek"] = str((Decimal(decimal_value(position["betrag"])) / menge).quantize(Decimal("0.01")))
                except (ValueError, InvalidOperation, ZeroDivisionError):
                    item["ek"] = None
                items.append(pruefe_position(item, language))
            elif text:
                warnings.append(
                    translate("errors.parser.unassigned_row", language, page=page.number, row_text=text)
                )
    warnings += gleiche_summe(total, items, language)
    return ergebnis(document, items, warnings, typ, nummer[1] if nummer else None, language)


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    """Auftragsdatum (Wert steht im Kopf direkt vor dem Titel „Auftragsdatum")."""
    treffer = re.search(r"(\d{2}\.\d{2}\.\d{4})\s+Auftragsdatum", document.text)
    if not treffer:
        raise DocumentParseError(translate("errors.importer.invoice_date_missing_or_ambiguous", language))
    tag = datetime.strptime(treffer[1], "%d.%m.%Y").date()
    return {"invoice_date": tag, "document_date": tag}
