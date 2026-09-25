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
    Lagerort,
    Lieferant,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from .reduktion import STUFEN

VORSCHAU_TAGE = 30
AKTUELLES_ANZAHL = 8
# So viele Bewegungen werden höchstens gelesen, um daraus die Einträge zu bilden.
AKTUELLES_ZEILEN = 2000


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


def reduktions_liste(session, lagerort_id: int, heute: date | None = None) -> list[dict]:
    """Seite „Runterschreiben" (Phase D): dieselbe Auswahl wie
    `reduktions_varianten`, aber je Artikel (Modell) zusammengefasst - die
    Reduktionsuhr läuft je Lieferanten-Artikelnummer (Regel 6), und ein
    Runterschreiben betrifft alle Farben und Grössen des Modells.

    Reihenfolge: zuerst fällig (−70 %, dann −50 %), danach bald."""
    heute = heute or date.today()
    auswahl = reduktions_varianten(session, lagerort_id, heute)
    eingaenge = _letzte_eingaenge(lagerort_id)
    ergebnis = []
    for stand in ("faellig", "bald"):
        for stufe in ("70", "50"):
            ids = auswahl[stufe][stand]
            if not ids:
                continue
            zeilen = session.execute(
                select(
                    Artikel.id,
                    Artikel.marke,
                    Artikel.bezeichnung,
                    Artikel.lieferanten_artikelnr,
                    eingaenge.c.datum,
                    func.count(Variante.id),
                    func.sum(Bestand.menge),
                )
                .join(Variante, Variante.artikel_id == Artikel.id)
                .join(Bestand, Bestand.varianten_id == Variante.id)
                .join(eingaenge, eingaenge.c.artikel_id == Artikel.id)
                .where(Bestand.lagerort_id == lagerort_id, Variante.id.in_(ids))
                .group_by(Artikel.id, Artikel.marke, Artikel.bezeichnung, Artikel.lieferanten_artikelnr, eingaenge.c.datum)
                .order_by(Artikel.marke, Artikel.bezeichnung, Artikel.id)
            ).all()
            for artikel_id, marke, bezeichnung, nummer, datum, varianten, stueck in zeilen:
                ergebnis.append(
                    {
                        "artikel_id": artikel_id,
                        "marke": marke,
                        "bezeichnung": bezeichnung,
                        "lieferanten_artikelnr": nummer,
                        "eingang": datum.isoformat() if datum else None,
                        "stufe": int(stufe),
                        "stand": stand,
                        "varianten": int(varianten),
                        "stueck": _zahl(stueck),
                    }
                )
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
    """Das Wichtigste der letzten Zeit, zusammengefasst (Anforderung 8 vom
    24.09.2026): eine Lieferung als ganze Lieferung (`lieferung`), eine
    Umlagerung als ein Eintrag (`umlagerung`) und Abgänge mit anderem Grund
    als Verkauf einzeln (`abgang`). Verkäufe, Korrekturen und Zugänge ohne
    Wareneingang erscheinen nicht. In der Filiale oder, ohne Filiale,
    überall - eine Umlagerung dann nur einmal (über ihre Quellseite)."""
    abfrage = (
        select(Lagerbewegung, Variante, Artikel, Lagerort.code, WareneingangPosition.wareneingang_id,
               Dokument.dokumentnummer, Lieferant.name)
        .join(Variante, Variante.id == Lagerbewegung.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .join(Lagerort, Lagerort.id == Lagerbewegung.lagerort_id)
        .outerjoin(WareneingangPosition, WareneingangPosition.id == Lagerbewegung.wareneingang_position_id)
        .outerjoin(Wareneingang, Wareneingang.id == WareneingangPosition.wareneingang_id)
        .outerjoin(Dokument, Dokument.id == Wareneingang.dokument_id)
        .outerjoin(Lieferant, Lieferant.id == Dokument.lieferant_id)
        .where(
            (Lagerbewegung.typ == "ausbuchung")
            | (Lagerbewegung.typ == "umlagerung")
            | ((Lagerbewegung.typ == "zugang") & Lagerbewegung.wareneingang_position_id.is_not(None))
        )
        .order_by(Lagerbewegung.zeitpunkt.desc(), Lagerbewegung.id.desc())
        .limit(AKTUELLES_ZEILEN)
    )
    if lagerort_id is None:
        abfrage = abfrage.where(~((Lagerbewegung.typ == "umlagerung") & (Lagerbewegung.menge > 0)))
    else:
        abfrage = abfrage.where(Lagerbewegung.lagerort_id == lagerort_id)

    eintraege: dict[tuple, dict] = {}
    for bewegung, variante, artikel, code, wareneingang_id, nummer, lieferant in session.execute(abfrage).all():
        person = bewegung.benutzer_name or bewegung.benutzer_kassennummer
        basis = {"zeitpunkt": bewegung.zeitpunkt.isoformat(), "person": person}
        if bewegung.typ == "ausbuchung":
            schluessel = ("abgang", bewegung.id)
            eintraege[schluessel] = basis | {
                "art": "abgang",
                "lagerort": code,
                "grund": bewegung.grund,
                "menge": _zahl(bewegung.menge),
                "marke": artikel.marke,
                "bezeichnung": artikel.bezeichnung,
                "farbe": variante.farbe,
                "groesse": variante.groesse,
            }
            continue
        if bewegung.typ == "umlagerung":
            gegenseite = (bewegung.grund or "").split(":", 1)[-1]
            von, nach = (code, gegenseite) if bewegung.menge < 0 else (gegenseite, code)
            schluessel = ("umlagerung", bewegung.zeitpunkt, von, nach)
            neu = basis | {"art": "umlagerung", "von": von, "nach": nach}
        else:
            schluessel = ("lieferung", wareneingang_id, bewegung.zeitpunkt.date())
            neu = basis | {"art": "lieferung", "lagerort": code, "dokumentnummer": nummer, "lieferant": lieferant}
        eintrag = eintraege.get(schluessel)
        if eintrag is None:
            if len(eintraege) >= anzahl:
                continue
            eintrag = eintraege[schluessel] = neu | {"_stueck": Decimal(0), "_varianten": set()}
        eintrag["_stueck"] += abs(bewegung.menge)
        eintrag["_varianten"].add(variante.id)

    ergebnis = []
    for eintrag in list(eintraege.values())[:anzahl]:
        if "_stueck" in eintrag:
            eintrag["stueck"] = _zahl(eintrag.pop("_stueck"))
            eintrag["positionen"] = len(eintrag.pop("_varianten"))
        ergebnis.append(eintrag)
    return ergebnis


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
