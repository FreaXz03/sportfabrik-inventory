from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
import hashlib
import json
from ..services.corrections import apply_corrections, CorrectionError
from starlette.concurrency import run_in_threadpool
from .auth import require_chef_api, require_chef_page
from ..services.parser import InvoiceParseError, parse_invoice
from pathlib import Path
from fastapi.responses import FileResponse

router = APIRouter()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get('/preview', include_in_schema=False)
def preview_page(user=Depends(require_chef_page)):
    return FileResponse(Path(__file__).resolve().parents[1] / 'templates' / 'preview.html')


@router.post('/upload-preview')
async def upload_preview(file: UploadFile, user=Depends(require_chef_api)):
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'Die PDF-Datei darf höchstens 20 MB gross sein.')
        try:
            result = await run_in_threadpool(parse_invoice, data)
        except InvoiceParseError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {'filename': file.filename, 'file_hash': hashlib.sha256(data).hexdigest(), **result}
    finally:
        await file.close()


@router.post('/import-invoice')
async def confirm_import(file: UploadFile, expected_hash: str = Form(...), confirmed: bool = Form(False),
                          corrections: str = Form('{}', max_length=500000), user=Depends(require_chef_api)):
    try:
        if not confirmed:
            raise HTTPException(400, 'Bitte zuerst die Vorschau prüfen und den Import bestätigen.')
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'Die PDF-Datei darf höchstens 20 MB gross sein.')
        from ..core.database import SessionLocal
        from ..services.importer import import_invoice, ImportRejected
        from sqlalchemy.exc import SQLAlchemyError
        try:
            return await run_in_threadpool(import_invoice, data, file.filename, expected_hash, SessionLocal,
                {'kassennummer': user.kassennummer, 'name': user.name}, decode_corrections(corrections))
        except (ImportRejected, InvoiceParseError) as exc:
            raise HTTPException(409, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, 'Datenbankfehler. Es wurde kein Teilimport gespeichert. Bitte erneut versuchen.') from exc
    finally:
        await file.close()


def decode_corrections(value):
    try:
        result = json.loads(value)
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except ValueError as exc:
        raise HTTPException(422, 'Ungültige Korrekturdaten.') from exc


@router.post('/validate-preview')
async def validate_preview(file: UploadFile, expected_hash: str = Form(...),
                           corrections: str = Form('{}', max_length=500000), user=Depends(require_chef_api)):
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'PDF zu gross.')
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise HTTPException(409, 'Datei stimmt nicht mit der Vorschau überein.')
        patches = decode_corrections(corrections)
        try:
            parsed = await run_in_threadpool(parse_invoice, data)
            result = apply_corrections(parsed, patches)
        except (InvoiceParseError, CorrectionError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return {'filename':file.filename, 'file_hash':expected_hash, **result}
    finally:
        await file.close()


@router.get('/invoice-import-status')
def invoice_import_status(file_hash: str, invoice_number: str = '', user=Depends(require_chef_api)):
    from ..core.database import SessionLocal
    from ..core.models import Invoice
    from sqlalchemy import select, or_
    from sqlalchemy.exc import SQLAlchemyError
    try:
        with SessionLocal() as session:
            invoice = session.scalar(select(Invoice).where(or_(
                Invoice.file_hash == file_hash, Invoice.invoice_number == invoice_number)))
            return {'imported': invoice is not None,
                    'invoice_id': invoice.id if invoice else None}
    except SQLAlchemyError as exc:
        raise HTTPException(503, 'Duplikatprüfung nicht verfügbar. Bitte erneut versuchen.') from exc
