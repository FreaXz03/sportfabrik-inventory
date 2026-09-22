"""Kategorie von Hand wählen (Phase B, Teilaufgabe B8).

Drei Endpunkte: die Auswahlliste (alle 35 Kassenkategorien, Regel 8), der
Stand eines Artikels (was ist gesetzt, woher kommt es, was schlägt der
FEDAS-Code vor) und das Setzen bzw. Leeren.

Die Kategorie hängt am Artikel, angesprochen wird sie aber - wie Notizen und
Preise - über die Varianten-Id aus der Artikelliste (`product_id`).

Rechte (Regel 9/D21): Artikelstamm pflegen ist kein Dokumenten-Upload, also
dürfen auch Mitarbeiter das.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from ..core.database import get_session
from ..core.i18n import translate
from ..services.kategorien import (
    KategorieError,
    KategorieNichtGefunden,
    artikel_kategorie,
    liste_kategorien,
    setze_kategorie,
)
from .auth import get_language, require_login_api

router = APIRouter()


@router.get("/api/kategorien")
def api_kategorien(
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        return {"items": liste_kategorien(session)}
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.kategorie.load_failed", language)
        ) from exc


@router.get("/api/articles/{product_id}/kategorie")
def api_artikel_kategorie(
    product_id: int,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        return artikel_kategorie(session, product_id, language)
    except KategorieNichtGefunden as exc:
        raise HTTPException(404, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.kategorie.load_failed", language)
        ) from exc


class KategorieBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `null` leert die Kategorie wieder (Tippfehler zurücknehmen).
    kategorie_id: int | None = None


@router.put("/api/articles/{product_id}/kategorie")
def api_kategorie_setzen(
    product_id: int,
    body: KategorieBody,
    user=Depends(require_login_api),
    session=Depends(get_session),
    language: str = Depends(get_language),
):
    try:
        return setze_kategorie(session, product_id, body.kategorie_id, language)
    except KategorieNichtGefunden as exc:
        raise HTTPException(404, str(exc)) from exc
    except KategorieError as exc:
        raise HTTPException(422, str(exc)) from exc
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            503, translate("errors.kategorie.save_failed", language)
        ) from exc
