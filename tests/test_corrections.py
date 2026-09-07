import pytest
from sqlalchemy import select, func
from test_importer import setup_import
from app.services.corrections import apply_corrections, CorrectionError
from app.services.parser import parse_invoice
from app.services.importer import import_invoice, ImportRejected
from app.core.models import InvoiceItemSource, InvoiceItem, Invoice


def test_corrected_import_preserves_original_and_actor(setup_import):
    pdf, digest, sessions, _ = setup_import
    actor = {"name": "Test Chef", "kassennummer": "999"}
    import_invoice(
        pdf,
        "test.pdf",
        digest,
        sessions,
        actor,
        {"1": {"quantity": "2,50", "description": "Korrigiert"}},
    )
    with sessions() as s:
        source = s.scalar(select(InvoiceItemSource).order_by(InvoiceItemSource.item_id))
        audit = source.data["correction_audit"]
        assert source.data["quantity"] == "2.50"
        assert audit["original"]["quantity"] == "1"
        assert audit["by"] == actor and audit["at"]
        assert audit["changes"]["description"]["after"] == "Korrigiert"
        assert (
            str(s.scalar(select(InvoiceItem).order_by(InvoiceItem.id)).quantity)
            == "2.50"
        )


@pytest.mark.parametrize(
    "patch", [{"1": {"id": "3"}}, {"9999": {"ean": "12345678"}}, {"1": {"ean": 123}}]
)
def test_reject_unknown_fields_and_rows(setup_import, patch):
    pdf, _, _, _ = setup_import
    with pytest.raises(CorrectionError):
        apply_corrections(parse_invoice(pdf), patch)


@pytest.mark.parametrize(
    "patch",
    [
        {"quantity": "NaN"},
        {"uvp": "-1"},
        {"quantity": "1.234"},
        {"ean": "abc"},
        {"brand": ""},
    ],
)
def test_invalid_values_block_import(setup_import, patch):
    pdf, digest, sessions, _ = setup_import
    with pytest.raises(ImportRejected):
        import_invoice(pdf, "test.pdf", digest, sessions, corrections={"1": patch})
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Invoice)) == 0


def test_repair_warnings_without_erasing_structural_problems(setup_import):
    pdf, _, _, _ = setup_import
    parsed = parse_invoice(pdf)
    parsed["items"][0]["ean"] = "bad"
    parsed["items"][0]["warnings"] = ["EAN hat ein unerwartetes Format."]
    parsed["warnings"] = ["Nicht zugeordnete Zeile"]
    result = apply_corrections(parsed, {"1": {"ean": "0012345678901"}})
    assert result["items"][0]["warnings"] == []
    assert result["warnings"] == ["Nicht zugeordnete Zeile"]
    assert result["items"][0]["ean"] == "0012345678901"
    assert parsed["items"][0]["ean"] == "bad"
