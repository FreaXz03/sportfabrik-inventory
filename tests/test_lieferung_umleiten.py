"""Punkt 3 (2026-10-01): eine erwartete Lieferung vor der Ankunft an eine
andere Filiale umleiten. Es wird nichts an der ersten Filiale gebucht (Regel
3); die Erwartung wandert, die Umleitung bleibt in der Historie, die Ziel-
Filiale bestätigt die Ankunft. Nur Filialleiter und Zentrale."""

from conftest import ANNA, CHEF, ZENTRALE
from sqlalchemy import func, select
from test_lieferung import _bestaetigung_importieren, _bestand

from app.core.models import Bestand, Lagerbewegung, WareneingangUmleitung


def _erwartet(welt, lagerort):
    welt.client.post("/api/active-lagerort", json={"lagerort_id": welt.codes[lagerort]})
    return welt.client.get("/api/wareneingaenge").json()["wareneingaenge"]


def test_lieferung_umleiten_bucht_nichts_und_ziel_bestaetigt(welt, monkeypatch):
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    wareneingang_id = _bestaetigung_importieren(welt, monkeypatch)
    url = f"/api/wareneingaenge/{wareneingang_id}/umleitung"

    # Mitarbeiter dürfen nicht umleiten.
    welt.anmelden(ANNA)
    assert client.post(url, json={"lagerort_id": codes["SF3"]}).status_code == 403

    welt.anmelden(CHEF)
    # Gleiches Ziel und unbekanntes Ziel werden abgelehnt.
    assert client.post(url, json={"lagerort_id": codes["SF1"]}).status_code == 409
    assert client.post(url, json={"lagerort_id": 999999}).status_code == 409
    antwort = client.post(url, json={"lagerort_id": codes["SF3"]})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["von"]["code"] == "SF1" and antwort.json()["nach"]["code"] == "SF3"

    # Die Erwartung ist jetzt in SF3, nicht mehr in SF1 - und gebucht ist nichts.
    # (Ansehen von SF3 als Zentrale: der Filialleiter ist nur SF1/SF2 zugewiesen.)
    welt.anmelden(ZENTRALE)
    assert _erwartet(welt, "SF1") == []
    am_ziel = _erwartet(welt, "SF3")
    assert [w["id"] for w in am_ziel] == [wareneingang_id]
    assert [(u["von"]["code"], u["nach"]["code"]) for u in am_ziel[0]["umleitungen"]] == [("SF1", "SF3")]
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 0
        assert session.scalar(select(func.count()).select_from(Bestand)) == 0

    # Weiter umleiten ist möglich (Historie wächst); danach Ankunft am letzten Ziel.
    welt.anmelden(CHEF)
    assert client.post(url, json={"lagerort_id": codes["SF2"]}).status_code == 200
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(WareneingangUmleitung)) == 2
    positionen = _erwartet(welt, "SF2")[0]["positionen"]
    assert [u["nach"]["code"] for u in _erwartet(welt, "SF2")[0]["umleitungen"]] == ["SF3", "SF2"]
    ankunft = client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft",
        json={"mengen": {str(p["id"]): p["menge_offen"] for p in positionen}},
    )
    assert ankunft.status_code == 200, ankunft.text
    assert sorted(_bestand(welt, "SF2")) == ["2.00", "3.00", "5.00"]
    assert _bestand(welt, "SF1") == [] and _bestand(welt, "SF3") == []
    with sessions() as session:
        assert all(b.aeltestes_eingangsdatum is not None for b in session.scalars(select(Bestand)))

    # Nach der Ankunft ist keine Umleitung mehr möglich.
    assert client.post(url, json={"lagerort_id": codes["SF4"]}).status_code == 409


def test_teilweise_angekommene_lieferung_laesst_sich_nicht_umleiten(welt, monkeypatch):
    client, codes = welt.client, welt.codes
    wareneingang_id = _bestaetigung_importieren(welt, monkeypatch)
    welt.anmelden(CHEF)
    client.post("/api/active-lagerort", json={"lagerort_id": codes["SF1"]})
    erste = client.get("/api/wareneingaenge").json()["wareneingaenge"][0]["positionen"][0]
    assert client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft", json={"mengen": {str(erste["id"]): "1"}}
    ).status_code == 200
    antwort = client.post(
        f"/api/wareneingaenge/{wareneingang_id}/umleitung", json={"lagerort_id": codes["SF3"]}
    )
    assert antwort.status_code == 409
