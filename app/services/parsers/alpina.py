"""ALPINA-Layout (Auftragsbestätigungen von ALPINA SPORTS Schweiz AG, Phase E).

Aufbau der Positionstabelle („Pos. Produkt Beschreibung Menge UVP HEK Rabatt
Einzelpreis (netto) Pos.-wert (netto)"):

    10  A9801132  TAUNUS burro-brown   4 Stück  89.90 CHF  44.95 CHF  22.50 CHF  90.00 CHF
                  matt 52-56
        Voraussichtlicher Liefertermin 09.09.2026 ...

Keine EAN (Regel 5: Hinweis, kein Hindernis). Die Beschreibung trägt Modell
(Grossbuchstaben), Farbe und am Ende die Grösse. Der UVP steht in der Spalte
UVP, der Einkaufspreis ist der Einzelpreis netto (Regel 10).

**Artikel = Modell** (Fabian, 24.09.2026: alle Grössen eines Modells zählen
zusammen, auch für die Reduktionsuhr). Alpina vergibt je Farbe und Grösse eine
eigene Nummer; die ersten fünf Zeichen sind das Modell (A9809 = ROOTAGE 2
MIPS), die sechste Stelle die Grösse, die letzten beiden die Farbe. Die
vollständige Nummer bleibt als `article_no` an der Position.
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
    joined,
    lines,
    pruefe_position,
)
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "alpina"
LIEFERANT_NAME = "ALPINA SPORTS Schweiz AG"
MARKE = "Alpina"

KOPF = {"Pos.", "Produkt", "Beschreibung", "Menge", "UVP", "HEK"}
NUMMER = re.compile(r"(Auftragsbestätigung|Lieferschein|Rechnung)[: ]+(\d{4,})")
PRODUKT = re.compile(r"A\d{7}")
GROESSE = re.compile(r"\s*(\d{2}-\d{2})$")
ZAHL = re.compile(r"-?[\d']+\.\d{2}")
MODELL_LAENGE = 5


def _kopfzeile(zeilen):
    return next((z for z in zeilen if KOPF <= {w[4] for w in z}), None)


def detect(document: Document) -> int | None:
    if not any(_kopfzeile(lines(page.words)) for page in document.pages):
        return None
    return 4 if "ALPINA SPORTS" in document.text.upper() else None


def _teile_beschreibung(text: str) -> tuple[str, str | None, str | None]:
    """„ROOTAGE 2 MIPS gun black neon 52-56" → Modell, Farbe, Grösse."""
    groesse = GROESSE.search(text)
    if groesse:
        text = text[: groesse.start()]
    worte = text.split()
    modell = []
    for wort in worte:
        if wort.isupper() or wort.isdigit():
            modell.append(wort)
        else:
            break
    farbe = " ".join(worte[len(modell):]) or None
    return " ".join(modell) or text.strip(), farbe, groesse[1] if groesse else None


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    items, warnings = [], []
    typ = nummer = None
    for page in document.pages:
        treffer = NUMMER.search(page.text)
        if treffer and nummer is None:
            typ, nummer = TYP_WORTE[treffer[1]], treffer[2]
        zeilen = lines(page.words)
        kopf = _kopfzeile(zeilen)
        if kopf is None:
            continue
        spalte = {w[4]: w[0] for w in kopf}
        oben = max(w[3] for w in kopf)
        aktuell = None
        for zeile in zeilen:
            if zeile[0][1] <= oben + 12:  # Kopf und „(netto)"
                continue
            text = joined(zeile)
            if text.startswith(("Gesamt", "Fracht", "Mehrwertsteuer", "Summe")):
                break
            produkt = next((w for w in zeile if PRODUKT.fullmatch(w[4])), None)
            if produkt is not None:
                menge_worte = [w for w in zeile if spalte["Menge"] - 5 <= w[0] < spalte["UVP"] - 25]
                zahlen = [w[4] for w in zeile if w[0] > spalte["UVP"] - 30 and ZAHL.fullmatch(w[4])]
                aktuell = dict(
                    brand=MARKE,
                    article_no=produkt[4],
                    supplier_article_no=produkt[4][:MODELL_LAENGE],
                    beschreibung=[joined([w for w in zeile if spalte["Beschreibung"] - 3 <= w[0] < spalte["Menge"] - 5])],
                    quantity=menge_worte[0][4] if menge_worte else "",
                    unit=menge_worte[1][4] if len(menge_worte) > 1 else "",
                    uvp=zahlen[0] if zahlen else "",
                    ek=zahlen[-2] if len(zahlen) >= 3 else "",
                    wert=zahlen[-1] if len(zahlen) >= 3 else "",
                    page=page.number,
                    raw_lines=[text],
                )
                items.append(aktuell)
            elif aktuell is not None and not text.startswith("Voraussichtlicher"):
                aktuell["beschreibung"].append(
                    joined([w for w in zeile if spalte["Beschreibung"] - 3 <= w[0] < spalte["Menge"] - 5])
                )
                aktuell["raw_lines"].append(text)
            elif text.startswith("Voraussichtlicher"):
                aktuell = None
    for item in items:
        description, color, size = _teile_beschreibung(" ".join(t for t in item.pop("beschreibung") if t))
        item.update(description=description, color=color, size=size)
        wert = item.pop("wert")
        pruefe_position(item, language)
        # Menge × Einzelpreis = Positionswert (Beträge nie als float).
        try:
            stimmt = Decimal(item["quantity"]) * Decimal(item["ek"]) == Decimal(decimal_value(wert))
        except (TypeError, ValueError, InvalidOperation):
            stimmt = False
        if not stimmt:
            item["warnings"].append(translate("errors.parser.position_value_mismatch", language))
    return ergebnis(document, items, warnings, typ, nummer, language)


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    """Beleg-Datum aus „Datum" im Kopf (auf Seite 1, Wert unter dem Titel)."""
    treffer = re.search(r"\bDatum\s+(\d{2}\.\d{2}\.\d{4})", document.text)
    if not treffer:
        raise DocumentParseError(translate("errors.importer.invoice_date_missing_or_ambiguous", language))
    tag = datetime.strptime(treffer[1], "%d.%m.%Y").date()
    return {"invoice_date": tag, "document_date": tag}
