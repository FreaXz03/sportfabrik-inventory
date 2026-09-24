"""Filialcodes korrigieren: SF2 Conthey, SF3 Regensdorf, SF4 Haegendorf.

Die Zuordnung Code -> Filiale war seit der ersten Lagerorte-Migration falsch.
Bestaetigt von Fabian am 22.09.2026: richtig ist SF1 Volketswil, SF2 Conthey,
SF3 Regensdorf, SF4 Haegendorf. Bestaetigt wird das nebenbei von einem echten
Beleg - die ALPINA-Auftragsbestaetigung 160166 nennt "SF3 Regensdorf".

Korrigiert wird nur der **Code** der bestehenden Zeile; Name und Adresse
bleiben, wo sie sind. Buchungen haengen an `lagerorte.id`, nicht am Code -
damit behaelt jede bisher gebuchte Ware ihre Filiale, egal ob auf SF2-SF4
schon etwas gebucht wurde.

`lagerorte.code` ist eindeutig und die Korrektur ist ein Ringtausch
(SF2 -> SF3 -> SF4 -> SF2). Deshalb zwei Durchgaenge ueber Zwischencodes:
sonst kollidiert der zweite Ort mit dem Code, den der erste noch traegt.

Die alte Migration a1b2c3d4e5f6 bleibt unveraendert - sie war der damalige
Stand und laeuft auf bestehenden Datenbanken nicht noch einmal.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


# Ort -> Code. Der Ort ist der stabile Teil, der Code war der falsche.
RICHTIG = {'Conthey': 'SF2', 'Regensdorf': 'SF3', 'Hägendorf': 'SF4'}
VORHER = {'Regensdorf': 'SF2', 'Hägendorf': 'SF3', 'Conthey': 'SF4'}

lagerorte = sa.table(
    'lagerorte',
    sa.column('code', sa.String),
    sa.column('ort', sa.String),
)


def _codes_setzen(conn, zuordnung):
    """Setzt je Ort den Code, in zwei Durchgaengen. `conn` statt op.get_bind(),
    damit der Ringtausch auch im Test gegen eine echte Tabelle mit ihrer
    Eindeutigkeit laufen kann (tests/test_lagerorte.py)."""
    for ort, code in zuordnung.items():
        conn.execute(
            lagerorte.update().where(lagerorte.c.ort == ort).values(code='TMP' + code)
        )
    for ort, code in zuordnung.items():
        conn.execute(
            lagerorte.update().where(lagerorte.c.ort == ort).values(code=code)
        )


def upgrade():
    _codes_setzen(op.get_bind(), RICHTIG)


def downgrade():
    _codes_setzen(op.get_bind(), VORHER)
