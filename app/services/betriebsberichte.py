"""Berichte für den Pilotbetrieb (Paket 3, Vorbereitung 01.10.2026).

* `pruefe_bestand`: `bestand` muss der Summe der `lagerbewegungen` entsprechen
  (Regel 2). Läuft täglich und nach jeder Wiederherstellung.
* `tagesabschluss`: was die App an einem Tag in einer Filiale gebucht hat - zum
  Abgleich mit dem Kassenbericht (täglich durch Fabian).
* `zaehlstatus`: Fortschritt der Eröffnungszählung - welche Bestandszeilen seit
  einem Zeitpunkt gezählt sind und welche noch fehlen.

Reine Lesezugriffe, nichts wird gebucht. Die Skripte unter `scripts/` rufen sie
auf (im Container: `docker compose exec app python scripts/...`).
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from ..core.models import (
    Artikel,
    Bestand,
    Lagerbewegung,
    Lagerort,
    Variante,
    Zaehlung,
)
from .ausbuchung import STORNO_PREFIX, zahl

ZEITZONE = ZoneInfo("Europe/Zurich")


def _zeile(variante: Variante, artikel: Artikel) -> dict:
    return {
        "varianten_id": variante.id,
        "ean": variante.ean,
        "marke": artikel.marke,
        "bezeichnung": artikel.bezeichnung,
        "lieferanten_artikelnr": artikel.lieferanten_artikelnr,
        "farbe": variante.farbe,
        "groesse": variante.groesse,
    }


def pruefe_bestand(session, lagerort_id: int | None = None) -> dict:
    """Vergleicht `bestand.menge` mit der Summe der Bewegungen je Variante und
    Lagerort. Eine Abweichung heisst: der Bestand wurde am Journal vorbei
    verändert (oder das Journal ist unvollständig). Ein negativer Bestand ist
    erlaubt (Entscheid 22.09.2026) und wird nur gezählt."""
    summen = (
        select(
            Lagerbewegung.varianten_id,
            Lagerbewegung.lagerort_id,
            func.sum(Lagerbewegung.menge).label("summe"),
        )
        .where(Lagerbewegung.bestandsart == "verkaufbar")
        .group_by(Lagerbewegung.varianten_id, Lagerbewegung.lagerort_id)
    )
    bestaende = select(Bestand.varianten_id, Bestand.lagerort_id, Bestand.menge)
    if lagerort_id is not None:
        summen = summen.where(Lagerbewegung.lagerort_id == lagerort_id)
        bestaende = bestaende.where(Bestand.lagerort_id == lagerort_id)

    aus_journal = {(v, lo): Decimal(s or 0) for v, lo, s in session.execute(summen)}
    gespeichert = {(v, lo): Decimal(m or 0) for v, lo, m in session.execute(bestaende)}
    abweichungen = []
    for schluessel in sorted(set(aus_journal) | set(gespeichert)):
        bestand = gespeichert.get(schluessel, Decimal(0))
        summe = aus_journal.get(schluessel, Decimal(0))
        if bestand != summe:
            abweichungen.append(
                {
                    "varianten_id": schluessel[0],
                    "lagerort_id": schluessel[1],
                    "bestand": zahl(bestand),
                    "summe_bewegungen": zahl(summe),
                }
            )
    # Gesperrter Bestand (Rückware in Prüfung, Paket 4) gegen seine eigenen Bewegungen.
    gesperrt_summen = (
        select(
            Lagerbewegung.varianten_id,
            Lagerbewegung.lagerort_id,
            func.sum(Lagerbewegung.menge),
        )
        .where(Lagerbewegung.bestandsart == "gesperrt")
        .group_by(Lagerbewegung.varianten_id, Lagerbewegung.lagerort_id)
    )
    gesperrt_bestaende = select(Bestand.varianten_id, Bestand.lagerort_id, Bestand.menge_gesperrt)
    if lagerort_id is not None:
        gesperrt_summen = gesperrt_summen.where(Lagerbewegung.lagerort_id == lagerort_id)
        gesperrt_bestaende = gesperrt_bestaende.where(Bestand.lagerort_id == lagerort_id)
    gesperrt_journal = {(v, lo): Decimal(m or 0) for v, lo, m in session.execute(gesperrt_summen)}
    gesperrt_gespeichert = {(v, lo): Decimal(m or 0) for v, lo, m in session.execute(gesperrt_bestaende)}
    for schluessel in sorted(set(gesperrt_journal) | set(gesperrt_gespeichert)):
        bestand = gesperrt_gespeichert.get(schluessel, Decimal(0))
        summe = gesperrt_journal.get(schluessel, Decimal(0))
        if bestand != summe:
            abweichungen.append(
                {
                    "varianten_id": schluessel[0],
                    "lagerort_id": schluessel[1],
                    "bestandsart": "gesperrt",
                    "bestand": zahl(bestand),
                    "summe_bewegungen": zahl(summe),
                }
            )
    return {
        "ok": not abweichungen,
        "geprueft": len(set(aus_journal) | set(gespeichert)),
        "negativ": sum(1 for menge in gespeichert.values() if menge < 0),
        "abweichungen": abweichungen,
    }


def _tagesgrenzen(tag: date) -> tuple[datetime, datetime]:
    """Beginn und Ende des Tages in Zürcher Zeit, als UTC (so ist gespeichert)."""
    start = datetime.combine(tag, time.min, tzinfo=ZEITZONE)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def tagesabschluss(session, lagerort_id: int, tag: date) -> dict:
    """Alle Bewegungen eines Tages in einer Filiale, zusammengefasst je Art und
    Variante. Verkäufe sind netto: ein stornierter Verkauf (Fehlscan) zählt
    nicht. Die Stornobuchung selbst erscheint nicht als Korrektur."""
    lagerort = session.get(Lagerort, lagerort_id)
    von, bis = _tagesgrenzen(tag)
    bewegungen = session.execute(
        select(Lagerbewegung, Variante, Artikel)
        .join(Variante, Variante.id == Lagerbewegung.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .where(
            Lagerbewegung.lagerort_id == lagerort_id,
            Lagerbewegung.zeitpunkt >= von,
            Lagerbewegung.zeitpunkt < bis,
        )
        .order_by(Lagerbewegung.id)
    ).all()

    # Welche Verkäufe/Ausbuchungen wurden (irgendwann) storniert? Nur deren
    # Gegenposten verschwinden aus dem Bericht (der Fehlscan zählt nicht). Die
    # Gegenbuchungen eines stornierten Belegs beziehen sich auf Zugänge: sie
    # bleiben sichtbar, damit der Zugang des Tages aufgeht.
    storno_ziele = {
        int(grund[len(STORNO_PREFIX):]): bewegung_id
        for bewegung_id, grund in session.execute(
            select(Lagerbewegung.id, Lagerbewegung.grund).where(
                Lagerbewegung.grund.like(f"{STORNO_PREFIX}%")
            )
        )
        if grund[len(STORNO_PREFIX):].isdigit()
    }
    typ_des_ziels = (
        dict(
            session.execute(
                select(Lagerbewegung.id, Lagerbewegung.typ).where(
                    Lagerbewegung.id.in_(storno_ziele)
                )
            ).all()
        )
        if storno_ziele
        else {}
    )
    storniert = {
        ziel for ziel in storno_ziele if typ_des_ziels.get(ziel) in ("verkauf", "ausbuchung")
    }

    summen: dict[tuple, dict] = {}
    for bewegung, variante, artikel in bewegungen:
        grund = bewegung.grund or ""
        if (
            bewegung.typ == "korrektur"
            and grund.startswith(STORNO_PREFIX)
            and grund[len(STORNO_PREFIX):].isdigit()
            and int(grund[len(STORNO_PREFIX):]) in storniert
        ):
            continue  # der Gegenposten eines stornierten Verkaufs: schon abgezogen
        if bewegung.typ in ("verkauf", "ausbuchung") and bewegung.id in storniert:
            continue
        if bewegung.typ in ("verkauf", "ausbuchung"):
            art, menge = bewegung.typ, -Decimal(bewegung.menge)
            text = "" if bewegung.typ == "verkauf" else grund
        elif bewegung.typ == "umlagerung":
            art = "umlagerung"
            menge, text = Decimal(bewegung.menge), grund
        else:
            art, menge = bewegung.typ, Decimal(bewegung.menge)
            text = grund if art == "korrektur" else ""
        schluessel = (art, variante.id, text)
        eintrag = summen.setdefault(
            schluessel, {"art": art, **_zeile(variante, artikel), "menge": Decimal(0), "grund": text}
        )
        eintrag["menge"] += menge

    zeilen = [
        {**eintrag, "menge": zahl(eintrag["menge"])}
        for eintrag in sorted(
            summen.values(),
            key=lambda e: (e["art"], e["marke"] or "", e["bezeichnung"] or "", e["varianten_id"]),
        )
    ]
    verkauft = sum(
        (Decimal(z["menge"]) for z in zeilen if z["art"] == "verkauf"), Decimal(0)
    )
    zaehlungen = session.scalar(
        select(func.count())
        .select_from(Zaehlung)
        .where(
            Zaehlung.lagerort_id == lagerort_id, Zaehlung.zeitpunkt >= von, Zaehlung.zeitpunkt < bis
        )
    )
    return {
        "lagerort": {"id": lagerort.id, "code": lagerort.code, "name": lagerort.name},
        "tag": tag.isoformat(),
        "verkauft_stueck": zahl(verkauft),
        "zaehlungen": zaehlungen or 0,
        "zeilen": zeilen,
    }


def zaehlstatus(session, lagerort_id: int, seit: datetime) -> dict:
    """Eröffnungszählung: Bestandszeilen mit Menge ≠ 0 (die leeren gibt es im
    Regal nicht zu zählen), davon seit `seit` gezählt (`zaehlungen`, auch ohne
    Differenz) und die noch offenen mit ihrem Bestand."""
    if seit.tzinfo is None:
        seit = seit.replace(tzinfo=ZEITZONE)
    seit = seit.astimezone(timezone.utc)
    gezaehlt_ids = set(
        session.scalars(
            select(Zaehlung.varianten_id)
            .where(Zaehlung.lagerort_id == lagerort_id, Zaehlung.zeitpunkt >= seit)
            .distinct()
        )
    )
    zeilen = session.execute(
        select(Bestand, Variante, Artikel)
        .join(Variante, Variante.id == Bestand.varianten_id)
        .join(Artikel, Artikel.id == Variante.artikel_id)
        .where(Bestand.lagerort_id == lagerort_id, Bestand.menge != 0)
        .order_by(Artikel.marke, Artikel.bezeichnung, Variante.id)
    ).all()
    offen = [
        {**_zeile(variante, artikel), "bestand": zahl(bestand.menge)}
        for bestand, variante, artikel in zeilen
        if variante.id not in gezaehlt_ids
    ]
    return {
        "zeilen": len(zeilen),
        "gezaehlt": len(zeilen) - len(offen),
        "offen": len(offen),
        "offen_stueck": zahl(sum((Decimal(z["bestand"]) for z in offen), Decimal(0))),
        "offen_liste": offen,
    }
