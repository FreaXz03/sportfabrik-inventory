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
from pydantic import BaseModel
from sqlalchemy import select

from ..core.database import get_session
from ..core.models import Lagerort, User
from ..core.security import verify_password
from ..services.lagerorte import get_primary_lagerort, list_user_lagerorte

ROLE_LABELS = {"mitarbeiter": "Mitarbeiter", "chef": "Filialleiter", "admin": "Zentrale"}

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
        raise HTTPException(
            303, headers={"Location": f"/login?next={quote(request.url.path)}"}
        )
    return user


def require_login_api(request: Request, session=Depends(get_session)) -> User:
    """Für API-/Aktions-Endpunkte (JSON): antwortet mit 401 statt umzuleiten."""
    user = _load_user(request, session)
    if user is None:
        raise HTTPException(401, "Bitte zuerst anmelden.")
    return user


def require_chef_page(user: User = Depends(require_login_page)) -> User:
    if user.role not in ("chef", "admin"):
        raise HTTPException(303, headers={"Location": "/"})
    return user


def require_chef_api(user: User = Depends(require_login_api)) -> User:
    if user.role not in ("chef", "admin"):
        raise HTTPException(403, "Dafür ist ein Filialleiter-Konto nötig.")
    return user


def _resolve_active_lagerort(
    request: Request, session, user: User
) -> Lagerort | None:
    """Aktive Filiale für die Session: der zuletzt per Filialwechsel gewählte
    Lagerort, sofern der Benutzer noch Zugriff darauf hat, sonst die primäre
    Zuordnung. None bedeutet „alle Filialen" (nur für Admin möglich)."""
    allowed = list_user_lagerorte(session, user)
    active_id = request.session.get("active_lagerort_id")
    if active_id is not None:
        match = next((lo for lo in allowed if lo.id == active_id), None)
        if match is not None:
            return match
        if user.role == "admin":
            match = session.get(Lagerort, active_id)
            if match is not None:
                return match
    return get_primary_lagerort(session, user)


@router.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "login.html"
    )


@router.post("/login")
def login(
    request: Request,
    kassennummer: str = Form(...),
    password: str | None = Form(None),
    session=Depends(get_session),
):
    user = session.scalar(select(User).where(User.kassennummer == kassennummer.strip()))
    if user is None:
        raise HTTPException(401, "Unbekannte Kassennummer.")
    if user.role in ("chef", "admin"):
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


def _lagerort_data(lagerort: Lagerort | None) -> dict | None:
    if lagerort is None:
        return None
    return {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name}


@router.get("/api/me")
def me(request: Request, user: User = Depends(require_login_api), session=Depends(get_session)):
    active = _resolve_active_lagerort(request, session, user)
    return {
        "kassennummer": user.kassennummer,
        "name": user.name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "lagerort": _lagerort_data(active),
        "lagerorte": [_lagerort_data(lo) for lo in list_user_lagerorte(session, user)],
        "kann_alle_filialen_waehlen": user.role == "admin",
    }


class ActiveLagerortBody(BaseModel):
    lagerort_id: int | None = None


@router.post("/api/active-lagerort")
def set_active_lagerort(
    body: ActiveLagerortBody,
    request: Request,
    user: User = Depends(require_login_api),
    session=Depends(get_session),
):
    if body.lagerort_id is None:
        if user.role != "admin":
            raise HTTPException(400, "Nur die Zentrale kann alle Filialen zugleich sehen.")
        request.session["active_lagerort_id"] = None
        return {"lagerort": None}
    allowed = list_user_lagerorte(session, user)
    match = next((lo for lo in allowed if lo.id == body.lagerort_id), None)
    if match is None:
        raise HTTPException(403, "Kein Zugriff auf diese Filiale.")
    request.session["active_lagerort_id"] = match.id
    return {"lagerort": _lagerort_data(match)}
