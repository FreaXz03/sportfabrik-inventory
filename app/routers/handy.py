"""Phone pages under /m (decision 28.09.2026). They use the same APIs as the
desktop pages; app/core/handy.py decides what a phone may reach."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from .auth import require_login_page

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
