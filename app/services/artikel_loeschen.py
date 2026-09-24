"""Falsch erfassten Artikel wieder entfernen (Entscheid vom 24.09.2026).

Trägt jemand auf der Seite „Erfassen" einen Artikel falsch neu ein, muss ihn
jemand wieder herausnehmen können. Dafür gilt:

* **Nur Filialleiter und Zentrale** dürfen löschen (Router).
* **Nur ohne Beleg**: hängt an irgendeiner Variante des Artikels eine
  Position aus einem Dokument, wird abgelehnt - Artikel aus Belegen bleiben
  im Stamm (Regel 4); dort korrigiert oder löscht man den Beleg.
* **Ganz weg**: Artikel, Varianten, Preise, Notizen, die manuellen
  Wareneingangspositionen (und leer gewordene manuelle Wareneingänge),
  Bestand und alle Lagerbewegungen der Varianten. Der Fehleintrag soll keine
  Spuren im Bestand hinterlassen - eine bewusste, eng begrenzte Ausnahme von
  Regel 2. Protokolliert wird der Vorgang im Server-Log (wer, wann, was).
"""

import logging

from sqlalchemy import delete, exists, func, select

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import (
    ArticleNote,
    Artikel,
    Bestand,
    Lagerbewegung,
    Preis,
    Variante,
    Wareneingang,
    WareneingangPosition,
    WareneingangPositionQuelle,
)
from .ausbuchung import sperren

log = logging.getLogger(__name__)


class LoeschenRejected(ValueError):
    """Der Artikel darf nicht gelöscht werden - nichts wurde verändert."""


def hat_beleg(session, artikel_id: int) -> bool:
    """Hängt an einer Variante des Artikels eine Position aus einem Dokument?"""
    return bool(
        session.scalar(
            select(
                exists()
                .where(WareneingangPosition.wareneingang_id == Wareneingang.id)
                .where(WareneingangPosition.varianten_id == Variante.id)
                .where(Variante.artikel_id == artikel_id)
                .where(Wareneingang.dokument_id.is_not(None))
            )
        )
    )


def loesche_artikel(
    session_factory,
    varianten_id: int,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Den Artikel der Variante `varianten_id` samt allem, was an ihm hängt,
    entfernen - nur wenn kein Beleg daran hängt."""
    with session_factory() as session, session.begin():
        sperren(session)
        variante = session.get(Variante, varianten_id)
        if variante is None:
            raise LoeschenRejected(translate("errors.ausbuchung.variant_not_found", language))
        artikel = session.get(Artikel, variante.artikel_id)
        if hat_beleg(session, artikel.id):
            raise LoeschenRejected(translate("errors.artikel_loeschen.has_document", language))

        varianten_ids = list(
            session.scalars(select(Variante.id).where(Variante.artikel_id == artikel.id)).all()
        )
        positionen = list(
            session.scalars(
                select(WareneingangPosition.id).where(
                    WareneingangPosition.varianten_id.in_(varianten_ids)
                )
            ).all()
        )
        wareneingaenge = set(
            session.scalars(
                select(WareneingangPosition.wareneingang_id).where(
                    WareneingangPosition.id.in_(positionen)
                )
            ).all()
        ) if positionen else set()

        bewegungen = session.execute(
            delete(Lagerbewegung).where(Lagerbewegung.varianten_id.in_(varianten_ids))
        ).rowcount
        session.execute(delete(Bestand).where(Bestand.varianten_id.in_(varianten_ids)))
        if positionen:
            session.execute(
                delete(WareneingangPositionQuelle).where(
                    WareneingangPositionQuelle.position_id.in_(positionen)
                )
            )
            session.execute(
                delete(WareneingangPosition).where(WareneingangPosition.id.in_(positionen))
            )
        # Ein manueller Wareneingang ohne Positionen ist leer - weg damit.
        for wareneingang_id in wareneingaenge:
            rest = session.scalar(
                select(func.count())
                .select_from(WareneingangPosition)
                .where(WareneingangPosition.wareneingang_id == wareneingang_id)
            )
            if not rest:
                session.execute(delete(Wareneingang).where(Wareneingang.id == wareneingang_id))
        session.execute(delete(Preis).where(Preis.varianten_id.in_(varianten_ids)))
        session.execute(delete(ArticleNote).where(ArticleNote.artikel_id == artikel.id))
        session.execute(delete(Variante).where(Variante.id.in_(varianten_ids)))
        session.execute(delete(Artikel).where(Artikel.id == artikel.id))

        ergebnis = {
            "artikel_id": artikel.id,
            "marke": artikel.marke,
            "bezeichnung": artikel.bezeichnung,
            "varianten": len(varianten_ids),
            "bewegungen": int(bewegungen or 0),
        }
    log.info(
        "Artikel geloescht: id=%s marke=%r bezeichnung=%r varianten=%s bewegungen=%s von %s (%s)",
        ergebnis["artikel_id"],
        ergebnis["marke"],
        ergebnis["bezeichnung"],
        ergebnis["varianten"],
        ergebnis["bewegungen"],
        (benutzer or {}).get("name"),
        (benutzer or {}).get("kassennummer"),
    )
    return ergebnis
