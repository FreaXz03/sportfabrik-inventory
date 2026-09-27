"""Phase D, offene Fragen D-F1/D-F2/D-F3 (25.09.2026).

Drei neue Tabellen, keine Altdaten zu migrieren:

* `reduktionen_bestaetigt` (D-F1): eine Filiale bestätigt ein fälliges Modell
  als heruntergeschrieben - es verschwindet aus der fälligen Liste, bis die
  nächste Stufe fällig wird.
* `hinweise` (D-F2): Nachlieferungs-Hinweis, wenn ein Modell mit bereits
  reduziertem Altbestand Nachschub bekommt (keine Chargentrennung im
  Bestand, darum nur ein Hinweis statt automatischer Trennung).
* `reduktion_empfehlung_zentrale` (D-F3): die Zentrale empfiehlt je Modell
  und Filiale eine Stufe ab einem Datum, die Filiale übernimmt oder lehnt
  mit Grund ab.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reduktionen_bestaetigt',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('artikel_id', sa.Integer(), sa.ForeignKey('artikel.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('stufe', sa.Integer(), nullable=False),
        sa.Column('benutzer_kassennummer', sa.String(20), nullable=True),
        sa.Column('benutzer_name', sa.String(100), nullable=True),
        sa.Column('bestaetigt_am', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('artikel_id', 'lagerort_id', name='uq_reduktion_bestaetigt_artikel_lagerort'),
    )
    op.create_index('ix_reduktionen_bestaetigt_artikel_id', 'reduktionen_bestaetigt', ['artikel_id'])
    op.create_index('ix_reduktionen_bestaetigt_lagerort_id', 'reduktionen_bestaetigt', ['lagerort_id'])

    op.create_table(
        'hinweise',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('artikel_id', sa.Integer(), sa.ForeignKey('artikel.id', ondelete='CASCADE'), nullable=False),
        sa.Column('typ', sa.String(30), nullable=False),
        sa.Column('alte_stufe', sa.Integer(), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("typ IN ('nachlieferung_reduziert')", name='ck_hinweise_typ'),
    )
    op.create_index('ix_hinweise_lagerort_id', 'hinweise', ['lagerort_id'])
    op.create_index('ix_hinweise_artikel_id', 'hinweise', ['artikel_id'])

    op.create_table(
        'reduktion_empfehlung_zentrale',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('artikel_id', sa.Integer(), sa.ForeignKey('artikel.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('prozent', sa.Integer(), nullable=False),
        sa.Column('ab_datum', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='offen'),
        sa.Column('ablehnungsgrund', sa.String(200), nullable=True),
        sa.Column('gesetzt_von_kassennummer', sa.String(20), nullable=True),
        sa.Column('gesetzt_von_name', sa.String(100), nullable=True),
        sa.Column('gesetzt_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('beantwortet_von_name', sa.String(100), nullable=True),
        sa.Column('beantwortet_am', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('prozent IN (30, 50, 70)', name='ck_empfehlung_zentrale_prozent'),
        sa.CheckConstraint(
            "status IN ('offen', 'uebernommen', 'abgelehnt')", name='ck_empfehlung_zentrale_status'
        ),
    )
    op.create_index('ix_empfehlung_zentrale_artikel_id', 'reduktion_empfehlung_zentrale', ['artikel_id'])
    op.create_index('ix_empfehlung_zentrale_lagerort_id', 'reduktion_empfehlung_zentrale', ['lagerort_id'])


def downgrade():
    op.drop_index('ix_empfehlung_zentrale_lagerort_id', table_name='reduktion_empfehlung_zentrale')
    op.drop_index('ix_empfehlung_zentrale_artikel_id', table_name='reduktion_empfehlung_zentrale')
    op.drop_table('reduktion_empfehlung_zentrale')

    op.drop_index('ix_hinweise_artikel_id', table_name='hinweise')
    op.drop_index('ix_hinweise_lagerort_id', table_name='hinweise')
    op.drop_table('hinweise')

    op.drop_index('ix_reduktionen_bestaetigt_lagerort_id', table_name='reduktionen_bestaetigt')
    op.drop_index('ix_reduktionen_bestaetigt_artikel_id', table_name='reduktionen_bestaetigt')
    op.drop_table('reduktionen_bestaetigt')
