from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .dashboard import router as dashboard_router

from fastapi import FastAPI
from sqlalchemy import text

from .database import engine
from .preview import router as preview_router
from .catalog import router as catalog_router
from .history import router as history_router


app = FastAPI(
    title="Sport-Fabrik Inventory"
)
app.include_router(preview_router)
app.include_router(catalog_router)
app.include_router(history_router)
app.include_router(dashboard_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / 'templates' / 'dashboard.html')


@app.get("/db-test")
def database_test():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1")
        ).scalar_one()

    return {
        "database": "connected",
        "result": result
    }
