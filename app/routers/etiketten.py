"""EAN nachtragen/erzeugen und Etiketten drucken (Phase B, Teilaufgabe B7).

Eine Aufgabe aus Sicht des Ladens: Ware scannbar machen und auszeichnen.
Fehlt die Hersteller-EAN, erzeugt das System auf Knopfdruck eine interne
(D10/D24); das Etikett (D25) kommt als PDF in Etikettengrösse, damit der
Sato CL4NX Plus (D14) es 1:1 druckt.

Rechte (Regel 9): Beides ist Lagerarbeit, kein Dokument - auch Mitarbeiter
dürfen es.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Bestand, Variante, Wareneingang, WareneingangPosition
from ..services.barcode import druckbare_nummer
from ..services.ean import EanError, EanNichtGefunden, setze_ean
from ..services.etikett import (
    GROESSEN,
    STANDARD_GROESSE,
    EtikettError,
    EtikettNichtGefunden,
    etiketten_pdf,
    rolle,
    sammle_etikett,
)
from ..services.reduktion import ERLAUBTE_STUFEN
from .auth import get_active_lagerort, get_language, require_login_api

router = APIRouter()


class EanBody(BaseModel):
    # Entweder eine EAN nachtragen oder eine interne erzeugen lassen (D24).
    ean: str | None = None
    generieren: bool = False


@router.post("/api/varianten/{varianten_id}/ean")
async def api_ean_setzen(
    varianten_id: int,
    body: EanBody,
    user=Depends(require_login_api),
    language: str = Depends(get_language),
):
    from ..core.database import SessionLocal

    try:
        return await run_in_threadpool(
            setze_ean,
            varianten_id,
            SessionLocal,
            ean=body.ean,
            generieren=body.generieren,
            language=language,
        )
    except EanNichtGefunden as exc:
        raise HTTPException(404, str(exc)) from exc
    except EanError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.import_db_error", language)
        ) from exc


def _pdf(inhalt: bytes, dateiname: str) -> Response:
    # `inline`: der Browser zeigt das Etikett an, von dort geht es zum Drucker.
    return Response(
        content=inhalt,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{dateiname}"'},
    )


def _groesse(wert: str | None, language: str) -> str:
    groesse = wert or STANDARD_GROESSE
    if groesse not in GROESSEN:
        raise HTTPException(422, translate("errors.etikett.unknown_size", language))
    return groesse


def _reduktion(wert: int | None, language: str) -> int | None:
    if wert is None:
        return None
    if wert not in ERLAUBTE_STUFEN:
        raise HTTPException(422, translate("errors.etikett.unknown_reduction", language))
    return wert


@router.get("/api/varianten/{varianten_id}/etikett")
def api_etikett_daten(
    varianten_id: int,
    reduktion: int | None = Query(default=None),
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Was auf dem Etikett stünde - für die Vorschau in der Oberfläche und
    damit die Seite die aktuelle EAN kennt, ohne das PDF zu bauen."""
    try:
        etikett = sammle_etikett(
            session,
            varianten_id,
            lagerort_id=None if lagerort is None else lagerort.id,
            reduktion=_reduktion(reduktion, language),
            language=language,
        )
    except EtikettNichtGefunden as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "varianten_id": varianten_id,
        "marke": etikett.marke,
        "bezeichnung": etikett.bezeichnung,
        "farbe": etikett.farbe,
        "groesse": etikett.groesse,
        "lieferant": etikett.lieferant,
        "lieferant_code": etikett.lieferant_code,
        # Betrag als Text - nie über float (CLAUDE.md „Technik").
        "uvp": None if etikett.uvp is None else str(etikett.uvp),
        "jahrgang": etikett.jahrgang,
        "reduktion": etikett.reduktion,
        "ean": etikett.ean,
        "ean_intern": etikett.ean_intern,
        "barcode": druckbare_nummer(etikett.ean) is not None,
        "lagerort": None
        if lagerort is None
        else {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
        # Welche vorgedruckte Rolle einzulegen ist (24.09.2026).
        "rolle": rolle(etikett.reduktion),
        "groessen": list(GROESSEN),
        "reduktionsstufen": list(ERLAUBTE_STUFEN),
    }


@router.get("/api/varianten/{varianten_id}/etikett.pdf")
def api_etikett(
    varianten_id: int,
    groesse: str | None = Query(default=None),
    reduktion: int | None = Query(default=None),
    anzahl: int = Query(default=1, ge=1, le=100),
    muster: bool = Query(default=False),
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Etikett einer Variante. Jahrgang und Reduktionsvorschlag kommen aus dem
    letzten Wareneingang in der aktiven Filiale (Regel 6); `reduktion`
    überschreibt den Vorschlag (z. B. die 30 % aus D25) und bestimmt die
    Rolle; `muster` zeichnet den Vordruck der Rolle zur Vorschau mit."""
    try:
        etikett = sammle_etikett(
            session,
            varianten_id,
            lagerort_id=None if lagerort is None else lagerort.id,
            reduktion=_reduktion(reduktion, language),
            anzahl=anzahl,
            hinweis_ohne_ean=translate("etikett.no_ean", language),
            language=language,
        )
        inhalt = etiketten_pdf([etikett], _groesse(groesse, language), language, muster)
    except EtikettNichtGefunden as exc:
        raise HTTPException(404, str(exc)) from exc
    except EtikettError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _pdf(inhalt, f"etikett-{varianten_id}.pdf")


@router.get("/api/wareneingaenge/{wareneingang_id}/etiketten.pdf")
def api_etiketten_wareneingang(
    wareneingang_id: int,
    groesse: str | None = Query(default=None),
    reduktion: int | None = Query(default=None),
    je_stueck: bool = Query(default=True),
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Alle Etiketten eines Wareneingangs auf einmal - der Weg nach der
    manuellen Erfassung (B6): erfassen, dann auszeichnen.

    `je_stueck` druckt ein Etikett pro Stück (Voreinstellung), sonst eines je
    Position. Massgebend für Jahrgang und Reduktion ist die Filiale des
    Wareneingangs, nicht die gerade aktive.
    """
    wareneingang = session.get(Wareneingang, wareneingang_id)
    if wareneingang is None:
        raise HTTPException(
            404, translate("errors.wareneingang.not_found", language, id=wareneingang_id)
        )
    positionen = session.execute(
        select(WareneingangPosition.varianten_id, WareneingangPosition.menge_eingetroffen)
        .join(Variante, Variante.id == WareneingangPosition.varianten_id)
        .where(
            WareneingangPosition.wareneingang_id == wareneingang.id,
            WareneingangPosition.menge_eingetroffen > 0,
        )
        .order_by(WareneingangPosition.id)
    ).all()
    if not positionen:
        raise HTTPException(404, translate("errors.etikett.no_positions", language))
    stufe = _reduktion(reduktion, language)
    groesse = _groesse(groesse, language)
    hinweis = translate("etikett.no_ean", language)
    try:
        etiketten = [
            sammle_etikett(
                session,
                varianten_id,
                lagerort_id=wareneingang.lagerort_id,
                reduktion=stufe,
                # Angebrochene Mengen (z. B. 2.5 kg) ergeben ein Etikett.
                anzahl=max(1, int(Decimal(menge or 0))) if je_stueck else 1,
                hinweis_ohne_ean=hinweis,
                language=language,
            )
            for varianten_id, menge in positionen
        ]
        inhalt = etiketten_pdf(etiketten, groesse, language)
    except EtikettError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _pdf(inhalt, f"etiketten-wareneingang-{wareneingang_id}.pdf")


@router.get("/api/artikel/{artikel_id}/etiketten.pdf")
def api_etiketten_artikel(
    artikel_id: int,
    reduktion: int | None = Query(default=None),
    lagerort_id: int | None = Query(default=None),
    groesse: str | None = Query(default=None),
    user=Depends(require_login_api),
    aktiver_lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Runterschreiben (Phase D): je Stück im Bestand der Filiale ein Etikett,
    für alle Farben und Grössen des Artikels. `reduktion` bestimmt die Rolle."""
    lagerort_id = lagerort_id if lagerort_id is not None else getattr(aktiver_lagerort, "id", None)
    stufe = _reduktion(reduktion, language)
    groesse = _groesse(groesse, language)
    varianten = session.execute(
        select(Variante.id, Bestand.menge)
        .join(Bestand, Bestand.varianten_id == Variante.id)
        .where(
            Variante.artikel_id == artikel_id,
            Bestand.lagerort_id == lagerort_id,
            Bestand.menge > 0,
        )
        .order_by(Variante.id)
    ).all()
    if not varianten:
        raise HTTPException(404, translate("errors.etikett.no_positions", language))
    hinweis = translate("etikett.no_ean", language)
    try:
        etiketten = [
            sammle_etikett(
                session,
                varianten_id,
                lagerort_id=lagerort_id,
                reduktion=stufe,
                anzahl=max(1, int(Decimal(menge))),
                hinweis_ohne_ean=hinweis,
                language=language,
            )
            for varianten_id, menge in varianten
        ]
        inhalt = etiketten_pdf(etiketten, groesse, language)
    except EtikettError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _pdf(inhalt, f"etiketten-artikel-{artikel_id}.pdf")
