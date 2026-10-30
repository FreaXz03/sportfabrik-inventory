"""Manager-only local upload, review and confirmed winter order reconciliation."""
import hashlib
import json
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from ..core.database import get_session
from ..core.i18n import translate
from ..services.lagerorte import list_wareneingang_lagerorte
from ..services.parsers import parse_document, DocumentParseError
from ..services.winter_reconciliation import candidates, snapshot, apply_revision, ReconciliationRejected
from .auth import require_chef_api, require_chef_page, get_language
from .preview import MAX_UPLOAD_BYTES

router=APIRouter()


@router.get('/winter-abgleich',include_in_schema=False)
def page(user=Depends(require_chef_page)):
    return FileResponse(Path(__file__).resolve().parents[1]/'templates'/'winter_reconciliation.html')


@router.get('/api/winter-abgleich')
def list_orders(user=Depends(require_chef_api),session=Depends(get_session)):
    return {'orders':candidates(session,{l.id for l in list_wareneingang_lagerorte(session,user)})}


async def read(file,language):
    data=await file.read(MAX_UPLOAD_BYTES+1)
    if len(data)>MAX_UPLOAD_BYTES:
        raise HTTPException(413,translate('errors.preview.file_too_large',language))
    return data,await run_in_threadpool(parse_document,data,language)


@router.post('/api/winter-abgleich/{receipt_id}/vorschau')
async def preview(receipt_id:int,file:UploadFile=File(...),user=Depends(require_chef_api),
                  session=Depends(get_session),language:str=Depends(get_language)):
    try:
        data,parsed=await read(file,language)
        view=snapshot(session,receipt_id,parsed,{l.id for l in list_wareneingang_lagerorte(session,user)},language)
        return {**view,'file_hash':hashlib.sha256(data).hexdigest()}
    except (DocumentParseError,ReconciliationRejected) as exc:
        raise HTTPException(409,str(exc)) from exc
    finally:
        await file.close()


@router.post('/api/winter-abgleich/{receipt_id}/uebernehmen')
async def apply(receipt_id:int,file:UploadFile=File(...),fingerprint:str=Form(...),selection:str=Form(...,max_length=100000),
                confirmed:bool=Form(False),revise_quantities:bool=Form(False),reason:str=Form('',max_length=500),withdraw:str=Form('[]',max_length=100000),
                user=Depends(require_chef_api),session=Depends(get_session),language:str=Depends(get_language)):
    from ..core.database import SessionLocal
    try:
        if not confirmed:raise ReconciliationRejected(translate('errors.preview.confirm_required',language))
        data,parsed=await read(file,language)
        try:
            selected=json.loads(selection);removed=json.loads(withdraw)
            if not isinstance(removed,list):raise ValueError
        except (TypeError,ValueError) as exc:
            raise ReconciliationRejected(translate('winter.selection_required',language)) from exc
        allowed={l.id for l in list_wareneingang_lagerorte(session,user)}
        return await run_in_threadpool(apply_revision,SessionLocal,receipt_id,parsed,hashlib.sha256(data).hexdigest(),
            file.filename,fingerprint,selected,allowed,{'kassennummer':user.kassennummer,'name':user.name},language,
            revise_quantities,reason.strip(),removed)
    except (DocumentParseError,ReconciliationRejected) as exc:
        raise HTTPException(409,str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503,translate('errors.preview.import_db_error',language)) from exc
    finally:
        await file.close()
