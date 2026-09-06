from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from .catalog import get_session
from .models import Product, Invoice, InvoiceItem
from .history import invoice_data
router=APIRouter()
@router.get('/api/dashboard')
def dashboard(session=Depends(get_session)):
    try:
        counts={key:session.scalar(select(func.count()).select_from(model)) for key,model in
            [('products',Product),('invoices',Invoice),('positions',InvoiceItem)]}
        rows=session.scalars(select(Invoice).order_by(Invoice.uploaded_at.desc(),Invoice.id.desc()).limit(5)).all()
        return dict(**counts,recent_invoices=[invoice_data(i) for i in rows])
    except SQLAlchemyError as exc:
        raise HTTPException(503,'Übersicht konnte nicht geladen werden. Bitte Datenbankverbindung prüfen.') from exc
