"""Parser-Registry: erkennt Lieferant und Layout eines hochgeladenen Dokuments
und wählt das zuständige Modul (Phase B, „Lieferanten-Erkennung").

Jedes Lieferanten-Layout liegt als eigenes Modul in diesem Paket und erfüllt
die in `intersport.py` beschriebene Schnittstelle. Neu dazu kommt ein Layout
durch genau zwei Schritte: Modul anlegen und in `PARSERS` eintragen (siehe
Roadmap Phase E). Alles läuft lokal auf dem eigenen Server, ohne KI und ohne
externe Dienste (Regel 1).

Ablauf:

1. `read_document()` liest die PDF einmal ein (mit OCR-Rückfall je Seite).
2. Jedes registrierte Modul bewertet das Dokument (`detect()`); das Modul mit
   der höchsten Punktzahl gewinnt.
3. Passt kein Modul, endet der Upload mit `UnknownLayoutError` - ein Layout,
   das das System noch nie gesehen hat, lässt sich ohne KI nicht automatisch
   lesen (projekt-kontext.md Abschnitt 6, Punkt 1).
"""

from . import intersport
from ...core.lieferanten import LIEFERANTEN_SEED
from .base import Document, DocumentParseError, decimal_value, read_document
from ..lieferadresse import erkenne_lagerort
from ...core.i18n import DEFAULT_LANGUAGE, translate

# Reihenfolge ohne Bedeutung - es gewinnt die höchste Punktzahl aus detect().
PARSERS = (intersport,)


class UnknownLayoutError(DocumentParseError):
    """Kein registriertes Layout passt (oder mehrere passen gleich gut)."""


def detect_parser(document: Document, language: str = DEFAULT_LANGUAGE):
    """Das zuständige Parser-Modul, oder `UnknownLayoutError`."""
    ranked = sorted(
        (
            (score, parser)
            for score, parser in ((p.detect(document), p) for p in PARSERS)
            if score is not None
        ),
        key=lambda entry: -entry[0],
    )
    if not ranked:
        # Bei einem Scan ist die häufigste Ursache nicht ein neues Layout,
        # sondern eine schlecht gelesene Seite - darum derselbe Hinweis wie
        # bei den übrigen OCR-Meldungen.
        hint = (
            translate("errors.parser.hint_ocr", language) if document.ocr_used else ""
        )
        raise UnknownLayoutError(
            translate("errors.parser.unknown_layout", language, hint=hint)
        )
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        raise UnknownLayoutError(
            translate(
                "errors.parser.ambiguous_layout",
                language,
                suppliers=", ".join(
                    parser.LIEFERANT_NAME
                    for score, parser in ranked
                    if score == ranked[0][0]
                ),
            )
        )
    return ranked[0][1]


def parse_with_parser(
    parser, document: Document, language: str = DEFAULT_LANGUAGE, lagerorte=()
) -> dict:
    """Positionen des erkannten Layouts, ergänzt um Lieferant und Parser-Key
    (`lieferanten.parser_key`, den der Import zum Nachschlagen braucht).

    Sind `lagerorte` (Adressdaten, siehe `app/services/lagerorte.py`)
    mitgegeben, kommt zusätzlich der aus der Lieferadresse erkannte Lagerort
    dazu - als **Vorschlag** (D19), den der Benutzer beim Import ändern kann.
    Die Parser-Module selbst sehen die Lagerorte nicht und bleiben damit frei
    von Datenbankwissen.
    """
    treffer = erkenne_lagerort(document.text, lagerorte)
    parsed = parser.parse(document, language)
    return {
        **parsed,
        "parser_key": parser.KEY,
        "supplier_name": _lieferant_name(parser, parsed.get("lieferant_typ")),
        "lagerort_suggestion": (
            None
            if treffer is None
            else {
                "id": treffer.lagerort.id,
                "code": treffer.lagerort.code,
                "name": treffer.lagerort.name,
                "from_delivery_address": treffer.aus_lieferadresse,
                "matched": list(treffer.merkmale),
            }
        ),
    }


def _lieferant_name(parser, lieferant_typ: str | None) -> str:
    """Anzeigename: der Parser-Lieferant, ausser das Dokument gehört zu einer
    anderen Lieferantengruppe (z. B. ECOM-Retoure im INTERSPORT-Layout)."""
    if lieferant_typ:
        for eintrag in LIEFERANTEN_SEED:
            if eintrag["typ"] == lieferant_typ:
                return eintrag["name"]
    return parser.LIEFERANT_NAME


def read_and_detect(pdf_data: bytes, language: str = DEFAULT_LANGUAGE):
    """(Dokument, Parser-Modul) - ein Lese-/OCR-Durchgang für alles Weitere."""
    document = read_document(pdf_data, language)
    return document, detect_parser(document, language)


def parse_document(
    pdf_data: bytes, language: str = DEFAULT_LANGUAGE, lagerorte=()
) -> dict:
    """Dokument lesen, Layout erkennen und Positionen auslesen (Vorschau)."""
    document, parser = read_and_detect(pdf_data, language)
    return parse_with_parser(parser, document, language, lagerorte)


__all__ = [
    "Document",
    "DocumentParseError",
    "PARSERS",
    "UnknownLayoutError",
    "decimal_value",
    "detect_parser",
    "parse_document",
    "parse_with_parser",
    "read_and_detect",
    "read_document",
]
