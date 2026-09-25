"""Gemeinsame Test-Grundlage.

Die Tests sind nach Hauptabläufen gebaut (Entscheid 24.09.2026, siehe
CLAUDE.md „Tests"): wenige grosse Ablauf-Tests über die echte App mit
Anmeldung, dazu kleine Tests nur für harte Regeln. Alle Ablauf-Tests teilen
sich die Welt aus diesem Modul: eine leere In-Memory-Datenbank mit den
Stammdaten (Lagerorte, Lieferanten, Kategorien) und Konten für jede Rolle.

SESSION_SECRET muss gesetzt sein, bevor ein Testmodul app.main importiert -
app.routers.auth schlägt ohne es beim Import fehl.
"""

import os

os.environ.setdefault("SESSION_SECRET", "test-secret-nicht-fuer-produktion")

from dataclasses import dataclass  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# Konten der Test-Welt: Kassennummer → Passwort (None = Mitarbeiter, ohne).
ANNA = "910141"  # Mitarbeiterin, SF1
BEAT = "910142"  # Mitarbeiter, SF2
CHEF = "910199"  # Filialleiter, SF1 (primär) und SF2
ZENTRALE = "910100"  # Admin/Zentrale, alle Filialen
PASSWOERTER = {ANNA: None, BEAT: None, CHEF: "geheim123", ZENTRALE: "zentrale123"}


@dataclass
class Welt:
    client: TestClient
    sessions: sessionmaker
    codes: dict  # Lagerort-Code → id

    def anmelden(self, kassennummer: str):
        """Meldet das Konto an (vorher abmelden) und gibt die Antwort zurück."""
        self.client.post("/logout")
        daten = {"kassennummer": kassennummer}
        if PASSWOERTER[kassennummer]:
            daten["password"] = PASSWOERTER[kassennummer]
        antwort = self.client.post("/login", data=daten)
        assert antwort.status_code == 200, antwort.text
        return antwort


def neue_datenbank() -> sessionmaker:
    """In-Memory-Datenbank mit allen Stammdaten, aber ohne Artikel.

    StaticPool + check_same_thread=False, weil der TestClient die Endpunkte in
    einem anderen Thread aufruft als der Test selbst."""
    from app.core.database import Base
    from app.core.kategorien import seed_kategorien
    from app.core.lagerorte import seed_lagerorte
    from app.core.lieferanten import seed_lieferanten

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        seed_lagerorte(session)
        seed_lieferanten(session)
        seed_kategorien(session)
    return sessions


@pytest.fixture
def welt(monkeypatch):
    """Echte App mit Test-Datenbank und den Konten von oben."""
    import app.core.database as database
    from app.core.database import get_session
    from app.core.models import BenutzerLagerort, Lagerort, User
    from app.core.security import hash_password
    from app.main import app

    sessions = neue_datenbank()
    with sessions.begin() as session:
        codes = {lo.code: lo.id for lo in session.scalars(select(Lagerort)).all()}
        konten = [
            (ANNA, "Anna", "mitarbeiter", ["SF1"]),
            (BEAT, "Beat", "mitarbeiter", ["SF2"]),
            (CHEF, "Chef", "chef", ["SF1", "SF2"]),
            (ZENTRALE, "Zentrale", "admin", []),
        ]
        for kassennummer, name, rolle, filialen in konten:
            passwort = PASSWOERTER[kassennummer]
            user = User(
                kassennummer=kassennummer,
                name=name,
                role=rolle,
                password_hash=hash_password(passwort) if passwort else None,
            )
            session.add(user)
            session.flush()
            for index, code in enumerate(filialen):
                session.add(
                    BenutzerLagerort(
                        user_id=user.id, lagerort_id=codes[code], ist_primaer=index == 0
                    )
                )

    def override_get_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    # Import und Buchungen laufen im Threadpool mit eigener Session-Fabrik.
    monkeypatch.setattr(database, "SessionLocal", sessions)
    # history.py importiert SessionLocal beim Laden des Moduls.
    import app.routers.history as history

    monkeypatch.setattr(history, "SessionLocal", sessions)
    with TestClient(app) as client:
        yield Welt(client=client, sessions=sessions, codes=codes)
    app.dependency_overrides.clear()
