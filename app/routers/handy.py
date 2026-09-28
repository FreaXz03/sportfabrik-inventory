"""Phone pages under /m (decision 28.09.2026). They use the same APIs as the
desktop pages; app/core/handy.py decides what a phone may reach."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from .auth import require_chef_page, require_login_page

router = APIRouter()

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


@router.get("/m", include_in_schema=False)
def phone_home(user=Depends(require_login_page)):
    return FileResponse(TEMPLATES / "handy.html")


@router.get("/m/suche", include_in_schema=False)
def phone_search(user=Depends(require_login_page)):
    return FileResponse(TEMPLATES / "handy-suche.html")


@router.get("/m/zaehlen", include_in_schema=False)
def phone_count(user=Depends(require_login_page)):
    return FileResponse(TEMPLATES / "handy-zaehlen.html")


@router.get("/m/lieferungen", include_in_schema=False)
def phone_deliveries(user=Depends(require_login_page)):
    return FileResponse(TEMPLATES / "handy-lieferungen.html")


@router.get("/m/umlagern", include_in_schema=False)
def phone_transfer(user=Depends(require_chef_page)):
    return FileResponse(TEMPLATES / "handy-umlagern.html")


@router.get("/m/ausbuchen", include_in_schema=False)
def phone_write_off(user=Depends(require_chef_page)):
    return FileResponse(TEMPLATES / "handy-ausbuchen.html")


@router.get("/m/erfassen", include_in_schema=False)
def phone_manual_entry(user=Depends(require_login_page)):
    return FileResponse(TEMPLATES / "handy-erfassen.html")
