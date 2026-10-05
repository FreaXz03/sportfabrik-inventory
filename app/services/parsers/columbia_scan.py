"""Gescannte Columbia-Linesheets: lokale Rasterlesung der kleinen Tabellen.

Die Ganzseiten-OCR verliert Rahmenzellen. Deshalb werden Grössen, Preise und
Farblegenden getrennt gelesen (wie bei CMP, ausschliesslich Tesseract).
Das bestätigte Scanraster hat drei Modellplätze je A4-Seite; Stilnummern
links sind die Anker. Andere Raster werden nicht durch Verschieben erraten.
Keine Bestellmengen, Zeilenbeträge oder Belegsummen: Menge 0 wie beim nativen
Katalog. Gegenprobe ist der Stilindex. OCR bleibt immer prüfpflichtig; auch
plausible Ziffern können falsch sein. Schuhgrössenbereiche werden ausdrücklich
nicht in erfundene Einzelgrössen oder EU-Grössen umgerechnet.
"""

import hashlib
import re
from datetime import date
from functools import lru_cache

import pymupdf

from . import columbia_katalog as katalog
from .base import DocumentParseError, ergebnis, joined, lines
from ...core.i18n import DEFAULT_LANGUAGE, translate

PREIS = re.compile(r"\d+[.,]\d{2}")
GROESSE = re.compile(r"XXXL|XXL|XXS|XS|XL|S|M|L|O/S|\d{1,3}(?:/\d{1,3})?")
BEREICH = re.compile(r"\d{1,2}-\d{1,2}")


def erkenne(document):
    text = document.text
    return document.ocr_used and "Columbia" in text and all(
        token in text for token in ("STYLE NUMBER INDEX", "MSRP", "BASE", "FEATURES")
    )


def groessen(text):
    """Nur vollständig lesbare Grössen; verklebte Buchstaben bleiben unsicher."""
    result, unsicher = [], False
    for token in text.split():
        if BEREICH.fullmatch(token):
            result.append(token)
            unsicher = True
            continue
        teile = GROESSE.findall(token)
        if not teile or "".join(teile) != token:
            return [], True
        # Zahlen nie aufteilen (z. B. 3032 ist kein belegtes Paar 30/32).
        if len(teile) > 1 and any(t[0].isdigit() for t in teile):
            return [], True
        result.extend(teile)
        unsicher |= len(teile) > 1
    if len(set(result)) != len(result) or len(result) > katalog.MAX_GROESSEN:
        return [], True
    return result, unsicher



def laengen(text):
    """Rückenlängen sind keine Varianten; explizite S/R/L-Inseams schon.
    Unlesbare bzw. numerische Längen werden nicht ergänzt oder umgerechnet."""
    if not text:
        return [], True
    if re.search(r"cm\b", text, re.IGNORECASE):
        return [], False
    teile = re.sub(r"^[A▲△]\s*", "", text).split()
    if teile and all(t in ("S", "R", "L") for t in teile) and len(set(teile)) == len(teile):
        return teile, False
    return [], True


def _preis(worte, label):
    marken = [w for w in worte if w[4] == label]
    if len(marken) != 1:
        return None
    marke = marken[0]
    kandidaten = [w[4] for w in worte if w[0] < marke[0] and abs(w[1] - marke[1]) < 3
                  and PREIS.fullmatch(w[4]) and w[5] >= 60]
    return kandidaten[0].replace(",", ".") if len(kandidaten) == 1 else None


def _farben(worte):
    codes = [w for w in worte if katalog.CODE.fullmatch(w[4]) and w[5] >= 60]
    if len(codes) > katalog.MAX_FARBEN:
        return []
    result = []
    for code in sorted(codes, key=lambda w: w[0]):
        rechts = min((w[0] - 2 for w in codes if w[0] > code[0] + 5), default=565)
        namen = [w for w in worte if code[0] - 2 <= w[0] < rechts
                 and code[1] + 3 <= w[1] <= code[1] + 13
                 and w[5] >= 45 and any(c.isalpha() for c in w[4])]
        name = " ".join(joined(zeile) for zeile in lines(namen))
        result.append((code[4], name))
    return result if len({c for c, _ in result}) == len(result) else []


@lru_cache(maxsize=2)
def _raster(pdf_data, spezifikation):
    """Ausschnitte einmal für parse/dates lesen; keine Datei wird geschrieben."""
    from ..ocr_raster import _ausschnitt

    bloecke, index, kopf = [], set(), ""
    index_unsicher = False
    with pymupdf.open(stream=pdf_data, filetype="pdf") as pdf:
        for nummer, art, anker in spezifikation:
            page = pdf[nummer - 1]
            if not (580 <= page.rect.width <= 610 and 820 <= page.rect.height <= 860) or page.rotation:
                bloecke.append(dict(stil="?", titel="", seite=nummer, fehler=True))
                continue
            if art == "kopf":
                kopf = " ".join(w[4] for w in _ausschnitt(page, 400, 120, 590, 340, dpi=400))
            elif art == "index":
                worte = _ausschnitt(page, 40, 90, 77, 740, dpi=400)
                index.update(w[4].rstrip(".,:") for w in worte
                             if re.fullmatch(r"\d{7}[.,:]*", w[4]))
                index_unsicher |= any(w[5] < 60 or not re.fullmatch(r"\d{7}[.,:]*", w[4])
                                      for w in worte if any(c.isdigit() for c in w[4]))
            elif art == "modell":
                for stil, y, titel in anker:
                    if not katalog.STIL.fullmatch(stil) or not 70 <= y <= 600:
                        bloecke.append(dict(stil=stil, titel=titel, seite=nummer, fehler=True))
                        continue
                    # Die Ganzseiten-OCR vereinigt manchmal Stilnummer und Bild
                    # zu einer hohen Textzeile. Die isolierte Nummer muss gleich
                    # lauten; nur ihre genaue y-Koordinate wird neu bestimmt.
                    nummern = _ausschnitt(page, 40, max(0, y - 3), 85, min(page.rect.height, y + 40), dpi=400)
                    genau = [w for w in nummern if w[4] == stil and w[5] >= 60]
                    if len(genau) != 1:
                        bloecke.append(dict(stil=stil, titel=titel, seite=nummer, fehler=True))
                        continue
                    y = genau[0][1]
                    # Der feste Tabellenabstand muss zum bekannten Scanraster passen.
                    if not any(abs(y - soll) < 12 for soll in (100, 330, 560)):
                        bloecke.append(dict(stil=stil, titel=titel, seite=nummer, fehler=True))
                        continue
                    preise = _ausschnitt(page, 330, y + 125, 412, y + 163, dpi=400)
                    farben = _ausschnitt(page, 142, y + 110, 565, y + 133, psm=6, dpi=400)
                    # Grössen sitzen in der ersten Rahmenzelle. Die Nachbarzelle
                    # (Länge) bleibt separat; mehrere Längen sind prüfpflichtig.
                    sizes = _ausschnitt(page, 145, y + 135, 240, y + 153, dpi=400)
                    size_text = " ".join(w[4] for w in sizes if any(c.isalnum() for c in w[4]))
                    gs, unsicher = groessen(size_text)
                    laengen_worte = _ausschnitt(page, 246, y + 135, 327, y + 153, dpi=400)
                    laengen_text = " ".join(w[4] for w in laengen_worte if any(c.isalnum() for c in w[4]))
                    ls, laengen_unsicher = laengen(laengen_text)
                    unsicher |= laengen_unsicher
                    bloecke.append(dict(
                        stil=stil, titel=titel, seite=nummer, farben=_farben(farben),
                        groessen=gs, laengen=ls, uvp=_preis(preise, "MSRP"), ek=_preis(preise, "BASE"),
                        unsicher=unsicher, roh=[titel, stil, size_text, laengen_text, " ".join(w[4] for w in preise),
                                                 " ".join(w[4] for w in farben)],
                    ))
    return dict(bloecke=bloecke, index=index, kopf=kopf, index_unsicher=index_unsicher)


def lesen(document, language):
    if document.pdf_data is None:
        raise DocumentParseError(translate("errors.ocr.unavailable", language))
    spezifikation = [(1, "kopf", ())]
    for page in document.pages[1:]:
        if "STYLE NUMBER INDEX" in page.text:
            spezifikation.append((page.number, "index", ()))
            continue
        if "STYLE NAME INDEX" in page.text or "FEATURES" not in page.text and "FABRICS" not in page.text:
            continue
        anker = sorted((w for w in page.words if katalog.STIL.fullmatch(w[4]) and 30 <= w[0] <= 80), key=lambda w: w[1])
        if len(anker) > 3 or len(page.words) > katalog.MAX_WORTE_JE_SEITE:
            anker = []
        specs = tuple((w[4], w[1], katalog._titel(page.words, w[1] - 35, w[1] - 3)) for w in anker)
        spezifikation.append((page.number, "modell", specs or (("?", -100, ""),)))
    return _raster(document.pdf_data, tuple(spezifikation))


def auswerten(document, gelesen, language):
    items, warnings, vollstaendig = [], [translate("errors.parser.columbia_scan_review", language)], set()
    for block in gelesen["bloecke"]:
        if block.get("fehler") or not block["farben"] or not block["groessen"] or not block["titel"]:
            warnings.append(translate("errors.parser.unassigned_row", language, page=block["seite"],
                                      row_text=f"{block['stil']} {block['titel']}"))
            continue
        neue = katalog._positionen(block, language)
        for item in neue:
            if block.get("unsicher") or not block["ek"] or not item["color"]:
                item["warnings"].append(translate("errors.parser.columbia_scan_row", language))
        items.extend(neue)
        vollstaendig.add(block["stil"])
        if len(items) > katalog.MAX_POSITIONEN:
            raise DocumentParseError(translate("errors.parser.no_positions_detected", language))
    index = gelesen["index"]
    if not index or index != vollstaendig or gelesen.get("index_unsicher"):
        warnings.append(translate("errors.parser.columbia_scan_index", language,
                                  missing=", ".join(sorted(index - vollstaendig)) or "-",
                                  extra=", ".join(sorted(vollstaendig - index)) or "-"))
    # Hash des Belegs, nicht bloss der zufällig erfolgreich gelesenen Positionen.
    inhalt = document.pdf_data or document.text.encode()
    nummer = "COLUMBIA-SCAN-" + hashlib.sha256(inhalt).hexdigest()[:16].upper()
    return ergebnis(document, items, warnings, "bestellung", nummer, language)


def parse(document, language=DEFAULT_LANGUAGE):
    return auswerten(document, lesen(document, language), language)


def dates(document, language=DEFAULT_LANGUAGE):
    match = katalog.ERSTELLT.search(lesen(document, language)["kopf"])
    try:
        if match is None:
            raise ValueError
        monat, tag, jahr = map(int, match.groups())
        datum = date(jahr, monat, tag)
    except ValueError as exc:
        raise DocumentParseError(translate("errors.importer.invoice_date_missing_or_ambiguous", language)) from exc
    return {"invoice_date": datum, "document_date": datum}
