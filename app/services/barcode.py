"""EAN-Barcode als Strichmuster (Phase B, Teilaufgabe B7).

Nur die Umrechnung Nummer → Striche; gezeichnet wird in
`app/services/etikett.py`. Bewusst ohne zusätzliche Bibliothek: die
Kodierung ist ein paar Tabellen gross, und jede weitere Abhängigkeit müsste
auf dem Server im Laden mitinstalliert und gepflegt werden.

Unterstützt EAN-13, EAN-8 und UPC-A (zwölfstellig, wird als EAN-13 mit
führender 0 gedruckt - so macht es jede Kasse). Eine EAN-14 (Umkarton) ist
kein EAN-Code, sondern ITF-14, und wird deshalb nicht gezeichnet.
"""

from .ean import pruefziffer_stimmt

# Linke Hälfte, ungerade Parität (A) …
L_CODES = {
    "0": "0001101", "1": "0011001", "2": "0010011", "3": "0111101", "4": "0100011",
    "5": "0110001", "6": "0101111", "7": "0111011", "8": "0110111", "9": "0001011",
}
# … rechte Hälfte (C): das Gegenteil von A …
R_CODES = {ziffer: "".join("1" if z == "0" else "0" for z in muster)
           for ziffer, muster in L_CODES.items()}
# … und die gerade Parität (B): C rückwärts gelesen.
G_CODES = {ziffer: muster[::-1] for ziffer, muster in R_CODES.items()}

# Die erste Ziffer einer EAN-13 wird nicht gedruckt, sondern über das
# Paritätsmuster der linken sechs Ziffern kodiert.
PARITAET = {
    "0": "AAAAAA", "1": "AABABB", "2": "AABBAB", "3": "AABBBA", "4": "ABAABB",
    "5": "ABBAAB", "6": "ABBBAA", "7": "ABABAB", "8": "ABABBA", "9": "ABBABA",
}

RAND = "101"        # Start- und Endzeichen
MITTE = "01010"     # Trennzeichen in der Mitte

# Ruhezone links/rechts in Modulen - ohne sie liest kein Scanner zuverlässig.
RUHEZONE_LINKS = 11
RUHEZONE_RECHTS = 7


class BarcodeNichtDruckbar(ValueError):
    """Diese Nummer lässt sich nicht als EAN-Strichcode drucken."""


def _ean13(ean: str) -> str:
    muster = [RAND]
    for stelle, ziffer in enumerate(ean[1:7]):
        tabelle = L_CODES if PARITAET[ean[0]][stelle] == "A" else G_CODES
        muster.append(tabelle[ziffer])
    muster.append(MITTE)
    muster.extend(R_CODES[ziffer] for ziffer in ean[7:])
    muster.append(RAND)
    return "".join(muster)


def _ean8(ean: str) -> str:
    muster = [RAND]
    muster.extend(L_CODES[ziffer] for ziffer in ean[:4])
    muster.append(MITTE)
    muster.extend(R_CODES[ziffer] for ziffer in ean[4:])
    muster.append(RAND)
    return "".join(muster)


def strichmuster(code: str | None) -> str:
    """Strichmuster als Folge von `1` (Strich) und `0` (Lücke), ohne Ruhezone.

    Wirft `BarcodeNichtDruckbar`, wenn die Nummer keine druckbare EAN ist -
    die Etikettenseite entscheidet dann, dass sie nur die Ziffern druckt.
    """
    code = (code or "").strip()
    if not code.isdigit():
        raise BarcodeNichtDruckbar("Nur Ziffern")
    if len(code) == 12:
        code = "0" + code  # UPC-A ist eine EAN-13 mit führender Null
    if len(code) not in (8, 13):
        raise BarcodeNichtDruckbar(f"Länge {len(code)} ist kein EAN-Strichcode")
    if not pruefziffer_stimmt(code):
        raise BarcodeNichtDruckbar("Prüfziffer stimmt nicht")
    return _ean13(code) if len(code) == 13 else _ean8(code)


def druckbare_nummer(code: str | None) -> str | None:
    """Die Nummer so, wie sie unter dem Strichcode steht (UPC-A als EAN-13),
    oder `None`, wenn sich kein Strichcode drucken lässt."""
    try:
        strichmuster(code)
    except BarcodeNichtDruckbar:
        return None
    code = code.strip()
    return "0" + code if len(code) == 12 else code
