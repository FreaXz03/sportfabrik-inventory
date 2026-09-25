"""Katalog der Funktionen, aus denen Schnellzugriffe wählbar sind (Punkt 14,
Entscheid 24.09.2026: 5 Funktionen und ihre Reihenfolge pro Benutzer
speichern). Eine Rolle sieht nur, was ihr auch sonst zugänglich ist
(Regel 9) - dieselbe Rollenliste wie in der Hauptnavigation (app/static/js/nav.js).
"""

FUNKTIONEN: dict[str, tuple[str, ...] | None] = {
    "bestand": None,
    "erfassen": None,
    "wareneingaenge": None,
    "umlagern": ("chef", "admin"),
    "ausbuchen": ("chef", "admin"),
    "runterschreiben": None,
    "articles": None,
    "invoices": None,
    "upload": ("chef", "admin"),
}

# Voreinstellung, solange niemand eine eigene Auswahl gespeichert hat -
# entspricht den bisherigen fünf fest verdrahteten Schnellzugriffen.
STANDARD = ["ausbuchen", "erfassen", "umlagern", "wareneingaenge", "upload"]

MAX_ANZAHL = 5


def verfuegbar_fuer(role: str) -> list[str]:
    """Funktionen, die eine Rolle grundsätzlich sehen darf, in Katalog-Reihenfolge."""
    return [key for key, nur in FUNKTIONEN.items() if nur is None or role in nur]


def wirksame_auswahl(gespeichert: list[str] | None, role: str) -> list[str]:
    """Die tatsächlich anzuzeigenden Schnellzugriffe: gespeicherte Auswahl,
    gefiltert auf gültige und für die Rolle erlaubte Funktionen. Leer oder
    nichts gespeichert -> Voreinstellung (ebenfalls rollengefiltert)."""
    erlaubt = verfuegbar_fuer(role)
    quelle = gespeichert if gespeichert else STANDARD
    ergebnis = [key for key in quelle if key in erlaubt]
    if ergebnis:
        return ergebnis[:MAX_ANZAHL]
    return [key for key in STANDARD if key in erlaubt][:MAX_ANZAHL]


def validieren(auswahl: list[str], role: str) -> str | None:
    """Prüft eine vom Benutzer gewählte Liste serverseitig. Gibt einen
    Fehlerschlüssel (für i18n) zurück, oder None wenn gültig."""
    if not auswahl or len(auswahl) > MAX_ANZAHL:
        return "errors.schnellzugriffe.anzahl"
    if len(set(auswahl)) != len(auswahl):
        return "errors.schnellzugriffe.doppelt"
    erlaubt = set(verfuegbar_fuer(role))
    if any(key not in erlaubt for key in auswahl):
        return "errors.schnellzugriffe.ungueltig"
    return None
