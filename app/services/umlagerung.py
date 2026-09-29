"""Ware zwischen Lagerorten umlagern (Phase C, Teilaufgabe C4; seit
28.09.2026 wie eine Lieferung).

Die Regeln dazu (docs/projekt-kontext.md Abschnitte 4 und 10):

* **Versand und Ankunft getrennt** (Entscheid 28.09.2026, ersetzt F5): die
  Quelle versendet mit einem Versanddatum - der Abgang wird sofort gebucht.
  Das Ziel bekommt einen erwarteten Wareneingang (`herkunft_lagerort_id`,
  `versanddatum`) und bestätigt die Ankunft wie bei einer Lieferung, nach
  dem Auspacken (D21, D22: Teilmengen bleiben offen). Dazwischen ist die
  Ware unterwegs und in keinem Bestand.
* **Externer Standort → Filiale** (D13): die Ware kommt zum ersten Mal in eine
  Filiale - das Eingangsdatum ist das Ankunftsdatum, auf Wunsch rückwirkend,
  und die Reduktionsuhr der Filiale startet.
* **Filiale → Filiale** (D17, F10): die Ware behält ihr Datum
  (`mitgebracht_datum`, beim Versand festgehalten), und die Uhr der
  Zielfiliale läuft unverändert weiter. Hatte die Zielfiliale diesen Artikel
  aber **noch nie**, startet ihre Uhr ab Ankunft (F11, 23.09.2026).
* **Ziel ohne Verkauf** (GEWA, VEBO, Dietikon): dort läuft keine Uhr, es gibt
  kein Eingangsdatum (Regel 6).
* **Zu wenig Bestand an der Quelle**: gewarnt und trotzdem gebucht, wie beim
  Ausbuchen (F9).

* **Stornieren unterwegs** (Entscheid 29.09.2026): Filialleiter der Quelle
  oder Zentrale. Der offene Rest geht mit seinem alten Datum an die Quelle
  zurück (Grund `zurueck:SF3`), schon Angekommenes bleibt am Ziel; der
  Wareneingang wird `storniert`.

Ob eine Umlagerung die Uhr startet, steht an ihrer Zugangsbewegung in
`lagerbewegungen.eingangsdatum`; `reduktion.letzter_wareneingang()` zählt
dieses Datum mit. Beide Bewegungen sind `typ = umlagerung`, der Grund nennt
die Gegenseite (`nach:SF2` bzw. `von:GEWA`). Der Wareneingang einer
Umlagerung bekommt nie ein eigenes `eingangsdatum`.
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import Artikel, Bestand, Lagerort, Variante, Wareneingang, WareneingangPosition
from .ausbuchung import buche_bewegung, sperren, zahl
from .reduktion import letzter_wareneingang
from .wareneingang import MAX_MENGE

MAX_POSITIONEN = 500


class UmlagerungRejected(ValueError):
    """Die Umlagerung ist nicht plausibel - nichts wurde gebucht."""


class UmlagerungForbidden(PermissionError):
    """Keine Berechtigung für diese Quelle - nichts wurde gebucht."""


def _mengen(positionen, language: str) -> dict[int, Decimal]:
    """Positionen prüfen und je Variante zusammenzählen (zweimal gescannt =
    zwei Stück)."""
    if not positionen:
        raise UmlagerungRejected(translate("errors.umlagerung.no_positions", language))
    if len(positionen) > MAX_POSITIONEN:
        raise UmlagerungRejected(
            translate("errors.umlagerung.too_many_positions", language, max=MAX_POSITIONEN)
        )
    mengen: dict[int, Decimal] = {}
    for position in positionen:
        try:
            varianten_id = int(position["varianten_id"])
            menge = Decimal(str(position["menge"]))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise UmlagerungRejected(
                translate("errors.umlagerung.invalid_position", language)
            ) from exc
        if (
            not menge.is_finite()
            or menge <= 0
            or menge != menge.quantize(Decimal(".01"))
            or menge >= MAX_MENGE
        ):
            raise UmlagerungRejected(
                translate("errors.umlagerung.invalid_quantity", language)
            )
        mengen[varianten_id] = mengen.get(varianten_id, Decimal("0")) + menge
    return mengen


def umlagern(
    session_factory,
    *,
    quelle_id: int,
    ziel_id: int,
    positionen: list[dict],
    versanddatum: date | None = None,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Ware von `quelle_id` an `ziel_id` versenden - alles in einer
    Transaktion, entweder ganz oder gar nicht.

    Bucht den Abgang an der Quelle und legt am Ziel einen erwarteten
    Wareneingang an; ohne `versanddatum` gilt heute. Die Antwort listet in
    `fehlbestand` die Positionen, für die die Quelle zu wenig Bestand hatte.
    """
    if quelle_id == ziel_id:
        raise UmlagerungRejected(translate("errors.umlagerung.same_location", language))
    heute = date.today()
    if versanddatum is not None and versanddatum > heute:
        raise UmlagerungRejected(translate("errors.erfassung.date_in_future", language))
    datum = versanddatum or heute
    mengen = _mengen(positionen, language)

    with session_factory() as session, session.begin():
        sperren(session)
        quelle = session.get(Lagerort, quelle_id)
        ziel = session.get(Lagerort, ziel_id)
        if quelle is None or ziel is None:
            raise UmlagerungRejected(translate("errors.bestand.unknown_lagerort", language))

        varianten = {}
        for varianten_id in mengen:
            variante = session.get(Variante, varianten_id)
            if variante is None:
                raise UmlagerungRejected(
                    translate("errors.ausbuchung.variant_not_found", language)
                )
            varianten[varianten_id] = variante

        wareneingang = Wareneingang(
            dokument_id=None,
            lagerort_id=ziel.id,
            status="erwartet",
            herkunft_lagerort_id=quelle.id,
            versanddatum=datum,
        )
        session.add(wareneingang)
        session.flush()

        jetzt = datetime.now(timezone.utc)
        ergebnis_positionen, fehlbestand = [], []
        for varianten_id, menge in mengen.items():
            variante = varianten[varianten_id]
            quell_bestand = session.get(Bestand, (varianten_id, quelle.id))
            session.add(
                WareneingangPosition(
                    wareneingang_id=wareneingang.id,
                    varianten_id=varianten_id,
                    menge=menge,
                    menge_eingetroffen=Decimal("0"),
                    mitgebracht_datum=quell_bestand.aeltestes_eingangsdatum if quell_bestand else None,
                )
            )
            _, quelle_vorher, quelle_nachher = buche_bewegung(
                session,
                lagerort_id=quelle.id,
                varianten_id=varianten_id,
                typ="umlagerung",
                menge=-menge,
                grund=f"nach:{ziel.code}",
                benutzer=benutzer,
                zeitpunkt=jetzt,
            )
            artikel = session.get(Artikel, variante.artikel_id)
            eintrag = {
                "varianten_id": varianten_id,
                "marke": artikel.marke,
                "bezeichnung": artikel.bezeichnung,
                "farbe": variante.farbe,
                "groesse": variante.groesse,
                "menge": zahl(menge),
                "bestand_quelle_vorher": zahl(quelle_vorher),
                "bestand_quelle_nachher": zahl(quelle_nachher),
            }
            ergebnis_positionen.append(eintrag)
            if quelle_vorher < menge:
                fehlbestand.append(eintrag)

        return {
            "wareneingang_id": wareneingang.id,
            "quelle": {"id": quelle.id, "code": quelle.code, "name": quelle.name},
            "ziel": {"id": ziel.id, "code": ziel.code, "name": ziel.name},
            "versanddatum": datum.isoformat(),
            "positionen": ergebnis_positionen,
            "fehlbestand": fehlbestand,
            "stueck": zahl(sum(mengen.values(), Decimal("0"))),
        }


def buche_ankunft(session, wareneingang, gebucht: dict, positionen: dict, datum: date, benutzer, jetzt) -> None:
    """Ankunft einer Umlagerung buchen (aufgerufen aus
    `wareneingang.bestaetige_ankunft`): Zugang am Ziel mit den Datumsregeln
    D13/D17/F10/F11. `gebucht` bildet Positions-Id → angekommene Menge ab,
    `datum` ist das Ankunftsdatum."""
    quelle = session.get(Lagerort, wareneingang.herkunft_lagerort_id)
    ziel = session.get(Lagerort, wareneingang.lagerort_id)
    varianten = {pid: session.get(Variante, positionen[pid].varianten_id) for pid in gebucht}

    # Vor dem Buchen feststellen, ob die Zielfiliale den Artikel schon kennt -
    # sonst sähe die zweite Variante desselben Artikels die Uhr, die die erste
    # gerade gestartet hat (F11 gilt je Artikel).
    uhr_laeuft = {}
    if ziel.verkauf and quelle.verkauf:
        for variante in varianten.values():
            if variante.artikel_id not in uhr_laeuft:
                uhr_laeuft[variante.artikel_id] = (
                    letzter_wareneingang(session, variante.artikel_id, ziel.id) is not None
                )

    for position_id, menge in gebucht.items():
        position = positionen[position_id]
        variante = varianten[position_id]
        mitgebracht = position.mitgebracht_datum
        if not ziel.verkauf:
            # Standort ohne Verkauf: keine Uhr, kein Datum (Regel 6).
            uhr_start, aeltestes = None, None
        elif not quelle.verkauf:
            # Erster Weg in eine Filiale (D13).
            uhr_start, aeltestes = datum, datum
        elif uhr_laeuft[variante.artikel_id]:
            # Filiale → Filiale, Ziel kennt den Artikel: nichts verjüngen
            # (D17), die Uhr des Ziels läuft weiter (F10).
            uhr_start, aeltestes = None, mitgebracht
        else:
            # Filiale → Filiale, Ziel hatte den Artikel nie (F11).
            uhr_start, aeltestes = datum, mitgebracht or datum
        buche_bewegung(
            session,
            lagerort_id=ziel.id,
            varianten_id=position.varianten_id,
            typ="umlagerung",
            menge=menge,
            grund=f"von:{quelle.code}",
            benutzer=benutzer,
            zeitpunkt=jetzt,
            eingangsdatum=uhr_start,
            aeltestes=aeltestes,
            position_id=position.id,
        )


def stornieren(
    session_factory,
    wareneingang_id: int,
    *,
    erlaubte_quellen: set[int] | None,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Umlagerung unterwegs stornieren (Entscheid 29.09.2026), z. B. bei
    falschem Ziel. Der noch offene Rest jeder Position geht an die Quelle
    zurück - mit dem Datum, das er beim Versand hatte (`mitgebracht_datum`),
    ohne die Reduktionsuhr neu zu starten. Schon Angekommenes bleibt am Ziel.
    `erlaubte_quellen` = None heisst: jede Quelle (Zentrale)."""
    with session_factory() as session, session.begin():
        sperren(session)
        wareneingang = session.get(Wareneingang, wareneingang_id)
        if wareneingang is None or wareneingang.herkunft_lagerort_id is None:
            raise UmlagerungRejected(translate("errors.umlagerung.not_a_transfer", language))
        if erlaubte_quellen is not None and wareneingang.herkunft_lagerort_id not in erlaubte_quellen:
            raise UmlagerungForbidden(translate("errors.auth.no_lagerort_access", language))
        if wareneingang.status != "erwartet":
            raise UmlagerungRejected(translate("errors.umlagerung.not_in_transit", language))
        quelle = session.get(Lagerort, wareneingang.herkunft_lagerort_id)
        ziel = session.get(Lagerort, wareneingang.lagerort_id)
        jetzt = datetime.now(timezone.utc)
        zurueck = Decimal("0")
        for position in session.scalars(
            select(WareneingangPosition)
            .where(WareneingangPosition.wareneingang_id == wareneingang.id)
            .order_by(WareneingangPosition.id)
        ):
            offen = (position.menge or 0) - (position.menge_eingetroffen or 0)
            if offen <= 0:
                continue
            buche_bewegung(
                session,
                lagerort_id=quelle.id,
                varianten_id=position.varianten_id,
                typ="umlagerung",
                menge=offen,
                grund=f"zurueck:{ziel.code}",
                benutzer=benutzer,
                zeitpunkt=jetzt,
                aeltestes=position.mitgebracht_datum,
                position_id=position.id,
            )
            zurueck += offen
        wareneingang.status = "storniert"
        return {
            "wareneingang_id": wareneingang.id,
            "quelle": {"id": quelle.id, "code": quelle.code, "name": quelle.name},
            "ziel": {"id": ziel.id, "code": ziel.code, "name": ziel.name},
            "stueck": zahl(zurueck),
        }
