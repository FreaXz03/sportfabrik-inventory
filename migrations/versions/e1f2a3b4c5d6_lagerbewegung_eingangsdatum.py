"""Eingangsdatum an der Lagerbewegung (Phase C, Teilaufgabe C4 - Umlagerung).

Die Reduktionsuhr einer Filiale laeuft ab dem letzten Wareneingang derselben
Artikelnummer in dieser Filiale (Regel 6). Eine Umlagerung ist kein
Wareneingang mit Beleg, kann die Uhr in der Zielfiliale aber trotzdem
starten:

* externer Standort (GEWA, VEBO, Dietikon) -> Filiale: die Ware kommt zum
  ersten Mal in eine Filiale, das Eingangsdatum wird erst jetzt gesetzt (D13),
  auf Wunsch rueckwirkend;
* Filiale -> Filiale, wenn die Zielfiliale diese Artikelnummer noch nie hatte:
  die Uhr startet ab Eintreffen (F11, 23.09.2026).

In allen anderen Faellen startet eine Umlagerung keine Uhr (F10). Welches
Datum gilt, steht deshalb an der Bewegung selbst: `eingangsdatum` ist leer,
wenn die Bewegung keine Uhr startet. Bestehende Zeilen sind durchweg Zugaenge,
deren Datum am Wareneingang steht - fuer sie bleibt die Spalte leer.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lagerbewegungen') as batch_op:
        batch_op.add_column(sa.Column('eingangsdatum', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('lagerbewegungen') as batch_op:
        batch_op.drop_column('eingangsdatum')
