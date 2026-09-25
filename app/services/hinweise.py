"""Nachlieferungs-Hinweis (D-F2, 25.09.2026).

Regel 6 lässt die Reduktionsuhr beim nächsten Wareneingang für das ganze
Modell neu starten - der Bestand trennt keine Chargen, ein Teil der
Lieferung könnte also noch auf der alten (höheren) Stufe stehen. Statt den
Bestand technisch aufzuteilen, bekommt die Filiale hier nur einen Hinweis,
damit sie den Altbestand bei Bedarf von Hand über `reduktionen_manuell`
wieder auf seine bisherige Stufe setzt.

`pruefe_und_merke` wird einmal je Artikel **vor** dem Buchen einer neuen
Lieferung aufgerufen (import oder Ankunftsbestätigung) und hält die vorher
geltende Stufe in `cache` fest, wenn sie über 0 lag. `erstelle_hinweise`
schreibt danach je betroffenem Artikel eine Zeile."""

from sqlalchemy import desc, select

from ..core.models import Artikel, Hinweis, Lagerort
from .reduktion import letzter_wareneingang, stufe

NACHLIEFERUNG_REDUZIERT = "nachlieferung_reduziert"
STANDARD_ANZAHL = 20


def pruefe_und_merke(session, artikel_id: int, lagerort_id: int, cache: dict) -> None:
    if artikel_id in cache:
        return
    vorher = stufe(letzter_wareneingang(session, artikel_id, lagerort_id))
    cache[artikel_id] = vorher if vorher > 0 else None


def erstelle_hinweise(session, lagerort_id: int, cache: dict) -> None:
    for artikel_id, alte_stufe in cache.items():
        if alte_stufe:
            session.add(
                Hinweis(
                    lagerort_id=lagerort_id,
                    artikel_id=artikel_id,
                    typ=NACHLIEFERUNG_REDUZIERT,
                    alte_stufe=alte_stufe,
                )
            )


def liste(session, lagerort_id: int, anzahl: int = STANDARD_ANZAHL) -> list[dict]:
    """Neueste Hinweise einer Filiale, für die Übersicht."""
    zeilen = session.execute(
        select(Hinweis, Artikel, Lagerort)
        .join(Artikel, Artikel.id == Hinweis.artikel_id)
        .join(Lagerort, Lagerort.id == Hinweis.lagerort_id)
        .where(Hinweis.lagerort_id == lagerort_id)
        .order_by(desc(Hinweis.erstellt_am), desc(Hinweis.id))
        .limit(anzahl)
    ).all()
    return [
        {
            "id": hinweis.id,
            "typ": hinweis.typ,
            "artikel_id": artikel.id,
            "marke": artikel.marke,
            "bezeichnung": artikel.bezeichnung,
            "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
            "alte_stufe": hinweis.alte_stufe,
            "erstellt_am": hinweis.erstellt_am.isoformat(),
            "lagerort": {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
        }
        for hinweis, artikel, lagerort in zeilen
    ]
