"""Preis-/Reduktionsetikett als PDF (Phase B, Teilaufgabe B7; neu gestaltet
am 24.09.2026).

Die Sportfabrik druckt auf **vorgedruckte Rollen** im Sato CL4NX Plus (D14):
47 mm breit, 83 mm hoch (Hochformat). Logo, Prozent-Punkt und Berge sind
schon auf der Rolle - je Reduktionsstufe eine eigene Rolle: 30 % gelber,
50 % roter, 70 % grüner Punkt. Gedruckt werden deshalb nur:

- der **UVP**, gross und durchgestrichen,
- links der **Code der Lieferantengruppe** (111/555/333/999/444),
- rechts der **Jahrgang** zweistellig (Jahr des Wareneingangs, D25),
- unter den Bergen der **EAN-Strichcode** mit Klarschrift - ohne ihn bliebe
  genau der Artikel an der Kasse unscannbar, für den die interne EAN (D10)
  gedacht ist.

Die Reduktion druckt das System nicht, sie sagt nur, **welche Rolle**
einzulegen ist (`rolle`). Das Etikett wird gerade neu gestaltet (alles etwas
nach oben, Strichcode unter den Bergen); die Positionen stehen darum an einer
Stelle (`LAYOUT`) und lassen sich an die neue Rolle anpassen. Mit
`muster=True` zeichnet das PDF den Vordruck angedeutet mit - als Vorschau,
nicht zum Drucken.

Die PDF-Seite ist exakt so gross wie das Etikett, damit der Drucker 1:1
druckt. Gezeichnet wird mit PyMuPDF und den eingebauten PDF-Schriften
(Helvetica) - keine zusätzliche Abhängigkeit, kein Internet (Regel 1).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pymupdf
from sqlalchemy import select

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.lieferanten import etikett_code
from ..core.models import Artikel, Lieferant, Preis, ReduktionManuell, Variante
from .barcode import (
    RUHEZONE_LINKS,
    RUHEZONE_RECHTS,
    BarcodeNichtDruckbar,
    druckbare_nummer,
    strichmuster,
)
from .reduktion import letzter_wareneingang, stufe

# Breite × Höhe in Millimetern: die vorgedruckte Rolle der Sportfabrik
# (Präzisierung vom 24.09.2026, ersetzt 84 × 47 mm).
GROESSEN = {"47x83": (47, 83)}
STANDARD_GROESSE = "47x83"

# Welche Rolle zu welcher Reduktion gehört (Farbe des vorgedruckten Punkts).
# Neue Ware ohne fällige Stufe kommt auf die 30er-Rolle (D5: Eingang -30 %).
ROLLEN = {30: "gelb", 50: "rot", 70: "gruen"}

# Positionen in Millimetern ab der linken oberen Ecke - hier anpassen, wenn
# die neu gestaltete Rolle andere Masse hat. y ist jeweils die Grundlinie.
LAYOUT = {
    "rand": 2.5,
    "logo_y": 6.0,  # Vordruck
    "preis_y": 18.0,
    "preis_hoehe": 10.0,  # Schriftgrösse des UVP in mm (höchstens)
    "punkt_mitte_y": 33.0,  # Vordruck
    "punkt_radius": 12.5,  # Vordruck
    "code_y": 51.0,  # Lieferantencode links, Jahrgang rechts
    "code_hoehe": 3.6,
    "berge_oben": 53.0,  # Vordruck
    "berge_unten": 64.0,  # Vordruck
    "barcode_oben": 66.0,
    "barcode_unten": 81.0,
}

MM = 72 / 25.4  # Millimeter → PDF-Punkte

MAX_ETIKETTEN = 500

# Breite eines Strichcode-Moduls: 0,33 mm ist die Normgrösse, 200 % das
# erlaubte Maximum. Wir bleiben mit 0,5 mm knapp darunter.
MAX_MODUL = 0.5 * 72 / 25.4

# Farben des Vordrucks, nur für das Muster.
_VORDRUCK = {
    "grund": (0.78, 0.78, 0.78),
    "logo": (0.87, 0.23, 0.13),
    "berge": (0.12, 0.1, 0.1),
    "gelb": (0.98, 0.9, 0.25),
    "rot": (0.9, 0.2, 0.15),
    "gruen": (0.35, 0.7, 0.3),
}

NORMAL, FETT = "helv", "hebo"


def rolle(reduktion: int | None) -> dict:
    """Welche vorgedruckte Rolle für diese Reduktion einzulegen ist."""
    prozent = reduktion if reduktion in ROLLEN else 30
    return {"prozent": prozent, "farbe": ROLLEN[prozent]}


class EtikettError(ValueError):
    """Das Etikett lässt sich so nicht drucken."""


class EtikettNichtGefunden(EtikettError):
    """Die Variante gibt es nicht."""


@dataclass(frozen=True)
class Etikett:
    """Alles, was auf ein Etikett kommt - schon fertig ausgewählt, damit das
    Zeichnen ohne Datenbank auskommt (und sich einzeln testen lässt)."""

    marke: str | None = None
    bezeichnung: str | None = None
    farbe: str | None = None
    groesse: str | None = None
    lieferant: str | None = None
    # Code der Lieferantengruppe (111/555/333/999/444, 23.09.2026).
    lieferant_code: str | None = None
    uvp: Decimal | None = None
    jahrgang: int | None = None
    reduktion: int = 0
    ean: str | None = None
    ean_intern: bool = False
    anzahl: int = 1
    # Kurzer Zusatz für den Fall, dass kein Strichcode gedruckt werden kann
    # (z. B. „ohne EAN"). Kommt schon übersetzt herein - hier wird nicht
    # übersetzt, damit das Zeichnen ohne i18n auskommt (Regel 7)."
    hinweis: str | None = None


def _preis(session, varianten_id: int) -> Preis | None:
    """Neuester Preiseintrag der Variante (der Verlauf ist in `preise`)."""
    return session.scalars(
        select(Preis)
        .where(Preis.varianten_id == varianten_id)
        .order_by(Preis.datum.desc().nullslast(), Preis.id.desc())
        .limit(1)
    ).first()


def sammle_etikett(
    session,
    varianten_id: int,
    lagerort_id: int | None = None,
    reduktion: int | None = None,
    anzahl: int = 1,
    heute: date | None = None,
    hinweis_ohne_ean: str | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> Etikett:
    """Etikettendaten einer Variante aus der Datenbank holen.

    `lagerort_id` entscheidet über Jahrgang und Reduktionsvorschlag: beides
    hängt am letzten Wareneingang **in dieser Filiale** (Regel 6). Ohne
    Filiale bleibt der Jahrgang leer. Eine ausdrücklich mitgegebene
    `reduktion` gewinnt immer - die 30 % aus D25 sind eine Entscheidung des
    Ladens, keine Zeitregel.
    """
    variante = session.get(Variante, varianten_id)
    if variante is None:
        raise EtikettNichtGefunden(
            translate("errors.etikett.variante_not_found", language, id=varianten_id)
        )
    artikel = session.get(Artikel, variante.artikel_id)
    lieferant = (
        session.get(Lieferant, artikel.lieferant_id) if artikel.lieferant_id else None
    )
    preis = _preis(session, variante.id)
    eingang = (
        letzter_wareneingang(session, artikel.id, lagerort_id)
        if lagerort_id is not None
        else None
    )
    if reduktion is None and lagerort_id is not None:
        # Von Hand gewählte Stufe dieser Filiale geht der Empfehlung vor
        # (24.09.2026).
        reduktion = session.scalar(
            select(ReduktionManuell.prozent).where(
                ReduktionManuell.artikel_id == artikel.id,
                ReduktionManuell.lagerort_id == lagerort_id,
            )
        )
    return Etikett(
        marke=artikel.marke,
        bezeichnung=artikel.bezeichnung,
        farbe=variante.farbe,
        groesse=variante.groesse,
        lieferant=lieferant.name if lieferant else None,
        lieferant_code=etikett_code(lieferant.typ) if lieferant else None,
        uvp=preis.uvp if preis else None,
        jahrgang=eingang.year if eingang else None,
        reduktion=stufe(eingang, heute) if reduktion is None else reduktion,
        ean=variante.ean,
        ean_intern=bool(variante.ean_intern),
        anzahl=anzahl,
        hinweis=None if variante.ean else hinweis_ohne_ean,
    )


def _kuerze(text: str, schrift: str, groesse: float, platz: float) -> str:
    """Text so weit kürzen, dass er in die Breite passt - lieber abgeschnitten
    als über den Rand hinaus."""
    if pymupdf.get_text_length(text, fontname=schrift, fontsize=groesse) <= platz:
        return text
    while text and pymupdf.get_text_length(
        text + "...", fontname=schrift, fontsize=groesse
    ) > platz:
        text = text[:-1]
    return text + "..."


def _latin1(text: str) -> str:
    """Die eingebauten PDF-Schriften können Latin-1. Zeichen ausserhalb (etwa
    kyrillische Buchstaben in einer Bezeichnung) würden sonst als leere
    Kästchen erscheinen."""
    return text.encode("latin-1", "replace").decode("latin-1")


def _zeile(page, x, y, text, schrift=NORMAL, groesse=7.0, farbe=(0, 0, 0), platz=None):
    text = _latin1((text or "").strip())
    if not text:
        return
    if platz:
        text = _kuerze(text, schrift, groesse, platz)
    page.insert_text((x, y), text, fontname=schrift, fontsize=groesse, color=farbe)


def _rechtsbuendig(page, rechts, y, text, schrift=FETT, groesse=7.0, farbe=(0, 0, 0)):
    text = _latin1((text or "").strip())
    if not text:
        return
    breite = pymupdf.get_text_length(text, fontname=schrift, fontsize=groesse)
    page.insert_text(
        (rechts - breite, y), text, fontname=schrift, fontsize=groesse, color=farbe
    )


def _zeichne_barcode(page, etikett, links, rechts, oben, unten) -> None:
    """Strichcode samt Klarschrift. Lässt sich die Nummer nicht als EAN
    drucken (z. B. EAN-14 vom Umkarton), stehen nur die Ziffern da."""
    schrift = 2.6 * MM
    nummer = druckbare_nummer(etikett.ean)
    if nummer is None:
        # Kein Strichcode möglich: wenigstens die Nummer und der Grund, damit
        # im Laden auffällt, dass hier eine interne EAN fehlt (D10/D24).
        y = (oben + unten) / 2
        if etikett.ean:
            _zeile(page, links, y, etikett.ean, NORMAL, schrift, platz=rechts - links)
            y += schrift * 1.3
        _zeile(page, links, y, etikett.hinweis, NORMAL, schrift, platz=rechts - links)
        return
    muster = strichmuster(etikett.ean)
    module = RUHEZONE_LINKS + len(muster) + RUHEZONE_RECHTS
    # So breit wie möglich, aber ein Modul nie breiter als MAX_MODUL (GS1
    # erlaubt bis 200 % der Normgrösse von 0,33 mm).
    modulbreite = min((rechts - links) / module, MAX_MODUL)
    x = links + (rechts - links - module * modulbreite) / 2 + RUHEZONE_LINKS * modulbreite
    strichunten = unten - schrift * 1.2
    for zeichen in muster:
        if zeichen == "1":
            page.draw_rect(
                pymupdf.Rect(x, oben, x + modulbreite, strichunten), color=None, fill=(0, 0, 0)
            )
        x += modulbreite
    beschriftung = nummer + (" *" if etikett.ean_intern else "")
    breite = pymupdf.get_text_length(beschriftung, fontname=NORMAL, fontsize=schrift)
    page.insert_text(((links + rechts - breite) / 2, unten), beschriftung, fontname=NORMAL, fontsize=schrift)


def _zeichne_vordruck(page, breite: float, hoehe: float, reduktion: int) -> None:
    """Nur für das Muster: Rolle mit Logo, Punkt und Bergen andeuten."""
    mm = lambda wert: wert * MM  # noqa: E731
    page.draw_rect(pymupdf.Rect(0, 0, breite, hoehe), color=None, fill=_VORDRUCK["grund"])
    _zeile(page, mm(LAYOUT["rand"]), mm(LAYOUT["logo_y"]), "SPORT-FABRIK", FETT, mm(4.6), _VORDRUCK["logo"])
    mitte = pymupdf.Point(breite / 2, mm(LAYOUT["punkt_mitte_y"]))
    stufe_der_rolle = rolle(reduktion)
    page.draw_circle(mitte, mm(LAYOUT["punkt_radius"]), color=None, fill=_VORDRUCK[stufe_der_rolle["farbe"]])
    text = f"-{stufe_der_rolle['prozent']}%"
    groesse = mm(6.5)
    textbreite = pymupdf.get_text_length(text, fontname=NORMAL, fontsize=groesse)
    page.insert_text((mitte.x - textbreite / 2, mitte.y + groesse * 0.36), text, fontname=NORMAL, fontsize=groesse)
    oben, unten = mm(LAYOUT["berge_oben"]), mm(LAYOUT["berge_unten"])
    gipfel = [(0, 0.55), (0.12, 0.35), (0.22, 0.05), (0.33, 0.4), (0.45, 0.2), (0.55, 0.45),
              (0.68, 0.0), (0.8, 0.3), (0.9, 0.2), (1.0, 0.5)]
    punkte = [pymupdf.Point(0, unten)] + [
        pymupdf.Point(x * breite, oben + y * (unten - oben)) for x, y in gipfel
    ] + [pymupdf.Point(breite, unten)]
    page.draw_polyline(punkte, color=None, fill=_VORDRUCK["berge"], closePath=True)


def _zeichne_etikett(page, etikett: Etikett, breite: float, hoehe: float, muster: bool = False) -> None:
    mm = lambda wert: wert * MM  # noqa: E731
    if muster:
        _zeichne_vordruck(page, breite, hoehe, etikett.reduktion)
    links, rechts = mm(LAYOUT["rand"]), breite - mm(LAYOUT["rand"])

    # UVP gross und durchgestrichen - so kleiner, dass er in die Breite passt.
    if etikett.uvp is not None:
        preis = str(Decimal(etikett.uvp).quantize(Decimal("0.01")))
        groesse = mm(LAYOUT["preis_hoehe"])
        groesse = min(groesse, groesse * (rechts - links) / pymupdf.get_text_length(preis, fontname=FETT, fontsize=groesse))
        y = mm(LAYOUT["preis_y"])
        page.insert_text((links, y), preis, fontname=FETT, fontsize=groesse)
        ende = links + pymupdf.get_text_length(preis, fontname=FETT, fontsize=groesse)
        # Leicht steigend, wie der Strich von Hand auf den heutigen Etiketten.
        page.draw_line(
            pymupdf.Point(links - mm(0.5), y - groesse * 0.12),
            pymupdf.Point(ende + mm(0.5), y - groesse * 0.62),
            color=(0, 0, 0),
            width=mm(0.45),
        )

    # Lieferantencode links, Jahrgang zweistellig rechts (Muster vom 24.09.2026).
    y = mm(LAYOUT["code_y"])
    _zeile(page, links, y, etikett.lieferant_code, NORMAL, mm(LAYOUT["code_hoehe"]))
    if etikett.jahrgang:
        _rechtsbuendig(page, rechts, y, f"{etikett.jahrgang % 100:02d}", NORMAL, mm(LAYOUT["code_hoehe"]))

    _zeichne_barcode(page, etikett, links, rechts, mm(LAYOUT["barcode_oben"]), mm(LAYOUT["barcode_unten"]))


def etiketten_pdf(
    etiketten,
    groesse: str = STANDARD_GROESSE,
    language: str = DEFAULT_LANGUAGE,
    muster: bool = False,
) -> bytes:
    """Ein PDF mit einer Seite je Etikett, Seitengrösse = Etikettengrösse.

    `anzahl` je Etikett wiederholt die Seite (ein Etikett je Stück Ware).
    `muster` zeichnet den Vordruck der Rolle angedeutet mit (Vorschau).
    """
    if groesse not in GROESSEN:
        raise EtikettError(translate("errors.etikett.unknown_size", language))
    etiketten = list(etiketten)
    if not etiketten:
        raise EtikettError(translate("errors.etikett.nothing_to_print", language))
    breite_mm, hoehe_mm = GROESSEN[groesse]
    breite, hoehe = breite_mm * MM, hoehe_mm * MM
    dokument = pymupdf.open()
    seiten = 0
    for etikett in etiketten:
        for _ in range(max(1, min(etikett.anzahl, MAX_ETIKETTEN))):
            seiten += 1
            if seiten > MAX_ETIKETTEN:
                raise EtikettError(
                    translate("errors.etikett.too_many", language, limit=MAX_ETIKETTEN)
                )
            _zeichne_etikett(dokument.new_page(width=breite, height=hoehe), etikett, breite, hoehe, muster)
    return dokument.tobytes()
