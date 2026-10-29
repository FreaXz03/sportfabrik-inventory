"""Fehlermeldung und unbekanntes Dokument an Fabian (Punkte 4 und 5, 2026-10-01).

Beides sind eigene, ausdrückliche Klicks der Benutzer - hier wird nie etwas von
selbst gesendet. Der Empfänger ist fest (`app/services/mail.py`). Dokumente
verlassen das System nur auf diesem Weg (Ausnahme von Regel 1, 2026-10-01);
die Verarbeitung der Dokumente bleibt lokal.
"""

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from ..core.i18n import translate
from ..services import mail
from .auth import get_active_lagerort, get_language, require_chef_api, require_login_api

router = APIRouter()

MAX_TITEL = 120
MAX_NACHRICHT = 4000
MAX_NOTIZ = 1000
MAX_BILDER = 4
MAX_BILD_BYTES = 5 * 1024 * 1024
MAX_DOKUMENT_BYTES = 10 * 1024 * 1024  # Mail-Postfächer nehmen selten mehr als ~20 MB inkl. Kodierung

BILD_TYPEN = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "image/gif": b"GIF8",
    "image/webp": b"RIFF",
}


def _kontext(user, lagerort, request: Request) -> str:
    return (
        f"Von: {user.name} (Kasse {user.kassennummer}, {user.role})\n"
        f"Filiale: {lagerort.code if lagerort else '-'}\n"
        f"Zeit: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
        f"Browser: {request.headers.get('user-agent', '-')[:200]}\n"
    )


def _senden(user, language: str, betreff: str, text: str, anhaenge) -> dict:
    try:
        mail.pruefe_limit(user.kassennummer)
        mail.sende(betreff, text, anhaenge)
    except mail.MailNichtKonfiguriert as exc:
        raise HTTPException(503, translate("errors.meldung.not_configured", language)) from exc
    except mail.ZuOft as exc:
        raise HTTPException(429, translate("errors.meldung.rate_limit", language)) from exc
    except mail.MailFehler as exc:
        raise HTTPException(502, translate("errors.meldung.send_failed", language)) from exc
    return {"gesendet": True}


@router.get("/api/meldungen/status")
def status(user=Depends(require_login_api)):
    """Ob der Versand eingerichtet ist und wohin er geht - die Oberfläche zeigt beides vor dem Senden."""
    return {"konfiguriert": mail.konfiguriert(), "empfaenger": mail.EMPFAENGER}


@router.post("/api/fehlermeldung")
async def fehlermeldung(
    request: Request,
    titel: str = Form(""),
    nachricht: str = Form(""),
    seite: str = Form("", max_length=300),
    bilder: list[UploadFile] = File(default=[]),
    user=Depends(require_login_api),
    lagerort=Depends(get_active_lagerort),
    language: str = Depends(get_language),
):
    titel, nachricht = " ".join(titel.split()), nachricht.strip()
    if not titel:
        raise HTTPException(422, translate("errors.meldung.title_required", language))
    if not nachricht:
        raise HTTPException(422, translate("errors.meldung.message_required", language))
    if len(titel) > MAX_TITEL or len(nachricht) > MAX_NACHRICHT:
        raise HTTPException(422, translate("errors.meldung.too_long", language))
    bilder = [b for b in bilder if b.filename]
    if len(bilder) > MAX_BILDER:
        raise HTTPException(422, translate("errors.meldung.too_many_images", language, max=MAX_BILDER))
    anhaenge = []
    for bild in bilder:
        inhalt = await bild.read(MAX_BILD_BYTES + 1)
        if len(inhalt) > MAX_BILD_BYTES:
            raise HTTPException(422, translate("errors.meldung.too_large", language, mb=MAX_BILD_BYTES // 1024 // 1024))
        kennung = BILD_TYPEN.get(bild.content_type or "")
        if kennung is None or not inhalt.startswith(kennung):
            raise HTTPException(422, translate("errors.meldung.image_type", language))
        anhaenge.append((bild.filename, inhalt, bild.content_type))
    text = f"{titel}\n\n{nachricht}\n\n--\n{_kontext(user, lagerort, request)}Seite: {seite or '-'}\n"
    return await run_in_threadpool(_senden, user, language, f"[Sportfabrik] Fehler: {titel}", text, anhaenge)


@router.post("/api/dokument-melden")
async def dokument_melden(
    request: Request,
    file: UploadFile,
    notiz: str = Form("", max_length=MAX_NOTIZ),
    user=Depends(require_chef_api),
    lagerort=Depends(get_active_lagerort),
    language: str = Depends(get_language),
):
    """Ein vom System nicht erkanntes Dokument auf ausdrücklichen Klick an Fabian senden."""
    inhalt = await file.read(MAX_DOKUMENT_BYTES + 1)
    if len(inhalt) > MAX_DOKUMENT_BYTES:
        raise HTTPException(422, translate("errors.meldung.too_large", language, mb=MAX_DOKUMENT_BYTES // 1024 // 1024))
    if not inhalt.startswith(b"%PDF"):
        raise HTTPException(422, translate("errors.meldung.not_pdf", language))
    name = file.filename or "dokument.pdf"
    text = (
        f"Das System hat dieses Dokument nicht erkannt; es wurde ausdrücklich per Klick gesendet.\n\n"
        f"Datei: {name} ({len(inhalt)} Bytes, SHA-256 {hashlib.sha256(inhalt).hexdigest()[:16]}…)\n"
        f"Notiz: {notiz.strip() or '-'}\n\n--\n{_kontext(user, lagerort, request)}"
    )
    return await run_in_threadpool(_senden, user, language, f"[Sportfabrik] Unbekanntes Dokument: {name}", text, [(name, inhalt, "application/pdf")])
