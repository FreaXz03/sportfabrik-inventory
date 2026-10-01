"""Bestand korrigieren - gezählte Menge buchen (Phase C, Teilaufgabe C5).

Die Regeln dazu (docs/projekt-kontext.md Abschnitt 10, 23.09.2026):

* **Eingegeben wird die gezählte Menge**, nicht die Differenz: wer im Regal 7
  Stück zählt, gibt 7 ein. Das System rechnet die Differenz zum Bestand
  **im Moment der Buchung** aus und bucht nur sie - eine Mini-Inventur je
  Zeile. Stimmt der Bestand schon, wird nichts gebucht.
* **Gründe:** Inventur/Zählung, Falsch gebucht, Ware gefunden, Sonstiges mit
  freiem Text.
* **Veraltete Zählung (Paket 2, Q4):** der Client schickt mit der Zählung
  `stand_bewegung_id` mit - die letzte Bewegung dieser Variante an dieser
  Filiale bei Zählbeginn. Hat sich der Bestand seither bewegt, bucht der Server
  nichts und meldet die Bewegungen seit Zählbeginn (`BestandGeaendert`): neu
  zählen, oder mit `bestaetigt` ausdrücklich gegen den Stand von jetzt buchen.
  Beides ist optional - ohne Marke gibt es keine Prüfung.
* **Jede Zählung wird festgehalten** (`zaehlungen`), auch eine ohne Differenz:
  „gezählt, kein Unterschied" ist dann nachweisbar.
* **Rechte:** alle Rollen (Regel 9).
* **Bestand** (Regel 2): die Differenz ist eine Zeile `typ = korrektur` in
  `lagerbewegungen`, unter derselben Sperre wie jeder Zugang. Eine Korrektur
  ist kein Wareneingang - das Eingangsdatum bleibt, wie es ist.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import Bestand, Lagerbewegung, Lagerort, Variante, Zaehlung
from . import operation
from .ausbuchung import FREITEXT_MAX, buche_bewegung, sperren, zahl
from .wareneingang import MAX_MENGE

# Reihenfolge = Reihenfolge in der Auswahl; die Zählung ist der Normalfall.
GRUENDE = ("inventur", "falsch_gebucht", "gefunden", "sonstiges")


class KorrekturRejected(ValueError):
    """Die Korrektur ist nicht plausibel - nichts wurde gebucht."""


class BestandGeaendert(KorrekturRejected):
    """Der Bestand hat sich seit Zählbeginn bewegt - neu zählen oder
    ausdrücklich bestätigen. `daten` ist die Antwort für den Client."""

    def __init__(self, message: str, daten: dict):
        super().__init__(message)
        self.daten = daten


def _gezaehlt(wert, language: str) -> Decimal:
    try:
        menge = Decimal(str(wert).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise KorrekturRejected(
            translate("errors.korrektur.invalid_quantity", language)
        ) from exc
    if (
        not menge.is_finite()
        or menge < 0
        or menge != menge.quantize(Decimal(".01"))
        or menge >= MAX_MENGE
    ):
        raise KorrekturRejected(translate("errors.korrektur.invalid_quantity", language))
    return menge


def _grund_text(grund: str | None, freitext: str | None, language: str) -> str:
    grund = (grund or "").strip()
    if grund not in GRUENDE:
        raise KorrekturRejected(translate("errors.ausbuchung.unknown_reason", language))
    if grund != "sonstiges":
        return grund
    freitext = (freitext or "").strip()
    if not freitext:
        raise KorrekturRejected(translate("errors.ausbuchung.text_required", language))
    if len(freitext) > FREITEXT_MAX:
        raise KorrekturRejected(
            translate("errors.ausbuchung.text_too_long", language, max=FREITEXT_MAX)
        )
    return f"sonstiges: {freitext}"


def korrigieren(
    session_factory,
    *,
    lagerort_id: int,
    varianten_id: int,
    gezaehlt,
    grund: str,
    freitext: str | None = None,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
    stand_bewegung_id: int | None = None,
    bestaetigt: bool = False,
    operation_id: str | None = None,
) -> dict:
    """Den Bestand einer Variante am Lagerort auf die gezählte Menge bringen.

    `gebucht` ist `False`, wenn der Bestand schon stimmte - dann entsteht
    keine Lagerbewegung, aber eine Zählung (`zaehlung_id`).
    """
    menge = _gezaehlt(gezaehlt, language)
    grund_text = _grund_text(grund, freitext, language)
    with session_factory() as session, session.begin():
        sperren(session)
        op = operation.starte(
            session, operation_id, "korrektur", benutzer,
            {"lagerort_id": lagerort_id, "varianten_id": varianten_id, "gezaehlt": str(gezaehlt),
             "grund": grund, "freitext": freitext, "stand_bewegung_id": stand_bewegung_id,
             "bestaetigt": bestaetigt},
            language,
        )
        if op.gespeichert is not None:
            return op.gespeichert
        lagerort = session.get(Lagerort, lagerort_id)
        if lagerort is None:
            raise KorrekturRejected(translate("errors.bestand.unknown_lagerort", language))
        if session.get(Variante, varianten_id) is None:
            raise KorrekturRejected(
                translate("errors.ausbuchung.variant_not_found", language)
            )
        # Die Differenz erst unter der Sperre rechnen: wurde zwischen Zählen
        # und Buchen etwas verkauft, zählt der Stand von jetzt.
        bestand = session.get(Bestand, (varianten_id, lagerort_id))
        vorher = Decimal(bestand.menge) if bestand else Decimal("0")
        differenz = menge - vorher
        geaendert = False
        if stand_bewegung_id is not None:
            neuer_stand = session.scalar(
                select(func.max(Lagerbewegung.id)).where(
                    Lagerbewegung.varianten_id == varianten_id,
                    Lagerbewegung.lagerort_id == lagerort_id,
                )
            ) or 0
            geaendert = neuer_stand > stand_bewegung_id
            if geaendert and not bestaetigt:
                seit = session.scalars(
                    select(Lagerbewegung)
                    .where(
                        Lagerbewegung.varianten_id == varianten_id,
                        Lagerbewegung.lagerort_id == lagerort_id,
                        Lagerbewegung.id > stand_bewegung_id,
                    )
                    .order_by(Lagerbewegung.id)
                ).all()
                raise BestandGeaendert(
                    translate("errors.korrektur.stock_changed", language),
                    {
                        "code": "bestand_geaendert",
                        "bestand_jetzt": zahl(vorher),
                        "stand_bewegung_id": neuer_stand,
                        "seit_zaehlbeginn": [
                            {
                                "id": b.id,
                                "typ": b.typ,
                                "menge": zahl(b.menge),
                                "zeitpunkt": b.zeitpunkt.isoformat(),
                                "benutzer_name": b.benutzer_name,
                            }
                            for b in seit
                        ],
                    },
                )
        ergebnis = {
            "varianten_id": varianten_id,
            "lagerort": {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
            "bestand_vorher": zahl(vorher),
            "bestand_nachher": zahl(menge),
            "differenz": zahl(differenz),
            "gebucht": False,
            "bewegung_id": None,
        }
        bewegung = None
        if differenz != 0:
            bewegung, _, _ = buche_bewegung(
                session,
                lagerort_id=lagerort_id,
                varianten_id=varianten_id,
                typ="korrektur",
                menge=differenz,
                grund=grund_text,
                benutzer=benutzer,
                zeitpunkt=datetime.now(timezone.utc),
            )
            ergebnis["gebucht"] = True
            ergebnis["bewegung_id"] = bewegung.id
            ergebnis["grund"] = grund_text
        zaehlung = Zaehlung(
            lagerort_id=lagerort_id,
            varianten_id=varianten_id,
            gezaehlt=menge,
            bestand_vorher=vorher,
            differenz=differenz,
            grund=grund_text,
            bewegung_id=bewegung.id if bewegung else None,
            bestaetigt_trotz_aenderung=geaendert and bestaetigt,
            benutzer_kassennummer=(benutzer or {}).get("kassennummer"),
            benutzer_name=(benutzer or {}).get("name"),
            zeitpunkt=datetime.now(timezone.utc),
        )
        session.add(zaehlung)
        session.flush()
        ergebnis["zaehlung_id"] = zaehlung.id
        return op.abschliessen(ergebnis)
