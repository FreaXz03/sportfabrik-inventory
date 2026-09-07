import hashlib
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import sessionmaker

from app.core.models import Base, Product, Invoice, InvoiceItem, InvoiceItemSource
from app.services.importer import import_invoice, ImportRejected


@pytest.fixture
def setup_import():
    path = os.environ.get("INTERSPORT_TEST_PDF")
    if not path:
        pytest.skip("Originalrechnung über INTERSPORT_TEST_PDF angeben")
    pdf = Path(path).read_bytes()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield pdf, hashlib.sha256(pdf).hexdigest(), sessionmaker(engine), engine
    engine.dispose()


def test_import_and_duplicate(setup_import):
    pdf, digest, sessions, _ = setup_import
    result = import_invoice(pdf, "rechnung.pdf", digest, sessions)
    assert result["item_count"] == 217
    assert result["new_products"] == 203
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(InvoiceItem)) == 217
        assert s.scalar(select(func.count()).select_from(InvoiceItemSource)) == 217
        assert s.scalar(select(func.count()).select_from(Product)) == 203
        invoice = s.scalar(select(Invoice))
        assert str(invoice.invoice_date) == "2026-08-05"
        assert str(invoice.document_date) == "2026-08-04"
    with pytest.raises(ImportRejected, match="bereits importiert"):
        import_invoice(pdf, "anderer-name.pdf", digest, sessions)
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Invoice)) == 1
        assert s.scalar(select(func.count()).select_from(InvoiceItem)) == 217


def test_file_changed(setup_import):
    pdf, _, sessions, _ = setup_import
    with pytest.raises(ImportRejected, match="stimmt nicht"):
        import_invoice(pdf, "rechnung.pdf", "wrong-hash", sessions)
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Invoice)) == 0


def test_transaction_rollback(setup_import):
    pdf, digest, sessions, engine = setup_import

    def fail_on_position(conn, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO invoice_items"):
            raise RuntimeError("simulierter Schreibfehler")

    event.listen(engine, "before_cursor_execute", fail_on_position)
    with pytest.raises(RuntimeError, match="Schreibfehler"):
        import_invoice(pdf, "rechnung.pdf", digest, sessions)
    with sessions() as s:
        for model in (Invoice, Product, InvoiceItem, InvoiceItemSource):
            assert s.scalar(select(func.count()).select_from(model)) == 0


def test_reuse_products_on_next_invoice(setup_import, monkeypatch):
    from app.services import importer

    pdf, digest, sessions, _ = setup_import
    import_invoice(pdf, "rechnung.pdf", digest, sessions)
    original_parse = importer.parse_invoice

    def another_invoice(data):
        parsed = original_parse(data)
        parsed["invoice_number"] = "test-next-invoice"
        return parsed

    monkeypatch.setattr(importer, "parse_invoice", another_invoice)
    changed = pdf + b"\n"
    result = import_invoice(
        changed, "next.pdf", hashlib.sha256(changed).hexdigest(), sessions
    )
    assert result["new_products"] == 0
    assert result["reused_products"] == 203
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(InvoiceItem)) == 434


def test_imported_by_is_recorded(setup_import):
    pdf, digest, sessions, _ = setup_import
    import_invoice(
        pdf,
        "rechnung.pdf",
        digest,
        sessions,
        {"kassennummer": "910199", "name": "Fabian Morf"},
    )
    with sessions() as s:
        invoice = s.scalar(select(Invoice))
        assert invoice.imported_by_kassennummer == "910199"
        assert invoice.imported_by_name == "Fabian Morf"


def test_imported_by_defaults_to_none_without_user(setup_import):
    pdf, digest, sessions, _ = setup_import
    import_invoice(pdf, "rechnung.pdf", digest, sessions)
    with sessions() as s:
        invoice = s.scalar(select(Invoice))
        assert invoice.imported_by_kassennummer is None
        assert invoice.imported_by_name is None
