import pymupdf
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .dashboard import router as dashboard_router

from fastapi import FastAPI, HTTPException, UploadFile
from sqlalchemy import text

from .database import engine
from .models import Base
from .preview import router as preview_router
from .catalog import router as catalog_router
from .history import router as history_router


Base.metadata.create_all(bind=engine)

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


@app.post("/upload-test")
async def upload_test(file: UploadFile):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Nur PDF-Dateien erlaubt."
        )

    pdf_data = await file.read()

    document = pymupdf.open(
        stream=pdf_data,
        filetype="pdf"
    )

    first_page_text = document[0].get_text()

    return {
        "filename": file.filename,
        "pages": len(document),
        "text_preview": first_page_text[:3000]
    }
