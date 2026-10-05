"""Package 4a (05.10.2026): customer returns and held stock.

* `bestand.menge_gesperrt`: Rueckware in Pruefung, nicht verkaeuflich.
* `lagerbewegungen.bestandsart` (verkaufbar | gesperrt) und die neuen Typen
  `retoure` und `freigabe`. Bestehende Zeilen sind `verkaufbar`.
* Neue Tabelle `retouren` (Kundenretoure mit Grund, Zustand, Erstattungs-
  verweis, Status und Ergebnis).
"""
from alembic import op
import sqlalchemy as sa

revision = 'b7c8d9e0f1a2'
down_revision = 'a6b7c8d9e0f1'
branch_labels = None
depends_on = None

_TYPEN_ALT = "typ IN ('zugang', 'verkauf', 'ausbuchung', 'korrektur', 'umlagerung')"
_TYPEN_NEU = "typ IN ('zugang', 'verkauf', 'ausbuchung', 'korrektur', 'umlagerung', 'retoure', 'freigabe')"


def upgrade():
    with op.batch_alter_table('bestand') as batch_op:
        batch_op.add_column(
            sa.Column('menge_gesperrt', sa.Numeric(10, 2), nullable=False, server_default=sa.text('0'))
        )
    with op.batch_alter_table('lagerbewegungen') as batch_op:
        batch_op.add_column(
            sa.Column('bestandsart', sa.String(length=12), nullable=False, server_default='verkaufbar')
        )
        batch_op.drop_constraint('ck_lagerbewegungen_typ', type_='check')
        batch_op.create_check_constraint('ck_lagerbewegungen_typ', _TYPEN_NEU)
        batch_op.create_check_constraint(
            'ck_lagerbewegungen_bestandsart', "bestandsart IN ('verkaufbar', 'gesperrt')"
        )
    op.create_table(
        'retouren',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('varianten_id', sa.Integer(), sa.ForeignKey('varianten.id'), nullable=False),
        sa.Column('menge', sa.Numeric(10, 2), nullable=False),
        sa.Column('grund', sa.String(length=20), nullable=False),
        sa.Column('freitext', sa.String(length=200), nullable=True),
        sa.Column('zustand', sa.String(length=20), nullable=False),
        sa.Column('verkauf_bewegung_id', sa.Integer(), sa.ForeignKey('lagerbewegungen.id'), nullable=True),
        sa.Column('erstattungsreferenz', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('ergebnis', sa.String(length=20), nullable=True),
        sa.Column('erfasst_von_kassennummer', sa.String(length=20), nullable=True),
        sa.Column('erfasst_von_name', sa.String(length=100), nullable=True),
        sa.Column('erfasst_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('entschieden_von_kassennummer', sa.String(length=20), nullable=True),
        sa.Column('entschieden_von_name', sa.String(length=100), nullable=True),
        sa.Column('entschieden_am', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('beantragt', 'in_pruefung', 'abgeschlossen', 'abgelehnt')",
            name='ck_retouren_status',
        ),
        sa.CheckConstraint(
            "ergebnis IS NULL OR ergebnis IN ('freigegeben', 'lieferant', 'abgeschrieben')",
            name='ck_retouren_ergebnis',
        ),
    )
    op.create_index('ix_retouren_lagerort_id', 'retouren', ['lagerort_id'])
    op.create_index('ix_retouren_varianten_id', 'retouren', ['varianten_id'])
    op.create_index('ix_retouren_status', 'retouren', ['status'])


def downgrade():
    # Nie verwerfen: gibt es schon Retouren oder gesperrte Bewegungen, bricht
    # das Zurueckrollen ab, statt Journal und Nachweise zu verlieren.
    verbindung = op.get_bind()
    belegt = verbindung.scalar(
        sa.text(
            "SELECT 1 WHERE EXISTS (SELECT 1 FROM retouren) "
            "OR EXISTS (SELECT 1 FROM lagerbewegungen WHERE typ IN ('retoure', 'freigabe') "
            "OR bestandsart = 'gesperrt')"
        )
    )
    if belegt:
        raise RuntimeError("Retouren oder gesperrte Bewegungen vorhanden - Downgrade abgebrochen.")
    op.drop_index('ix_retouren_status', table_name='retouren')
    op.drop_index('ix_retouren_varianten_id', table_name='retouren')
    op.drop_index('ix_retouren_lagerort_id', table_name='retouren')
    op.drop_table('retouren')
    with op.batch_alter_table('lagerbewegungen') as batch_op:
        batch_op.drop_constraint('ck_lagerbewegungen_bestandsart', type_='check')
        batch_op.drop_constraint('ck_lagerbewegungen_typ', type_='check')
        batch_op.create_check_constraint('ck_lagerbewegungen_typ', _TYPEN_ALT)
        batch_op.drop_column('bestandsart')
    with op.batch_alter_table('bestand') as batch_op:
        batch_op.drop_column('menge_gesperrt')
