"""Lagerdauer und Reduktionsstufe (Regel 6).

Die Runterschreib-Regel der Sportfabrik: **18 Monate → 50 %, 36 Monate →
70 %**, gerechnet ab dem letzten Wareneingang derselben Lieferanten-
Artikelnummer **in dieser Filiale** (eine Nachlieferung startet die Uhr neu).
Die 30 % aus D25 sind eine Entscheidung des Ladens, keine Zeitregel - sie
lassen sich am Etikett von Hand mitgeben.

Hier steht vorerst nur, was das Etikett (Teilaufgabe B7) braucht: das
massgebende Datum und die daraus folgende Stufe. Die Hinweise für die
Filialen (Phase D) bauen darauf auf.
"""

from datetime import date

from sqlalchemy import func, select

from ..core.models import Lagerbewegung, Variante, Wareneingang, WareneingangPosition

# Absteigend, damit die erste zutreffende Stufe gewinnt.
STUFEN = ((36, 70), (18, 50))

ERLAUBTE_STUFEN = (0, 30, 50, 70)


def letzter_wareneingang(session, artikel_id: int, lagerort_id: int) -> date | None:
    """Datum des letzten **angekommenen** Wareneingangs dieses Artikels in
    dieser Filiale (Regel 6). `None`, wenn es dort keinen gibt - oder nur
    solche ohne Eingangsdatum (Lager ohne Verkauf, dort läuft keine Uhr).

    Mitgezählt wird eine Umlagerung, die die Uhr in dieser Filiale gestartet
    hat (`lagerbewegungen.eingangsdatum`, Teilaufgabe C4): der Weg von einem
    externen Standort (D13) oder in eine Filiale, die den Artikel noch nie
    hatte (F11). Jede andere Umlagerung lässt die Uhr unverändert (F10).
    """
    aus_umlagerung = session.scalar(
        select(func.max(Lagerbewegung.eingangsdatum))
        .join(Variante, Variante.id == Lagerbewegung.varianten_id)
        .where(
            Variante.artikel_id == artikel_id,
            Lagerbewegung.lagerort_id == lagerort_id,
            Lagerbewegung.typ == "umlagerung",
        )
    )
    aus_wareneingang = session.scalar(
        select(func.max(Wareneingang.eingangsdatum))
        .select_from(WareneingangPosition)
        .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
        .join(Variante, Variante.id == WareneingangPosition.varianten_id)
        .where(
            Variante.artikel_id == artikel_id,
            Wareneingang.lagerort_id == lagerort_id,
            WareneingangPosition.menge_eingetroffen > 0,
        )
    )
    daten = [datum for datum in (aus_wareneingang, aus_umlagerung) if datum]
    return max(daten) if daten else None


def monate_seit(eingang: date, heute: date) -> int:
    """Volle Monate zwischen zwei Daten - der Tag im Monat entscheidet, wie
    bei einem Geburtstag (am 5.3. sind seit dem 5.9. sechs Monate um, am
    4.3. noch nicht)."""
    monate = (heute.year - eingang.year) * 12 + (heute.month - eingang.month)
    if heute.day < eingang.day:
        monate -= 1
    return max(monate, 0)


def stufe(eingang: date | None, heute: date | None = None) -> int:
    """Fällige Reduktion in Prozent (0, 50 oder 70) nach Regel 6."""
    if eingang is None:
        return 0
    heute = heute or date.today()
    alter = monate_seit(eingang, heute)
    for monate, prozent in STUFEN:
        if alter >= monate:
            return prozent
    return 0
