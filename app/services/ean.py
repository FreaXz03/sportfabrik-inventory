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
from ..core.models import Variante, VarianteEan
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
        _pruefe_frei(session, neue_ean, variante.id, language)
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


def _pruefe_frei(session, ean: str, varianten_id: int, language: str) -> None:
    """Die EAN darf an keiner anderen Variante hängen - weder als Hauptnummer
    noch als weitere EAN (Punkt 8) - und nicht schon an dieser."""
    belegt = session.scalar(
        select(Variante.id).where(Variante.ean == ean, Variante.id != varianten_id)
    ) or session.scalar(select(VarianteEan.varianten_id).where(VarianteEan.ean == ean))
    if belegt:
        raise EanError(translate("errors.ean.taken", language, ean=ean))


def fuege_ean_hinzu(
    varianten_id: int,
    session_factory,
    *,
    ean: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Einer Variante später eine weitere EAN nachtragen (Punkt 8, 2026-10-01).

    Eine Ergänzung, kein Ersatz: die vorhandene Hauptnummer (Etikett) bleibt,
    die neue führt zur selben Variante - z. B. die Original-EAN neben der
    internen, die bereits auf der Ware klebt. Hat die Variante noch gar keine
    EAN, wird die neue zur Hauptnummer (wie `setze_ean`). Prüfziffer und
    Eindeutigkeit wie dort; die interne Markierung (Regel 5) hängt an der EAN.
    """
    with session_factory() as session, session.begin():
        if session.bind.dialect.name == "postgresql":
            session.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})"))
        variante = session.get(Variante, varianten_id)
        if variante is None:
            raise EanNichtGefunden(
                translate("errors.ean.variante_not_found", language, id=varianten_id)
            )
        neue_ean = pruefe_nachgetragene_ean(ean, language)
        intern = ist_intern(neue_ean)
        if variante.ean == neue_ean:
            raise EanError(translate("errors.ean.taken", language, ean=neue_ean))
        _pruefe_frei(session, neue_ean, variante.id, language)
        if variante.ean is None:
            variante.ean = neue_ean
            variante.ean_intern = intern
        else:
            session.add(VarianteEan(varianten_id=variante.id, ean=neue_ean, ean_intern=intern))
        try:
            session.flush()
        except IntegrityError as exc:
            raise EanError(translate("errors.ean.taken", language, ean=neue_ean)) from exc
        return {"varianten_id": variante.id, "ean": neue_ean, "ean_intern": intern}


def generate_receipt_eans(receipt_id, quantities, session_factory, allowed_locations, language="de"):
    """Assign missing identifiers atomically, without receiving any goods."""
    from decimal import InvalidOperation
    from ..core.models import Wareneingang, WareneingangPosition
    from .wareneingang import _menge, AnkunftRejected
    from .receipt_ean import missing_receipt_eans

    with session_factory() as session, session.begin():
        if session.bind.dialect.name == "postgresql":
            session.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})"))
        receipt = session.get(Wareneingang, receipt_id)
        if receipt is None or receipt.status != "erwartet" or receipt.herkunft_lagerort_id is not None:
            raise EanError(translate("errors.receipt.bulk_unavailable", language))
        if receipt.lagerort_id not in allowed_locations:
            raise PermissionError(translate("errors.receipt.bulk_forbidden", language))
        positions = {str(p.id): p for p in session.scalars(select(WareneingangPosition).where(
            WareneingangPosition.wareneingang_id == receipt_id, WareneingangPosition.ersetzt_durch_abgleich_id.is_(None)))}
        selected = set()
        for key, value in quantities.items():
            if key not in positions:
                raise EanError(translate("errors.wareneingang.unknown_position", language))
            try:
                amount = _menge(value, language)
                if not amount.is_finite():
                    raise InvalidOperation
            except (AnkunftRejected, InvalidOperation, ValueError) as exc:
                raise EanError(translate("errors.wareneingang.invalid_quantity", language)) from exc
            if amount > 0:
                selected.add(positions[key].varianten_id)
        variants = list(session.scalars(select(Variante).where(Variante.id.in_(selected)).order_by(Variante.id)))
        missing = missing_receipt_eans(session, variants, language)
        missing_ids = {row["varianten_id"] for row in missing}
        generated = []
        for variant in variants:
            if variant.id not in missing_ids:
                continue
            # An existing malformed identifier needs manual correction, never replacement.
            if variant.ean:
                raise EanError(translate("errors.ean.already_set", language, ean=variant.ean))
            new_ean = interne_ean(variant.id)
            _pruefe_frei(session, new_ean, variant.id, language)
            variant.ean, variant.ean_intern = new_ean, True
            generated.append({"varianten_id": variant.id, "ean": new_ean})
        session.flush()
        if missing_receipt_eans(session, variants, language):
            raise EanError(translate("errors.receipt.bulk_unavailable", language))
        return {"generated": len(generated), "identifiers": generated}


def remove_receipt_eans(receipt_id, identifiers, session_factory, allowed_locations, language="de"):
    """Undo generated primary labels on unused variants, with stale-value protection."""
    from ..core.models import Lagerbewegung, Wareneingang, WareneingangPosition

    with session_factory() as session, session.begin():
        if session.bind.dialect.name == "postgresql":
            session.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})"))
        receipt = session.get(Wareneingang, receipt_id)
        if receipt is None or receipt.status != "erwartet" or receipt.herkunft_lagerort_id is not None:
            raise EanError(translate("errors.receipt.bulk_unavailable", language))
        if receipt.lagerort_id not in allowed_locations:
            raise PermissionError(translate("errors.receipt.bulk_forbidden", language))
        variants = {str(v.id): v for v in session.scalars(select(Variante).join(
            WareneingangPosition, WareneingangPosition.varianten_id == Variante.id
        ).where(WareneingangPosition.wareneingang_id == receipt_id, WareneingangPosition.ersetzt_durch_abgleich_id.is_(None))).unique()}
        removed = 0
        for key, expected in identifiers.items():
            variant = variants.get(key)
            if variant is None:
                raise EanError(translate("errors.wareneingang.unknown_position", language))
            if expected != interne_ean(variant.id):
                raise EanError(translate("errors.receipt.remove_internal_only", language))
            if variant.ean is None:
                continue  # A retry must not remove a subsequently added original EAN.
            if variant.ean != expected or not variant.ean_intern:
                raise EanError(translate("errors.receipt.remove_internal_only", language))
            if session.scalar(select(Lagerbewegung.id).where(
                Lagerbewegung.varianten_id == variant.id).limit(1)) is not None:
                raise EanError(translate("errors.receipt.remove_used", language))
            variant.ean, variant.ean_intern = None, False
            removed += 1
        session.flush()
        return {"removed": removed}
