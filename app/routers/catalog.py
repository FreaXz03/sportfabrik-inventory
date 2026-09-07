from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.exc import SQLAlchemyError
from .auth import require_login_api, require_login_page
from ..core.database import get_session
from ..core.models import Product, Invoice, InvoiceItem

router = APIRouter()


# Whitelist of columns the article table may be sorted by. Only real,
# per-product columns are sortable - "Geliefert gesamt" and "Letzter
# UVP"/"UVP vom" are computed after pagination from separate queries
# below and are intentionally left out.
SORTABLE_COLUMNS = {
    "brand": Product.brand,
    "description": Product.description,
    "article_no": Product.article_no,
    "supplier_article_no": Product.supplier_article_no,
    "ean": Product.ean,
    "color": Product.color,
    "size": Product.size,
    "first_seen": Product.first_seen,
    "last_seen": Product.last_seen,
}


@router.get("/articles", include_in_schema=False)
def articles_page(user=Depends(require_login_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "articles.html"
    )


def contains(column, value):
    # Search wildcards are literal user input, never SQL wildcard expressions.
    escaped = value.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return column.ilike("%" + escaped + "%", escape="!")


@router.get("/api/brands")
def brands(user=Depends(require_login_api), session=Depends(get_session)):
    try:
        return session.scalars(
            select(Product.brand)
            .where(Product.brand.is_not(None), Product.brand != "")
            .distinct()
            .order_by(Product.brand)
        ).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, "Datenbank nicht erreichbar. Bitte erneut versuchen."
        ) from exc


@router.get("/api/articles/export")
@router.get("/api/articles")
def articles(
    request: Request,
    q: str = Query("", max_length=200),
    brand: str = Query("", max_length=100),
    ean: str = Query("", max_length=30),
    article_no: str = Query("", max_length=100),
    description: str = Query("", max_length=500),
    last_delivery_from: str | None = Query(None),
    last_delivery_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal[
        "brand",
        "description",
        "article_no",
        "supplier_article_no",
        "ean",
        "color",
        "size",
        "first_seen",
        "last_seen",
    ] = Query("brand"),
    sort_dir: Literal["asc", "desc"] = Query("asc"),
    user=Depends(require_login_api),
    session=Depends(get_session),
):
    try:
        last_delivery_from = date.fromisoformat(last_delivery_from) if last_delivery_from else None
        last_delivery_to = date.fromisoformat(last_delivery_to) if last_delivery_to else None
    except ValueError as exc:
        raise HTTPException(422, 'Bitte ein gültiges Lieferdatum eingeben.') from exc
    if last_delivery_from and last_delivery_to and last_delivery_from > last_delivery_to:
        raise HTTPException(422, 'Das Von-Datum darf nicht nach dem Bis-Datum liegen.')
    conditions = []
    if last_delivery_from:
        conditions.append(Product.last_seen >= last_delivery_from)
    if last_delivery_to:
        conditions.append(Product.last_seen <= last_delivery_to)
    if q.strip():
        conditions.append(
            or_(
                *(
                    contains(c, q)
                    for c in (
                        Product.brand,
                        Product.ean,
                        Product.article_no,
                        Product.supplier_article_no,
                        Product.description,
                        Product.color,
                        Product.size,
                    )
                )
            )
        )
    if brand:
        conditions.append(Product.brand == brand)
    if ean.strip():
        conditions.append(Product.ean == ean.strip())
    if article_no.strip():
        conditions.append(
            or_(
                contains(Product.article_no, article_no),
                contains(Product.supplier_article_no, article_no),
            )
        )
    if description.strip():
        conditions.append(contains(Product.description, description))
    try:
        total = session.scalar(
            select(func.count()).select_from(Product).where(*conditions)
        )
        sort_column = SORTABLE_COLUMNS[sort_by]
        primary = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
        exporting = request.url.path.endswith("/export")
        product_query = (select(Product)
            .where(*conditions)
            .order_by(primary.nulls_last(), Product.id)
        )
        if not exporting:
            product_query = product_query.offset((page - 1) * page_size).limit(page_size)
        products = session.scalars(product_query).all()
        ids = [p.id for p in products]
        totals = {}
        latest = {}
        if ids:
            for product_id, unit, quantity in session.execute(
                select(
                    InvoiceItem.product_id,
                    InvoiceItem.unit,
                    func.sum(InvoiceItem.quantity),
                )
                .where(InvoiceItem.product_id.in_(ids))
                .group_by(InvoiceItem.product_id, InvoiceItem.unit)
            ):
                totals.setdefault(product_id, []).append(
                    {
                        "unit": unit,
                        "quantity": (
                            format(quantity, "f") if quantity is not None else None
                        ),
                    }
                )
            ranked = (
                select(
                    InvoiceItem.product_id,
                    InvoiceItem.uvp,
                    Invoice.invoice_date,
                    func.row_number()
                    .over(
                        partition_by=InvoiceItem.product_id,
                        order_by=(
                            Invoice.invoice_date.desc().nulls_last(),
                            Invoice.uploaded_at.desc(),
                            Invoice.id.desc(),
                            InvoiceItem.id.desc(),
                        ),
                    )
                    .label("rank"),
                )
                .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
                .where(InvoiceItem.product_id.in_(ids), InvoiceItem.uvp.is_not(None))
                .subquery()
            )
            for row in session.execute(
                select(ranked).where(ranked.c.rank == 1)
            ).mappings():
                latest[row["product_id"]] = row
        items = []
        for p in products:
            item = {
                key: getattr(p, key)
                for key in (
                    "id",
                    "brand",
                    "supplier_article_no",
                    "article_no",
                    "ean",
                    "description",
                    "color",
                    "size",
                    "first_seen",
                    "last_seen",
                )
            }
            price = latest.get(p.id)
            item.update(
                delivered=totals.get(p.id, []),
                latest_uvp=format(price["uvp"], "f") if price else None,
                uvp_date=price["invoice_date"] if price else None,
            )
            items.append(item)
        if exporting:
            from ..services.article_export import export_articles
            return export_articles(items)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        }
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, "Artikelsuche fehlgeschlagen. Bitte die Datenbankverbindung prüfen."
        ) from exc
