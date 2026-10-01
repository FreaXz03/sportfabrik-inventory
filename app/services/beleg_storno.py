"""Ein gebuchtes Dokument stornieren statt löschen (Paket 1, 01.10.2026).

Regel 2: die Historie wird nie umgeschrieben. Jede Zugangsbuchung des
Dokuments bekommt eine Gegenbuchung (Muster: `ausbuchung.storniere`); Dokument,
Originaltext, Positionen und Preise bleiben. Das Dokument gilt danach als
`storniert`, seine Wareneingänge ebenso - der Rest, der noch erwartet wurde,
ist damit nicht mehr offen. Was seither verkauft, ausgebucht oder umgelagert
wurde, bleibt gebucht: der Bestand kann ins Minus gehen (Entscheid 22.09.2026,
Minus ist erlaubt, wird aber in der Vorschau gezeigt).
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import (
    Artikel,
    Bestand,
    Dokument,
    Lagerbewegung,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from .ausbuchung import STORNO_PREFIX, buche_bewegung, sperren, zahl
from .importer import aktualisiere_first_last_seen

SPAETERE_TYPEN = ("verkauf", "ausbuchung", "umlagerung", "korrektur")


class StornoRejected(ValueError):
    """Das Dokument lässt sich nicht stornieren - nichts wurde gebucht."""


class StornoNotFound(StornoRejected):
    pass


def _zugaenge(session, dokument_id: int) -> list[Lagerbewegung]:
    """Zugangsbuchungen des Dokuments. Ein Dokument wird nur einmal storniert
    (Status), darum hat noch keine davon eine Gegenbuchung."""
    return list(
        session.scalars(
            select(Lagerbewegung)
            .join(
                WareneingangPosition,
                WareneingangPosition.id == Lagerbewegung.wareneingang_position_id,
            )
            .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
            .where(Wareneingang.dokument_id == dokument_id, Lagerbewegung.typ == "zugang")
            .order_by(Lagerbewegung.id)
        )
    )


def _lade_dokument(session, dokument_id: int, language: str) -> Dokument:
    dokument = session.get(Dokument, dokument_id)
    if dokument is None:
        raise StornoNotFound(
            translate("errors.importer.invoice_not_found", language, id=dokument_id)
        )
    if dokument.status == "storniert":
        raise StornoRejected(translate("errors.beleg_storno.already_cancelled", language))
    return dokument


def vorschau(session, dokument_id: int, language: str = DEFAULT_LANGUAGE) -> dict:
    """Mengenwirkung je Variante und Lagerort, ohne etwas zu buchen. Markiert
    Varianten, die seit dem Wareneingang weiter bewegt wurden."""
    _lade_dokument(session, dokument_id, language)
    summen: dict[tuple[int, int], Decimal] = {}
    erste: dict[tuple[int, int], int] = {}
    for bewegung in _zugaenge(session, dokument_id):
        schluessel = (bewegung.varianten_id, bewegung.lagerort_id)
        summen[schluessel] = summen.get(schluessel, Decimal("0")) + Decimal(bewegung.menge)
        erste.setdefault(schluessel, bewegung.id)

    zeilen = []
    for (varianten_id, lagerort_id), menge in summen.items():
        bestand = session.get(Bestand, (varianten_id, lagerort_id))
        jetzt = Decimal(bestand.menge) if bestand else Decimal("0")
        spaeter = session.scalar(
            select(Lagerbewegung.id)
            .where(
                Lagerbewegung.varianten_id == varianten_id,
                Lagerbewegung.lagerort_id == lagerort_id,
                Lagerbewegung.typ.in_(SPAETERE_TYPEN),
                Lagerbewegung.id > erste[(varianten_id, lagerort_id)],
            )
            .limit(1)
        )
        variante = session.get(Variante, varianten_id)
        artikel = session.get(Artikel, variante.artikel_id)
        zeilen.append(
            {
                "varianten_id": varianten_id,
                "lagerort_id": lagerort_id,
                "marke": artikel.marke,
                "bezeichnung": artikel.bezeichnung,
                "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
                "farbe": variante.farbe,
                "groesse": variante.groesse,
                "bestand_jetzt": zahl(jetzt),
                "wareneingang": zahl(menge),
                "bestand_danach": zahl(jetzt - menge),
                "spaetere_bewegungen": spaeter is not None,
            }
        )
    return {
        "zeilen": zeilen,
        "hat_spaetere_bewegungen": any(z["spaetere_bewegungen"] for z in zeilen),
        "hat_negativen_bestand": any(Decimal(z["bestand_danach"]) < 0 for z in zeilen),
    }


def storniere_dokument(
    dokument_id: int,
    session_factory,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    with session_factory() as session, session.begin():
        # Dieselbe Sperre wie Import, Ausbuchung und Löschen.
        sperren(session)
        dokument = _lade_dokument(session, dokument_id, language)
        jetzt = datetime.now(timezone.utc)

        zugaenge = _zugaenge(session, dokument_id)
        for original in zugaenge:
            buche_bewegung(
                session,
                lagerort_id=original.lagerort_id,
                varianten_id=original.varianten_id,
                typ="korrektur",
                menge=-Decimal(original.menge),
                grund=f"{STORNO_PREFIX}{original.id}",
                benutzer=benutzer,
                zeitpunkt=jetzt,
                position_id=original.wareneingang_position_id,
            )

        wareneingaenge = session.scalars(
            select(Wareneingang).where(Wareneingang.dokument_id == dokument_id)
        ).all()
        positionen = session.scalars(
            select(WareneingangPosition).where(
                WareneingangPosition.wareneingang_id.in_([w.id for w in wareneingaenge])
            )
        ).all()
        # Welche Eingangsdaten dieses Beleg je Variante × Filiale geliefert hat -
        # vor dem Nullsetzen der angekommenen Mengen festhalten.
        lagerort_von = {w.id: (w.lagerort_id, w.eingangsdatum) for w in wareneingaenge}
        daten_des_belegs: dict[tuple[int, int], set] = {}
        for position in positionen:
            if (position.menge_eingetroffen or 0) > 0:
                lagerort_id, datum = lagerort_von[position.wareneingang_id]
                daten_des_belegs.setdefault((position.varianten_id, lagerort_id), set()).add(datum)
        # Die angekommene Menge steht weiter in Zugang + Gegenbuchung. Die
        # Position selbst gilt nicht mehr als angekommen - so zählt sie für
        # Reduktionsuhr, Etiketten und Statistik nicht mehr als Lieferung.
        for position in positionen:
            position.menge_eingetroffen = Decimal("0")
        for wareneingang in wareneingaenge:
            wareneingang.status = "storniert"
        dokument.status = "storniert"
        dokument.storniert_am = jetzt
        dokument.storniert_von_kassennummer = (benutzer or {}).get("kassennummer")
        dokument.storniert_von_name = (benutzer or {}).get("name")
        session.flush()

        betroffen = {(z.varianten_id, z.lagerort_id) for z in zugaenge}
        for varianten_id, lagerort_id in betroffen:
            bestand = session.get(Bestand, (varianten_id, lagerort_id))
            # Nur neu rechnen, wenn der stornierte Wareneingang das älteste
            # Datum geliefert hat. Ein älteres Datum kann von einer Umlagerung
            # stammen (Regel 6, D17: das Datum bleibt) - das darf ein
            # unbeteiligter Beleg nicht überschreiben.
            if bestand is not None and bestand.aeltestes_eingangsdatum in daten_des_belegs.get(
                (varianten_id, lagerort_id), set()
            ):
                bestand.aeltestes_eingangsdatum = session.scalar(
                    select(func.min(Wareneingang.eingangsdatum))
                    .select_from(WareneingangPosition)
                    .join(
                        Wareneingang,
                        Wareneingang.id == WareneingangPosition.wareneingang_id,
                    )
                    .where(
                        WareneingangPosition.varianten_id == varianten_id,
                        Wareneingang.lagerort_id == lagerort_id,
                        WareneingangPosition.menge_eingetroffen > 0,
                    )
                )
        aktualisiere_first_last_seen(session, {v for v, _ in betroffen})
        return {
            "invoice_id": dokument.id,
            "invoice_number": dokument.dokumentnummer,
            "gegenbuchungen": len(zugaenge),
        }
