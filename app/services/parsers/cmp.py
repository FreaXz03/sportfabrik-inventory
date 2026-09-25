"""CMP-Layout (Auftragsbestätigungen von F.lli Campagnolo S.p.A., Phase E).

Die Positionen stehen als **Grössenraster**: je Artikel und Farbe ein Block

    92  98  104  110  116  ...                       ← Grössen
    30A1494 KID LONG PANT  09EZ (1) OLIVE ANTRACITE  von 01/09/2026   4  4  4 ...
    96% PL 4% EA                                     bis 15/09/2026
                                   31,75 31,75 31,75 ...   44        ← EK je Grösse, Blocksumme
                                   69,90 69,90 69,90 ...             ← VK (= UVP) je Grösse

Mengen und Preise stehen rechtsbündig unter ihrer Grösse; zugeordnet wird
darum über den rechten Rand. Die Spalten liegen je Beleg etwas anders, der
Parser misst deshalb alles relativ zu den erkannten Zeilen. Ein Block ohne
Artikelnummer gehört zum Artikel darüber (weitere Farbe). „STORNIERT"e Blöcke
werden übersprungen. Jede Blocksumme wird gegengerechnet - fehlt eine Menge,
sperrt eine Warnung den Import.

Keine EAN (Regel 5: Hinweis). Einheit Stück.
"""

import re
from datetime import date

from .base import Document, DocumentParseError, ergebnis, pruefe_position
from .base import lines as _zeilen
from ...core.i18n import DEFAULT_LANGUAGE, translate

KEY = "cmp"
LIEFERANT_NAME = "CMP (F.lli Campagnolo S.p.A.)"
MARKE = "CMP"

NUMMER = re.compile(r"Auftragsbestätigung\s+(\S+)\s+von\s+(\d{2})/(\d{2})/(\d{4})")
FARB_NR = re.compile(r"^\(\d+\)$")
GROESSE = re.compile(r"^(?:[A-Z]{0,2}\d{1,3}|X{0,3}[SML]|\d?XL|XXS)$")
PREIS = re.compile(r"^\d+,\d{2}$")
GANZZAHL = re.compile(r"^\d+$")
ARTIKELNR = re.compile(r"^(?=.*\d)[0-9A-Z]{7,8}$")
TOLERANZ = 8  # Punkte zwischen rechtem Rand von Grösse und Wert


def detect(document: Document) -> int | None:
    text = document.text
    if "Campagnolo" not in text or "Farb-Beschreibung" not in text:
        return None
    return 4


def _groessenzeile(zeile) -> bool:
    return len(zeile) >= 3 and all(GROESSE.fullmatch(w[4]) for w in zeile)


def _zu_groesse(wort, groessen):
    """Grösse, unter der dieser Wert rechtsbündig steht (oder None)."""
    abstand, groesse = min((abs(wort[2] - g[2]), g[4]) for g in groessen)
    return groesse if abstand <= TOLERANZ else None


def parse(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    items, warnings = [], []
    kopf = NUMMER.search(document.text)
    groessen = None
    artikel = None
    block = None
    bloecke = []
    for page in document.pages:
        for zeile in _zeilen(page.words):
            if _groessenzeile(zeile):
                groessen = zeile
                continue
            marke_index = next((i for i, w in enumerate(zeile) if FARB_NR.fullmatch(w[4])), None)
            if marke_index is not None and groessen is not None:
                worte = [w[4] for w in zeile]
                farbcode = worte[marke_index - 1] if marke_index else ""
                links = worte[: max(marke_index - 1, 0)]
                if links and ARTIKELNR.fullmatch(links[0]):
                    artikel = dict(code=links[0], bezeichnung=" ".join(links[1:]))
                ende = next((i for i, w in enumerate(worte) if w in ("von", "STORNIERT")), len(worte))
                storniert = "STORNIERT" in worte
                datum_x = next((w[2] for w in zeile if re.fullmatch(r"\d{2}/\d{2}/\d{4}", w[4])), None)
                mengen = [w for w in zeile if datum_x and w[0] > datum_x and GANZZAHL.fullmatch(w[4])]
                block = dict(
                    artikel=artikel,
                    farbcode=farbcode,
                    farbe=" ".join(worte[marke_index + 1 : ende]),
                    groessen=groessen,
                    mengen=mengen,
                    preise=[],
                    summe=None,
                    storniert=storniert,
                    page=page.number,
                )
                bloecke.append(block)
                continue
            if block is None:
                continue
            rechts = max(g[2] for g in block["groessen"])
            preise = [w for w in zeile if PREIS.fullmatch(w[4]) and w[2] <= rechts + TOLERANZ]
            if preise and "bis" not in {w[4] for w in zeile} and len(block["preise"]) < 2:
                block["preise"].append(preise)
            # Blocksumme: ganze Zahl rechts vom Raster - aber nicht der
            # Tausender-Teil eines Betrags wie „1 397,00" (Nachbar dicht daneben).
            summe = [
                w
                for w in zeile
                if GANZZAHL.fullmatch(w[4])
                and rechts + 5 < w[0] < rechts + 60
                and not any(0 <= v[0] - w[2] < 6 for v in zeile if v is not w)
            ]
            if summe and block["summe"] is None and "bis" not in {w[4] for w in zeile}:
                block["summe"] = summe[0][4]

    for block in bloecke:
        if block["storniert"]:
            continue
        artikel = block["artikel"] or {}
        warnung = []
        if len(block["preise"]) != 2:
            warnung.append(translate("errors.parser.invalid_value", language, field=translate("fields.uvp", language), value="-"))
        ek = {_zu_groesse(w, block["groessen"]): w[4] for w in (block["preise"] or [[]])[0]}
        vk = {_zu_groesse(w, block["groessen"]): w[4] for w in (block["preise"][1] if len(block["preise"]) > 1 else [])}
        positionen = []
        for wort in block["mengen"]:
            groesse = _zu_groesse(wort, block["groessen"])
            if groesse is None:
                warnung.append(translate("errors.parser.unassigned_row", language, page=block["page"], row_text=wort[4]))
                continue
            if wort[4] == "0":
                continue
            positionen.append(
                dict(
                    brand=MARKE,
                    supplier_article_no=artikel.get("code", ""),
                    article_no=f"{artikel.get('code', '')} {block['farbcode']}".strip(),
                    description=artikel.get("bezeichnung", ""),
                    color=block["farbe"] or None,
                    size=groesse,
                    quantity=wort[4],
                    unit="Stk",
                    uvp=vk.get(groesse, ""),
                    ek=ek.get(groesse, ""),
                    page=block["page"],
                )
            )
        ist = sum(int(p["quantity"]) for p in positionen)
        if block["summe"] is None or int(block["summe"]) != ist:
            warnung.append(
                translate("errors.parser.total_mismatch", language, summe=ist, beleg=block["summe"] or "-")
            )
        for position in positionen:
            position["warnings"] = list(warnung)
            items.append(pruefe_position(position, language))
    return ergebnis(
        document,
        items,
        warnings,
        "auftragsbestaetigung" if kopf else None,
        kopf[1] if kopf else None,
        language,
    )


def dates(document: Document, language: str = DEFAULT_LANGUAGE) -> dict:
    kopf = NUMMER.search(document.text)
    if not kopf:
        raise DocumentParseError(translate("errors.importer.invoice_date_missing_or_ambiguous", language))
    tag = date(int(kopf[4]), int(kopf[3]), int(kopf[2]))
    return {"invoice_date": tag, "document_date": tag}
