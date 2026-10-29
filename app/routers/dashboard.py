from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from .auth import get_active_lagerort, get_language, require_login_api
from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Dokument, Lieferant, Variante, WareneingangPosition
from ..services import hinweise as hinweise_service
from ..services import uebersicht
from .history import invoice_data

router = APIRouter()


@router.get("/api/dashboard")
def dashboard(
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Stammzahlen und zuletzt importierte Belege; dazu seit 23.09.2026
    Kennzahlen und anstehende Vorgänge der aktiven Filiale (`filiale`, leer
    ohne aktive Filiale), die letzten Buchungen (`aktuelles`) und Hinweise
    zum Artikelstamm (`stamm`)."""
    try:
        counts = {
            key: session.scalar(select(func.count()).select_from(model))
            for key, model in [
                ("products", Variante),
                ("invoices", Dokument),
                ("positions", WareneingangPosition),
            ]
        }
        rows = session.execute(
            select(Dokument, Lieferant.name)
            .outerjoin(Lieferant, Lieferant.id == Dokument.lieferant_id)
            .order_by(Dokument.hochgeladen_am.desc(), Dokument.id.desc())
            .limit(5)
        ).all()
        ziele = uebersicht.ziel_filialen(session, [d.id for d, _ in rows])
        filiale = None if lagerort is None else uebersicht.filiale(session, lagerort.id)
        stamm = uebersicht.stamm(session)
        delivered_quantity = session.scalar(select(func.sum(WareneingangPosition.menge)))
        return dict(
            **counts,
            delivered_quantity=(
                format(delivered_quantity, "f")
                if delivered_quantity is not None
                else "0"
            ),
            recent_invoices=[dict(invoice_data(d, supplier), lagerort=ziele[d.id]) for d, supplier in rows],
            lagerort=None
            if lagerort is None
            else {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
            filiale=filiale,
            aktuelles=uebersicht.aktuelles(session, None if lagerort is None else lagerort.id),
            stamm=stamm,
            meldungen=uebersicht.liste_meldungen(filiale, stamm),
            hinweise=hinweise_service.liste(session, lagerort.id) if lagerort else [],
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.dashboard.load_failed", language)
        ) from exc


@router.get("/api/anstehend/anzahl")
def anstehend_anzahl(
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Zahl der Meldungen unter „Anstehend" für die Glocke (jede Seite)."""
    try:
        if lagerort is not None and not lagerort.verkauf:
            return {"anzahl": 0, "meldungen": []}  # Punkt 10: kein Anstehend ohne Verkauf
        filiale = None if lagerort is None else uebersicht.meldungen_filiale(session, lagerort.id)
        meldungen = uebersicht.liste_meldungen(filiale, uebersicht.stamm(session))
        return {"anzahl": len(meldungen), "meldungen": meldungen}
    except SQLAlchemyError as exc:
        raise HTTPException(503, translate("errors.dashboard.load_failed", language)) from exc


@router.get("/api/uebersicht/verlaeufe")
def uebersicht_verlaeufe(
    tage: int,
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    """Bestand und neue Artikelvarianten über `tage` Tage mit Vergleich zur Vorperiode."""
    if tage not in uebersicht.VERLAUF_PERIODEN:
        raise HTTPException(422, translate("errors.dashboard.period_invalid", language))
    try:
        return uebersicht.verlaeufe(session, None if lagerort is None else lagerort.id, tage)
    except SQLAlchemyError as exc:
        raise HTTPException(503, translate("errors.dashboard.load_failed", language)) from exc
