"""Empfehlung der Zentrale (D-F3, 25.09.2026): die Zentrale setzt je Modell
und Filiale eine Stufe ab einem Datum, die Filiale übernimmt sie (setzt
dieselbe Stufe von Hand) oder lehnt sie mit Grund ab; die Zentrale sieht alle
Antworten (Abweichungen)."""

from conftest import ANNA, BEAT, CHEF, ZENTRALE
from sqlalchemy import select
from testbelege import importieren, kopf, rechnung_pdf

from app.core.models import Artikel, Variante


def _zeile(art, nr, ean, bezeichnung, menge, uvp="49.90"):
    return ["Nike", "224100", art, nr, ean, bezeichnung, menge, "Stk", uvp, "20.00"]


def test_empfehlung_setzen_uebernehmen_und_ablehnen(welt):
    client, codes = welt.client, welt.codes
    welt.anmelden(CHEF)
    pdf = rechnung_pdf(
        header_lines=kopf(nummer="9500000001", datum="01.01.2026"),
        rows=[_zeile("A1", "1", "4006632041234", "Poloshirt", "5")],
    )
    assert importieren(client, pdf, lagerort_id=str(codes["SF1"])).status_code == 200
    with welt.sessions() as session:
        artikel_id = session.scalar(select(Artikel.id).where(Artikel.lieferanten_artikelnr == "A1"))
        varianten_id = session.scalar(select(Variante.id).where(Variante.artikel_id == artikel_id))

    # Nur die Zentrale darf setzen.
    welt.anmelden(CHEF)
    verboten = client.post(
        "/api/empfehlungen",
        json={"artikel_id": artikel_id, "lagerort_id": codes["SF1"], "prozent": 50, "ab_datum": "2026-10-01"},
    )
    assert verboten.status_code == 403
    assert client.get("/empfehlungen", follow_redirects=False).status_code == 303

    welt.anmelden(ZENTRALE)
    assert client.get("/empfehlungen").status_code == 200
    gesetzt = client.post(
        "/api/empfehlungen",
        json={"artikel_id": artikel_id, "lagerort_id": codes["SF1"], "prozent": 50, "ab_datum": "2026-10-01"},
    )
    assert gesetzt.status_code == 200, gesetzt.text
    assert gesetzt.json()["status"] == "offen"
    empfehlung_id = gesetzt.json()["id"]
    # Auch für eine zweite Filiale.
    client.post(
        "/api/empfehlungen",
        json={"artikel_id": artikel_id, "lagerort_id": codes["SF2"], "prozent": 30, "ab_datum": "2026-10-01"},
    )
    assert client.post(
        "/api/empfehlungen",
        json={"artikel_id": artikel_id, "lagerort_id": codes["SF1"], "prozent": 40, "ab_datum": "2026-10-01"},
    ).status_code == 422

    # SF1 (Anna) sieht die Empfehlung auf ihrer Liste und übernimmt sie.
    welt.anmelden(ANNA)
    liste = client.get("/api/reduktionen").json()
    assert [(e["lieferanten_artikelnr"], e["prozent"], e["status"]) for e in liste["empfehlungen"]] == [("A1", 50, "offen")]

    # Andere Filiale kann nicht antworten (Beat gehört zu SF2, nicht SF1).
    welt.anmelden(BEAT)
    fremd = client.post(f"/api/empfehlungen/{empfehlung_id}/antwort", json={"status": "uebernommen"})
    assert fremd.status_code == 403

    welt.anmelden(ANNA)
    uebernommen = client.post(f"/api/empfehlungen/{empfehlung_id}/antwort", json={"status": "uebernommen"})
    assert uebernommen.status_code == 200, uebernommen.text
    assert uebernommen.json()["status"] == "uebernommen"
    # Übernehmen setzt dieselbe Stufe von Hand.
    stand = client.get(f"/api/articles/{varianten_id}/reduktion").json()["filialen"]
    sf1 = next(f for f in stand if f["lagerort"]["code"] == "SF1")
    assert sf1["manuell"] == 50 and sf1["wirksam"] == 50

    # Nochmals antworten geht nicht mehr.
    assert client.post(f"/api/empfehlungen/{empfehlung_id}/antwort", json={"status": "uebernommen"}).status_code == 422
    # Verschwindet aus der offenen Liste.
    assert client.get("/api/reduktionen").json()["empfehlungen"] == []

    # SF2 (Beat) lehnt ab - Grund nötig.
    welt.anmelden(BEAT)
    sf2_liste = client.get("/api/reduktionen").json()["empfehlungen"]
    sf2_id = sf2_liste[0]["id"]
    ohne_grund = client.post(f"/api/empfehlungen/{sf2_id}/antwort", json={"status": "abgelehnt"})
    assert ohne_grund.status_code == 422
    abgelehnt = client.post(
        f"/api/empfehlungen/{sf2_id}/antwort", json={"status": "abgelehnt", "grund": "Zu wenig Bestand"}
    )
    assert abgelehnt.status_code == 200, abgelehnt.text
    assert abgelehnt.json() == {**abgelehnt.json(), "status": "abgelehnt", "ablehnungsgrund": "Zu wenig Bestand"}
    # Ablehnen setzt keine manuelle Reduktion.
    stand2 = client.get(f"/api/articles/{varianten_id}/reduktion").json()["filialen"]
    sf2 = next(f for f in stand2 if f["lagerort"]["code"] == "SF2")
    assert sf2["manuell"] is None

    # Die Zentrale sieht beide Antworten - die Abweichung.
    welt.anmelden(ZENTRALE)
    uebersicht = {e["lagerort"]["code"]: e["status"] for e in client.get("/api/empfehlungen").json()["empfehlungen"]}
    assert uebersicht == {"SF1": "uebernommen", "SF2": "abgelehnt"}

    assert client.post(
        "/api/empfehlungen", json={"artikel_id": 999999, "lagerort_id": codes["SF1"], "prozent": 50, "ab_datum": "2026-10-01"}
    ).status_code == 404


def test_empfehlung_an_alle_zurueckziehen_und_anstehend(welt):
    """2026-09-30: die Zentrale sendet eine Empfehlung an alle Verkaufsfilialen
    in einer Aktion (auch ohne Bestand, jede Filiale antwortet einzeln), sie
    erscheint sofort unter „Anstehend" der Filiale, und die Zentrale kann jede
    Empfehlung jederzeit zurückziehen - vor und nach der Antwort, ohne dass
    eine schon gesetzte Stufe zurückgenommen wird."""
    client, codes = welt.client, welt.codes
    welt.anmelden(CHEF)
    pdf = rechnung_pdf(
        header_lines=kopf(nummer="9500000002", datum="01.01.2026"),
        rows=[_zeile("A2", "1", "4006632041241", "Poloshirt", "5")],
    )
    assert importieren(client, pdf, lagerort_id=str(codes["SF1"])).status_code == 200
    with welt.sessions() as session:
        artikel_id = session.scalar(select(Artikel.id).where(Artikel.lieferanten_artikelnr == "A2"))
        varianten_id = session.scalar(select(Variante.id).where(Variante.artikel_id == artikel_id))
    verkaufsfilialen = {"SF1", "SF2", "SF3", "SF4"}
    body = {"artikel_id": artikel_id, "prozent": 50, "ab_datum": "2099-01-01"}

    # Nur die Zentrale; genau ein Ziel: eine Filiale oder alle.
    assert client.post("/api/empfehlungen", json={**body, "alle_filialen": True}).status_code == 403
    welt.anmelden(ZENTRALE)
    assert client.post("/api/empfehlungen", json=body).status_code == 422
    assert client.post("/api/empfehlungen", json={**body, "alle_filialen": True, "lagerort_id": codes["SF1"]}).status_code == 422

    antwort = client.post("/api/empfehlungen", json={**body, "alle_filialen": True})
    assert antwort.status_code == 200, antwort.text
    angelegt = antwort.json()["empfehlungen"]
    assert {e["lagerort_id"] for e in angelegt} == {codes[c] for c in verkaufsfilialen}
    assert {e["status"] for e in angelegt} == {"offen"}
    ids = {e["lagerort_id"]: e["id"] for e in angelegt}

    # Sofort unter „Anstehend" der Filiale - auch mit Datum in der Zukunft,
    # auch ohne Bestand (SF2); in der Zahl der Glocke enthalten.
    welt.anmelden(ANNA)
    assert client.get("/api/dashboard").json()["filiale"]["empfehlungen_offen"] == 1
    assert client.get("/api/anstehend/anzahl").json()["anzahl"] >= 1
    welt.anmelden(BEAT)
    assert client.get("/api/dashboard").json()["filiale"]["empfehlungen_offen"] == 1

    # SF1 übernimmt; danach zieht die Zentrale zurück: Status zurückgezogen,
    # die von Hand gesetzte Stufe bleibt (kein Rollback).
    welt.anmelden(ANNA)
    assert client.post(f"/api/empfehlungen/{ids[codes['SF1']]}/antwort", json={"status": "uebernommen"}).status_code == 200
    welt.anmelden(CHEF)
    assert client.post(f"/api/empfehlungen/{ids[codes['SF1']]}/zurueckziehen").status_code == 403
    welt.anmelden(ZENTRALE)
    zurueck = client.post(f"/api/empfehlungen/{ids[codes['SF1']]}/zurueckziehen")
    assert zurueck.status_code == 200, zurueck.text
    assert zurueck.json()["status"] == "zurueckgezogen"
    stand = client.get(f"/api/articles/{varianten_id}/reduktion").json()["filialen"]
    assert next(f for f in stand if f["lagerort"]["code"] == "SF1")["manuell"] == 50

    # SF2: vor der Antwort zurückgezogen - verschwindet aus „Anstehend" und
    # lässt sich nicht mehr beantworten.
    assert client.post(f"/api/empfehlungen/{ids[codes['SF2']]}/zurueckziehen").status_code == 200
    welt.anmelden(BEAT)
    assert client.get("/api/dashboard").json()["filiale"]["empfehlungen_offen"] == 0
    assert client.get("/api/reduktionen").json()["empfehlungen"] == []
    assert client.post(f"/api/empfehlungen/{ids[codes['SF2']]}/antwort", json={"status": "uebernommen"}).status_code == 422

    # Nochmals zurückziehen / unbekannte Id; die Zentrale sieht den Status.
    welt.anmelden(ZENTRALE)
    assert client.post(f"/api/empfehlungen/{ids[codes['SF2']]}/zurueckziehen").status_code == 422
    assert client.post("/api/empfehlungen/999999/zurueckziehen").status_code == 404
    uebersicht = {e["lagerort"]["code"]: e["status"] for e in client.get("/api/empfehlungen").json()["empfehlungen"]}
    assert uebersicht == {"SF1": "zurueckgezogen", "SF2": "zurueckgezogen", "SF3": "offen", "SF4": "offen"}

    # Keine Rücknahme: stattdessen eine neue Empfehlung - sie ist wieder offen.
    neu = client.post("/api/empfehlungen", json={**body, "lagerort_id": codes["SF2"], "prozent": 30})
    assert neu.status_code == 200 and neu.json()["status"] == "offen"
