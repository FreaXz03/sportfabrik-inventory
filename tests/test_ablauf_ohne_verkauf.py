"""Punkt 10 (2026-10-01): Statistik und Anstehend gibt es nur an Orten mit
Verkauf. Bei GEWA, VEBO und Dietikon (`lagerorte.verkauf = false`) sind
Seiten und Glocke weg - gemeint ist der gewählte Ort, auch bei gemischter
Zuweisung. Lese- und Buchungsrechte bleiben unverändert (Regel 9)."""

from conftest import ZENTRALE


def test_statistik_und_anstehend_nur_an_verkaufsorten(welt):
    client, codes = welt.client, welt.codes
    welt.anmelden(ZENTRALE)

    # Verkaufsort: wie bisher.
    client.post("/api/active-lagerort", json={"lagerort_id": codes["SF1"]})
    assert client.get("/api/me").json()["lagerort"]["verkauf"] is True
    assert client.get("/statistiken", follow_redirects=False).status_code == 200
    assert client.get("/anstehend", follow_redirects=False).status_code == 200

    # Ort ohne Verkauf, jeder der drei: Seiten leiten auf die Übersicht, die Glocke ist leer.
    for code in ("GEWA", "VEBO", "DIETIKON"):
        client.post("/api/active-lagerort", json={"lagerort_id": codes[code]})
        assert client.get("/api/me").json()["lagerort"]["verkauf"] is False
        for seite in ("/statistiken", "/anstehend"):
            antwort = client.get(seite, follow_redirects=False)
            assert (antwort.status_code, antwort.headers["location"]) == (303, "/"), (code, seite)
        assert client.get("/api/anstehend/anzahl").json() == {"anzahl": 0, "meldungen": []}
        # Andere Seiten bleiben erreichbar (Wareneingang an diesen Orten ist ja gerade der Zweck).
        assert client.get("/wareneingaenge", follow_redirects=False).status_code == 200

    # „Alle Filialen" (Zentrale ohne gewählten Ort): nichts ausgeblendet.
    client.post("/api/active-lagerort", json={"lagerort_id": None})
    assert client.get("/statistiken", follow_redirects=False).status_code == 200
