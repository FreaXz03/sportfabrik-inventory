"""Übersicht (Redesign 29.09.2026): Reduktionsstufen des Bestands, Verkaufs-
verlauf der letzten 14 Tage und Bestseller der Woche - alles je aktive
Filiale (Regel 4/6)."""

from datetime import date, datetime, time, timedelta, timezone

from conftest import CHEF
from testbelege import importieren, kopf, rechnung_pdf

from sqlalchemy import select

from app.core.models import Artikel, Bestand, Kategorie, Lagerbewegung, Variante
from app.services.uebersicht import _monate_zurueck


def _zeile(nr, art, ean, bezeichnung, menge):
    return ["Nike", "224100", art, nr, ean, bezeichnung, menge, "Stk", "49.90", "20.00"]


def test_uebersicht_stufen_verlauf_bestseller(welt):
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    heute = date.today()
    welt.anmelden(CHEF)
    for nummer, monate, zeilen in [
        ("9000000061", 1, [_zeile("1", "D4", "5901234123457", "Cap", "4")]),
        ("9000000062", 20, [_zeile("2", "B2", "4006632041234", "Poloshirt", "5")]),
        ("9000000063", 40, [_zeile("3", "C3", "4006632041258", "Laufschuh", "2")]),
    ]:
        pdf = rechnung_pdf(
            header_lines=kopf(nummer=nummer, datum=_monate_zurueck(heute, monate).strftime("%d.%m.%Y")),
            rows=zeilen,
        )
        assert importieren(client, pdf, lagerort_id=str(codes["SF1"])).status_code == 200

    # Heute: 2 Caps und 1 Poloshirt verkauft; dazu vor 3 Tagen 3 Caps (direkt im Journal).
    for ean, anzahl in [("5901234123457", 2), ("4006632041234", 1)]:
        for _ in range(anzahl):
            assert client.post("/api/ausbuchen", json={"ean": ean, "grund": "verkauf"}).status_code == 200
    with sessions.begin() as session:
        cap = session.scalar(Variante.__table__.select().where(Variante.ean == "5901234123457").with_only_columns(Variante.id))
        vor_drei_tagen = datetime.combine(heute - timedelta(days=3), time(12, 0)).astimezone(timezone.utc)
        session.add(Lagerbewegung(lagerort_id=codes["SF1"], varianten_id=cap, typ="verkauf", menge=-3, zeitpunkt=vor_drei_tagen))

    filiale = client.get("/api/dashboard").json()["filiale"]

    # Stück im Bestand nach Stufe (Alter des letzten Eingangs): Cap 2 (30 %), Polo 4 (50 %), Laufschuh 2 (70 %).
    assert filiale["stufen"] == {"30": "2.00", "50": "4.00", "70": "2.00"}

    # Verlauf: 14 Tage, ältester zuerst, heute zuletzt.
    verlauf = filiale["verlauf"]
    assert len(verlauf) == 14
    assert verlauf[-1] == {"tag": heute.isoformat(), "verkauft": "3.00"}
    assert verlauf[0]["tag"] == (heute - timedelta(days=13)).isoformat()
    assert {v["tag"]: v["verkauft"] for v in verlauf}[(heute - timedelta(days=3)).isoformat()] == "3.00"
    assert sum(1 for v in verlauf if v["verkauft"] != "0.00") == 2

    # Bestseller der letzten 7 Tage: Cap 5, Poloshirt 1.
    assert [(b["bezeichnung"], b["stueck"]) for b in filiale["bestseller"]] == [("Cap", "5.00"), ("Poloshirt", "1.00")]

    # Redesign Phase 7: Bestand je Tag (30 Tage, heute zuletzt) und je Hauptgruppe.
    # Heute 11 eingebucht, 3 verkauft = 8. Dazu eine Korrektur +5 vor 3 Tagen
    # (Journal und Bestand gemeinsam, Regel 2) und Kategorien an zwei Modellen.
    with sessions.begin() as session:
        polo = session.scalar(select(Variante.id).where(Variante.ean == "4006632041234"))
        session.add(Lagerbewegung(lagerort_id=codes["SF1"], varianten_id=cap, typ="korrektur", menge=5, zeitpunkt=vor_drei_tagen))
        session.get(Bestand, (cap, codes["SF1"])).menge += 5
        textil = session.scalar(select(Kategorie.id).where(Kategorie.hauptgruppe == "Textil", Kategorie.sportbereich == "Running"))
        for variante in (cap, polo):
            session.get(Artikel, session.get(Variante, variante).artikel_id).kategorie_id = textil
    filiale = client.get("/api/dashboard").json()["filiale"]
    verlauf = filiale["bestandsverlauf"]
    assert len(verlauf) == 30
    assert verlauf[-1] == {"tag": heute.isoformat(), "bestand": "13.00"}
    je_tag = {v["tag"]: v["bestand"] for v in verlauf}
    assert je_tag[(heute - timedelta(days=1)).isoformat()] == "5.00"
    assert je_tag[(heute - timedelta(days=3)).isoformat()] == "5.00"
    # Vor 3 Tagen: +5 Korrektur und die weiter oben nur ins Journal gesetzten -3 Verkäufe,
    # darum steht der Vortag bei 5 - (5 - 3) = 3.
    assert je_tag[(heute - timedelta(days=4)).isoformat()] == "3.00"
    assert filiale["kategorien"] == [{"hauptgruppe": "Textil", "stueck": "13.00"}]
    # Cap ohne Kategorie (7 Stück): "ohne" steht zuletzt, auch wenn es mehr Stück sind.
    with sessions.begin() as session:
        session.get(Artikel, session.get(Variante, cap).artikel_id).kategorie_id = None
    ohne = client.get("/api/dashboard").json()["filiale"]["kategorien"]
    assert ohne == [
        {"hauptgruppe": "Textil", "stueck": "6.00"},
        {"hauptgruppe": None, "stueck": "7.00"},
    ]

    # Andere Filiale: nichts davon (Regel 4).
    welt.anmelden(CHEF)
    client.post("/api/active-lagerort", json={"lagerort_id": codes["SF2"]})
    sf2 = client.get("/api/dashboard").json()["filiale"]
    assert sf2["kategorien"] == []
    assert all(v["bestand"] == "0.00" for v in sf2["bestandsverlauf"])
    assert sf2["stufen"] == {"30": "0.00", "50": "0.00", "70": "0.00"}
    assert sf2["bestseller"] == []
    assert all(v["verkauft"] == "0.00" for v in sf2["verlauf"])
