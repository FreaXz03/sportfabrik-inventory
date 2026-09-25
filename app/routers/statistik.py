"""Statistikseite (Anforderung 9, 24.09.2026) - nur Filialleiter/Zentrale."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..core.database import get_session
from ..services.lagerorte import list_all_lagerorte
from ..services.statistik import UnbekannterZeitraum, ZEITRAEUME, auswertung
from .auth import require_chef_api, require_chef_page

router = APIRouter()


@router.get("/statistiken", include_in_schema=False)
def statistiken_page(user=Depends(require_chef_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "statistiken.html"
    )


@router.get("/api/statistik")
def api_statistik(
    zeitraum: str,
    lagerort_id: int | None = None,
    user=Depends(require_chef_api),
    session=Depends(get_session),
):
    if zeitraum not in ZEITRAEUME:
        raise HTTPException(422, f"zeitraum muss einer von {', '.join(ZEITRAEUME)} sein")
    try:
        ergebnis = auswertung(session, zeitraum, lagerort_id)
    except UnbekannterZeitraum:
        raise HTTPException(422, f"zeitraum muss einer von {', '.join(ZEITRAEUME)} sein")
    ergebnis["lagerorte"] = [
        {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name}
        for lagerort in list_all_lagerorte(session)
        if lagerort.verkauf
    ]
    return ergebnis
