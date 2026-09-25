"""FEDAS-Code → Kassenkategorie-Vorschlag (Regel 8).

FEDAS ist ein europäischer 6-stelliger Code für Sportartikel, der auf
INTERSPORT-Rechnungen je Position mitgeliefert wird
(`app/services/parsers/intersport.py` erfasst ihn als `fedas_code`). Aufbau
laut FEDAS-Liste (deutsche Übersicht, von Fabian am 24.09.2026 bereitgestellt):

- Ziffer 1: Produkt-Typ (1 Hartware, 2 Textil, 3 Schuhe) = Hauptgruppe
- Ziffern 2–3: Erlebnisbereich (54 Stück, z. B. 24 Tennis, 46 Running)
- Ziffern 4–5: Haupt-Warengruppe (z. B. 01–08 unter Bike = ganze Fahrräder)
- Ziffer 6: Unter-Warengruppe

Die Kasse kennt nur 11 Sportbereiche. Die Zuordnung der 54 Erlebnisbereiche
darauf hat Fabian am 24.09.2026 bestätigt. Die FEDAS-Liste selbst liegt nicht
im Repo (öffentlich, Liste gehört FEDAS) - nur diese Zuordnung.

Nicht ableitbar ist **Kids**: FEDAS kennt kein Alter. Solche Artikel und alle
Codes ohne Zuordnung bekommen keinen Vorschlag (`None`) und werden auf der
Artikelseite von Hand gewählt (`app/services/kategorien.py`, B8). Eine Wahl
von Hand bleibt dauerhaft (`artikel.kategorie_manuell`); weder ein späterer
Import noch diese Tabelle überschreibt sie.
"""

HAUPTGRUPPE_NACH_PRODUKTART = {
    "1": "Hartware",
    "2": "Textil",
    "3": "Schuhe",
}

# Erlebnisbereich (FEDAS-Ziffern 2–3) → Sportbereich der Kasse.
SPORTBEREICH_NACH_ERLEBNISBEREICH = {
    # Winter
    "01": "Winter",  # Ski Alpin
    "02": "Winter",  # Langlauf
    "03": "Winter",  # Tourenskifahren / Telemark
    "04": "Winter",  # Snowboarding
    "05": "Winter",  # Schlitteln / Rodeln
    "08": "Winter",  # Eishockey
    "09": "Winter",  # Eiskunstlauf
    "10": "Winter",  # Eisschnelllauf
    "11": "Winter",  # Eisstock / Curling
    # Freizeitliches im Winter führt die Sportfabrik unter Outdoor.
    "14": "Outdoor",  # Freizeit / Mode Winter
    # Baden
    "15": "Baden",  # Baden / Beach
    "16": "Baden",  # Windsurfen
    "17": "Baden",  # Tauchen
    "18": "Baden",  # Wasserski
    "19": "Baden",  # Segeln
    "20": "Baden",  # Rudern
    "21": "Baden",  # Kajak / Kanu
    # Tennis
    "24": "Tennis",
    "25": "Tennis",  # Squash
    "26": "Tennis",  # Badminton
    "27": "Tennis",  # Tischtennis
    # Fussball
    "32": "Fussball",
    # Indoor
    "33": "Indoor",  # Basketball
    "34": "Indoor",  # Volleyball
    "35": "Indoor",  # Handball
    "38": "Indoor",  # Unihockey / Feldhockey
    "78": "Indoor",  # Fitness / Workout
    "80": "Indoor",  # Boxen
    "81": "Indoor",  # Ringen
    "82": "Indoor",  # Kampfsport
    # Running
    "45": "Running",  # Walking / Nordic Walking
    "46": "Running",
    "47": "Running",  # Leichtathletik
    "48": "Running",  # Orientierungslauf
    "56": "Running",  # Triathlon
    # Velo
    "60": "Velo",  # Bike
    # Rollsport
    "62": "Rollsport",  # Funwheel Sports
    # Outdoor
    "64": "Outdoor",  # Bergsport / Wandern
    "65": "Outdoor",  # Paragliding
    "67": "Outdoor",  # Camping
    "69": "Outdoor",  # Jagd
    "70": "Outdoor",  # Fischen
    # Freizeit
    "00": "Freizeit",  # Multisport
    "36": "Freizeit",  # American Football / Rugby
    "37": "Freizeit",  # Baseball / Softball
    "49": "Freizeit",  # Golf
    "50": "Freizeit",  # Bogenschiessen / Waffensport
    "71": "Freizeit",  # Reiten
    "75": "Freizeit",  # Freizeit / Mode Sommer
    "84": "Freizeit",  # Billard / Snooker
    "85": "Freizeit",  # Bowling / Kegeln
    "87": "Freizeit",  # Darts
    "88": "Freizeit",  # Verschiedene Spiele
    "98": "Freizeit",  # Werbe- / Promotionsaktivitäten
}

# Hauptgruppen der Kasse ohne Sportbereich (Regel 8): ganze Fahrräder und
# Anhänger (Hartware × Bike, Warengruppen 01–08) sind Velo, Sportnahrung
# (Hartware × Multisport, Warengruppe 20) ist Food.
VELO_WARENGRUPPEN = {f"1600{ziffer}" for ziffer in "12345678"}
FOOD_WARENGRUPPEN = {"10020"}


def suggest_kategorie(fedas_code: str | None) -> tuple[str, str | None] | None:
    """(hauptgruppe, sportbereich) für einen FEDAS-Code, oder None, wenn er
    fehlt oder nicht zugeordnet ist. Velo und Food haben keinen Sportbereich."""
    if not fedas_code or len(fedas_code) < 3:
        return None
    warengruppe = fedas_code[:5]
    if warengruppe in VELO_WARENGRUPPEN:
        return "Velo", None
    if warengruppe in FOOD_WARENGRUPPEN:
        return "Food", None
    hauptgruppe = HAUPTGRUPPE_NACH_PRODUKTART.get(fedas_code[0])
    sportbereich = SPORTBEREICH_NACH_ERLEBNISBEREICH.get(fedas_code[1:3])
    if hauptgruppe is None or sportbereich is None:
        return None
    return hauptgruppe, sportbereich
