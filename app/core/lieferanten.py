"""Seed-Daten für Lieferanten. ECOM-Retouren laufen über das INTERSPORT-Layout
(projekt-kontext.md Abschnitt 6, Punkt 7); der Parser erkennt sie an der
Referenz „ret.Ecom" und der Import bucht sie auf den Lieferanten der Gruppe
ECOM (`lieferant_typ` im Parser-Ergebnis). Weitere Lieferanten
(Alpina, Chris Sports, CMP, externe Händler, jeweils eigenes Parser-Modul)
folgen in Phase E. `parser_key` muss zum KEY des Parser-Moduls passen, sonst
findet der Import den Lieferanten nicht (siehe app/services/importer.py).
Einzige Quelle für diese Daten - Migration und Tests nutzen sie.
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
    # Je Lieferantengruppe ein Eintrag für Ware, die von Hand erfasst wird
    # (Anforderungen vom 23.09.2026, Migration f2a3b4c5d6e7).
    {"name": "ECOM (Retouren Intersport-Onlineshop)", "typ": "ecom", "parser_key": None},
    {"name": "Händler (Restposten)", "typ": "extern", "parser_key": None},
    {"name": "Dritte-Händler (Marke direkt)", "typ": "drittanbieter", "parser_key": None},
    {"name": "Nike", "typ": "intern", "parser_key": None},
    {"name": "adidas", "typ": "intern", "parser_key": None},
    {"name": "The North Face", "typ": "intern", "parser_key": None},
]

# Lieferantengruppe (= `lieferanten.typ`) → Code auf dem Etikett
# (Anforderungen vom 23.09.2026). Intern = Direktbestellungen ausschliesslich
# bei Nike, adidas und The North Face; Dritte-Händler = alle anderen Marken
# direkt; Händler = Verkaufsläden in der Umgebung, die Ware abgeben.
ETIKETT_CODES = {
    "intersport": "111",
    "ecom": "555",
    "extern": "333",
    "drittanbieter": "999",
    "intern": "444",
}


def etikett_code(typ: str | None) -> str | None:
    """Etikett-Code einer Lieferantengruppe, `None` ohne Lieferant."""
    return ETIKETT_CODES.get(typ) if typ else None


def seed_lieferanten(session: Session) -> None:
    """Legt fehlende Lieferanten aus LIEFERANTEN_SEED an. Idempotent."""
    existing_names = set(session.scalars(select(Lieferant.name)).all())
    for data in LIEFERANTEN_SEED:
        if data["name"] not in existing_names:
            session.add(Lieferant(**data))
