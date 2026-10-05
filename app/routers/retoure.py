"""Kundenretouren und gesperrter Bestand (Paket 4a, 05.10.2026).

Rechte (Entscheid Q8): Passform/Geschmack bucht jede Mitarbeiterin in ihren
Filialen direkt; jeder andere Grund ist ein Antrag, den Filialleiter/Zentrale
genehmigt oder ablehnt. Freigeben darf eine Mitarbeiterin nur eine Passform-/
Geschmack-Retoure ihrer Filialen; Lieferantenretoure und Abschreiben sind
Filialleiter/Zentrale. Lesen dürfen alle alle Filialen (wie beim Bestand).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Lagerort
from ..services.lagerorte import list_wareneingang_lagerorte
from ..services.retoure import (
    GRUENDE,
    GRUENDE_DIREKT,
    ZUSTAENDE,
    RetoureForbidden,
    RetoureRejected,
    ergebnis_buchen,
    erfasse,
    genehmige,
    lehne_ab,
    liste_retouren,
)
from .auth import (
    get_active_lagerort,
    get_language,
    require_chef_api,
    require_login_api,
    resolve_wareneingang_lagerort,
)
from .operation_id import operation_id_aus_header

router = APIRouter()


def _benutzer(user) -> dict:
    return {"kassennummer": user.kassennummer, "name": user.name}


def _ist_chef(user) -> bool:
    return user.role in ("chef", "admin")


def _fehler(exc: Exception, language: str) -> HTTPException:
    if isinstance(exc, RetoureRejected):
        return HTTPException(409, str(exc))
    if isinstance(exc, RetoureForbidden):
        return HTTPException(403, str(exc))
    return HTTPException(503, translate("errors.preview.import_db_error", language))


@router.get("/api/retouren/stammdaten")
def api_stammdaten(user=Depends(require_login_api)):
    """Gründe (mit Kennzeichnung, welche direkt buchbar sind) und Zustände."""
    return {
        "gruende": [{"grund": g, "direkt": g in GRUENDE_DIREKT} for g in GRUENDE],
        "zustaende": list(ZUSTAENDE),
        "darf_verwalten": _ist_chef(user),
    }


@router.get("/api/retouren")
def api_liste(
    lagerort_id: int | None = None,
    alle: bool = False,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user=Depends(require_login_api),
    aktiver_lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    if alle:
        gewaehlt = None
    elif lagerort_id is not None:
        if session.get(Lagerort, lagerort_id) is None:
            raise HTTPException(404, translate("errors.bestand.unknown_lagerort", language))
        gewaehlt = lagerort_id
    else:
        gewaehlt = None if aktiver_lagerort is None else aktiver_lagerort.id
    ergebnis = liste_retouren(session, gewaehlt, status, limit, offset)
    ergebnis["gewaehlt"] = gewaehlt
    return ergebnis


class RetoureBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    varianten_id: int
    grund: str
    zustand: str
    lagerort_id: int | None = None
    menge: int | None = None
    freitext: str | None = None
    verkauf_bewegung_id: int | None = None
    erstattungsreferenz: str | None = None
    sofort_freigeben: bool = False


@router.post("/api/retouren")
async def api_erfassen(
    request: Request,
    body: RetoureBody,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
    operation_id: str | None = Depends(operation_id_aus_header),
):
    """Retoure erfassen - in einer eigenen Filiale (wie die manuelle Erfassung)."""
    from ..core.database import SessionLocal

    lagerort = resolve_wareneingang_lagerort(request, session, user, body.lagerort_id, language)
    try:
        return await run_in_threadpool(
            lambda: erfasse(
                SessionLocal,
                lagerort_id=lagerort.id,
                varianten_id=body.varianten_id,
                grund=body.grund,
                zustand=body.zustand,
                menge=body.menge,
                freitext=body.freitext,
                verkauf_bewegung_id=body.verkauf_bewegung_id,
                erstattungsreferenz=body.erstattungsreferenz,
                sofort_freigeben=body.sofort_freigeben,
                benutzer=_benutzer(user),
                language=language,
                operation_id=operation_id,
            )
        )
    except (RetoureRejected, RetoureForbidden, SQLAlchemyError) as exc:
        raise _fehler(exc, language) from exc


@router.post("/api/retouren/{retoure_id}/genehmigen")
async def api_genehmigen(
    retoure_id: int, user=Depends(require_chef_api), language: str = Depends(get_language)
):
    from ..core.database import SessionLocal

    try:
        return await run_in_threadpool(genehmige, SessionLocal, retoure_id, _benutzer(user), language)
    except (RetoureRejected, SQLAlchemyError) as exc:
        raise _fehler(exc, language) from exc


@router.post("/api/retouren/{retoure_id}/ablehnen")
async def api_ablehnen(
    retoure_id: int, user=Depends(require_chef_api), language: str = Depends(get_language)
):
    from ..core.database import SessionLocal

    try:
        return await run_in_threadpool(lehne_ab, SessionLocal, retoure_id, _benutzer(user), language)
    except (RetoureRejected, SQLAlchemyError) as exc:
        raise _fehler(exc, language) from exc


class ErgebnisBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ergebnis: str


@router.post("/api/retouren/{retoure_id}/ergebnis")
async def api_ergebnis(
    retoure_id: int,
    body: ErgebnisBody,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    from ..core.database import SessionLocal

    erlaubt = {lo.id for lo in list_wareneingang_lagerorte(session, user)}
    try:
        return await run_in_threadpool(
            lambda: ergebnis_buchen(
                SessionLocal,
                retoure_id,
                body.ergebnis,
                darf_verwalten=_ist_chef(user),
                erlaubte_lagerorte=erlaubt,
                benutzer=_benutzer(user),
                language=language,
            )
        )
    except (RetoureRejected, RetoureForbidden, SQLAlchemyError) as exc:
        raise _fehler(exc, language) from exc
