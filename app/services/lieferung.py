"""Dokumente und Lieferungen (Paket 1, Schritt 2, 01.10.2026).

Eine Lieferung ist ein Wareneingang. Lieferschein und Rechnung zur selben Ware
wie eine bestehende Lieferung (Auftragsbestätigung, früherer Lieferschein)
buchen nichts ein zweites Mal, sondern hängen an ihr. Die Wahl trifft immer
der Benutzer (Entscheid Q3): erkennt das System eine passende Lieferung, fragt
es, bevor es etwas bucht oder anhängt.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..core.models import (
    Dokument,
    Lieferant,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from .artikel import (
    artikel_group_key,
    finde_artikel,
    finde_variante_ohne_ean,
    finde_variante_per_ean,
)

# Nur Dokumente über Ware, die schon da ist oder kommt, fragen nach einer
# Lieferung; eine Auftragsbestätigung/Bestellung beginnt selbst eine.
FRAGT_NACH_LIEFERUNG = frozenset({"rechnung", "lieferschein"})
# Eine Lieferung gilt als passend, wenn mindestens diese Hälfte der Zeilen
# des neuen Dokuments dort vorkommt und sie nicht älter als MATCH_TAGE ist.
# Richtwerte - ein Nachbessern ändert nur, wann gefragt wird, nie, was gebucht wird.
MATCH_MIN_ANTEIL = 0.5
MATCH_TAGE = 120
NEU = "neu"


def finde_lieferant(session, parsed: dict) -> Lieferant | None:
    """Lieferant aus dem erkannten Layout: `parser_key` verbindet Parser-Modul
    und Stammdaten. Gehört das Dokument zu einer anderen Lieferantengruppe als
    der Parser (ECOM-Retoure im INTERSPORT-Layout), zählt die Gruppe."""
    if parsed.get("lieferant_typ"):
        return session.scalar(
            select(Lieferant)
            .where(Lieferant.typ == parsed["lieferant_typ"])
            .order_by(Lieferant.id)
            .limit(1)
        )
    return session.scalar(select(Lieferant).where(Lieferant.parser_key == parsed["parser_key"]))


def bekannte_varianten(session, lieferant_id: int, items: list[dict]) -> dict[int, Variante | None]:
    """Variante je Position (Index) - nur Bestehende, nichts wird angelegt."""
    ergebnis = {}
    for index, item in enumerate(items):
        variante = finde_variante_per_ean(session, item.get("ean") or None)
        if variante is None and not item.get("ean"):
            artikel = finde_artikel(
                session,
                lieferant_id,
                artikel_group_key(item.get("brand"), item.get("supplier_article_no")),
            )
            if artikel is not None:
                variante = finde_variante_ohne_ean(
                    session, artikel.id, item.get("color"), item.get("size")
                )
        ergebnis[index] = variante
    return ergebnis


def finde_kandidaten(
    session, lieferant_id: int, lagerort_id: int, items: list[dict]
) -> list[dict]:
    """Bestehende Lieferungen dieses Lieferanten an dieser Filiale, die zu den
    Zeilen des neuen Dokuments passen - die beste zuerst."""
    if not items:
        return []
    varianten_ids = {
        v.id for v in bekannte_varianten(session, lieferant_id, items).values() if v is not None
    }
    if not varianten_ids:
        return []
    seit = datetime.now(timezone.utc) - timedelta(days=MATCH_TAGE)
    rows = session.execute(
        select(Wareneingang, Dokument)
        .join(Dokument, Dokument.id == Wareneingang.dokument_id)
        .where(
            Dokument.lieferant_id == lieferant_id,
            Dokument.status == "aktiv",
            Dokument.hochgeladen_am >= seit,
            Wareneingang.lagerort_id == lagerort_id,
            Wareneingang.status.in_(("erwartet", "eingetroffen", "abgeschlossen")),
        )
    ).all()
    kandidaten = []
    for wareneingang, dokument in rows:
        in_lieferung = set(
            session.scalars(
                select(WareneingangPosition.varianten_id).where(
                    WareneingangPosition.wareneingang_id == wareneingang.id
                )
            )
        )
        treffer = len(varianten_ids & in_lieferung)
        if treffer / len(items) < MATCH_MIN_ANTEIL:
            continue
        kandidaten.append(
            {
                "wareneingang_id": wareneingang.id,
                "status": wareneingang.status,
                "dokument": {
                    "id": dokument.id,
                    "invoice_number": dokument.dokumentnummer,
                    "typ": dokument.typ,
                    "invoice_date": dokument.dokumentdatum,
                },
                "treffer": treffer,
                "zeilen": len(items),
            }
        )
    kandidaten.sort(key=lambda k: (-k["treffer"], -k["dokument"]["id"]))
    return kandidaten


def pruefe_ziel(
    session, wareneingang_id: int, lieferant_id: int, lagerort_id: int
) -> Wareneingang | None:
    """Die gewählte Lieferung, wenn sie zu diesem Lieferanten und dieser
    Filiale gehört und nicht storniert ist - sonst `None`."""
    return session.scalar(
        select(Wareneingang)
        .join(Dokument, Dokument.id == Wareneingang.dokument_id)
        .where(
            Wareneingang.id == wareneingang_id,
            Dokument.lieferant_id == lieferant_id,
            Dokument.status == "aktiv",
            Wareneingang.lagerort_id == lagerort_id,
            Wareneingang.status.in_(("erwartet", "eingetroffen", "abgeschlossen")),
        )
    )
