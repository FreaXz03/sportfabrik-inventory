"""Columbia-Layout (Auftragsempfangsbestätigung der Columbia Sportswear
International SARL, „OA…"-Nummer; Liq- und Regulär-Bestellungen).

Ein Block je Artikel und Farbe, in dieser Lesereihenfolge der Textebene:

    2118541845                                          (Material-Nr., 10 Ziffern)
    AO3772845 Zero Rules Light SS Grap-Super Sonic, Sc  (Stil+Farbe, Name-Farbe)
    Größe / Stückzahl
    -S-  2   -M-  2   -L-  2 ...                        (Grösse, Menge je Grösse)
    10  22,70  50,00  11,35  113,50                     (Menge, Preis, Rabatt %,
                                                         Nettopreis/Stück, Betrag)

Name und Farbe sind vom Absender nach 50 Zeichen abgeschnitten („Sc"); sie
werden so übernommen. Preis = Listenpreis vor Rabatt; als EK gilt der
Nettopreis je Stück (Regel 10). Eine UVP steht nicht im Dokument: das
Pflichtfeld wird als Warnung gemeldet und in der Vorschau von Hand ergänzt,
nicht geraten. Die Folgeseiten (AGB) werden ignoriert; ein Artikelblock über
einen Seitenwechsel ist bisher in keinem Beispiel vorgekommen.

Gegenproben: Mengen je Grösse = Menge des Blocks, Menge × Nettopreis = Betrag
(5 Rappen Spielraum), Summe aller Blöcke = „Gesamtmenge" und „Zwischensumme".

Typ „auftragsbestaetigung": erwartete Lieferung, kein Bestand (Regel 3).
Lieferant Columbia, Gruppe Dritte-Händler (Direktbestellung bei der Marke,
angenommen wie Alpina/Chris/CMP).
"""

import re
from datetime import datetime
from decimal import Decimal

from . import columbia_katalog
from .base import Document, DocumentParseError, ergebnis, pruefe_position
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "columbia"
LIEFERANT_NAME = "Columbia"
MARKE = "Columbia"

NUMMER = re.compile(r"Auftrags-\s*Nr\.:\s*(\d+)")
DATUM = re.compile(r"Bestelldatum:\s*(\d{2})\.(\d{2})\.(\d{4})")
GESAMTMENGE = re.compile(r"Gesamtmenge\s+(\d+)")
ZWISCHENSUMME = re.compile(r"Zwischensumme\s+([\d.']+,\d{2})")
MATERIAL = re.compile(r"\d{10}")
STIL = re.compile(r"([A-Z]{2}\d+)\s+(.+)")
GROESSE = re.compile(r"-(.+)-")
GANZZAHL = re.compile(r"\d+")
BETRAG = re.compile(r"[\d.']*\d,\d{2}")
KOPF_ENDE = "Gesamtbetrag"
FUSS = "Gesamtmenge"
TOLERANZ = Decimal("0.05")


def detect(document: Document) -> int | None:
    text = document.text
    if "Columbia Sportswear" in text and "Auftragsempfangsbestätigung" in text:
        return 5
    # Linesheet (Saisonkatalog ohne Mengen), eigenes Modul: columbia_katalog.py
    if columbia_katalog.erkenne(document):
        return 5
    return None


def _betrag(text: str) -> str:
    """„1.048,85" → „1048.85" (Tausenderpunkt, Dezimalkomma)."""
    return re.sub(r"[.'\s]", "", text).replace(",", ".")


def _bezeichnung(text: str) -> tuple[str, str | None]:
    bezeichnung, trenner, farbe = text.rpartition("-")
    if not trenner:
        return text.strip(), None
    return bezeichnung.strip(), farbe.strip() or None


def _seitenzeilen(page) -> list[str]:
    """Zeilen zwischen Tabellenkopf und „Gesamtmenge"; leer ohne Tabellenkopf."""
    zeilen = [z.strip() for z in page.text.split("\n")]
    if KOPF_ENDE not in zeilen:
        return []
    start = zeilen.index(KOPF_ENDE) + 1
    ende = zeilen.index(FUSS) if FUSS in zeilen[start:] else len(zeilen)
    return [z for z in zeilen[start:ende] if z]


def _block(zeilen: list[str], anfang: int, page, language: str) -> tuple[list, Decimal, int]:
    """(Positionen, Betrag, Index nach dem Block) eines Artikelblocks."""
    material = zeilen[anfang]
    index = anfang + 1
    stil = STIL.fullmatch(zeilen[index]) if index < len(zeilen) else None
    if stil is None:
        return [], Decimal(0), anfang + 1
    index += 1
    if zeilen[index : index + 2] == ["Größe", "Stückzahl"]:
        index += 2
    groessen = []
    while index + 1 < len(zeilen):
        groesse = GROESSE.fullmatch(zeilen[index])
        if groesse is None or not GANZZAHL.fullmatch(zeilen[index + 1]):
            break
        groessen.append((groesse[1], zeilen[index + 1]))
        index += 2
    summe = zeilen[index : index + 5]
    if (
        not groessen
        or len(summe) < 5
        or not GANZZAHL.fullmatch(summe[0])
        or not all(BETRAG.fullmatch(z) for z in summe[1:])
    ):
        return [], Decimal(0), index
    index += 5
    gesamt = int(summe[0])
    netto, betrag = _betrag(summe[3]), Decimal(_betrag(summe[4]))
    roh = zeilen[anfang:index]

    warnungen = []
    mengen = sum(int(menge) for _, menge in groessen)
    if mengen != gesamt:
        warnungen.append(translate("errors.parser.size_quantity_mismatch", language, summe=mengen, total=gesamt))
    rechnung = Decimal(netto) * gesamt
    if abs(rechnung - betrag) > TOLERANZ:
        warnungen.append(translate("errors.parser.amount_mismatch", language, summe=f"{rechnung:.2f}", beleg=f"{betrag:.2f}"))

    bezeichnung, farbe = _bezeichnung(stil[2])
    items = []
    for groesse, menge in groessen:
        if int(menge) == 0:
            continue
        item = pruefe_position(
            dict(
                brand=MARKE,
                supplier_article_no=stil[1],
                article_no=material,
                description=bezeichnung,
                color=farbe,
                size=groesse,
                quantity=menge,
                unit="Stk",
                ek=netto,
                uvp="",
                page=page.number,
                raw_lines=roh,
            ),
            language,
        )
        item["warnings"] += warnungen
        items.append(item)
    return items, betrag, index


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    if columbia_katalog.erkenne(document):
        return columbia_katalog.parse(document, language)
    items, warnings = [], []
    betrag = Decimal(0)
    for page in document.pages:
        zeilen = _seitenzeilen(page)
        index = 0
        while index < len(zeilen):
            if MATERIAL.fullmatch(zeilen[index]):
                neue, block_betrag, naechster = _block(zeilen, index, page, language)
                if neue:
                    items += neue
                    betrag += block_betrag
                else:
                    warnings.append(
                        translate("errors.parser.unassigned_row", language, page=page.number, row_text=" ".join(zeilen[index:naechster]))
                    )
                index = naechster
            else:
                warnings.append(
                    translate("errors.parser.unassigned_row", language, page=page.number, row_text=zeilen[index])
                )
                index += 1
    menge, summe = GESAMTMENGE.search(document.text), ZWISCHENSUMME.search(document.text)
    gezaehlt = sum(Decimal(i["quantity"]) for i in items if i["quantity"])
    if menge and summe and (
        int(menge[1]) != gezaehlt or abs(Decimal(_betrag(summe[1])) - betrag) > TOLERANZ
    ):
        warnings.append(
            translate(
                "errors.parser.order_total_mismatch",
                language,
                menge=gezaehlt,
                betrag=betrag,
                soll_menge=menge[1],
                soll_betrag=_betrag(summe[1]),
            )
        )
    nummer = NUMMER.search(document.text)
    return ergebnis(document, items, warnings, "auftragsbestaetigung", nummer[1] if nummer else None, language)


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    if columbia_katalog.erkenne(document):
        return columbia_katalog.dates(document, language)
    treffer = DATUM.search(document.text)
    if not treffer:
        raise DocumentParseError(
            translate("errors.importer.invoice_date_missing_or_ambiguous", language)
        )
    tag = datetime.strptime("-".join(reversed(treffer.groups())), "%Y-%m-%d").date()
    return {"invoice_date": tag, "document_date": tag}
