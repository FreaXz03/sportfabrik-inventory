"""Punkt 6 (2026-10-01): Grössen vereinheitlichen. `D38` → `38`; US/UK-
Schuhgrössen über die Tabelle von Fabian (Herren/Damen getrennt) nach EU. Nur
wenn Marke "US"/"UK" und Geschlecht klar sind - sonst bleibt die Grösse
unverändert (nie raten, Regel 1/7: Artikeldaten sonst nicht übersetzt)."""

import pytest

from app.core.groessen import normalisiere_groesse


@pytest.mark.parametrize(
    "groesse,bezeichnung,erwartet",
    [
        ("D38", None, "38"),
        ("D 40", "Laufschuh", "40"),
        ("d42", None, "42"),
        ("M", "T-Shirt", "M"),  # Buchstabengrössen bleiben
        ("38", None, "38"),
        ("DX1", None, "DX1"),
        ("US 8", "Gel-Kayano Herren", "41"),
        ("US8", "Men's Court", "41"),
        ("8 US", "MAN Runner", "41"),
        ("US 8,5", "Herren Schuh", "42"),
        ("US 6", "Gel Women", "36.5"),
        ("US 12", "Damen Schuh", "44.5"),
        ("US 12", "Men Schuh", "47"),
        ("UK 7", "Men Schuh", "41"),
        ("UK 5.5", "Damen", "38.5"),
        ("US 8", None, "US 8"),  # Geschlecht unbekannt: nicht raten
        ("US 8", "Unisex Schuh", "US 8"),
        ("US 99", "Herren", "US 99"),  # nicht in der Tabelle
        (None, "Herren", None),
        ("", "Herren", ""),
    ],
)
def test_normalisiere_groesse(groesse, bezeichnung, erwartet):
    assert normalisiere_groesse(groesse, bezeichnung) == erwartet


def test_parse_with_parser_normalisiert_und_merkt_das_original():
    from types import SimpleNamespace

    from app.services.parsers import parse_with_parser

    items = [
        {"size": "D38", "description": "Hose"},
        {"size": "US 8", "description": "Runner Herren"},
        {"size": "M", "description": "Shirt"},
    ]
    parser = SimpleNamespace(
        KEY="x", LIEFERANT_NAME="x", parse=lambda document, language: {"items": items}
    )
    document = SimpleNamespace(text="")
    ergebnis = parse_with_parser(parser, document)
    assert [i["size"] for i in ergebnis["items"]] == ["38", "41", "M"]
    assert [i.get("size_original") for i in ergebnis["items"]] == ["D38", "US 8", None]
