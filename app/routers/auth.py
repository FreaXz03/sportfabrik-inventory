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
from ..core.i18n import LANGUAGES, normalize_language, translate
from ..core.models import Lagerort, User
from ..core.security import verify_password
from ..services.lagerorte import (
    get_primary_lagerort,
    list_user_lagerorte,
    list_wareneingang_lagerorte,
)

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


def _resolve_language(request: Request, user: User | None) -> str:
    """Sprache für Antworten dieses Requests: eingeloggt die Kontosprache,
    sonst (z.B. /login) aus dem Accept-Language-Header, sonst Deutsch."""
    if user is not None:
        return normalize_language(user.language)
    accept_language = request.headers.get("accept-language", "")
    for part in accept_language.split(","):
        code = part.split(";")[0].strip()[:2].lower()
        if code in LANGUAGES:
            return code
    return normalize_language(None)


def get_language_optional(request: Request, session=Depends(get_session)) -> str:
    """Sprache ermitteln, ohne eine Anmeldung vorauszusetzen (z.B. /login)."""
    return _resolve_language(request, _load_user(request, session))


def require_login_page(request: Request, session=Depends(get_session)) -> User:
    """Für Seiten (GET, liefert HTML): leitet nicht angemeldete Nutzer zum Login um."""
    user = _load_user(request, session)
    if user is None:
        raise HTTPException(
            303, headers={"Location": f"/login?next={quote(request.url.path)}"}
        )
    return user


def require_login_api(
    request: Request, session=Depends(get_session)
) -> User:
    """Für API-/Aktions-Endpunkte (JSON): antwortet mit 401 statt umzuleiten."""
    user = _load_user(request, session)
    if user is None:
        raise HTTPException(
            401, translate("errors.auth.not_logged_in", _resolve_language(request, None))
        )
    return user


def get_language(user: User = Depends(require_login_api)) -> str:
    """Sprache für Endpunkte, die ohnehin eine Anmeldung verlangen - nutzt den
    von require_login_api bereits geladenen Benutzer (FastAPI cached
    Dependencies pro Request, keine zusätzliche DB-Abfrage). `user` ist in
    Produktion nie None (require_login_api wirft sonst 401) - getattr fängt
    nur Tests ab, die require_login_api mit `lambda: None` überschreiben."""
    return normalize_language(getattr(user, "language", None))


def require_chef_page(user: User = Depends(require_login_page)) -> User:
    if user.role not in ("chef", "admin"):
        raise HTTPException(303, headers={"Location": "/"})
    return user


def require_chef_api(
    user: User = Depends(require_login_api), language: str = Depends(get_language)
) -> User:
    if user.role not in ("chef", "admin"):
        raise HTTPException(403, translate("errors.auth.chef_required", language))
    return user


def require_active_lagerort(
    request: Request,
    user: User = Depends(require_chef_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
) -> Lagerort:
    """Konkrete Filiale für Aktionen, die eine Filiale brauchen (z.B. Wareneingang
    buchen) - Admin ohne gewählte Filiale ("alle Filialen") kann nicht buchen,
    muss vorher eine Filiale wählen (siehe /api/active-lagerort)."""
    lagerort = _resolve_active_lagerort(request, session, user)
    if lagerort is None:
        raise HTTPException(400, translate("errors.auth.lagerort_required", language))
    return lagerort


def get_active_lagerort(
    request: Request,
    user: User = Depends(require_login_api),
    session=Depends(get_session),
) -> Lagerort | None:
    """Aktive Filiale für Ansichten, die ohne sie auskommen (dann eben
    filialübergreifend) - im Gegensatz zu `require_active_lagerort`, das eine
    Filiale erzwingt, weil gebucht wird."""
    return _resolve_active_lagerort(request, session, user)


def resolve_wareneingang_lagerort(
    request: Request, session, user: User, lagerort_id: int | None, language: str
) -> Lagerort:
    """Ziel-Lagerort für einen Wareneingang.

    Ohne ausdrückliche Wahl gilt die aktive Filiale (wie bisher). Wird ein
    Lagerort mitgegeben - die Oberfläche schickt den aus der Lieferadresse
    vorgeschlagenen, D19 -, muss der Benutzer darauf buchen dürfen; geprüft
    wird das hier serverseitig, nie nur im Browser.
    """
    if lagerort_id is None:
        lagerort = _resolve_active_lagerort(request, session, user)
        if lagerort is None:
            raise HTTPException(400, translate("errors.auth.lagerort_required", language))
        return lagerort
    erlaubt = list_wareneingang_lagerorte(session, user)
    match = next((lo for lo in erlaubt if lo.id == lagerort_id), None)
    if match is None:
        raise HTTPException(403, translate("errors.auth.no_lagerort_access", language))
    return match


def _resolve_active_lagerort(
    request: Request, session, user: User
) -> Lagerort | None:
    """Aktive Filiale für die Session: der zuletzt per Filialwechsel gewählte
    Lagerort, sofern der Benutzer noch Zugriff darauf hat, sonst die primäre
    Zuordnung. None bedeutet „alle Filialen" (nur für Admin möglich)."""
    # list_user_lagerorte() liefert Admins bereits alle Lagerorte, deshalb
    # genuegt die Suche in `allowed` - ein Sonderzweig fuer Admin waere hier
    # nie erreichbar.
    allowed = list_user_lagerorte(session, user)
    active_id = request.session.get("active_lagerort_id")
    if active_id is not None:
        match = next((lo for lo in allowed if lo.id == active_id), None)
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
    language: str = Depends(get_language_optional),
):
    user = session.scalar(select(User).where(User.kassennummer == kassennummer.strip()))
    if user is None:
        raise HTTPException(401, translate("errors.auth.unknown_kassennummer", language))
    if user.role in ("chef", "admin"):
        if not password:
            return {"requires_password": True}
        if not verify_password(password, user.password_hash):
            raise HTTPException(401, translate("errors.auth.wrong_password", language))
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
def me(
    request: Request,
    user: User = Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    active = _resolve_active_lagerort(request, session, user)
    return {
        "kassennummer": user.kassennummer,
        "name": user.name,
        "role": user.role,
        "role_label": translate(f"role.{user.role}", language),
        "language": user.language,
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
    language: str = Depends(get_language),
):
    if body.lagerort_id is None:
        if user.role != "admin":
            raise HTTPException(400, translate("errors.auth.admin_required_all_lagerorte", language))
        request.session["active_lagerort_id"] = None
        return {"lagerort": None}
    allowed = list_user_lagerorte(session, user)
    match = next((lo for lo in allowed if lo.id == body.lagerort_id), None)
    if match is None:
        raise HTTPException(403, translate("errors.auth.no_lagerort_access", language))
    request.session["active_lagerort_id"] = match.id
    return {"lagerort": _lagerort_data(match)}


class LanguageBody(BaseModel):
    language: str


@router.post("/api/language")
def set_language(
    body: LanguageBody,
    user: User = Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    if body.language not in LANGUAGES:
        raise HTTPException(422, translate("errors.auth.invalid_language", language))
    user.language = body.language
    session.commit()
    return {"language": user.language}
