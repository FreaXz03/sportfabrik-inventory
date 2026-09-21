"""Artikel und Varianten finden - gemeinsam für alle Wege, auf denen Ware ins
System kommt (Dokument-Import und manuelle Erfassung).

Die beiden Schlüssel aus dem Zielbild:

* **Artikel** (Modell-Ebene, Regel 4): gleicher Lieferant + gleiche Marke +
  gleiche, nicht-leere Lieferanten-Artikelnummer. Fehlt die Nummer, bleibt
  jedes Vorkommen ein eigener Artikel - ohne sie lässt sich nicht sagen, ob
  zwei Zeilen dasselbe Modell meinen.
* **Variante** (Regel 5): die EAN, wenn es eine gibt; sonst Artikel + Farbe +
  Grösse.

Beide Regeln stehen absichtlich nur hier, damit Import und manuelle Erfassung
nicht auseinanderlaufen (und weil die Alembic-Migration `c3d4e5f6a7b8` die
Altdaten nach genau derselben Regel gruppiert hat).
"""

import re

from sqlalchemy import func, select

from ..core.models import Artikel, Variante

# Format einer echten EAN: EAN-8, UPC-12, EAN-13 oder EAN-14 (Umkarton).
# Steht hier, damit Vorschau-Korrekturen und manuelle Erfassung dieselbe
# Pruefung verwenden; die Pruefziffer selbst kommt mit Teilaufgabe B7.
EAN_MUSTER = re.compile(r"(?:[0-9]{8}|[0-9]{12,14})")


def artikel_group_key(marke: str | None, lieferanten_artikelnr: str | None):
    """`(marke_klein, artikelnr)` oder `None`, wenn keine Artikelnummer da ist
    (dann wird immer ein neuer Artikel angelegt)."""
    nummer = (lieferanten_artikelnr or "").strip()
    if not nummer:
        return None
    return ((marke or "").strip().lower(), nummer)


def finde_artikel(session, lieferant_id: int | None, group_key) -> Artikel | None:
    """Artikel zum Gruppen-Schlüssel, oder `None`. Ohne Lieferant wird unter
    den Artikeln ohne Lieferant gesucht (manuelle Erfassung, D23)."""
    if group_key is None:
        return None
    marke, nummer = group_key
    bedingung = (
        Artikel.lieferant_id == lieferant_id
        if lieferant_id is not None
        else Artikel.lieferant_id.is_(None)
    )
    return session.scalar(
        select(Artikel).where(
            bedingung,
            func.lower(func.trim(func.coalesce(Artikel.marke, ""))) == marke,
            func.trim(Artikel.lieferanten_artikelnr) == nummer,
        )
    )


def finde_variante_ohne_ean(
    session, artikel_id: int, farbe: str | None, groesse: str | None
) -> Variante | None:
    """Variante über Artikel + Farbe + Grösse (Regel 5, Schlüssel ohne EAN)."""
    return session.scalar(
        select(Variante).where(
            Variante.artikel_id == artikel_id,
            func.coalesce(Variante.farbe, "") == (farbe or ""),
            func.coalesce(Variante.groesse, "") == (groesse or ""),
        )
    )


def finde_variante_per_ean(session, ean: str | None) -> Variante | None:
    if not ean:
        return None
    return session.scalar(select(Variante).where(Variante.ean == ean))
