"""Kategorie aus Stichwörtern (Punkt 2, 2026-10-01).

Reicht der FEDAS-Code nicht (fehlt oder kennt nur die Hauptgruppe), werden
Artikelname und Dateiname nach ganzen Wörtern durchsucht: "PANT" im Namen →
Textil, "OUTDOOR" im Dateinamen → Sportbereich Outdoor. Die Hauptgruppe kommt
nur aus dem Artikelnamen (der Dateiname sagt nichts über das Produkt), der
Sportbereich aus Name und Dateiname.

Vorrang (siehe `kombiniere`): Wahl von Hand > FEDAS > Stichwörter. Stichwörter
füllen nur Lücken und überschreiben nie. Velo und Food werden nie über
Stichwörter vergeben (zu viele falsche Treffer: "Bike" ist auch Zubehör).
Die Listen sind ein Startsatz und gehören der Sportfabrik - ergänzen, wenn
Artikel falsch oder gar nicht zugeordnet werden.
"""

import re

HAUPTGRUPPE_STICHWOERTER = {
    "Textil": {
        "PANT", "PANTS", "HOSE", "SHIRT", "TSHIRT", "TEE", "JACKET", "JACKE", "HOODIE", "SHORT",
        "SHORTS", "JERSEY", "TIGHT", "TIGHTS", "SWEATER", "FLEECE", "TOP", "SKIRT", "DRESS",
    },
    "Schuhe": {"SHOE", "SHOES", "SCHUH", "SCHUHE", "SNEAKER", "BOOT", "BOOTS", "SANDAL", "SANDALS"},
    "Hartware": {"BALL", "RACKET", "RACQUET", "SCHLAEGER", "BOTTLE", "FLASCHE", "HELMET", "HELM"},
}

# Sportbereiche wie in der Kasse (Regel 8); "Velo" bewusst nicht.
SPORTBEREICH_STICHWOERTER = {
    "Outdoor": {"OUTDOOR", "TREKKING", "HIKING", "WANDERN"},
    "Running": {"RUNNING", "RUN", "LAUF", "JOGGING"},
    "Tennis": {"TENNIS", "PADEL", "SQUASH", "BADMINTON"},
    "Fussball": {"FUSSBALL", "FOOTBALL", "SOCCER"},
    "Baden": {"SWIM", "SWIMMING", "BADE", "BEACH"},
    "Winter": {"SKI", "SNOWBOARD", "WINTER"},
    "Kids": {"KIDS", "JUNIOR", "KINDER"},
    "Indoor": {"FITNESS", "YOGA", "INDOOR", "HANDBALL", "BASKETBALL"},
}


def _woerter(text: str | None) -> set[str]:
    if not text:
        return set()
    normal = text.upper().replace("Ä", "AE").replace("Ö", "OE").replace("Ü", "UE")
    return set(re.findall(r"[A-Z0-9]+", normal))


def _treffer(woerter: set[str], tabelle: dict[str, set[str]]) -> str | None:
    """Der eindeutige Treffer, sonst None (mehrere Treffer = unklar, nicht raten)."""
    gefunden = [name for name, begriffe in tabelle.items() if woerter & begriffe]
    return gefunden[0] if len(gefunden) == 1 else None


def kategorie_aus_text(bezeichnung: str | None, dateiname: str | None) -> tuple[str | None, str | None]:
    """(hauptgruppe, sportbereich) aus Artikelname und Dateiname; je `None`,
    wo nichts oder Mehrdeutiges gefunden wurde."""
    name = _woerter(bezeichnung)
    hauptgruppe = _treffer(name, HAUPTGRUPPE_STICHWOERTER)
    sportbereich = _treffer(name | _woerter(dateiname), SPORTBEREICH_STICHWOERTER)
    return hauptgruppe, sportbereich


def kombiniere(
    fedas: tuple[str, str | None] | None, text: tuple[str | None, str | None]
) -> tuple[str, str | None] | None:
    """FEDAS und Stichwörter zu einem Vorschlag (hauptgruppe, sportbereich).

    FEDAS mit Sportbereich und Velo/Food gelten unverändert. Kennt FEDAS nur
    die Hauptgruppe, ergänzt der Stichwort-Sportbereich sie (die Hauptgruppe
    bleibt die von FEDAS). Ohne FEDAS braucht es mindestens eine Hauptgruppe
    aus dem Text; ein Sportbereich allein ergibt keine Kategorie."""
    text_gruppe, text_bereich = text
    if fedas is not None:
        gruppe, bereich = fedas
        if bereich is not None or gruppe in ("Velo", "Food"):
            return fedas
        return gruppe, text_bereich
    if text_gruppe is None:
        return None
    return text_gruppe, text_bereich
