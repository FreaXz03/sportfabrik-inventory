from fastapi import APIRouter, HTTPException, UploadFile, Form
import hashlib
from starlette.concurrency import run_in_threadpool
from .parser import InvoiceParseError, parse_invoice
from pathlib import Path
from fastapi.responses import FileResponse

router = APIRouter()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get('/preview', include_in_schema=False)
def preview_page():
    return FileResponse(Path(__file__).parent / 'templates' / 'preview.html')


@router.post('/upload-preview')
async def upload_preview(file: UploadFile):
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
async def confirm_import(file: UploadFile, expected_hash: str = Form(...), confirmed: bool = Form(False)):
    try:
        if not confirmed:
            raise HTTPException(400, 'Bitte zuerst die Vorschau prüfen und den Import bestätigen.')
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'Die PDF-Datei darf höchstens 20 MB gross sein.')
        from .database import SessionLocal
        from .importer import import_invoice, ImportRejected
        from sqlalchemy.exc import SQLAlchemyError
        try:
            return await run_in_threadpool(import_invoice, data, file.filename, expected_hash, SessionLocal)
        except (ImportRejected, InvoiceParseError) as exc:
            raise HTTPException(409, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, 'Datenbankfehler. Es wurde kein Teilimport gespeichert. Bitte erneut versuchen.') from exc
    finally:
        await file.close()
