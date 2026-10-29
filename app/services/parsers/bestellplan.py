"""Interner Bestellplan (Excel-Ausdruck „Bestellung Winter HW26 SF1 - SF4").

Querformat-Tabelle, eine Zeile je Produkt, Abschnitte je Warengruppe:

    Skischuhe Lady VP EP                                   (Abschnittskopf)
    Head Edge 7 W HV R102mm 335.00 103.00 20 18 16 18 72 7416.00 24120.00 16884.00 15.09.2026 X
    Total pro Grösse 99 78 82 75 334                       (Abschnittssumme)
    CHF 797'324.85 CHF 2'143'272.10 CHF 1'500'290.47      (Seitenfuss: EP/VP/VP-30%)

Spalten: Name, VP, EP, Menge SF1-SF4, Total, EP Total, VP Total, VP-30%,
Liefertermin. Die Köpfe „EP VP" über den Preisspalten sind in manchen
Abschnitten vertauscht, die Werte nicht - gelesen wird immer VP, dann EP; die
Gegenrechnung EP × Total = EP Total fängt einen Fehler ab.

Der Plan trägt weder Lieferant noch Belegnummer noch Datum, keine Grösse und keine
EAN. Er stammt von Dritt-Lieferanten direkt (Fabian, 05.10.2026: Code 999,
Marke = erstes Wort). Erzeugt werden: Nummer „Bestellung Winter HW26-<Hash>",
Datum = heute, Grösse ONESIZE, Lieferantenartikel = Bezeichnung. Typ
„bestellung": je Produkt und Filiale mit Menge > 0 eine Position mit
`lagerort_code` - erwartete Lieferung an diese Filiale, kein Bestand (Regel 3).
Der Liefertermin je Zeile bleibt im Originaltext der Vorschau.
"""

import hashlib
import re
from datetime import date
from decimal import Decimal

from .base import Document, ergebnis, gleiche_summe, pruefe_position
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "bestellplan"
LIEFERANT_NAME = "Bestellplan (Dritte-Händler)"

KOPF_WORTE = frozenset({"SF1", "SF2", "SF3", "SF4", "Liefertermin", "GEWA", "VEBO", "EP", "VP"})
FILIALEN = ("SF1", "SF2", "SF3", "SF4")
PREIS = re.compile(r"\d+(\.\d{1,2})?")  # VP steht teils ohne Rappen („255")
GANZZAHL = re.compile(r"\d+")
FRANKEN = re.compile(r"[\d’']+\.\d{2}")
TITEL = re.compile(r"Bestellung\s+Winter\s+\S+")
ZEILEN_TOLERANZ = 3.0
# Linke Kante jeder Spalte (x in pt, Ausdruck 1684 pt breit); ein Wort gehört
# zur letzten Spalte, deren Kante es erreicht. Zahlen stehen rechtsbündig, ihre
# linke Kante schwankt um wenige pt.
SPALTEN = [
    ("name", 0),
    ("vp", 280),
    ("ep", 335),
    ("SF1", 390),
    ("SF2", 440),
    ("SF3", 490),
    ("SF4", 540),
    ("total", 590),
    ("ep_total", 650),
    ("vp_total", 780),
    ("vp30", 905),
    ("termin", 1000),
    ("rest", 1100),
]


def detect(document: Document) -> int | None:
    kopf = {w[4] for page in document.pages for w in page.words}
    return 5 if KOPF_WORTE <= kopf else None


def _spalte(x: float) -> str:
    name = SPALTEN[0][0]
    for key, links in SPALTEN:
        if x >= links:
            name = key
    return name


def _zeilen(words) -> list[list]:
    """Wörter nach Zeilenmitte gruppiert, jede Zeile von links nach rechts."""
    zeilen: list[list] = []
    erste_mitte = 0.0
    for w in sorted(words, key=lambda w: (w[1] + w[3]) / 2):
        mitte = (w[1] + w[3]) / 2
        if zeilen and mitte - erste_mitte <= ZEILEN_TOLERANZ:
            zeilen[-1].append(w)
        else:
            zeilen.append([w])
            erste_mitte = mitte
    return [sorted(z, key=lambda w: w[0]) for z in zeilen]


def _felder(zeile) -> dict:
    felder = {key: [] for key, _ in SPALTEN}
    for w in zeile:
        felder[_spalte(w[0])].append(w[4])
    return felder


def _betrag(text: str) -> Decimal:
    return Decimal(text.replace("’", "").replace("'", ""))


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    items, warnings = [], []
    soll_menge, ist_ep, soll_ep = Decimal(0), Decimal(0), None
    for page in document.pages:
        for zeile in _zeilen(page.words):
            text = " ".join(w[4] for w in zeile)
            f = _felder(zeile)
            name = " ".join(f["name"])
            if name.startswith("Total pro Grösse"):
                soll_menge += Decimal(f["total"][0]) if f["total"] else 0
                continue
            if f["ep_total"] and f["vp_total"] and f["vp30"] and not name:
                # Seitenfuss „CHF <EP> CHF <VP> CHF <VP-30%>"
                betraege = [w[4] for w in zeile if FRANKEN.fullmatch(w[4])]
                if betraege:
                    soll_ep = _betrag(betraege[0])
                continue
            if not (name and f["vp"] and PREIS.fullmatch(f["vp"][0]) and f["ep"] and f["total"]):
                if name and any(re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", t) for t in f["termin"]):  # Produktzeile, die nicht gelesen werden konnte
                    warnings.append(
                        translate("errors.parser.unassigned_row", language, page=page.number, row_text=text)
                    )
                continue  # sonst Titel, Kopf, Abschnittskopf
            if not (PREIS.fullmatch(f["ep"][0]) and GANZZAHL.fullmatch(f["total"][0])):
                warnings.append(
                    translate("errors.parser.unassigned_row", language, page=page.number, row_text=text)
                )
                continue
            mengen = {code: f[code][0] for code in FILIALEN if f[code] and GANZZAHL.fullmatch(f[code][0])}
            total = int(f["total"][0])
            if sum(int(m) for m in mengen.values()) != total:
                warnings.append(
                    translate("errors.parser.unassigned_row", language, page=page.number, row_text=text)
                )
            if f["ep_total"] and PREIS.fullmatch(f["ep_total"][0]):
                if Decimal(f["ep"][0]) * total != Decimal(f["ep_total"][0]):
                    warnings.append(
                        translate("errors.parser.unassigned_row", language, page=page.number, row_text=text)
                    )
                ist_ep += Decimal(f["ep_total"][0])
            for code in FILIALEN:
                if code not in mengen or int(mengen[code]) == 0:
                    continue
                item = dict(
                    brand=name.split()[0],
                    supplier_article_no=name,
                    article_no=name,
                    ean="",
                    description=name,
                    color=None,
                    size="ONESIZE",
                    quantity=mengen[code],
                    unit="Stk",
                    ek=f["ep"][0],
                    uvp=f["vp"][0],
                    lagerort_code=code,
                    page=page.number,
                    raw_lines=[text],
                )
                items.append(pruefe_position(item, language))
    if soll_menge:
        warnings += gleiche_summe(soll_menge, items, language)
    if soll_ep is not None and soll_ep != ist_ep:
        warnings.append(
            translate(
                "errors.parser.order_total_mismatch", language,
                menge=sum(Decimal(i["quantity"]) for i in items),
                betrag=f"{ist_ep:.2f}", soll_menge=soll_menge, soll_betrag=f"{soll_ep:.2f}",
            )
        )
    return ergebnis(document, items, warnings, "bestellung", _nummer(document), language)


def _nummer(document: Document) -> str:
    """Titel + Hash des Inhalts: dieselbe Datei ergibt immer dieselbe Nummer."""
    treffer = TITEL.search(document.text)
    titel = " ".join(treffer[0].split()) if treffer else "Bestellplan"
    return f"{titel}-{hashlib.sha256(document.text.encode()).hexdigest()[:8].upper()}"


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    heute = date.today()
    return {"invoice_date": heute, "document_date": heute}
