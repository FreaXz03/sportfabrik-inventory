"""Seed-Daten für die Kassenkategorien: Hauptgruppe × Sportbereich, exakt wie
in der Kasse (Regel 8). Textil/Hartware/Schuhe haben dieselben 11
Sportbereiche, Velo und Food keinen. 35 Kombinationen total. Einzige Quelle
für diese Daten - Migration und Tests nutzen sie, damit beide garantiert
übereinstimmen (siehe app/core/lagerorte.py für dasselbe Muster).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Kategorie

SPORTBEREICHE = [
    "Velo",
    "Freizeit",
    "Tennis",
    "Winter",
    "Outdoor",
    "Fussball",
    "Kids",
    "Baden",
    "Indoor",
    "Running",
    "Rollsport",
]

HAUPTGRUPPEN_MIT_SPORTBEREICH = ["Textil", "Hartware", "Schuhe"]
HAUPTGRUPPEN_OHNE_SPORTBEREICH = ["Velo", "Food"]

KATEGORIEN_SEED = [
    {"hauptgruppe": hauptgruppe, "sportbereich": sportbereich}
    for hauptgruppe in HAUPTGRUPPEN_MIT_SPORTBEREICH
    for sportbereich in SPORTBEREICHE
] + [
    {"hauptgruppe": hauptgruppe, "sportbereich": None}
    for hauptgruppe in HAUPTGRUPPEN_OHNE_SPORTBEREICH
]


def seed_kategorien(session: Session) -> None:
    """Legt fehlende Kategorien aus KATEGORIEN_SEED an. Idempotent - bestehende
    Hauptgruppe/Sportbereich-Kombinationen werden übersprungen."""
    existing = set(
        session.execute(select(Kategorie.hauptgruppe, Kategorie.sportbereich)).all()
    )
    for data in KATEGORIEN_SEED:
        key = (data["hauptgruppe"], data["sportbereich"])
        if key not in existing:
            session.add(Kategorie(**data))
