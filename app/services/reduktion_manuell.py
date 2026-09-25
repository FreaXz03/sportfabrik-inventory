"""Manuelle Reduktion je Modell × Filiale (Artikeldetails-Paket, 24.09.2026).

Die **Empfehlung** folgt weiter Regel 6 (18 Monate → 50 %, 36 → 70 %, ab dem
letzten Wareneingang des Modells in dieser Filiale). Daneben darf jede
Mitarbeiterin in ihren Filialen **30, 50 oder 70 %** von Hand wählen - keine
freien Prozentsätze. Gilt eine Wahl von Hand, ist sie die **wirksame** Stufe,
sonst die Empfehlung. Wer darf, prüft der Router (buchbare Lagerorte wie bei
Erfassung und Korrektur - die Wahl erweitert keine Filialzuordnung).
"""

from datetime import datetime, timezone

from sqlalchemy import select

from ..core.models import Artikel, ReduktionManuell, Variante
from .reduktion import stufe
from .uebersicht import _letzte_eingaenge

MANUELLE_STUFEN = (30, 50, 70)


def stufen(session, lagerort_id: int, artikel_ids) -> dict[int, dict]:
    """Empfehlung, Wahl von Hand und wirksame Stufe je Artikel in einer
    Filiale - für viele Artikel mit zwei Abfragen (Bestandsliste)."""
    artikel_ids = set(artikel_ids)
    if not artikel_ids:
        return {}
    eingaenge = _letzte_eingaenge(lagerort_id)
    daten = dict(
        session.execute(
            select(eingaenge.c.artikel_id, eingaenge.c.datum).where(
                eingaenge.c.artikel_id.in_(artikel_ids)
            )
        ).all()
    )
    manuell = dict(
        session.execute(
            select(ReduktionManuell.artikel_id, ReduktionManuell.prozent).where(
                ReduktionManuell.lagerort_id == lagerort_id,
                ReduktionManuell.artikel_id.in_(artikel_ids),
            )
        ).all()
    )
    ergebnis = {}
    for artikel_id in artikel_ids:
        empfehlung = stufe(daten.get(artikel_id))
        von_hand = manuell.get(artikel_id)
        ergebnis[artikel_id] = {
            "empfehlung": empfehlung,
            "manuell": von_hand,
            "wirksam": empfehlung if von_hand is None else von_hand,
        }
    return ergebnis


def artikel_von_variante(session, varianten_id: int) -> int | None:
    return session.scalar(select(Variante.artikel_id).where(Variante.id == varianten_id))


def setzen(session, artikel_id: int, lagerort_id: int, prozent: int | None, benutzer) -> dict:
    """Stufe von Hand setzen (30/50/70) oder mit `None` zurück zur
    Empfehlung. Pro Modell und Filiale gibt es höchstens eine Zeile."""
    eintrag = session.scalar(
        select(ReduktionManuell).where(
            ReduktionManuell.artikel_id == artikel_id,
            ReduktionManuell.lagerort_id == lagerort_id,
        )
    )
    if prozent is None:
        if eintrag is not None:
            session.delete(eintrag)
    else:
        if eintrag is None:
            eintrag = ReduktionManuell(artikel_id=artikel_id, lagerort_id=lagerort_id)
            session.add(eintrag)
        eintrag.prozent = prozent
        eintrag.benutzer_kassennummer = benutzer.kassennummer
        eintrag.benutzer_name = benutzer.name
        # Neu gesetzt: auch der Zeitpunkt ist neu.
        eintrag.gesetzt_am = datetime.now(timezone.utc)
    session.commit()
    return stufen(session, lagerort_id, [artikel_id])[artikel_id]


def liste(session, lagerort_id: int) -> list[dict]:
    """Alle Wahlen von Hand in einer Filiale, für die Seite Runterschreiben."""
    zeilen = session.execute(
        select(ReduktionManuell, Artikel)
        .join(Artikel, Artikel.id == ReduktionManuell.artikel_id)
        .where(ReduktionManuell.lagerort_id == lagerort_id)
        .order_by(Artikel.marke, Artikel.bezeichnung, Artikel.id)
    ).all()
    return [
        {
            "artikel_id": artikel.id,
            "marke": artikel.marke,
            "bezeichnung": artikel.bezeichnung,
            "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
            "prozent": eintrag.prozent,
            "gesetzt_von": eintrag.benutzer_name,
            "gesetzt_am": eintrag.gesetzt_am.isoformat() if eintrag.gesetzt_am else None,
        }
        for eintrag, artikel in zeilen
    ]
