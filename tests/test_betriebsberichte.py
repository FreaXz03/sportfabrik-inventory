"""Package 3 preparation (2026-10-01): reports for the SF1 pilot.

* `pruefe_bestand`: `bestand` must equal the sum of `lagerbewegungen` (hard
  rule 2); run daily and after every restore.
* `tagesabschluss`: what the app booked on one day at one branch, to reconcile
  against the till report (Fabian, daily).
* `zaehlstatus`: progress of the opening count - which stock lines have been
  counted since a given time and which still wait.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from conftest import CHEF
from sqlalchemy import select

from app.core.models import Bestand, Lagerbewegung
from app.services.betriebsberichte import pruefe_bestand, tagesabschluss, zaehlstatus

EANS = ["4006632041233", "4006632041240", "4006632041257"]


def _erfassen(welt, mengen, lagerort="SF1"):
    welt.anmelden(CHEF)
    positionen = [
        {"marke": "Nike", "bezeichnung": f"Artikel {i}", "menge": str(m), "uvp": "39.90", "ean": EANS[i]}
        for i, m in enumerate(mengen)
    ]
    antwort = welt.client.post(
        "/api/erfassen", json={"lagerort_id": welt.codes[lagerort], "positionen": positionen}
    )
    assert antwort.status_code == 200, antwort.text
    return [welt.client.get(f"/api/articles?ean={e}").json()["items"][0]["id"] for e in EANS[: len(mengen)]]


def _verkauf(welt, v, grund="verkauf", lagerort="SF1"):
    antwort = welt.client.post(
        "/api/ausbuchen", json={"grund": grund, "varianten_id": v, "lagerort_id": welt.codes[lagerort]}
    )
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["bewegung_id"]


# --- stock consistency ------------------------------------------------------


def test_stock_matches_movements_after_normal_bookings(welt):
    a, b, _ = _erfassen(welt, [5, 3, 2])
    _verkauf(welt, a)
    _verkauf(welt, b, "defekt")
    welt.client.post(
        "/api/korrektur",
        json={"varianten_id": a, "lagerort_id": welt.codes["SF1"], "gezaehlt": "7", "grund": "inventur"},
    )
    with welt.sessions() as session:
        ergebnis = pruefe_bestand(session)
    assert ergebnis["ok"] is True
    assert ergebnis["abweichungen"] == []
    assert ergebnis["geprueft"] == 3


def test_stock_that_differs_from_movements_is_reported(welt):
    a, b, _ = _erfassen(welt, [5, 3, 2])
    with welt.sessions.begin() as session:
        session.get(Bestand, (a, welt.codes["SF1"])).menge = 6  # someone overwrote the stock
        # a movement without any stock row
        session.add(
            Lagerbewegung(
                lagerort_id=welt.codes["SF2"],
                varianten_id=b,
                typ="korrektur",
                menge=2,
                grund="test",
                zeitpunkt=datetime.now(timezone.utc),
            )
        )
    with welt.sessions() as session:
        ergebnis = pruefe_bestand(session)
        nur_sf1 = pruefe_bestand(session, welt.codes["SF1"])
    assert ergebnis["ok"] is False
    gefunden = {(z["varianten_id"], z["lagerort_id"]): z for z in ergebnis["abweichungen"]}
    assert gefunden[(a, welt.codes["SF1"])]["bestand"] == "6.00"
    assert gefunden[(a, welt.codes["SF1"])]["summe_bewegungen"] == "5.00"
    assert gefunden[(b, welt.codes["SF2"])]["bestand"] == "0.00"
    assert gefunden[(b, welt.codes["SF2"])]["summe_bewegungen"] == "2.00"
    assert [(z["varianten_id"], z["lagerort_id"]) for z in nur_sf1["abweichungen"]] == [(a, welt.codes["SF1"])]


def test_negative_stock_is_counted_but_not_a_mismatch(welt):
    a, _, _ = _erfassen(welt, [1, 1, 1])
    _verkauf(welt, a)
    _verkauf(welt, a)
    with welt.sessions() as session:
        ergebnis = pruefe_bestand(session)
    assert ergebnis["ok"] is True and ergebnis["negativ"] == 1


# --- daily closing ----------------------------------------------------------


def _heute():
    return datetime.now(ZoneInfo("Europe/Zurich")).date()


def test_daily_closing_lists_net_sales_and_other_movements(welt):
    a, b, _ = _erfassen(welt, [8, 5, 2])
    _verkauf(welt, a)
    _verkauf(welt, a)
    storniert = _verkauf(welt, a)
    welt.client.post(f"/api/ausbuchen/{storniert}/storno")  # scanned by mistake
    _verkauf(welt, b, "defekt")
    welt.client.post(
        "/api/korrektur",
        json={"varianten_id": b, "lagerort_id": welt.codes["SF1"], "gezaehlt": "3", "grund": "inventur"},
    )
    with welt.sessions() as session:
        bericht = tagesabschluss(session, welt.codes["SF1"], _heute())

    assert bericht["lagerort"]["code"] == "SF1" and bericht["tag"] == _heute().isoformat()
    verkauf = [z for z in bericht["zeilen"] if z["art"] == "verkauf"]
    assert [(z["ean"], z["menge"]) for z in verkauf] == [(EANS[0], "2.00")]  # 3 scanned, 1 cancelled
    assert bericht["verkauft_stueck"] == "2.00"
    ausbuchung = [z for z in bericht["zeilen"] if z["art"] == "ausbuchung"]
    assert [(z["ean"], z["menge"], z["grund"]) for z in ausbuchung] == [(EANS[1], "1.00", "defekt")]
    korrektur = [z for z in bericht["zeilen"] if z["art"] == "korrektur"]
    assert [(z["ean"], z["menge"]) for z in korrektur] == [(EANS[1], "-1.00")]  # 5 - 1 sold out = 4 -> counted 3
    zugang = [z for z in bericht["zeilen"] if z["art"] == "zugang"]
    assert sorted(z["menge"] for z in zugang) == ["2.00", "5.00", "8.00"]
    assert bericht["zaehlungen"] == 1


def test_daily_closing_only_covers_the_requested_day_and_branch(welt):
    a, _, _ = _erfassen(welt, [4, 1, 1])
    _verkauf(welt, a)
    with welt.sessions() as session:
        gestern = tagesabschluss(session, welt.codes["SF1"], _heute() - timedelta(days=1))
        anderer = tagesabschluss(session, welt.codes["SF2"], _heute())
    assert gestern["zeilen"] == [] and gestern["verkauft_stueck"] == "0.00"
    assert anderer["zeilen"] == []


# --- opening count progress -------------------------------------------------


def test_count_status_lists_lines_not_yet_counted(welt):
    a, b, c = _erfassen(welt, [5, 3, 2])
    vorher = datetime.now(timezone.utc) - timedelta(minutes=1)
    welt.client.post(
        "/api/korrektur",
        json={"varianten_id": a, "lagerort_id": welt.codes["SF1"], "gezaehlt": "5", "grund": "inventur"},
    )  # counted, no difference
    welt.client.post(
        "/api/korrektur",
        json={"varianten_id": b, "lagerort_id": welt.codes["SF1"], "gezaehlt": "1", "grund": "inventur"},
    )  # counted, difference
    with welt.sessions() as session:
        status = zaehlstatus(session, welt.codes["SF1"], vorher)
        spaeter = zaehlstatus(session, welt.codes["SF1"], datetime.now(timezone.utc) + timedelta(hours=1))
    assert (status["zeilen"], status["gezaehlt"], status["offen"]) == (3, 2, 1)
    assert [z["varianten_id"] for z in status["offen_liste"]] == [c]
    assert status["offen_liste"][0]["bestand"] == "2.00"
    assert status["offen_stueck"] == "2.00"
    assert (spaeter["gezaehlt"], spaeter["offen"]) == (0, 3)


def test_count_status_ignores_empty_lines_and_other_branches(welt):
    a, b, _ = _erfassen(welt, [2, 1, 1])
    _verkauf(welt, a)
    _verkauf(welt, a)  # a is now 0: nothing to count on the shelf
    with welt.sessions() as session:
        status = zaehlstatus(session, welt.codes["SF1"], datetime.now(timezone.utc) - timedelta(hours=1))
        sf2 = zaehlstatus(session, welt.codes["SF2"], datetime.now(timezone.utc) - timedelta(hours=1))
    assert status["zeilen"] == 2
    assert sf2["zeilen"] == 0 and sf2["offen_liste"] == []


# --- command line -----------------------------------------------------------


def test_cli_pruefe_exit_code_and_daily_csv(welt):
    import io

    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "betrieb", Path(__file__).resolve().parents[1] / "scripts" / "betrieb.py"
    )
    betrieb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(betrieb)

    a, b, _ = _erfassen(welt, [5, 3, 2])
    _verkauf(welt, a)

    out = io.StringIO()
    assert betrieb.main(["pruefe"], welt.sessions, out, io.StringIO()) == 0
    assert "OK" in out.getvalue()

    out, err = io.StringIO(), io.StringIO()
    assert betrieb.main(["tagesabschluss", "SF1"], welt.sessions, out, err) == 0
    zeilen = out.getvalue().splitlines()
    assert zeilen[0].startswith("art,ean,marke")
    assert any(z.startswith("verkauf,4006632041233,Nike") and ",1.00," in z for z in zeilen)
    assert "verkauft 1.00 Stück" in err.getvalue()

    out = io.StringIO()
    assert betrieb.main(["zaehlstatus", "SF1", "--seit", "2020-01-01 00:00", "--liste"], welt.sessions, out, io.StringIO()) == 0
    assert "0 von 3 Zeilen gezählt, 3 offen" in out.getvalue()

    with welt.sessions.begin() as session:
        session.get(Bestand, (a, welt.codes["SF1"])).menge = 99
    out = io.StringIO()
    assert betrieb.main(["pruefe", "SF1"], welt.sessions, out, io.StringIO()) == 1
    assert "ABWEICHUNG" in out.getvalue() and "FEHLER" in out.getvalue()


def test_daily_closing_shows_the_reversal_of_a_cancelled_document(welt):
    """A receipt booked and cancelled the same day must net out: the counter
    movements of a cancelled document are not hidden like those of a cancelled sale."""
    from testbelege import importieren, kopf, rechnung_pdf

    welt.anmelden(CHEF)
    antwort = importieren(
        welt.client, rechnung_pdf(header_lines=kopf(nummer="9100000001")), lagerort_id=str(welt.codes["SF1"])
    )
    assert antwort.status_code == 200, antwort.text
    assert welt.client.post(f"/api/invoices/{antwort.json()['invoice_id']}/cancel").status_code == 200
    with welt.sessions() as session:
        bericht = tagesabschluss(session, welt.codes["SF1"], _heute())
    zugang = sum(float(z["menge"]) for z in bericht["zeilen"] if z["art"] == "zugang")
    korrektur = sum(float(z["menge"]) for z in bericht["zeilen"] if z["art"] == "korrektur")
    assert zugang == 10.0 and korrektur == -10.0
