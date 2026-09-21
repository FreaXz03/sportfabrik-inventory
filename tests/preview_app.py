"""Test-App für die Vorschau-Endpunkte ohne Anmeldung.

`/upload-preview` und `/validate-preview` brauchen seit Teilaufgabe B4 eine
Datenbank (Lagerort-Adressen für die Lieferadress-Erkennung) und einen
Benutzer (welche Lagerorte zur Wahl stehen). Wo ein Test nur das Parsen prüft,
stellt dieses Modul beides bereit und schaltet die Rechteprüfung ab. Die
Rechte selbst prüfen `tests/test_auth.py` und
`tests/test_wareneingang_lagerort.py` an der echten App.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.core.database import Base, get_session
from app.core.lagerorte import seed_lagerorte
from app.core.models import User
from app.routers.auth import get_language, require_chef_api, require_chef_page
from app.routers.preview import router


def leere_datenbank():
    """In-Memory-Datenbank mit den Lagerorten (für die Adresserkennung)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        seed_lagerorte(session)
    return sessions


def build_client(sessions=None) -> TestClient:
    """Vorschau-Router mit Session-Middleware, Datenbank und Admin-Attrappe."""
    if sessions is None:
        sessions = leere_datenbank()
    app = FastAPI()
    app.include_router(router)
    app.add_middleware(SessionMiddleware, secret_key="nur-fuer-tests")

    def override_get_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    # Admin: darf Dokumente hochladen und sieht alle Lagerorte, ohne dass dafür
    # Benutzerdaten in der Datenbank stehen müssen.
    app.dependency_overrides[require_chef_api] = lambda: User(
        id=1, kassennummer="900000", name="Test", role="admin"
    )
    app.dependency_overrides[require_chef_page] = lambda: None
    app.dependency_overrides[get_language] = lambda: "de"
    return TestClient(app)
