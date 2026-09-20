"""FEDAS-Code → Kassenkategorie-Vorschlag (Phase B, siehe projekt-kontext.md
Abschnitt 6). FEDAS ist ein europäischer 6-stelliger Code für Sportartikel,
der auf INTERSPORT-Rechnungen je Position mitgeliefert wird
(`app/services/parser.py` erfasst ihn als `fedas_code`). 1. Ziffer =
Produktart (Hauptgruppe), Ziffern 2–3 = Sportart (Sportbereich) - beide
offenbar unabhängig voneinander kombinierbar, siehe die beiden Tabellen
unten.

Nur aus echten Rechnungen bestätigte Codes sind hier eingetragen. Fehlt eine
Zuordnung (unbekannte Produktart- und/oder Sportart-Ziffern, z. B. für die
Hauptgruppen Velo/Food, deren Produktart-Ziffer noch nicht bekannt ist),
liefert `suggest_kategorie()` `None` - die Kategorie bleibt dann unbesetzt
und muss (sobald eine Auswahl-Oberfläche dafür existiert) von Hand gewählt
werden, danach aber dauerhaft gemerkt (siehe `app/services/importer.py`)."""

HAUPTGRUPPE_NACH_PRODUKTART = {
    "1": "Hartware",
    "2": "Textil",
    "3": "Schuhe",
}

SPORTBEREICH_NACH_SPORTART = {
    "24": "Tennis",
    "32": "Fussball",
    "60": "Velo",
    "64": "Outdoor",
    "75": "Freizeit",
}


def suggest_kategorie(fedas_code: str | None) -> tuple[str, str] | None:
    """(hauptgruppe, sportbereich) für einen FEDAS-Code, oder None, wenn die
    Produktart- und/oder Sportart-Ziffern (noch) nicht zugeordnet sind."""
    if not fedas_code or len(fedas_code) < 3:
        return None
    hauptgruppe = HAUPTGRUPPE_NACH_PRODUKTART.get(fedas_code[0])
    sportbereich = SPORTBEREICH_NACH_SPORTART.get(fedas_code[1:3])
    if hauptgruppe is None or sportbereich is None:
        return None
    return hauptgruppe, sportbereich
