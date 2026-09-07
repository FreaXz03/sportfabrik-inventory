from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from .routers.dashboard import router as dashboard_router

from fastapi import Depends, FastAPI
from sqlalchemy import text

from .routers.auth import SESSION_MAX_AGE, SESSION_SECRET, require_login_page
from .routers.auth import router as auth_router
from .core.database import engine
from .routers.preview import router as preview_router
from .routers.catalog import router as catalog_router
from .routers.history import router as history_router
from .routers.article_details import router as article_details_router

app = FastAPI(title="Sport-Fabrik Inventory")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
)
app.include_router(auth_router)
app.include_router(preview_router)
app.include_router(catalog_router)
app.include_router(history_router)
app.include_router(article_details_router)
app.include_router(dashboard_router)
app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)


@app.get("/")
def home(user=Depends(require_login_page)):
    return FileResponse(Path(__file__).parent / "templates" / "dashboard.html")


@app.get("/db-test")
def database_test():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()

    return {"database": "connected", "result": result}
