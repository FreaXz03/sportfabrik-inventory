"""Testweite Vorbereitung: SESSION_SECRET muss gesetzt sein, bevor irgendein
Testmodul app.catalog/app.history/app.dashboard/app.preview importiert - diese
importieren app.auth, das ohne SESSION_SECRET beim Import fehlschlägt."""
import os

os.environ.setdefault("SESSION_SECRET", "test-secret-nicht-fuer-produktion")
