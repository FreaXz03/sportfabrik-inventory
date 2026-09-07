from fastapi import HTTPException
from sqlalchemy import select, func
from ..core.models import Product


def article_group(session, product_id):
    """Group variants by brand and supplier number; missing numbers stay separate."""
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, 'Artikel nicht gefunden.')
    number = (product.supplier_article_no or '').strip()
    if not number:
        return product, select(Product.id).where(Product.id == product_id)
    ids = select(Product.id).where(
        func.trim(Product.supplier_article_no) == number,
        func.lower(func.trim(func.coalesce(Product.brand, ''))) == (product.brand or '').strip().lower(),
    )
    return product, ids
