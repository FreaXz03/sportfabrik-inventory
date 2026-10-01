"""Operations-ID aus dem Header `X-Operation-Id` (Paket 2, 01.10.2026).

Optional: ohne Header gilt die Anfrage wie bisher. Mit Header schützt sie vor
doppelter Buchung bei Wiederholung (app/services/operation.py)."""

from fastapi import Depends, HTTPException, Request

from ..core.i18n import translate
from ..services.operation import gueltige_id
from .auth import get_language


def operation_id_aus_header(request: Request, language: str = Depends(get_language)) -> str | None:
    wert = request.headers.get("x-operation-id")
    if wert is None:
        return None
    if not gueltige_id(wert):
        raise HTTPException(422, translate("errors.operation.invalid", language))
    return wert
