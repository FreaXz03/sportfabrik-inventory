"""Ware zwischen Lagerorten umlagern (Phase C, Teilaufgabe C4).

Die Regeln dazu (docs/projekt-kontext.md Abschnitte 4 und 10):

* **Gebucht wird beim Empfang, von der empfangenden Filiale** (F5): eine
  Buchung erledigt beides - Abgang am Quell-Lagerort, Zugang am Ziel. Einen
  Zwischenstand „unterwegs" gibt es nicht.
* **Externer Standort → Filiale** (D13): die Ware kommt zum ersten Mal in eine
  Filiale - das Eingangsdatum wird jetzt gesetzt, auf Wunsch rückwirkend, und
  die Reduktionsuhr der Filiale startet.
* **Filiale → Filiale** (D17, F10): die Ware behält ihr Datum, und die Uhr der
  Zielfiliale läuft unverändert weiter - eine Umlagerung ist dort kein
  Wareneingang. Hatte die Zielfiliale diesen Artikel aber **noch nie**, startet
  ihre Uhr ab Eintreffen (F11, 23.09.2026).
* **Ziel ohne Verkauf** (GEWA, VEBO, Dietikon): dort läuft keine Uhr, es gibt
  kein Eingangsdatum (Regel 6).
* **Zu wenig Bestand an der Quelle**: gewarnt und trotzdem gebucht, wie beim
  Ausbuchen (F9) - der migrierte Bestand ist kumulierter Wareneingang ohne
  Verkäufe, die Ware ist physisch aber da, wenn sie ankommt.

Ob eine Umlagerung die Uhr startet, steht an ihrer Zugangsbewegung in
`lagerbewegungen.eingangsdatum`; `reduktion.letzter_wareneingang()` zählt
dieses Datum mit. Beide Bewegungen sind `typ = umlagerung`, der Grund nennt
die Gegenseite (`nach:SF2` bzw. `von:GEWA`).
"""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import Artikel, Bestand, Lagerort, Variante
from .ausbuchung import buche_bewegung, sperren, zahl
from .reduktion import letzter_wareneingang
from .wareneingang import MAX_MENGE

MAX_POSITIONEN = 500


class UmlagerungRejected(ValueError):
    """Die Umlagerung ist nicht plausibel - nichts wurde gebucht."""


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
    eingangsdatum: date | None = None,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Ware von `quelle_id` nach `ziel_id` umbuchen - alles in einer
    Transaktion, entweder ganz oder gar nicht.

    `eingangsdatum` zählt nur dort, wo die Umlagerung die Uhr der Zielfiliale
    startet (D13, F11); ohne Angabe gilt heute. Die Antwort nennt je Position,
    ob die Uhr gestartet wurde (`uhr_start`), und listet in `fehlbestand` die
    Positionen, für die die Quelle zu wenig Bestand hatte.
    """
    if quelle_id == ziel_id:
        raise UmlagerungRejected(translate("errors.umlagerung.same_location", language))
    heute = date.today()
    if eingangsdatum is not None and eingangsdatum > heute:
        raise UmlagerungRejected(translate("errors.erfassung.date_in_future", language))
    datum = eingangsdatum or heute
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

        # Vor dem Buchen feststellen, ob die Zielfiliale den Artikel schon
        # kennt - sonst sähe die zweite Variante desselben Artikels die Uhr,
        # die die erste gerade gestartet hat (F11 gilt je Artikel).
        uhr_laeuft = {}
        if ziel.verkauf and quelle.verkauf:
            for variante in varianten.values():
                if variante.artikel_id not in uhr_laeuft:
                    uhr_laeuft[variante.artikel_id] = (
                        letzter_wareneingang(session, variante.artikel_id, ziel.id)
                        is not None
                    )

        jetzt = datetime.now(timezone.utc)
        ergebnis_positionen, fehlbestand = [], []
        for varianten_id, menge in mengen.items():
            variante = varianten[varianten_id]
            quell_bestand = session.get(Bestand, (varianten_id, quelle.id))
            mitgebracht = quell_bestand.aeltestes_eingangsdatum if quell_bestand else None

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
            _, _, ziel_nachher = buche_bewegung(
                session,
                lagerort_id=ziel.id,
                varianten_id=varianten_id,
                typ="umlagerung",
                menge=menge,
                grund=f"von:{quelle.code}",
                benutzer=benutzer,
                zeitpunkt=jetzt,
                eingangsdatum=uhr_start,
                aeltestes=aeltestes,
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
                "bestand_ziel_nachher": zahl(ziel_nachher),
                "uhr_start": uhr_start.isoformat() if uhr_start else None,
            }
            ergebnis_positionen.append(eintrag)
            if quelle_vorher < menge:
                fehlbestand.append(eintrag)

        return {
            "quelle": {"id": quelle.id, "code": quelle.code, "name": quelle.name},
            "ziel": {"id": ziel.id, "code": ziel.code, "name": ziel.name},
            "positionen": ergebnis_positionen,
            "fehlbestand": fehlbestand,
            "stueck": zahl(sum(mengen.values(), Decimal("0"))),
        }
