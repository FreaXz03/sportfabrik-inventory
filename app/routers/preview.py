from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
import hashlib
import json
from ..services.corrections import apply_corrections, CorrectionError
from starlette.concurrency import run_in_threadpool
from .auth import get_language, require_active_lagerort, require_chef_api, require_chef_page
from ..core.i18n import translate
from ..core.models import Lagerort
from ..services.parsers import DocumentParseError, parse_document
from pathlib import Path
from fastapi.responses import FileResponse

router = APIRouter()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get("/preview", include_in_schema=False)
def preview_page(user=Depends(require_chef_page)):
    return FileResponse(
        Path(__file__).resolve().parents[1] / "templates" / "preview.html"
    )


@router.post("/upload-preview")
async def upload_preview(
    file: UploadFile,
    user=Depends(require_chef_api),
    language: str = Depends(get_language),
):
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, translate("errors.preview.file_too_large", language))
        try:
            result = await run_in_threadpool(parse_document, data, language)
        except DocumentParseError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "filename": file.filename,
            "file_hash": hashlib.sha256(data).hexdigest(),
            **result,
        }
    finally:
        await file.close()


@router.post("/import-invoice")
async def confirm_import(
    file: UploadFile,
    expected_hash: str = Form(...),
    confirmed: bool = Form(False),
    corrections: str = Form("{}", max_length=500000),
    user=Depends(require_chef_api),
    lagerort: Lagerort = Depends(require_active_lagerort),
    language: str = Depends(get_language),
):
    try:
        if not confirmed:
            raise HTTPException(
                400, translate("errors.preview.confirm_required", language)
            )
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, translate("errors.preview.file_too_large", language))
        from ..core.database import SessionLocal
        from ..services.importer import import_invoice, ImportRejected
        from sqlalchemy.exc import SQLAlchemyError

        try:
            return await run_in_threadpool(
                import_invoice,
                data,
                file.filename,
                expected_hash,
                SessionLocal,
                lagerort.id,
                {"kassennummer": user.kassennummer, "name": user.name},
                decode_corrections(corrections, language),
                language,
            )
        except (ImportRejected, DocumentParseError) as exc:
            raise HTTPException(409, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                503, translate("errors.preview.import_db_error", language)
            ) from exc
    finally:
        await file.close()


def decode_corrections(value, language: str = "de"):
    try:
        result = json.loads(value)
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except ValueError as exc:
        raise HTTPException(422, translate("errors.preview.invalid_corrections", language)) from exc


@router.post("/validate-preview")
async def validate_preview(
    file: UploadFile,
    expected_hash: str = Form(...),
    corrections: str = Form("{}", max_length=500000),
    user=Depends(require_chef_api),
    language: str = Depends(get_language),
):
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, translate("errors.preview.file_too_large_short", language))
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise HTTPException(409, translate("errors.preview.file_mismatch", language))
        patches = decode_corrections(corrections, language)
        try:
            parsed = await run_in_threadpool(parse_document, data, language)
            result = apply_corrections(parsed, patches, None, language)
        except (DocumentParseError, CorrectionError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"filename": file.filename, "file_hash": expected_hash, **result}
    finally:
        await file.close()


@router.get("/invoice-import-status")
def invoice_import_status(
    file_hash: str,
    invoice_number: str = "",
    user=Depends(require_chef_api),
    language: str = Depends(get_language),
):
    from ..core.database import SessionLocal
    from ..core.models import Dokument
    from sqlalchemy import select, or_
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with SessionLocal() as session:
            invoice = session.scalar(
                select(Dokument).where(
                    or_(
                        Dokument.datei_hash == file_hash,
                        Dokument.dokumentnummer == invoice_number,
                    )
                )
            )
            return {
                "imported": invoice is not None,
                "invoice_id": invoice.id if invoice else None,
            }
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, translate("errors.preview.duplicate_check_unavailable", language)
        ) from exc
