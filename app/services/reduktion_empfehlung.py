"""Empfehlung der Zentrale (D-F3, 25.09.2026).

Die Zentrale setzt je Modell und Filiale eine Stufe ab einem Datum („−50 %
ab 1.10."). Die Filiale sieht die offene Empfehlung auf ihrer
Runterschreiben-Liste und übernimmt sie (setzt dieselbe Stufe von Hand,
`reduktionen_manuell`) oder lehnt sie mit kurzem Grund ab. Die Zentrale sieht
alle Antworten - so werden Abweichungen sichtbar.

Höchstens eine offene Empfehlung je Modell × Filiale: eine neue Empfehlung
ersetzt eine ältere (auch eine schon beantwortete) für dieselbe Kombination.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from ..core.models import Artikel, Lagerort, ReduktionEmpfehlungZentrale
from . import reduktion_manuell

PROZENTE = (30, 50, 70)
STATUS = ("offen", "uebernommen", "abgelehnt")
GRUND_MAX = 200


class EmpfehlungRejected(ValueError):
    """Ungültige Eingabe - nichts wurde gespeichert."""


def setzen(session, *, artikel_id: int, lagerort_id: int, prozent: int, ab_datum, benutzer) -> dict:
    if prozent not in PROZENTE:
        raise EmpfehlungRejected(f"Prozent muss einer von {PROZENTE} sein.")
    eintrag = session.scalar(
        select(ReduktionEmpfehlungZentrale).where(
            ReduktionEmpfehlungZentrale.artikel_id == artikel_id,
            ReduktionEmpfehlungZentrale.lagerort_id == lagerort_id,
        )
    )
    if eintrag is None:
        eintrag = ReduktionEmpfehlungZentrale(artikel_id=artikel_id, lagerort_id=lagerort_id)
        session.add(eintrag)
    eintrag.prozent = prozent
    eintrag.ab_datum = ab_datum
    eintrag.status = "offen"
    eintrag.ablehnungsgrund = None
    eintrag.gesetzt_von_kassennummer = benutzer.kassennummer
    eintrag.gesetzt_von_name = benutzer.name
    eintrag.gesetzt_am = datetime.now(timezone.utc)
    eintrag.beantwortet_von_name = None
    eintrag.beantwortet_am = None
    session.commit()
    return _daten(eintrag)


def _daten(eintrag: ReduktionEmpfehlungZentrale) -> dict:
    return {
        "id": eintrag.id,
        "artikel_id": eintrag.artikel_id,
        "lagerort_id": eintrag.lagerort_id,
        "prozent": eintrag.prozent,
        "ab_datum": eintrag.ab_datum.isoformat(),
        "status": eintrag.status,
        "ablehnungsgrund": eintrag.ablehnungsgrund,
        "gesetzt_von": eintrag.gesetzt_von_name,
        "gesetzt_am": eintrag.gesetzt_am.isoformat() if eintrag.gesetzt_am else None,
        "beantwortet_von": eintrag.beantwortet_von_name,
        "beantwortet_am": eintrag.beantwortet_am.isoformat() if eintrag.beantwortet_am else None,
    }


def liste_offen_fuer_filiale(session, lagerort_id: int) -> list[dict]:
    zeilen = session.execute(
        select(ReduktionEmpfehlungZentrale, Artikel)
        .join(Artikel, Artikel.id == ReduktionEmpfehlungZentrale.artikel_id)
        .where(
            ReduktionEmpfehlungZentrale.lagerort_id == lagerort_id,
            ReduktionEmpfehlungZentrale.status == "offen",
        )
        .order_by(ReduktionEmpfehlungZentrale.ab_datum, Artikel.marke, Artikel.bezeichnung)
    ).all()
    return [
        {
            **_daten(eintrag),
            "marke": artikel.marke,
            "bezeichnung": artikel.bezeichnung,
            "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
        }
        for eintrag, artikel in zeilen
    ]


def liste_zentrale(session) -> list[dict]:
    """Alle Empfehlungen mit Antwortstatus, für die Zentrale - zeigt
    Abweichungen zwischen Filialen."""
    zeilen = session.execute(
        select(ReduktionEmpfehlungZentrale, Artikel, Lagerort)
        .join(Artikel, Artikel.id == ReduktionEmpfehlungZentrale.artikel_id)
        .join(Lagerort, Lagerort.id == ReduktionEmpfehlungZentrale.lagerort_id)
        .order_by(ReduktionEmpfehlungZentrale.gesetzt_am.desc(), ReduktionEmpfehlungZentrale.id.desc())
    ).all()
    return [
        {
            **_daten(eintrag),
            "marke": artikel.marke,
            "bezeichnung": artikel.bezeichnung,
            "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
            "lagerort": {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
        }
        for eintrag, artikel, lagerort in zeilen
    ]


def antworten(session, empfehlung_id: int, *, status: str, grund: str | None, benutzer) -> dict:
    if status not in ("uebernommen", "abgelehnt"):
        raise EmpfehlungRejected("Status muss uebernommen oder abgelehnt sein.")
    eintrag = session.get(ReduktionEmpfehlungZentrale, empfehlung_id)
    if eintrag is None:
        return None
    if eintrag.status != "offen":
        raise EmpfehlungRejected("Diese Empfehlung wurde bereits beantwortet.")
    if status == "abgelehnt":
        grund = (grund or "").strip()
        if not grund:
            raise EmpfehlungRejected("Für eine Ablehnung ist ein Grund nötig.")
        if len(grund) > GRUND_MAX:
            raise EmpfehlungRejected(f"Grund darf höchstens {GRUND_MAX} Zeichen haben.")
        eintrag.ablehnungsgrund = grund
    else:
        reduktion_manuell.setzen(session, eintrag.artikel_id, eintrag.lagerort_id, eintrag.prozent, benutzer)
    eintrag.status = status
    eintrag.beantwortet_von_name = benutzer.name
    eintrag.beantwortet_am = datetime.now(timezone.utc)
    session.commit()
    return _daten(eintrag)
