"""Neues Datenmodell (Phase A Punkt 3): Lieferanten, Kategorien, Artikel/
Varianten, Preise, Dokumente, Wareneingaenge, Lagerbewegungen, Bestand.

Migriert alle bestehenden Daten (products, invoices, invoice_items,
invoice_item_sources, article_notes) verlustfrei in die neuen Tabellen -
die alten Tabellen bleiben unangetastet in der Datenbank (kein DROP, "nie
verwerfen"), werden aber ab dieser Migration von der App nicht mehr benutzt.

Bekannte Einschraenkung der Migration (siehe docs/datenmodell.md): jede
migrierte Rechnungsposition erzeugt eine Lagerbewegung vom Typ 'zugang' an
SF1, `bestand` wird daraus aggregiert. Da das alte System nie Verkaeufe
erfasst hat, entspricht der so entstehende Bestand der kumulierten
historischen Wareneingaenge, nicht dem tatsaechlichen physischen Bestand -
das wird erst mit dem manuellen Ausbuchen (Phase C) und/oder einer
Inventur korrigiert.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Fixe Seed-Daten (dieselben wie app/core/kategorien.py / app/core/lieferanten.py
# - hier dupliziert, damit die Migration nicht von App-Code abhaengt, der sich
# spaeter aendern koennte; siehe bestehende Migrationen a1b2c3d4e5f6 fuer
# dasselbe Muster).
# ---------------------------------------------------------------------------

_SPORTBEREICHE = [
    "Velo", "Freizeit", "Tennis", "Winter", "Outdoor", "Fussball",
    "Kids", "Baden", "Indoor", "Running", "Rollsport",
]
_HAUPTGRUPPEN_MIT_SPORTBEREICH = ["Textil", "Hartware", "Schuhe"]
_HAUPTGRUPPEN_OHNE_SPORTBEREICH = ["Velo", "Food"]

_KATEGORIEN_SEED = [
    {"id": i + 1, "hauptgruppe": hg, "sportbereich": sb}
    for i, (hg, sb) in enumerate(
        [(hg, sb) for hg in _HAUPTGRUPPEN_MIT_SPORTBEREICH for sb in _SPORTBEREICHE]
        + [(hg, None) for hg in _HAUPTGRUPPEN_OHNE_SPORTBEREICH]
    )
]

_INTERSPORT_LIEFERANT_ID = 1
_LIEFERANTEN_SEED = [
    {
        "id": _INTERSPORT_LIEFERANT_ID,
        "name": "INTERSPORT Schweiz AG",
        "typ": "intersport",
        "parser_key": "intersport",
    },
]


def upgrade():
    _create_tables()
    _seed_reference_data()

    with op.batch_alter_table('article_notes') as batch_op:
        batch_op.add_column(
            sa.Column('artikel_id', sa.Integer(), sa.ForeignKey('artikel.id'), nullable=True)
        )

    # Die eigentliche Datenmigration braucht eine echte Verbindung (bestehende
    # Zeilen lesen und gruppieren) und laeuft daher nicht im Offline-Modus
    # (`alembic ... --sql`, reine DDL-Vorschau ohne DB) - siehe a1b2c3d4e5f6
    # fuer dasselbe Muster.
    if not context.is_offline_mode():
        _migrate_existing_data(op.get_bind())

    with op.batch_alter_table('article_notes') as batch_op:
        batch_op.alter_column('artikel_id', nullable=False)
        batch_op.drop_column('product_id')
    # DROP COLUMN product_id hat den darauf liegenden Index bereits mitgeloescht
    # (Postgres: automatisch per CASCADE; SQLite-Batch-Modus: Tabelle wird ohne
    # den alten Index neu aufgebaut) - ihn hier nochmal droppen wuerde fehlschlagen.
    op.create_index('ix_article_notes_artikel_id', 'article_notes', ['artikel_id'])


def _create_tables():
    op.create_table(
        'lieferanten',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False, unique=True),
        sa.Column('typ', sa.String(20), nullable=False),
        sa.Column('parser_key', sa.String(50), nullable=True),
        sa.CheckConstraint(
            "typ IN ('intersport', 'ecom', 'drittanbieter', 'extern')",
            name='ck_lieferanten_typ',
        ),
    )

    op.create_table(
        'kategorien',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('hauptgruppe', sa.String(20), nullable=False),
        sa.Column('sportbereich', sa.String(20), nullable=True),
        sa.CheckConstraint(
            "hauptgruppe IN ('Textil', 'Hartware', 'Schuhe', 'Velo', 'Food')",
            name='ck_kategorien_hauptgruppe',
        ),
        sa.UniqueConstraint('hauptgruppe', 'sportbereich', name='uq_kategorien_kombi'),
    )

    op.create_table(
        'dokumente',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lieferant_id', sa.Integer(), sa.ForeignKey('lieferanten.id'), nullable=True),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=True),
        sa.Column('typ', sa.String(30), nullable=False),
        sa.Column('dokumentnummer', sa.String(100), nullable=False, unique=True),
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
    )
    op.create_index('ix_dokumente_lieferant_id', 'dokumente', ['lieferant_id'])
    op.create_index('ix_dokumente_lagerort_id', 'dokumente', ['lagerort_id'])
    op.create_index('ix_dokumente_dokumentnummer', 'dokumente', ['dokumentnummer'], unique=True)

    op.create_table(
        'artikel',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lieferant_id', sa.Integer(), sa.ForeignKey('lieferanten.id'), nullable=False),
        sa.Column('marke', sa.String(100), nullable=True),
        sa.Column('lieferanten_artikelnr', sa.String(100), nullable=True),
        sa.Column('bezeichnung', sa.String(500), nullable=True),
        sa.Column('kategorie_id', sa.Integer(), sa.ForeignKey('kategorien.id'), nullable=True),
        sa.Column('fedas_code', sa.String(10), nullable=True),
    )
    op.create_index('ix_artikel_lieferant_id', 'artikel', ['lieferant_id'])
    op.create_index('ix_artikel_lieferanten_artikelnr', 'artikel', ['lieferanten_artikelnr'])

    op.create_table(
        'varianten',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('artikel_id', sa.Integer(), sa.ForeignKey('artikel.id'), nullable=False),
        sa.Column('farbe', sa.String(250), nullable=True),
        sa.Column('groesse', sa.String(100), nullable=True),
        sa.Column('ean', sa.String(30), nullable=True, unique=True),
        sa.Column('ean_intern', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('first_seen', sa.Date(), nullable=True),
        sa.Column('last_seen', sa.Date(), nullable=True),
    )
    op.create_index('ix_varianten_artikel_id', 'varianten', ['artikel_id'])
    op.create_index('ix_varianten_ean', 'varianten', ['ean'], unique=True)

    op.create_table(
        'preise',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('varianten_id', sa.Integer(), sa.ForeignKey('varianten.id'), nullable=False),
        sa.Column('uvp', sa.Numeric(10, 2), nullable=False),
        sa.Column('ek', sa.Numeric(10, 2), nullable=True),
        sa.Column('datum', sa.Date(), nullable=True),
        sa.Column('dokument_id', sa.Integer(), sa.ForeignKey('dokumente.id'), nullable=True),
    )
    op.create_index('ix_preise_varianten_id', 'preise', ['varianten_id'])

    op.create_table(
        'wareneingaenge',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('dokument_id', sa.Integer(), sa.ForeignKey('dokumente.id'), nullable=False),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('eingangsdatum', sa.Date(), nullable=True),
        sa.CheckConstraint(
            "status IN ('erwartet', 'eingetroffen')", name='ck_wareneingaenge_status'
        ),
    )
    op.create_index('ix_wareneingaenge_dokument_id', 'wareneingaenge', ['dokument_id'])
    op.create_index('ix_wareneingaenge_lagerort_id', 'wareneingaenge', ['lagerort_id'])

    op.create_table(
        'wareneingang_positionen',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('wareneingang_id', sa.Integer(), sa.ForeignKey('wareneingaenge.id'), nullable=False),
        sa.Column('varianten_id', sa.Integer(), sa.ForeignKey('varianten.id'), nullable=False),
        sa.Column('menge', sa.Numeric(10, 2), nullable=True),
        sa.Column('einheit', sa.String(30), nullable=True),
        sa.Column('uvp', sa.Numeric(10, 2), nullable=True),
        sa.Column('ek', sa.Numeric(10, 2), nullable=True),
    )
    op.create_index('ix_wareneingang_positionen_wareneingang_id', 'wareneingang_positionen', ['wareneingang_id'])
    op.create_index('ix_wareneingang_positionen_varianten_id', 'wareneingang_positionen', ['varianten_id'])

    op.create_table(
        'wareneingang_positionen_quelle',
        sa.Column('position_id', sa.Integer(), sa.ForeignKey('wareneingang_positionen.id'), primary_key=True),
        sa.Column('data', sa.JSON(), nullable=False),
    )

    op.create_table(
        'lagerbewegungen',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), nullable=False),
        sa.Column('varianten_id', sa.Integer(), sa.ForeignKey('varianten.id'), nullable=False),
        sa.Column('typ', sa.String(20), nullable=False),
        sa.Column('menge', sa.Numeric(10, 2), nullable=False),
        sa.Column('grund', sa.String(200), nullable=True),
        sa.Column('wareneingang_position_id', sa.Integer(), sa.ForeignKey('wareneingang_positionen.id'), nullable=True),
        sa.Column('benutzer_kassennummer', sa.String(20), nullable=True),
        sa.Column('benutzer_name', sa.String(100), nullable=True),
        sa.Column('zeitpunkt', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "typ IN ('zugang', 'verkauf', 'ausbuchung', 'korrektur', 'umlagerung')",
            name='ck_lagerbewegungen_typ',
        ),
    )
    op.create_index('ix_lagerbewegungen_lagerort_id', 'lagerbewegungen', ['lagerort_id'])
    op.create_index('ix_lagerbewegungen_varianten_id', 'lagerbewegungen', ['varianten_id'])

    op.create_table(
        'bestand',
        sa.Column('varianten_id', sa.Integer(), sa.ForeignKey('varianten.id'), primary_key=True),
        sa.Column('lagerort_id', sa.Integer(), sa.ForeignKey('lagerorte.id'), primary_key=True),
        sa.Column('menge', sa.Numeric(10, 2), nullable=False, server_default=sa.text('0')),
        sa.Column('aeltestes_eingangsdatum', sa.Date(), nullable=True),
    )


def _seed_reference_data():
    lieferanten = sa.table(
        'lieferanten',
        sa.column('id', sa.Integer()),
        sa.column('name', sa.String()),
        sa.column('typ', sa.String()),
        sa.column('parser_key', sa.String()),
    )
    op.bulk_insert(lieferanten, _LIEFERANTEN_SEED)

    kategorien = sa.table(
        'kategorien',
        sa.column('id', sa.Integer()),
        sa.column('hauptgruppe', sa.String()),
        sa.column('sportbereich', sa.String()),
    )
    op.bulk_insert(kategorien, _KATEGORIEN_SEED)


def _migrate_existing_data(connection):
    products = sa.table(
        'products',
        sa.column('id', sa.Integer()), sa.column('brand', sa.String()),
        sa.column('supplier_article_no', sa.String()), sa.column('article_no', sa.String()),
        sa.column('ean', sa.String()), sa.column('description', sa.String()),
        sa.column('color', sa.String()), sa.column('size', sa.String()),
        sa.column('first_seen', sa.Date()), sa.column('last_seen', sa.Date()),
    )
    invoices = sa.table(
        'invoices',
        sa.column('id', sa.Integer()), sa.column('invoice_number', sa.String()),
        sa.column('invoice_date', sa.Date()), sa.column('document_date', sa.Date()),
        sa.column('filename', sa.String()), sa.column('file_hash', sa.String()),
        sa.column('uploaded_at', sa.DateTime()),
        sa.column('imported_by_kassennummer', sa.String()), sa.column('imported_by_name', sa.String()),
        sa.column('ocr_used', sa.Boolean()),
    )
    invoice_items = sa.table(
        'invoice_items',
        sa.column('id', sa.Integer()), sa.column('invoice_id', sa.Integer()),
        sa.column('product_id', sa.Integer()), sa.column('quantity', sa.Numeric()),
        sa.column('unit', sa.String()), sa.column('uvp', sa.Numeric()),
    )
    invoice_item_sources = sa.table(
        'invoice_item_sources',
        sa.column('item_id', sa.Integer()), sa.column('data', sa.JSON()),
    )
    article_notes_old = sa.table(
        'article_notes', sa.column('id', sa.Integer()), sa.column('product_id', sa.Integer()),
    )

    product_rows = connection.execute(sa.select(products)).mappings().all()
    if not product_rows:
        return  # frische/leere Datenbank (z.B. Tests) - nichts zu migrieren

    sf1_id = connection.execute(
        sa.text("SELECT id FROM lagerorte WHERE code = 'SF1'")
    ).scalar_one()

    # --- artikel + varianten -------------------------------------------
    # Gleiche Gruppierung wie bisher app/services/article_groups.py zur
    # Laufzeit: gleiche Marke (ohne Gross-/Kleinschreibung, getrimmt) UND
    # gleiche, nicht-leere Lieferanten-Artikelnummer (getrimmt) = ein
    # Artikel. Fehlt die Nummer, bleibt jedes Produkt ein eigener Artikel.
    artikel_rows = []
    varianten_rows = []
    group_to_artikel_id = {}
    product_to_varianten_id = {}
    varianten_id_to_artikel_id = {}
    next_artikel_id = 1
    next_varianten_id = 1

    for row in sorted(product_rows, key=lambda r: r["id"]):
        supplier_no = (row["supplier_article_no"] or "").strip()
        brand_key = (row["brand"] or "").strip().lower()
        group_key = (brand_key, supplier_no) if supplier_no else ("__singleton__", row["id"])

        artikel_id = group_to_artikel_id.get(group_key)
        if artikel_id is None:
            artikel_id = next_artikel_id
            next_artikel_id += 1
            group_to_artikel_id[group_key] = artikel_id
            artikel_rows.append({
                "id": artikel_id,
                "lieferant_id": _INTERSPORT_LIEFERANT_ID,
                "marke": row["brand"],
                "lieferanten_artikelnr": row["supplier_article_no"],
                "bezeichnung": row["description"],
                "kategorie_id": None,
                "fedas_code": None,
            })

        varianten_id = next_varianten_id
        next_varianten_id += 1
        product_to_varianten_id[row["id"]] = varianten_id
        varianten_id_to_artikel_id[varianten_id] = artikel_id
        varianten_rows.append({
            "id": varianten_id,
            "artikel_id": artikel_id,
            "farbe": row["color"],
            "groesse": row["size"],
            "ean": row["ean"],
            "ean_intern": False,
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
        })

    _bulk_insert_with_id_column(connection, 'artikel',
        ['id', 'lieferant_id', 'marke', 'lieferanten_artikelnr', 'bezeichnung', 'kategorie_id', 'fedas_code'],
        artikel_rows)
    _bulk_insert_with_id_column(connection, 'varianten',
        ['id', 'artikel_id', 'farbe', 'groesse', 'ean', 'ean_intern', 'first_seen', 'last_seen'],
        varianten_rows)

    # --- dokumente + wareneingaenge --------------------------------------
    invoice_rows = connection.execute(sa.select(invoices)).mappings().all()
    dokument_rows = []
    wareneingang_rows = []
    invoice_to_dokument_id = {}
    invoice_to_wareneingang_id = {}
    next_dokument_id = 1
    next_wareneingang_id = 1

    for row in sorted(invoice_rows, key=lambda r: r["id"]):
        dokument_id = next_dokument_id
        next_dokument_id += 1
        invoice_to_dokument_id[row["id"]] = dokument_id
        dokument_rows.append({
            "id": dokument_id,
            "lieferant_id": _INTERSPORT_LIEFERANT_ID,
            "lagerort_id": sf1_id,
            "typ": "rechnung",
            "dokumentnummer": row["invoice_number"],
            "dokumentdatum": row["invoice_date"],
            "belegdatum": row["document_date"],
            "dateiname": row["filename"],
            "datei_hash": row["file_hash"],
            "hochgeladen_am": row["uploaded_at"],
            "hochgeladen_von_kassennummer": row["imported_by_kassennummer"],
            "hochgeladen_von_name": row["imported_by_name"],
            "ocr_verwendet": bool(row["ocr_used"]),
        })

        wareneingang_id = next_wareneingang_id
        next_wareneingang_id += 1
        invoice_to_wareneingang_id[row["id"]] = wareneingang_id
        wareneingang_rows.append({
            "id": wareneingang_id,
            "dokument_id": dokument_id,
            "lagerort_id": sf1_id,
            "status": "eingetroffen",
            "eingangsdatum": row["invoice_date"],
        })

    _bulk_insert_with_id_column(connection, 'dokumente',
        ['id', 'lieferant_id', 'lagerort_id', 'typ', 'dokumentnummer', 'dokumentdatum',
         'belegdatum', 'dateiname', 'datei_hash', 'hochgeladen_am',
         'hochgeladen_von_kassennummer', 'hochgeladen_von_name', 'ocr_verwendet'],
        dokument_rows)
    _bulk_insert_with_id_column(connection, 'wareneingaenge',
        ['id', 'dokument_id', 'lagerort_id', 'status', 'eingangsdatum'],
        wareneingang_rows)

    # --- wareneingang_positionen (+ quelle) + preise + lagerbewegungen ---
    item_rows = connection.execute(sa.select(invoice_items)).mappings().all()
    source_by_item_id = {
        r["item_id"]: r["data"]
        for r in connection.execute(sa.select(invoice_item_sources)).mappings().all()
    }
    dokument_by_id = {d["id"]: d for d in dokument_rows}
    wareneingang_by_id = {w["id"]: w for w in wareneingang_rows}

    position_rows = []
    quelle_rows = []
    preis_rows = []
    bewegung_rows = []
    item_to_position_id = {}
    next_position_id = 1
    next_preis_id = 1
    next_bewegung_id = 1

    for row in sorted(item_rows, key=lambda r: r["id"]):
        position_id = next_position_id
        next_position_id += 1
        item_to_position_id[row["id"]] = position_id
        wareneingang_id = invoice_to_wareneingang_id[row["invoice_id"]]
        varianten_id = product_to_varianten_id[row["product_id"]]
        position_rows.append({
            "id": position_id,
            "wareneingang_id": wareneingang_id,
            "varianten_id": varianten_id,
            "menge": row["quantity"],
            "einheit": row["unit"],
            "uvp": row["uvp"],
            "ek": None,
        })

        source_data = source_by_item_id.get(row["id"])
        if source_data is not None:
            quelle_rows.append({"position_id": position_id, "data": source_data})

        dokument_id = wareneingang_by_id[wareneingang_id]["dokument_id"]
        dokument = dokument_by_id[dokument_id]

        if row["uvp"] is not None:
            preis_rows.append({
                "id": next_preis_id,
                "varianten_id": varianten_id,
                "uvp": row["uvp"],
                "ek": None,
                "datum": dokument["dokumentdatum"],
                "dokument_id": dokument_id,
            })
            next_preis_id += 1

        if row["quantity"] is not None:
            bewegung_rows.append({
                "id": next_bewegung_id,
                "lagerort_id": sf1_id,
                "varianten_id": varianten_id,
                "typ": "zugang",
                "menge": row["quantity"],
                "grund": "Migration Altdaten (Phase A Punkt 3)",
                "wareneingang_position_id": position_id,
                "benutzer_kassennummer": dokument["hochgeladen_von_kassennummer"],
                "benutzer_name": dokument["hochgeladen_von_name"],
                "zeitpunkt": dokument["hochgeladen_am"],
            })
            next_bewegung_id += 1

    _bulk_insert_with_id_column(connection, 'wareneingang_positionen',
        ['id', 'wareneingang_id', 'varianten_id', 'menge', 'einheit', 'uvp', 'ek'],
        position_rows)
    if quelle_rows:
        quelle_table = sa.table(
            'wareneingang_positionen_quelle',
            sa.column('position_id', sa.Integer()), sa.column('data', sa.JSON()),
        )
        op.bulk_insert(quelle_table, quelle_rows)
    _bulk_insert_with_id_column(connection, 'preise',
        ['id', 'varianten_id', 'uvp', 'ek', 'datum', 'dokument_id'], preis_rows)
    _bulk_insert_with_id_column(connection, 'lagerbewegungen',
        ['id', 'lagerort_id', 'varianten_id', 'typ', 'menge', 'grund',
         'wareneingang_position_id', 'benutzer_kassennummer', 'benutzer_name', 'zeitpunkt'],
        bewegung_rows)

    # --- bestand: aus lagerbewegungen aggregiert (Regel 2) ---------------
    bestand_by_key = {}
    for bewegung in bewegung_rows:
        key = (bewegung["varianten_id"], bewegung["lagerort_id"])
        entry = bestand_by_key.setdefault(key, {"menge": 0, "aeltestes": None})
        entry["menge"] += bewegung["menge"]
    eingang_by_varianten = {}
    for position in position_rows:
        wareneingang_id = position["wareneingang_id"]
        eingangsdatum = wareneingang_by_id[wareneingang_id]["eingangsdatum"]
        if eingangsdatum is None:
            continue
        key = (position["varianten_id"], sf1_id)
        current = eingang_by_varianten.get(key)
        if current is None or eingangsdatum < current:
            eingang_by_varianten[key] = eingangsdatum

    bestand_rows = [
        {
            "varianten_id": key[0],
            "lagerort_id": key[1],
            "menge": entry["menge"],
            "aeltestes_eingangsdatum": eingang_by_varianten.get(key),
        }
        for key, entry in bestand_by_key.items()
    ]
    if bestand_rows:
        bestand_table = sa.table(
            'bestand',
            sa.column('varianten_id', sa.Integer()), sa.column('lagerort_id', sa.Integer()),
            sa.column('menge', sa.Numeric()), sa.column('aeltestes_eingangsdatum', sa.Date()),
        )
        op.bulk_insert(bestand_table, bestand_rows)

    # --- article_notes: product_id -> artikel_id --------------------------
    note_rows = connection.execute(sa.select(article_notes_old)).mappings().all()
    for note in note_rows:
        varianten_id = product_to_varianten_id.get(note["product_id"])
        if varianten_id is None:
            continue
        artikel_id = varianten_id_to_artikel_id[varianten_id]
        connection.execute(
            sa.text("UPDATE article_notes SET artikel_id = :artikel_id WHERE id = :note_id"),
            {"artikel_id": artikel_id, "note_id": note["id"]},
        )

    # --- Sequenzen (Postgres) auf den naechsten freien Wert vorziehen -----
    if connection.dialect.name == "postgresql":
        for table_name, rows in [
            ("lieferanten", _LIEFERANTEN_SEED), ("kategorien", _KATEGORIEN_SEED),
            ("artikel", artikel_rows), ("varianten", varianten_rows),
            ("dokumente", dokument_rows), ("wareneingaenge", wareneingang_rows),
            ("wareneingang_positionen", position_rows), ("preise", preis_rows),
            ("lagerbewegungen", bewegung_rows),
        ]:
            if not rows:
                continue
            max_id = max(r["id"] for r in rows)
            connection.execute(
                sa.text(
                    "SELECT setval(pg_get_serial_sequence(:table, 'id'), :max_id)"
                ),
                {"table": table_name, "max_id": max_id},
            )


def _bulk_insert_with_id_column(connection, table_name, columns, rows):
    if not rows:
        return
    table = sa.table(table_name, *(sa.column(c) for c in columns))
    op.bulk_insert(table, rows)


def downgrade():
    """Best-effort: stellt die Tabellenstruktur wieder her, nicht die exakte
    Notiz-Zuordnung (article_notes.product_id wird leer/NULL angelegt - die
    alten products/invoices/... Tabellen selbst wurden nie geloescht und
    enthalten die Originaldaten weiterhin unveraendert).

    ACHTUNG: Da die urspruengliche product_id -> artikel_id Zuordnung dabei
    verworfen wird (mehrere products koennen zu einem artikel gruppiert sein,
    die Umkehrung ist nicht eindeutig rekonstruierbar), schlaegt ein
    anschliessendes erneutes `upgrade` fehl, sobald mind. eine Notiz
    existiert (NOT NULL artikel_id kann fuer verwaiste Notizen nicht befuellt
    werden). Downgrade ist daher nur zur Fehleranalyse direkt nach einer
    fehlgeschlagenen Migration gedacht, nicht als reversibler Zwischenschritt
    - im Zweifel stattdessen aus Backup wiederherstellen."""
    with op.batch_alter_table('article_notes') as batch_op:
        batch_op.add_column(
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=True)
        )
        batch_op.drop_column('artikel_id')
    # siehe upgrade(): DROP COLUMN artikel_id hat den Index bereits mitgeloescht.
    op.create_index('ix_article_notes_product_id', 'article_notes', ['product_id'])

    op.drop_table('bestand')
    op.drop_table('lagerbewegungen')
    op.drop_table('wareneingang_positionen_quelle')
    op.drop_table('wareneingang_positionen')
    op.drop_table('wareneingaenge')
    op.drop_table('preise')
    op.drop_table('varianten')
    op.drop_table('artikel')
    op.drop_table('dokumente')
    op.drop_table('kategorien')
    op.drop_table('lieferanten')
