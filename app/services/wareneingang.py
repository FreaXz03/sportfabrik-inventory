"""Erwartete Wareneingänge und die Bestätigung ihrer Ankunft (Phase B,
Teilaufgabe B5).

Regel 3 / D6: Eine Auftragsbestätigung oder Bestellung kündigt Ware nur an -
Bestand entsteht erst, wenn sie da ist. Der Import legt für solche Dokumente
einen Wareneingang mit Status `erwartet` an (ohne Lagerbewegung, ohne Bestand,
ohne Eingangsdatum); hier wird daraus bei Ankunft ein gebuchter Zugang.

Die Regeln dazu:

* **Mengenkontrolle** (D22): Beim Bestätigen wird je Position eingetragen, wie
  viel tatsächlich angekommen ist. Kommt weniger, bleibt die Restmenge offen
  und der Wareneingang weiter `erwartet` - so ist fehlende Ware sichtbar.
  Nachlieferungen werden einfach ein weiteres Mal bestätigt.
* **Rechte** (D21): Ankunft bestätigen ist Lagerarbeit, das dürfen auch
  Mitarbeiter - anders als das Hochladen von Dokumenten (Regel 9).
* **Eingangsdatum** (Regel 6 / D13): Wird beim ersten Zugang gesetzt, auf
  Wunsch rückwirkend. Ware in einem Lager ohne Verkauf (GEWA) bekommt keines -
  die Reduktionsuhr startet erst in der Filiale.
* **Bestand** (Regel 2): nie direkt schreiben, sondern als Lagerbewegung
  buchen - dieselbe Funktion wie beim Import (`buche_zugang`).
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select, text

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import (
    Artikel,
    Bestand,
    Dokument,
    Lagerbewegung,
    Lagerort,
    Lieferant,
    Variante,
    Wareneingang,
    WareneingangPosition,
)

# Dieselbe Sperre wie der Import: Zugänge und Bestand dürfen sich zwischen
# mehreren Arbeitsplätzen nicht überholen (siehe app/services/importer.py).
ADVISORY_LOCK_ID = 73421061

MAX_MENGE = Decimal("100000000")


class AnkunftRejected(ValueError):
    """Die Bestätigung ist nicht plausibel - nichts wurde gebucht."""


def buche_zugang(
    session,
    *,
    lagerort_id: int,
    varianten_id: int,
    position_id: int | None,
    menge: Decimal,
    eingangsdatum: date | None,
    benutzer: dict | None,
    zeitpunkt: datetime,
    grund: str | None = None,
) -> None:
    """Einen Zugang buchen: Lagerbewegung schreiben und Bestand nachführen
    (Regel 2). Wird vom Import und von der Ankunftsbestätigung gleichermassen
    benutzt, damit beide Wege garantiert dasselbe tun."""
    session.add(
        Lagerbewegung(
            lagerort_id=lagerort_id,
            varianten_id=varianten_id,
            typ="zugang",
            menge=menge,
            grund=grund,
            wareneingang_position_id=position_id,
            benutzer_kassennummer=(benutzer or {}).get("kassennummer"),
            benutzer_name=(benutzer or {}).get("name"),
            zeitpunkt=zeitpunkt,
        )
    )
    bestand = session.get(Bestand, (varianten_id, lagerort_id))
    if bestand is None:
        session.add(
            Bestand(
                varianten_id=varianten_id,
                lagerort_id=lagerort_id,
                menge=menge,
                aeltestes_eingangsdatum=eingangsdatum,
            )
        )
        return
    bestand.menge += menge
    if eingangsdatum and (
        bestand.aeltestes_eingangsdatum is None
        or eingangsdatum < bestand.aeltestes_eingangsdatum
    ):
        bestand.aeltestes_eingangsdatum = eingangsdatum


def _menge(wert, language: str) -> Decimal:
    try:
        menge = Decimal(str(wert))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AnkunftRejected(
            translate("errors.wareneingang.invalid_quantity", language)
        ) from exc
    if menge != menge.quantize(Decimal(".01")) or abs(menge) >= MAX_MENGE:
        raise AnkunftRejected(translate("errors.wareneingang.invalid_quantity", language))
    if menge < 0:
        raise AnkunftRejected(translate("errors.wareneingang.negative_quantity", language))
    return menge


def _zahl(wert) -> str:
    """Mengen immer gleich formatiert (zwei Nachkommastellen) - egal, ob der
    Wert gerade aus der Datenbank kommt oder frisch gerechnet ist."""
    return str(Decimal(wert or 0).quantize(Decimal("0.01")))


def liste_erwartete(session, lagerort_id: int | None = None) -> list[dict]:
    """Offene (erwartete) Wareneingänge samt Positionen - für die Filiale, die
    die Ware erwartet. Ohne `lagerort_id` filialübergreifend (Admin)."""
    abfrage = (
        select(Wareneingang, Dokument, Lagerort, Lieferant)
        .join(Dokument, Dokument.id == Wareneingang.dokument_id)
        .join(Lagerort, Lagerort.id == Wareneingang.lagerort_id)
        .join(Lieferant, Lieferant.id == Dokument.lieferant_id, isouter=True)
        .where(Wareneingang.status == "erwartet")
        .order_by(Dokument.dokumentdatum, Wareneingang.id)
    )
    if lagerort_id is not None:
        abfrage = abfrage.where(Wareneingang.lagerort_id == lagerort_id)

    ergebnis = []
    for wareneingang, dokument, lagerort, lieferant in session.execute(abfrage).all():
        positionen = session.execute(
            select(WareneingangPosition, Variante, Artikel)
            .join(Variante, Variante.id == WareneingangPosition.varianten_id)
            .join(Artikel, Artikel.id == Variante.artikel_id)
            .where(WareneingangPosition.wareneingang_id == wareneingang.id)
            .order_by(WareneingangPosition.id)
        ).all()
        ergebnis.append(
            {
                "id": wareneingang.id,
                "dokument": {
                    "id": dokument.id,
                    "typ": dokument.typ,
                    "nummer": dokument.dokumentnummer,
                    "datum": dokument.dokumentdatum.isoformat()
                    if dokument.dokumentdatum
                    else None,
                    "lieferant": lieferant.name if lieferant else None,
                },
                "lagerort": {
                    "id": lagerort.id,
                    "code": lagerort.code,
                    "name": lagerort.name,
                    # Regel 6/D13: ein Lager ohne Verkauf bekommt kein
                    # Eingangsdatum - die Oberfläche blendet das Feld aus.
                    "verkauf": bool(lagerort.verkauf),
                },
                "positionen": [
                    {
                        "id": position.id,
                        "marke": artikel.marke,
                        "bezeichnung": artikel.bezeichnung,
                        "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
                        "farbe": variante.farbe,
                        "groesse": variante.groesse,
                        "ean": variante.ean,
                        "einheit": position.einheit,
                        "menge_erwartet": _zahl(position.menge),
                        "menge_eingetroffen": _zahl(position.menge_eingetroffen),
                        "menge_offen": _zahl(
                            (position.menge or 0) - (position.menge_eingetroffen or 0)
                        ),
                    }
                    for position, variante, artikel in positionen
                ],
            }
        )
    return ergebnis


def bestaetige_ankunft(
    wareneingang_id: int,
    mengen: dict,
    session_factory,
    benutzer: dict | None = None,
    eingangsdatum: date | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Ankunft (ganz oder teilweise) bestätigen und den Zugang buchen.

    `mengen` bildet Positions-Id → jetzt angekommene Menge ab. Nicht genannte
    Positionen bleiben unangetastet. Der Wareneingang gilt erst als
    `eingetroffen`, wenn keine Position mehr offen ist (D22).
    """
    with session_factory() as session, session.begin():
        if session.bind.dialect.name == "postgresql":
            session.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})"))
        wareneingang = session.get(Wareneingang, wareneingang_id)
        if wareneingang is None:
            raise AnkunftRejected(
                translate("errors.wareneingang.not_found", language, id=wareneingang_id)
            )
        if wareneingang.status != "erwartet":
            raise AnkunftRejected(
                translate("errors.wareneingang.already_arrived", language)
            )

        positionen = {
            position.id: position
            for position in session.scalars(
                select(WareneingangPosition).where(
                    WareneingangPosition.wareneingang_id == wareneingang.id
                )
            ).all()
        }
        gebucht = {}
        for position_id, wert in (mengen or {}).items():
            try:
                position_id = int(position_id)
            except (TypeError, ValueError) as exc:
                raise AnkunftRejected(
                    translate("errors.wareneingang.unknown_position", language)
                ) from exc
            if position_id not in positionen:
                raise AnkunftRejected(
                    translate("errors.wareneingang.unknown_position", language)
                )
            menge = _menge(wert, language)
            if menge:
                gebucht[position_id] = menge
        if not gebucht:
            raise AnkunftRejected(translate("errors.wareneingang.nothing_to_book", language))

        # Regel 6/D13: Ein Lager ohne Verkauf (GEWA) bekommt kein Eingangsdatum.
        lagerort_verkauft = session.scalar(
            select(Lagerort.verkauf).where(Lagerort.id == wareneingang.lagerort_id)
        )
        datum = (eingangsdatum or date.today()) if lagerort_verkauft else None
        jetzt = datetime.now(timezone.utc)
        dokumentdatum = session.scalar(
            select(Dokument.dokumentdatum).where(
                Dokument.id == wareneingang.dokument_id
            )
        )

        for position_id, menge in gebucht.items():
            position = positionen[position_id]
            position.menge_eingetroffen = (position.menge_eingetroffen or 0) + menge
            buche_zugang(
                session,
                lagerort_id=wareneingang.lagerort_id,
                varianten_id=position.varianten_id,
                position_id=position.id,
                menge=menge,
                eingangsdatum=datum,
                benutzer=benutzer,
                zeitpunkt=jetzt,
            )
            # first_seen/last_seen zählen nur angekommene Ware - eine blosse
            # Ankündigung ist keine Lieferung (siehe app/services/importer.py).
            if dokumentdatum:
                variante = session.get(Variante, position.varianten_id)
                variante.first_seen = (
                    min(variante.first_seen, dokumentdatum)
                    if variante.first_seen
                    else dokumentdatum
                )
                variante.last_seen = (
                    max(variante.last_seen, dokumentdatum)
                    if variante.last_seen
                    else dokumentdatum
                )

        if datum and wareneingang.eingangsdatum is None:
            wareneingang.eingangsdatum = datum
        offen = [
            position
            for position in positionen.values()
            if (position.menge or 0) > (position.menge_eingetroffen or 0)
        ]
        if not offen:
            wareneingang.status = "eingetroffen"
        session.flush()
        return {
            "wareneingang_id": wareneingang.id,
            "status": wareneingang.status,
            "gebuchte_positionen": len(gebucht),
            "offene_positionen": len(offen),
            "eingangsdatum": wareneingang.eingangsdatum.isoformat()
            if wareneingang.eingangsdatum
            else None,
        }


def zaehle_erwartete(session, lagerort_id: int | None = None) -> int:
    """Anzahl offener Wareneingänge - für die Übersichtsseite."""
    abfrage = (
        select(func.count())
        .select_from(Wareneingang)
        .where(Wareneingang.status == "erwartet")
    )
    if lagerort_id is not None:
        abfrage = abfrage.where(Wareneingang.lagerort_id == lagerort_id)
    return session.scalar(abfrage) or 0
