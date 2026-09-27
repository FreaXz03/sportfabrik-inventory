"""Runterschreiben (Phase D, Teil 1): welche Artikel einer Filiale −50 % bzw.
−70 % erreicht haben oder in den nächsten 30 Tagen erreichen (Regel 6, D5).

Rechte: lesen dürfen alle, und zwar alle Filialen (F3). Etiketten drucken ist
Lagerarbeit und ebenfalls für alle Rollen (Regel 9); der Druck selbst liegt in
`app/routers/etiketten.py`.
"""

from pathlib import Path

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Artikel, Lagerort, ReduktionEmpfehlungZentrale
from ..services.etikett import rolle
from ..services import reduktion_manuell
from ..services import reduktion_bestaetigung
from ..services import reduktion_empfehlung
from ..services.lagerorte import list_all_lagerorte, list_wareneingang_lagerorte
from ..services.uebersicht import VORSCHAU_TAGE, reduktions_liste
from .auth import (
    get_active_lagerort,
    get_language,
    require_login_api,
    require_login_page,
    resolve_wareneingang_lagerort,
)

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
        # Von Hand gewählte Stufen dieser Filiale (24.09.2026), separat.
        "manuell": reduktion_manuell.liste(session, lagerort.id),
        # Offene Empfehlungen der Zentrale (D-F3, 25.09.2026).
        "empfehlungen": reduktion_empfehlung.liste_offen_fuer_filiale(session, lagerort.id),
        "lagerorte": [
            {"id": lo.id, "code": lo.code, "name": lo.name}
            for lo in list_all_lagerorte(session)
            if lo.verkauf  # externe Standorte haben keine Reduktionsuhr (D13)
        ],
    }


def _artikel_id(session, varianten_id: int, language: str) -> int:
    artikel_id = reduktion_manuell.artikel_von_variante(session, varianten_id)
    if artikel_id is None:
        raise HTTPException(404, translate("errors.bestand.unknown_article", language))
    return artikel_id


@router.get("/api/articles/{varianten_id}/reduktion")
def api_artikel_reduktion(
    varianten_id: int,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Artikeldetails: Empfehlung, Wahl von Hand und wirksame Stufe des
    Modells in jeder Filiale (externe Lager haben keine Reduktion, D13)."""
    artikel_id = _artikel_id(session, varianten_id, language)
    erlaubt = {lo.id for lo in list_wareneingang_lagerorte(session, user)}
    return {
        "filialen": [
            {
                "lagerort": {"id": lo.id, "code": lo.code, "name": lo.name},
                **reduktion_manuell.stufen(session, lo.id, [artikel_id])[artikel_id],
                "darf_aendern": lo.id in erlaubt,
            }
            for lo in list_all_lagerorte(session)
            if lo.verkauf
        ]
    }


class BestaetigenBody(BaseModel):
    artikel_id: int
    lagerort_id: int
    stufe: Literal[50, 70]


@router.post("/api/reduktionen/bestaetigen")
def api_bestaetigen(
    body: BestaetigenBody,
    request: Request,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Runterschreiben bestätigt (D-F1): das Modell verschwindet aus der
    fälligen Liste dieser Filiale, bis die nächste Stufe fällig wird."""
    lagerort = _filiale_zum_aendern(request, session, user, body.lagerort_id, language)
    if session.get(Artikel, body.artikel_id) is None:
        raise HTTPException(404, translate("errors.bestand.unknown_article", language))
    reduktion_bestaetigung.bestaetigen(session, body.artikel_id, lagerort.id, body.stufe, user)
    return {"artikel_id": body.artikel_id, "lagerort_id": lagerort.id, "stufe": body.stufe}


class EmpfehlungAntwortBody(BaseModel):
    status: Literal["uebernommen", "abgelehnt"]
    grund: str | None = None


@router.post("/api/empfehlungen/{empfehlung_id}/antwort")
def api_empfehlung_antworten(
    empfehlung_id: int,
    body: EmpfehlungAntwortBody,
    request: Request,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Die Filiale übernimmt eine Empfehlung der Zentrale (setzt dieselbe
    Stufe von Hand) oder lehnt sie mit Grund ab - gleiche Grenze wie die
    manuelle Reduktion (Mitarbeiter nur in ihren Filialen)."""
    eintrag = session.get(ReduktionEmpfehlungZentrale, empfehlung_id)
    if eintrag is None:
        raise HTTPException(404, "Empfehlung nicht gefunden.")
    _filiale_zum_aendern(request, session, user, eintrag.lagerort_id, language)
    try:
        ergebnis = reduktion_empfehlung.antworten(
            session, empfehlung_id, status=body.status, grund=body.grund, benutzer=user
        )
    except reduktion_empfehlung.EmpfehlungRejected as exc:
        raise HTTPException(422, str(exc))
    return ergebnis


class ManuellBody(BaseModel):
    varianten_id: int
    lagerort_id: int
    prozent: Literal[30, 50, 70]


def _filiale_zum_aendern(request, session, user, lagerort_id, language):
    """Gleiche Grenze wie Erfassung/Korrektur: Mitarbeiter nur eigene
    Filialen. Dazu nur Filialen mit Verkauf - extern gibt es keine Reduktion."""
    lagerort = resolve_wareneingang_lagerort(request, session, user, lagerort_id, language)
    if not lagerort.verkauf:
        raise HTTPException(409, translate("errors.reduktion.no_sales_location", language))
    return lagerort


@router.put("/api/reduktion/manuell")
def api_manuell_setzen(
    body: ManuellBody,
    request: Request,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    lagerort = _filiale_zum_aendern(request, session, user, body.lagerort_id, language)
    artikel_id = _artikel_id(session, body.varianten_id, language)
    return reduktion_manuell.setzen(session, artikel_id, lagerort.id, body.prozent, user)


@router.delete("/api/reduktion/manuell")
def api_manuell_zuruecksetzen(
    varianten_id: int,
    lagerort_id: int,
    request: Request,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Zurück zur Empfehlung nach Regel 6."""
    lagerort = _filiale_zum_aendern(request, session, user, lagerort_id, language)
    artikel_id = _artikel_id(session, varianten_id, language)
    return reduktion_manuell.setzen(session, artikel_id, lagerort.id, None, user)
