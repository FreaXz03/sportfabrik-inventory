"""Ware von Hand ausbuchen - Verkauf oder Abgang per Scan (Phase C,
Teilaufgabe C3).

Rechte (Regel 9): Ausbuchen ist Lagerarbeit, kein Dokumenten-Upload - das
dürfen auch Mitarbeiter. Vorgewählt ist die aktive Filiale; welcher Lagerort
gebucht werden darf, wird wie bei der Erfassung serverseitig geprüft
(`resolve_wareneingang_lagerort`). Denselben Weg nimmt der vorübergehende
Knopf „1 Stück abbuchen" in der Bestandsansicht (23.09.2026).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ..core.database import get_session
from ..core.i18n import translate
from ..services.ausbuchung import GRUENDE, AusbuchungRejected, ausbuchen, storniere
from ..services.lagerorte import list_wareneingang_lagerorte
from .auth import (
    get_active_lagerort,
    get_language,
    require_login_api,
    require_login_page,
    resolve_wareneingang_lagerort,
)

router = APIRouter()


@router.get("/ausbuchen", include_in_schema=False)
def ausbuchen_page(user=Depends(require_login_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "ausbuchen.html"
    )


@router.get("/api/ausbuchen/stammdaten")
def api_stammdaten(
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
):
    """Buchbare Lagerorte (eigene zuerst) und die Gründe (F14)."""
    return {
        "lagerorte": [
            {"id": eintrag.id, "code": eintrag.code, "name": eintrag.name}
            for eintrag in list_wareneingang_lagerorte(session, user)
        ],
        "lagerort_aktiv": None if lagerort is None else lagerort.id,
        "gruende": list(GRUENDE),
    }


class AusbuchenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grund: str
    ean: str | None = None
    varianten_id: int | None = None
    freitext: str | None = None
    lagerort_id: int | None = None


@router.post("/api/ausbuchen")
async def api_ausbuchen(
    request: Request,
    body: AusbuchenBody,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Ein Stück ausbuchen (F15). Die Antwort meldet `bestand_reicht_nicht`,
    wenn der Bestand vorher unter einem Stück lag - gebucht ist trotzdem."""
    from ..core.database import SessionLocal

    lagerort = resolve_wareneingang_lagerort(
        request, session, user, body.lagerort_id, language
    )
    try:
        return await run_in_threadpool(
            lambda: ausbuchen(
                SessionLocal,
                lagerort_id=lagerort.id,
                grund=body.grund,
                ean=body.ean,
                varianten_id=body.varianten_id,
                freitext=body.freitext,
                benutzer={"kassennummer": user.kassennummer, "name": user.name},
                language=language,
            )
        )
    except AusbuchungRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.import_db_error", language)
        ) from exc


@router.post("/api/ausbuchen/{bewegung_id}/storno")
async def api_storno(
    bewegung_id: int,
    user=Depends(require_login_api),
    language: str = Depends(get_language),
):
    """Einen Fehlscan per Gegenbuchung aufheben (Regel 2: nichts löschen)."""
    from ..core.database import SessionLocal

    try:
        return await run_in_threadpool(
            storniere,
            SessionLocal,
            bewegung_id,
            {"kassennummer": user.kassennummer, "name": user.name},
            language,
        )
    except AusbuchungRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.import_db_error", language)
        ) from exc
