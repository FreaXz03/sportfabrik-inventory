"""Belegnummer nur je Lieferant eindeutig (Phase B, Teilaufgabe B2).

`dokumente.dokumentnummer` war global eindeutig. Solange nur INTERSPORT
liefert, ist das folgenlos - mit dem zweiten Lieferanten wuerde der Import
eine fremde Rechnung abweisen, nur weil sie zufaellig dieselbe Belegnummer
traegt (Belegnummern sind Lieferantensache und ueberschneiden sich zwangslos).
Diese Migration ersetzt die globale Eindeutigkeit durch
UNIQUE (lieferant_id, dokumentnummer).

`datei_hash` bleibt global eindeutig: dieselbe Datei ist dasselbe Dokument,
egal von wem.

Bestehende Daten koennen die neue, schwaechere Regel nicht verletzen - die
Migration braucht darum keine Datenbereinigung. Der Weg zurueck
(`downgrade`) schlaegt dagegen fehl, sobald zwei Lieferanten dieselbe Nummer
benutzt haben; das ist gewollt, denn dann gibt es keine global eindeutige
Nummer mehr.

Zwei Objekte muessen weg, weil Migration c3d4e5f6a7b8 beides angelegt hat:
die Spalten-Eindeutigkeit (in PostgreSQL als Constraint
`dokumente_dokumentnummer_key`) und zusaetzlich einen eigenen UNIQUE-Index
`ix_dokumente_dokumentnummer`. Der Index bleibt, nur nicht mehr eindeutig.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None

UNIQUE_NAME = 'uq_dokumente_lieferant_dokumentnummer'
INDEX_NAME = 'ix_dokumente_dokumentnummer'


def _dokumente(mit_kombi_constraint: bool) -> sa.Table:
    """Tabellendefinition fuer SQLites Tabellen-Neuaufbau (`copy_from`).

    SQLite kann einen Constraint nicht einzeln loeschen, und die alte
    Spalten-Eindeutigkeit hat dort gar keinen Namen - Alembic baut die Tabelle
    deshalb aus dieser Definition neu auf und kopiert die Daten. Zwei
    Besonderheiten von `copy_from`: was hier fehlt, ist nach dem Neuaufbau weg
    (so verschwindet die namenlose Spalten-Eindeutigkeit), und was der Batch
    loeschen soll, muss hier stehen (darum der Schalter fuer den
    Kombi-Constraint). Spalten wie in Migration c3d4e5f6a7b8. (PostgreSQL
    braucht das nicht, siehe upgrade().)
    """
    return sa.Table(
        'dokumente',
        sa.MetaData(),
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lieferant_id', sa.Integer(), sa.ForeignKey('lieferanten.id'), nullable=True, index=True),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=True, index=True),
        sa.Column('typ', sa.String(30), nullable=False),
        sa.Column('dokumentnummer', sa.String(100), nullable=False, index=True),
        sa.Column('dokumentdatum', sa.Date(), nullable=True),
        sa.Column('belegdatum', sa.Date(), nullable=True),
        sa.Column('dateiname', sa.String(500), nullable=True),
        sa.Column('datei_hash', sa.String(64), nullable=True, unique=True),
        sa.Column('hochgeladen_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('hochgeladen_von_kassennummer', sa.String(20), nullable=True),
        sa.Column('hochgeladen_von_name', sa.String(100), nullable=True),
        sa.Column('ocr_verwendet', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.CheckConstraint(
            "typ IN ('rechnung', 'lieferschein', 'auftragsbestaetigung', 'bestellung')",
            name='ck_dokumente_typ',
        ),
        *(
            [sa.UniqueConstraint('lieferant_id', 'dokumentnummer', name=UNIQUE_NAME)]
            if mit_kombi_constraint
            else []
        ),
    )


def _indizes_neu_anlegen(dokumentnummer_eindeutig: bool) -> None:
    """Die drei Indizes aus c3d4e5f6a7b8 nach SQLites Tabellen-Neuaufbau wieder
    anlegen: der Neuaufbau nimmt sie mit der alten Tabelle mit, `copy_from`
    legt sie aber nicht von selbst wieder an."""
    op.create_index('ix_dokumente_lieferant_id', 'dokumente', ['lieferant_id'])
    op.create_index('ix_dokumente_lagerort_id', 'dokumente', ['lagerort_id'])
    op.create_index(
        INDEX_NAME, 'dokumente', ['dokumentnummer'], unique=dokumentnummer_eindeutig
    )


def upgrade():
    if op.get_context().dialect.name == 'postgresql':
        # Von `unique=True` an der Spalte automatisch benannter Constraint;
        # IF EXISTS, weil eine mit dem Modell erzeugte Datenbank
        # (Base.metadata.create_all, z. B. in Tests) ihn nicht hat.
        op.execute(
            'ALTER TABLE dokumente DROP CONSTRAINT IF EXISTS dokumente_dokumentnummer_key'
        )
        op.drop_index(INDEX_NAME, table_name='dokumente')
        op.create_index(INDEX_NAME, 'dokumente', ['dokumentnummer'])
        op.create_unique_constraint(
            UNIQUE_NAME, 'dokumente', ['lieferant_id', 'dokumentnummer']
        )
        return
    with op.batch_alter_table(
        'dokumente',
        copy_from=_dokumente(mit_kombi_constraint=False),
        recreate='always',
    ) as batch_op:
        batch_op.create_unique_constraint(UNIQUE_NAME, ['lieferant_id', 'dokumentnummer'])
    _indizes_neu_anlegen(dokumentnummer_eindeutig=False)


def downgrade():
    if op.get_context().dialect.name == 'postgresql':
        op.drop_constraint(UNIQUE_NAME, 'dokumente', type_='unique')
        op.drop_index(INDEX_NAME, table_name='dokumente')
        op.create_index(INDEX_NAME, 'dokumente', ['dokumentnummer'], unique=True)
        op.create_unique_constraint(
            'dokumente_dokumentnummer_key', 'dokumente', ['dokumentnummer']
        )
        return
    with op.batch_alter_table(
        'dokumente',
        copy_from=_dokumente(mit_kombi_constraint=True),
        recreate='always',
    ) as batch_op:
        batch_op.drop_constraint(UNIQUE_NAME, type_='unique')
        batch_op.create_unique_constraint('dokumente_dokumentnummer_key', ['dokumentnummer'])
    _indizes_neu_anlegen(dokumentnummer_eindeutig=True)
