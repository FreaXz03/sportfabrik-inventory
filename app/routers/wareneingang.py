"""Erwartete Lieferungen ansehen und ihre Ankunft bestätigen (Phase B,
Teilaufgabe B5).

Rechte (D21): Ankunft bestätigen ist Lagerarbeit - das dürfen auch
Mitarbeiter, anders als das Hochladen von Dokumenten (Regel 9). Die Liste
zeigt standardmässig die Lieferungen der aktiven Filiale; welche Filiale
gebucht wird, steht ohnehin am Wareneingang selbst, nicht am Benutzer.
"""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..core.database import get_session
from ..core.i18n import translate
from ..services.wareneingang import (
    AnkunftRejected,
    bestaetige_ankunft,
    liste_erwartete,
)
from .auth import (
    get_active_lagerort,
    get_language,
    require_login_api,
    require_login_page,
)

router = APIRouter()


@router.get("/wareneingaenge", include_in_schema=False)
def wareneingaenge_page(user=Depends(require_login_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "wareneingaenge.html"
    )


@router.get("/api/wareneingaenge")
def api_erwartete_wareneingaenge(
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
):
    """Offene Lieferungen der aktiven Filiale (ohne aktive Filiale: alle)."""
    return {
        "lagerort": None
        if lagerort is None
        else {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
        "wareneingaenge": liste_erwartete(
            session, None if lagerort is None else lagerort.id
        ),
    }


class AnkunftBody(BaseModel):
    # Positions-Id → jetzt eingetroffene Menge (als Text, damit nichts über
    # float läuft - siehe CLAUDE.md „Beträge/Mengen als Numeric, nie float").
    mengen: dict[str, str] = Field(default_factory=dict)
    eingangsdatum: str | None = None


@router.post("/api/wareneingaenge/{wareneingang_id}/ankunft")
async def api_ankunft_bestaetigen(
    wareneingang_id: int,
    body: AnkunftBody,
    user=Depends(require_login_api),
    language: str = Depends(get_language),
):
    from ..core.database import SessionLocal
    from sqlalchemy.exc import SQLAlchemyError

    eingangsdatum = None
    if body.eingangsdatum:
        try:
            eingangsdatum = date.fromisoformat(body.eingangsdatum)
        except ValueError as exc:
            raise HTTPException(
                422, translate("errors.wareneingang.invalid_date", language)
            ) from exc
    try:
        return await run_in_threadpool(
            bestaetige_ankunft,
            wareneingang_id,
            body.mengen,
            SessionLocal,
            {"kassennummer": user.kassennummer, "name": user.name},
            eingangsdatum,
            language,
        )
    except AnkunftRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.import_db_error", language)
        ) from exc
