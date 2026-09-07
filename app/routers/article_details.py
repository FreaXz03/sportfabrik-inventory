from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, update, delete
from sqlalchemy.exc import SQLAlchemyError
from .auth import require_login_api
from ..services.article_groups import article_group
from ..core.database import get_session
from ..core.models import Product, Invoice, InvoiceItem, ArticleNote

router = APIRouter()


@router.delete("/api/articles/{product_id}/notes/{note_id}", status_code=204)
def delete_note(
    product_id: int,
    note_id: int,
    version: int = Query(..., ge=1),
    user=Depends(require_login_api),
    session=Depends(get_session),
):
    try:
        _, group_ids = article_group(session, product_id)
        note = session.scalar(select(ArticleNote).where(ArticleNote.id == note_id, ArticleNote.product_id.in_(group_ids)))
        if note is None:
            raise HTTPException(404, "Notiz nicht gefunden.")
        if user.role != "chef" and note.author_user_id != user.id:
            raise HTTPException(
                403, "Nur eigene Notizen oder als Filialleiter löschen."
            )
        result = session.execute(
            delete(ArticleNote).where(
                ArticleNote.id == note_id, ArticleNote.version == version
            )
        )
        if result.rowcount != 1:
            session.rollback()
            raise HTTPException(
                409,
                "Die Notiz wurde inzwischen geändert. Bitte neu laden und erneut prüfen.",
            )
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(503, "Notiz konnte nicht gelöscht werden.") from exc


def product_exists(session, product_id):
    if session.get(Product, product_id) is None:
        raise HTTPException(404, "Artikel nicht gefunden.")


@router.get("/api/articles/{product_id}/prices")
def prices(
    product_id: int, user=Depends(require_login_api), session=Depends(get_session)
):
    try:
        _, group_ids = article_group(session, product_id)
        rows = session.execute(
            select(
                Invoice.id,
                Invoice.invoice_number,
                Invoice.invoice_date,
                InvoiceItem.unit,
                InvoiceItem.uvp,
                func.count(InvoiceItem.id).label("positions"),
            )
            .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
            .where(InvoiceItem.product_id.in_(group_ids), InvoiceItem.uvp.is_not(None))
            .group_by(
                Invoice.id,
                Invoice.invoice_number,
                Invoice.invoice_date,
                InvoiceItem.unit,
                InvoiceItem.uvp,
            )
            .order_by(
                Invoice.invoice_date.asc().nulls_last(),
                Invoice.id,
                InvoiceItem.unit,
                InvoiceItem.uvp,
            )
        ).all()
        return {
            "items": [
                {
                    "invoice_id": r[0],
                    "invoice_number": r[1],
                    "date": r[2],
                    "unit": r[3],
                    "uvp": format(r[4], "f"),
                    "positions": r[5],
                }
                for r in rows
            ]
        }
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Preisverlauf konnte nicht geladen werden.") from exc


class NoteBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Notiz darf nicht leer sein.")
        return value


class NoteEdit(NoteBody):
    version: int = Field(ge=1)


def note_data(note, user):
    result = {
        key: getattr(note, key)
        for key in (
            "id",
            "body",
            "author_name",
            "author_number",
            "updated_by",
            "created_at",
            "updated_at",
            "version",
        )
    }
    # SQLite drops timezone info; database values are stored in UTC.
    for key in ("created_at", "updated_at"):
        if result[key].tzinfo is None:
            result[key] = result[key].replace(tzinfo=timezone.utc)
    result["can_edit"] = user.role == "chef" or user.id == note.author_user_id
    return result


@router.get("/api/articles/{product_id}/notes")
def notes(
    product_id: int,
    page: int = Query(1, ge=1),
    user=Depends(require_login_api),
    session=Depends(get_session),
):
    try:
        _, group_ids = article_group(session, product_id)
        condition = ArticleNote.product_id.in_(group_ids)
        count = session.scalar(
            select(func.count()).select_from(ArticleNote).where(condition)
        )
        rows = session.scalars(
            select(ArticleNote)
            .where(condition)
            .order_by(ArticleNote.created_at.desc(), ArticleNote.id.desc())
            .offset((page - 1) * 20)
            .limit(20)
        ).all()
        return {
            "items": [note_data(note, user) for note in rows],
            "total": count,
            "page": page,
            "page_size": 20,
        }
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Notizen konnten nicht geladen werden.") from exc


@router.post("/api/articles/{product_id}/notes", status_code=201)
def create_note(
    product_id: int,
    payload: NoteBody,
    user=Depends(require_login_api),
    session=Depends(get_session),
):
    try:
        product_exists(session, product_id)
        name = user.name or user.kassennummer
        note = ArticleNote(
            product_id=product_id,
            body=payload.body,
            author_user_id=user.id,
            author_name=name,
            author_number=user.kassennummer,
            updated_by=name,
        )
        session.add(note)
        session.flush()
        result = note_data(note, user)
        session.commit()
        return result
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(503, "Notiz konnte nicht gespeichert werden.") from exc


@router.put("/api/articles/{product_id}/notes/{note_id}")
def edit_note(
    product_id: int,
    note_id: int,
    payload: NoteEdit,
    user=Depends(require_login_api),
    session=Depends(get_session),
):
    try:
        _, group_ids = article_group(session, product_id)
        note = session.scalar(select(ArticleNote).where(ArticleNote.id == note_id, ArticleNote.product_id.in_(group_ids)))
        if note is None:
            raise HTTPException(404, "Notiz nicht gefunden.")
        if user.role != "chef" and note.author_user_id != user.id:
            raise HTTPException(
                403, "Nur eigene Notizen oder als Filialleiter bearbeiten."
            )
        result = session.execute(
            update(ArticleNote)
            .where(ArticleNote.id == note_id, ArticleNote.version == payload.version)
            .values(
                body=payload.body,
                version=ArticleNote.version + 1,
                updated_at=datetime.now(timezone.utc),
                updated_by=user.name or user.kassennummer,
            )
        )
        if result.rowcount != 1:
            session.rollback()
            raise HTTPException(
                409,
                "Die Notiz wurde inzwischen geändert. Bitte neu laden und Änderungen vergleichen.",
            )
        session.refresh(note)
        result = note_data(note, user)
        session.commit()
        return result
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(503, "Notiz konnte nicht aktualisiert werden.") from exc
