"""Package 4c (2026-10-05): Pending also lists the new exceptions of package 4.

Returns waiting for approval (urgent) or in inspection, transfers in transit
for more than 14 days (urgent), and shortages under investigation. Each entry
carries a count and a link to where it is resolved.
"""

from datetime import date, timedelta

from conftest import ANNA, BEAT, CHEF

EAN = "4006632041233"


def _meldungen(welt, kassennummer):
    welt.anmelden(kassennummer)
    daten = welt.client.get("/api/anstehend/anzahl").json()
    return {m["art"]: m for m in daten["meldungen"]}


def _artikel(welt):
    welt.anmelden(CHEF)
    antwort = welt.client.post(
        "/api/erfassen",
        json={
            "lagerort_id": welt.codes["SF1"],
            "positionen": [{"marke": "Nike", "bezeichnung": "Pegasus", "menge": "10", "uvp": "139.90", "ean": EAN}],
        },
    )
    assert antwort.status_code == 200, antwort.text
    return welt.client.get(f"/api/articles?ean={EAN}").json()["items"][0]["id"]


def test_returns_show_up_as_pending_entries(welt):
    varianten_id = _artikel(welt)
    welt.anmelden(ANNA)
    for grund in ("passform", "defekt"):
        antwort = welt.client.post(
            "/api/retouren",
            json={"varianten_id": varianten_id, "lagerort_id": welt.codes["SF1"], "grund": grund, "zustand": "gebraucht"},
        )
        assert antwort.status_code == 200, antwort.text
    meldungen = _meldungen(welt, ANNA)
    assert meldungen["returns_inspection"]["anzahl"] == 1
    assert meldungen["returns_request"]["anzahl"] == 1 and meldungen["returns_request"]["dringend"] is True
    assert meldungen["returns_request"]["href"].startswith("/retouren")
    # Another branch does not see them.
    assert "returns_request" not in _meldungen(welt, BEAT)


def test_overdue_transfer_and_difference_under_investigation(welt):
    varianten_id = _artikel(welt)
    welt.anmelden(CHEF)
    for tage in (20, 3):
        vor = (date.today() - timedelta(days=tage)).isoformat()
        antwort = welt.client.post(
            "/api/umlagerung",
            json={
                "quelle_id": welt.codes["SF1"],
                "ziel_id": welt.codes["SF2"],
                "versanddatum": vor,
                "positionen": [{"varianten_id": varianten_id, "menge": "2"}],
            },
        )
        assert antwort.status_code == 200, antwort.text
    meldungen = _meldungen(welt, BEAT)  # SF2 expects both; only the 20-day one is overdue
    assert meldungen["transit_overdue"]["anzahl"] == 1 and meldungen["transit_overdue"]["dringend"] is True
    assert "delivery_differences" not in meldungen

    # Receive 1 of 2 of the old transfer and flag the rest as under investigation.
    erwartet = welt.client.get("/api/wareneingaenge").json()["wareneingaenge"]
    alt = next(w for w in erwartet if w["umlagerung"]["tage_unterwegs"] >= 20)
    position_id = alt["positionen"][0]["id"]
    assert welt.client.post(
        f"/api/wareneingaenge/{alt['id']}/ankunft", json={"mengen": {str(position_id): "1"}}
    ).status_code == 200
    assert welt.client.post(
        f"/api/wareneingaenge/{alt['id']}/differenz",
        json={"position_id": position_id, "art": "in_klaerung", "menge": "1"},
    ).status_code == 200
    meldungen = _meldungen(welt, BEAT)
    assert meldungen["delivery_differences"]["anzahl"] == 1
    assert meldungen["delivery_differences"]["href"] == "/wareneingaenge"
