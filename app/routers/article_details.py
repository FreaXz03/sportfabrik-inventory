from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, update, delete
from sqlalchemy.exc import SQLAlchemyError
from .auth import get_language, require_login_api
from ..services.article_groups import article_group
from ..core.database import get_session
from ..core.i18n import translate
from ..core.models import ArticleNote, Dokument, Variante, Wareneingang, WareneingangPosition

router = APIRouter()


def _may_edit_any_note(user) -> bool:
    """Filialleiter und Admin/Zentrale dürfen alle Notizen bearbeiten/löschen,
    Mitarbeiter nur eigene (siehe CLAUDE.md Regel 9)."""
    return user.role in ("chef", "admin")


def _artikel_id(session, varianten_id, language):
    """Notizen hängen am Artikel (Modell-Ebene, siehe ArticleNote), nicht an
    der einzelnen Variante - `product_id` in der URL ist weiterhin eine
    Varianten-Id (wie in der Artikelliste angeklickt)."""
    variante, _ = article_group(session, varianten_id, language)
    return variante.artikel_id


@router.delete("/api/articles/{product_id}/notes/{note_id}", status_code=204)
def delete_note(
    product_id: int,
    note_id: int,
    version: int = Query(..., ge=1),
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        artikel_id = _artikel_id(session, product_id, language)
        note = session.scalar(
            select(ArticleNote).where(
                ArticleNote.id == note_id, ArticleNote.artikel_id == artikel_id
            )
        )
        if note is None:
            raise HTTPException(404, translate("errors.article_details.note_not_found", language))
        if not _may_edit_any_note(user) and note.author_user_id != user.id:
            raise HTTPException(
                403, translate("errors.article_details.note_delete_forbidden", language)
            )
        result = session.execute(
            delete(ArticleNote).where(
                ArticleNote.id == note_id, ArticleNote.version == version
            )
        )
        if result.rowcount != 1:
            session.rollback()
            raise HTTPException(
                409, translate("errors.article_details.note_version_conflict", language)
            )
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            503, translate("errors.article_details.note_delete_failed", language)
        ) from exc


def product_exists(session, product_id, language):
    if session.get(Variante, product_id) is None:
        raise HTTPException(404, translate("errors.article_details.product_not_found", language))


@router.get("/api/articles/{product_id}/prices")
def prices(
    product_id: int,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        _, group_ids = article_group(session, product_id, language)
        rows = session.execute(
            select(
                Dokument.id,
                Dokument.dokumentnummer,
                Dokument.dokumentdatum,
                WareneingangPosition.einheit,
                WareneingangPosition.uvp,
                func.count(WareneingangPosition.id).label("positions"),
                func.sum(WareneingangPosition.menge).label("quantity"),
            )
            .select_from(WareneingangPosition)
            .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
            .join(Dokument, Dokument.id == Wareneingang.dokument_id)
            .where(
                WareneingangPosition.varianten_id.in_(group_ids),
                WareneingangPosition.uvp.is_not(None),
            )
            .group_by(
                Dokument.id,
                Dokument.dokumentnummer,
                Dokument.dokumentdatum,
                WareneingangPosition.einheit,
                WareneingangPosition.uvp,
            )
            .order_by(
                Dokument.dokumentdatum.asc().nulls_last(),
                Dokument.id,
                WareneingangPosition.einheit,
                WareneingangPosition.uvp,
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
                    "quantity": format(r[6], "f") if r[6] is not None else None,
                }
                for r in rows
            ]
        }
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.article_details.prices_failed", language)
        ) from exc


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
    result["can_edit"] = _may_edit_any_note(user) or user.id == note.author_user_id
    return result


@router.get("/api/articles/{product_id}/notes")
def notes(
    product_id: int,
    page: int = Query(1, ge=1),
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        artikel_id = _artikel_id(session, product_id, language)
        condition = ArticleNote.artikel_id == artikel_id
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
        raise HTTPException(
            503, translate("errors.article_details.notes_failed", language)
        ) from exc


@router.post("/api/articles/{product_id}/notes", status_code=201)
def create_note(
    product_id: int,
    payload: NoteBody,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        artikel_id = _artikel_id(session, product_id, language)
        name = user.name or user.kassennummer
        note = ArticleNote(
            artikel_id=artikel_id,
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
        raise HTTPException(
            503, translate("errors.article_details.note_save_failed", language)
        ) from exc


@router.put("/api/articles/{product_id}/notes/{note_id}")
def edit_note(
    product_id: int,
    note_id: int,
    payload: NoteEdit,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        artikel_id = _artikel_id(session, product_id, language)
        note = session.scalar(
            select(ArticleNote).where(
                ArticleNote.id == note_id, ArticleNote.artikel_id == artikel_id
            )
        )
        if note is None:
            raise HTTPException(404, translate("errors.article_details.note_not_found", language))
        if not _may_edit_any_note(user) and note.author_user_id != user.id:
            raise HTTPException(
                403, translate("errors.article_details.note_edit_forbidden", language)
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
                409, translate("errors.article_details.note_edit_conflict", language)
            )
        session.refresh(note)
        result = note_data(note, user)
        session.commit()
        return result
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            503, translate("errors.article_details.note_update_failed", language)
        ) from exc
