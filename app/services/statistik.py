"""Statistikseite (Anforderung 9, 24.09.2026): verkaufte Stück je
Kassenkategorie, geschätzte Einnahmen und eine Bestellempfehlung, je Zeitraum.
Nur Filialleiter/Zentrale dürfen sie sehen (Router prüft das).

**Einnahmen sind ausdrücklich eine Schätzung** (Entscheid 24.09.2026): für
jeden `verkauf` wird der zu diesem Zeitpunkt gültige UVP (jüngster `Preis`
davor, sonst der früheste bekannte) mit der zu diesem Zeitpunkt automatisch
fälligen Reduktion (Regel 6) verrechnet. Eine von Hand gewählte Reduktion
(`reduktionen_manuell`) hat keine Historie - sie fliesst bewusst nicht ein,
das wäre nicht mehr als ein Verkaufszeitpunkt zurückrechenbar. Eine
stornierte Buchung (Gegenbuchung `korrektur`, Grund `storno:<id>`) zählt
nicht mit.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from ..core.models import Artikel, Bestand, Kategorie, Lagerbewegung, Preis, Variante, Wareneingang, WareneingangPosition
from .ausbuchung import STORNO_PREFIX
from .reduktion import stufe

ZEITRAEUME = ("tag", "woche", "monat", "jahr", "gesamt")


class UnbekannterZeitraum(ValueError):
    pass


def zeitraum_grenzen(schluessel: str, heute: date | None = None) -> tuple[date | None, date]:
    """Anfang (`None` = ohne Grenze) und Ende (heute) des Zeitraums."""
    heute = heute or date.today()
    if schluessel == "tag":
        return heute, heute
    if schluessel == "woche":
        return heute - timedelta(days=heute.weekday()), heute
    if schluessel == "monat":
        return heute.replace(day=1), heute
    if schluessel == "jahr":
        return heute.replace(month=1, day=1), heute
    if schluessel == "gesamt":
        return None, heute
    raise UnbekannterZeitraum(schluessel)


def _storniert_ids(session, bewegung_ids: list[int]) -> set[int]:
    """Von den gegebenen Bewegungen die, die per Gegenbuchung storniert
    wurden (gleiches Muster wie `ausbuchung.liste_ausbuchungen`)."""
    if not bewegung_ids:
        return set()
    gruende = [f"{STORNO_PREFIX}{bewegung_id}" for bewegung_id in bewegung_ids]
    treffer = session.scalars(
        select(Lagerbewegung.grund).where(Lagerbewegung.grund.in_(gruende))
    ).all()
    storniert_ids = set()
    for grund in treffer:
        storniert_ids.add(int(grund[len(STORNO_PREFIX):]))
    return storniert_ids


def _letzter_wareneingang_bis(session, artikel_id: int, lagerort_id: int, bis: date) -> date | None:
    """Wie `reduktion.letzter_wareneingang`, aber nur, was bis zu einem
    bestimmten Datum schon da war - für die Schätzung braucht es die Stufe,
    die zum Verkaufszeitpunkt galt, nicht die heutige."""
    aus_umlagerung = session.scalar(
        select(func.max(Lagerbewegung.eingangsdatum))
        .join(Variante, Variante.id == Lagerbewegung.varianten_id)
        .where(
            Variante.artikel_id == artikel_id,
            Lagerbewegung.lagerort_id == lagerort_id,
            Lagerbewegung.typ == "umlagerung",
            Lagerbewegung.eingangsdatum <= bis,
        )
    )
    aus_wareneingang = session.scalar(
        select(func.max(Wareneingang.eingangsdatum))
        .select_from(WareneingangPosition)
        .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
        .join(Variante, Variante.id == WareneingangPosition.varianten_id)
        .where(
            Variante.artikel_id == artikel_id,
            Wareneingang.lagerort_id == lagerort_id,
            WareneingangPosition.menge_eingetroffen > 0,
            Wareneingang.eingangsdatum <= bis,
        )
    )
    daten = [datum for datum in (aus_wareneingang, aus_umlagerung) if datum]
    return max(daten) if daten else None


def _geschaetzter_preis(session, variante_id: int, artikel_id: int, lagerort_id: int, zeitpunkt: date) -> Decimal | None:
    uvp = session.scalar(
        select(Preis.uvp)
        .where(Preis.varianten_id == variante_id, Preis.datum <= zeitpunkt)
        .order_by(Preis.datum.desc())
        .limit(1)
    )
    if uvp is None:
        uvp = session.scalar(
            select(Preis.uvp)
            .where(Preis.varianten_id == variante_id)
            .order_by(Preis.datum.asc().nulls_last())
            .limit(1)
        )
    if uvp is None:
        return None
    eingang = _letzter_wareneingang_bis(session, artikel_id, lagerort_id, zeitpunkt)
    prozent = stufe(eingang, zeitpunkt)
    return (Decimal(uvp) * (Decimal(100 - prozent) / Decimal(100))).quantize(Decimal("0.01"))


def auswertung(session, schluessel: str, lagerort_id: int | None = None, heute: date | None = None) -> dict:
    von, bis = zeitraum_grenzen(schluessel, heute)

    filter_ = [Lagerbewegung.typ == "verkauf"]
    if lagerort_id is not None:
        filter_.append(Lagerbewegung.lagerort_id == lagerort_id)
    if von is not None:
        filter_.append(
            Lagerbewegung.zeitpunkt >= datetime.combine(von, datetime.min.time(), tzinfo=timezone.utc)
        )
    filter_.append(
        Lagerbewegung.zeitpunkt < datetime.combine(bis + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    )

    zeilen = session.execute(
        select(Lagerbewegung, Variante, Artikel)
        .join(Variante, Variante.id == Lagerbewegung.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .where(*filter_)
    ).all()

    storniert = _storniert_ids(session, [bewegung.id for bewegung, *_ in zeilen])
    zeilen = [z for z in zeilen if z[0].id not in storniert]

    kategorie_ids = {artikel.kategorie_id for _, _, artikel in zeilen if artikel.kategorie_id}
    kategorien = {
        k.id: k for k in session.scalars(select(Kategorie).where(Kategorie.id.in_(kategorie_ids)))
    } if kategorie_ids else {}

    stueck_je_kategorie: dict[int | None, Decimal] = {}
    stueck_je_artikel: dict[int, Decimal] = {}
    einnahmen = Decimal("0")

    for bewegung, variante, artikel in zeilen:
        stueck = -Decimal(bewegung.menge)
        stueck_je_kategorie[artikel.kategorie_id] = stueck_je_kategorie.get(artikel.kategorie_id, Decimal("0")) + stueck
        stueck_je_artikel[artikel.id] = stueck_je_artikel.get(artikel.id, Decimal("0")) + stueck
        preis = _geschaetzter_preis(
            session, variante.id, artikel.id, bewegung.lagerort_id, bewegung.zeitpunkt.date()
        )
        if preis is not None:
            einnahmen += preis * stueck

    kategorien_liste = [
        {
            "kategorie_id": kategorie_id,
            "hauptgruppe": kategorien[kategorie_id].hauptgruppe if kategorie_id else None,
            "sportbereich": kategorien[kategorie_id].sportbereich if kategorie_id else None,
            "stueck": format(stueck.quantize(Decimal("0.01")), "f"),
        }
        for kategorie_id, stueck in sorted(
            stueck_je_kategorie.items(), key=lambda item: item[1], reverse=True
        )
    ]

    artikel_daten = {
        artikel.id: artikel for _, _, artikel in zeilen
    }
    bestand_je_artikel: dict[int, Decimal] = {}
    if stueck_je_artikel:
        bestand_filter = [Variante.artikel_id.in_(stueck_je_artikel)]
        if lagerort_id is not None:
            bestand_filter.append(Bestand.lagerort_id == lagerort_id)
        for artikel_id, menge in session.execute(
            select(Variante.artikel_id, func.coalesce(func.sum(Bestand.menge), 0))
            .join(Bestand, Bestand.varianten_id == Variante.id)
            .where(*bestand_filter)
            .group_by(Variante.artikel_id)
        ).all():
            bestand_je_artikel[artikel_id] = Decimal(menge)

    bestellempfehlung = [
        {
            "artikel_id": artikel_id,
            "marke": artikel_daten[artikel_id].marke,
            "bezeichnung": artikel_daten[artikel_id].bezeichnung,
            "lieferanten_artikelnr": artikel_daten[artikel_id].lieferanten_artikelnr,
            "verkauft": format(stueck.quantize(Decimal("0.01")), "f"),
            "bestand": format(bestand_je_artikel.get(artikel_id, Decimal("0")).quantize(Decimal("0.01")), "f"),
        }
        for artikel_id, stueck in sorted(
            stueck_je_artikel.items(), key=lambda item: item[1], reverse=True
        )
    ][:10]

    return {
        "zeitraum": {
            "schluessel": schluessel,
            "von": von.isoformat() if von else None,
            "bis": bis.isoformat(),
        },
        "kategorien": kategorien_liste,
        "einnahmen_geschaetzt": format(einnahmen.quantize(Decimal("0.01")), "f"),
        "einnahmen_ist_schaetzung": True,
        "bestellempfehlung": bestellempfehlung,
    }
