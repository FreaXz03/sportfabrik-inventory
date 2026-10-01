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
    DokumentLieferung,
    Kategorie,
    Lagerbewegung,
    Lagerort,
    Lieferant,
    ReduktionEmpfehlungZentrale,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from .reduktion import STUFEN, stufe as reduktionsstufe
from .reduktion_bestaetigung import bestaetigte_stufen

VORSCHAU_TAGE = 30
AKTUELLES_ANZAHL = 8
# So viele Bewegungen werden höchstens gelesen, um daraus die Einträge zu bilden.
AKTUELLES_ZEILEN = 2000
VERLAUF_TAGE = 14
BESTAND_TAGE = 30
BESTSELLER_TAGE = 7
BESTSELLER_ANZAHL = 5


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
            bestaetigt = (
                bestaetigte_stufen(session, lagerort_id, (a for a, *_ in zeilen))
                if stand == "faellig"
                else {}
            )
            for artikel_id, marke, bezeichnung, nummer, datum, varianten, stueck in zeilen:
                if stand == "faellig" and bestaetigt.get(artikel_id) == int(stufe):
                    continue
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


def _tagesbeginn(tag: date) -> datetime:
    return datetime.combine(tag, time.min).astimezone(timezone.utc)


def stufen_verteilung(session, lagerort_id: int, heute: date) -> dict:
    """Stück im Bestand je Reduktionsstufe (Alter des letzten Eingangs, Regel
    6). Bestand ohne Eingangsdatum zählt nicht - dort läuft keine Uhr."""
    eingaenge = _letzte_eingaenge(lagerort_id)
    zeilen = session.execute(
        select(eingaenge.c.datum, func.sum(Bestand.menge))
        .select_from(Bestand)
        .join(Variante, Variante.id == Bestand.varianten_id)
        .join(eingaenge, eingaenge.c.artikel_id == Variante.artikel_id)
        .where(Bestand.lagerort_id == lagerort_id, Bestand.menge > 0)
        .group_by(eingaenge.c.datum)
    ).all()
    summen = {"30": Decimal(0), "50": Decimal(0), "70": Decimal(0)}
    for datum, stueck in zeilen:
        summen[str(reduktionsstufe(datum, heute))] += stueck
    return {stufe: _zahl(menge) for stufe, menge in summen.items()}


def verkaufsverlauf(session, lagerort_id: int, heute: date) -> list[dict]:
    """Verkaufte Stück je Tag der letzten `VERLAUF_TAGE` Tage, ältester
    zuerst, heute zuletzt (Tage ohne Verkauf mit 0)."""
    tage = [heute - timedelta(days=i) for i in range(VERLAUF_TAGE - 1, -1, -1)]
    summen = {tag: Decimal(0) for tag in tage}
    for zeitpunkt, menge in session.execute(
        select(Lagerbewegung.zeitpunkt, Lagerbewegung.menge).where(
            Lagerbewegung.lagerort_id == lagerort_id,
            Lagerbewegung.typ == "verkauf",
            Lagerbewegung.zeitpunkt >= _tagesbeginn(tage[0]),
        )
    ):
        if zeitpunkt.tzinfo is None:  # SQLite liefert UTC ohne Zeitzone
            zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
        tag = zeitpunkt.astimezone().date()
        if tag in summen:
            summen[tag] -= menge
    return [{"tag": tag.isoformat(), "verkauft": _zahl(summen[tag])} for tag in tage]


def bestandsverlauf(session, lagerort_id: int, heute: date, tage_anzahl: int = BESTAND_TAGE) -> list[dict]:
    """Stück im Bestand am Ende jedes der letzten `tage_anzahl` Tage, ältester
    zuerst, heute zuletzt. Aus dem Journal rückwärts gerechnet (Regel 2): der
    heutige Stand ist die Summe des Bestands, jeder Tag davor ist der Stand
    des Folgetags minus dessen Bewegungen."""
    tage = [heute - timedelta(days=i) for i in range(tage_anzahl - 1, -1, -1)]
    stand = Decimal(
        session.scalar(select(func.coalesce(func.sum(Bestand.menge), 0)).where(Bestand.lagerort_id == lagerort_id))
    )
    je_tag = {tag: Decimal(0) for tag in tage}
    for zeitpunkt, menge in session.execute(
        select(Lagerbewegung.zeitpunkt, Lagerbewegung.menge).where(
            Lagerbewegung.lagerort_id == lagerort_id,
            Lagerbewegung.zeitpunkt >= _tagesbeginn(tage[0]),
        )
    ):
        if zeitpunkt.tzinfo is None:  # SQLite liefert UTC ohne Zeitzone
            zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
        tag = zeitpunkt.astimezone().date()
        if tag in je_tag:
            je_tag[tag] += menge
    ergebnis = []
    for tag in reversed(tage):
        ergebnis.append({"tag": tag.isoformat(), "bestand": _zahl(stand)})
        stand -= je_tag[tag]
    return list(reversed(ergebnis))


def kategorien_verteilung(session, lagerort_id: int) -> list[dict]:
    """Stück im Bestand je Hauptgruppe der Kassenkategorie (Regel 8), grösste
    zuerst; Artikel ohne Kategorie als `hauptgruppe: None`."""
    zeilen = session.execute(
        select(Kategorie.hauptgruppe, func.sum(Bestand.menge))
        .select_from(Bestand)
        .join(Variante, Variante.id == Bestand.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .outerjoin(Kategorie, Kategorie.id == Artikel.kategorie_id)
        .where(Bestand.lagerort_id == lagerort_id, Bestand.menge > 0)
        .group_by(Kategorie.hauptgruppe)
    ).all()
    # Ohne Kategorie immer zuletzt, sonst nach Menge, bei Gleichstand nach Name.
    zeilen.sort(key=lambda z: (z[0] is None, -z[1], z[0] or ""))
    return [{"hauptgruppe": gruppe, "stueck": _zahl(menge)} for gruppe, menge in zeilen]


def bestand_gruppen(session, lagerort_id: int) -> dict:
    """Stück im Bestand je Hauptgruppe, aufgeschlüsselt nach Sportbereich
    (Regel 8; 2026-10-01, Kreisdiagramme der Statistik). Artikel ohne
    Kategorie fehlen hier - sie stehen in `kategorien_verteilung`. Velo und
    Food haben keinen Sportbereich (`None`)."""
    zeilen = session.execute(
        select(Kategorie.hauptgruppe, Kategorie.sportbereich, func.sum(Bestand.menge))
        .select_from(Bestand)
        .join(Variante, Variante.id == Bestand.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .join(Kategorie, Kategorie.id == Artikel.kategorie_id)
        .where(Bestand.lagerort_id == lagerort_id, Bestand.menge > 0)
        .group_by(Kategorie.hauptgruppe, Kategorie.sportbereich)
    ).all()
    zeilen.sort(key=lambda z: (z[0], -z[2], z[1] or ""))
    gruppen: dict[str, list[dict]] = {}
    for hauptgruppe, sportbereich, menge in zeilen:
        gruppen.setdefault(hauptgruppe, []).append({"sportbereich": sportbereich, "stueck": _zahl(menge)})
    return gruppen


VERLAUF_PERIODEN = (7, 30, 180)


def _prozent(jetzt: Decimal | int, vorher: Decimal | int) -> float | None:
    """Änderung in Prozent gegenüber `vorher`; ohne Basis (0) keine Zahl erfinden."""
    if not vorher:
        return None
    # abs(): bei negativem Bestand (erlaubt) zeigt ein Anstieg trotzdem nach oben.
    return round(float((jetzt - vorher) / abs(vorher) * 100), 1)


def verlaeufe(session, lagerort_id: int | None, tage: int, heute: date | None = None) -> dict:
    """Bestand (aktive Filiale) und neu erfasste Artikelvarianten (ganzer
    Stamm, nach erster Lieferung) der letzten `tage` Tage, je mit Vergleich
    zur Periode davor: Bestand am Ende gegen Bestand am Ende der Vorperiode,
    neue Varianten gegen die der Vorperiode (2026-10-01)."""
    heute = heute or date.today()
    ergebnis: dict = {"tage": tage, "bestand": None}
    if lagerort_id is not None:
        # Ein Tag mehr: der erste Punkt ist der Stand am Ende der Vorperiode.
        punkte = bestandsverlauf(session, lagerort_id, heute, tage + 1)
        vorher, jetzt = Decimal(punkte[0]["bestand"]), Decimal(punkte[-1]["bestand"])
        ergebnis["bestand"] = {
            "reihe": punkte[1:],
            "jetzt": _zahl(jetzt),
            "vorher": _zahl(vorher),
            "prozent": _prozent(jetzt, vorher),
        }
    tage_liste = [heute - timedelta(days=i) for i in range(2 * tage - 1, -1, -1)]
    je_tag = {tag: 0 for tag in tage_liste}
    for erste, anzahl in session.execute(
        select(Variante.first_seen, func.count())
        .where(Variante.first_seen >= tage_liste[0], Variante.first_seen <= heute)
        .group_by(Variante.first_seen)
    ):
        je_tag[erste] = anzahl
    summe = sum(je_tag[tag] for tag in tage_liste[tage:])
    vorher_summe = sum(je_tag[tag] for tag in tage_liste[:tage])
    ergebnis["neu"] = {
        "reihe": [{"tag": tag.isoformat(), "anzahl": je_tag[tag]} for tag in tage_liste[tage:]],
        "summe": summe,
        "vorher": vorher_summe,
        "prozent": _prozent(summe, vorher_summe),
    }
    return ergebnis


def bestseller(session, lagerort_id: int, heute: date) -> list[dict]:
    """Meistverkaufte Artikel (Modelle) der letzten `BESTSELLER_TAGE` Tage."""
    stueck = func.sum(-Lagerbewegung.menge)
    zeilen = session.execute(
        select(Artikel.id, Artikel.marke, Artikel.bezeichnung, stueck)
        .select_from(Lagerbewegung)
        .join(Variante, Variante.id == Lagerbewegung.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .where(
            Lagerbewegung.lagerort_id == lagerort_id,
            Lagerbewegung.typ == "verkauf",
            Lagerbewegung.zeitpunkt >= _tagesbeginn(heute - timedelta(days=BESTSELLER_TAGE - 1)),
        )
        .group_by(Artikel.id, Artikel.marke, Artikel.bezeichnung)
        .order_by(stueck.desc(), Artikel.marke, Artikel.bezeichnung, Artikel.id)
        .limit(BESTSELLER_ANZAHL)
    ).all()
    return [
        {"artikel_id": artikel_id, "marke": marke, "bezeichnung": bezeichnung, "stueck": _zahl(menge)}
        for artikel_id, marke, bezeichnung, menge in zeilen
    ]


def _empfehlungen_offen(session, lagerort_id: int) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ReduktionEmpfehlungZentrale)
            .where(
                ReduktionEmpfehlungZentrale.lagerort_id == lagerort_id,
                ReduktionEmpfehlungZentrale.status == "offen",
            )
        )
        or 0
    )


def meldungen_filiale(session, lagerort_id: int, heute: date | None = None) -> dict:
    """Nur was die Glocke zum Zählen braucht - viel leichter als `filiale()`,
    weil sie bei jedem Seitenaufruf läuft."""
    return {
        "erwartet_total": int(
            session.scalar(
                select(func.count())
                .select_from(Wareneingang)
                .where(Wareneingang.status == "erwartet", Wareneingang.lagerort_id == lagerort_id)
            )
            or 0
        ),
        "negativ": int(
            session.scalar(
                select(func.count()).select_from(Bestand).where(
                    Bestand.lagerort_id == lagerort_id, Bestand.menge < 0
                )
            )
            or 0
        ),
        "empfehlungen_offen": _empfehlungen_offen(session, lagerort_id),
        "reduktionen": _reduktionen(session, lagerort_id, heute or date.today()),
    }


def filiale(session, lagerort_id: int, heute: date | None = None) -> dict:
    """Kennzahlen und anstehende Vorgänge der aktiven Filiale."""
    heute = heute or date.today()
    tagesbeginn = _tagesbeginn(heute)

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
        # Offene Empfehlungen der Zentrale für diese Filiale, sofort - auch mit
        # Datum in der Zukunft und ohne Bestand (Entscheid 30.09.2026).
        "empfehlungen_offen": _empfehlungen_offen(session, lagerort_id),
        "reduktionen": _reduktionen(session, lagerort_id, heute),
        "stufen": stufen_verteilung(session, lagerort_id, heute),
        "verlauf": verkaufsverlauf(session, lagerort_id, heute),
        "bestseller": bestseller(session, lagerort_id, heute),
        "bestandsverlauf": bestandsverlauf(session, lagerort_id, heute),
        "kategorien": kategorien_verteilung(session, lagerort_id),
        "bestand_gruppen": bestand_gruppen(session, lagerort_id),
    }


def ziel_filialen(session, dokument_ids: list[int]) -> dict[int, str | None]:
    """Code der Filiale, in die ein Beleg importiert wurde („Zuletzt importiert",
    2026-10-01): sein eigener Wareneingang oder - bei einem Beleg, der nur an
    eine Lieferung angehängt ist - der Wareneingang dieser Lieferung."""
    if not dokument_ids:
        return {}
    eigene = select(Wareneingang.dokument_id.label("dokument_id"), Lagerort.code.label("code")).join(
        Lagerort, Lagerort.id == Wareneingang.lagerort_id
    ).where(Wareneingang.dokument_id.in_(dokument_ids))
    angehaengt = (
        select(DokumentLieferung.dokument_id.label("dokument_id"), Lagerort.code.label("code"))
        .join(Wareneingang, Wareneingang.id == DokumentLieferung.wareneingang_id)
        .join(Lagerort, Lagerort.id == Wareneingang.lagerort_id)
        .where(DokumentLieferung.dokument_id.in_(dokument_ids))
    )
    codes: dict[int, set[str]] = {}
    for dokument_id, code in session.execute(union_all(eigene, angehaengt)):
        codes.setdefault(dokument_id, set()).add(code)
    return {dokument_id: ", ".join(sorted(codes[dokument_id])) if dokument_id in codes else None for dokument_id in dokument_ids}


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


def varianten_mit_bestand(lagerort_id: int):
    """Bedingung: die Variante hat in diesem Lagerort Bestand (auch negativen)
    - so gehört eine Lücke im Artikelstamm zu dieser Filiale."""
    return (
        select(Bestand.varianten_id)
        .where(Bestand.lagerort_id == lagerort_id, Bestand.menge != 0)
        .scalar_subquery()
    )


def stamm(session) -> dict:
    """Lücken im Artikelstamm für „Anstehend". Der Artikelstamm gehört allen
    Filialen (Regel 4): Entscheid 29.09.2026 - die beiden Zahlen zählen den
    ganzen Stamm, für alle Rollen in jeder Filiale."""
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
        "ohne_ean": int(session.scalar(select(func.count()).select_from(Variante).where(Variante.ean.is_(None))) or 0),
    }


def liste_meldungen(filiale_daten: dict | None, stamm_daten: dict) -> list[dict]:
    """Die Punkte unter „Anstehend" mit Ziel, in der Reihenfolge von
    anstehend-liste.js (Glocke und Popup, 2026-10-01). Ohne aktive Filiale
    zählen nur die Stammdaten-Hinweise."""
    meldungen: list[dict] = []

    def punkt(art: str, anzahl: int, href: str, dringend: bool = False, **extra) -> None:
        if anzahl:
            meldungen.append({"art": art, "anzahl": anzahl, "href": href, "dringend": dringend, **extra})

    if filiale_daten:
        punkt("expected", filiale_daten["erwartet_total"], "/wareneingaenge")
        punkt("recommendations", filiale_daten["empfehlungen_offen"], "/runterschreiben#empfehlungPanel")
        punkt("negative", filiale_daten["negativ"], "/bestand?nur_negativ=true", True)
        for name in ("70", "50"):
            stufe = filiale_daten["reduktionen"].get(name, {})
            ziel = f"/bestand?reduktion={name}&reduktion_status="
            punkt("reduction_due", stufe.get("faellig", 0), ziel + "faellig", True, stufe=name)
            punkt("reduction_soon", stufe.get("bald", 0), ziel + "bald", False, stufe=name)
    punkt("no_category", stamm_daten["ohne_kategorie"], "/articles?kategorie_fehlt=true")
    punkt("no_ean", stamm_daten["ohne_ean"], "/articles?ohne_ean=true")
    return meldungen


def anzahl_meldungen(filiale_daten: dict | None, stamm_daten: dict) -> int:
    """Zahl der Punkte unter „Anstehend" - ein Punkt je Meldung, genau wie
    anstehend-liste.js sie zeichnet (Glocke, 30.09.2026)."""
    return len(liste_meldungen(filiale_daten, stamm_daten))
