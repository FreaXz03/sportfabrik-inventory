from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from .auth import get_language, require_login_api
from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import Dokument, Lieferant, Variante, WareneingangPosition
from .history import invoice_data

router = APIRouter()


@router.get("/api/dashboard")
def dashboard(
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
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
        delivered_quantity = session.scalar(select(func.sum(WareneingangPosition.menge)))
        return dict(
            **counts,
            delivered_quantity=(
                format(delivered_quantity, "f")
                if delivered_quantity is not None
                else "0"
            ),
            recent_invoices=[invoice_data(d, supplier) for d, supplier in rows],
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.dashboard.load_failed", language)
        ) from exc
