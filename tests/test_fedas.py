"""FEDAS-Code -> Kassenkategorie-Vorschlag (Phase B, app/core/fedas.py)."""

import pytest

from app.core.fedas import suggest_kategorie


@pytest.mark.parametrize(
    "fedas_code,expected",
    [
        ("124100", ("Hartware", "Tennis")),
        ("224100", ("Textil", "Tennis")),
        ("324100", ("Schuhe", "Tennis")),
        ("232000", ("Textil", "Fussball")),
        ("160000", ("Hartware", "Velo")),
        ("164500", ("Hartware", "Outdoor")),
        ("275000", ("Textil", "Freizeit")),
    ],
)
def test_known_codes_resolve(fedas_code, expected):
    assert suggest_kategorie(fedas_code) == expected


@pytest.mark.parametrize(
    "fedas_code",
    [
        None,
        "",
        "1",
        "12",
        "999999",  # unbekannte Produktart-Ziffer
        "199999",  # bekannte Produktart, unbekannte Sportart
    ],
)
def test_unknown_or_missing_codes_return_none(fedas_code):
    assert suggest_kategorie(fedas_code) is None
