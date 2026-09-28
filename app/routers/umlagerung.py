"""Ware zwischen Lagerorten umlagern (Phase C, Teilaufgabe C4).

Rechte (24.09.2026): Umlagern dürfen nur Filialleiter/Zentrale. Seit
28.09.2026 wie eine Lieferung: die **Quelle** versendet (vorgewählt ist die
aktive Filiale; ob von dort gebucht werden darf, prüft der Server mit
`resolve_wareneingang_lagerort`), das Ziel bestätigt die Ankunft unter
„Lieferungen" (`/api/wareneingaenge/{id}/ankunft`, alle Rollen, D21).
"""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Lagerort
from ..services.lagerorte import list_all_lagerorte, list_wareneingang_lagerorte
from ..services.umlagerung import UmlagerungRejected, umlagern
from .auth import (
    get_active_lagerort,
    get_language,
    require_chef_api,
    require_chef_page,
    resolve_wareneingang_lagerort,
)

router = APIRouter()


@router.get("/umlagern", include_in_schema=False)
def umlagern_page(user=Depends(require_chef_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "umlagern.html"
    )


def _lagerort(eintrag) -> dict:
    return {
        "id": eintrag.id,
        "code": eintrag.code,
        "name": eintrag.name,
        # Regel 6/D13: ohne Verkauf kein Eingangsdatum, keine Uhr.
        "verkauf": bool(eintrag.verkauf),
    }


@router.get("/api/umlagerung/stammdaten")
def api_stammdaten(
    user=Depends(require_chef_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
):
    """Quellen (buchbare, eigene zuerst), Ziele (alle Lagerorte), die aktive
    Filiale als vorgewählte Quelle und das heutige Datum vom Server."""
    return {
        "quellen": [
            _lagerort(eintrag) for eintrag in list_wareneingang_lagerorte(session, user)
        ],
        "ziele": [_lagerort(eintrag) for eintrag in list_all_lagerorte(session)],
        "quelle_aktiv": None if lagerort is None else lagerort.id,
        "heute": date.today().isoformat(),
    }


class UmlagerungPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    varianten_id: int
    # Als Text, damit nichts über float läuft (CLAUDE.md „Technik").
    menge: str


class UmlagerungBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quelle_id: int | None = None
    ziel_id: int
    versanddatum: str | None = None
    positionen: list[UmlagerungPosition] = Field(default_factory=list)


@router.post("/api/umlagerung")
async def api_umlagern(
    request: Request,
    body: UmlagerungBody,
    user=Depends(require_chef_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    from ..core.database import SessionLocal

    quelle = resolve_wareneingang_lagerort(request, session, user, body.quelle_id, language)
    if session.get(Lagerort, body.ziel_id) is None:
        raise HTTPException(404, translate("errors.bestand.unknown_lagerort", language))
    versanddatum = None
    if body.versanddatum:
        try:
            versanddatum = date.fromisoformat(body.versanddatum)
        except ValueError as exc:
            raise HTTPException(
                422, translate("errors.wareneingang.invalid_date", language)
            ) from exc
    try:
        return await run_in_threadpool(
            lambda: umlagern(
                SessionLocal,
                quelle_id=quelle.id,
                ziel_id=body.ziel_id,
                positionen=[position.model_dump() for position in body.positionen],
                versanddatum=versanddatum,
                benutzer={"kassennummer": user.kassennummer, "name": user.name},
                language=language,
            )
        )
    except UmlagerungRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.import_db_error", language)
        ) from exc
