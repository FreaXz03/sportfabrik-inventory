"""Ware von Hand erfassen - Scanner oder Tastatur, ohne Beleg (Phase B,
Teilaufgabe B6).

Rechte (Regel 9/D21): Erfassen ist Lagerarbeit, kein Dokumenten-Upload - das
dürfen auch Mitarbeiter. Der Ziel-Lagerort wird wie beim Import serverseitig
geprüft (`resolve_wareneingang_lagerort`, D26): vorgewählt ist die aktive
Filiale, gebucht werden darf auf jeden Lagerort - eine Direktlieferung kann
auch für eine andere Filiale oder einen externen Standort (GEWA, VEBO,
Dietikon - ohne eigenes Personal, D11) eintreffen.
"""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Lieferant
from ..services.kategorien import liste_kategorien
from ..services.lagerorte import list_wareneingang_lagerorte
from ..services.manuelle_erfassung import (
    ErfassungRejected,
    erfasse_wareneingang,
    variante_per_ean,
)
from .auth import (
    get_active_lagerort,
    get_language,
    require_login_api,
    require_login_page,
    resolve_wareneingang_lagerort,
)

router = APIRouter()


@router.get("/erfassen", include_in_schema=False)
def erfassen_page(user=Depends(require_login_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "erfassen.html"
    )


@router.get("/api/erfassen/stammdaten")
def api_stammdaten(
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
):
    """Auswahllisten für die Erfassung: buchbare Lagerorte (D26, eigene zuerst),
    bekannte Lieferanten und Kassenkategorien (beide optional, D23) und das
    heutige Datum vom Server - die Kasse im Laden muss dafür keine richtige
    Uhr haben."""
    lagerorte = list_wareneingang_lagerorte(session, user)
    lieferanten = session.scalars(select(Lieferant).order_by(Lieferant.name)).all()
    return {
        "lagerorte": [
            {
                "id": eintrag.id,
                "code": eintrag.code,
                "name": eintrag.name,
                # Regel 6/D13: Lager ohne Verkauf bekommt kein Eingangsdatum.
                "verkauf": bool(eintrag.verkauf),
            }
            for eintrag in lagerorte
        ],
        "lagerort_aktiv": None if lagerort is None else lagerort.id,
        "lieferanten": [
            {"id": eintrag.id, "name": eintrag.name} for eintrag in lieferanten
        ],
        # Kassenkategorien in der Reihenfolge der Kasse (Regel 8).
        "kategorien": liste_kategorien(session),
        "heute": date.today().isoformat(),
    }


@router.get("/api/erfassen/variante")
def api_variante(
    ean: str = Query(default="", max_length=30),
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Nachschlag für den Scanner: bekannte EAN → Artikeldaten als Vorschlag,
    unbekannte EAN → `gefunden: false` (dann wird neu erfasst, Regel 5)."""
    try:
        treffer = variante_per_ean(session, ean, language)
    except ErfassungRejected as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"gefunden": treffer is not None, "variante": treffer}


class ErfassungPosition(BaseModel):
    # Zahlen als Text, damit nichts über float läuft (CLAUDE.md „Technik").
    model_config = ConfigDict(extra="forbid")

    marke: str = ""
    bezeichnung: str = ""
    menge: str = ""
    uvp: str = ""
    ean: str | None = None
    farbe: str | None = None
    groesse: str | None = None
    einheit: str | None = None
    lieferanten_artikelnr: str | None = None
    ek: str | None = None
    # Kassenkategorie freiwillig gleich mitgeben (Teilaufgabe B8, D23).
    kategorie_id: int | None = None


class ErfassungBody(BaseModel):
    positionen: list[ErfassungPosition] = Field(default_factory=list)
    lagerort_id: int | None = None
    lieferant_id: int | None = None
    eingangsdatum: str | None = None


@router.post("/api/erfassen")
async def api_erfassen(
    request: Request,
    body: ErfassungBody,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    from sqlalchemy.exc import SQLAlchemyError

    from ..core.database import SessionLocal

    lagerort = resolve_wareneingang_lagerort(
        request, session, user, body.lagerort_id, language
    )
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
            erfasse_wareneingang,
            [position.model_dump() for position in body.positionen],
            SessionLocal,
            lagerort_id=lagerort.id,
            benutzer={"kassennummer": user.kassennummer, "name": user.name},
            eingangsdatum=eingangsdatum,
            lieferant_id=body.lieferant_id,
            language=language,
        )
    except ErfassungRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.import_db_error", language)
        ) from exc
