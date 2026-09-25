"""Nachlieferungs-Hinweis (D-F2, 25.09.2026): Regel 6 lässt die
Reduktionsuhr beim nächsten Wareneingang für das ganze Modell neu starten -
der Bestand trennt keine Chargen. Statt den Bestand technisch aufzuteilen
(kein „muss", eine Mitteilung reicht), bekommt die Filiale nur einen Hinweis
auf der Übersicht, damit sie den Altbestand bei Bedarf von Hand über die
manuelle Reduktion wieder auf seine bisherige Stufe setzt.
"""

from datetime import date

from conftest import ANNA, CHEF
from testbelege import importieren, kopf, rechnung_pdf

from app.services import importer


def _zeile(art, nr, ean, bezeichnung, menge, uvp="49.90"):
    return ["Nike", "224100", art, nr, ean, bezeichnung, menge, "Stk", uvp, "20.00"]


def test_nachlieferung_erzeugt_hinweis(welt):
    client, codes = welt.client, welt.codes
    heute = date.today()
    welt.anmelden(CHEF)

    # Erste Lieferung vor 40 Monaten: Modell A1 ist längst auf 70% fällig.
    erste = rechnung_pdf(
        header_lines=kopf(nummer="9300000001", datum="01.01.2023"),
        rows=[_zeile("A1", "1", "4006632041234", "Poloshirt", "5")],
    )
    assert importieren(client, erste, lagerort_id=str(codes["SF1"])).status_code == 200

    # Noch keine Nachlieferung: kein Hinweis.
    welt.anmelden(ANNA)
    ohne_hinweis = client.get("/api/dashboard").json()
    assert ohne_hinweis["hinweise"] == []

    # Nachlieferung heute, gleiches Modell, gleiche Filiale: Hinweis.
    welt.anmelden(CHEF)
    zweite = rechnung_pdf(
        header_lines=kopf(nummer="9300000002", datum=heute.strftime("%d.%m.%Y")),
        rows=[_zeile("A1", "2", "4006632041241", "Poloshirt", "5")],
    )
    assert importieren(client, zweite, lagerort_id=str(codes["SF1"])).status_code == 200

    welt.anmelden(ANNA)
    mit_hinweis = client.get("/api/dashboard").json()["hinweise"]
    assert len(mit_hinweis) == 1
    assert mit_hinweis[0]["lieferanten_artikelnr"] == "A1"
    assert mit_hinweis[0]["alte_stufe"] == 70
    assert mit_hinweis[0]["typ"] == "nachlieferung_reduziert"

    # Andere Filiale: eigene Uhr, kein Altbestand dort - kein Hinweis.
    welt.anmelden(CHEF)
    dritte = rechnung_pdf(
        header_lines=kopf(nummer="9300000003", datum=heute.strftime("%d.%m.%Y")),
        rows=[_zeile("A1", "3", "4006632041258", "Poloshirt", "5")],
    )
    assert importieren(client, dritte, lagerort_id=str(codes["SF2"])).status_code == 200
    assert client.post("/api/active-lagerort", json={"lagerort_id": codes["SF2"]}).status_code == 200
    assert client.get("/api/dashboard").json()["hinweise"] == []

    # Erstlieferung eines neuen Modells: keine Vorgeschichte, kein Hinweis.
    neu = rechnung_pdf(
        header_lines=kopf(nummer="9300000004", datum=heute.strftime("%d.%m.%Y")),
        rows=[_zeile("Z9", "1", "4006632049999", "Neuware", "5")],
    )
    assert importieren(client, neu, lagerort_id=str(codes["SF1"])).status_code == 200
    assert client.post("/api/active-lagerort", json={"lagerort_id": codes["SF1"]}).status_code == 200
    hinweise = client.get("/api/dashboard").json()["hinweise"]
    assert [h["lieferanten_artikelnr"] for h in hinweise] == ["A1"]


def test_nachlieferung_ueber_ankunftsbestaetigung_erzeugt_hinweis(welt, monkeypatch):
    """Derselbe Hinweis auch über den zweiten Weg, wie Ware ins System kommt:
    eine Auftragsbestätigung, deren Ankunft erst später bestätigt wird
    (D6/D22)."""
    client, codes = welt.client, welt.codes
    heute = date.today()
    welt.anmelden(CHEF)

    # Altbestand: vor 40 Monaten geliefert, längst auf 70% fällig.
    erste = rechnung_pdf(
        header_lines=kopf(nummer="9400000001", datum="01.01.2023"),
        rows=[_zeile("A1", "1", "4006632041234", "Poloshirt", "5")],
    )
    assert importieren(client, erste, lagerort_id=str(codes["SF1"])).status_code == 200

    # Auftragsbestätigung für dasselbe Modell - erst nur angekündigt.
    original = importer.parse_with_parser
    monkeypatch.setattr(
        importer,
        "parse_with_parser",
        lambda *args, **kwargs: {**original(*args, **kwargs), "document_type": "auftragsbestaetigung"},
    )
    zweite = rechnung_pdf(
        header_lines=kopf(nummer="9400000002", datum=heute.strftime("%d.%m.%Y")),
        rows=[_zeile("A1", "2", "4006632041241", "Poloshirt", "5")],
    )
    assert importieren(client, zweite, lagerort_id=str(codes["SF1"])).status_code == 200

    welt.anmelden(ANNA)
    assert client.get("/api/dashboard").json()["hinweise"] == []

    # Ankunft bestätigen: erst jetzt zählt es als Nachlieferung.
    wareneingang_id = client.get("/api/wareneingaenge").json()["wareneingaenge"][0]["id"]
    position_id = client.get("/api/wareneingaenge").json()["wareneingaenge"][0]["positionen"][0]["id"]
    ankunft = client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft",
        json={"mengen": {str(position_id): "5"}},
    )
    assert ankunft.status_code == 200, ankunft.text

    hinweise = client.get("/api/dashboard").json()["hinweise"]
    assert len(hinweise) == 1
    assert hinweise[0]["lieferanten_artikelnr"] == "A1"
    assert hinweise[0]["alte_stufe"] == 70
