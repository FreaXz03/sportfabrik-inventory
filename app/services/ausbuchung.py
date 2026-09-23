"""Ware von Hand ausbuchen - Verkauf oder Abgang per Scan (Phase C,
Teilaufgabe C3).

Die Regeln dazu (docs/projekt-kontext.md Abschnitt 10):

* **Ein Scan = ein Stück** (F15, 23.09.2026). Mehrere Stück werden mehrmals
  gescannt; eine Mengenabfrage gibt es bewusst nicht.
* **Gründe** (F14, 23.09.2026): Verkauf, Bruch/Defekt, Diebstahl/Schwund,
  Eigenbedarf, Retoure an den Lieferanten, Sonstiges mit freiem Text. Ein
  Verkauf wird als `typ = verkauf` gebucht, alles andere als `ausbuchung` -
  so lassen sich Verkäufe später von Schwund trennen.
* **Negativer Bestand** (F9, 22.09.2026): Reicht der Bestand nicht, wird
  gewarnt und trotzdem gebucht - wie an der Kasse. Der migrierte Bestand ist
  kumulierter Wareneingang ohne Verkäufe, Differenzen sind anfangs normal.
* **Bestand** (Regel 2): nie direkt überschreiben, jede Änderung ist eine
  Zeile in `lagerbewegungen` - unter derselben Sperre wie der Zugang.
* **Rückgängig**: Ein Fehlscan wird nicht gelöscht, sondern mit einer
  Gegenbuchung (`typ = korrektur`, Grund `storno:<id>`) aufgehoben. Das
  Journal bleibt so vollständig.

Der Grund `test` gehört zum vorübergehenden Knopf „1 Stück abbuchen" in der
Bestandsansicht (23.09.2026) - er ist in der Ausbuchen-Seite nicht wählbar,
damit echte Abgänge nicht darin verschwinden, und lässt sich später gezielt
wiederfinden.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text

from ..core.i18n import DEFAULT_LANGUAGE, translate
from ..core.models import Artikel, Bestand, Lagerbewegung, Lagerort, Variante
from .artikel import EAN_MUSTER, finde_variante_per_ean
from .wareneingang import ADVISORY_LOCK_ID

# Reihenfolge = Reihenfolge in der Auswahl; Verkauf zuerst, er ist der
# häufigste Fall am Tresen.
GRUENDE = ("verkauf", "defekt", "diebstahl", "eigenbedarf", "retoure", "sonstiges")
TEST_GRUND = "test"
FREITEXT_MAX = 150
STORNO_PREFIX = "storno:"

EIN_STUECK = Decimal("1")


class AusbuchungRejected(ValueError):
    """Die Ausbuchung ist nicht plausibel - nichts wurde gebucht."""


def zahl(wert) -> str:
    return str(Decimal(wert or 0).quantize(Decimal("0.01")))


def buche_bewegung(
    session,
    *,
    lagerort_id: int,
    varianten_id: int,
    typ: str,
    menge: Decimal,
    grund: str | None,
    benutzer: dict | None,
    zeitpunkt: datetime,
    eingangsdatum: date | None = None,
    aeltestes: date | None = None,
) -> tuple[Lagerbewegung, Decimal, Decimal]:
    """Eine Bewegung ausser dem Zugang schreiben und den Bestand nachführen
    (Regel 2). `menge` ist vorzeichenbehaftet: negativ für einen Abgang.

    Ein Abgang ist nie ein Wareneingang - das Eingangsdatum bleibt, wie es
    ist. Nur eine Umlagerung gibt `eingangsdatum` (startet die Reduktionsuhr,
    siehe app/services/umlagerung.py) und `aeltestes` (das Datum, das die Ware
    mitbringt, D17) mit. Gibt die Bewegung und den Bestand vorher/nachher
    zurück.
    """
    bewegung = Lagerbewegung(
        lagerort_id=lagerort_id,
        varianten_id=varianten_id,
        typ=typ,
        menge=menge,
        grund=grund,
        eingangsdatum=eingangsdatum,
        benutzer_kassennummer=(benutzer or {}).get("kassennummer"),
        benutzer_name=(benutzer or {}).get("name"),
        zeitpunkt=zeitpunkt,
    )
    session.add(bewegung)
    bestand = session.get(Bestand, (varianten_id, lagerort_id))
    if bestand is None:
        # Ausbuchen ohne je gebuchten Zugang: der Bestand geht ins Minus
        # (F9) - ohne Eingangsdatum, weil nichts eingetroffen ist.
        bestand = Bestand(
            varianten_id=varianten_id, lagerort_id=lagerort_id, menge=Decimal("0")
        )
        session.add(bestand)
    vorher = Decimal(bestand.menge or 0)
    bestand.menge = vorher + menge
    if aeltestes and (
        bestand.aeltestes_eingangsdatum is None
        or aeltestes < bestand.aeltestes_eingangsdatum
    ):
        bestand.aeltestes_eingangsdatum = aeltestes
    session.flush()
    return bewegung, vorher, Decimal(bestand.menge)


def sperren(session) -> None:
    if session.bind.dialect.name == "postgresql":
        session.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})"))


def _grund_text(grund: str | None, freitext: str | None, language: str) -> str:
    grund = (grund or "").strip()
    if grund not in GRUENDE and grund != TEST_GRUND:
        raise AusbuchungRejected(translate("errors.ausbuchung.unknown_reason", language))
    if grund != "sonstiges":
        return grund
    freitext = (freitext or "").strip()
    if not freitext:
        raise AusbuchungRejected(translate("errors.ausbuchung.text_required", language))
    if len(freitext) > FREITEXT_MAX:
        raise AusbuchungRejected(
            translate("errors.ausbuchung.text_too_long", language, max=FREITEXT_MAX)
        )
    return f"sonstiges: {freitext}"


def _finde_variante(session, ean, varianten_id, language: str) -> Variante:
    if (ean is None) == (varianten_id is None):
        raise AusbuchungRejected(translate("errors.ausbuchung.ean_or_variant", language))
    if varianten_id is not None:
        variante = session.get(Variante, varianten_id)
        if variante is None:
            raise AusbuchungRejected(
                translate("errors.ausbuchung.variant_not_found", language)
            )
        return variante
    ean = str(ean).strip()
    if not ean:
        raise AusbuchungRejected(translate("errors.erfassung.ean_missing", language))
    if not EAN_MUSTER.fullmatch(ean):
        raise AusbuchungRejected(translate("errors.erfassung.ean_format", language))
    variante = finde_variante_per_ean(session, ean)
    if variante is None:
        raise AusbuchungRejected(
            translate("errors.ausbuchung.ean_unknown", language, ean=ean)
        )
    return variante


def _antwort(session, bewegung, variante, vorher, nachher) -> dict:
    artikel = session.get(Artikel, variante.artikel_id)
    lagerort = session.get(Lagerort, bewegung.lagerort_id)
    return {
        "bewegung_id": bewegung.id,
        "typ": bewegung.typ,
        "grund": bewegung.grund,
        "zeitpunkt": bewegung.zeitpunkt.isoformat(),
        "varianten_id": variante.id,
        "marke": artikel.marke,
        "bezeichnung": artikel.bezeichnung,
        "farbe": variante.farbe,
        "groesse": variante.groesse,
        "ean": variante.ean,
        "lagerort": {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
        "bestand_vorher": zahl(vorher),
        "bestand_nachher": zahl(nachher),
    }


def ausbuchen(
    session_factory,
    *,
    lagerort_id: int,
    grund: str,
    ean: str | None = None,
    varianten_id: int | None = None,
    freitext: str | None = None,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Ein Stück einer Variante am Lagerort ausbuchen (F15).

    Die Variante kommt über die gescannte EAN oder - für den Knopf in der
    Bestandsansicht und Varianten ohne EAN (Regel 5) - über ihre Id.
    `bestand_reicht_nicht` meldet, dass der Bestand vorher unter einem Stück
    lag; gebucht ist trotzdem (F9).
    """
    grund_text = _grund_text(grund, freitext, language)
    typ = "verkauf" if grund == "verkauf" else "ausbuchung"
    with session_factory() as session, session.begin():
        sperren(session)
        if session.get(Lagerort, lagerort_id) is None:
            raise AusbuchungRejected(translate("errors.bestand.unknown_lagerort", language))
        variante = _finde_variante(session, ean, varianten_id, language)
        bewegung, vorher, nachher = buche_bewegung(
            session,
            lagerort_id=lagerort_id,
            varianten_id=variante.id,
            typ=typ,
            menge=-EIN_STUECK,
            grund=grund_text,
            benutzer=benutzer,
            zeitpunkt=datetime.now(timezone.utc),
        )
        ergebnis = _antwort(session, bewegung, variante, vorher, nachher)
        ergebnis["bestand_reicht_nicht"] = vorher < EIN_STUECK
        return ergebnis


def storniere(
    session_factory,
    bewegung_id: int,
    benutzer: dict | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """Eine Ausbuchung per Gegenbuchung aufheben - einmal, nicht öfter."""
    with session_factory() as session, session.begin():
        sperren(session)
        bewegung = session.get(Lagerbewegung, bewegung_id)
        if bewegung is None or bewegung.typ not in ("verkauf", "ausbuchung"):
            raise AusbuchungRejected(
                translate("errors.ausbuchung.not_cancellable", language)
            )
        schon = session.scalar(
            select(Lagerbewegung.id).where(
                Lagerbewegung.grund == f"{STORNO_PREFIX}{bewegung.id}"
            )
        )
        if schon is not None:
            raise AusbuchungRejected(
                translate("errors.ausbuchung.already_cancelled", language)
            )
        gegen, vorher, nachher = buche_bewegung(
            session,
            lagerort_id=bewegung.lagerort_id,
            varianten_id=bewegung.varianten_id,
            typ="korrektur",
            menge=-Decimal(bewegung.menge),
            grund=f"{STORNO_PREFIX}{bewegung.id}",
            benutzer=benutzer,
            zeitpunkt=datetime.now(timezone.utc),
        )
        variante = session.get(Variante, bewegung.varianten_id)
        ergebnis = _antwort(session, gegen, variante, vorher, nachher)
        ergebnis["storniert"] = bewegung.id
        return ergebnis
