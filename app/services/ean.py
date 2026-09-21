"""EAN prüfen, nachtragen und erzeugen (Phase B, Teilaufgabe B7).

Regel 5 / D10: Die EAN ist optional - viele Lieferanten liefern keine. Damit
ein solcher Artikel an der Kasse trotzdem scannbar wird, erzeugt das System
auf Knopfdruck (D24) eine **interne EAN-13 im GS1-Bereich 20-29** und
markiert sie als intern (`varianten.ean_intern`). Dieser Bereich ist von GS1
für den Hausgebrauch reserviert; die Nummern verlassen das Haus nie und
kollidieren deshalb nicht mit Hersteller-EANs.

Aufbau der internen Nummer: `20` + zehnstellige Varianten-Id + Prüfziffer.
Damit ist sie ohne zusätzlichen Zähler eindeutig, nachvollziehbar (die Id
steht drin) und für dieselbe Variante immer dieselbe.

Die Prüfziffer steht hier auch für Barcodes: das Etikett (siehe
`app/services/etikett.py`) zeichnet nur, was sich wirklich als EAN lesen
lässt.
"""

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import Variante
from .wareneingang import ADVISORY_LOCK_ID

# GS1-Bereich für den Hausgebrauch (D10). Die erste Stelle ist immer 2, die
# zweite wählt den Nummernkreis - wir nutzen 0, also `20…`.
INTERNER_PRAEFIX = "20"

# Länge der internen Nummer ohne Präfix und ohne Prüfziffer.
_STELLEN = 13 - len(INTERNER_PRAEFIX) - 1


class EanError(ValueError):
    """Die EAN ist nicht brauchbar - nichts wurde geändert."""


def pruefziffer(ziffern: str) -> int:
    """Prüfziffer nach GS1 (EAN-8/EAN-13/UPC): von rechts nach links
    abwechselnd ×3 und ×1, dann auf das nächste Vielfache von 10 ergänzen.

    `ziffern` ist die Nummer **ohne** Prüfziffer.
    """
    if not ziffern.isdigit():
        raise EanError("Nur Ziffern erlaubt.")
    summe = 0
    for position, zeichen in enumerate(reversed(ziffern)):
        summe += int(zeichen) * (3 if position % 2 == 0 else 1)
    return (10 - summe % 10) % 10


def pruefziffer_stimmt(ean: str) -> bool:
    """`True`, wenn die letzte Stelle die korrekte Prüfziffer ist. Für
    Längen, die keine GS1-Nummer sind, immer `False`."""
    ean = (ean or "").strip()
    if not ean.isdigit() or len(ean) not in (8, 12, 13, 14):
        return False
    return pruefziffer(ean[:-1]) == int(ean[-1])


def mit_pruefziffer(ziffern: str) -> str:
    return ziffern + str(pruefziffer(ziffern))


def interne_ean(varianten_id: int) -> str:
    """Interne EAN-13 für eine Variante (D10/D24). Deterministisch: dieselbe
    Variante bekommt immer dieselbe Nummer."""
    if varianten_id <= 0 or len(str(varianten_id)) > _STELLEN:
        raise EanError(f"Varianten-Id passt nicht in eine EAN-13: {varianten_id}")
    return mit_pruefziffer(INTERNER_PRAEFIX + str(varianten_id).zfill(_STELLEN))


def ist_intern(ean: str | None) -> bool:
    """Liegt die Nummer im GS1-Bereich für den Hausgebrauch (20-29)? Das sind
    genau die EAN-13, die mit 2 beginnen."""
    ean = (ean or "").strip()
    return len(ean) == 13 and ean.isdigit() and ean.startswith("2")


def pruefe_nachgetragene_ean(ean: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Von Hand nachgetragene EAN prüfen (Format **und** Prüfziffer).

    Beim Import bleibt es bewusst beim Formatcheck: dort steht die Nummer so
    im Lieferantendokument, und eine ungewohnte Hausnummer soll den Import
    nicht sperren (Teilaufgabe B3). Hier tippt oder scannt dagegen jemand
    bewusst eine EAN nach - ein Zahlendreher wäre sonst für immer im
    Artikelstamm.
    """
    ean = (ean or "").strip()
    if not ean:
        raise EanError(translate("errors.ean.missing", language))
    if not ean.isdigit() or len(ean) not in (8, 12, 13, 14):
        raise EanError(translate("errors.ean.format", language))
    if not pruefziffer_stimmt(ean):
        raise EanError(
            translate("errors.ean.check_digit", language, ziffer=pruefziffer(ean[:-1]))
        )
    return ean


# --- EAN an einer Variante setzen -----------------------------------------
#
# Ab hier wird geschrieben; darüber steht reine Rechnerei ohne Datenbank.


class EanNichtGefunden(EanError):
    """Die Variante gibt es nicht."""


def setze_ean(
    varianten_id: int,
    session_factory,
    *,
    ean: str | None = None,
    generieren: bool = False,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """EAN einer Variante nachtragen oder eine interne erzeugen (D24).

    Eine vorhandene EAN wird **nie** überschrieben: der Artikelstamm bleibt
    für immer (Regel 4), und eine einmal gedruckte Nummer klebt auf der Ware.
    """
    with session_factory() as session, session.begin():
        # Dieselbe Sperre wie Import und Erfassung: zwei Arbeitsplätze dürfen
        # nicht gleichzeitig dieselbe EAN vergeben.
        if session.bind.dialect.name == "postgresql":
            session.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})"))
        variante = session.get(Variante, varianten_id)
        if variante is None:
            raise EanNichtGefunden(
                translate("errors.ean.variante_not_found", language, id=varianten_id)
            )
        if variante.ean:
            raise EanError(
                translate("errors.ean.already_set", language, ean=variante.ean)
            )
        if generieren:
            neue_ean = interne_ean(variante.id)
            intern = True
        else:
            neue_ean = pruefe_nachgetragene_ean(ean or "", language)
            intern = ist_intern(neue_ean)
        belegt = session.scalar(
            select(Variante.id).where(
                Variante.ean == neue_ean, Variante.id != variante.id
            )
        )
        if belegt:
            raise EanError(translate("errors.ean.taken", language, ean=neue_ean))
        variante.ean = neue_ean
        variante.ean_intern = intern
        try:
            session.flush()
        except IntegrityError as exc:
            raise EanError(translate("errors.ean.taken", language, ean=neue_ean)) from exc
        return {
            "varianten_id": variante.id,
            "ean": variante.ean,
            "ean_intern": variante.ean_intern,
        }
