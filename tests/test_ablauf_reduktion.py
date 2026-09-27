"""Ablauf „Runterschreiben" (Phase D, Teil 1): die Filiale sieht, welche
Artikel −50 % bzw. −70 % erreicht haben oder in den nächsten 30 Tagen
erreichen, und druckt dafür gleich die Etiketten.

Regel 6 / D5: gerechnet je Filiale ab dem letzten Wareneingang derselben
Lieferanten-Artikelnummer (Modell); nur Ware mit Bestand zählt.
"""

from datetime import date, timedelta

import pymupdf
from conftest import ANNA, CHEF
from sqlalchemy import select
from testbelege import importieren, kopf, rechnung_pdf

from app.core.models import Artikel
from app.services.etikett import MM
from app.services.uebersicht import _monate_zurueck


def _zeile(nr, art, ean, bezeichnung, menge, uvp="49.90"):
    return ["Nike", "224100", art, nr, ean, bezeichnung, menge, "Stk", uvp, "20.00"]


def test_runterschreiben_liste_und_etiketten(welt):
    client, codes = welt.client, welt.codes
    heute = date.today()
    lieferungen = [
        # (Belegnummer, Eingang, Lagerort, Zeilen)
        ("9000000041", _monate_zurueck(heute, 40), "SF1", [
            _zeile("1", "A1", "4006632041234", "Poloshirt", "5"),
            _zeile("2", "A1", "4006632041241", "Poloshirt", "3"),
        ]),
        ("9000000042", _monate_zurueck(heute, 20), "SF1", [_zeile("3", "B2", "4006632041258", "Laufschuh", "2", "129.00")]),
        # Erreicht 18 Monate in 10 Tagen: „bald".
        ("9000000043", _monate_zurueck(heute + timedelta(days=10), 18), "SF1", [_zeile("4", "C3", "4006381333931", "Hoodie", "1")]),
        ("9000000044", _monate_zurueck(heute, 1), "SF1", [_zeile("5", "D4", "5901234123457", "Cap", "4")]),
        # Alte Ware in einer anderen Filiale erscheint in SF1 nicht.
        ("9000000045", _monate_zurueck(heute, 40), "SF2", [_zeile("6", "E5", "96385074", "Rucksack", "1")]),
    ]
    welt.anmelden(CHEF)
    for nummer, eingang, lagerort, zeilen in lieferungen:
        pdf = rechnung_pdf(header_lines=kopf(nummer=nummer, datum=eingang.strftime("%d.%m.%Y")), rows=zeilen)
        antwort = importieren(client, pdf, lagerort_id=str(codes[lagerort]))
        assert antwort.status_code == 200, antwort.text

    # Mitarbeiter dürfen die Liste sehen und drucken (Regel 9).
    welt.anmelden(ANNA)
    assert client.get("/runterschreiben").status_code == 200
    liste = client.get("/api/reduktionen").json()
    assert liste["lagerort"]["code"] == "SF1"
    zeilen = [(a["lieferanten_artikelnr"], a["stufe"], a["stand"], a["stueck"], a["varianten"]) for a in liste["artikel"]]
    assert zeilen == [
        ("A1", 70, "faellig", "8.00", 2),
        ("B2", 50, "faellig", "2.00", 1),
        ("C3", 50, "bald", "1.00", 1),
    ]
    polo = liste["artikel"][0]
    assert polo["bezeichnung"] == "Poloshirt" and polo["eingang"] == _monate_zurueck(heute, 40).isoformat()
    assert polo["rolle"] == {"prozent": 70, "farbe": "gruen"}
    assert liste["artikel"][1]["rolle"] == {"prozent": 50, "farbe": "rot"}

    # Andere Filiale wählbar (alle dürfen alles lesen, F3).
    sf2 = client.get(f"/api/reduktionen?lagerort_id={codes['SF2']}").json()["artikel"]
    assert [a["lieferanten_artikelnr"] for a in sf2] == ["E5"]

    # Etiketten für alle Stück eines Artikels in der Filiale, Rolle −70 %.
    etiketten = client.get(f"/api/artikel/{polo['artikel_id']}/etiketten.pdf?reduktion=70")
    assert etiketten.status_code == 200, etiketten.text
    with pymupdf.open(stream=etiketten.content, filetype="pdf") as pdf:
        assert pdf.page_count == 8
        assert (round(pdf[0].rect.width / MM), round(pdf[0].rect.height / MM)) == (47, 83)
        assert "49.90" in pdf[0].get_text()
    # Ohne Bestand kein Etikett; unbekannter Artikel 404; falsche Stufe 422.
    with welt.sessions() as session:
        rucksack = session.scalar(select(Artikel.id).where(Artikel.lieferanten_artikelnr == "E5"))
    assert client.get(f"/api/artikel/{rucksack}/etiketten.pdf?reduktion=70").status_code == 404
    assert client.get("/api/artikel/999999/etiketten.pdf?reduktion=70").status_code == 404
    assert client.get(f"/api/artikel/{polo['artikel_id']}/etiketten.pdf?reduktion=40").status_code == 422

    # Ohne Anmeldung nichts.
    client.post("/logout")
    assert client.get("/api/reduktionen").status_code == 401
    assert client.get("/runterschreiben", follow_redirects=False).status_code == 303


def test_manuelle_reduktion_je_filiale(welt):
    """Manuelle Reduktion (24.09.2026): alle Mitarbeitenden dürfen je Filiale
    30/50/70 % setzen, aber nur in ihren zugewiesenen Filialen. Empfehlung und
    Wahl von Hand bleiben getrennt; der Bestand zeigt die wirksame Stufe."""
    client, codes = welt.client, welt.codes
    heute = date.today()
    welt.anmelden(CHEF)
    for nummer, eingang, zeilen in [
        ("9000000051", _monate_zurueck(heute, 40), [_zeile("1", "A1", "4006632041234", "Poloshirt", "5")]),
        ("9000000052", _monate_zurueck(heute, 1), [_zeile("2", "D4", "5901234123457", "Cap", "4")]),
    ]:
        pdf = rechnung_pdf(header_lines=kopf(nummer=nummer, datum=eingang.strftime("%d.%m.%Y")), rows=zeilen)
        assert importieren(client, pdf, lagerort_id=str(codes["SF1"])).status_code == 200
    cap = client.get("/api/articles?ean=5901234123457").json()["items"][0]["id"]
    polo = client.get("/api/articles?ean=4006632041234").json()["items"][0]["id"]

    welt.anmelden(ANNA)
    stand = {e["lagerort"]["code"]: e for e in client.get(f"/api/articles/{cap}/reduktion").json()["filialen"]}
    assert set(stand) == {"SF1", "SF2", "SF3", "SF4"}  # nur Filialen, keine externen Lager
    assert stand["SF1"] == {**stand["SF1"], "empfehlung": 0, "manuell": None, "wirksam": 0, "darf_aendern": True}
    assert stand["SF2"]["darf_aendern"] is False

    url = "/api/reduktion/manuell"
    assert client.put(url, json={"varianten_id": cap, "lagerort_id": codes["SF1"], "prozent": 40}).status_code == 422
    assert client.put(url, json={"varianten_id": cap, "lagerort_id": codes["SF2"], "prozent": 30}).status_code == 403
    gesetzt = client.put(url, json={"varianten_id": cap, "lagerort_id": codes["SF1"], "prozent": 30})
    assert gesetzt.status_code == 200 and gesetzt.json()["wirksam"] == 30
    # Nochmals setzen ändert die Stufe, legt keine zweite an.
    assert client.put(url, json={"varianten_id": cap, "lagerort_id": codes["SF1"], "prozent": 50}).json()["wirksam"] == 50

    # Das Etikett schlägt die wirksame Stufe vor (Rolle mit rotem Punkt).
    assert client.get(f"/api/varianten/{cap}/etikett").json()["rolle"]["prozent"] == 50
    # Bestand zeigt Empfehlung, Wahl von Hand und wirksame Stufe.
    zeilen = {z["ean"]: z["reduktion"] for z in client.get(f"/api/bestand?lagerort_id={codes['SF1']}").json()["zeilen"]}
    assert zeilen["5901234123457"] == {"empfehlung": 0, "manuell": 50, "wirksam": 50}
    assert zeilen["4006632041234"] == {"empfehlung": 70, "manuell": None, "wirksam": 70}
    # Runterschreiben listet die Wahl von Hand separat.
    manuell = client.get("/api/reduktionen").json()["manuell"]
    assert [(a["lieferanten_artikelnr"], a["prozent"], a["gesetzt_von"]) for a in manuell] == [("D4", 50, "Anna")]

    # Zurück zur Empfehlung; eine Stufe unter der Empfehlung ist erlaubt.
    assert client.delete(f"{url}?varianten_id={cap}&lagerort_id={codes['SF1']}").json()["wirksam"] == 0
    assert client.put(url, json={"varianten_id": polo, "lagerort_id": codes["SF1"], "prozent": 30}).json()["wirksam"] == 30
    assert client.get("/api/reduktionen").json()["manuell"][0]["lieferanten_artikelnr"] == "A1"


def test_runterschreiben_bestaetigen(welt):
    """D-F1 (25.09.2026): eine Filiale bestätigt ein fälliges Modell als
    heruntergeschrieben - es verschwindet aus der fälligen Liste, bis die
    nächste Stufe fällig wird. „Bald" bleibt unberührt (nichts zu bestätigen)."""
    client, codes = welt.client, welt.codes
    heute = date.today()
    welt.anmelden(CHEF)
    # A1: 40 Monate her -> 70% fällig. C3: in 10 Tagen 18 Monate -> 50% "bald".
    for nummer, eingang, zeilen in [
        ("9000000061", _monate_zurueck(heute, 40), [_zeile("1", "A1", "4006632041234", "Poloshirt", "5")]),
        ("9000000062", _monate_zurueck(heute + timedelta(days=10), 18), [_zeile("2", "C3", "4006381333931", "Hoodie", "1")]),
    ]:
        pdf = rechnung_pdf(header_lines=kopf(nummer=nummer, datum=eingang.strftime("%d.%m.%Y")), rows=zeilen)
        assert importieren(client, pdf, lagerort_id=str(codes["SF1"])).status_code == 200

    welt.anmelden(ANNA)
    with welt.sessions() as session:
        polo_id = session.scalar(select(Artikel.id).where(Artikel.lieferanten_artikelnr == "A1"))
        hoodie_id = session.scalar(select(Artikel.id).where(Artikel.lieferanten_artikelnr == "C3"))

    url = "/api/reduktionen/bestaetigen"
    # Falsche Stufe: nichts wird gebucht.
    assert client.post(url, json={"artikel_id": polo_id, "lagerort_id": codes["SF1"], "stufe": 50}).status_code == 200
    liste = client.get("/api/reduktionen").json()["artikel"]
    # Falsche Stufe bestätigt (50 statt tatsächlich fälliger 70) - Poloshirt bleibt in der Liste.
    assert [(a["lieferanten_artikelnr"], a["stand"]) for a in liste] == [("A1", "faellig"), ("C3", "bald")]

    # Richtige Stufe (70) bestätigt: Poloshirt verschwindet, Hoodie ("bald") bleibt unberührt.
    bestaetigt = client.post(url, json={"artikel_id": polo_id, "lagerort_id": codes["SF1"], "stufe": 70})
    assert bestaetigt.status_code == 200, bestaetigt.text
    liste = client.get("/api/reduktionen").json()["artikel"]
    assert [(a["lieferanten_artikelnr"], a["stand"]) for a in liste] == [("C3", "bald")]

    # Andere Filiale unberührt (Bestätigung gilt nur dort, wo bestätigt wurde).
    assert client.get(f"/api/reduktionen?lagerort_id={codes['SF2']}").json()["artikel"] == []

    # Mitarbeiter dürfen nur in ihrer Filiale bestätigen (Regel 9, gleiche Grenze wie manuelle Reduktion).
    verboten = client.post(url, json={"artikel_id": hoodie_id, "lagerort_id": codes["SF2"], "stufe": 50})
    assert verboten.status_code == 403

    assert client.post(url, json={"artikel_id": 999999, "lagerort_id": codes["SF1"], "stufe": 70}).status_code == 404
    assert client.post(url, json={"artikel_id": polo_id, "lagerort_id": codes["SF1"], "stufe": 40}).status_code == 422
