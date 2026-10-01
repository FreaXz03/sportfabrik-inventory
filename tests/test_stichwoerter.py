"""Punkt 2 (2026-10-01): Kategorie aus Stichwörtern im Artikelnamen und im
Dateinamen. FEDAS bleibt massgebend, Stichwörter füllen nur Lücken, eine
Wahl von Hand wird nie überschrieben (Regel 8, B8)."""

import pytest
from conftest import neue_datenbank
from sqlalchemy import select

from app.core.models import Artikel, Kategorie
from app.core.stichwoerter import kategorie_aus_text, kombiniere
from app.services.importer import _backfill_artikel


@pytest.mark.parametrize(
    "name,datei,erwartet",
    [
        ("WOMAN PANT", None, ("Textil", None)),
        ("WOMAN PANT", "OUTDOOR Bestellung SF1.pdf", ("Textil", "Outdoor")),
        ("Kids Running Shoe", None, ("Schuhe", "Kids")),  # Entscheid 2026-10-01: Kinderware ist immer Kids
        ("Girls Tee", None, ("Textil", "Kids")),
        ("Boys Jacket", "OUTDOOR.pdf", ("Textil", "Kids")),
        ("Junior Ball", None, ("Hartware", "Kids")),
        ("Trail-Jacket", "outdoor_2026.pdf", ("Textil", "Outdoor")),
        ("Tennis Racket", None, ("Hartware", "Tennis")),
        ("PANTHER 2000", None, (None, None)),  # ganze Wörter, kein Teilstring
        ("Allrounder", "OUTDOOR.pdf", (None, "Outdoor")),  # Bereich allein, Hauptgruppe offen
        ("E-Bike Rahmen", "BIKE.pdf", (None, None)),  # Velo ist nie ein Stichwort-Treffer
        (None, None, (None, None)),
    ],
)
def test_kategorie_aus_text(name, datei, erwartet):
    assert kategorie_aus_text(name, datei) == erwartet


@pytest.mark.parametrize(
    "fedas,text,erwartet",
    [
        (("Textil", "Tennis"), (None, "Outdoor"), ("Textil", "Tennis")),  # FEDAS gewinnt
        (("Velo", None), ("Textil", "Outdoor"), ("Velo", None)),
        (("Textil", None), (None, "Outdoor"), ("Textil", "Outdoor")),  # Lücke gefüllt
        (("Textil", None), ("Schuhe", "Outdoor"), ("Textil", "Outdoor")),  # Hauptgruppe bleibt FEDAS
        (("Textil", "Running"), (None, "Kids"), ("Textil", "Kids")),  # Kids schlägt den FEDAS-Bereich
        (("Textil", "Tennis"), (None, "Outdoor"), ("Textil", "Tennis")),
        (("Velo", None), (None, "Kids"), ("Velo", None)),  # Velo/Food bleiben
        (None, ("Textil", "Outdoor"), ("Textil", "Outdoor")),
        (None, ("Textil", None), ("Textil", None)),
        (None, (None, "Outdoor"), None),  # ohne Hauptgruppe keine Kategorie
        (None, (None, None), None),
    ],
)
def test_kombinieren(fedas, text, erwartet):
    assert kombiniere(fedas, text) == erwartet


def test_importer_nutzt_stichwoerter_aber_nie_gegen_manuell():
    sessions = neue_datenbank()
    with sessions() as session:
        ids = {(k.hauptgruppe, k.sportbereich): k.id for k in session.scalars(select(Kategorie))}
        offen = Artikel(bezeichnung="WOMAN PANT")
        manuell = Artikel(bezeichnung="WOMAN PANT", kategorie_id=ids[("Hartware", "Tennis")], kategorie_manuell=True)
        session.add_all([offen, manuell])
        session.flush()
        item = {"description": "WOMAN PANT"}
        for artikel in (offen, manuell):
            _backfill_artikel(session, {}, artikel, item, dateiname="OUTDOOR Nachbestellung.pdf")
        assert offen.kategorie_id == ids[("Textil", "Outdoor")]
        assert manuell.kategorie_id == ids[("Hartware", "Tennis")]
