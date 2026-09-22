"""FEDAS-Kategorievorschlag beim Live-Import (app/services/importer.py) -
nutzt einen synthetischen Rechnungs-Payload statt einer echten PDF
(monkeypatcht Layout-Erkennung und Parser), damit der Test unabhängig von
INTERSPORT_TEST_PDF läuft, siehe app/core/fedas.py für die Codes."""

import hashlib
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.kategorien import seed_kategorien
from app.core.lagerorte import seed_lagerorte
from app.core.lieferanten import seed_lieferanten
from app.core.models import Artikel, Base, Kategorie, Lagerort, Variante
from app.services import importer
from app.services.parsers import intersport
from app.services.importer import import_invoice


def _fake_item(**overrides):
    item = dict(
        brand="Nike",
        fedas_code="224100",  # Textil x Tennis
        supplier_article_no="ABC123",
        article_no="IS-1",
        ean="4006381333931",
        description="Poloshirt",
        color="Weiss",
        size="M",
        quantity="5",
        unit="Stk",
        uvp="49.90",
        row_number=1,
        page=1,
        raw_lines=["Nike ABC123 IS-1 4006381333931 Poloshirt (Weiss)/M 5 Stk 49.90"],
    )
    item.update(overrides)
    return item


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as s:
        seed_lagerorte(s)
        seed_lieferanten(s)
        seed_kategorien(s)
        s.commit()
        sf1_id = s.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))

    state = {"items": [_fake_item()], "invoice_number": "FEDAS-1"}

    def fake_parse_with_parser(parser, document, language="de"):
        return {
            "parser_key": intersport.KEY,
            "supplier_name": intersport.LIEFERANT_NAME,
            "document_type": "rechnung",
            "invoice_number": state["invoice_number"],
            "warnings": [],
            "rows_with_warnings": 0,
            "item_count": len(state["items"]),
            "ocr_used": False,
            "items": state["items"],
        }

    class FakeParser:
        KEY = intersport.KEY
        LIEFERANT_NAME = intersport.LIEFERANT_NAME

        @staticmethod
        def dates(document, language="de"):
            return {"invoice_date": date(2026, 1, 10), "document_date": date(2026, 1, 9)}

    monkeypatch.setattr(importer, "read_and_detect", lambda pdf, language="de": (None, FakeParser))
    monkeypatch.setattr(importer, "parse_with_parser", fake_parse_with_parser)
    return sessions, sf1_id, state


def _import(sessions, sf1_id, pdf=b"%PDF-fedas-test"):
    digest = hashlib.sha256(pdf).hexdigest()
    return import_invoice(pdf, "test.pdf", digest, sessions, sf1_id)


def test_known_fedas_code_sets_kategorie_on_new_artikel(setup):
    sessions, sf1_id, _ = setup
    _import(sessions, sf1_id)
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "ABC123"))
        assert artikel.fedas_code == "224100"
        kategorie = s.get(Kategorie, artikel.kategorie_id)
        assert (kategorie.hauptgruppe, kategorie.sportbereich) == ("Textil", "Tennis")


def test_unmapped_fedas_code_leaves_kategorie_unset(setup):
    sessions, sf1_id, state = setup
    state["items"] = [_fake_item(fedas_code="999999", supplier_article_no="ZZZ999")]
    _import(sessions, sf1_id)
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "ZZZ999"))
        assert artikel.fedas_code == "999999"
        assert artikel.kategorie_id is None


def test_missing_fedas_code_leaves_kategorie_unset(setup):
    sessions, sf1_id, state = setup
    state["items"] = [_fake_item(fedas_code="", supplier_article_no="NOFEDAS")]
    _import(sessions, sf1_id)
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "NOFEDAS"))
        assert artikel.fedas_code is None
        assert artikel.kategorie_id is None


def test_later_invoice_backfills_category_once_code_is_known(setup):
    sessions, sf1_id, state = setup
    state["items"] = [_fake_item(fedas_code="", supplier_article_no="ABC123", ean=None)]
    _import(sessions, sf1_id)
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "ABC123"))
        assert artikel.kategorie_id is None

    state["invoice_number"] = "FEDAS-2"
    state["items"] = [
        _fake_item(fedas_code="224100", supplier_article_no="ABC123", ean=None, quantity="2")
    ]
    _import(sessions, sf1_id, pdf=b"%PDF-fedas-test-2")
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "ABC123"))
        assert artikel.fedas_code == "224100"
        kategorie = s.get(Kategorie, artikel.kategorie_id)
        assert (kategorie.hauptgruppe, kategorie.sportbereich) == ("Textil", "Tennis")


def test_existing_category_is_not_overwritten_by_later_invoice(setup):
    sessions, sf1_id, state = setup
    _import(sessions, sf1_id)  # 224100 -> Textil/Tennis
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "ABC123"))
        original_kategorie_id = artikel.kategorie_id
        assert original_kategorie_id is not None

    state["invoice_number"] = "FEDAS-2"
    state["items"] = [
        _fake_item(fedas_code="232000", supplier_article_no="ABC123", ean=None, quantity="2")
    ]
    _import(sessions, sf1_id, pdf=b"%PDF-fedas-test-2")
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "ABC123"))
        assert artikel.kategorie_id == original_kategorie_id


def test_manual_category_survives_a_later_invoice(setup):
    """Teilaufgabe B8: von Hand gewählt schlägt jeden Vorschlag - auch wenn
    eine spätere Rechnung einen bekannten FEDAS-Code mitbringt."""
    from app.services.kategorien import setze_kategorie

    sessions, sf1_id, state = setup
    state["items"] = [_fake_item(fedas_code="", supplier_article_no="ABC123", ean=None)]
    _import(sessions, sf1_id)
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "ABC123"))
        variante_id = s.scalar(
            select(Variante.id).where(Variante.artikel_id == artikel.id)
        )
        von_hand = s.scalar(
            select(Kategorie.id).where(
                Kategorie.hauptgruppe == "Schuhe", Kategorie.sportbereich == "Running"
            )
        )
        setze_kategorie(s, variante_id, von_hand)

    state["invoice_number"] = "FEDAS-2"
    state["items"] = [
        _fake_item(fedas_code="224100", supplier_article_no="ABC123", ean=None, quantity="2")
    ]
    _import(sessions, sf1_id, pdf=b"%PDF-fedas-test-2")
    with sessions() as s:
        artikel = s.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == "ABC123"))
        # Der Code vom Beleg wird nachgetragen, die Kategorie bleibt von Hand.
        assert artikel.fedas_code == "224100"
        assert artikel.kategorie_id == von_hand
        assert artikel.kategorie_manuell is True
