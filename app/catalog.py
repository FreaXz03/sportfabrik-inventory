from pathlib import Path
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.exc import SQLAlchemyError
from .auth import require_login_api, require_login_page
from .database import get_session  # re-exported: history.py/dashboard.py import get_session from here
from .models import Product, Invoice, InvoiceItem

router = APIRouter()



@router.get('/articles', include_in_schema=False)
def articles_page(user=Depends(require_login_page)):
    return FileResponse(Path(__file__).parent / 'templates' / 'articles.html')


def contains(column, value):
    # Search wildcards are literal user input, never SQL wildcard expressions.
    escaped = value.strip().replace('!', '!!').replace('%', '!%').replace('_', '!_')
    return column.ilike('%' + escaped + '%', escape='!')


@router.get('/api/brands')
def brands(user=Depends(require_login_api), session=Depends(get_session)):
    try:
        return session.scalars(select(Product.brand).where(Product.brand.is_not(None),
            Product.brand != '').distinct().order_by(Product.brand)).all()
    except SQLAlchemyError as exc:
        raise HTTPException(503, 'Datenbank nicht erreichbar. Bitte erneut versuchen.') from exc


@router.get('/api/articles')
def articles(q: str = Query('', max_length=200), brand: str = Query('', max_length=100),
             ean: str = Query('', max_length=30), article_no: str = Query('', max_length=100),
             description: str = Query('', max_length=500),
             page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
             user=Depends(require_login_api), session=Depends(get_session)):
    conditions = []
    if q.strip():
        conditions.append(or_(*(contains(c, q) for c in (Product.brand,
            Product.ean, Product.article_no, Product.supplier_article_no,
            Product.description, Product.color, Product.size))))
    if brand:
        conditions.append(Product.brand == brand)
    if ean.strip():
        conditions.append(Product.ean == ean.strip())
    if article_no.strip():
        conditions.append(or_(contains(Product.article_no, article_no),
                              contains(Product.supplier_article_no, article_no)))
    if description.strip():
        conditions.append(contains(Product.description, description))
    try:
        total = session.scalar(select(func.count()).select_from(Product).where(*conditions))
        products = session.scalars(select(Product).where(*conditions).order_by(
            Product.brand.asc().nulls_last(), Product.description.asc().nulls_last(), Product.id
        ).offset((page-1)*page_size).limit(page_size)).all()
        ids = [p.id for p in products]
        totals = {}
        latest = {}
        if ids:
            for product_id, unit, quantity in session.execute(select(InvoiceItem.product_id,
                InvoiceItem.unit, func.sum(InvoiceItem.quantity)).where(InvoiceItem.product_id.in_(ids))
                .group_by(InvoiceItem.product_id, InvoiceItem.unit)):
                totals.setdefault(product_id, []).append({'unit': unit,
                    'quantity': format(quantity, 'f') if quantity is not None else None})
            ranked = select(InvoiceItem.product_id, InvoiceItem.uvp, Invoice.invoice_date,
                func.row_number().over(partition_by=InvoiceItem.product_id, order_by=(
                    Invoice.invoice_date.desc().nulls_last(), Invoice.uploaded_at.desc(),
                    Invoice.id.desc(), InvoiceItem.id.desc())).label('rank')
                ).join(Invoice, Invoice.id == InvoiceItem.invoice_id).where(
                    InvoiceItem.product_id.in_(ids), InvoiceItem.uvp.is_not(None)).subquery()
            for row in session.execute(select(ranked).where(ranked.c.rank == 1)).mappings():
                latest[row['product_id']] = row
        items = []
        for p in products:
            item = {key: getattr(p, key) for key in ('id','brand','supplier_article_no',
                'article_no','ean','description','color','size','first_seen','last_seen')}
            price = latest.get(p.id)
            item.update(delivered=totals.get(p.id, []), latest_uvp=format(price['uvp'], 'f')
                if price else None, uvp_date=price['invoice_date'] if price else None)
            items.append(item)
        return {'items': items, 'total': total, 'page': page, 'page_size': page_size}
    except SQLAlchemyError as exc:
        raise HTTPException(503, 'Artikelsuche fehlgeschlagen. Bitte die Datenbankverbindung prüfen.') from exc
