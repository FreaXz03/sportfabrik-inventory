"""Tabellenseiten lesen, deren Textebene unbrauchbar ist (Rasterausdruck mit
schlechter Fremd-OCR) - lokal mit Tesseract (Regel 1), nur auf Anforderung
eines Parsers (`parsers/cmp_bestellung.py`).

Anders als `ocr.ocr_page` (Rückfall für Seiten ganz ohne Text) liest dieses
Modul **nicht die ganze Seite auf einmal**: Auf farbigen Zeilen (grün, blau,
gelb) verliert Tesseract im Gesamtbild Ziffern. Stattdessen wird die Struktur
aus den Hintergrundfarben gefunden und jede Zeile für sich gelesen:

    blauer Kopf → weisse/grüne Zeilen im Wechsel → hellblaue Preiszeile → gelbe VK-Zeile

Titel (Zeile über dem Kopf), Zeilen, Preiszeile und VK-Zeile werden als eigene
Ausschnitte gelesen. Die Grössen im blauen Kopf (dunkle Schrift auf Blau) werden
je Spalte mehrfach gelesen und müssen eine Zahlenfolge ergeben.
"""

import pymupdf

from decimal import Decimal

from ..core.i18n import DEFAULT_LANGUAGE, translate
from . import ocr

try:
    from PIL import Image, ImageChops, ImageOps
except ImportError:  # pragma: no cover
    Image = None

TEXT_DPI = 300
ZELLEN_DPI = 400
BILD_DPI = 100  # für das Finden der Zeilen aus den Hintergrundfarben
PROBE_X = (445, 500)  # Punkte: Bereich zwischen „Gesamtmenge" und „Gesamtmenge(CHF)", meist leer
RAND_X = (45, 545)  # Tabellenbreite in Punkten

# Mehrere Aufbereitungen je Kopfzelle, jede liest etwas anders; gezählt wird nachher.
VARIANTEN = ((0.62, 7), (0.72, 7), (0.72, 8), (0.82, 8))


def _klasse(r: int, g: int, b: int) -> str:
    """Hintergrundart einer Pixelzeile (Median über den Probebereich)."""
    if b - r > 90 and b > 140:
        return "kopf"
    if g - r > 20 and g - b > 25:
        return "gruen"
    if r > 235 and g > 235 and b < r - 35:
        return "gelb"
    if r < 238 and b > 235 and g > 235 and b - r > 15:
        return "preis"
    if r > 240 and g > 240 and b > 240:
        return "weiss"
    return "?"


def _median(werte):
    werte = sorted(werte)
    return werte[len(werte) // 2]


def zeilenstruktur(seite) -> list[dict]:
    """Zusammenhängende Hintergrundstreifen der Seite: `{"art", "y0", "y1"}` in
    Punkten (kopf/gruen/weiss/preis/gelb), unklare Pixelzeilen übernehmen die
    Art der vorigen. Aufeinanderfolgende gleichfarbige werden zusammengefasst."""
    pix = seite.get_pixmap(dpi=BILD_DPI, colorspace=pymupdf.csRGB)
    skala = 72 / BILD_DPI
    xs = range(int(PROBE_X[0] / skala), min(int(PROBE_X[1] / skala), pix.width))
    arten = []
    for y in range(pix.height):
        pixel = [pix.pixel(x, y) for x in xs]
        arten.append(_klasse(*(_median(p[i] for p in pixel) for i in range(3))))
    vorige = "weiss"
    for i, art in enumerate(arten):
        if art == "?":
            arten[i] = vorige
        else:
            vorige = art
    streifen = []
    for y, art in enumerate(arten):
        if streifen and streifen[-1]["art"] == art:
            streifen[-1]["y1"] = (y + 1) * skala
        else:
            streifen.append({"art": art, "y0": y * skala, "y1": (y + 1) * skala})
    return streifen


def kaesten(streifen) -> list[dict]:
    """Artikelkästen aus den Streifen: Kopf, dann Zeilen (weiss/grün im Wechsel),
    dann Preiszeile (hellblau) und VK-Zeile (gelb). Zu kurze Streifen (Rahmen,
    Linien) zählen nicht."""
    ergebnis, aktuell = [], None
    for s in streifen:
        hoehe = s["y1"] - s["y0"]
        if s["art"] == "kopf" and hoehe >= 8:
            aktuell = {"kopf": s, "zeilen": [], "preis": None, "vk": None}
            ergebnis.append(aktuell)
        elif aktuell is None or hoehe < 6:
            continue
        elif s["art"] in ("weiss", "gruen") and aktuell["preis"] is None:
            aktuell["zeilen"].append(s)
        elif s["art"] == "preis" and aktuell["preis"] is None:
            aktuell["preis"] = s
        elif s["art"] == "gelb" and aktuell["vk"] is None:
            aktuell["vk"] = s
    return [k for k in ergebnis if k["preis"] is not None and k["vk"] is not None]


def _ausschnitt(seite, x0, y0, x1, y1, psm=6, dpi=TEXT_DPI) -> list[tuple]:
    """Wörter eines Ausschnitts (Punkte, absolute Seitenkoordinaten); die
    Sicherheit von Tesseract steht an Stelle 5 des Tupels."""
    clip = pymupdf.Rect(x0, y0, x1, y1)
    pix = seite.get_pixmap(dpi=dpi, clip=clip, colorspace=pymupdf.csGRAY)
    bild = ImageOps.autocontrast(Image.frombytes("L", (pix.width, pix.height), pix.samples), cutoff=1)
    daten = ocr.pytesseract.image_to_data(bild, output_type=ocr.Output.DICT, config=f"--psm {psm}")
    skala = 72 / dpi
    erg = []
    for i, text in enumerate(daten["text"]):
        if text.strip():
            x, y = clip.x0 + daten["left"][i] * skala, clip.y0 + daten["top"][i] * skala
            erg.append((x, y, x + daten["width"][i] * skala, y + daten["height"][i] * skala, text.strip(), float(daten["conf"][i]), 0, 0))
    return erg


FARBZELLE_X = (76, 200)  # Farbcode, Saison, Farbname; links davon steht ein Vorschaubild


GESAMT_X = (430, 478)  # Spalte „Gesamtmenge" (Seitenvorlage des Portals)
BETRAG_X = (485, 545)  # Spalte „Gesamtmenge(CHF)"
ZIEL_HOEHE = 50  # Pixel Schrifthöhe, auf die jede Zelle vor dem Lesen gebracht wird
TINTE_MIN = 8  # so viele dunkle Pixel (bei 300 dpi) braucht eine Zelle, um nicht leer zu sein
TINTE_ANTEIL = 0.75  # dunkler als dieser Anteil des Zellhintergrunds = Schrift


def _zellbinaer(seite, x0, y0, x1, y1, rand=None, anteil=None, eng=False):
    """Zelle als Schwarzweissbild (Schrift schwarz), oder `None`, wenn sie leer ist.
    Schwarzweiss gegen den Zellhintergrund (nicht „Kontrast strecken"): so
    verschwinden die hellgrauen Tabellenlinien, die sonst als `1`/`4` gelesen
    werden. Farbige Schrift (hellblau auf grün) zeigt sich im dunkelsten
    Farbkanal am stärksten."""
    # Oben und unten Rand lassen: dort bleiben Reste der Zeilenlinie, die als Strich an der Ziffer hängen.
    rand = min(4.0, (y1 - y0) * 0.2) if rand is None else rand
    pix = seite.get_pixmap(dpi=300, clip=pymupdf.Rect(x0, y0 + rand, x1, y1 - rand), colorspace=pymupdf.csRGB)
    r, g, b = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).split()
    bild = ImageChops.darker(ImageChops.darker(r, g), b)
    anteil = TINTE_ANTEIL if anteil is None else anteil
    werte = list(bild.get_flattened_data())
    hintergrund = _median(werte)
    if sum(1 for v in werte if v < hintergrund * anteil) < TINTE_MIN:
        return None
    bild = _ohne_duenne_striche(_ohne_linien(bild.point(lambda v: 0 if v < hintergrund * anteil else 255)))
    if eng:
        return _eng(bild)
    return bild.resize((bild.width * 2, bild.height * 2))


def _ohne_duenne_striche(bild, max_dicke=2, min_laenge=6):
    """Waagrechte Striche von höchstens `max_dicke` Pixeln Dicke weiss machen: Reste
    der Zeilenlinie, die unten an einer Ziffer hängen. Ziffernstriche sind dicker."""
    b, h = bild.size
    px = bild.load()
    zu_loeschen = []
    for y in range(h):
        x = 0
        while x < b:
            if px[x, y] != 0:
                x += 1
                continue
            start = x
            while x < b and px[x, y] == 0:
                x += 1
            if x - start < min_laenge:
                continue
            # Dicke an der dicksten Stelle des Laufs: schwarze Pixel übereinander.
            dicke = 0
            for xx in range(start, x):
                oben = y
                while oben > 0 and px[xx, oben - 1] == 0:
                    oben -= 1
                unten = y
                while unten < h - 1 and px[xx, unten + 1] == 0:
                    unten += 1
                dicke = max(dicke, unten - oben + 1)
            if dicke <= max_dicke:
                zu_loeschen.append((start, x, y))
    for start, ende, y in zu_loeschen:
        for xx in range(start, ende):
            px[xx, y] = 255
    return bild


def _eng(bild):
    """Auf die Schrift zuschneiden und auf normale Textgrösse bringen: eine
    einzelne kleine Ziffer in einer grossen leeren Zelle liest Tesseract unzuverlässig."""
    kasten = ImageOps.invert(bild).getbbox()
    if kasten is None:
        return bild
    x0, y0, x1, y1 = kasten
    bild = bild.crop((max(x0 - 10, 0), max(y0 - 10, 0), min(x1 + 10, bild.width), min(y1 + 10, bild.height)))
    faktor = max(1.0, min(4.0, ZIEL_HOEHE / max(y1 - y0, 1)))
    return bild.resize((int(bild.width * faktor), int(bild.height * faktor)), Image.LANCZOS)


def _ohne_linien(bild, anteil=0.8):
    """Durchgehende senkrechte und waagrechte Striche (Tabellenrahmen am Zellrand)
    weiss machen - Ziffern füllen nie fast die ganze Zellhöhe bzw. -breite."""
    b, h = bild.size
    px = bild.load()
    for x in range(b):
        if sum(1 for y in range(h) if px[x, y] == 0) >= anteil * h:
            for y in range(h):
                px[x, y] = 255
    for y in range(h):
        if sum(1 for x in range(b) if px[x, y] == 0) >= anteil * b:
            for x in range(b):
                px[x, y] = 255
    return bild


def zahlen_lesen(seite, zellen, rand=None, psm=6, einzeln=False, anteil=None, eng=False) -> list[str | None]:
    """Mehrere Tabellenzellen `(x0, y0, x1, y1)` auf einmal lesen: leer → `None`,
    sonst die Ziffern. Die nicht leeren Zellen werden durch Weiss getrennt zu
    einer Reihe zusammengesetzt und mit einem einzigen Tesseract-Aufruf gelesen
    (eine Zelle allein liest Tesseract besser als eine ganze Zeile, ein Aufruf je
    Zelle wäre aber langsam). `einzeln=True` liest dennoch jede Zelle für sich -
    der langsamere zweite Versuch, wenn die Gegenrechnung nicht aufgeht."""
    luecke = 200
    bilder = [_zellbinaer(seite, *z, rand=rand, anteil=anteil, eng=eng) for z in zellen]
    belegt = [(i, b) for i, b in enumerate(bilder) if b is not None]
    ergebnis = [None] * len(zellen)
    if not belegt:
        return ergebnis
    konfig = f"-c tessedit_char_whitelist=0123456789"
    if einzeln:
        for i, b in belegt:
            gross = ImageOps.expand(b, border=40, fill=255)
            text = ocr.pytesseract.image_to_string(gross, config=f"--psm {psm} {konfig}").strip()
            ergebnis[i] = text or None
        return ergebnis
    breite = sum(b.width for _, b in belegt) + luecke * (len(belegt) + 1)
    reihe = Image.new("L", (breite, max(b.height for _, b in belegt) + 80), 255)
    grenzen, x = [], luecke
    for i, b in belegt:
        reihe.paste(b, (x, 40))
        grenzen.append((i, x, x + b.width))
        x += b.width + luecke
    daten = ocr.pytesseract.image_to_data(reihe, output_type=ocr.Output.DICT, config=f"--psm {psm} {konfig}")
    for k, text in enumerate(daten["text"]):
        text = text.strip()
        if not text.isdigit():
            continue
        mitte = daten["left"][k] + daten["width"][k] / 2
        for i, a, b in grenzen:
            if a - luecke / 2 <= mitte <= b + luecke / 2:
                ergebnis[i] = (ergebnis[i] or "") + text
                break
    return ergebnis


def _zahl_lesen(seite, x0, y0, x1, y1) -> str | None:
    return zahlen_lesen(seite, [(x0, y0, x1, y1)])[0]


def _preis_text(ziffern: str | None) -> str | None:
    """„3475" → „34.75": Preise haben immer zwei Rappen, das Komma geht beim Lesen verloren."""
    if not ziffern or not ziffern.isdigit() or len(ziffern) < 3:
        return None
    return f"{int(ziffern[:-2])}.{ziffern[-2:]}"


def spalten_erweitern(seite, streifen, zentren) -> list[float]:
    """Spaltenmitten um Spalten ergänzen, deren Preis in der Wortlesung fehlte:
    Von den gefundenen Spalten aus wird im Spaltenabstand nach links und rechts
    weitergegangen, solange die Preiszelle Schrift enthält."""
    if len(zentren) < 1:
        return zentren
    schritt = spaltenabstand(zentren)
    zentren = sorted(zentren)
    c = zentren[-1] + schritt
    while c + 12 < GESAMT_X[0] - 5 and zahlen_lesen(seite, [(c - 12, streifen["y0"], c + 12, streifen["y1"])], rand=1.0)[0]:
        zentren.append(c)
        c += schritt
    c = zentren[0] - schritt
    while c - 12 > 215 and zahlen_lesen(seite, [(c - 12, streifen["y0"], c + 12, streifen["y1"])], rand=1.0)[0]:
        zentren.insert(0, c)
        c -= schritt
    return zentren


# Weitere Leseversuche für eine Farbzeile, falls die Mengen nicht zur Gesamtmenge passen.
WIEDERHOLUNGEN = (
    dict(anteil=0.7),
    dict(anteil=0.8),
    dict(anteil=0.65),
    dict(einzeln=True, psm=10),
    dict(einzeln=True, psm=10, anteil=0.7),
    dict(einzeln=True, psm=10, anteil=0.85),
)


def _stimmt(mengen, gesamt) -> bool:
    """Die gelesenen Mengen ergeben die gelesene Gesamtmenge."""
    return (
        bool(gesamt)
        and gesamt.isdigit()
        and all(m is None or m.isdigit() for m in mengen)
        and sum(int(m) for m in mengen if m) == int(gesamt)
    )


def _betrag_stimmt(mengen, ek, betrag) -> bool:
    """Summe Menge × Einkaufspreis ergibt den gelesenen Zeilenbetrag („3900" = 39,00)."""
    if not betrag or not betrag.isdigit() or any(m and (not m.isdigit() or e is None) for m, e in zip(mengen, ek)):
        return False
    summe = sum((int(m) * Decimal(e) for m, e in zip(mengen, ek) if m), Decimal(0))
    return summe == Decimal(int(betrag)) / 100


def _zeile_lesen(seite, z, zentren, ek) -> dict:
    """Eine Farbzeile: die Farbzelle allein als Wörter (ohne das Vorschaubild links,
    sonst liest Tesseract Teile des Bilds als Text) für Code und Farbname, dazu
    jede Mengenzelle, die Gesamtmenge und den Betrag als Zahl.

    Zwei Gegenrechnungen: die Mengen müssen die Gesamtmenge ergeben, und Mengen ×
    Einkaufspreis den Betrag. Geht eine nicht auf, wird die betroffene Zahl mit
    anderen Einstellungen noch einmal gelesen, bis es aufgeht."""
    # Mengen stehen rechtsbündig in der Spalte: der Ausschnitt lässt beide Zellränder aus.
    zellen = [(cx - 5, z["y0"], cx + 11.5, z["y1"]) for cx in zentren]
    gesamt_zelle = (GESAMT_X[0], z["y0"], GESAMT_X[1], z["y1"])
    betrag_zelle = (BETRAG_X[0], z["y0"], BETRAG_X[1], z["y1"])
    gesamt, betrag = zahlen_lesen(seite, [gesamt_zelle, betrag_zelle])
    mengen = zahlen_lesen(seite, zellen, eng=True)
    if not (_stimmt(mengen, gesamt) or _betrag_stimmt(mengen, ek, betrag)):
        for versuch in WIEDERHOLUNGEN:
            neu = zahlen_lesen(seite, zellen, eng=True, **versuch)
            if _stimmt(neu, gesamt) or _betrag_stimmt(neu, ek, betrag):
                mengen = neu
                break
    # Mengen gesichert (ergeben Gesamtmenge): fehlt nur der Betrag, ihn anders lesen.
    if _stimmt(mengen, gesamt) and not _betrag_stimmt(mengen, ek, betrag):
        for anteil in (0.65, 0.85, 0.7, 0.8):
            neu = zahlen_lesen(seite, [betrag_zelle], anteil=anteil)[0]
            if _betrag_stimmt(mengen, ek, neu):
                betrag = neu
                break
    return {
        "farbe": _ausschnitt(seite, FARBZELLE_X[0], z["y0"], FARBZELLE_X[1], z["y1"]),
        "mengen": mengen,
        "gesamt": gesamt,
        # Nur Ziffern: das Komma geht beim Lesen verloren, es sind immer zwei Rappen.
        "betrag": betrag,
    }


# --- Grössen im blauen Kopf ------------------------------------------------


def _zellbild(seite, x0, y0, x1, y1, anteil):
    pix = seite.get_pixmap(dpi=ZELLEN_DPI, clip=pymupdf.Rect(x0, y0 + 1, x1, y1 - 1), colorspace=pymupdf.csGRAY)
    bild = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    hintergrund = _median(list(bild.get_flattened_data()))  # das Blau der Zelle
    return bild.point(lambda v: 0 if v < hintergrund * anteil else 255)


def kandidaten_je_spalte(seite, y0, y1, zentren) -> list[list[int]]:
    """Mögliche Zahlen je Spalte: die Kopfzellen werden schwarzweiss gemacht, in
    einer Reihe (durch Weiss getrennt) zusammengesetzt und mehrfach gelesen."""
    ergebnis = [[] for _ in zentren]
    for anteil, psm in VARIANTEN:
        zellen = [_zellbild(seite, cx - 10, y0, cx + 10, y1, anteil) for cx in zentren]
        luecke = 90
        breite = sum(z.width for z in zellen) + luecke * (len(zellen) + 1)
        reihe = Image.new("L", (breite, max(z.height for z in zellen) + 80), 255)
        grenzen, x = [], luecke
        for z in zellen:
            reihe.paste(z, (x, 40))
            grenzen.append((x, x + z.width))
            x += z.width + luecke
        daten = ocr.pytesseract.image_to_data(
            reihe, output_type=ocr.Output.DICT, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789"
        )
        for i, text in enumerate(daten["text"]):
            if not text.strip().isdigit():
                continue
            mitte = daten["left"][i] + daten["width"][i] / 2
            for k, (a, b) in enumerate(grenzen):
                if a - luecke / 2 <= mitte <= b + luecke / 2:
                    ergebnis[k].append(int(text.strip()))
                    break
    return ergebnis


def passende_folge(kandidaten, zentren, schritt_pt, schritte=(2, 1, 6, 4, 3)):
    """Die Grössenfolge `start + schritt * Spaltenindex`, die die meisten
    Leseversuche bestätigt - mindestens in der Hälfte der Spalten (und 2)."""
    index = [round((cx - zentren[0]) / schritt_pt) for cx in zentren]
    beste = None
    for schritt in schritte:
        for start in range(20, 200):
            treffer = sum(1 for k, liste in zip(index, kandidaten) if (start + schritt * k) in liste)
            stimmen = sum(liste.count(start + schritt * k) for k, liste in zip(index, kandidaten))
            if beste is None or (treffer, stimmen) > beste[0]:
                beste = ((treffer, stimmen), start, schritt)
    if beste is None:
        return None
    (treffer, _), start, schritt = beste
    if treffer < max(2, (len(zentren) + 1) // 2):
        return None
    return [str(start + schritt * k) for k in index]


def spaltenabstand(zentren) -> float:
    """Abstand benachbarter Spalten: der kleinste plausible Abstand der Mitten
    (Spalten sind gleich breit), sonst der übliche."""
    abstaende = [b - a for a, b in zip(zentren, zentren[1:]) if b - a >= 15]
    return min(abstaende) if abstaende else 24.4


# --- Gesamtablauf -------------------------------------------------------


def lies_bestellung(pdf_data: bytes, language: str, spaltenfinder) -> dict:
    """`{"kaesten": [...], "kopf_text", "fuss_text"}`.

    Je Kasten `{"page", "titel": [Wörter], "columns": [(x_mitte, Grösse|None)],
    "zeilen": [{"farbe": [Wörter], "mengen": [Text|None je Spalte], "gesamt", "betrag"}],
    "ek": [Preis|None je Spalte], "vk": [...]}`; Wörter im Format
    der PyMuPDF-Wörter (Punkte). `spaltenfinder(preis_woerter)` liefert die
    x-Mitten der Spalten aus der Preiszeile."""
    if ocr.pytesseract is None or Image is None:
        raise ocr.OcrUnavailableError(translate("errors.ocr.unavailable", language))
    ergebnis = {"kaesten": [], "kopf_text": "", "fuss_text": ""}
    x0, x1 = RAND_X
    try:
        with pymupdf.open(stream=pdf_data, filetype="pdf") as dokument:
            letzter = None
            for nummer, seite in enumerate(dokument, start=1):
                if nummer == 1:
                    ergebnis["kopf_text"] = " ".join(w[4] for w in _ausschnitt(seite, x0, 90, x1, 240))
                for k in kaesten(zeilenstruktur(seite)):
                    kopf = k["kopf"]
                    preis = _ausschnitt(seite, x0, k["preis"]["y0"], x1, k["preis"]["y1"])
                    zentren = spalten_erweitern(seite, k["preis"], spaltenfinder(preis))
                    beschriftung = None
                    if zentren:
                        beschriftung = passende_folge(
                            kandidaten_je_spalte(seite, kopf["y0"], kopf["y1"], zentren), zentren, spaltenabstand(zentren)
                        )
                    ek = [_preis_text(t) for t in zahlen_lesen(seite, [(cx - 12, k["preis"]["y0"], cx + 12, k["preis"]["y1"]) for cx in zentren], rand=1.0)]
                    ergebnis["kaesten"].append(
                        {
                            "page": nummer,
                            "titel": _ausschnitt(seite, x0, max(kopf["y0"] - 24, 0), x1, kopf["y0"] - 1),
                            "columns": [(cx, beschriftung[i] if beschriftung else None) for i, cx in enumerate(zentren)],
                            "zeilen": [_zeile_lesen(seite, z, zentren, ek) for z in k["zeilen"]],
                            # Preise je Spalte als Zelle gelesen („34.75" oder None).
                            "ek": ek,
                            "vk": [_preis_text(t) for t in zahlen_lesen(seite, [(cx - 12, k["vk"]["y0"], cx + 12, k["vk"]["y1"]) for cx in zentren], rand=1.0)],
                        }
                    )
                    letzter = (seite, k["vk"]["y1"])
            if letzter is not None:
                seite, y = letzter
                ergebnis["fuss_text"] = " ".join(w[4] for w in _ausschnitt(seite, x0, y + 5, x1, min(y + 90, seite.rect.height)))
    except ocr.pytesseract.TesseractNotFoundError as exc:
        raise ocr.OcrUnavailableError(translate("errors.ocr.unavailable", language)) from exc
    return ergebnis
