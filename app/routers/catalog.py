from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.exc import SQLAlchemyError
from .auth import get_language, require_login_api, require_login_page
from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import (
    Artikel,
    Dokument,
    Kategorie,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from ..services.kategorien import kategorie_daten

router = APIRouter()


# Whitelist of columns the article table may be sorted by. Only real,
# per-variant/per-model columns are sortable - "Geliefert gesamt" and
# "Letzter UVP"/"UVP vom" are computed after pagination from separate queries
# below and are intentionally left out.
SORTABLE_COLUMNS = {
    "brand": Artikel.marke,
    "description": Artikel.bezeichnung,
    "supplier_article_no": Artikel.lieferanten_artikelnr,
    "ean": Variante.ean,
    "color": Variante.farbe,
    "size": Variante.groesse,
    "first_seen": Variante.first_seen,
    "last_seen": Variante.last_seen,
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
def brands(
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        return session.scalars(
            select(Artikel.marke)
            .where(Artikel.marke.is_not(None), Artikel.marke != "")
            .distinct()
            .order_by(Artikel.marke)
        ).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.catalog.database_unreachable", language)
        ) from exc


@router.get("/api/articles/export")
@router.get("/api/articles")
def articles(
    request: Request,
    q: str = Query("", max_length=200),
    brand: str = Query("", max_length=100),
    ean: str = Query("", max_length=30),
    supplier_article_no: str = Query("", max_length=100),
    description: str = Query("", max_length=500),
    kategorie_id: int | None = Query(None, ge=1),
    kategorie_fehlt: bool = Query(False),
    last_delivery_from: str | None = Query(None),
    last_delivery_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal[
        "brand",
        "description",
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
    language: str = Depends(get_language),
):
    try:
        last_delivery_from = date.fromisoformat(last_delivery_from) if last_delivery_from else None
        last_delivery_to = date.fromisoformat(last_delivery_to) if last_delivery_to else None
    except ValueError as exc:
        raise HTTPException(
            422, translate("errors.catalog.invalid_delivery_date", language)
        ) from exc
    if last_delivery_from and last_delivery_to and last_delivery_from > last_delivery_to:
        raise HTTPException(422, translate("errors.catalog.delivery_date_range", language))
    conditions = []
    if last_delivery_from:
        conditions.append(Variante.last_seen >= last_delivery_from)
    if last_delivery_to:
        conditions.append(Variante.last_seen <= last_delivery_to)
    if q.strip():
        conditions.append(
            or_(
                *(
                    contains(c, q)
                    for c in (
                        Artikel.marke,
                        Variante.ean,
                        Artikel.bezeichnung,
                        Artikel.lieferanten_artikelnr,
                        Variante.farbe,
                        Variante.groesse,
                    )
                )
            )
        )
    if brand:
        conditions.append(Artikel.marke == brand)
    if ean.strip():
        conditions.append(Variante.ean == ean.strip())
    if supplier_article_no.strip():
        conditions.append(contains(Artikel.lieferanten_artikelnr, supplier_article_no))
    if description.strip():
        conditions.append(contains(Artikel.bezeichnung, description))
    # Kategorie (Teilaufgabe B8): „ohne Kategorie" ist der wichtigere Filter -
    # er zeigt genau die Artikel, bei denen noch jemand von Hand wählen muss.
    if kategorie_fehlt:
        conditions.append(Artikel.kategorie_id.is_(None))
    elif kategorie_id is not None:
        conditions.append(Artikel.kategorie_id == kategorie_id)
    try:
        base_query = (
            select(Variante, Artikel, Kategorie)
            .join(Artikel, Artikel.id == Variante.artikel_id)
            .outerjoin(Kategorie, Kategorie.id == Artikel.kategorie_id)
        )
        total = session.scalar(
            select(func.count())
            .select_from(Variante)
            .join(Artikel, Artikel.id == Variante.artikel_id)
            .where(*conditions)
        )
        sort_column = SORTABLE_COLUMNS[sort_by]
        primary = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
        exporting = request.url.path.endswith("/export")
        variant_query = (
            base_query.where(*conditions).order_by(primary.nulls_last(), Variante.id)
        )
        if not exporting:
            variant_query = variant_query.offset((page - 1) * page_size).limit(page_size)
        rows = session.execute(variant_query).all()
        ids = [v.id for v, _, _ in rows]
        totals = {}
        latest = {}
        if ids:
            for varianten_id, unit, quantity in session.execute(
                select(
                    WareneingangPosition.varianten_id,
                    WareneingangPosition.einheit,
                    func.sum(WareneingangPosition.menge),
                )
                .where(WareneingangPosition.varianten_id.in_(ids))
                .group_by(WareneingangPosition.varianten_id, WareneingangPosition.einheit)
            ):
                totals.setdefault(varianten_id, []).append(
                    {
                        "unit": unit,
                        "quantity": (
                            format(quantity, "f") if quantity is not None else None
                        ),
                    }
                )
            ranked = (
                select(
                    WareneingangPosition.varianten_id,
                    WareneingangPosition.uvp,
                    Dokument.dokumentdatum,
                    func.row_number()
                    .over(
                        partition_by=WareneingangPosition.varianten_id,
                        order_by=(
                            Dokument.dokumentdatum.desc().nulls_last(),
                            Dokument.hochgeladen_am.desc(),
                            Dokument.id.desc(),
                            WareneingangPosition.id.desc(),
                        ),
                    )
                    .label("rank"),
                )
                .select_from(WareneingangPosition)
                .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
                .join(Dokument, Dokument.id == Wareneingang.dokument_id)
                .where(
                    WareneingangPosition.varianten_id.in_(ids),
                    WareneingangPosition.uvp.is_not(None),
                )
                .subquery()
            )
            for row in session.execute(
                select(ranked).where(ranked.c.rank == 1)
            ).mappings():
                latest[row["varianten_id"]] = row
        items = []
        for v, a, k in rows:
            item = {
                "id": v.id,
                "brand": a.marke,
                "supplier_article_no": a.lieferanten_artikelnr,
                "ean": v.ean,
                "description": a.bezeichnung,
                "color": v.farbe,
                "size": v.groesse,
                "first_seen": v.first_seen,
                "last_seen": v.last_seen,
                "kategorie": kategorie_daten(k),
            }
            price = latest.get(v.id)
            item.update(
                delivered=totals.get(v.id, []),
                latest_uvp=format(price["uvp"], "f") if price else None,
                uvp_date=price["dokumentdatum"] if price else None,
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
            503, translate("errors.catalog.search_failed", language)
        ) from exc
