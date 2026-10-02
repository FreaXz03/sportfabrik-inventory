"""Bliz-Layout (Bestellformular/Preisliste, Excel-Ausdruck).

Eine Tabelle mit einer Zeile je Brillenmodell und Farbe:

    QTY VALUE MATERIAL GRID VALUE STYLE NAME FRAME LENS COLOR VLT Filter Category MATERIAL UPC WHLS RRP
    0   0ZG8002 13 00 RAVE MATTE BLUE BROWN W BLUE MULTI 13% CAT.3 INJECTED 8056262462416 52.28 120.00

Die Spalten liegen fest (Excel-Vorlage); die Kopfzeile steht nur auf der ersten
Seite, die Folgeseiten setzen die Tabelle ohne Kopf fort. Jede Zeile beginnt mit
dem Stil-Code (Spalte MATERIAL); die UPC (= EAN) ist optional (Regel 5). Preise stehen 1 pt höher als der Rest der Zeile,
darum wird jedes Wort der Zeile zugeordnet, deren Mitte ihm am nächsten liegt.

Das Formular trägt weder Belegnummer noch Datum und bei der Vorlage stehen alle
Mengen auf 0: es bleibt eine Vorschau, der Import weist es ab (Regel 3: ohne
Menge keine Ware). Eine Brille hat keine Grösse (ONESIZE); Farbe = Rahmen / Linse.
"""

import re

from .base import Document, DocumentParseError, ergebnis, pruefe_position
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "bliz"
LIEFERANT_NAME = "Bliz"
MARKE = "Bliz"

KOPF_WORTE = frozenset({"QTY", "STYLE", "FRAME", "LENS", "VLT", "UPC", "WHLS", "RRP"})
PREIS = re.compile(r"\d+\.\d{2}")
# Linke Kante jeder Spalte (x in pt); ein Wort gehört zur letzten Spalte, deren
# Kante es erreicht. Reihenfolge = Reihenfolge im Formular.
SPALTEN = [
    ("qty", 0),
    ("artikel", 78),
    ("code", 112),
    ("name", 160),
    ("rahmen", 215),
    ("linse", 280),
    ("vlt", 358),
    ("kategorie", 415),
    ("material", 460),
    ("upc", 480),
    ("preis", 518),
]
MITTE_TOLERANZ = 3.5


def detect(document: Document) -> int | None:
    kopf = {w[4] for page in document.pages for w in page.words}
    return 5 if KOPF_WORTE <= kopf else None


def _spalte(x: float) -> str:
    name = SPALTEN[0][0]
    for key, links in SPALTEN:
        if x >= links:
            name = key
    return name


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    items, warnings = [], []
    for page in document.pages:
        woerter = sorted(page.words, key=lambda w: (w[1], w[0]))
        kopf = [w for w in woerter if w[4] in KOPF_WORTE]
        oben = max((w[3] for w in kopf), default=0)
        anker = [w for w in woerter if w[1] > oben and _spalte(w[0]) == "artikel"]
        zeilen = [(a, []) for a in sorted(anker, key=lambda w: w[1])]
        for w in woerter:
            if w[1] <= oben or w in anker:
                continue
            mitte = (w[1] + w[3]) / 2
            abstand, zeile = min(
                ((abs((a[1] + a[3]) / 2 - mitte), z) for a, z in zeilen), default=(None, None)
            )
            if zeile is None or abstand > MITTE_TOLERANZ:
                warnings.append(
                    translate("errors.parser.unassigned_row", language, page=page.number, row_text=w[4])
                )
                continue
            zeile.append(w)
        for a, rest in zeilen:
            felder = {key: [] for key, _ in SPALTEN}
            for w in sorted(rest + [a], key=lambda w: w[0]):
                felder[_spalte(w[0])].append(w[4])
            preise = [t for t in felder["preis"] if PREIS.fullmatch(t)]
            code = " ".join(felder["code"])
            artikel = " ".join(felder["artikel"])
            rahmen, linse = " ".join(felder["rahmen"]), " ".join(felder["linse"])
            item = dict(
                brand=MARKE,
                supplier_article_no=artikel,
                article_no=f"{artikel} {code}".strip(),
                ean=" ".join(felder["upc"]),
                description=" ".join(felder["name"]),
                color=" / ".join(t for t in (rahmen, linse) if t) or None,
                size="ONESIZE",
                quantity=" ".join(felder["qty"]),
                unit="Stk",
                ek=preise[0] if preise else "",
                uvp=preise[1] if len(preise) > 1 else "",
                page=page.number,
                raw_lines=[" ".join(w[4] for w in sorted(rest + [a], key=lambda w: w[0]))],
            )
            items.append(pruefe_position(item, language))
    return ergebnis(document, items, warnings, None, None, language)


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    raise DocumentParseError(translate("errors.importer.invoice_date_missing_or_ambiguous", language))
