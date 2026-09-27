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
