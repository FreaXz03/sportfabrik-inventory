"""Offene Restmenge einer Lieferung ausdrücklich behandeln (Paket 4b,
05.10.2026).

Bisher blieb ein nicht angekommener Rest einfach offen. Jetzt gibt es drei
ausdrückliche Wege (`lieferung_differenzen`):

* `in_klaerung` - die Fehlmenge wird untersucht. Das darf jede Mitarbeiterin
  der Filiale, die die Ware erwartet; der Rest bleibt offen.
* `verloren` - unterwegs verloren (Entscheid Q8: Filialleiter/Zentrale). Es
  gibt keine Lagerbewegung: die Ware ist beim Versand schon von der Quelle
  abgegangen und taucht dort nicht wieder auf. Das Verlustprotokoll ist die
  Differenz-Zeile.
* `lieferant_storniert` - der Lieferant liefert den Rest nicht
  (Filialleiter/Zentrale; nur bei Lieferantenlieferungen, nicht bei
  Umlagerungen - dort gibt es das Stornieren zur Quelle).

Verloren und storniert zählen nicht mehr als offen. Ist danach nichts mehr
offen, wird die Lieferung `abgeschlossen`. Eine frühere Meldung `in_klaerung`
derselben Position gilt mit der Erklärung als aufgelöst.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import LieferungDifferenz, Wareneingang, WareneingangPosition
from .ausbuchung import sperren, zahl

ARTEN = ("in_klaerung", "verloren", "lieferant_storniert")
ARTEN_SCHLIESSEND = ("verloren", "lieferant_storniert")
NOTIZ_MAX = 200


class DifferenzRejected(ValueError):
    """Die Erklärung ist nicht plausibel - nichts wurde gespeichert."""


class DifferenzForbidden(PermissionError):
    """Keine Berechtigung - nichts wurde gespeichert."""


def geschlossene_menge(session, position_id: int) -> Decimal:
    """Menge, die als verloren oder vom Lieferanten storniert erklärt ist."""
    return Decimal(
        session.scalar(
            select(func.coalesce(func.sum(LieferungDifferenz.menge), 0)).where(
                LieferungDifferenz.wareneingang_position_id == position_id,
                LieferungDifferenz.art.in_(ARTEN_SCHLIESSEND),
            )
        )
        or 0
    )


def offene_menge(session, position: WareneingangPosition) -> Decimal:
    return (
        Decimal(position.menge or 0)
        - Decimal(position.menge_eingetroffen or 0)
        - geschlossene_menge(session, position.id)
    )


def schliesse_wenn_erledigt(session, wareneingang: Wareneingang) -> None:
    """Lieferung `abgeschlossen`, sobald keine Position mehr offen ist und
    mindestens ein Rest ausdrücklich erklärt wurde; sonst unverändert (die
    Ankunftsbestätigung setzt `eingetroffen` selbst)."""
    if wareneingang.status != "erwartet":
        return
    positionen = session.scalars(
        select(WareneingangPosition).where(WareneingangPosition.wareneingang_id == wareneingang.id)
    ).all()
    if any(offene_menge(session, position) > 0 for position in positionen):
        return
    erklaert = any(geschlossene_menge(session, position.id) > 0 for position in positionen)
    wareneingang.status = "abgeschlossen" if erklaert else "eingetroffen"


def differenzen_je_position(session, position_ids: list[int]) -> dict[int, list[dict]]:
    """Differenzen je Position für die Lieferungsliste (neueste zuletzt)."""
    if not position_ids:
        return {}
    ergebnis: dict[int, list[dict]] = {}
    for zeile in session.scalars(
        select(LieferungDifferenz)
        .where(LieferungDifferenz.wareneingang_position_id.in_(position_ids))
        .order_by(LieferungDifferenz.id)
    ):
        ergebnis.setdefault(zeile.wareneingang_position_id, []).append(
            {
                "id": zeile.id,
                "art": zeile.art,
                "menge": zahl(zeile.menge),
                "notiz": zeile.notiz,
                "von": zeile.benutzer_name,
                "zeitpunkt": zeile.zeitpunkt.isoformat(),
                "aufgeloest": zeile.aufgeloest_am is not None,
            }
        )
    return ergebnis


def erklaere(
    session_factory,
    wareneingang_id: int,
    *,
    position_id: int,
    art: str,
    menge,
    notiz: str | None = None,
    darf_verwalten: bool,
    erlaubte_lagerorte: set[int] | None = None,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Einen Rest einer Position erklären. `erlaubte_lagerorte`: Filialen,
    in denen die Person buchen darf; `in_klaerung` verlangt die erwartende
    Filiale, die beiden anderen Arten `darf_verwalten`."""
    if art not in ARTEN:
        raise DifferenzRejected(translate("errors.differenz.unknown_kind", language))
    try:
        menge = Decimal(str(menge))
    except InvalidOperation:
        raise DifferenzRejected(translate("errors.differenz.quantity_invalid", language)) from None
    notiz = (notiz or "").strip() or None
    if notiz and len(notiz) > NOTIZ_MAX:
        raise DifferenzRejected(translate("errors.ausbuchung.text_too_long", language, max=NOTIZ_MAX))
    jetzt = datetime.now(timezone.utc)
    with session_factory() as session, session.begin():
        sperren(session)
        wareneingang = session.get(Wareneingang, wareneingang_id)
        position = session.get(WareneingangPosition, position_id)
        if wareneingang is None or position is None or position.wareneingang_id != wareneingang.id:
            raise DifferenzRejected(translate("errors.differenz.not_found", language))
        if art in ARTEN_SCHLIESSEND and not darf_verwalten:
            raise DifferenzForbidden(translate("errors.differenz.reserved", language))
        if not darf_verwalten and (
            erlaubte_lagerorte is None or wareneingang.lagerort_id not in erlaubte_lagerorte
        ):
            raise DifferenzForbidden(translate("errors.auth.no_lagerort_access", language))
        if wareneingang.status != "erwartet":
            raise DifferenzRejected(translate("errors.differenz.not_open", language))
        if art == "lieferant_storniert" and wareneingang.herkunft_lagerort_id is not None:
            raise DifferenzRejected(translate("errors.differenz.not_for_transfer", language))
        offen = offene_menge(session, position)
        if menge <= 0 or menge != menge.to_integral_value() or menge > offen:
            raise DifferenzRejected(
                translate("errors.differenz.quantity_range", language, offen=zahl(offen))
            )
        session.add(
            LieferungDifferenz(
                wareneingang_position_id=position.id,
                art=art,
                menge=menge,
                notiz=notiz,
                benutzer_kassennummer=(benutzer or {}).get("kassennummer"),
                benutzer_name=(benutzer or {}).get("name"),
                zeitpunkt=jetzt,
            )
        )
        session.flush()
        if art in ARTEN_SCHLIESSEND:
            # Eine frühere Meldung „in Klärung" ist mit der Erklärung erledigt.
            for frueher in session.scalars(
                select(LieferungDifferenz).where(
                    LieferungDifferenz.wareneingang_position_id == position.id,
                    LieferungDifferenz.art == "in_klaerung",
                    LieferungDifferenz.aufgeloest_am.is_(None),
                )
            ):
                frueher.aufgeloest_am = jetzt
            schliesse_wenn_erledigt(session, wareneingang)
        session.flush()
        return {
            "wareneingang_id": wareneingang.id,
            "position_id": position.id,
            "status": wareneingang.status,
            "menge_offen": zahl(offene_menge(session, position)),
        }
