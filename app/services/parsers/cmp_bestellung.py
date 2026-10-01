"""CMP-Bestellung aus dem Campagnolo-Portal (Punkt 7, 2026-10-01).

Zweites CMP-Layout neben `cmp.py`: eine Bestellung („Bestellung: 22065",
„Bestellt am: 15/08/2026"), als Bildschirmausdruck gespeichert. Die PDF-Seiten
sind Rasterbilder mit einer unbrauchbaren Textebene - dieses Modul liest sie
darum **selbst per OCR** (lokal, Tesseract, Regel 1; `app/services/ocr_raster.py`)
und nutzt die Textebene nur zur Erkennung des Layouts.

Aufbau je Artikel (ein Kasten):

    33N6677 : MAN T-SHIRT - [2026P] - 100%PL            ← Titel: Artikelnummer, Name
    Farbe | ... | 46 | 48 | 50 | 52 | 54 | 56 | 58 | Gesamtmenge | Gesamtmenge(CHF)
    91UR [2027P] ANTRACITE-SILVER          2   1       3      39,00   ← je Farbe eine Zeile
    P753 [2026P] CORDA                2  2  2  2       8     104,00
    Preise (CHF)                     13,00 13,00 ...                  ← EK je Grösse
    VK (CHF)                         29,90 29,90 ...                  ← VK (= UVP) je Grösse

Mengen und Preise gehören zu der Spalte, in der sie stehen. Gelesen wird nie
blind: jede Farbzeile wird gegengerechnet (Summe der Mengen = Gesamtmenge,
Mengen × EK = Betrag), am Ende die Seitensumme „Menge: 159 Produkte,
3 505,30 CHF". Stimmt etwas nicht, steht eine Warnung da und der Import ist
gesperrt - ein schlecht lesbares Layout wird gemeldet, nicht geraten.

Keine EAN (Regel 5: Hinweis). Einheit Stück. Typ: Bestellung - die Ware ist
erwartet, nicht gebucht (Regel 3).
"""

import re
from datetime import date
from decimal import Decimal
from functools import lru_cache

from .base import DocumentParseError, ergebnis, pruefe_position
from ...core.i18n import DEFAULT_LANGUAGE, translate

MARKE = "CMP"

BESTELLUNG = re.compile(r"Bestellung:\s*(\d{3,})")
DATUM = re.compile(r"Bestellt\s+am:?\s*(\d{2})/(\d{2})/(\d{4})")
SUMME = re.compile(r"Menge:\s*(\d+)\s+Produkte,\s*([\d\s.']+[,.]\d{2})\s*CHF")
SAISON = re.compile(r"\s+[-~–]\s+\[?\d{4}[A-Z]?[\]\)]?(?:\s+[-~–]\s+.*)?$")
SAISON_ZEILE = re.compile(r"^[\[\(]?\d{4}[A-Z]?[\]\)}]?$")
ARTIKELNR_MUSTER = re.compile(r"^\d{2}[A-Z]\d{4}[A-Z]?$")
PREIS = re.compile(r"^\d{1,3}(?:[ .']\d{3})*,\d{2}$|^\d+,\d{2}$")
GANZZAHL = re.compile(r"^\d{1,3}$")
SPALTE_BETRAG_X = 480  # „Gesamtmenge(CHF)" steht ganz rechts (Seitenvorlage des Portals)
SPALTENBREITE = 24.4
FARBE_X = (70, 100)  # Farbcode und -name stehen in dieser Spalte (links ein Vorschaubild)

# OCR-Verwechslungen, getrennt nach der Stelle, die Ziffer bzw. Buchstabe sein muss.
ZU_ZIFFER = {"S": "5", "O": "0", "I": "1", "L": "1", "B": "8", "Z": "2", "G": "6", "l": "1", "o": "0"}
# An der Buchstabenstelle der Artikelnummer (3. Zeichen) wird am häufigsten ein S als Ziffer gelesen.
ZU_BUCHSTABE = {"5": "S", "8": "S", "3": "S", "7": "T", "0": "O", "1": "I", "2": "Z", "6": "G"}


def artikelnummer(roh: str) -> str:
    """Artikelnummer nach dem festen Muster `99X9999` (+ optional ein Buchstabe)
    zurechtrücken: an Ziffernstellen steht nie S/O/I/B (OCR-Verwechslung)."""
    zeichen = list(roh.upper())
    for i, z in enumerate(zeichen[:7]):
        zeichen[i] = ZU_BUCHSTABE.get(z, z) if i == 2 else ZU_ZIFFER.get(z, z)
    return "".join(zeichen)


def sauber(text: str) -> str:
    """Zahl-Wort ohne Rahmenreste: die OCR hängt Tabellenlinien als `!`, `|` oder
    Klammern an („34,75!", „(34,75")."""
    return text.strip("|!()[]{}‘’“”\"' ")


FARBCODE_A = re.compile(r"^\d{2}[A-Z]{2}$")  # 91UR, 24UV, 38ZV
FARBCODE_B = re.compile(r"^[A-Z]\d{3}$")  # P753, N950, U887
ZIFFER_ZU_BUCHSTABE = {"2": "Z", "0": "O", "1": "I", "5": "S", "8": "B", "6": "G", "7": "T"}


def farbcode(roh: str) -> tuple[str | None, bool]:
    """Farbcode nach dem Muster `99XX` oder `X999`; die OCR-Verwechslungen
    Ziffer↔Buchstabe werden korrigiert (zweiter Wert: wurde etwas geändert).
    Passt keines der Muster, ist der Code unsicher (`None`)."""
    roh = roh.upper()
    if len(roh) in (5, 6):
        # Rest eines Vorschaubilds oder einer Linie vor/in dem Code: genau ein
        # weggelassenes Zeichen, das ein gültiges Muster ergibt, zählt.
        passend = {roh[:i] + roh[i + 1 :] for i in range(len(roh))}
        passend = {c for c in passend if len(c) == 4 and (FARBCODE_A.fullmatch(c) or FARBCODE_B.fullmatch(c))}
        if len(passend) == 1:
            return passend.pop(), True
        return None, False
    if len(roh) != 4:
        return None, False
    a = "".join([ZU_ZIFFER.get(roh[0], roh[0]), ZU_ZIFFER.get(roh[1], roh[1]), ZIFFER_ZU_BUCHSTABE.get(roh[2], roh[2]), ZIFFER_ZU_BUCHSTABE.get(roh[3], roh[3])])
    b = "".join([ZIFFER_ZU_BUCHSTABE.get(roh[0], roh[0]), ZU_ZIFFER.get(roh[1], roh[1]), ZU_ZIFFER.get(roh[2], roh[2]), ZU_ZIFFER.get(roh[3], roh[3])])
    kandidaten = [c for c, muster in ((a, FARBCODE_A), (b, FARBCODE_B)) if muster.fullmatch(c)]
    if roh in kandidaten:
        return roh, False
    if len(kandidaten) == 1:
        return kandidaten[0], True
    return None, False


def zahl(text: str) -> Decimal:
    return Decimal(re.sub(r"[\s.']", "", text).replace(",", "."))


def _zeilen(woerter, toleranz=4):
    """Wörter zu Zeilen (y-Abstand ≤ Toleranz), jede links→rechts."""
    ergebnis_ = []
    for w in sorted(woerter, key=lambda w: (w[1], w[0])):
        if not ergebnis_ or abs(ergebnis_[-1][0][1] - w[1]) > toleranz:
            ergebnis_.append([])
        ergebnis_[-1].append(w)
    return [sorted(z, key=lambda w: w[0]) for z in ergebnis_]


def _mitte(w) -> float:
    return (w[0] + w[2]) / 2


def _spalte(wort, spalten):
    """Grösse der Spalte `(x_mitte, Grösse)`, in der das Wort steht. Mengen stehen
    rechtsbündig, Preise zentriert: eine Menge liegt bis etwa 12 pt rechts der
    Spaltenmitte."""
    for cx, groesse in spalten:
        if cx - SPALTENBREITE / 2 - 1 <= _mitte(wort) <= cx + SPALTENBREITE / 2 + 2:
            return groesse
    return None


def _zerlegt(woerter):
    """Wörter, in denen die OCR mehrere Zahlen mit `|` verklebt hat („34,75|34,75"),
    in einzelne Wörter mit anteiligen Koordinaten teilen; Reste (`!`, Klammern) weg."""
    erg = []
    for w in woerter:
        teile = [t for t in re.split(r"\|", w[4]) if t]
        breite = (w[2] - w[0]) / max(len(w[4]), 1)
        pos = 0
        for t in teile:
            start = w[4].index(t, pos)
            pos = start + len(t)
            erg.append((w[0] + start * breite, w[1], w[0] + pos * breite, w[3], sauber(t), *w[5:]))
    return erg


def preisspalten(preis_woerter) -> list[float]:
    """x-Mitten der Preisspalten aus der „Preise (CHF)"-Zeile: jede Grösse mit
    Preis ist eine Spalte."""
    return sorted(_mitte(w) for w in _zerlegt(preis_woerter) if PREIS.fullmatch(w[4]) and w[0] < SPALTE_BETRAG_X)


def titel_lesen(woerter) -> dict | None:
    """`{"code", "bezeichnung", "korrigiert"}` aus der Titelzeile „99X9999 : Name - [Saison] - Material".
    Von der Artikelnummer zählt das Muster; die OCR-Verwechslung S↔Ziffer an der
    Buchstabenstelle wird korrigiert (`korrigiert`: Hinweis für den Benutzer)."""
    for zeile in _zeilen(woerter, toleranz=7):
        for i, w in enumerate(zeile):
            roh = re.sub(r"[:;]$", "", w[4]).upper()
            nach = zeile[i + 1][4] if i + 1 < len(zeile) else ""
            if not re.fullmatch(r"[0-9A-Z]{7,8}", roh) or not (w[4][-1] in ":;" or nach in (":", ";")):
                continue
            code = artikelnummer(roh)
            if not ARTIKELNR_MUSTER.fullmatch(code):
                continue
            rest = " ".join(x[4] for x in zeile[i + 1 :]).lstrip(":; ")
            return dict(code=code, korrigiert=code != roh, bezeichnung=SAISON.sub("", rest).strip(" -"))
    return None


def _preise(texte, spalten) -> dict:
    """Preis je Grösse aus den je Spalte gelesenen Zellen („34.75" oder None)."""
    return {g: t for (_, g), t in zip(spalten, texte) if t is not None}


def _farbzeile(zeile: dict, spalten) -> dict:
    """Farbcode und Farbname (aus den Wörtern der Farbzelle), Mengen je Grösse,
    Gesamtmenge und Betrag (je Zelle einzeln gelesen) einer Zeile."""
    woerter = _zerlegt(zeile["farbe"])
    # Der Farbcode ist das erste Wort der Zelle (sonst die Saison „[2026P]" und der Name).
    kopf = sorted(woerter, key=lambda w: (w[1], w[0]))[:1]
    code = kopf[0] if kopf else None
    name = ""
    for z in _zeilen(woerter):
        text = re.sub(r"^[^\w\[(]+", "", " ".join(w[4] for w in z if w is not code))  # Reste vom Vorschaubild/Rahmen
        if not text or SAISON_ZEILE.fullmatch(text):
            continue
        name = name + text if name.endswith("-") else (name + " " + text).strip()
    mengen = {}
    for (_, groesse), text in zip(spalten, zeile["mengen"]):
        if text is not None and text.isdigit():
            mengen[groesse] = int(text)
    gesamt = int(zeile["gesamt"]) if zeile["gesamt"] and zeile["gesamt"].isdigit() else None
    # Der Betrag kommt als Ziffern ohne Komma (immer zwei Rappen): „3900" = 39,00.
    betrag = Decimal(int(zeile["betrag"])) / 100 if zeile["betrag"] and zeile["betrag"].isdigit() else None
    korrigiert, geaendert = farbcode(code[4]) if code else (None, False)
    return dict(
        code=korrigiert or (code[4].upper() if code else None),
        geaendert=geaendert,
        unsicher=None if korrigiert or code is None else code[4],
        name=name, mengen=mengen, gesamt=gesamt, betrag=betrag,
    )


def baue_positionen(kaesten: list[dict], language: str = DEFAULT_LANGUAGE) -> tuple[list, list, tuple[int, Decimal]]:
    """Positionen aus den gelesenen Kästen (`ocr_raster.lies_bestellung`).

    Rein rechnerisch, ohne OCR - damit testbar. Gibt `(items, warnings,
    (Stück, Betrag))` zurück; die Summe ist, was die Positionen ergeben, für den
    Vergleich mit der Seitensumme."""
    items, warnings = [], []
    gesamt_stueck, gesamt_betrag = 0, Decimal("0")
    for kasten in kaesten:
        titel = titel_lesen(kasten["titel"])
        spalten = kasten["columns"]
        if titel is None:
            warnings.append(translate("errors.parser.unassigned_row", language, page=kasten["page"], row_text="?"))
            continue
        if not spalten or any(g is None for _, g in spalten):
            warnings.append(translate("errors.parser.invalid_value", language, field=translate("fields.size", language), value=titel["code"]))
            continue
        ek, vk = _preise(kasten["ek"], spalten), _preise(kasten["vk"], spalten)
        for zeile in kasten["zeilen"]:
            farbe = _farbzeile(zeile, spalten)
            if farbe["code"] is None:
                warnings.append(translate("errors.parser.unassigned_row", language, page=kasten["page"], row_text=titel["code"]))
                continue
            mengen = {g: m for g, m in farbe["mengen"].items() if m}
            ist = sum(mengen.values())
            erwartet_betrag = sum((Decimal(ek[g]) * m for g, m in mengen.items() if g in ek), Decimal("0"))
            warnung = []
            if farbe["gesamt"] is not None and farbe["gesamt"] != ist:
                warnung.append(translate("errors.parser.total_mismatch", language, summe=ist, beleg=farbe["gesamt"]))
            if farbe["unsicher"]:
                warnung.append(translate("errors.parser.invalid_value", language, field=translate("fields.article_no", language), value=farbe["unsicher"]))
            if any(g not in ek or g not in vk for g in mengen):
                warnung.append(translate("errors.parser.invalid_value", language, field=translate("fields.uvp", language), value="-"))
            elif farbe["betrag"] != erwartet_betrag:
                warnung.append(
                    translate(
                        "errors.parser.total_mismatch", language,
                        summe=format(erwartet_betrag, "f"), beleg=farbe["betrag"] if farbe["betrag"] is not None else "-",
                    )
                )
            for groesse, menge in mengen.items():
                gesamt_stueck += menge
                gesamt_betrag += Decimal(ek[groesse]) * menge if groesse in ek else 0
                position = dict(
                    brand=MARKE,
                    supplier_article_no=titel["code"],
                    article_no=f"{titel['code']} {farbe['code']}",
                    description=titel["bezeichnung"],
                    color=farbe["name"] or None,
                    size=groesse,
                    quantity=str(menge),
                    unit="Stk",
                    uvp=vk.get(groesse, ""),
                    ek=ek.get(groesse, ""),
                    page=kasten["page"],
                    # Gelesene Zeile für die Prüfung in der Vorschau (Originaltext je Position).
                    raw_lines=[
                        f"{titel['code']} {farbe['code']} {farbe['name']} | Grösse {groesse}: {menge} | "
                        f"EK {ek.get(groesse, '?')} VK {vk.get(groesse, '?')} | Zeile gesamt {farbe['gesamt']} / {farbe['betrag']}"
                    ],
                    warnings=list(warnung),
                )
                position = pruefe_position(position, language)
                if titel["korrigiert"] or farbe["geaendert"]:
                    position["hints"].append(translate("errors.parser.article_no_corrected", language, nr=position["article_no"]))
                items.append(position)
    return items, warnings, (gesamt_stueck, gesamt_betrag)


@lru_cache(maxsize=2)
def _gelesen(pdf_data: bytes, language: str) -> dict:
    """Einmal OCR je PDF - `parse` und `dates` brauchen beide den gelesenen Text
    (die Textebene der PDF ist falsch, z. B. „22055" statt „22065")."""
    from ..ocr_raster import lies_bestellung

    return lies_bestellung(pdf_data, language, preisspalten)


def _gelesen_von(document, language: str) -> dict:
    if getattr(document, "pdf_data", None) is None:
        raise DocumentParseError(translate("errors.ocr.unavailable", language))
    return _gelesen(document.pdf_data, language)


def parse(document, language: str = DEFAULT_LANGUAGE) -> dict:
    gelesen = _gelesen_von(document, language)
    items, warnings, (stueck, betrag) = baue_positionen(gelesen["kaesten"], language)
    summe = SUMME.search(gelesen["fuss_text"])
    if summe is None:
        warnings.append(translate("errors.parser.total_mismatch", language, summe=stueck, beleg="-"))
    else:
        soll_stueck, soll_betrag = int(summe.group(1)), zahl(summe.group(2).replace(".", ","))
        if soll_stueck != stueck or soll_betrag != betrag:
            warnings.append(
                translate("errors.parser.total_mismatch", language, summe=f"{stueck} / {betrag}", beleg=f"{soll_stueck} / {soll_betrag}")
            )
    nummer = BESTELLUNG.search(gelesen["kopf_text"])
    return ergebnis(document, items, warnings, "bestellung", nummer.group(1) if nummer else None, language)


def dates(document, language: str = DEFAULT_LANGUAGE) -> dict:
    kopf = DATUM.search(_gelesen_von(document, language)["kopf_text"])
    if not kopf:
        raise DocumentParseError(translate("errors.importer.invoice_date_missing_or_ambiguous", language))
    tag = date(int(kopf[3]), int(kopf[2]), int(kopf[1]))
    return {"invoice_date": tag, "document_date": tag}
