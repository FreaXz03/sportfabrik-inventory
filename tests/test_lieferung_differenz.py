"""Package 4b (2026-10-05): explicit outcomes for the open remainder of a delivery.

Ship 10, receive 9: the 10th piece is an open remainder. It stays open
("under investigation", any employee of the receiving branch may mark that)
until branch manager/head office close it explicitly: *lost in transit* (a
linked loss record, no unit reappears at the source) or - for supplier
deliveries - *supplier cancelled the remainder*. Closing the last open
remainder closes the delivery (`abgeschlossen`).
"""

from conftest import ANNA, BEAT, CHEF
from sqlalchemy import func, select

from app.core.models import Bestand, Lagerbewegung, LieferungDifferenz, Wareneingang

EAN = "4006632041233"


def _versendet(welt, menge="10"):
    """10 Stück in SF1, Filialleiter versendet sie nach SF2; SF2 bestätigt 9."""
    welt.anmelden(CHEF)
    antwort = welt.client.post(
        "/api/erfassen",
        json={
            "lagerort_id": welt.codes["SF1"],
            "positionen": [{"marke": "Nike", "bezeichnung": "Pegasus", "menge": menge, "uvp": "139.90", "ean": EAN}],
        },
    )
    assert antwort.status_code == 200, antwort.text
    varianten_id = welt.client.get(f"/api/articles?ean={EAN}").json()["items"][0]["id"]
    versand = welt.client.post(
        "/api/umlagerung",
        json={
            "quelle_id": welt.codes["SF1"],
            "ziel_id": welt.codes["SF2"],
            "positionen": [{"varianten_id": varianten_id, "menge": menge}],
        },
    )
    assert versand.status_code == 200, versand.text
    welt.anmelden(BEAT)
    erwartet = welt.client.get("/api/wareneingaenge").json()["wareneingaenge"][0]
    position_id = erwartet["positionen"][0]["id"]
    ankunft = welt.client.post(
        f"/api/wareneingaenge/{erwartet['id']}/ankunft", json={"mengen": {str(position_id): "9"}}
    )
    assert ankunft.status_code == 200, ankunft.text
    assert ankunft.json()["status"] == "erwartet"  # one piece still open
    return varianten_id, erwartet["id"], position_id


def _differenz(welt, wareneingang_id, position_id, art, menge="1", notiz=None):
    return welt.client.post(
        f"/api/wareneingaenge/{wareneingang_id}/differenz",
        json={"position_id": position_id, "art": art, "menge": menge, "notiz": notiz},
    )


def _bewegungen(welt):
    with welt.sessions() as session:
        return session.scalar(select(func.count()).select_from(Lagerbewegung))


def test_lost_in_transit_closes_the_delivery_without_a_stock_movement(welt):
    varianten_id, wareneingang_id, position_id = _versendet(welt)
    bewegungen = _bewegungen(welt)

    # An employee of the receiving branch may flag the shortage for investigation ...
    antwort = _differenz(welt, wareneingang_id, position_id, "in_klaerung", notiz="Karton zählen")
    assert antwort.status_code == 200, antwort.text
    erwartet = welt.client.get("/api/wareneingaenge").json()["wareneingaenge"][0]
    assert erwartet["positionen"][0]["menge_offen"] == "1.00"
    assert erwartet["positionen"][0]["differenzen"][0]["art"] == "in_klaerung"
    # ... but only branch manager/head office can declare it lost.
    assert _differenz(welt, wareneingang_id, position_id, "verloren").status_code == 403

    welt.anmelden(CHEF)
    antwort = _differenz(welt, wareneingang_id, position_id, "verloren", notiz="Spedition meldet Verlust")
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["status"] == "abgeschlossen"

    # Closed with a linked loss: no longer expected, no stock movement, nothing back at the source.
    assert welt.client.get("/api/wareneingaenge").json()["wareneingaenge"] == []
    assert _bewegungen(welt) == bewegungen
    with welt.sessions() as session:
        assert str(session.get(Bestand, (varianten_id, welt.codes["SF1"])).menge) == "0.00"
        assert str(session.get(Bestand, (varianten_id, welt.codes["SF2"])).menge) == "9.00"
        assert session.get(Wareneingang, wareneingang_id).status == "abgeschlossen"
        arten = {(d.art, str(d.menge)) for d in session.scalars(select(LieferungDifferenz))}
        assert ("verloren", "1.00") in arten
        # The "under investigation" note is resolved by the loss declaration.
        offen = session.scalars(
            select(LieferungDifferenz).where(
                LieferungDifferenz.art == "in_klaerung", LieferungDifferenz.aufgeloest_am.is_(None)
            )
        ).all()
        assert offen == []


def test_more_than_the_open_remainder_is_rejected(welt):
    _, wareneingang_id, position_id = _versendet(welt)
    welt.anmelden(CHEF)
    assert _differenz(welt, wareneingang_id, position_id, "verloren", menge="2").status_code == 409
    assert _differenz(welt, wareneingang_id, position_id, "verloren", menge="0").status_code == 409
    assert _differenz(welt, wareneingang_id, position_id, "unbekannt").status_code == 409


def test_supplier_cancellation_is_not_possible_for_a_transfer(welt):
    _, wareneingang_id, position_id = _versendet(welt)
    welt.anmelden(CHEF)
    assert _differenz(welt, wareneingang_id, position_id, "lieferant_storniert").status_code == 409


def test_employee_of_another_branch_cannot_flag_a_difference(welt):
    _, wareneingang_id, position_id = _versendet(welt)
    welt.anmelden(ANNA)  # SF1 only, the delivery is expected in SF2
    assert _differenz(welt, wareneingang_id, position_id, "in_klaerung").status_code == 403


def test_cancelling_a_transfer_does_not_return_units_declared_lost(welt):
    varianten_id, _, _ = _versendet(welt, menge="10")  # SF2 now holds 9
    welt.anmelden(CHEF)
    versand = welt.client.post(
        "/api/umlagerung",
        json={
            "quelle_id": welt.codes["SF2"],
            "ziel_id": welt.codes["SF1"],
            "positionen": [{"varianten_id": varianten_id, "menge": "5"}],
        },
    )
    assert versand.status_code == 200, versand.text
    wareneingang_id = versand.json()["wareneingang_id"]
    unterwegs = welt.client.get(f"/api/umlagerung/unterwegs?quelle_id={welt.codes['SF2']}").json()["umlagerungen"]
    position_id = unterwegs[0]["positionen"][0]["id"]
    assert _differenz(welt, wareneingang_id, position_id, "verloren", menge="2").status_code == 200
    storno = welt.client.post(f"/api/umlagerung/{wareneingang_id}/stornieren")
    assert storno.status_code == 200, storno.text
    # Only the 3 pieces that were neither lost nor arrived go back to SF2.
    assert storno.json()["stueck"] == "3.00"
