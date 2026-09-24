"""Runterschreiben (Phase D, Teil 1): welche Artikel einer Filiale −50 % bzw.
−70 % erreicht haben oder in den nächsten 30 Tagen erreichen (Regel 6, D5).

Rechte: lesen dürfen alle, und zwar alle Filialen (F3). Etiketten drucken ist
Lagerarbeit und ebenfalls für alle Rollen (Regel 9); der Druck selbst liegt in
`app/routers/etiketten.py`.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Lagerort
from ..services.etikett import rolle
from ..services.lagerorte import list_all_lagerorte
from ..services.uebersicht import VORSCHAU_TAGE, reduktions_liste
from .auth import get_active_lagerort, get_language, require_login_api, require_login_page

router = APIRouter()


@router.get("/runterschreiben", include_in_schema=False)
def runterschreiben_page(user=Depends(require_login_page)):
    return FileResponse(Path(__file__).resolve().parents[1] / "templates" / "runterschreiben.html")


@router.get("/api/reduktionen")
def api_reduktionen(
    lagerort_id: int | None = None,
    user=Depends(require_login_api),
    aktiver_lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Fällige und bald fällige Reduktionen je Artikel in einer Filiale -
    ohne Wahl die aktive. Reduktion gilt je Filiale, darum braucht es eine."""
    lagerort = session.get(Lagerort, lagerort_id) if lagerort_id is not None else aktiver_lagerort
    if lagerort is None:
        raise HTTPException(
            400 if lagerort_id is None else 404,
            translate(
                "errors.auth.lagerort_required" if lagerort_id is None else "errors.bestand.unknown_lagerort",
                language,
            ),
        )
    artikel = reduktions_liste(session, lagerort.id)
    for eintrag in artikel:
        eintrag["rolle"] = rolle(eintrag["stufe"])
    return {
        "lagerort": {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
        "vorschau_tage": VORSCHAU_TAGE,
        "artikel": artikel,
        "lagerorte": [
            {"id": lo.id, "code": lo.code, "name": lo.name}
            for lo in list_all_lagerorte(session)
            if lo.verkauf  # externe Standorte haben keine Reduktionsuhr (D13)
        ],
    }
