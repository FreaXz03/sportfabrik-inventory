"""Lieferantengruppen und ihre Etikett-Codes (Anforderungen vom 23.09.2026)."""

import importlib.util
from pathlib import Path

import pytest

from app.core.lieferanten import ETIKETT_CODES, LIEFERANTEN_SEED, etikett_code

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "f2a3b4c5d6e7_lieferantengruppen.py"
)


@pytest.mark.parametrize(
    "typ, code",
    [("intersport", "111"), ("ecom", "555"), ("extern", "333"), ("drittanbieter", "999"), ("intern", "444")],
)
def test_code_je_gruppe(typ, code):
    assert etikett_code(typ) == code


def test_ohne_lieferant_kein_code():
    assert etikett_code(None) is None
    assert etikett_code("unbekannt") is None


def test_intern_nur_nike_adidas_north_face():
    intern = {eintrag["name"] for eintrag in LIEFERANTEN_SEED if eintrag["typ"] == "intern"}
    assert intern == {"Nike", "adidas", "The North Face"}


def test_jede_gruppe_hat_einen_seed_eintrag():
    assert {eintrag["typ"] for eintrag in LIEFERANTEN_SEED} == set(ETIKETT_CODES)


def test_migration_und_seed_meinen_dasselbe():
    spec = importlib.util.spec_from_file_location("lieferantengruppen", MIGRATION)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    aus_seed = [e for e in LIEFERANTEN_SEED if e["name"] != "INTERSPORT Schweiz AG"]
    assert modul._NEUE_LIEFERANTEN == aus_seed
