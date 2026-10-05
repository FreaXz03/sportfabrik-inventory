"""Package 4a (2026-10-05): customer returns and held stock.

* A returned item is *held* (inspection), not saleable: `bestand.menge`
  (saleable) stays as it is, `bestand.menge_gesperrt` counts it. Every change
  is a movement line (rule 2) with `bestandsart`.
* Reason fit/taste: an employee books directly in an assigned branch. Any
  other reason is a request that books nothing until branch manager or head
  office approves it (decision Q8).
* Outcomes: release (back to saleable), supplier return, write-off. Employees
  may only release a fit/taste return; the rest is branch manager/head office.
"""

from conftest import ANNA, BEAT, CHEF
from sqlalchemy import select

from app.core.models import Bestand, Lagerbewegung
from app.services.betriebsberichte import pruefe_bestand

EAN = "4006632041233"


def _artikel(welt, menge="5", lagerort="SF1"):
    welt.anmelden(CHEF)
    antwort = welt.client.post(
        "/api/erfassen",
        json={
            "lagerort_id": welt.codes[lagerort],
            "positionen": [
                {"marke": "Nike", "bezeichnung": "Pegasus", "menge": menge, "uvp": "139.90", "ean": EAN}
            ],
        },
    )
    assert antwort.status_code == 200, antwort.text
    return welt.client.get(f"/api/articles?ean={EAN}").json()["items"][0]["id"]


def _stand(welt, varianten_id, lagerort="SF1"):
    with welt.sessions() as session:
        bestand = session.get(Bestand, (varianten_id, welt.codes[lagerort]))
        return str(bestand.menge), str(bestand.menge_gesperrt)


def _retoure(welt, varianten_id, grund="passform", lagerort="SF1", **extra):
    return welt.client.post(
        "/api/retouren",
        json={
            "varianten_id": varianten_id,
            "lagerort_id": welt.codes[lagerort],
            "grund": grund,
            "zustand": "gebraucht",
            **extra,
        },
    )


def test_two_returned_shoes_are_held_and_not_saleable(welt):
    varianten_id = _artikel(welt, menge="5")
    welt.anmelden(ANNA)
    for _ in range(2):
        antwort = _retoure(welt, varianten_id, erstattungsreferenz="Kasse 4711")
        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["status"] == "in_pruefung"
    # Saleable stock unchanged, both pairs held - neither is saleable automatically.
    assert _stand(welt, varianten_id) == ("5.00", "2.00")
    with welt.sessions() as session:
        arten = session.scalars(
            select(Lagerbewegung.bestandsart).where(Lagerbewegung.typ == "retoure")
        ).all()
        assert arten == ["gesperrt", "gesperrt"]
        assert pruefe_bestand(session)["ok"]
    zeile = welt.client.get("/api/bestand?lagerort_id=%d" % welt.codes["SF1"]).json()["zeilen"][0]
    assert (zeile["menge"], zeile["gesperrt"]) == ("5.00", "2.00")


def test_release_moves_one_pair_back_to_saleable(welt):
    varianten_id = _artikel(welt, menge="5")
    welt.anmelden(ANNA)
    erste = _retoure(welt, varianten_id).json()
    _retoure(welt, varianten_id)
    antwort = welt.client.post(f"/api/retouren/{erste['id']}/ergebnis", json={"ergebnis": "freigeben"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["status"] == "abgeschlossen"
    assert _stand(welt, varianten_id) == ("6.00", "1.00")
    with welt.sessions() as session:
        assert pruefe_bestand(session)["ok"]
    # Done twice is not possible.
    assert welt.client.post(f"/api/retouren/{erste['id']}/ergebnis", json={"ergebnis": "freigeben"}).status_code == 409


def test_other_reason_waits_for_approval_and_books_nothing(welt):
    varianten_id = _artikel(welt, menge="5")
    welt.anmelden(ANNA)
    antwort = _retoure(welt, varianten_id, grund="defekt")
    assert antwort.status_code == 200, antwort.text
    retoure = antwort.json()
    assert retoure["status"] == "beantragt"
    assert _stand(welt, varianten_id) == ("5.00", "0.00")
    # An employee cannot approve; the branch manager can, then the item is held.
    assert welt.client.post(f"/api/retouren/{retoure['id']}/genehmigen").status_code == 403
    welt.anmelden(CHEF)
    freigabe = welt.client.post(f"/api/retouren/{retoure['id']}/genehmigen")
    assert freigabe.status_code == 200, freigabe.text
    assert freigabe.json()["status"] == "in_pruefung"
    assert _stand(welt, varianten_id) == ("5.00", "1.00")


def test_rejected_request_books_nothing(welt):
    varianten_id = _artikel(welt)
    welt.anmelden(ANNA)
    retoure = _retoure(welt, varianten_id, grund="reklamation").json()
    welt.anmelden(CHEF)
    assert welt.client.post(f"/api/retouren/{retoure['id']}/ablehnen").json()["status"] == "abgelehnt"
    assert _stand(welt, varianten_id) == ("5.00", "0.00")


def test_write_off_and_supplier_return_are_reserved_for_managers(welt):
    varianten_id = _artikel(welt)
    welt.anmelden(ANNA)
    retoure = _retoure(welt, varianten_id).json()
    for ergebnis in ("abschreiben", "lieferant"):
        assert welt.client.post(f"/api/retouren/{retoure['id']}/ergebnis", json={"ergebnis": ergebnis}).status_code == 403
    welt.anmelden(CHEF)
    antwort = welt.client.post(f"/api/retouren/{retoure['id']}/ergebnis", json={"ergebnis": "abschreiben"})
    assert antwort.status_code == 200, antwort.text
    # Held stock gone, saleable stock untouched, journal still adds up.
    assert _stand(welt, varianten_id) == ("5.00", "0.00")
    with welt.sessions() as session:
        assert pruefe_bestand(session)["ok"]


def test_employee_may_not_book_a_return_in_a_foreign_branch(welt):
    varianten_id = _artikel(welt)
    welt.anmelden(ANNA)  # assigned to SF1 only
    assert _retoure(welt, varianten_id, lagerort="SF2").status_code == 403
    welt.anmelden(BEAT)  # SF2: allowed to book a return there, even with no stock yet
    assert _retoure(welt, varianten_id, lagerort="SF2").status_code == 200
