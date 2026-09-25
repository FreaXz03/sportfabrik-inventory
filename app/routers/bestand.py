"""Bestand ansehen (Phase C, Teilaufgabe C2).

Rechte: jede Anmeldung darf lesen, und zwar **alle** Filialen (bestätigt am
22.09.2026, siehe docs/projekt-kontext.md Abschnitt 10). Der Filialwechsel
oben in der Sitzungsleiste bleibt davon unberührt - er bestimmt nur, was
vorausgewählt ist und wohin gebucht wird.
"""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Lagerort, Variante
from ..services.bestand import STANDARD_LIMIT, liste_bestand
from ..services.lagerorte import list_all_lagerorte, list_wareneingang_lagerorte
from ..services import reduktion_manuell
from ..services.reduktion import STUFEN
from ..services.uebersicht import reduktions_varianten
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
    nur_negativ: bool = False,
    reduktion: int | None = None,
    reduktion_status: Literal["faellig", "bald"] = "faellig",
    artikel_von: int | None = None,
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

    # Links aus „Anstehend" der Übersicht (24.09.2026): dieselbe Auswahl wie
    # dort gezählt. Reduktion gilt je Filiale, braucht also eine.
    varianten_ids = None
    if reduktion is not None:
        if str(reduktion) not in {str(prozent) for _, prozent in STUFEN} or gewaehlt is None:
            raise HTTPException(422, translate("errors.bestand.unknown_reduction", language))
        varianten_ids = reduktions_varianten(session, gewaehlt)[str(reduktion)][reduktion_status]

    # Artikeldetails (24.09.2026): alle Grössen und Farben des Artikels, zu
    # dem die angeklickte Variante gehört.
    if artikel_von is not None:
        artikel_id = session.scalar(select(Variante.artikel_id).where(Variante.id == artikel_von))
        if artikel_id is None:
            raise HTTPException(404, translate("errors.bestand.unknown_article", language))
        alle_varianten = session.scalars(select(Variante.id).where(Variante.artikel_id == artikel_id)).all()
        varianten_ids = [v for v in alle_varianten if varianten_ids is None or v in varianten_ids]

    ergebnis = liste_bestand(
        session,
        lagerort_id=gewaehlt,
        suche=q,
        nur_vorhanden=nur_vorhanden,
        limit=limit,
        offset=offset,
        nur_negativ=nur_negativ,
        varianten_ids=varianten_ids,
    )
    # Reduktionsstufe je Zeile (24.09.2026): Empfehlung, Wahl von Hand und
    # wirksame Stufe. Externe Lager haben keine Reduktion (D13).
    je_lagerort = {}
    for zeile in ergebnis["zeilen"]:
        if zeile["lagerort"]["verkauf"]:
            je_lagerort.setdefault(zeile["lagerort"]["id"], set()).add(zeile["artikel_id"])
    stufen = {
        lagerort_id: reduktion_manuell.stufen(session, lagerort_id, artikel_ids)
        for lagerort_id, artikel_ids in je_lagerort.items()
    }
    for zeile in ergebnis["zeilen"]:
        zeile["reduktion"] = stufen.get(zeile["lagerort"]["id"], {}).get(zeile["artikel_id"])
    ergebnis["rechte"] = {
        "ausbuchen": user.role in ("chef", "admin"),
        "korrektur_lagerorte": [lo.id for lo in list_wareneingang_lagerorte(session, user)],
    }
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
