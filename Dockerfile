FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/inventory
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
