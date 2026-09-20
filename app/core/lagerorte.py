"""Seed-Daten für die Lagerorte: SF1-SF4 (Filialen mit Verkauf) und GEWA
(externes Aufbereitungslager, kein Verkauf). Adressen aus docs/projekt-kontext.md
Abschnitt 1. Einzige Quelle für diese Daten - Migration und Tests nutzen sie,
damit beide garantiert übereinstimmen.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Lagerort

LAGERORTE_SEED = [
    {
        "code": "SF1",
        "name": "Volketswil",
        "strasse": "Industriestrasse 21",
        "plz": "8604",
        "ort": "Volketswil",
        "telefon": "043 444 93 33",
        "email": "volketswil@sportfabrik.ch",
        "verkauf": True,
    },
    {
        "code": "SF2",
        "name": "Regensdorf",
        "strasse": "Althardstrasse 10",
        "plz": "8105",
        "ort": "Regensdorf",
        "telefon": "044 840 05 90",
        "email": "regensdorf@sportfabrik.ch",
        "verkauf": True,
    },
    {
        "code": "SF3",
        "name": "Hägendorf",
        "strasse": "Industriestrasse West 40/42",
        "plz": "4614",
        "ort": "Hägendorf",
        "telefon": "062 216 53 88",
        "email": "haegendorf@sportfabrik.ch",
        "verkauf": True,
    },
    {
        "code": "SF4",
        "name": "Conthey",
        "strasse": "Route Cantonale 7",
        "plz": "1964",
        "ort": "Conthey",
        "telefon": "027 322 75 83",
        "email": "conthey@sportfabrik.ch",
        "verkauf": True,
    },
    {
        "code": "GEWA",
        "name": "GEWA (externes Lager)",
        "strasse": "Grubenstrasse 22",
        "plz": "3322",
        "ort": "Urtenen-Schönbühl",
        "telefon": None,
        "email": None,
        "verkauf": False,
    },
]


def seed_lagerorte(session: Session) -> None:
    """Legt fehlende Lagerorte aus LAGERORTE_SEED an. Idempotent - bestehende
    Codes werden übersprungen, damit das mehrfach gefahrlos aufgerufen werden
    kann (z.B. in Tests)."""
    existing_codes = set(session.scalars(select(Lagerort.code)).all())
    for data in LAGERORTE_SEED:
        if data["code"] not in existing_codes:
            session.add(Lagerort(**data))
