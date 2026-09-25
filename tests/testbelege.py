"""Selbst gebaute Test-Belege.

Echte Lieferantenbelege gehören nie ins Repo (öffentlich, Regel 1). Die Tests
bauen ihre PDFs darum selbst mit PyMuPDF - im Layout von INTERSPORT, so wie es
der Parser in app/services/parsers/intersport.py erwartet.
"""

import hashlib

import pymupdf

# Spalten-x-Positionen der Positionstabelle. Weit genug auseinander, dass keine
# Spalte in die nächste läuft (der Parser ordnet jedes Wort über seine linke
# Kante einer Spalte zu).
COLUMNS = [
    ("Marke", 30),
    ("FEDAS", 120),
    ("Lief.", 210),
    ("Art.", 300),
    ("Art.", 390),
    ("EAN", 470),
    ("Bezeichnung", 570),
    ("Menge", 680),
    ("Einheit", 740),
    ("UVP", 820),
    ("Preis", 890),
]
# Lief. und die erste Art.-Spalte gehören beim Auslesen zusammen
# (Lieferanten-Artikelnummer), darum hat eine Position eine Spalte weniger.
POSITION_COLUMNS = [x for _, x in COLUMNS if x != 300]

# Marke, FEDAS, Lief.-Art., Art., EAN, Bezeichnung, Menge, Einheit, UVP, Preis.
# FEDAS 224100 = Textil × Tennis, 324100 = Schuhe × Tennis (app/core/fedas.py).
POSITIONEN = [
    ["Nike", "224100", "A1", "9988770010", "4006632041234", "Poloshirt", "5", "Stk", "49.90", "30.00"],
    ["Nike", "224100", "A1", "9988770011", "4006632041241", "Poloshirt", "3", "Stk", "49.90", "30.00"],
    ["Nike", "324100", "B2", "9988770012", "4006632041258", "Laufschuh", "2", "Stk", "129.00", "80.00"],
]

LIEFERADRESSE_CONTHEY = [
    [(30, "Rechnungsadresse: Sport Fabrik AG, Industriestrasse 21, 8604 Volketswil")],
    [(30, "Lieferadresse: Sport Fabrik AG, Route Cantonale 7, 1964 Conthey")],
]


def kopf(nummer="9001759392", datum="05.08.2026", belegdatum="04.08.2026"):
    return [
        [(30, "INTERSPORT"), (200, "Schweiz"), (300, "AG")],
        [(30, "Rechnung"), (130, "Nr."), (200, nummer)],
        [(30, "Rechnungsdatum"), (200, datum)],
        [(30, "Belegdatum"), (200, belegdatum)],
    ]


def text_pdf(*lines_of_text: str) -> bytes:
    """Einseitige PDF mit Textebene - eine Zeile je Argument."""
    with pymupdf.open() as document:
        page = document.new_page()
        for index, text in enumerate(lines_of_text):
            page.insert_text((30, 40 + index * 20), text)
        return document.tobytes()


def rechnung_pdf(*, header_lines=None, rows=POSITIONEN) -> bytes:
    """Einseitige PDF im INTERSPORT-Layout: Kopfzeilen, darunter die
    Positionstabelle mit Kopfzeile und einer Zeile je Eintrag in `rows`."""
    header_lines = kopf() if header_lines is None else header_lines
    with pymupdf.open() as document:
        page = document.new_page(width=1000, height=800)
        for index, line in enumerate(header_lines):
            for x, text in line:
                page.insert_text((x, 40 + index * 20), text)
        for label, x in COLUMNS:
            page.insert_text((x, 200), label)
        for index, row in enumerate(rows):
            for x, value in zip(POSITION_COLUMNS, row):
                if value:
                    page.insert_text((x, 240 + index * 20), value)
        return document.tobytes()


def hochladen(client, pdf, name="beleg.pdf"):
    return client.post("/upload-preview", files={"file": (name, pdf, "application/pdf")})


def importieren(client, pdf, name="beleg.pdf", **felder):
    daten = {"expected_hash": hashlib.sha256(pdf).hexdigest(), "confirmed": "true", **felder}
    return client.post(
        "/import-invoice", files={"file": (name, pdf, "application/pdf")}, data=daten
    )
