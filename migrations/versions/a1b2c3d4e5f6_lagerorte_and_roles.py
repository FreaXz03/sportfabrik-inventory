"""Lagerorte (SF1-SF4 + GEWA), Benutzer-Lagerort-Zuordnung (m:n) und Admin-Rolle.

Bestehende Benutzer werden auf SF1 (Volketswil) als primäre Filiale gesetzt,
siehe CLAUDE.md ("Altdaten -> Lagerort SF1").
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'e901abc23456'
branch_labels = None
depends_on = None

_LAGERORTE_SEED = [
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


def upgrade():
    op.create_table(
        'lagerorte',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(10), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('strasse', sa.String(200), nullable=True),
        sa.Column('plz', sa.String(10), nullable=True),
        sa.Column('ort', sa.String(100), nullable=True),
        sa.Column('telefon', sa.String(30), nullable=True),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column(
            'verkauf', sa.Boolean(), nullable=False, server_default=sa.text('true')
        ),
    )
    op.create_index('ix_lagerorte_code', 'lagerorte', ['code'], unique=True)

    op.create_table(
        'benutzer_lagerorte',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column(
            'lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), primary_key=True
        ),
        sa.Column(
            'ist_primaer', sa.Boolean(), nullable=False, server_default=sa.text('false')
        ),
    )

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('ck_users_chef_has_password', type_='check')
        batch_op.drop_constraint('ck_users_role', type_='check')
        batch_op.create_check_constraint(
            'ck_users_role', "role IN ('mitarbeiter', 'chef', 'admin')"
        )
        batch_op.create_check_constraint(
            'ck_users_chef_has_password',
            "(role IN ('chef', 'admin') AND password_hash IS NOT NULL) OR "
            "(role = 'mitarbeiter' AND password_hash IS NULL)",
        )

    lagerorte = sa.table(
        'lagerorte',
        sa.column('id', sa.Integer()),
        sa.column('code', sa.String()),
        sa.column('name', sa.String()),
        sa.column('strasse', sa.String()),
        sa.column('plz', sa.String()),
        sa.column('ort', sa.String()),
        sa.column('telefon', sa.String()),
        sa.column('email', sa.String()),
        sa.column('verkauf', sa.Boolean()),
    )
    op.bulk_insert(lagerorte, _LAGERORTE_SEED)

    # Die folgende Zuordnung bestehender Benutzer braucht eine echte Verbindung
    # (SF1-Id und vorhandene Benutzer nachschlagen) und läuft daher nicht im
    # Offline-Modus (`alembic ... --sql`, reine DDL-Vorschau ohne DB).
    if not context.is_offline_mode():
        connection = op.get_bind()
        sf1_id = connection.execute(
            sa.text("SELECT id FROM lagerorte WHERE code = 'SF1'")
        ).scalar_one()
        user_ids = connection.execute(sa.text("SELECT id FROM users")).scalars().all()
        if user_ids:
            benutzer_lagerorte = sa.table(
                'benutzer_lagerorte',
                sa.column('user_id', sa.Integer()),
                sa.column('lagerort_id', sa.Integer()),
                sa.column('ist_primaer', sa.Boolean()),
            )
            op.bulk_insert(
                benutzer_lagerorte,
                [
                    {"user_id": user_id, "lagerort_id": sf1_id, "ist_primaer": True}
                    for user_id in user_ids
                ],
            )


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('ck_users_chef_has_password', type_='check')
        batch_op.drop_constraint('ck_users_role', type_='check')
        batch_op.create_check_constraint(
            'ck_users_role', "role IN ('mitarbeiter', 'chef')"
        )
        batch_op.create_check_constraint(
            'ck_users_chef_has_password',
            "(role = 'chef' AND password_hash IS NOT NULL) OR "
            "(role = 'mitarbeiter' AND password_hash IS NULL)",
        )
    op.drop_table('benutzer_lagerorte')
    op.drop_index('ix_lagerorte_code', table_name='lagerorte')
    op.drop_table('lagerorte')
