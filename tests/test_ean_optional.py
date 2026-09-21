"""Regel 5: „EAN ist optional" - vom Parser über die Korrekturen bis in die
Datenbank (Phase B, Teilaufgabe B3).

Entschieden (Fabian, 21.09.2026): Eine Position ohne EAN läuft **mit Hinweis**
durch, der Import wird davon nicht gesperrt. Eine EAN, die im Dokument steht
aber unleserlich ist, bleibt dagegen eine blockierende Warnung - das ist ein
Lesefehler-Verdacht und keine bewusst fehlende Nummer.

Alle PDFs werden selbst gebaut (siehe tests/test_parser_registry.py), der Test
braucht also keine echte Lieferantenrechnung.
"""

import hashlib

import pytest
from sqlalchemy import func, select
from test_import_end_to_end import KOPFZEILEN, _sf1, sessions  # noqa: F401 (Fixture)
from test_parser_registry import _invoice_pdf

from app.core.i18n import translate
from app.core.models import Artikel, Bestand, Variante
from app.services.corrections import apply_corrections
from app.services.importer import import_invoice
from app.services.parsers import parse_document

OHNE_EAN = ["Nike", "224100", "A1", "9988770010", "", "Poloshirt", "5", "Stk", "49.90", "30.00"]
MIT_EAN = ["Nike", "224100", "A1", "9988770011", "4006632041234", "Poloshirt", "3", "Stk", "49.90", "30.00"]
KAPUTTE_EAN = ["Nike", "224100", "A1", "9988770012", "40066", "Poloshirt", "2", "Stk", "49.90", "30.00"]

EAN_HINWEIS = translate("hints.parser.ean_missing")


def _pdf(*rows):
    return _invoice_pdf(header_lines=KOPFZEILEN, rows=list(rows))


# --- Parser ---------------------------------------------------------------


def test_position_without_ean_only_gets_a_hint():
    result = parse_document(_pdf(OHNE_EAN))
    position = result["items"][0]
    assert position["ean"] == ""
    assert position["warnings"] == []
    assert position["hints"] == [EAN_HINWEIS]
    # Entscheidend: nichts, was den Import sperrt.
    assert result["rows_with_warnings"] == 0
    assert result["rows_with_hints"] == 1


def test_unreadable_ean_still_blocks():
    """„40066" ist keine EAN - wahrscheinlich hat der Parser/die
    Texterkennung die Spalte falsch gelesen. Das muss auffallen."""
    result = parse_document(_pdf(KAPUTTE_EAN))
    position = result["items"][0]
    assert position["hints"] == []
    assert position["warnings"] == [
        translate("errors.parser.ean_unexpected_format")
    ]
    assert result["rows_with_warnings"] == 1


def test_hint_counts_only_the_positions_without_ean():
    result = parse_document(_pdf(OHNE_EAN, MIT_EAN))
    assert [bool(i["hints"]) for i in result["items"]] == [True, False]
    assert result["rows_with_hints"] == 1
    assert result["rows_with_warnings"] == 0


# --- Korrekturen (serverseitige Neuvalidierung) --------------------------


def test_revalidation_keeps_the_hint_without_blocking():
    result = apply_corrections(parse_document(_pdf(OHNE_EAN)))
    assert result["items"][0]["hints"] == [EAN_HINWEIS]
    assert result["items"][0]["warnings"] == []
    assert result["rows_with_hints"] == 1 and result["rows_with_warnings"] == 0


def test_hint_is_not_duplicated_by_repeated_validation():
    einmal = apply_corrections(parse_document(_pdf(OHNE_EAN)))
    zweimal = apply_corrections(einmal)
    assert zweimal["items"][0]["hints"] == [EAN_HINWEIS]


def test_clearing_an_ean_by_hand_is_allowed():
    """Wer eine falsch gelesene EAN löscht, bekommt den Hinweis - nicht einen
    Fehler, der den Import sperrt."""
    result = apply_corrections(parse_document(_pdf(MIT_EAN)), {"1": {"ean": ""}})
    assert result["items"][0]["hints"] == [EAN_HINWEIS]
    assert result["items"][0]["warnings"] == []
    assert result["items"][0]["correction_audit"]["changes"]["ean"]["after"] == ""


def test_correcting_an_ean_to_nonsense_still_blocks():
    result = apply_corrections(parse_document(_pdf(MIT_EAN)), {"1": {"ean": "abc"}})
    assert result["items"][0]["warnings"] == [
        translate("errors.corrections.invalid_ean")
    ]
    assert result["items"][0]["hints"] == []


def test_adding_the_ean_by_hand_removes_the_hint():
    result = apply_corrections(
        parse_document(_pdf(OHNE_EAN)), {"1": {"ean": "4006632041258"}}
    )
    assert result["items"][0]["hints"] == []
    assert result["items"][0]["warnings"] == []


# --- Import ---------------------------------------------------------------


def _import(pdf, sessions, lagerort_id, filename="rechnung.pdf"):
    return import_invoice(
        pdf, filename, hashlib.sha256(pdf).hexdigest(), sessions, lagerort_id
    )


def test_import_stores_a_variant_without_ean(sessions):
    lagerort_id = _sf1(sessions)
    result = _import(_pdf(OHNE_EAN), sessions, lagerort_id)
    assert result["item_count"] == 1
    with sessions() as session:
        variante = session.scalar(select(Variante))
        assert variante.ean is None
        assert variante.ean_intern is False
        assert (variante.farbe, variante.groesse) == (None, None)
        bestand = session.scalar(select(Bestand))
        assert str(bestand.menge) == "5.00"


def test_variants_without_ean_are_matched_by_article_colour_and_size(sessions):
    """Schlüssel ohne EAN ist Lieferant + Artikelnummer + Farbe + Grösse
    (Regel 5): zweimal dieselbe Kombination ist **eine** Variante."""
    lagerort_id = _sf1(sessions)
    _import(_pdf(OHNE_EAN, OHNE_EAN), sessions, lagerort_id)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Artikel)) == 1
        assert session.scalar(select(func.count()).select_from(Variante)) == 1
        # Beide Positionen buchen auf denselben Bestand.
        assert str(session.scalar(select(Bestand)).menge) == "10.00"


def _variantenzeile(variante):
    """Folgezeile „(Farbe)/Grösse" - im INTERSPORT-Layout steht die Variante
    unter der Bezeichnung, nicht in derselben Zeile (siehe
    app/services/parsers/intersport.py)."""
    return ["", "", "", "", "", variante, "", "", "", ""]


def test_positions_without_ean_stay_apart_when_the_size_differs(sessions):
    lagerort_id = _sf1(sessions)
    _import(
        _pdf(
            OHNE_EAN,
            _variantenzeile("(Weiss)/M"),
            OHNE_EAN,
            _variantenzeile("(Weiss)/L"),
        ),
        sessions,
        lagerort_id,
    )
    with sessions() as session:
        varianten = session.scalars(select(Variante).order_by(Variante.id)).all()
        assert [(v.farbe, v.groesse, v.ean) for v in varianten] == [
            ("Weiss", "M", None),
            ("Weiss", "L", None),
        ]


def test_unreadable_ean_blocks_the_import(sessions):
    from app.services.importer import ImportRejected

    with pytest.raises(ImportRejected, match="Warnungen"):
        _import(_pdf(KAPUTTE_EAN), sessions, _sf1(sessions))
