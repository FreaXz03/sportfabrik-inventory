"""Hauptgruppe ohne Sportbereich als Kassenkategorie (Punkt 1, 01.10.2026).

Textil, Hartware und Schuhe gibt es zusätzlich nur als Hauptgruppe, solange
der Sportbereich nicht bekannt ist (Erweiterung von Regel 8, von Fabian am
2026-10-01 bestätigt). Artikel mit FEDAS-Code, aber ohne Kategorie, weil nur
der Erlebnisbereich unbekannt war, bekommen die Hauptgruppe nachgetragen.
Von Hand gewählte oder bereits gesetzte Kategorien bleiben unberührt.
"""
from alembic import op

revision = 'a0b1c2d3e4f5'
down_revision = 'f9a0b1c2d3e4'
branch_labels = None
depends_on = None

# Ziffer 1 des FEDAS-Codes -> Hauptgruppe (dieselbe Zuordnung wie app/core/fedas.py).
_HAUPTGRUPPEN = {'1': 'Hartware', '2': 'Textil', '3': 'Schuhe'}


def upgrade():
    # Nur reine Statements (kein Lesen), damit `alembic upgrade --sql` geht.
    for ziffer, hauptgruppe in _HAUPTGRUPPEN.items():
        op.execute(
            "INSERT INTO kategorien (hauptgruppe, sportbereich) "
            f"SELECT '{hauptgruppe}', NULL WHERE NOT EXISTS "
            f"(SELECT 1 FROM kategorien WHERE hauptgruppe = '{hauptgruppe}' AND sportbereich IS NULL)"
        )
        op.execute(
            "UPDATE artikel SET kategorie_id = "
            f"(SELECT id FROM kategorien WHERE hauptgruppe = '{hauptgruppe}' AND sportbereich IS NULL) "
            "WHERE kategorie_id IS NULL AND kategorie_manuell = false "
            f"AND fedas_code IS NOT NULL AND length(fedas_code) >= 3 AND substr(fedas_code, 1, 1) = '{ziffer}'"
        )


def downgrade():
    # Artikel mit nur einer Hauptgruppe werden wieder kategorielos; die
    # Hauptgruppen-Kategorien verschwinden. Von Hand gewählte Zuordnungen
    # zu ihnen gehen dabei verloren.
    for hauptgruppe in _HAUPTGRUPPEN.values():
        op.execute(
            "UPDATE artikel SET kategorie_id = NULL WHERE kategorie_id IN "
            f"(SELECT id FROM kategorien WHERE hauptgruppe = '{hauptgruppe}' AND sportbereich IS NULL)"
        )
        op.execute(
            f"DELETE FROM kategorien WHERE hauptgruppe = '{hauptgruppe}' AND sportbereich IS NULL"
        )
