"""Zwei weitere externe Lagerorte: VEBO (Verarbeitung) und Lager Dietikon.

Konzeptaenderung: Es gibt nicht eine, sondern zwei externe Verarbeitungsstellen
(GEWA und VEBO, fachlich gleichwertig) und zusaetzlich ein externes Lager in
Dietikon. Alle drei laufen mit `verkauf = False` - daran haengt Regel 6
(Eingangsdatum und damit die Reduktionsuhr starten erst in einer Filiale), die
Logik in app/services/importer.py gilt dadurch unveraendert fuer alle drei.

GEWA wird nur umbenannt ("externes Lager" -> "externe Verarbeitung"), damit der
Unterschied zum reinen Lager Dietikon im Namen sichtbar ist.

Adressen von VEBO und Dietikon sind noch offen und werden nachgetragen, sobald
sie vorliegen (gebraucht erst fuer die Lagerort-Erkennung aus der Lieferadresse
in Phase B). Seed-Daten bewusst literal dupliziert - siehe a1b2c3d4e5f6.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None

_NEUE_LAGERORTE = [
    {
        "code": "VEBO",
        "name": "VEBO (externe Verarbeitung)",
        "strasse": None,
        "plz": None,
        "ort": None,
        "telefon": None,
        "email": None,
        "verkauf": False,
    },
    {
        "code": "DIETIKON",
        "name": "Lager Dietikon",
        "strasse": None,
        "plz": None,
        "ort": "Dietikon",
        "telefon": None,
        "email": None,
        "verkauf": False,
    },
]


def _lagerorte_table():
    return sa.table(
        'lagerorte',
        sa.column('code', sa.String()),
        sa.column('name', sa.String()),
        sa.column('strasse', sa.String()),
        sa.column('plz', sa.String()),
        sa.column('ort', sa.String()),
        sa.column('telefon', sa.String()),
        sa.column('email', sa.String()),
        sa.column('verkauf', sa.Boolean()),
    )


def upgrade():
    # Reine Datenmigration: im Offline-Modus (`alembic ... --sql`) gibt es keine
    # Verbindung, um vorhandene Codes zu pruefen - siehe a1b2c3d4e5f6.
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    vorhanden = set(
        connection.scalars(sa.text("SELECT code FROM lagerorte")).all()
    )
    fehlende = [lo for lo in _NEUE_LAGERORTE if lo["code"] not in vorhanden]
    if fehlende:
        op.bulk_insert(_lagerorte_table(), fehlende)
    connection.execute(
        sa.text("UPDATE lagerorte SET name = :name WHERE code = 'GEWA'"),
        {"name": "GEWA (externe Verarbeitung)"},
    )


def downgrade():
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    # Nur loeschen, solange nichts daran haengt - sonst lieber stehen lassen als
    # Bestand/Wareneingaenge mitzureissen ("nie verwerfen").
    for code in ("VEBO", "DIETIKON"):
        belegt = connection.scalar(
            sa.text(
                "SELECT 1 FROM lagerorte lo WHERE lo.code = :code AND ("
                "  EXISTS (SELECT 1 FROM bestand b WHERE b.lagerort_id = lo.id)"
                "  OR EXISTS (SELECT 1 FROM wareneingaenge w WHERE w.lagerort_id = lo.id)"
                "  OR EXISTS (SELECT 1 FROM dokumente d WHERE d.lagerort_id = lo.id)"
                "  OR EXISTS (SELECT 1 FROM lagerbewegungen lb WHERE lb.lagerort_id = lo.id)"
                "  OR EXISTS (SELECT 1 FROM benutzer_lagerorte bl WHERE bl.lagerort_id = lo.id)"
                ")"
            ),
            {"code": code},
        )
        if not belegt:
            connection.execute(
                sa.text("DELETE FROM lagerorte WHERE code = :code"), {"code": code}
            )
    connection.execute(
        sa.text("UPDATE lagerorte SET name = :name WHERE code = 'GEWA'"),
        {"name": "GEWA (externes Lager)"},
    )
