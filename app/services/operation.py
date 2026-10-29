"""Wiederholungsschutz für Buchungen (Paket 2, 01.10.2026).

Ablauf in der Transaktion der Buchung, unter derselben Sperre:

1. `starte(...)` sucht die Operations-ID. Ist sie bekannt und die Anfrage
   dieselbe, liefert `op.gespeichert` die frühere Antwort - es wird nichts
   gebucht. Ist sie bekannt, aber Anfrage oder Benutzer sind andere, ist das ein
   Fehler (`OperationConflict`): eine ID gehört zu genau einer Aktion.
2. Nach der Buchung speichert `op.abschliessen(antwort)` die Antwort mit - im
   selben Commit. Eine abgewiesene Anfrage hinterlässt nichts.

Ohne ID (optional, Entscheid 01.10.2026) tut `starte` nichts.
"""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import Operation

ID_MUSTER = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
AUFBEWAHRUNG = timedelta(days=30)


class OperationConflict(ValueError):
    """Dieselbe Operations-ID für eine andere Aktion oder einen anderen Benutzer."""


def gueltige_id(wert: str | None) -> bool:
    return bool(wert) and ID_MUSTER.match(wert) is not None


def _hash(nutzlast: dict) -> str:
    text = json.dumps(nutzlast, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_sicher(antwort: dict) -> dict:
    """Die Antwort so speichern, wie ein Client sie gesehen hat (Daten/Zahlen
    als Text) - eine Wiederholung liefert dieselbe Gestalt."""
    return json.loads(json.dumps(antwort, default=str))


class _Keine:
    gespeichert = None

    def abschliessen(self, antwort: dict) -> dict:
        return antwort


class _Aktiv:
    gespeichert = None

    def __init__(self, session, operation_id, endpunkt, kassennummer, anfrage_hash):
        self._session = session
        self._werte = (operation_id, endpunkt, kassennummer, anfrage_hash)

    def abschliessen(self, antwort: dict) -> dict:
        operation_id, endpunkt, kassennummer, anfrage_hash = self._werte
        jetzt = datetime.now(timezone.utc)
        self._session.execute(delete(Operation).where(Operation.erstellt_am < jetzt - AUFBEWAHRUNG))
        self._session.add(
            Operation(
                operation_id=operation_id,
                endpunkt=endpunkt,
                kassennummer=kassennummer,
                anfrage_hash=anfrage_hash,
                antwort=_json_sicher(antwort),
                erstellt_am=jetzt,
            )
        )
        self._session.flush()
        return antwort


class _Wiederholung:
    def __init__(self, antwort: dict):
        self.gespeichert = {**antwort, "wiederholt": True}


def starte(
    session,
    operation_id: str | None,
    endpunkt: str,
    benutzer: dict | None,
    nutzlast: dict,
    language: str = DEFAULT_LANGUAGE,
):
    if not operation_id:
        return _Keine()
    kassennummer = (benutzer or {}).get("kassennummer")
    anfrage_hash = _hash(nutzlast)
    bekannt = session.get(Operation, operation_id)
    if bekannt is None:
        return _Aktiv(session, operation_id, endpunkt, kassennummer, anfrage_hash)
    if (
        bekannt.endpunkt != endpunkt
        or bekannt.kassennummer != kassennummer
        or bekannt.anfrage_hash != anfrage_hash
    ):
        raise OperationConflict(translate("errors.operation.conflict", language))
    return _Wiederholung(bekannt.antwort)
