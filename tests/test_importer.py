import hashlib
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import sessionmaker

from app.core.lagerorte import seed_lagerorte
from app.core.lieferanten import seed_lieferanten
from app.core.models import (
    Artikel,
    Base,
    Dokument,
    Lagerort,
    Variante,
    Wareneingang,
    WareneingangPosition,
    WareneingangPositionQuelle,
)
from app.services.importer import import_invoice, ImportRejected


@pytest.fixture
def setup_import():
    path = os.environ.get("INTERSPORT_TEST_PDF")
    if not path:
        pytest.skip("Originalrechnung über INTERSPORT_TEST_PDF angeben")
    pdf = Path(path).read_bytes()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as s:
        seed_lagerorte(s)
        seed_lieferanten(s)
        s.commit()
        sf1_id = s.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
    yield pdf, hashlib.sha256(pdf).hexdigest(), sessions, engine, sf1_id
    engine.dispose()


def test_import_and_duplicate(setup_import):
    pdf, digest, sessions, _, sf1_id = setup_import
    result = import_invoice(pdf, "rechnung.pdf", digest, sessions, sf1_id)
    assert result["item_count"] == 217
    assert result["new_products"] == 203
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(WareneingangPosition)) == 217
        assert s.scalar(select(func.count()).select_from(WareneingangPositionQuelle)) == 217
        assert s.scalar(select(func.count()).select_from(Variante)) == 203
        dokument = s.scalar(select(Dokument))
        assert str(dokument.dokumentdatum) == "2026-08-05"
        assert str(dokument.belegdatum) == "2026-08-04"
        wareneingang = s.scalar(select(Wareneingang))
        assert wareneingang.status == "eingetroffen"
        assert wareneingang.lagerort_id == sf1_id
    with pytest.raises(ImportRejected, match="bereits importiert"):
        import_invoice(pdf, "anderer-name.pdf", digest, sessions, sf1_id)
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Dokument)) == 1
        assert s.scalar(select(func.count()).select_from(WareneingangPosition)) == 217


def test_file_changed(setup_import):
    pdf, _, sessions, _, sf1_id = setup_import
    with pytest.raises(ImportRejected, match="stimmt nicht"):
        import_invoice(pdf, "rechnung.pdf", "wrong-hash", sessions, sf1_id)
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Dokument)) == 0


def test_transaction_rollback(setup_import):
    pdf, digest, sessions, engine, sf1_id = setup_import

    def fail_on_position(conn, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO wareneingang_positionen"):
            raise RuntimeError("simulierter Schreibfehler")

    event.listen(engine, "before_cursor_execute", fail_on_position)
    with pytest.raises(RuntimeError, match="Schreibfehler"):
        import_invoice(pdf, "rechnung.pdf", digest, sessions, sf1_id)
    with sessions() as s:
        for model in (
            Dokument,
            Wareneingang,
            Artikel,
            Variante,
            WareneingangPosition,
            WareneingangPositionQuelle,
        ):
            assert s.scalar(select(func.count()).select_from(model)) == 0


def test_reuse_products_on_next_invoice(setup_import, monkeypatch):
    from app.services import importer

    pdf, digest, sessions, _, sf1_id = setup_import
    import_invoice(pdf, "rechnung.pdf", digest, sessions, sf1_id)
    original_parse = importer.parse_with_parser

    def another_invoice(parser, document, language="de"):
        parsed = original_parse(parser, document, language)
        parsed["invoice_number"] = "test-next-invoice"
        return parsed

    monkeypatch.setattr(importer, "parse_with_parser", another_invoice)
    changed = pdf + b"\n"
    result = import_invoice(
        changed, "next.pdf", hashlib.sha256(changed).hexdigest(), sessions, sf1_id
    )
    assert result["new_products"] == 0
    assert result["reused_products"] == 203
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(WareneingangPosition)) == 434


def test_imported_by_is_recorded(setup_import):
    pdf, digest, sessions, _, sf1_id = setup_import
    import_invoice(
        pdf,
        "rechnung.pdf",
        digest,
        sessions,
        sf1_id,
        {"kassennummer": "910199", "name": "Fabian Morf"},
    )
    with sessions() as s:
        dokument = s.scalar(select(Dokument))
        assert dokument.hochgeladen_von_kassennummer == "910199"
        assert dokument.hochgeladen_von_name == "Fabian Morf"


def test_imported_by_defaults_to_none_without_user(setup_import):
    pdf, digest, sessions, _, sf1_id = setup_import
    import_invoice(pdf, "rechnung.pdf", digest, sessions, sf1_id)
    with sessions() as s:
        dokument = s.scalar(select(Dokument))
        assert dokument.hochgeladen_von_kassennummer is None
        assert dokument.hochgeladen_von_name is None
