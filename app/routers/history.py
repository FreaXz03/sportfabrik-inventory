from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from .auth import require_chef_api, require_login_api, require_login_page
from .catalog import contains
from ..core.database import SessionLocal, get_session
from ..services.importer import delete_invoice, DeleteRejected
from ..core.models import Product, Invoice, InvoiceItem, InvoiceItemSource

router = APIRouter()

@router.get('/invoices', include_in_schema=False)
@router.get('/invoices/{record_id}', include_in_schema=False)
@router.get('/articles/{record_id}/history', include_in_schema=False)
def history_page(record_id: int = 0, user=Depends(require_login_page)):
    return FileResponse(Path(__file__).resolve().parents[1] / 'templates' / 'history.html')


def invoice_data(invoice):
    return {key:getattr(invoice,key) for key in ('id','invoice_number','invoice_date',
        'document_date','supplier','filename','uploaded_at','imported_by_kassennummer','imported_by_name','ocr_used')}


@router.get('/api/invoices')
def invoices(q: str = Query('', max_length=200), page: int = Query(1, ge=1),
             page_size: int = Query(25, ge=1, le=100),
             user=Depends(require_login_api), session=Depends(get_session)):
    try:
        condition = [contains(Invoice.invoice_number,q)] if q.strip() else []
        total=session.scalar(select(func.count()).select_from(Invoice).where(*condition))
        count=select(func.count(InvoiceItem.id)).where(InvoiceItem.invoice_id==Invoice.id).scalar_subquery()
        rows=session.execute(select(Invoice,count).where(*condition).order_by(
            Invoice.invoice_date.desc().nulls_last(),Invoice.id.desc()).offset((page-1)*page_size).limit(page_size))
        return dict(total=total,page=page,page_size=page_size,items=[dict(**invoice_data(i),item_count=n) for i,n in rows])
    except SQLAlchemyError as exc:
        raise HTTPException(503,'Rechnungen konnten nicht geladen werden. Bitte erneut versuchen.') from exc


def positions(session, condition, page, page_size, chronological=False):
    total=session.scalar(select(func.count()).select_from(InvoiceItem).where(condition))
    stmt=select(InvoiceItem,Product,Invoice,InvoiceItemSource).join(Product,
        Product.id==InvoiceItem.product_id).join(Invoice,Invoice.id==InvoiceItem.invoice_id).outerjoin(
        InvoiceItemSource,InvoiceItemSource.item_id==InvoiceItem.id).where(condition)
    ordering=(Invoice.invoice_date.desc().nulls_last(),Invoice.id.desc(),InvoiceItem.id) if chronological else (InvoiceItem.id,)
    rows=session.execute(stmt.order_by(*ordering).offset((page-1)*page_size).limit(page_size))
    items=[]
    for item,product,invoice,source in rows:
        snapshot=source.data if source else {}
        data={key:snapshot.get(key,getattr(product,key)) for key in
            ('brand','description','ean','article_no','supplier_article_no','color','size')}
        data.update(id=item.id,product_id=product.id,invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,invoice_date=invoice.invoice_date,
            quantity=format(item.quantity,'f') if item.quantity is not None else None,
            unit=item.unit,uvp=format(item.uvp,'f') if item.uvp is not None else None,
            source_available=bool(source),row_number=snapshot.get('row_number'),
            page=snapshot.get('page'),raw_lines=snapshot.get('raw_lines',[]))
        items.append(data)
    return dict(total=total,page=page,page_size=page_size,items=items)


@router.get('/api/invoices/{invoice_id}')
def invoice_detail(invoice_id:int, page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),
                    user=Depends(require_login_api), session=Depends(get_session)):
    try:
        invoice=session.get(Invoice,invoice_id)
        if invoice is None: raise HTTPException(404,'Rechnung nicht gefunden.')
        return dict(invoice=invoice_data(invoice),**positions(session,InvoiceItem.invoice_id==invoice_id,page,page_size))
    except SQLAlchemyError as exc:
        raise HTTPException(503,'Rechnungspositionen konnten nicht geladen werden.') from exc


@router.get('/api/articles/{product_id}/history')
def article_history(product_id:int,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),
                     user=Depends(require_login_api), session=Depends(get_session)):
    try:
        product=session.get(Product,product_id)
        if product is None: raise HTTPException(404,'Artikel nicht gefunden.')
        return dict(product={key:getattr(product,key) for key in ('id','brand','description','ean')},
            **positions(session,InvoiceItem.product_id==product_id,page,page_size,True))
    except SQLAlchemyError as exc:
        raise HTTPException(503,'Artikelhistorie konnte nicht geladen werden.') from exc


@router.delete('/api/invoices/{invoice_id}')
def remove_invoice(invoice_id: int, user=Depends(require_chef_api)):
    try:
        return delete_invoice(invoice_id, SessionLocal)
    except DeleteRejected as exc:
        raise HTTPException(404, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, 'Rechnung konnte nicht gelöscht werden. Bitte erneut versuchen.') from exc
