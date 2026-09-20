"""Seed-Daten für Lieferanten. Aktuell nur INTERSPORT Schweiz AG (der einzige
Lieferant mit funktionierendem Parser, siehe app/services/parser.py) - ECOM
läuft über dasselbe Layout (siehe projekt-kontext.md Abschnitt 6, Punkt 7),
braucht daher (noch) keinen eigenen Lieferanten-Eintrag. Weitere Lieferanten
(Alpina, Chris Sports, CMP, externe Händler, jeweils eigener Parser) folgen
in Phase E. Einzige Quelle für diese Daten - Migration und Tests nutzen sie.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Lieferant

LIEFERANTEN_SEED = [
    {
        "name": "INTERSPORT Schweiz AG",
        "typ": "intersport",
        "parser_key": "intersport",
    },
]


def seed_lieferanten(session: Session) -> None:
    """Legt fehlende Lieferanten aus LIEFERANTEN_SEED an. Idempotent."""
    existing_names = set(session.scalars(select(Lieferant.name)).all())
    for data in LIEFERANTEN_SEED:
        if data["name"] not in existing_names:
            session.add(Lieferant(**data))
