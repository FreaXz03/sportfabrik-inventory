from fastapi import HTTPException
from sqlalchemy import select
from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import Variante


def article_group(session, varianten_id, language: str = DEFAULT_LANGUAGE):
    """Alle Varianten desselben Artikels - seit der Migration auf das neue
    Datenmodell (Phase A Punkt 3) eine echte Fremdschlüsselbeziehung
    (`varianten.artikel_id`) statt einer zur Laufzeit nachgebildeten
    Gruppierung über Marke + Lieferanten-Artikelnummer."""
    variante = session.get(Variante, varianten_id)
    if variante is None:
        raise HTTPException(404, translate("errors.article_details.product_not_found", language))
    ids = select(Variante.id).where(Variante.artikel_id == variante.artikel_id)
    return variante, ids
