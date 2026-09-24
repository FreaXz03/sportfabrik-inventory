"""Übersicht: Kennzahlen, anstehende Vorgänge und Aktuelles je Filiale
(Anforderungen vom 23.09.2026)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.lagerorte import seed_lagerorte
from app.core.models import (
    Artikel,
    Bestand,
    Lagerort,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from app.services import uebersicht
from app.services.ausbuchung import ausbuchen
from app.services.uebersicht import _monate_zurueck

HEUTE = date(2026, 9, 24)


@pytest.fixture
def daten():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        seed_lagerorte(session)
        session.flush()
        codes = {lo.code: lo.id for lo in session.scalars(select(Lagerort)).all()}

        def artikel(name, eingang, menge):
            a = Artikel(marke="Nike", lieferanten_artikelnr=name, bezeichnung=name)
            session.add(a)
            session.flush()
            v = Variante(artikel_id=a.id, ean=None)
            session.add(v)
            session.flush()
            w = Wareneingang(lagerort_id=codes["SF1"], status="eingetroffen", eingangsdatum=eingang)
            session.add(w)
            session.flush()
            session.add(WareneingangPosition(
                wareneingang_id=w.id, varianten_id=v.id, menge=Decimal(1), menge_eingetroffen=Decimal(1)
            ))
            session.add(Bestand(varianten_id=v.id, lagerort_id=codes["SF1"], menge=Decimal(menge),
                                aeltestes_eingangsdatum=eingang))
            return v.id

        ids = {
            # seit 19 Monaten da → 50 % fällig
            "alt": artikel("ALT", _monate_zurueck(HEUTE, 19), 3),
            # erreicht die 18 Monate in 10 Tagen → bald
            "bald": artikel("BALD", _monate_zurueck(HEUTE + timedelta(days=10), 18), 2),
            # seit 40 Monaten da → 70 % fällig
            "uralt": artikel("URALT", _monate_zurueck(HEUTE, 40), 1),
            # neu, aber Bestand negativ → zählen
            "minus": artikel("MINUS", HEUTE, -2),
        }
        session.add(Wareneingang(lagerort_id=codes["SF1"], status="erwartet"))
    yield sessions, codes, ids
    engine.dispose()


def test_monate_zurueck_kuerzt_am_monatsende():
    assert _monate_zurueck(date(2026, 8, 31), 18) == date(2025, 2, 28)
    assert _monate_zurueck(date(2026, 9, 24), 18) == date(2025, 3, 24)


def test_kennzahlen_der_filiale(daten):
    sessions, codes, ids = daten
    ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", varianten_id=ids["alt"])
    ausbuchen(sessions, lagerort_id=codes["SF1"], grund="defekt", varianten_id=ids["alt"])
    with sessions() as session:
        f = uebersicht.filiale(session, codes["SF1"])
    assert f["stueck"] == "4.00"  # 1 + 2 + 1 (der negative zählt nicht mit)
    assert f["varianten"] == 3
    assert f["verkauft_heute"] == "1.00"
    assert f["abgaenge_heute"] == "1.00"
    assert f["negativ"] == 1
    assert f["erwartet_total"] == 1


def test_reduktionen_faellig_und_bald(daten):
    sessions, codes, _ = daten
    with sessions() as session:
        f = uebersicht.filiale(session, codes["SF1"], heute=HEUTE)
    assert f["reduktionen"] == {
        "50": {"faellig": 1, "bald": 1},
        "70": {"faellig": 1, "bald": 0},
    }


def test_andere_filiale_ist_leer(daten):
    sessions, codes, _ = daten
    with sessions() as session:
        f = uebersicht.filiale(session, codes["SF2"], heute=HEUTE)
    assert f["stueck"] == "0.00"
    assert f["erwartet_total"] == 0
    assert f["reduktionen"]["50"] == {"faellig": 0, "bald": 0}


def test_aktuelles_neueste_zuerst(daten):
    sessions, codes, ids = daten
    ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", varianten_id=ids["alt"],
              benutzer={"kassennummer": "1", "name": "Anna"})
    ausbuchen(sessions, lagerort_id=codes["SF1"], grund="defekt", varianten_id=ids["bald"])
    with sessions() as session:
        liste = uebersicht.aktuelles(session, codes["SF1"])
        anderswo = uebersicht.aktuelles(session, codes["SF2"])
    assert [e["typ"] for e in liste] == ["ausbuchung", "verkauf"]
    assert liste[1]["person"] == "Anna"
    assert anderswo == []


def test_stamm_hinweise(daten):
    sessions, _, _ = daten
    with sessions() as session:
        s = uebersicht.stamm(session)
    assert s == {"ohne_kategorie": 4, "ohne_ean": 4}
