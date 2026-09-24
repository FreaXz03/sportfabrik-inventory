"""Preis-/Reduktionsetikett als PDF (Phase B, Teilaufgabe B7).

D25: Auf dem Etikett stehen **Jahrgang** (wann die Ware eingetroffen ist),
**Lieferant**, **UVP** und die **Reduktionsstufe** (30/50/70 %). Dazu kommt
der EAN-Strichcode: ohne ihn bliebe genau der Artikel an der Kasse
unscannbar, für den die interne EAN (D10) gedacht ist - die Nummer allein
nützt an der Kasse nichts.

Gedruckt wird auf dem Sato CL4NX Plus (D14), Rollen 84 × 47 mm (bestätigt
am 23.09.2026). Die Grösse bleibt **einstellbar** (`GROESSEN`); die PDF-Seite ist
exakt so gross wie das Etikett, damit der Drucker 1:1 druckt und nichts
skaliert werden muss.

Gezeichnet wird mit PyMuPDF, das ohnehin für das Lesen der Rechnungen im
Einsatz ist - keine zusätzliche Abhängigkeit, keine externen Dienste
(Regel 1). Schriften sind die im PDF eingebauten (Helvetica), also auch
ohne Internet und ohne Schriftinstallation auf dem Drucker verfügbar.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pymupdf
from sqlalchemy import select

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.lieferanten import etikett_code
from ..core.models import Artikel, Lieferant, Preis, Variante
from .barcode import (
    RUHEZONE_LINKS,
    RUHEZONE_RECHTS,
    BarcodeNichtDruckbar,
    druckbare_nummer,
    strichmuster,
)
from .reduktion import letzter_wareneingang, stufe

# Breite × Höhe in Millimetern. Voreinstellung 84 × 47 mm - die Rollen im
# Sato CL4NX Plus der Sportfabrik (bestätigt am 23.09.2026). Die übrigen
# Grössen bleiben wählbar, falls einmal andere Rollen eingelegt sind.
GROESSEN = {
    "84x47": (84, 47),
    "50x30": (50, 30),
    "57x32": (57, 32),
    "70x40": (70, 40),
    "100x50": (100, 50),
}
STANDARD_GROESSE = "84x47"

MM = 72 / 25.4  # Millimeter → PDF-Punkte

MAX_ETIKETTEN = 500

# Breite eines Strichcode-Moduls: 0,33 mm ist die Normgrösse, 200 % das
# erlaubte Maximum. Wir bleiben mit 0,5 mm knapp darunter.
MAX_MODUL = 0.5 * 72 / 25.4

NORMAL, FETT = "helv", "hebo"


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


def _zeichne_barcode(page, etikett, links, rechts, oben, hoehe, skala) -> None:
    """Strichcode samt Klarschrift. Lässt sich die Nummer nicht als EAN
    drucken (z. B. EAN-14 vom Umkarton), stehen nur die Ziffern da."""
    nummer = druckbare_nummer(etikett.ean)
    if nummer is None:
        # Kein Strichcode möglich: wenigstens die Nummer und der Grund, damit
        # im Laden auffällt, dass hier eine interne EAN fehlt (D10/D24).
        y = oben + hoehe / 2
        if etikett.ean:
            _zeile(page, links, y, etikett.ean, NORMAL, 6 * skala, platz=rechts - links)
            y += 7 * skala
        _zeile(page, links, y, etikett.hinweis, NORMAL, 6 * skala, (0.35, 0.35, 0.35), rechts - links)
        return
    muster = strichmuster(etikett.ean)
    module = RUHEZONE_LINKS + len(muster) + RUHEZONE_RECHTS
    # So breit wie möglich, aber ein Modul nie breiter als MAX_MODUL: sonst
    # wäre der Strichcode auf einem grossen Etikett masslos in die Breite
    # gezogen (GS1 erlaubt bis 200 % der Normgrösse von 0,33 mm).
    modulbreite = min((rechts - links) / module, MAX_MODUL)
    # Ruhezone links, Rest mittig - der Strichcode beginnt eingerückt.
    x = links + (rechts - links - module * modulbreite) / 2 + RUHEZONE_LINKS * modulbreite
    strichhoehe = hoehe - 7 * skala
    for zeichen in muster:
        if zeichen == "1":
            page.draw_rect(
                pymupdf.Rect(x, oben, x + modulbreite, oben + strichhoehe),
                color=None,
                fill=(0, 0, 0),
            )
        x += modulbreite
    mitte = (links + rechts) / 2
    beschriftung = nummer + (" *" if etikett.ean_intern else "")
    breite = pymupdf.get_text_length(beschriftung, fontname=NORMAL, fontsize=5.5 * skala)
    page.insert_text(
        (mitte - breite / 2, oben + hoehe - 1 * skala),
        beschriftung,
        fontname=NORMAL,
        fontsize=5.5 * skala,
    )


def _zeichne_etikett(page, etikett: Etikett, breite: float, hoehe: float) -> None:
    skala = hoehe / (30 * MM)  # 50 × 30 mm ist die Bezugsgrösse
    rand = 2 * MM
    links, rechts = rand, breite - rand
    platz = rechts - links

    # Kopf: Marke und Jahrgang (D25) - das Wichtigste auf einen Blick.
    _zeile(page, links, 8 * skala, etikett.marke, FETT, 8.5 * skala, platz=platz * 0.72)
    if etikett.jahrgang:
        _rechtsbuendig(page, rechts, 8 * skala, str(etikett.jahrgang), FETT, 8.5 * skala)

    _zeile(page, links, 16 * skala, etikett.bezeichnung, NORMAL, 7 * skala, platz=platz)
    variante = " / ".join(t for t in (etikett.farbe, etikett.groesse) if t)
    _zeile(page, links, 23 * skala, variante, NORMAL, 6.5 * skala, (0.35, 0.35, 0.35), platz)
    # Rechts neben dem Lieferanten der Gruppen-Code - fett, damit er im
    # Laden auf einen Blick lesbar ist (Anforderungen vom 23.09.2026).
    code_platz = 0
    if etikett.lieferant_code:
        _rechtsbuendig(page, rechts, 29.5 * skala, etikett.lieferant_code, FETT, 8 * skala)
        code_platz = pymupdf.get_text_length(etikett.lieferant_code, fontname=FETT, fontsize=8 * skala) + 3 * skala
    _zeile(page, links, 29.5 * skala, etikett.lieferant, NORMAL, 6 * skala, (0.35, 0.35, 0.35), platz - code_platz)

    # Preis und Reduktionsstufe.
    if etikett.uvp is not None:
        preis = f"CHF {Decimal(etikett.uvp).quantize(Decimal('0.01'))}"
        _zeile(page, links, 41.5 * skala, preis, FETT, 13 * skala)
    if etikett.reduktion:
        _rechtsbuendig(page, rechts, 41.5 * skala, f"-{etikett.reduktion}%", FETT, 13 * skala)

    # Der Rest gehört dem Strichcode: je höher die Striche, desto leichter
    # findet ihn der Scanner.
    oben = 45.5 * skala
    _zeichne_barcode(page, etikett, links, rechts, oben, hoehe - oben - rand / 2, skala)


def etiketten_pdf(
    etiketten, groesse: str = STANDARD_GROESSE, language: str = DEFAULT_LANGUAGE
) -> bytes:
    """Ein PDF mit einer Seite je Etikett, Seitengrösse = Etikettengrösse.

    `anzahl` je Etikett wiederholt die Seite (ein Etikett je Stück Ware).
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
            _zeichne_etikett(dokument.new_page(width=breite, height=hoehe), etikett, breite, hoehe)
    return dokument.tobytes()
