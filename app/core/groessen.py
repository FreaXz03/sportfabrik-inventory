"""Grössen vereinheitlichen (Punkt 6, 2026-10-01).

- `D38` → `38` (D = Deutschland/EU-Schreibweise einiger Lieferanten).
- US- und UK-Schuhgrössen → EU, über die Tabelle unten (Fabian, 2026-10-01).
  Umgerechnet wird nur, wenn die Grösse ausdrücklich als US oder UK gekennzeichnet
  ist **und** das Geschlecht aus der Bezeichnung klar ist (Herren/Damen haben
  verschiedene Tabellen). Sonst bleibt die Grösse unverändert - nie raten.

Die Tabelle ist eine allgemeine Schuhgrössen-Tabelle; Marken weichen davon ab.
Gibt es für eine Marke eine eigene verlässliche Tabelle, kommt sie hier dazu.
Sonstige Artikeldaten aus Lieferantendokumenten werden nicht übersetzt (Regel 7).
"""

import re

# US → (EU, UK)
HERREN = {
    "7": ("40", "6"), "7.5": ("40.5", "6.5"), "8": ("41", "7"), "8.5": ("42", "7.5"),
    "9": ("42.5", "8"), "9.5": ("43", "8.5"), "10": ("44", "9"), "10.5": ("44.5", "9.5"),
    "11": ("45", "10"), "11.5": ("46", "10.5"), "12": ("47", "11"), "13": ("48", "12"),
    "14": ("49", "13"), "15": ("49.5", "14"),
}
DAMEN = {
    "5": ("35.5", "2.5"), "5.5": ("36", "3"), "6": ("36.5", "3.5"), "6.5": ("37", "4"),
    "7": ("37.5", "4.5"), "7.5": ("38", "5"), "8": ("38.5", "5.5"), "8.5": ("39", "6"),
    "9": ("40", "6.5"), "9.5": ("40.5", "7"), "10": ("41", "7.5"), "10.5": ("42", "8"),
    "11": ("42.5", "8.5"), "11.5": ("43", "9"), "12": ("44.5", "9.5"),
}

_D_PRAEFIX = re.compile(r"^D\s?(\d{2}(?:[.,]5)?)$", re.IGNORECASE)
_US_UK = re.compile(r"^(?:(US|UK)\s?(\d{1,2}(?:[.,]5)?)|(\d{1,2}(?:[.,]5)?)\s?(US|UK))$", re.IGNORECASE)
_HERREN = {"MEN", "MENS", "MEN'S", "MAN", "HERREN", "HERR", "MALE"}
_DAMEN = {"WOMEN", "WOMENS", "WOMEN'S", "WOMAN", "WMNS", "DAMEN", "DAME", "FEMALE", "LADIES"}


def _geschlecht(bezeichnung: str | None) -> dict | None:
    woerter = set(re.findall(r"[A-Z']+", (bezeichnung or "").upper()))
    herren, damen = woerter & _HERREN, woerter & _DAMEN
    if herren and not damen:
        return HERREN
    if damen and not herren:
        return DAMEN
    return None


def normalisiere_groesse(groesse: str | None, bezeichnung: str | None = None) -> str | None:
    """Einheitliche Grösse, oder die unveränderte, wenn nichts sicher ist."""
    if not groesse:
        return groesse
    roh = groesse.strip()
    treffer = _D_PRAEFIX.fullmatch(roh)
    if treffer:
        return treffer.group(1).replace(",", ".")
    treffer = _US_UK.fullmatch(roh)
    if not treffer:
        return groesse
    system = (treffer.group(1) or treffer.group(4)).upper()
    nummer = (treffer.group(2) or treffer.group(3)).replace(",", ".")
    tabelle = _geschlecht(bezeichnung)
    if tabelle is None:
        return groesse
    if system == "US":
        eintrag = tabelle.get(nummer)
    else:
        eintrag = next((eu_uk for eu_uk in tabelle.values() if eu_uk[1] == nummer), None)
    return groesse if eintrag is None else eintrag[0]
