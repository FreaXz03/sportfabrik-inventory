"""Falsch erfassten Artikel löschen (Entscheid vom 24.09.2026): nur
Filialleiter/Zentrale, nur ohne Beleg, und dann samt Bestand und Buchungen."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.database as database
from app.core.database import Base, get_session
from app.core.lagerorte import seed_lagerorte
from app.core.models import (
    Artikel,
    BenutzerLagerort,
    Bestand,
    Dokument,
    Lagerbewegung,
    Lagerort,
    User,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from app.main import app
from app.core.security import hash_password
from app.services.artikel_loeschen import LoeschenRejected, hat_beleg, loesche_artikel
from app.services.ausbuchung import ausbuchen
from app.services.manuelle_erfassung import erfasse_wareneingang


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
        # Artikel aus einem Beleg
        dokument = Dokument(typ="rechnung", dokumentnummer="R1", lagerort_id=codes["SF1"])
        session.add(dokument)
        session.flush()
        beleg_artikel = Artikel(marke="Nike", lieferanten_artikelnr="B1", bezeichnung="Aus Beleg")
        session.add(beleg_artikel)
        session.flush()
        beleg_variante = Variante(artikel_id=beleg_artikel.id)
        session.add(beleg_variante)
        session.flush()
        eingang = Wareneingang(dokument_id=dokument.id, lagerort_id=codes["SF1"],
                               status="eingetroffen", eingangsdatum=date(2026, 1, 1))
        session.add(eingang)
        session.flush()
        session.add(WareneingangPosition(wareneingang_id=eingang.id, varianten_id=beleg_variante.id,
                                         menge=Decimal(1), menge_eingetroffen=Decimal(1)))
        for kassennummer, rolle in (("910141", "mitarbeiter"), ("900001", "chef")):
            user = User(kassennummer=kassennummer, name=kassennummer, role=rolle,
                        password_hash=hash_password("geheim-123") if rolle == "chef" else None)
            session.add(user)
            session.flush()
            session.add(BenutzerLagerort(user_id=user.id, lagerort_id=codes["SF1"], ist_primaer=True))
        beleg_id = beleg_variante.id
    ergebnis = erfasse_wareneingang(
        [{"marke": "Puma", "bezeichnung": "Falsch getippt", "menge": "3", "uvp": "10",
          "farbe": "Rot", "groesse": "M", "lieferanten_artikelnr": "X1"},
         {"marke": "Puma", "bezeichnung": "Falsch getippt", "menge": "1", "uvp": "10",
          "farbe": "Rot", "groesse": "L", "lieferanten_artikelnr": "X1"}],
        sessions,
        lagerort_id=codes["SF1"],
    )
    with sessions() as session:
        manuell_id = session.scalar(
            select(Variante.id).join(Artikel).where(Artikel.bezeichnung == "Falsch getippt").limit(1)
        )
    yield sessions, codes, beleg_id, manuell_id
    engine.dispose()


def _anzahl(sessions, modell):
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(modell))


def test_hat_beleg(daten):
    sessions, _, beleg_id, manuell_id = daten
    with sessions() as session:
        assert hat_beleg(session, session.get(Variante, beleg_id).artikel_id) is True
        assert hat_beleg(session, session.get(Variante, manuell_id).artikel_id) is False


def test_manueller_artikel_verschwindet_ganz(daten):
    sessions, codes, _, manuell_id = daten
    ausbuchen(sessions, lagerort_id=codes["SF1"], grund="verkauf", varianten_id=manuell_id)
    ergebnis = loesche_artikel(sessions, manuell_id, {"name": "Chef", "kassennummer": "900001"})
    assert ergebnis["varianten"] == 2
    assert ergebnis["bewegungen"] == 3  # zwei Zugänge, ein Verkauf
    with sessions() as session:
        assert session.scalar(select(Artikel).where(Artikel.bezeichnung == "Falsch getippt")) is None
        # Nur der Beleg-Artikel bleibt - mit seiner Position und seinem Eingang.
        assert session.scalar(select(func.count()).select_from(Variante)) == 1
        assert session.scalar(select(func.count()).select_from(WareneingangPosition)) == 1
        assert session.scalar(select(func.count()).select_from(Wareneingang)) == 1
    assert _anzahl(sessions, Lagerbewegung) == 0
    assert _anzahl(sessions, Bestand) == 0


def test_artikel_aus_beleg_bleibt(daten):
    sessions, _, beleg_id, _ = daten
    with pytest.raises(LoeschenRejected):
        loesche_artikel(sessions, beleg_id)
    with sessions() as session:
        assert session.get(Variante, beleg_id) is not None


def test_unbekannte_variante(daten):
    sessions, _, _, _ = daten
    with pytest.raises(LoeschenRejected):
        loesche_artikel(sessions, 9999)


@pytest.fixture
def client(daten, monkeypatch):
    sessions, codes, beleg_id, manuell_id = daten

    def override_get_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(database, "SessionLocal", sessions)
    with TestClient(app) as test_client:
        yield test_client, sessions, beleg_id, manuell_id
    app.dependency_overrides.clear()


def test_api_mitarbeiter_darf_nicht_loeschen(client):
    test_client, sessions, _, manuell_id = client
    test_client.post("/login", data={"kassennummer": "910141"})
    assert test_client.delete(f"/api/articles/{manuell_id}").status_code == 403
    with sessions() as session:
        assert session.get(Variante, manuell_id) is not None


def test_api_filialleiter_loescht_manuellen_artikel(client):
    test_client, sessions, beleg_id, manuell_id = client
    test_client.post("/login", data={"kassennummer": "900001", "password": "geheim-123"})
    historie = test_client.get(f"/api/articles/{manuell_id}/history").json()
    assert historie["product"]["manuell"] is True
    assert test_client.get(f"/api/articles/{beleg_id}/history").json()["product"]["manuell"] is False
    assert test_client.delete(f"/api/articles/{beleg_id}").status_code == 409
    assert test_client.delete(f"/api/articles/{manuell_id}").status_code == 200
    with sessions() as session:
        assert session.get(Variante, manuell_id) is None


def test_api_filter_nur_manuell(client):
    test_client, _, _, _ = client
    test_client.post("/login", data={"kassennummer": "910141"})
    body = test_client.get("/api/articles?nur_manuell=true").json()
    assert {item["description"] for item in body["items"]} == {"Falsch getippt"}
    assert test_client.get("/api/articles").json()["total"] == 3  # 1 aus Beleg + 2 Varianten
