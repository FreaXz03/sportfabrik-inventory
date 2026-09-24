"""Ablauf „Lager": Ware kommt über GEWA in die Filialen, wird zwischen
Filialen umgelagert, verkauft/ausgebucht, rückgängig gemacht und gezählt;
Bestandsansicht, Ausbuchungsliste und Übersicht zeigen das Ergebnis.

Deckt Phase C (C2–C5), Regel 2, 6, 9 sowie D13, D17, F9–F11, F14, F15 über
die echte App mit Anmeldung ab.
"""

from datetime import date, timedelta
from decimal import Decimal

from conftest import ANNA, CHEF
from sqlalchemy import func, select, update
from testbelege import POSITIONEN, importieren, kopf, rechnung_pdf

from app.core.models import Bestand, Lagerbewegung, Variante
from app.services.reduktion import letzter_wareneingang

POLO_M = "4006632041234"


def _menge(sessions, varianten_id, lagerort_id):
    with sessions() as session:
        bestand = session.get(Bestand, (varianten_id, lagerort_id))
        return None if bestand is None else bestand.menge


def _uhr(sessions, varianten_id, lagerort_id):
    """Start der Reduktionsuhr (Regel 6) für diesen Artikel in dieser Filiale."""
    with sessions() as session:
        artikel_id = session.get(Variante, varianten_id).artikel_id
        return letzter_wareneingang(session, artikel_id, lagerort_id)


def _bestand_ist_summe_der_bewegungen(sessions):
    """Regel 2: der Bestand ist immer die Summe der Lagerbewegungen."""
    with sessions() as session:
        summen = {
            (varianten_id, lagerort_id): summe
            for varianten_id, lagerort_id, summe in session.execute(
                select(
                    Lagerbewegung.varianten_id,
                    Lagerbewegung.lagerort_id,
                    func.sum(Lagerbewegung.menge),
                ).group_by(Lagerbewegung.varianten_id, Lagerbewegung.lagerort_id)
            )
        }
        for bestand in session.scalars(select(Bestand)):
            schluessel = (bestand.varianten_id, bestand.lagerort_id)
            assert Decimal(summen.get(schluessel, 0)) == bestand.menge, schluessel


def test_gewa_filiale_umlagern_ausbuchen_zaehlen(welt):
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    sf1, sf2, gewa = codes["SF1"], codes["SF2"], codes["GEWA"]

    # Lieferung an die GEWA: Bestand dort, aber noch keine Uhr (D13).
    welt.anmelden(CHEF)
    assert importieren(client, rechnung_pdf(), lagerort_id=str(gewa)).status_code == 200
    polo = client.get(f"/api/erfassen/variante?ean={POLO_M}").json()["variante"]["varianten_id"]
    assert _menge(sessions, polo, gewa) == Decimal("5")
    assert _uhr(sessions, polo, gewa) is None

    # GEWA → SF1: die empfangende Filiale bucht (F5), die Mitarbeiterin darf.
    # Das Eingangsdatum wird erst jetzt gesetzt, auch rückwirkend (D13).
    welt.anmelden(ANNA)
    stamm = client.get("/api/umlagerung/stammdaten").json()
    assert stamm["ziel_aktiv"] == sf1
    antwort = client.post(
        "/api/umlagerung",
        json={
            "quelle_id": gewa,
            "eingangsdatum": "2026-08-10",
            "positionen": [{"varianten_id": polo, "menge": "2"}, {"varianten_id": polo, "menge": "1"}],
        },
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["ziel"]["code"] == "SF1" and antwort.json()["stueck"] == "3.00"
    assert _menge(sessions, polo, gewa) == Decimal("2")
    assert _menge(sessions, polo, sf1) == Decimal("3")
    assert _uhr(sessions, polo, sf1) == date(2026, 8, 10)
    # Unbekanntes Ziel wird abgelehnt.
    assert client.post(
        "/api/umlagerung",
        json={"quelle_id": gewa, "ziel_id": 999999, "positionen": [{"varianten_id": polo, "menge": "1"}]},
    ).status_code == 403

    # SF1 → SF2, die SF2 hatte den Artikel nie: Uhr startet beim Empfang (F11).
    welt.anmelden(CHEF)
    erste = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf1, "ziel_id": sf2, "positionen": [{"varianten_id": polo, "menge": "1"}]},
    )
    assert erste.status_code == 200, erste.text
    assert _uhr(sessions, polo, sf2) == date.today()
    # Zweite Umlagerung: jetzt kennt die SF2 den Artikel, die Uhr bleibt (F10),
    # und das ursprüngliche Eingangsdatum reist mit (D17).
    with sessions() as session:
        session.execute(
            update(Lagerbewegung)
            .where(Lagerbewegung.lagerort_id == sf2)
            .values(eingangsdatum=date(2026, 8, 12))
        )
        session.commit()
    zweite = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf1, "ziel_id": sf2, "positionen": [{"varianten_id": polo, "menge": "1"}]},
    )
    assert zweite.status_code == 200, zweite.text
    assert _uhr(sessions, polo, sf2) == date(2026, 8, 12)
    with sessions() as session:
        assert session.get(Bestand, (polo, sf2)).aeltestes_eingangsdatum == date(2026, 8, 10)
    # Zu wenig an der Quelle: gemeldet, trotzdem gebucht.
    knapp = client.post(
        "/api/umlagerung",
        json={"quelle_id": sf2, "ziel_id": sf1, "positionen": [{"varianten_id": polo, "menge": "3"}]},
    )
    assert knapp.status_code == 200 and knapp.json()["fehlbestand"]
    assert _menge(sessions, polo, sf2) == Decimal("-1")
    assert _menge(sessions, polo, sf1) == Decimal("4")

    # Ausbuchen per Scan: ein Scan = ein Stück (F15), Gründe nach F14.
    welt.anmelden(ANNA)
    assert client.get("/api/ausbuchen/stammdaten").json()["gruende"][0] == "verkauf"
    verkauf = client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "verkauf"})
    assert verkauf.status_code == 200, verkauf.text
    assert verkauf.json()["lagerort"]["code"] == "SF1"
    assert verkauf.json()["bestand_nachher"] == "3.00"
    for _ in range(3):
        client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "diebstahl"})
    # Zu wenig Bestand: warnen, trotzdem buchen (F9).
    minus = client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "defekt"})
    assert minus.status_code == 200 and minus.json()["bestand_reicht_nicht"] is True
    assert _menge(sessions, polo, sf1) == Decimal("-1")
    # Rückgängig ist eine Gegenbuchung, nur einmal.
    storno = client.post(f"/api/ausbuchen/{minus.json()['bewegung_id']}/storno")
    assert storno.status_code == 200
    assert client.post(f"/api/ausbuchen/{minus.json()['bewegung_id']}/storno").status_code == 409
    assert _menge(sessions, polo, sf1) == Decimal("0")
    # Fehler verständlich, nichts gebucht.
    assert client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "sonstiges"}).status_code == 409
    unbekannt = client.post("/api/ausbuchen", json={"ean": "7612345678900", "grund": "verkauf"})
    assert unbekannt.status_code == 409 and "7612345678900" in unbekannt.json()["detail"]
    sonstiges = client.post(
        "/api/ausbuchen", json={"ean": POLO_M, "grund": "sonstiges", "freitext": "Musterteil"}
    )
    assert sonstiges.status_code == 200

    # Liste der Ausbuchungen: Zeit, Person, Grund, Storno.
    liste = client.get("/api/ausbuchungen").json()
    assert liste["gewaehlt"] == sf1
    assert sorted(z["grund"] for z in liste["zeilen"]) == [
        "defekt", "diebstahl", "diebstahl", "diebstahl", "sonstiges: Musterteil", "verkauf"
    ]
    assert {z["benutzer_name"] for z in liste["zeilen"]} == {"Anna"}
    assert sum(z["storniert"] for z in liste["zeilen"]) == 1

    # Korrektur (C5): gezählte Menge eingeben, System bucht die Differenz.
    zaehlen = client.post(
        "/api/korrektur",
        json={"varianten_id": polo, "lagerort_id": sf1, "gezaehlt": "5", "grund": "inventur"},
    )
    assert zaehlen.status_code == 200, zaehlen.text
    assert zaehlen.json()["differenz"] == "6.00"
    assert _menge(sessions, polo, sf1) == Decimal("5")
    assert client.post(
        "/api/korrektur",
        json={"varianten_id": polo, "lagerort_id": sf1, "gezaehlt": "-3", "grund": "inventur"},
    ).status_code in (409, 422)

    # Bestandsansicht: aktive Filiale, Suche, alle Lagerorte (C2).
    eigene = client.get("/api/bestand").json()
    assert eigene["gewaehlt"] == sf1
    assert [(z["varianten_id"], z["menge"]) for z in eigene["zeilen"]] == [(polo, "5.00")]
    assert client.get("/api/bestand?q=Laufschuh").json()["zeilen"] == []
    alle = client.get("/api/bestand?alle=true").json()["zeilen"]
    assert {z["lagerort"]["code"] for z in alle} == {"SF1", "SF2", "GEWA"}
    assert any(z["lagerort"]["verkauf"] is False for z in alle)

    # Übersicht der aktiven Filiale.
    uebersicht = client.get("/api/dashboard")
    assert uebersicht.status_code == 200 and uebersicht.json()["filiale"]

    _bestand_ist_summe_der_bewegungen(sessions)

    # Ohne Anmeldung nichts.
    client.post("/logout")
    for pfad in ("/api/ausbuchen", "/api/umlagerung", "/api/korrektur"):
        assert client.post(pfad, json={}).status_code in (401, 422), pfad
    assert client.get("/api/bestand").status_code == 401
    assert client.get("/ausbuchen", follow_redirects=False).status_code == 303


def test_anstehend_fuehrt_zur_gefilterten_liste(welt):
    """Inbox 24.09.2026: ein Klick auf einen Punkt unter „Anstehend" zeigt
    genau die gezählten Einträge. Darum muss jede Zahl der Übersicht gleich
    der Trefferzahl der verlinkten, gefilterten Liste sein."""
    client, codes = welt.client, welt.codes
    heute = date.today()
    vor_40_monaten = date(heute.year - 3, heute.month, 1) - timedelta(days=150)  # > 36 Monate
    vor_20_monaten = date(heute.year - 2, heute.month, 1) + timedelta(days=150)  # 18–36 Monate
    welt.anmelden(CHEF)
    alt = rechnung_pdf(header_lines=kopf(nummer="9000000021", datum=vor_40_monaten.strftime("%d.%m.%Y")), rows=POSITIONEN[:2])
    mittel = rechnung_pdf(header_lines=kopf(nummer="9000000022", datum=vor_20_monaten.strftime("%d.%m.%Y")), rows=POSITIONEN[2:])
    assert importieren(client, alt, lagerort_id=str(codes["SF1"])).status_code == 200
    assert importieren(client, mittel, lagerort_id=str(codes["SF1"])).status_code == 200
    # Von Hand: ohne EAN und ohne Kategorie; eine Variante ins Minus.
    client.post("/api/erfassen", json={"positionen": [{"marke": "CMP", "bezeichnung": "Jacke", "menge": "1", "uvp": "99"}]})
    for _ in range(6):
        client.post("/api/ausbuchen", json={"ean": POLO_M, "grund": "verkauf"})

    uebersicht = client.get("/api/dashboard").json()
    filiale, stamm = uebersicht["filiale"], uebersicht["stamm"]
    assert filiale["negativ"] == 1
    assert stamm["ohne_ean"] == 1 and stamm["ohne_kategorie"] == 1
    assert filiale["reduktionen"]["70"]["faellig"] == 1  # Poloshirt L (M ist negativ)
    assert filiale["reduktionen"]["50"]["faellig"] == 1  # Laufschuh

    def treffer(pfad):
        antwort = client.get(pfad)
        assert antwort.status_code == 200, (pfad, antwort.text)
        return antwort.json()["total"]

    assert treffer("/api/articles?ohne_ean=true") == stamm["ohne_ean"]
    assert treffer("/api/articles?kategorie_fehlt=true") == stamm["ohne_kategorie"]
    assert treffer("/api/bestand?nur_negativ=true") == filiale["negativ"]
    for stufe in ("50", "70"):
        for stand in ("faellig", "bald"):
            pfad = f"/api/bestand?reduktion={stufe}&reduktion_status={stand}"
            assert treffer(pfad) == filiale["reduktionen"][stufe][stand], pfad
    zeilen = client.get("/api/bestand?reduktion=50&reduktion_status=faellig").json()["zeilen"]
    assert [z["bezeichnung"] for z in zeilen] == ["Laufschuh"]
    assert client.get("/api/bestand?reduktion=40&reduktion_status=faellig").status_code == 422
