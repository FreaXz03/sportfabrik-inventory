"""Gonso-Layout (Auftrag aus dem „Elastic"-Portal von ws4sports, Vertrieb
der Marke Gonso; Status „Nicht bestätigt").

Ein Block je Artikel und Farbe; links der Kopf, rechts die Tabelle:

    "Sitivo Tight M"          Einzelhandel  Großhandel  Menge  Gesamtkosten
    Stilnr.: 3000402          CHF139.90     CHF63.60    7      CHF445.20 / CHF979.30
    Farbname: "black / ..."   Größe/Menge
    Farbcode: M19018          S - Normal  M - Normal  L - Normal ...
                              1           2           2     ...

Jede Menge steht unter ihrer Grösse (x-Position). Grössen ohne Menge bleiben
leer und ergeben keine Position. Einzelhandel = UVP, Großhandel = EK ohne den
Rabatt, der in den „Seitenhinweisen" steht (Regel 10: EK ist nur, was im Beleg
steht). Die Stilnummer ist nicht je Farbe eindeutig: Stilnr. = Lieferanten-
artikelnummer, Farbcode = Artikelnummer.

Gegenproben: Mengen je Grösse = Menge des Blocks, Menge × Grosshandelspreis =
Gesamtkosten, Summe aller Blöcke = „Einheiten gesamt" und „Gesamtbetrag".

Typ „bestellung": erwartete Lieferung, kein Bestand (Regel 3); das Dokument
ist noch nicht bestätigt. Lieferant Gonso, Gruppe Dritte-Händler (angenommen
wie Columbia/Alpina/Chris/CMP).
"""

import re
from datetime import datetime
from decimal import Decimal

from .base import Document, DocumentParseError, ergebnis, joined, lines, pruefe_position
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "gonso"
LIEFERANT_NAME = "Gonso"
MARKE = "Gonso"

NUMMER = re.compile(r"Elastic-Auftrag\s*#\s*[–-]\s*(\d+)")
DATUM = re.compile(r"Auftragsdatum\s*[–-]\s*(\d{2})/(\d{2})/(\d{4})")
EINHEITEN = re.compile(r"Einheiten gesamt\s+(\d+)\s+Einzelhandelspreis")
GESAMTBETRAG = re.compile(r"Gesamtbetrag\s+CHF\s*([\d,]+\.\d{2})")
PREISZEILE = re.compile(
    r"CHF([\d,]+\.\d{2}) CHF([\d,]+\.\d{2}) (\d+) CHF([\d,]+\.\d{2}) / CHF([\d,]+\.\d{2})"
)
GANZZAHL = re.compile(r"\d+")
# Tabelle beginnt rechts der linken Kopfspalte (x in pt).
TABELLE_AB = 200
TOLERANZ = Decimal("0.05")


def detect(document: Document) -> int | None:
    text = document.text
    if "Elastic-Auftrag" in text and "Stilnr." in text and "Powered by Elastic" in text:
        return 5
    return None


def _zahl(text: str) -> str:
    """„1,017.60" → „1017.60"."""
    return text.replace(",", "")


def _ohne_anfuehrung(text: str) -> str:
    return text.strip().strip('"').strip()


def _links(zeilen: list) -> str:
    return joined([w for zeile in zeilen for w in zeile if w[0] < TABELLE_AB])


def _block(rows: list, start: int, anker: int, ende: int, page, language: str, warnings: list) -> tuple[list, Decimal]:
    """Positionen (eine je Grösse) und Betrag des Blocks aus den Zeilen
    `start` (Zeile „Einzelhandel Großhandel …") bis `ende` (exklusiv); die
    Zeile „Stilnr.:" liegt bei `anker`. Der Name steht links zwischen
    `start` und `anker`, in y-Reihenfolge mit der Tabellenzeile vermischt."""
    name = _ohne_anfuehrung(_links(rows[start:anker]))
    stil = joined(rows[anker]).replace("Stilnr.:", "").strip()
    farbname = farbcode = ""
    for zeile in rows[anker + 1 : anker + 4]:
        links = joined([w for w in zeile if w[0] < TABELLE_AB])
        if links.startswith("Farbname:"):
            farbname = _ohne_anfuehrung(links.removeprefix("Farbname:"))
        elif links.startswith("Farbcode:"):
            farbcode = links.removeprefix("Farbcode:").strip()

    tabelle = [[w for w in zeile if w[0] >= TABELLE_AB] for zeile in rows[start:ende]]
    tabelle = [zeile for zeile in tabelle if zeile]
    roh = [joined(zeile) for zeile in rows[start:ende]]
    preis = next((m for m in (PREISZEILE.fullmatch(joined(z)) for z in tabelle) if m), None)
    kopf = next((i for i, z in enumerate(tabelle) if joined(z) == "Größe/Menge"), None)
    if preis is None or kopf is None or kopf + 1 >= len(tabelle):
        warnings.append(
            translate("errors.parser.unassigned_row", language, page=page.number, row_text=" ".join(roh))
        )
        return [], Decimal(0)
    uvp, ek, gesamt, betrag = _zahl(preis[1]), _zahl(preis[2]), int(preis[3]), Decimal(_zahl(preis[4]))

    # Grössen aus der Zeile unter „Größe/Menge" („M - Normal"); die Mitte der drei Wörter ist die Spalte.
    spalten = []
    zeile = tabelle[kopf + 1]
    index = 0
    while index + 2 < len(zeile) and zeile[index + 1][4] == "-":
        gruppe = zeile[index : index + 3]
        suffix = gruppe[2][4]
        groesse = gruppe[0][4] if suffix == "Normal" else f"{gruppe[0][4]} {suffix}"
        spalten.append(dict(mitte=(gruppe[0][0] + gruppe[2][2]) / 2, groesse=groesse, menge=None))
        index += 3
    fremd = []
    for zeile in tabelle[kopf + 2 :]:
        for wort in zeile:
            if not GANZZAHL.fullmatch(wort[4]) or not spalten:
                fremd.append(wort[4])
                continue
            mitte = (wort[0] + wort[2]) / 2
            spalte = min(spalten, key=lambda s: abs(s["mitte"] - mitte))
            if spalte["menge"] is not None:
                fremd.append(wort[4])
            else:
                spalte["menge"] = wort[4]

    block_warnungen = []
    if fremd or not spalten:
        block_warnungen.append(
            translate("errors.parser.unassigned_row", language, page=page.number, row_text=" ".join(fremd) or name)
        )
    summe = sum(int(s["menge"]) for s in spalten if s["menge"])
    if summe != gesamt:
        block_warnungen.append(
            translate("errors.parser.size_quantity_mismatch", language, summe=summe, total=gesamt)
        )
    rechnung = Decimal(ek) * gesamt
    if abs(rechnung - betrag) > TOLERANZ:
        block_warnungen.append(
            translate("errors.parser.amount_mismatch", language, summe=f"{rechnung:.2f}", beleg=f"{betrag:.2f}")
        )

    items = []
    for spalte in spalten:
        if not spalte["menge"] or int(spalte["menge"]) == 0:
            continue
        item = pruefe_position(
            dict(
                brand=MARKE,
                supplier_article_no=stil,
                article_no=farbcode,
                description=name,
                color=farbname,
                size=spalte["groesse"],
                quantity=spalte["menge"],
                unit="Stk",
                ek=ek,
                uvp=uvp,
                page=page.number,
                raw_lines=roh,
            ),
            language,
        )
        item["warnings"] += block_warnungen
        items.append(item)
    if not items:
        warnings.append(
            translate("errors.parser.unassigned_row", language, page=page.number, row_text=" ".join(roh))
        )
    return items, betrag


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    items, warnings = [], []
    betrag = Decimal(0)
    for page in document.pages:
        rows = lines(page.words)
        # Seitenfuss („Seite – n", Druckvermerk, Adresse) gehört zu keinem Block.
        fuss = min((r[0][1] for r in rows if r[0][4] == "Seite"), default=page.height)
        rows = [r for r in rows if r[0][1] < fuss]
        starts = [i for i, r in enumerate(rows) if any(w[4] == "Einzelhandel" for w in r)]
        anker = [i for i, r in enumerate(rows) if any(w[4] == "Stilnr.:" for w in r)]
        if len(starts) != len(anker):
            warnings.append(
                translate("errors.parser.unassigned_row", language, page=page.number, row_text=joined([w for r in rows for w in r]))
            )
            continue
        for nummer, (start, index) in enumerate(zip(starts, anker)):
            ende = starts[nummer + 1] if nummer + 1 < len(starts) else len(rows)
            neue, block_betrag = _block(rows, start, index, ende, page, language, warnings)
            items += neue
            betrag += block_betrag
    text = document.text.replace("\n", " ")
    einheiten, gesamtbetrag = EINHEITEN.search(text), GESAMTBETRAG.search(text)
    menge = sum(Decimal(i["quantity"]) for i in items if i["quantity"])
    if einheiten and gesamtbetrag and (
        int(einheiten[1]) != menge or abs(Decimal(_zahl(gesamtbetrag[1])) - betrag) > TOLERANZ
    ):
        warnings.append(
            translate(
                "errors.parser.order_total_mismatch",
                language,
                menge=menge,
                betrag=betrag,
                soll_menge=einheiten[1],
                soll_betrag=_zahl(gesamtbetrag[1]),
            )
        )
    nummer = NUMMER.search(document.text)
    return ergebnis(document, items, warnings, "bestellung", nummer[1] if nummer else None, language)


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    treffer = DATUM.search(document.text)
    if not treffer:
        raise DocumentParseError(
            translate("errors.importer.invoice_date_missing_or_ambiguous", language)
        )
    tag = datetime.strptime("-".join(reversed(treffer.groups())), "%Y-%m-%d").date()
    return {"invoice_date": tag, "document_date": tag}
