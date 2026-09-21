import re
from decimal import Decimal
from typing import Literal
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from .auth import get_language, require_chef_api, require_login_api, require_login_page
from .catalog import contains
from ..services.article_groups import article_group
from ..core.database import SessionLocal, get_session
from ..core.i18n import translate
from ..services.importer import delete_invoice, DeleteRejected
from ..core.models import (
    Artikel,
    Dokument,
    Lieferant,
    Variante,
    Wareneingang,
    WareneingangPosition,
    WareneingangPositionQuelle,
)

router = APIRouter()


@router.get("/invoices", include_in_schema=False)
@router.get("/invoices/{record_id}", include_in_schema=False)
@router.get("/articles/{record_id}/history", include_in_schema=False)
def history_page(record_id: int = 0, user=Depends(require_login_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "history.html"
    )


def invoice_data(dokument, supplier=None):
    return {
        "id": dokument.id,
        "invoice_number": dokument.dokumentnummer,
        "invoice_date": dokument.dokumentdatum,
        "document_date": dokument.belegdatum,
        "supplier": supplier,
        "filename": dokument.dateiname,
        "uploaded_at": dokument.hochgeladen_am,
        "imported_by_kassennummer": dokument.hochgeladen_von_kassennummer,
        "imported_by_name": dokument.hochgeladen_von_name,
        "ocr_used": dokument.ocr_verwendet,
    }


@router.get("/api/invoices")
def invoices(
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        condition = [contains(Dokument.dokumentnummer, q)] if q.strip() else []
        total = session.scalar(
            select(func.count()).select_from(Dokument).where(*condition)
        )
        count = (
            select(func.count(WareneingangPosition.id))
            .select_from(WareneingangPosition)
            .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
            .where(Wareneingang.dokument_id == Dokument.id)
            .scalar_subquery()
        )
        rows = session.execute(
            select(Dokument, Lieferant.name, count)
            .outerjoin(Lieferant, Lieferant.id == Dokument.lieferant_id)
            .where(*condition)
            .order_by(Dokument.dokumentdatum.desc().nulls_last(), Dokument.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return dict(
            total=total,
            page=page,
            page_size=page_size,
            items=[dict(**invoice_data(d, supplier), item_count=n) for d, supplier, n in rows],
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.history.invoices_failed", language)
        ) from exc


SortField = Literal[
    "position",
    "invoice_date",
    "description",
    "ean",
    "article_no",
    "color",
    "size",
    "quantity",
    "unit",
    "uvp",
]


def position_sort_key(item, field):
    value = item.get("row_number" if field == "position" else field)
    if field in ("quantity", "uvp", "position"):
        return Decimal(str(value))
    if field == "invoice_date":
        return value
    value = str(value).strip().upper()
    sizes = {
        "XXXS": 0,
        "XXS": 1,
        "XS": 2,
        "S": 3,
        "M": 4,
        "L": 5,
        "XL": 6,
        "XXL": 7,
        "2XL": 7,
        "XXXL": 8,
        "3XL": 8,
        "4XL": 9,
        "5XL": 10,
    }
    if field == "size" and value in sizes:
        return ((0, Decimal(sizes[value])),)
    return tuple(
        (
            (0, Decimal(part.replace(",", ".")))
            if re.fullmatch(r"\d+(?:[.,]\d+)?", part)
            else (1, part)
        )
        for part in re.split(r"(\d+(?:[.,]\d+)?)", value)
        if part
    )


def positions(
    session,
    condition,
    page,
    page_size,
    chronological=False,
    sort_by=None,
    sort_dir="asc",
):
    total = session.scalar(
        select(func.count())
        .select_from(WareneingangPosition)
        .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
        .where(condition)
    )
    stmt = (
        select(WareneingangPosition, Variante, Artikel, Wareneingang, Dokument, WareneingangPositionQuelle)
        .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
        .join(Dokument, Dokument.id == Wareneingang.dokument_id)
        .join(Variante, Variante.id == WareneingangPosition.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .outerjoin(
            WareneingangPositionQuelle,
            WareneingangPositionQuelle.position_id == WareneingangPosition.id,
        )
        .where(condition)
    )
    ordering = (
        (Dokument.dokumentdatum.desc().nulls_last(), Dokument.id.desc(), WareneingangPosition.id)
        if chronological
        else (WareneingangPosition.id,)
    )
    rows = session.execute(
        stmt.order_by(*ordering)
        if sort_by
        else stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)
    )
    items = []
    for position, variante, artikel, _wareneingang, dokument, source in rows:
        snapshot = source.data if source else {}
        fallback = {
            "brand": artikel.marke,
            "description": artikel.bezeichnung,
            "ean": variante.ean,
            # Die frühere INTERSPORT-eigene Artikelnummer wird nicht mehr als
            # eigene Spalte geführt (siehe docs/projekt-kontext.md 8.2) - nur
            # noch im unveränderten Original-Snapshot vorhanden, falls dort da.
            "article_no": None,
            "supplier_article_no": artikel.lieferanten_artikelnr,
            "color": variante.farbe,
            "size": variante.groesse,
        }
        data = {key: snapshot.get(key, fallback[key]) for key in fallback}
        data.update(
            id=position.id,
            product_id=variante.id,
            invoice_id=dokument.id,
            invoice_number=dokument.dokumentnummer,
            invoice_date=dokument.dokumentdatum,
            quantity=format(position.menge, "f") if position.menge is not None else None,
            unit=position.einheit,
            uvp=format(position.uvp, "f") if position.uvp is not None else None,
            source_available=bool(source),
            row_number=snapshot.get("row_number"),
            page=snapshot.get("page"),
            raw_lines=snapshot.get("raw_lines", []),
            correction_audit=snapshot.get("correction_audit"),
        )
        items.append(data)
    if sort_by:
        field = "row_number" if sort_by == "position" else sort_by
        present = [item for item in items if item.get(field) not in (None, "")]
        missing = [item for item in items if item.get(field) in (None, "")]
        present.sort(
            key=lambda item: position_sort_key(item, sort_by),
            reverse=sort_dir == "desc",
        )
        items = (present + missing)[(page - 1) * page_size : page * page_size]
    return dict(total=total, page=page, page_size=page_size, items=items)


@router.get("/api/invoices/{invoice_id}")
def invoice_detail(
    invoice_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: SortField | None = Query(None),
    sort_dir: Literal["asc", "desc"] = Query("asc"),
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        dokument = session.get(Dokument, invoice_id)
        if dokument is None:
            raise HTTPException(404, translate("errors.history.invoice_not_found", language))
        supplier = None
        if dokument.lieferant_id is not None:
            supplier = session.scalar(
                select(Lieferant.name).where(Lieferant.id == dokument.lieferant_id)
            )
        return dict(
            invoice=invoice_data(dokument, supplier),
            **positions(
                session,
                Wareneingang.dokument_id == invoice_id,
                page,
                page_size,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.history.positions_failed", language)
        ) from exc


@router.get("/api/articles/{product_id}/history")
def article_history(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: SortField | None = Query(None),
    sort_dir: Literal["asc", "desc"] = Query("asc"),
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        variante, group_ids = article_group(session, product_id, language)
        artikel = session.get(Artikel, variante.artikel_id)
        return dict(
            product={
                "id": variante.id,
                "brand": artikel.marke,
                "description": artikel.bezeichnung,
                "ean": variante.ean,
                "supplier_article_no": artikel.lieferanten_artikelnr,
            },
            **positions(
                session,
                WareneingangPosition.varianten_id.in_(group_ids),
                page,
                page_size,
                True,
                sort_by,
                sort_dir,
            )
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.history.article_history_failed", language)
        ) from exc


@router.delete("/api/invoices/{invoice_id}")
def remove_invoice(
    invoice_id: int,
    user=Depends(require_chef_api),
    language: str = Depends(get_language),
):
    try:
        return delete_invoice(invoice_id, SessionLocal, language)
    except DeleteRejected as exc:
        raise HTTPException(404, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.history.invoice_delete_failed", language)
        ) from exc
