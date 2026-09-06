FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/inventory
# tesseract-ocr: OCR-Fallback fuer eingescannte (bildbasierte) Rechnungen ohne Textebene,
# siehe app/services/ocr.py. Sprachpakete (eng: Artikeltexte, deu: Tabellenkopf/Farben)
# und osd (Ausrichtungserkennung fuer schief eingescannte Blaetter) sind eigene Pakete.
RUN apt-get update && apt-get install --no-install-recommends -y \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-osd \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt
RUN useradd --create-home --uid 10001 inventory
COPY --chown=inventory:inventory app ./app
COPY --chown=inventory:inventory migrations ./migrations
COPY --chown=inventory:inventory alembic.ini ./alembic.ini
COPY --chown=inventory:inventory scripts ./scripts
USER inventory
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers"]
