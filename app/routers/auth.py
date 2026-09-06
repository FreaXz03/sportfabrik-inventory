"""Anmeldung nach Kassensystem-Muster: Mitarbeiter mit blosser Kassennummer,
Chefs zusätzlich mit Passwort. Session-Cookie bleibt aktiv bis zur manuellen
Abmeldung (kein automatisches Ablaufen), analog zum bestehenden Kassensystem.
"""
import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select

from ..core.database import get_session
from ..core.models import User
from ..core.security import verify_password

load_dotenv()

SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    raise RuntimeError(
        "SESSION_SECRET fehlt. In .env (lokal) bzw. .env.server (Server) setzen "
        "- ein langer, zufälliger Wert, z.B. mit 'python -c \"import secrets; print(secrets.token_hex(32))\"'."
    )

# "Bis manuell abgemeldet": Cookie lebt praktisch unbegrenzt (5 Jahre).
SESSION_MAX_AGE = 60 * 60 * 24 * 365 * 5

router = APIRouter()


def _load_user(request: Request, session) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return session.get(User, user_id)


def require_login_page(request: Request, session=Depends(get_session)) -> User:
    """Für Seiten (GET, liefert HTML): leitet nicht angemeldete Nutzer zum Login um."""
    user = _load_user(request, session)
    if user is None:
        raise HTTPException(303, headers={"Location": f"/login?next={quote(request.url.path)}"})
    return user


def require_login_api(request: Request, session=Depends(get_session)) -> User:
    """Für API-/Aktions-Endpunkte (JSON): antwortet mit 401 statt umzuleiten."""
    user = _load_user(request, session)
    if user is None:
        raise HTTPException(401, "Bitte zuerst anmelden.")
    return user


def require_chef_page(user: User = Depends(require_login_page)) -> User:
    if user.role != "chef":
        raise HTTPException(303, headers={"Location": "/"})
    return user


def require_chef_api(user: User = Depends(require_login_api)) -> User:
    if user.role != "chef":
        raise HTTPException(403, "Dafür ist ein Filialleiter-Konto nötig.")
    return user


@router.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(Path(__file__).resolve().parents[1] / "templates" / "login.html")


@router.post("/login")
def login(request: Request, kassennummer: str = Form(...), password: str | None = Form(None),
          session=Depends(get_session)):
    user = session.scalar(select(User).where(User.kassennummer == kassennummer.strip()))
    if user is None:
        raise HTTPException(401, "Unbekannte Kassennummer.")
    if user.role == "chef":
        if not password:
            return {"requires_password": True}
        if not verify_password(password, user.password_hash):
            raise HTTPException(401, "Falsches Passwort.")
    request.session.clear()
    request.session["user_id"] = user.id
    return {"name": user.name, "role": user.role}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/api/me")
def me(user: User = Depends(require_login_api)):
    return {"kassennummer": user.kassennummer, "name": user.name, "role": user.role}
