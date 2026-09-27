"""Ablauf „Kontoverwaltung" (Anforderung 13, 24./25.09.2026): die Zentrale
darf Konten (Mitarbeiter und Filialleiter) anlegen und löschen. Wird ein
Konto gelöscht, bleiben alle Buchungen in der Datenbank - der Name bleibt als
Momentaufnahme stehen, nur die Verknüpfung zum Konto entfällt (Entscheid
24.09.2026, siehe docs/projekt-kontext.md Abschnitt 11).
"""

from conftest import ANNA, CHEF, ZENTRALE
from sqlalchemy import select

from app.core.models import BenutzerLagerort, User


def test_konten_anlegen_und_loeschen(welt):
    client, codes = welt.client, welt.codes

    # Nur die Zentrale sieht die Kontoverwaltung - nicht Filialleiter, nicht
    # Mitarbeiter.
    welt.anmelden(CHEF)
    assert client.get("/konten", follow_redirects=False).status_code == 303
    assert client.get("/api/konten").status_code == 403
    welt.anmelden(ANNA)
    assert client.get("/api/konten").status_code == 403

    welt.anmelden(ZENTRALE)
    assert client.get("/konten").status_code == 200
    start = client.get("/api/konten").json()["konten"]
    assert {k["kassennummer"] for k in start} == {ANNA, "910142", CHEF, ZENTRALE}

    url = "/api/konten"

    # Mitarbeiterin ohne Passwort, mit Filiale.
    dora = client.post(
        url,
        json={
            "kassennummer": "910150",
            "name": "Dora",
            "role": "mitarbeiter",
            "lagerort_ids": [codes["SF1"]],
        },
    )
    assert dora.status_code == 200, dora.text
    dora_id = dora.json()["id"]
    assert dora.json() == {
        "id": dora_id,
        "kassennummer": "910150",
        "name": "Dora",
        "role": "mitarbeiter",
        "lagerort_ids": [codes["SF1"]],
    }

    # Filialleiterin mit Passwort und zwei Filialen.
    lena = client.post(
        url,
        json={
            "kassennummer": "910151",
            "name": "Lena",
            "role": "chef",
            "password": "geheim123",
            "lagerort_ids": [codes["SF1"], codes["SF2"]],
        },
    )
    assert lena.status_code == 200, lena.text
    assert sorted(lena.json()["lagerort_ids"]) == sorted([codes["SF1"], codes["SF2"]])

    # Zentrale ohne Filiale.
    zw = client.post(
        url,
        json={"kassennummer": "910152", "name": "Zweite Zentrale", "role": "admin", "password": "zentrale456"},
    )
    assert zw.status_code == 200, zw.text
    assert zw.json()["lagerort_ids"] == []

    # Harte Regeln.
    doppelt = client.post(url, json={"kassennummer": "910150", "name": "Doppelt", "role": "mitarbeiter", "lagerort_ids": [codes["SF1"]]})
    assert doppelt.status_code == 409
    unbekannte_rolle = client.post(url, json={"kassennummer": "910160", "name": "X", "role": "aushilfe", "lagerort_ids": [codes["SF1"]]})
    assert unbekannte_rolle.status_code == 422
    ohne_filiale = client.post(url, json={"kassennummer": "910161", "name": "Y", "role": "mitarbeiter", "lagerort_ids": []})
    assert ohne_filiale.status_code == 422
    chef_ohne_passwort = client.post(url, json={"kassennummer": "910162", "name": "Z", "role": "chef", "lagerort_ids": [codes["SF1"]]})
    assert chef_ohne_passwort.status_code == 422
    kurzes_passwort = client.post(url, json={"kassennummer": "910163", "name": "W", "role": "chef", "password": "123", "lagerort_ids": [codes["SF1"]]})
    assert kurzes_passwort.status_code == 422
    mitarbeiter_mit_passwort = client.post(
        url, json={"kassennummer": "910164", "name": "V", "role": "mitarbeiter", "password": "geheim123", "lagerort_ids": [codes["SF1"]]}
    )
    assert mitarbeiter_mit_passwort.status_code == 422

    # Dora meldet sich an, funktioniert wie jedes andere Mitarbeiterkonto.
    client.post("/logout")
    assert client.post("/login", data={"kassennummer": "910150"}).status_code == 200
    assert client.get("/api/me").json()["name"] == "Dora"

    # Löschen: die Zentrale, nicht sich selbst.
    welt.anmelden(ZENTRALE)
    assert client.delete(f"/api/konten/{dora_id}").status_code == 200
    with welt.sessions() as session:
        assert session.get(User, dora_id) is None
        assert session.scalars(
            select(BenutzerLagerort).where(BenutzerLagerort.user_id == dora_id)
        ).all() == []
    # Nach dem Löschen kein Login mehr möglich.
    assert client.post("/login", data={"kassennummer": "910150"}).status_code == 401

    eigenes_konto = client.get("/api/konten").json()["konten"]
    zentrale_id = next(k["id"] for k in eigenes_konto if k["kassennummer"] == ZENTRALE)
    selbstloeschung = client.delete(f"/api/konten/{zentrale_id}")
    assert selbstloeschung.status_code == 409

    unbekannt = client.delete("/api/konten/999999")
    assert unbekannt.status_code == 404
