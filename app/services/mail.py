"""Mailversand an Fabian (Punkte 4 und 5, 2026-10-01).

Zwei Wege führen hierher: die Fehlermeldung (jeder Benutzer, mit Titel, Text
und Bildern) und das Senden eines unbekannten Dokuments (Filialleiter/Zentrale,
Ausnahme von Regel 1). Beides nur auf ausdrücklichen Klick - nie automatisch.

Der Empfänger steht fest hier im Code und kommt **nie** aus einer Eingabe: das
System kann so an niemand anderen als Fabians Postfach senden.

Einrichtung über die Umgebung (siehe docs/SERVER-SETUP.md):
`SMTP_HOST` (ohne ihn ist der Versand aus), `SMTP_PORT` (587), `SMTP_USER`,
`SMTP_PASSWORD`, `SMTP_FROM` (sonst `SMTP_USER`), `SMTP_STARTTLS` (1) bzw.
`SMTP_SSL=1` für Port 465.
"""

import os
import smtplib
import time
from email.message import EmailMessage

EMPFAENGER = "fabian_morf@icloud.com"

# Pro Konto höchstens so viele Meldungen je Stunde (Schutz vor Dauerfeuer).
MAX_JE_STUNDE = 10
_versand_log: dict[str, list[float]] = {}


class MailNichtKonfiguriert(RuntimeError):
    """Auf diesem Server ist kein SMTP-Server eingerichtet."""


class MailFehler(RuntimeError):
    """Der SMTP-Server hat die Mail nicht angenommen."""


class ZuOft(RuntimeError):
    """Dieses Konto hat die Stundengrenze erreicht."""


def konfiguriert() -> bool:
    return bool(os.getenv("SMTP_HOST", "").strip()) and bool(_absender())


def _absender() -> str:
    return (os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "").strip()


def _einzeilig(text: str, laenge: int) -> str:
    """Kopfzeilen-Text: Zeilenumbrüche weg (sonst liessen sich Kopfzeilen einschleusen)."""
    return " ".join(str(text).split())[:laenge]


def pruefe_limit(konto: str) -> None:
    jetzt = time.time()
    liste = [t for t in _versand_log.get(konto, []) if jetzt - t < 3600]
    if len(liste) >= MAX_JE_STUNDE:
        _versand_log[konto] = liste
        raise ZuOft()
    liste.append(jetzt)
    _versand_log[konto] = liste


def sende(betreff: str, text: str, anhaenge: list[tuple[str, bytes, str]] = (), antwort_an: str | None = None) -> None:
    """Mail an Fabian senden. `anhaenge`: `(Dateiname, Inhalt, "typ/untertyp")`."""
    if not konfiguriert():
        raise MailNichtKonfiguriert()
    nachricht = EmailMessage()
    nachricht["From"] = _absender()
    nachricht["To"] = EMPFAENGER
    nachricht["Subject"] = _einzeilig(betreff, 150)
    if antwort_an:
        nachricht["Reply-To"] = _einzeilig(antwort_an, 200)
    nachricht.set_content(text)
    for name, inhalt, typ in anhaenge:
        haupt, _, unter = typ.partition("/")
        nachricht.add_attachment(inhalt, maintype=haupt, subtype=unter or "octet-stream", filename=_einzeilig(name, 150))
    host, port = os.environ["SMTP_HOST"].strip(), int(os.getenv("SMTP_PORT", "587"))
    try:
        if os.getenv("SMTP_SSL", "").strip().lower() in ("1", "true", "yes"):
            verbindung = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            verbindung = smtplib.SMTP(host, port, timeout=20)
        with verbindung as smtp:
            if os.getenv("SMTP_STARTTLS", "1").strip().lower() not in ("0", "false", "no") and not isinstance(verbindung, smtplib.SMTP_SSL):
                smtp.starttls()
            if os.getenv("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(nachricht)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailFehler(str(exc)) from exc
