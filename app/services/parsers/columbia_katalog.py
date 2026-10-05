"""Columbia-Linesheet (Saisonkatalog „CHE | F26 – SPORT-FABRIK <Gruppe>“,
Columbia Sportswear International SARL). Wird von `columbia.py` mit
ausgeliefert: gleicher Lieferant, anderes Layout.

Das Dokument ist **keine Bestellung**: es nennt weder Mengen noch Belegnummer
noch Liefertermin, nur Modelle mit Preisen. Es legt Artikel und Preise an,
gebucht wird nichts (Regel 3) - wie beim Bliz-Formular. Menge 0 je Position;
Nummer `COLUMBIA-<Saison>-<Gruppe>-<Hash des Inhalts>`, Datum aus „Created“
(Monat/Tag/Jahr).

Ein Block je Modell, mit festen Spalten (x in pt):

    LAKE 22™ II DOWN HOODED JACKET        (Titel, 30 pt)
    2088363                               (Stil-Nr., 7 Ziffern)
    FEATURES … FABRICS …                  (Beschreibung links, wird ignoriert)
    348          309                      (Farbcodes, ab 142 pt, mehrere Spalten)
    Safari       Tea Light                (Farbname, darunter)
    XS S M L XL  △ 25in / 63.5cm   Pan-EU Active
                                   165.00 MSRP / 78.60 BASE

Eine Farbe ist Code + Name („Dark Stone, Black“ ist ein Name). Material-Nr. =
Stil + Farbcode (10 Ziffern, wie in der Auftragsbestätigung). Je Farbe und
Grösse eine Position: Annahme (Fabian bestätigt offen), dass jede Farbe in
allen Grössen des Modells geführt wird. Mehrere Längen hinter „▲“ (Beinlänge)
ergeben „Grösse x Länge“; eine einzelne („R“) wird ignoriert.
MSRP = UVP, BASE = EK (Regel 10, nur was im Beleg steht).

Gegenprobe: die Stil-Nummern der Blöcke = das „STYLE NUMBER INDEX“ am Ende.
"""

import hashlib
import re
from datetime import date

from .base import Document, DocumentParseError, ergebnis, pruefe_position
from ...core.i18n import DEFAULT_LANGUAGE, translate

MARKE = "Columbia"

STIL = re.compile(r"\d{7}")
CODE = re.compile(r"\d{3}")
PREIS = re.compile(r"\d+\.\d{2}")
INDEX_ZEILE = re.compile(r"(\d{7})\.{3,}\s*\d+")
ERSTELLT = re.compile(r"Created\s+(\d{1,2})/(\d{1,2})/(\d{4})")
SAISON = re.compile(r"\b([A-Z]\d{2})\b")
# Spalten (x in pt)
LINKS = 40  # Stil-Nr. und Titel stehen links davon
FARBE_AB = 138
PREIS_AB = 340
GRUPPEN = ("FREIZEIT", "OUTDOOR", "SKI")


def erkenne(document: Document) -> bool:
    text = document.text
    return (
        "Columbia Sportswear International" in text
        and "STYLE NUMBER INDEX" in text
        and "MSRP" in text
        and "BASE" in text
    )


def _kopf(document: Document) -> tuple[str, str]:
    """(Saison, Gruppe) von der Titelseite, z. B. („F26“, „OUTDOOR“)."""
    erste = document.pages[0].text
    saison = SAISON.search(erste)
    gruppe = next((g for g in GRUPPEN if g in erste.upper()), "")
    return (saison[1] if saison else ""), gruppe


def _titel(worte: list, oben: float, unten: float) -> str:
    zeilen = sorted((w for w in worte if oben < w[1] < unten), key=lambda w: (round(w[1]), w[0]))
    return " ".join(w[4] for w in zeilen).strip()


def _farben(worte: list) -> list[tuple[str, str]]:
    """(Code, Name) je Farbzelle. Die Zellen liegen in einem Raster von rund
    61 pt; der Name steht unter dem Code und bricht innerhalb der Zelle um. Ein
    Wort gehört darum zum Code, der links davon am nächsten steht (grösstes x)
    und über ihm am nächsten (grösstes y)."""
    codes = [w for w in worte if CODE.fullmatch(w[4])]
    namen: dict[int, list] = {id(c): [] for c in codes}
    for wort in worte:
        if CODE.fullmatch(wort[4]):
            continue
        kandidaten = [c for c in codes if c[0] <= wort[0] + 4 and c[1] <= wort[1] + 4]
        if not kandidaten:
            continue
        bester = max(kandidaten, key=lambda c: (round(c[0]), c[1]))
        namen[id(bester)].append(wort)
    farben = []
    for code in sorted(codes, key=lambda c: (round(c[1] / 8), c[0])):
        teile = sorted(namen[id(code)], key=lambda w: (round(w[1]), w[0]))
        farben.append((code[4], " ".join(w[4] for w in teile).strip()))
    return farben


def _groessen(worte: list, y_von: float, y_bis: float) -> tuple[list[str], list[str]]:
    """(Grössen, Längen) der Grössenzeile; Längen stehen hinter „▲“."""
    zeile = sorted(
        (w for w in worte if y_von <= w[1] <= y_bis and FARBE_AB <= w[0] < PREIS_AB),
        key=lambda w: w[0],
    )
    groessen, laengen = [], []
    ziel = groessen
    for wort in zeile:
        text = wort[4]
        if text == "▲":
            ziel = laengen
            continue
        if text == "△":
            break
        ziel.append(text.strip('"'))
    return groessen, laengen


def _bloecke(page) -> list[dict]:
    worte = page.words
    anker = sorted(
        (w for w in worte if STIL.fullmatch(w[4]) and w[0] < LINKS and w[1] < 700),
        key=lambda w: w[1],
    )
    ergebnisse = []
    for index, stil in enumerate(anker):
        bis = anker[index + 1][1] - 36 if index + 1 < len(anker) else 760
        region = [w for w in worte if stil[1] - 4 < w[1] < bis]
        titel = _titel(worte, stil[1] - 36, stil[1] - 3)
        msrp = next((w for w in region if w[4] == "MSRP"), None)
        base = next((w for w in region if w[4] == "BASE"), None)
        if msrp is None or base is None:
            ergebnisse.append(dict(stil=stil[4], titel=titel, fehler=True))
            continue
        zahl = lambda marke: next(
            (w[4] for w in region if PREIS.fullmatch(w[4]) and abs(w[1] - marke[1]) < 3 and w[0] < marke[0]),
            None,
        )
        farbband = [w for w in region if w[0] >= FARBE_AB and w[1] > stil[1] and w[1] < msrp[1] - 3]
        groessen, laengen = _groessen(region, msrp[1] + 2, base[1] + 1)
        ergebnisse.append(
            dict(
                stil=stil[4],
                titel=titel,
                uvp=zahl(msrp),
                ek=zahl(base),
                farben=_farben(farbband),
                groessen=groessen,
                laengen=laengen,
                roh=[w[4] for w in sorted(region, key=lambda w: (round(w[1]), w[0]))],
                seite=page.number,
            )
        )
    return ergebnisse


def _positionen(block: dict, language: str) -> list[dict]:
    groessen = block["groessen"]
    if len(block["laengen"]) > 1:
        groessen = [f"{g}x{laenge}" for g in groessen for laenge in block["laengen"]]
    items = []
    for code, name in block["farben"]:
        for groesse in groessen:
            nummer = f"{block['stil']}{code}"
            items.append(
                pruefe_position(
                    dict(
                        brand=MARKE,
                        supplier_article_no=nummer,
                        article_no=nummer,
                        description=block["titel"],
                        color=name or None,
                        size=groesse,
                        quantity="0",
                        unit="Stk",
                        ek=block["ek"],
                        uvp=block["uvp"],
                        page=block["seite"],
                        raw_lines=block["roh"],
                    ),
                    language,
                )
            )
    return items


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    items, warnings, gelesen = [], [], []
    for page in document.pages:
        for block in _bloecke(page):
            if block.get("fehler") or not block["farben"] or not block["groessen"] or not block["uvp"] or not block["ek"]:
                warnings.append(
                    translate(
                        "errors.parser.unassigned_row", language, page=page.number,
                        row_text=f"{block['stil']} {block['titel']}",
                    )
                )
                continue
            gelesen.append(block["stil"])
            items += _positionen(block, language)
    # Gegenprobe: dieselben Stil-Nummern wie im Index am Ende.
    index = set(INDEX_ZEILE.findall(document.text))
    if index and index != set(gelesen):
        fehlt = sorted(index - set(gelesen))
        warnings.append(
            translate("errors.parser.unassigned_row", language, page=1, row_text="Index: " + ", ".join(fehlt or sorted(set(gelesen) - index)))
        )
    saison, gruppe = _kopf(document)
    inhalt = hashlib.sha256("|".join(f"{i['supplier_article_no']}{i['size']}" for i in items).encode()).hexdigest()[:8]
    nummer = "-".join(part for part in ("COLUMBIA", saison, gruppe, inhalt.upper()) if part)
    return ergebnis(document, items, warnings, "bestellung", nummer, language)


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    treffer = ERSTELLT.search(document.pages[0].text)
    if not treffer:
        raise DocumentParseError(translate("errors.importer.invoice_date_missing_or_ambiguous", language))
    monat, tag, jahr = (int(g) for g in treffer.groups())
    try:
        tag = date(jahr, monat, tag)
    except ValueError as exc:
        raise DocumentParseError(translate("errors.importer.invoice_date_missing_or_ambiguous", language)) from exc
    return {"invoice_date": tag, "document_date": tag}
