"""Sperre nach zu vielen falschen Passwörtern (Sicherheit S2, Entscheid von
Fabian am 24.09.2026): nach **5** Fehlversuchen ist das Konto **20 Minuten**
gesperrt, auch für das richtige Passwort. Ein erfolgreicher Login setzt den
Zähler zurück. Gezählt wird je Konto und in der Datenbank, damit ein Neustart
die Sperre nicht aufhebt. Mitarbeiter haben kein Passwort und damit keine
Fehlversuche - ihr Schutz ist, dass nur Laden-PCs den Server erreichen
(docs/sicherheit.md).
"""

import math
from datetime import datetime, timedelta, timezone

MAX_FEHLVERSUCHE = 5
SPERRDAUER = timedelta(minutes=20)


def jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _utc(zeitpunkt: datetime) -> datetime:
    # SQLite gibt Zeitpunkte ohne Zeitzone zurück; gespeichert wird immer UTC.
    return zeitpunkt if zeitpunkt.tzinfo else zeitpunkt.replace(tzinfo=timezone.utc)


def gesperrt_minuten(user) -> int | None:
    """Restliche Sperrzeit in ganzen Minuten (aufgerundet), sonst None."""
    if user.gesperrt_bis is None:
        return None
    rest = _utc(user.gesperrt_bis) - jetzt()
    if rest <= timedelta(0):
        return None
    return math.ceil(rest.total_seconds() / 60)


def fehlversuch(user) -> None:
    """Falsches Passwort zählen; beim fünften sperren und neu zählen."""
    user.fehlversuche = (user.fehlversuche or 0) + 1
    if user.fehlversuche >= MAX_FEHLVERSUCHE:
        user.gesperrt_bis = jetzt() + SPERRDAUER
        user.fehlversuche = 0


def erfolg(user) -> None:
    user.fehlversuche = 0
    user.gesperrt_bis = None
