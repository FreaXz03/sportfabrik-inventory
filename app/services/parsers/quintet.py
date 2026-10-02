"""Quintet-24-Layout (Bestellinformation aus der INTERSPORT-Bestellplattform,
bisher nur The North Face, Vororder FW26).

Ein Block je Artikel und Farbe:

    The North Face
    M COMBAL SOFTSHELL 2.0 - TNF BLACK black black      (Farbe nach „ - ",
    356343                                               Farbfamilie klein)
    Lieferantartikel Nr. NF0A8BX1
    Liefertermin
    2026-07-22
    S M L XL XXL                                         (Grössen-Raster)
    1 2 2 1 1 7 60,50 CHF 423,50 CHF                     (Mengen, Total, EP, Betrag)
    130,00 CHF                                           (UVP)

Jede Menge gehört zur Grösse direkt darüber. Breite Raster laufen über die
Spalte der Gesamtmenge hinaus: dann stehen die Preise eine Zeile tiefer, und
lange Grössen brechen um („XLREGUL" / „AR"). Gegenproben: Mengen je Grösse =
Gesamtmenge des Blocks, Summe aller Blöcke = „Wert:" im Seitenfuss. Ein Block,
der über einen Seitenwechsel läuft, wird nicht zusammengesetzt, sondern als
nicht zugeordnete Zeile gemeldet (bisher in keinem Beispiel vorgekommen).

Das Dokument ist ausdrücklich keine Bestellbestätigung. Typ „bestellung":
erwartete Lieferung, kein Bestand (Regel 3). Lieferant The North Face, Gruppe
Intern (Fabian, 02.10.2026). Andere Marken auf Quintet werden nicht geraten,
sondern als unbekanntes Layout gemeldet (`detect`).
"""

import re
from datetime import datetime
from decimal import Decimal

from .base import Document, DocumentParseError, ergebnis, joined, lines, pruefe_position
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "quintet"
LIEFERANT_NAME = "The North Face"

NUMMER = re.compile(r"Bestellung\s+#(\d+)")
DATUM = re.compile(r"Bestelldatum:\s*(\d{4}-\d{2}-\d{2})")
WERT = re.compile(r"Wert:\s*(\d+)\s+([\d.']+,\d{2})\s*CHF")
BETRAG = re.compile(r"[\d.']+,\d{2}")
GANZZAHL = re.compile(r"\d+")
# Abstand (pt), in dem eine Menge oder ein Grössen-Rest noch unter einer Grösse liegt.
TOLERANZ = 4


def detect(document: Document) -> int | None:
    text = document.text
    if "Quintet" in text and "Lieferantartikel" in text and LIEFERANT_NAME in text:
        return 5
    return None


def _betrag(text: str) -> str:
    """„1.048,85" → „1048.85" (Tausenderpunkt, Dezimalkomma)."""
    return re.sub(r"[.'\s]", "", text).replace(",", ".")


def _spalte(spalten: list, wort) -> dict | None:
    mitte = (wort[0] + wort[2]) / 2
    return next(
        (s for s in spalten if s["x0"] - TOLERANZ <= mitte <= s["x1"] + TOLERANZ), None
    )


def _bezeichnung(zeilen: list[str]) -> tuple[str, str | None]:
    """Bezeichnung und Farbe; die klein geschriebene Farbfamilie am Ende fällt weg."""
    worte = " ".join(zeilen).split()
    while worte and worte[-1].islower():
        worte.pop()
    text = " ".join(worte)
    if " - " not in text:
        return text, None
    bezeichnung, _, farbe = text.rpartition(" - ")
    return bezeichnung.strip(), farbe.strip() or None


def _block(rows: list, anker: int, page, language: str, warnings: list) -> tuple[list, Decimal]:
    """Positionen (eine je Grösse) und Betrag eines Artikelblocks."""
    links = rows[anker][0][0]
    oben = anker - 1
    # Hinauf bis zum Ende des vorigen Blocks (Zeile mit „CHF") oder bis zu
    # einer Zeile, die anders eingerückt ist (Kopf der Seite).
    while (
        oben > 0
        and abs(rows[oben - 1][0][0] - links) <= TOLERANZ
        and not any(w[4] == "CHF" for w in rows[oben - 1])
    ):
        oben -= 1
    kopf = [joined(r) for r in rows[oben:anker]]
    if len(kopf) < 3:
        warnings.append(
            translate("errors.parser.unassigned_row", language, page=page.number, row_text=joined(rows[anker]))
        )
        return [], Decimal(0)
    marke, *beschreibung, artikel = kopf
    bezeichnung, farbe = _bezeichnung(beschreibung)
    lieferant_artikel = rows[anker][-1][4]

    # Nach „Lieferantartikel": Liefertermin, Datum, dann das Raster bis zur
    # Zeile mit den Preisen (erste Zeile mit „CHF"), danach die UVP-Zeile.
    raster = []
    preise = None
    for index in range(anker + 3, len(rows)):
        if any(w[4] == "CHF" for w in rows[index]):
            preise = index
            break
        raster.append(rows[index])
    if preise is None or not raster:
        warnings.append(
            translate("errors.parser.unassigned_row", language, page=page.number, row_text=joined(rows[anker]))
        )
        return [], Decimal(0)
    preiszeile = rows[preise]
    betraege = [i for i, w in enumerate(preiszeile) if BETRAG.fullmatch(w[4])]
    erster = betraege[0] if betraege else len(preiszeile)
    gesamt = preiszeile[erster - 1][4] if erster > 0 else ""
    ep = _betrag(preiszeile[betraege[0]][4]) if betraege else ""
    betrag = Decimal(_betrag(preiszeile[betraege[1]][4])) if len(betraege) > 1 else Decimal(0)
    # UVP-Zeile nur, wenn sie wirklich „<Betrag> CHF" ist - sonst fehlt die
    # UVP, und pruefe_position meldet das Pflichtfeld.
    ende = preise + 1
    if ende < len(rows) and any(w[4] == "CHF" for w in rows[ende]):
        uvp = next((_betrag(w[4]) for w in rows[ende] if BETRAG.fullmatch(w[4])), "")
        ende += 1
    else:
        uvp = ""

    beschriftet = [r for r in raster if not all(GANZZAHL.fullmatch(w[4]) for w in r)]
    spalten = [dict(x0=w[0], x1=w[2], groesse=w[4], menge=None) for w in beschriftet[0]] if beschriftet else []
    fremd = []  # Wörter, die unter keiner Grösse liegen
    for rest in beschriftet[1:]:
        for wort in rest:
            spalte = _spalte(spalten, wort)
            if spalte is None:
                fremd.append(wort[4])
            else:
                spalte["groesse"] += wort[4]
    mengen = [w for r in raster if r not in beschriftet for w in r]
    mengen += preiszeile[: max(erster - 1, 0)]
    for wort in mengen:
        spalte = _spalte(spalten, wort)
        if not GANZZAHL.fullmatch(wort[4]) or spalte is None or spalte["menge"] is not None:
            fremd.append(wort[4])
        else:
            spalte["menge"] = wort[4]
    block_warnungen = []
    if fremd:
        block_warnungen.append(
            translate("errors.parser.unassigned_row", language, page=page.number, row_text=" ".join(fremd))
        )
    summe = sum(int(s["menge"]) for s in spalten if s["menge"])
    if not gesamt.isdigit() or summe != int(gesamt):
        block_warnungen.append(
            translate("errors.parser.size_quantity_mismatch", language, summe=summe, total=gesamt)
        )

    roh = [joined(r) for r in rows[oben:ende]]
    items = []
    for spalte in spalten:
        if not spalte["menge"] or int(spalte["menge"]) == 0:
            continue
        item = pruefe_position(
            dict(
                brand=marke,
                supplier_article_no=lieferant_artikel,
                article_no=artikel,
                description=bezeichnung,
                color=farbe,
                size=spalte["groesse"],
                quantity=spalte["menge"],
                unit="Stk",
                ek=ep,
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
            translate("errors.parser.unassigned_row", language, page=page.number, row_text=joined(rows[anker]))
        )
    return items, betrag


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    items, warnings = [], []
    betrag = Decimal(0)
    for page in document.pages:
        rows = lines(page.words)
        # Seitenfuss („Seite: …", „Wert: …", AGB) gehört zu keinem Block.
        fuss = min(
            (r[0][1] for r in rows if r[0][4] in {"Seite:", "Wert:"} or "Quintet" in joined(r)),
            default=page.height,
        )
        rows = [r for r in rows if r[0][1] < fuss]
        for index, row in enumerate(rows):
            if row[0][4] == "Lieferantartikel":
                neue, block_betrag = _block(rows, index, page, language, warnings)
                items += neue
                betrag += block_betrag
    wert = WERT.search(document.text)
    menge = sum(Decimal(i["quantity"]) for i in items if i["quantity"])
    # Quintet rundet je Zeile: beim Betrag 5 Rappen Spielraum, die Menge ist exakt.
    if wert and (
        int(wert[1]) != menge or abs(Decimal(_betrag(wert[2])) - betrag) > Decimal("0.05")
    ):
        warnings.append(
            translate(
                "errors.parser.order_total_mismatch",
                language,
                menge=menge,
                betrag=betrag,
                soll_menge=wert[1],
                soll_betrag=_betrag(wert[2]),
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
    tag = datetime.strptime(treffer[1], "%Y-%m-%d").date()
    return {"invoice_date": tag, "document_date": tag}
