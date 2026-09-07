"""Anmeldung (Kassennummer für Mitarbeiter, Kassennummer+Passwort für Chefs)
und rollenbasierte Zugriffsrechte: Mitarbeiter dürfen nur ansehen/suchen,
nur Chefs dürfen Rechnungen hochladen/importieren/löschen."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.core.models import Base, User
from app.core.security import hash_password


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as s:
        s.add(
            User(
                kassennummer="910141",
                name="Anna",
                role="mitarbeiter",
                password_hash=None,
            )
        )
        s.add(
            User(
                kassennummer="910199",
                name="Chef",
                role="chef",
                password_hash=hash_password("geheim123"),
            )
        )

    def override_get_session():
        with sessions() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def login_mitarbeiter(client):
    return client.post("/login", data={"kassennummer": "910141"})


def login_chef(client):
    return client.post(
        "/login", data={"kassennummer": "910199", "password": "geheim123"}
    )


def test_unknown_kassennummer_rejected(client):
    assert client.post("/login", data={"kassennummer": "000000"}).status_code == 401


def test_mitarbeiter_logs_in_without_password(client):
    r = login_mitarbeiter(client)
    assert r.status_code == 200
    assert r.json() == {"name": "Anna", "role": "mitarbeiter"}


def test_chef_must_provide_password(client):
    r = client.post("/login", data={"kassennummer": "910199"})
    assert r.status_code == 200
    assert r.json() == {"requires_password": True}


def test_chef_wrong_password_rejected(client):
    client.post("/login", data={"kassennummer": "910199"})
    r = client.post("/login", data={"kassennummer": "910199", "password": "falsch"})
    assert r.status_code == 401


def test_chef_correct_password_accepted(client):
    r = login_chef(client)
    assert r.status_code == 200
    assert r.json() == {"name": "Chef", "role": "chef"}


def test_anonymous_page_redirects_to_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login?next=/"


def test_anonymous_api_gets_401_not_redirect(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/articles").status_code == 401
    assert client.get("/api/invoices").status_code == 401


def test_logout_ends_session(client):
    login_mitarbeiter(client)
    assert client.get("/").status_code == 200
    client.post("/logout")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_me_reflects_logged_in_user(client):
    login_chef(client)
    assert client.get("/api/me").json() == {
        "kassennummer": "910199",
        "name": "Chef",
        "role": "chef",
    }


def test_mitarbeiter_can_view_but_not_upload(client):
    login_mitarbeiter(client)
    assert client.get("/articles").status_code == 200
    assert client.get("/invoices").status_code == 200
    assert client.get("/api/articles").status_code == 200
    assert client.get("/api/invoices").status_code == 200
    assert client.get("/api/dashboard").status_code == 200
    # Rechnung hochladen bleibt Chefs vorbehalten.
    assert client.get("/preview", follow_redirects=False).status_code == 303
    assert (
        client.post(
            "/upload-preview", files={"file": ("x.pdf", b"", "application/pdf")}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/import-invoice",
            data={"expected_hash": "x", "confirmed": "true"},
            files={"file": ("x.pdf", b"", "application/pdf")},
        ).status_code
        == 403
    )
    assert client.delete("/api/invoices/1").status_code == 403


def test_chef_can_reach_upload_page_and_gate(client):
    login_chef(client)
    assert client.get("/preview", follow_redirects=False).status_code == 200
    # RBAC lässt den Chef durch; die 400 kommt aus einer davon unabhängigen Prüfung
    # (Import ohne Bestätigung), zeigt aber, dass der Aufruf nicht an der Rolle scheitert.
    r = client.post(
        "/import-invoice",
        data={"expected_hash": "x", "confirmed": "false"},
        files={"file": ("x.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 400


def test_chef_passes_delete_rbac_gate(client, monkeypatch):
    calls = {}

    def fake_delete_invoice(invoice_id, session_factory):
        calls["invoice_id"] = invoice_id
        return {
            "invoice_id": invoice_id,
            "invoice_number": "9001759392",
            "item_count": 0,
            "affected_products": 0,
        }

    monkeypatch.setattr("app.routers.history.delete_invoice", fake_delete_invoice)
    login_chef(client)
    r = client.delete("/api/invoices/42")
    assert r.status_code == 200
    assert calls["invoice_id"] == 42
