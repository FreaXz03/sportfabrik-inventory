"""Testweite Vorbereitung: SESSION_SECRET muss gesetzt sein, bevor irgendein
Testmodul app.routers.catalog/app.routers.history/app.routers.dashboard/
app.routers.preview importiert - diese importieren app.routers.auth, das ohne
SESSION_SECRET beim Import fehlschlägt."""
import os

os.environ.setdefault("SESSION_SECRET", "test-secret-nicht-fuer-produktion")
