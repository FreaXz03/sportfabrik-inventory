"""Bestand ansehen (Phase C, Teilaufgabe C2).

Rechte: jede Anmeldung darf lesen, und zwar **alle** Filialen (bestätigt am
22.09.2026, siehe docs/projekt-kontext.md Abschnitt 10). Der Filialwechsel
oben in der Sitzungsleiste bleibt davon unberührt - er bestimmt nur, was
vorausgewählt ist und wohin gebucht wird.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Lagerort
from ..services.bestand import STANDARD_LIMIT, liste_bestand
from ..services.lagerorte import list_all_lagerorte
from .auth import (
    get_active_lagerort,
    get_language,
    require_login_api,
    require_login_page,
)

router = APIRouter()


@router.get("/bestand", include_in_schema=False)
def bestand_page(user=Depends(require_login_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "bestand.html"
    )


@router.get("/api/bestand")
def api_bestand(
    lagerort_id: int | None = None,
    alle: bool = False,
    q: str | None = None,
    nur_vorhanden: bool = True,
    limit: int = STANDARD_LIMIT,
    offset: int = 0,
    user=Depends(require_login_api),
    aktiver_lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Bestand der gewählten Filiale; ohne Wahl die aktive, mit `alle=true`
    filialübergreifend."""
    if alle:
        gewaehlt = None
    elif lagerort_id is not None:
        if session.scalar(select(Lagerort.id).where(Lagerort.id == lagerort_id)) is None:
            raise HTTPException(
                404, translate("errors.bestand.unknown_lagerort", language)
            )
        gewaehlt = lagerort_id
    else:
        gewaehlt = None if aktiver_lagerort is None else aktiver_lagerort.id

    ergebnis = liste_bestand(
        session,
        lagerort_id=gewaehlt,
        suche=q,
        nur_vorhanden=nur_vorhanden,
        limit=limit,
        offset=offset,
    )
    ergebnis["gewaehlt"] = gewaehlt
    ergebnis["lagerorte"] = [
        {
            "id": lagerort.id,
            "code": lagerort.code,
            "name": lagerort.name,
            "verkauf": bool(lagerort.verkauf),
        }
        for lagerort in list_all_lagerorte(session)
    ]
    return ergebnis
