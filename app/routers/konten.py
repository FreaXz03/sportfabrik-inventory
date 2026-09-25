"""Kontoverwaltung (Anforderung 13, 24./25.09.2026) - nur die Zentrale."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core.database import get_session
from ..core.models import User
from ..services import konten
from .auth import get_language, require_admin_api, require_admin_page

router = APIRouter()


@router.get("/konten", include_in_schema=False)
def konten_page(user=Depends(require_admin_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "konten.html"
    )


@router.get("/api/konten")
def api_konten(user=Depends(require_admin_api), session=Depends(get_session)):
    return {"konten": konten.liste(session)}


class KontoBody(BaseModel):
    kassennummer: str
    name: str
    role: str
    password: str | None = None
    lagerort_ids: list[int] = []


@router.post("/api/konten")
def api_konto_anlegen(
    body: KontoBody,
    user=Depends(require_admin_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        return konten.anlegen(
            session,
            kassennummer=body.kassennummer,
            name=body.name,
            role=body.role,
            password=body.password,
            lagerort_ids=body.lagerort_ids,
        )
    except konten.KontoDuplicate:
        raise HTTPException(409, "Diese Kassennummer ist schon vergeben.")
    except konten.KontoRejected as exc:
        raise HTTPException(422, str(exc))


@router.delete("/api/konten/{konto_id}")
def api_konto_loeschen(
    konto_id: int,
    user: User = Depends(require_admin_api),
    session=Depends(get_session),
):
    if session.get(User, konto_id) is None:
        raise HTTPException(404, "Konto nicht gefunden.")
    try:
        konten.loeschen(session, konto_id, user)
    except konten.KontoSelbstloeschung:
        raise HTTPException(409, "Das eigene Konto lässt sich nicht löschen.")
    return {"geloescht": konto_id}
