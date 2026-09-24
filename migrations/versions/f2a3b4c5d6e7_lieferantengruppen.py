"""Lieferantengruppen mit Etikett-Codes (Anforderungen vom 23.09.2026).

Die Sportfabrik teilt ihre Ware nach Herkunft in fuenf Gruppen ein; der Code
steht auf dem Etikett:

    Intersport 111 · ECOM 555 · Haendler 333 · Dritte-Haendler 999 · Intern 444

`lieferanten.typ` kannte vier davon schon (`intersport`, `ecom`, `extern` =
Haendler, `drittanbieter` = Dritte-Haendler). Neu ist `intern`:
Direktbestellungen ausschliesslich bei Nike, adidas und The North Face. Der
Code selbst wird nicht gespeichert, sondern aus `typ` abgeleitet
(app/core/lieferanten.py) - eine Quelle, kein Auseinanderlaufen.

Dazu je Gruppe ein Lieferant, damit Ware von Hand (Seite „Erfassen") einer
Gruppe zugeordnet werden kann, solange es fuer die Quelle keinen eigenen
Parser gibt. Seed-Daten bewusst literal dupliziert - siehe a1b2c3d4e5f6.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None

ALT = "typ IN ('intersport', 'ecom', 'drittanbieter', 'extern')"
NEU = "typ IN ('intersport', 'ecom', 'drittanbieter', 'extern', 'intern')"

_NEUE_LIEFERANTEN = [
    {"name": "ECOM (Retouren Intersport-Onlineshop)", "typ": "ecom", "parser_key": None},
    {"name": "Händler (Restposten)", "typ": "extern", "parser_key": None},
    {"name": "Dritte-Händler (Marke direkt)", "typ": "drittanbieter", "parser_key": None},
    {"name": "Nike", "typ": "intern", "parser_key": None},
    {"name": "adidas", "typ": "intern", "parser_key": None},
    {"name": "The North Face", "typ": "intern", "parser_key": None},
]


def upgrade():
    with op.batch_alter_table('lieferanten') as batch_op:
        batch_op.drop_constraint('ck_lieferanten_typ', type_='check')
        batch_op.create_check_constraint('ck_lieferanten_typ', NEU)
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    vorhanden = set(connection.scalars(sa.text("SELECT name FROM lieferanten")).all())
    for eintrag in _NEUE_LIEFERANTEN:
        if eintrag["name"] not in vorhanden:
            connection.execute(
                sa.text(
                    "INSERT INTO lieferanten (name, typ, parser_key) "
                    "VALUES (:name, :typ, :parser_key)"
                ),
                eintrag,
            )


def downgrade():
    if not context.is_offline_mode():
        connection = op.get_bind()
        # Nur loeschen, solange nichts daran haengt ("nie verwerfen").
        for eintrag in _NEUE_LIEFERANTEN:
            belegt = connection.scalar(
                sa.text(
                    "SELECT 1 FROM lieferanten l WHERE l.name = :name AND ("
                    "  EXISTS (SELECT 1 FROM artikel a WHERE a.lieferant_id = l.id)"
                    "  OR EXISTS (SELECT 1 FROM dokumente d WHERE d.lieferant_id = l.id))"
                ),
                {"name": eintrag["name"]},
            )
            if not belegt:
                connection.execute(
                    sa.text("DELETE FROM lieferanten WHERE name = :name"),
                    {"name": eintrag["name"]},
                )
        # Ein Lieferant `intern`, an dem etwas haengt, wird zu Dritte-Haendler -
        # sonst liesse sich der alte Check nicht wieder anlegen.
        connection.execute(
            sa.text("UPDATE lieferanten SET typ = 'drittanbieter' WHERE typ = 'intern'")
        )
    with op.batch_alter_table('lieferanten') as batch_op:
        batch_op.drop_constraint('ck_lieferanten_typ', type_='check')
        batch_op.create_check_constraint('ck_lieferanten_typ', ALT)
