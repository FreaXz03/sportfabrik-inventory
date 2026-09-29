from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from .routers.dashboard import router as dashboard_router

from fastapi import Depends, FastAPI, Request
from sqlalchemy import text

from .routers.auth import (
    SESSION_HTTPS_ONLY,
    SESSION_MAX_AGE,
    SESSION_SECRET,
    phone_gate,
    require_login_page,
)
from .routers.auth import router as auth_router
from .core.database import engine
from .routers.preview import router as preview_router
from .routers.catalog import router as catalog_router
from .routers.history import router as history_router
from .routers.article_details import router as article_details_router
from .routers.wareneingang import router as wareneingang_router
from .routers.erfassung import router as erfassung_router
from .routers.etiketten import router as etiketten_router
from .routers.kategorien import router as kategorien_router
from .routers.ausbuchung import router as ausbuchung_router
from .routers.bestand import router as bestand_router
from .routers.korrektur import router as korrektur_router
from .routers.umlagerung import router as umlagerung_router
from .routers.reduktion import router as reduktion_router
from .routers.statistik import router as statistik_router
from .routers.konten import router as konten_router
from .routers.empfehlung import router as empfehlung_router
from .routers.handy import router as handy_router

# S5 (docs/sicherheit.md): keine API-Doku ohne Login im Betrieb.
app = FastAPI(
    title="Sport-Fabrik Inventory",
    dependencies=[Depends(phone_gate)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# S7: Schutz-Header auf jeder Antwort. Die CSP gilt für HTML-Seiten: nur
# eigene Skripte und Stile (keine Inline-Skripte, Regel 1 ohnehin ohne CDN),
# `data:` nur für die kleinen SVG-Pfeile im CSS, nie in einem Rahmen.
CSP = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)


@app.middleware("http")
async def schutz_header(request: Request, call_next):
    antwort = await call_next(request)
    antwort.headers["X-Frame-Options"] = "DENY"
    antwort.headers["X-Content-Type-Options"] = "nosniff"
    if antwort.headers.get("content-type", "").startswith("text/html"):
        antwort.headers["Content-Security-Policy"] = CSP
    return antwort

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)
app.include_router(auth_router)
app.include_router(preview_router)
app.include_router(catalog_router)
app.include_router(history_router)
app.include_router(article_details_router)
app.include_router(dashboard_router)
app.include_router(wareneingang_router)
app.include_router(bestand_router)
app.include_router(ausbuchung_router)
app.include_router(umlagerung_router)
app.include_router(korrektur_router)
app.include_router(erfassung_router)
app.include_router(etiketten_router)
app.include_router(kategorien_router)
app.include_router(reduktion_router)
app.include_router(statistik_router)
app.include_router(konten_router)
app.include_router(empfehlung_router)
app.include_router(handy_router)
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)


@app.get("/")
def home(user=Depends(require_login_page)):
    return FileResponse(Path(__file__).parent / "templates" / "dashboard.html")


@app.get("/db-test")
def database_test():
    """Health-Check für Docker - ohne Login, deshalb ohne Details (S6)."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()
    return {"ok": True}
