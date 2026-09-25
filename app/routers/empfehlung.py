"""Empfehlung der Zentrale (D-F3, 25.09.2026) - Setzen und Übersicht sind
Sache der Zentrale; die Antwort der Filiale liegt in `reduktion.py`
(`POST /api/empfehlungen/{id}/antwort`, `GET /api/reduktionen`)."""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core.database import get_session
from ..core.models import Artikel, Lagerort
from ..services import reduktion_empfehlung
from .auth import require_admin_api, require_admin_page

router = APIRouter()


@router.get("/empfehlungen", include_in_schema=False)
def empfehlungen_page(user=Depends(require_admin_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "empfehlungen.html"
    )


@router.get("/api/empfehlungen")
def api_empfehlungen_liste(
    user=Depends(require_admin_api),
    session=Depends(get_session),
):
    return {"empfehlungen": reduktion_empfehlung.liste_zentrale(session)}


class EmpfehlungBody(BaseModel):
    artikel_id: int
    lagerort_id: int
    prozent: int
    ab_datum: date


@router.post("/api/empfehlungen")
def api_empfehlung_setzen(
    body: EmpfehlungBody,
    user=Depends(require_admin_api),
    session=Depends(get_session),
):
    if session.get(Artikel, body.artikel_id) is None:
        raise HTTPException(404, "Artikel nicht gefunden.")
    if session.get(Lagerort, body.lagerort_id) is None:
        raise HTTPException(404, "Lagerort nicht gefunden.")
    try:
        return reduktion_empfehlung.setzen(
            session,
            artikel_id=body.artikel_id,
            lagerort_id=body.lagerort_id,
            prozent=body.prozent,
            ab_datum=body.ab_datum,
            benutzer=user,
        )
    except reduktion_empfehlung.EmpfehlungRejected as exc:
        raise HTTPException(422, str(exc))
