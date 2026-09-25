"""Bestätigen auf der Runterschreiben-Liste (D-F1, 25.09.2026).

Eine Filiale bestätigt ein fälliges Modell als heruntergeschrieben - es
verschwindet dann aus der fälligen Liste, bis die nächste Stufe (Regel 6)
fällig wird. Bezieht sich auf die automatische Stufe, nicht auf eine von Hand
gewählte Reduktion (`reduktionen_manuell`)."""

from datetime import datetime, timezone

from sqlalchemy import select

from ..core.models import ReduktionBestaetigt


def bestaetigte_stufen(session, lagerort_id: int, artikel_ids) -> dict[int, int]:
    """Je Artikel die zuletzt bestätigte Stufe in dieser Filiale."""
    artikel_ids = set(artikel_ids)
    if not artikel_ids:
        return {}
    return dict(
        session.execute(
            select(ReduktionBestaetigt.artikel_id, ReduktionBestaetigt.stufe).where(
                ReduktionBestaetigt.lagerort_id == lagerort_id,
                ReduktionBestaetigt.artikel_id.in_(artikel_ids),
            )
        ).all()
    )


def bestaetigen(session, artikel_id: int, lagerort_id: int, stufe: int, benutzer) -> None:
    eintrag = session.scalar(
        select(ReduktionBestaetigt).where(
            ReduktionBestaetigt.artikel_id == artikel_id,
            ReduktionBestaetigt.lagerort_id == lagerort_id,
        )
    )
    if eintrag is None:
        eintrag = ReduktionBestaetigt(artikel_id=artikel_id, lagerort_id=lagerort_id)
        session.add(eintrag)
    eintrag.stufe = stufe
    eintrag.benutzer_kassennummer = benutzer.kassennummer
    eintrag.benutzer_name = benutzer.name
    eintrag.bestaetigt_am = datetime.now(timezone.utc)
    session.commit()
