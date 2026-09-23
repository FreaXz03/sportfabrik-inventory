"""Bestand korrigieren (Phase C, Teilaufgabe C5).

Rechte (Regel 9, bestätigt 23.09.2026): alle Rollen. Gebucht wird aus der
Bestandsansicht heraus, also auf den Lagerort der Zeile; ob darauf gebucht
werden darf, prüft der Server (`resolve_wareneingang_lagerort`).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ..core.database import get_session
from ..core.i18n import translate
from ..services.korrektur import GRUENDE, KorrekturRejected, korrigieren
from .auth import get_language, require_login_api, resolve_wareneingang_lagerort

router = APIRouter()


@router.get("/api/korrektur/gruende")
def api_gruende(user=Depends(require_login_api)):
    return {"gruende": list(GRUENDE)}


class KorrekturBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    varianten_id: int
    lagerort_id: int | None = None
    # Als Text, damit nichts über float läuft (CLAUDE.md „Technik").
    gezaehlt: str
    grund: str
    freitext: str | None = None


@router.post("/api/korrektur")
async def api_korrigieren(
    request: Request,
    body: KorrekturBody,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Gezählte Menge buchen - gebucht wird nur die Differenz."""
    from ..core.database import SessionLocal

    lagerort = resolve_wareneingang_lagerort(
        request, session, user, body.lagerort_id, language
    )
    try:
        return await run_in_threadpool(
            lambda: korrigieren(
                SessionLocal,
                lagerort_id=lagerort.id,
                varianten_id=body.varianten_id,
                gezaehlt=body.gezaehlt,
                grund=body.grund,
                freitext=body.freitext,
                benutzer={"kassennummer": user.kassennummer, "name": user.name},
                language=language,
            )
        )
    except KorrekturRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.import_db_error", language)
        ) from exc
