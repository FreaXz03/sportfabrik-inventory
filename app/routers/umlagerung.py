"""Ware zwischen Lagerorten umlagern (Phase C, Teilaufgabe C4).

Rechte (24.09.2026): Umlagern dürfen nur Filialleiter/Zentrale. Seit
28.09.2026 wie eine Lieferung: die **Quelle** versendet (vorgewählt ist die
aktive Filiale; ob von dort gebucht werden darf, prüft der Server mit
`resolve_wareneingang_lagerort`), das Ziel bestätigt die Ankunft unter
„Lieferungen" (`/api/wareneingaenge/{id}/ankunft`, alle Rollen, D21).

Stornieren unterwegs (29.09.2026): Filialleiter für Umlagerungen aus ihren
eigenen Filialen und für selbst versendete, die Zentrale für alle.
"""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Lagerort
from ..services.lagerorte import (
    list_all_lagerorte,
    list_user_lagerorte,
    list_wareneingang_lagerorte,
)
from ..services.umlagerung import (
    UmlagerungForbidden,
    UmlagerungRejected,
    stornieren,
    umlagern,
)
from ..services.wareneingang import liste_erwartete
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


def _eigene_quellen(session, user) -> set[int] | None:
    """Quellen, deren Umlagerungen der Benutzer stornieren darf - None heisst
    alle (Zentrale)."""
    if user.role == "admin":
        return None
    return {lagerort.id for lagerort in list_user_lagerorte(session, user)}


@router.get("/api/umlagerung/unterwegs")
def api_unterwegs(
    quelle_id: int | None = Query(default=None),
    user=Depends(require_chef_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Umlagerungen unterwegs aus den eigenen Filialen und selbst versendete
    (Zentrale: alle), auf Wunsch nur aus einer Quelle."""
    erlaubt = _eigene_quellen(session, user)
    if quelle_id is not None:
        if erlaubt is not None and quelle_id not in erlaubt:
            raise HTTPException(403, translate("errors.auth.no_lagerort_access", language))
        erlaubt = {quelle_id}
    elif erlaubt is None:
        erlaubt = {lagerort.id for lagerort in list_all_lagerorte(session)}
    return {
        "umlagerungen": liste_erwartete(
            session,
            herkunft_ids=erlaubt,
            # Selbst versendete gehören dazu, ausser beim Filter auf eine Quelle.
            versendet_von=None if quelle_id is not None else user.kassennummer,
        )
    }


@router.post("/api/umlagerung/{wareneingang_id}/stornieren")
async def api_stornieren(
    wareneingang_id: int,
    user=Depends(require_chef_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    from ..core.database import SessionLocal

    erlaubt = _eigene_quellen(session, user)
    try:
        return await run_in_threadpool(
            lambda: stornieren(
                SessionLocal,
                wareneingang_id,
                erlaubte_quellen=erlaubt,
                benutzer={"kassennummer": user.kassennummer, "name": user.name},
                language=language,
            )
        )
    except UmlagerungForbidden as exc:
        raise HTTPException(403, str(exc)) from exc
    except UmlagerungRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.import_db_error", language)
        ) from exc
