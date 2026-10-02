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


# INTERSPORT-Auftragsbestätigung: gleiche Tabellenfamilie wie die Rechnung,
# aber ohne EAN-Spalte, „EP" statt „Preis" und mit Liefertermin. Farbe und
# Grösse stehen schon in der ersten Bezeichnungszeile und laufen oft um.
AB_COLUMNS = [
    ("Marke", 30), ("FEDAS", 120), ("Lief.", 210), ("Art.", 300), ("Art.", 390),
    ("Bezeichnung", 470), ("Menge", 700), ("Einheit", 760), ("UVP", 830),
    ("EP", 900), ("Rabatt", 960), ("Total", 1020), ("Liefertermin", 1080),
]
AB_POSITIONEN = [
    # (Zeile 1, Zeile 2) je Position: Marke, FEDAS, Lief.-Art., Art., Bezeichnung, Menge, Einheit, UVP, EP
    (
        ["The North", "100898", "NF0A52SA", "186391.084", "BASE CAMP DUFFEL - M (Summit Gold-TNF", "2", "STK", "170.00", "82.95"],
        ["Face", "", "", "", "Black-N)/ONESIZE"],
    ),
    (
        ["The North", "100898", "NF0A52SA", "186391.085", "BASE CAMP DUFFEL - M (Summit Navy-", "1", "STK", "170.00", "82.95"],
        ["Face", "", "", "", "TNF Black-N)/ONESIZE"],
    ),
]


def auftragsbestaetigung_pdf(positionen=AB_POSITIONEN, *, titel=True) -> bytes:
    """Einseitige INTERSPORT-Auftragsbestätigung (Layout wie 900-VA…). Ohne
    `titel` fehlt die Überschrift mit der Nummer (manche PDFs zeichnen sie
    als Grafik statt als Text)."""
    # Lief. und die erste Art.-Spalte gehören zusammen (wie bei der Rechnung).
    x_werte = [30, 120, 210, 390, 470, 700, 760, 830, 900]
    with pymupdf.open() as document:
        page = document.new_page(width=1200, height=800)
        if titel:
            page.insert_text((500, 40), "Auftragsbestätigung 900-VA0212349")
        page.insert_text((30, 60), "Sport-Fabrik AG Auftragsdatum 15.07.2026")
        page.insert_text((30, 80), "Conthey Shop Auftragsnr. 678235_1")
        for label, x in AB_COLUMNS:
            page.insert_text((x, 200), label)
        y = 240
        for zeilen in positionen:
            for zeile in zeilen:
                for x, value in zip(x_werte, zeile):
                    if value:
                        page.insert_text((x, y), value)
                y += 14
            y += 6
        # Formularrest, den INTERSPORT unter die Tabelle druckt.
        page.insert_text((25, y + 20), "False")
        page.insert_text((30, y + 40), "INTERSPORT Schweiz AG, Wölflistrasse 2, 3006 Bern")
        return document.tobytes()


def hochladen(client, pdf, name="beleg.pdf"):
    return client.post("/upload-preview", files={"file": (name, pdf, "application/pdf")})


def importieren(client, pdf, name="beleg.pdf", **felder):
    daten = {"expected_hash": hashlib.sha256(pdf).hexdigest(), "confirmed": "true", **felder}
    return client.post(
        "/import-invoice", files={"file": (name, pdf, "application/pdf")}, data=daten
    )
