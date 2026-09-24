"""Ablauf „Anmeldung und Rechte": wer meldet sich wie an, was sieht wer, wer
darf welche Filiale wählen, in welcher Sprache antwortet das System.

Deckt Regel 7 und 9, D8, D26, F3 und die Filialcodes (F13) ab. Was eine Rolle
beim Buchen darf, prüfen die übrigen Ablauf-Tests direkt im jeweiligen Ablauf.
"""

from conftest import ANNA, CHEF, ZENTRALE

from app.core.i18n import translate


def test_anmelden_rollen_filialwahl_sprache(welt):
    client, codes = welt.client, welt.codes

    # Ohne Anmeldung: Seiten leiten um, APIs antworten mit 401.
    seite = client.get("/", follow_redirects=False)
    assert seite.status_code == 303 and seite.headers["location"] == "/login?next=/"
    for pfad in ("/api/dashboard", "/api/articles", "/api/invoices", "/api/me"):
        assert client.get(pfad).status_code == 401, pfad
    # Fehlermeldung beim Login: Sprache aus dem Browser, sonst Deutsch.
    fremd = client.post("/login", data={"kassennummer": "000000"}, headers={"Accept-Language": "fr-CH"})
    assert fremd.status_code == 401
    assert fremd.json()["detail"] == translate("errors.auth.unknown_kassennummer", "fr")
    italienisch = client.post("/login", data={"kassennummer": "000000"}, headers={"Accept-Language": "it"})
    assert italienisch.json()["detail"] == translate("errors.auth.unknown_kassennummer", "de")

    # Mitarbeiter ohne Passwort; Filialleiter und Zentrale mit.
    anna = client.post("/login", data={"kassennummer": ANNA})
    assert anna.json() == {"name": "Anna", "role": "mitarbeiter"}
    me = client.get("/api/me").json()
    assert me["role_label"] == "Mitarbeiter" and me["language"] == "de"
    assert me["lagerort"]["code"] == "SF1" and me["lagerort"]["name"] == "Volketswil"
    assert [lo["code"] for lo in me["lagerorte"]] == ["SF1"]
    assert me["kann_alle_filialen_waehlen"] is False
    # Alles ansehen, aber keine Belege hochladen (Regel 9).
    for pfad in ("/articles", "/invoices", "/bestand", "/ausbuchen", "/umlagern", "/wareneingaenge"):
        assert client.get(pfad).status_code == 200, pfad
    assert client.get("/preview", follow_redirects=False).status_code == 303
    assert client.post("/api/active-lagerort", json={"lagerort_id": None}).status_code == 400
    assert client.post("/api/active-lagerort", json={"lagerort_id": codes["SF2"]}).status_code == 403
    client.post("/logout")
    assert client.get("/", follow_redirects=False).status_code == 303

    assert client.post("/login", data={"kassennummer": CHEF}).json() == {"requires_password": True}
    assert client.post("/login", data={"kassennummer": CHEF, "password": "falsch"}).status_code == 401
    welt.anmelden(CHEF)
    me = client.get("/api/me").json()
    assert [lo["code"] for lo in me["lagerorte"]] == ["SF1", "SF2"]
    assert client.get("/preview", follow_redirects=False).status_code == 200
    # Wechsel nur zu zugewiesenen Filialen.
    wechsel = client.post("/api/active-lagerort", json={"lagerort_id": codes["SF2"]})
    assert wechsel.status_code == 200 and wechsel.json()["lagerort"]["code"] == "SF2"
    assert client.get("/api/me").json()["lagerort"]["code"] == "SF2"
    assert client.post("/api/active-lagerort", json={"lagerort_id": codes["SF3"]}).status_code == 403

    # Zentrale: alle Filialen, Voreinstellung „alle".
    assert client.post("/login", data={"kassennummer": ZENTRALE}).json() == {"requires_password": True}
    welt.anmelden(ZENTRALE)
    me = client.get("/api/me").json()
    assert me["lagerort"] is None and me["kann_alle_filialen_waehlen"] is True
    assert [lo["code"] for lo in me["lagerorte"]] == [
        "SF1", "SF2", "SF3", "SF4", "GEWA", "VEBO", "DIETIKON"
    ]
    assert client.post("/api/active-lagerort", json={"lagerort_id": codes["SF4"]}).json()["lagerort"]["code"] == "SF4"
    assert client.post("/api/active-lagerort", json={"lagerort_id": None}).status_code == 200

    # Sprache je Konto (Regel 7): gespeichert und für Fehlermeldungen benutzt.
    assert client.post("/api/language", json={"language": "xx"}).status_code == 422
    assert client.post("/api/language", json={"language": "en"}).status_code == 200
    assert client.get("/api/me").json()["language"] == "en"
    fehler = client.post("/api/active-lagerort", json={"lagerort_id": 999999})
    assert fehler.json()["detail"] == translate("errors.auth.no_lagerort_access", "en")
    welt.anmelden(ANNA)
    welt.anmelden(ZENTRALE)
    assert client.get("/api/me").json()["language"] == "en"
    client.post("/logout")
    assert client.post("/api/language", json={"language": "fr"}).status_code == 401
