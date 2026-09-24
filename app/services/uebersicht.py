"""Kennzahlen, anstehende Vorgänge und Aktuelles für die Übersicht
(Anforderungen vom 23.09.2026).

Alles bezieht sich auf **einen** Lagerort - die aktive Filiale -, ausser den
Stammdaten (Artikel, Belege), die filialübergreifend sind (Regel 4). Hier
wird nur gelesen.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, union_all

from ..core.models import (
    Artikel,
    Bestand,
    Dokument,
    Lagerbewegung,
    Lieferant,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from .reduktion import STUFEN

VORSCHAU_TAGE = 30
AKTUELLES_ANZAHL = 8


def _zahl(wert) -> str:
    return str(Decimal(wert or 0).quantize(Decimal("0.01")))


def _monate_zurueck(tag: date, monate: int) -> date:
    """Gleicher Kalendertag `monate` früher - am Monatsende auf den letzten
    Tag gekürzt (wie `reduktion.monate_seit` zählt)."""
    jahr, monat = divmod(tag.year * 12 + tag.month - 1 - monate, 12)
    monat += 1
    for tag_im_monat in range(tag.day, 0, -1):
        try:
            return date(jahr, monat, tag_im_monat)
        except ValueError:
            continue
    raise ValueError(tag)


def _letzte_eingaenge(lagerort_id: int):
    """Unterabfrage: je Artikel das Datum, ab dem die Reduktionsuhr in dieser
    Filiale läuft - letzter Wareneingang oder Umlagerung mit Eingangsdatum
    (dieselbe Regel wie `reduktion.letzter_wareneingang`, nur für alle
    Artikel auf einmal)."""
    aus_eingang = (
        select(Variante.artikel_id.label("artikel_id"), Wareneingang.eingangsdatum.label("datum"))
        .select_from(WareneingangPosition)
        .join(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
        .join(Variante, Variante.id == WareneingangPosition.varianten_id)
        .where(
            Wareneingang.lagerort_id == lagerort_id,
            WareneingangPosition.menge_eingetroffen > 0,
            Wareneingang.eingangsdatum.is_not(None),
        )
    )
    aus_umlagerung = (
        select(Variante.artikel_id.label("artikel_id"), Lagerbewegung.eingangsdatum.label("datum"))
        .select_from(Lagerbewegung)
        .join(Variante, Variante.id == Lagerbewegung.varianten_id)
        .where(
            Lagerbewegung.lagerort_id == lagerort_id,
            Lagerbewegung.typ == "umlagerung",
            Lagerbewegung.eingangsdatum.is_not(None),
        )
    )
    alle = union_all(aus_eingang, aus_umlagerung).subquery()
    return (
        select(alle.c.artikel_id, func.max(alle.c.datum).label("datum"))
        .group_by(alle.c.artikel_id)
        .subquery()
    )


def reduktions_varianten(session, lagerort_id: int, heute: date | None = None) -> dict:
    """Varianten mit Bestand in dieser Filiale, deren nächste Reduktionsstufe
    fällig ist oder in den nächsten `VORSCHAU_TAGE` Tagen fällig wird (Regel 6:
    18 Monate → 50 %, 36 Monate → 70 %; die Uhr läuft je Artikel).

    `{"50": {"faellig": [ids], "bald": [ids]}, "70": {...}}` - dieselbe
    Auswahl zählt die Übersicht und filtert die Bestandsliste, damit ein Klick
    auf „Anstehend" genau die gezählten Zeilen zeigt (24.09.2026)."""
    heute = heute or date.today()
    eingaenge = _letzte_eingaenge(lagerort_id)
    daten = session.execute(
        select(Variante.id, eingaenge.c.datum)
        .join(Bestand, Bestand.varianten_id == Variante.id)
        .join(eingaenge, eingaenge.c.artikel_id == Variante.artikel_id)
        .where(Bestand.lagerort_id == lagerort_id, Bestand.menge > 0)
    ).all()
    ergebnis = {}
    for monate, prozent in sorted(STUFEN):  # 18 → 50 %, dann 36 → 70 %
        grenze_heute = _monate_zurueck(heute, monate)
        grenze_bald = _monate_zurueck(heute + timedelta(days=VORSCHAU_TAGE), monate)
        naechste = [m for m, _ in sorted(STUFEN) if m > monate]
        obergrenze = _monate_zurueck(heute, naechste[0]) if naechste else None
        ergebnis[str(prozent)] = {
            "faellig": sorted(
                vid for vid, datum in daten
                if datum <= grenze_heute and (obergrenze is None or datum > obergrenze)
            ),
            "bald": sorted(vid for vid, datum in daten if grenze_heute < datum <= grenze_bald),
        }
    return ergebnis


def _reduktionen(session, lagerort_id: int, heute: date) -> dict:
    """Anzahl Varianten je Stufe - siehe `reduktions_varianten`."""
    return {
        stufe: {stand: len(ids) for stand, ids in je_stand.items()}
        for stufe, je_stand in reduktions_varianten(session, lagerort_id, heute).items()
    }


def filiale(session, lagerort_id: int, heute: date | None = None) -> dict:
    """Kennzahlen und anstehende Vorgänge der aktiven Filiale."""
    heute = heute or date.today()
    tagesbeginn = datetime.combine(heute, time.min).astimezone(timezone.utc)

    stueck, varianten = session.execute(
        select(func.coalesce(func.sum(Bestand.menge), 0), func.count()).where(
            Bestand.lagerort_id == lagerort_id, Bestand.menge > 0
        )
    ).one()
    negativ = session.scalar(
        select(func.count()).select_from(Bestand).where(
            Bestand.lagerort_id == lagerort_id, Bestand.menge < 0
        )
    )
    heute_je_typ = dict(
        session.execute(
            select(Lagerbewegung.typ, func.coalesce(func.sum(-Lagerbewegung.menge), 0))
            .where(
                Lagerbewegung.lagerort_id == lagerort_id,
                Lagerbewegung.typ.in_(("verkauf", "ausbuchung")),
                Lagerbewegung.zeitpunkt >= tagesbeginn,
            )
            .group_by(Lagerbewegung.typ)
        ).all()
    )
    erwartet = session.execute(
        select(Wareneingang.id, Wareneingang.lagerort_id, Dokument.dokumentnummer,
               Dokument.dokumentdatum, Lieferant.name)
        .outerjoin(Dokument, Dokument.id == Wareneingang.dokument_id)
        .outerjoin(Lieferant, Lieferant.id == Dokument.lieferant_id)
        .where(Wareneingang.status == "erwartet", Wareneingang.lagerort_id == lagerort_id)
        .order_by(Dokument.dokumentdatum.asc().nullslast(), Wareneingang.id)
    ).all()
    return {
        "stueck": _zahl(stueck),
        "varianten": int(varianten or 0),
        "verkauft_heute": _zahl(heute_je_typ.get("verkauf")),
        "abgaenge_heute": _zahl(heute_je_typ.get("ausbuchung")),
        "negativ": int(negativ or 0),
        "erwartet": [
            {
                "id": wareneingang_id,
                "dokumentnummer": nummer,
                "dokumentdatum": datum.isoformat() if datum else None,
                "lieferant": lieferant,
            }
            for wareneingang_id, _, nummer, datum, lieferant in erwartet[:5]
        ],
        "erwartet_total": len(erwartet),
        "reduktionen": _reduktionen(session, lagerort_id, heute),
    }


def aktuelles(session, lagerort_id: int | None, anzahl: int = AKTUELLES_ANZAHL) -> list[dict]:
    """Die letzten Bewegungen (Zugang, Verkauf, Abgang, Korrektur,
    Umlagerung) - in der Filiale oder, ohne Filiale, überall."""
    abfrage = (
        select(Lagerbewegung, Variante, Artikel)
        .join(Variante, Variante.id == Lagerbewegung.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .order_by(Lagerbewegung.zeitpunkt.desc(), Lagerbewegung.id.desc())
        .limit(anzahl)
    )
    if lagerort_id is not None:
        abfrage = abfrage.where(Lagerbewegung.lagerort_id == lagerort_id)
    return [
        {
            "zeitpunkt": bewegung.zeitpunkt.isoformat(),
            "typ": bewegung.typ,
            "grund": bewegung.grund,
            "menge": _zahl(bewegung.menge),
            "person": bewegung.benutzer_name or bewegung.benutzer_kassennummer,
            "marke": artikel.marke,
            "bezeichnung": artikel.bezeichnung,
            "farbe": variante.farbe,
            "groesse": variante.groesse,
        }
        for bewegung, variante, artikel in session.execute(abfrage).all()
    ]


def stamm(session) -> dict:
    """Filialübergreifende Zahlen zum Artikelstamm."""
    return {
        # Varianten, nicht Artikel: die Artikelliste zeigt eine Zeile je
        # Variante, und ein Klick soll genau so viele Zeilen zeigen.
        "ohne_kategorie": int(
            session.scalar(
                select(func.count())
                .select_from(Variante)
                .join(Artikel, Artikel.id == Variante.artikel_id)
                .where(Artikel.kategorie_id.is_(None))
            )
            or 0
        ),
        "ohne_ean": int(
            session.scalar(select(func.count()).select_from(Variante).where(Variante.ean.is_(None))) or 0
        ),
    }
