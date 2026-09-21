"""Lagerbewegungen, Bestand und das Aufräumen beim Löschen eines Dokuments
(app/services/importer.py). Prüft die harten Regeln aus CLAUDE.md:

* Regel 2 - Bestand wird nie direkt überschrieben, sondern aus den Zeilen in
  `lagerbewegungen` abgeleitet; beim Löschen wird er daraus neu berechnet.
* Regel 3/6 - Ware an GEWA (`verkauf = False`) bekommt noch kein
  Eingangsdatum, damit die Reduktionsuhr nicht im Zwischenlager läuft.
* Regel 4 - Artikelstamm bleibt für immer; nur Bestand/Bewegungen gehen.

Wie test_importer_fedas.py mit einem synthetischen Rechnungs-Payload
(monkeypatch auf Layout-Erkennung und Parser), damit kein PDF nötig ist.
"""

import hashlib
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.kategorien import seed_kategorien
from app.core.lagerorte import seed_lagerorte
from app.core.lieferanten import seed_lieferanten
from app.core.models import (
    Artikel,
    Base,
    Bestand,
    Dokument,
    Lagerbewegung,
    Lagerort,
    Preis,
    Variante,
    Wareneingang,
    WareneingangPosition,
    WareneingangPositionQuelle,
)
from app.services import importer
from app.services.parsers import intersport
from app.services.importer import delete_invoice, import_invoice


def _fake_item(**overrides):
    item = dict(
        brand="Nike",
        fedas_code="224100",
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
        lagerorte = {
            code: s.scalar(select(Lagerort.id).where(Lagerort.code == code))
            for code in ("SF1", "SF2", "GEWA")
        }

    state = {
        "items": [_fake_item()],
        "invoice_number": "LB-1",
        "invoice_date": date(2026, 1, 10),
        "document_date": date(2026, 1, 9),
    }

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
            return {
                "invoice_date": state["invoice_date"],
                "document_date": state["document_date"],
            }

    monkeypatch.setattr(importer, "read_and_detect", lambda pdf, language="de": (None, FakeParser))
    monkeypatch.setattr(importer, "parse_with_parser", fake_parse_with_parser)
    return sessions, lagerorte, state


def _import(sessions, lagerort_id, pdf=b"%PDF-lb-1"):
    return import_invoice(pdf, "test.pdf", hashlib.sha256(pdf).hexdigest(), sessions, lagerort_id)


def _bestand(sessions, lagerort_id, ean="4006381333931"):
    with sessions() as s:
        varianten_id = s.scalar(select(Variante.id).where(Variante.ean == ean))
        return s.get(Bestand, (varianten_id, lagerort_id))


# --- Zugang: Bewegung schreiben, Bestand daraus fuehren ---------------------


def test_import_writes_zugang_and_matching_bestand(setup):
    sessions, lagerorte, _ = setup
    _import(sessions, lagerorte["SF1"])
    with sessions() as s:
        bewegungen = s.scalars(select(Lagerbewegung)).all()
        assert len(bewegungen) == 1
        bewegung = bewegungen[0]
        assert bewegung.typ == "zugang"
        assert bewegung.menge == Decimal("5")
        assert bewegung.lagerort_id == lagerorte["SF1"]
        # Regel 2: die Bewegung haengt an ihrer Wareneingangsposition.
        assert bewegung.wareneingang_position_id is not None
    bestand = _bestand(sessions, lagerorte["SF1"])
    assert bestand.menge == Decimal("5")
    assert bestand.aeltestes_eingangsdatum == date(2026, 1, 10)


def test_second_invoice_adds_to_bestand_and_keeps_oldest_date(setup):
    sessions, lagerorte, state = setup
    _import(sessions, lagerorte["SF1"])

    state["invoice_number"] = "LB-2"
    state["invoice_date"] = date(2026, 3, 1)
    state["items"] = [_fake_item(quantity="3")]
    _import(sessions, lagerorte["SF1"], pdf=b"%PDF-lb-2")

    bestand = _bestand(sessions, lagerorte["SF1"])
    assert bestand.menge == Decimal("8")
    # aeltestes_eingangsdatum ist das frueheste, nicht das zuletzt gebuchte.
    assert bestand.aeltestes_eingangsdatum == date(2026, 1, 10)
    with sessions() as s:
        assert s.scalar(select(func.count(Lagerbewegung.id))) == 2


def test_earlier_invoice_moves_oldest_date_back(setup):
    sessions, lagerorte, state = setup
    _import(sessions, lagerorte["SF1"])

    state["invoice_number"] = "LB-0"
    state["invoice_date"] = date(2025, 11, 2)
    _import(sessions, lagerorte["SF1"], pdf=b"%PDF-lb-0")

    assert _bestand(sessions, lagerorte["SF1"]).aeltestes_eingangsdatum == date(2025, 11, 2)


def test_bestand_is_per_lagerort(setup):
    sessions, lagerorte, state = setup
    _import(sessions, lagerorte["SF1"])

    state["invoice_number"] = "LB-SF2"
    state["items"] = [_fake_item(quantity="2")]
    _import(sessions, lagerorte["SF2"], pdf=b"%PDF-lb-sf2")

    assert _bestand(sessions, lagerorte["SF1"]).menge == Decimal("5")
    assert _bestand(sessions, lagerorte["SF2"]).menge == Decimal("2")
    with sessions() as s:
        # Regel 4: der Artikelstamm bleibt filialuebergreifend einer.
        assert s.scalar(select(func.count(Artikel.id))) == 1
        assert s.scalar(select(func.count(Variante.id))) == 1


# --- Regel 6: GEWA bekommt noch kein Eingangsdatum -------------------------


def test_gewa_delivery_has_no_eingangsdatum(setup):
    sessions, lagerorte, _ = setup
    _import(sessions, lagerorte["GEWA"])
    with sessions() as s:
        wareneingang = s.scalar(select(Wareneingang))
        assert wareneingang.lagerort_id == lagerorte["GEWA"]
        assert wareneingang.eingangsdatum is None
        # Das Dokumentdatum bleibt erhalten - nur das Eingangsdatum fehlt.
        assert s.scalar(select(Dokument.dokumentdatum)) == date(2026, 1, 10)
    bestand = _bestand(sessions, lagerorte["GEWA"])
    assert bestand.menge == Decimal("5")
    assert bestand.aeltestes_eingangsdatum is None


def test_gewa_does_not_lower_oldest_date_of_a_filiale(setup):
    sessions, lagerorte, state = setup
    _import(sessions, lagerorte["SF1"])

    state["invoice_number"] = "LB-GEWA"
    state["invoice_date"] = date(2025, 5, 4)
    _import(sessions, lagerorte["GEWA"], pdf=b"%PDF-lb-gewa")

    assert _bestand(sessions, lagerorte["SF1"]).aeltestes_eingangsdatum == date(2026, 1, 10)
    assert _bestand(sessions, lagerorte["GEWA"]).aeltestes_eingangsdatum is None


# --- Loeschen: Bestand aus dem verbleibenden Journal neu berechnen ---------


def test_delete_recomputes_bestand_from_remaining_bewegungen(setup):
    sessions, lagerorte, state = setup
    first = _import(sessions, lagerorte["SF1"])

    state["invoice_number"] = "LB-2"
    state["invoice_date"] = date(2026, 3, 1)
    state["items"] = [_fake_item(quantity="3")]
    _import(sessions, lagerorte["SF1"], pdf=b"%PDF-lb-2")
    assert _bestand(sessions, lagerorte["SF1"]).menge == Decimal("8")

    result = delete_invoice(first["invoice_id"], sessions)
    assert result["item_count"] == 1
    assert result["affected_products"] == 1

    bestand = _bestand(sessions, lagerorte["SF1"])
    assert bestand.menge == Decimal("3")
    # Nur noch die zweite Rechnung zaehlt fuer die Lagerdauer.
    assert bestand.aeltestes_eingangsdatum == date(2026, 3, 1)
    with sessions() as s:
        assert s.scalar(select(func.count(Lagerbewegung.id))) == 1


def test_delete_last_invoice_removes_bestand_but_keeps_artikelstamm(setup):
    sessions, lagerorte, _ = setup
    imported = _import(sessions, lagerorte["SF1"])
    delete_invoice(imported["invoice_id"], sessions)

    assert _bestand(sessions, lagerorte["SF1"]) is None
    with sessions() as s:
        # Regel 4: Artikel und Variante bleiben bestehen ...
        assert s.scalar(select(func.count(Artikel.id))) == 1
        assert s.scalar(select(func.count(Variante.id))) == 1
        # ... alles Dokumentbezogene ist weg.
        for entity in (
            Dokument,
            Wareneingang,
            WareneingangPosition,
            WareneingangPositionQuelle,
            Lagerbewegung,
            Preis,
        ):
            assert s.scalar(select(func.count()).select_from(entity)) == 0, entity.__name__
        variante = s.scalar(select(Variante))
        assert variante.first_seen is None and variante.last_seen is None


def test_delete_leaves_other_lagerort_untouched(setup):
    sessions, lagerorte, state = setup
    sf1 = _import(sessions, lagerorte["SF1"])

    state["invoice_number"] = "LB-SF2"
    state["items"] = [_fake_item(quantity="2")]
    _import(sessions, lagerorte["SF2"], pdf=b"%PDF-lb-sf2")

    delete_invoice(sf1["invoice_id"], sessions)

    assert _bestand(sessions, lagerorte["SF1"]) is None
    assert _bestand(sessions, lagerorte["SF2"]).menge == Decimal("2")


def test_delete_keeps_first_seen_of_a_gewa_only_variante(setup):
    """first_seen/last_seen kommen aus dem Dokumentdatum. Wuerden sie beim
    Loeschen aus dem Eingangsdatum neu berechnet, waeren sie fuer Ware, die
    nur an GEWA liegt, danach leer (dort ist es nach Regel 6 NULL)."""
    sessions, lagerorte, state = setup
    _import(sessions, lagerorte["GEWA"])

    state["invoice_number"] = "LB-GEWA-2"
    state["invoice_date"] = date(2026, 4, 6)
    state["items"] = [_fake_item(quantity="1")]
    zweite = _import(sessions, lagerorte["GEWA"], pdf=b"%PDF-lb-gewa-2")

    delete_invoice(zweite["invoice_id"], sessions)

    with sessions() as s:
        variante = s.scalar(select(Variante))
        assert variante.first_seen == date(2026, 1, 10)
        assert variante.last_seen == date(2026, 1, 10)
    assert _bestand(sessions, lagerorte["GEWA"]).menge == Decimal("5")
