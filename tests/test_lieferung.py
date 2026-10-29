"""Package 1, step 2 (2026-10-01): documents of one physical delivery are
linked instead of booked twice (Q2/Q3: the delivery note comes with the goods,
the invoice usually later; whenever a document matches an existing delivery
the user is always asked — nothing is attached or booked automatically).
"""

from conftest import ANNA, CHEF
from sqlalchemy import func, select
from testbelege import importieren, kopf, rechnung_pdf

from app.core.models import (
    Bestand,
    Dokument,
    DokumentLieferung,
    Lagerbewegung,
    Preis,
    Wareneingang,
)
from app.services import importer


def _typ(monkeypatch, typ):
    original = importer.parse_with_parser
    monkeypatch.setattr(
        importer,
        "parse_with_parser",
        lambda *args, **kwargs: {**original(*args, **kwargs), "document_type": typ},
    )


def _beleg(nummer):
    return rechnung_pdf(header_lines=kopf(nummer=nummer))


def _bestand(welt, lagerort="SF1"):
    with welt.sessions() as session:
        return sorted(
            str(m)
            for m in session.scalars(
                select(Bestand.menge).where(Bestand.lagerort_id == welt.codes[lagerort])
            )
        )


def _anzahl(welt, modell):
    with welt.sessions() as session:
        return session.scalar(select(func.count()).select_from(modell))


def _kandidaten(welt, pdf, lagerort="SF1"):
    import hashlib

    antwort = welt.client.post(
        "/api/lieferung-kandidaten",
        files={"file": ("beleg.pdf", pdf, "application/pdf")},
        data={
            "expected_hash": hashlib.sha256(pdf).hexdigest(),
            "lagerort_id": str(welt.codes[lagerort]),
        },
    )
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _bestaetigung_importieren(welt, monkeypatch, nummer="1000000001"):
    """Order confirmation 5+3+2 = 10 expected at SF1."""
    _typ(monkeypatch, "auftragsbestaetigung")
    welt.anmelden(CHEF)
    antwort = importieren(welt.client, _beleg(nummer), lagerort_id=str(welt.codes["SF1"]))
    assert antwort.status_code == 200, antwort.text
    with welt.sessions() as session:
        return session.scalar(select(Wareneingang.id))


def test_confirmation_partial_arrival_attach_delivery_note_and_invoice_then_rest(welt, monkeypatch):
    """Acceptance (b): confirmation 10, receive 8, attach delivery note and
    invoice, receive 2 → stock 10, all documents linked, nothing left open."""
    wareneingang_id = _bestaetigung_importieren(welt, monkeypatch)

    welt.anmelden(ANNA)
    positionen = welt.client.get("/api/wareneingaenge").json()["wareneingaenge"][0]["positionen"]
    polo_m, polo_l, schuh = [p["id"] for p in positionen]
    teil = welt.client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft",
        json={"mengen": {str(polo_m): "5", str(polo_l): "3"}},
    )
    assert teil.status_code == 200, teil.text
    assert _bestand(welt) == ["3.00", "5.00"]

    welt.anmelden(CHEF)
    # Delivery note: the user must choose; attaching books nothing.
    _typ(monkeypatch, "lieferschein")
    lieferschein = _beleg("2000000001")
    assert importieren(welt.client, lieferschein, lagerort_id=str(welt.codes["SF1"])).status_code == 409
    antwort = importieren(
        welt.client, lieferschein, lagerort_id=str(welt.codes["SF1"]), lieferung=str(wareneingang_id)
    )
    assert antwort.status_code == 200, antwort.text
    assert _bestand(welt) == ["3.00", "5.00"]
    assert _anzahl(welt, Lagerbewegung) == 2

    # Invoice arriving later: same.
    _typ(monkeypatch, "rechnung")
    rechnung = _beleg("3000000001")
    antwort = importieren(
        welt.client, rechnung, lagerort_id=str(welt.codes["SF1"]), lieferung=str(wareneingang_id)
    )
    assert antwort.status_code == 200, antwort.text
    assert _bestand(welt) == ["3.00", "5.00"]
    assert _anzahl(welt, Wareneingang) == 1
    # The invoice's prices are kept for the matched variants (rule 10: EK if present).
    with welt.sessions() as session:
        angehaengt = session.scalars(
            select(Dokument).join(DokumentLieferung, DokumentLieferung.dokument_id == Dokument.id)
        ).all()
        assert sorted(d.typ for d in angehaengt) == ["lieferschein", "rechnung"]
        assert session.scalar(
            select(func.count()).select_from(Preis).where(Preis.dokument_id == angehaengt[0].id)
        ) == 3

    # The detail page of the confirmation lists both attached documents.
    haupt = welt.client.get("/api/invoices").json()["items"]
    haupt_id = next(i["id"] for i in haupt if i["invoice_number"] == "1000000001")
    detail = welt.client.get(f"/api/invoices/{haupt_id}").json()["invoice"]
    assert sorted(d["invoice_number"] for d in detail["attached_documents"]) == ["2000000001", "3000000001"]
    angehaengt_id = next(i["id"] for i in haupt if i["invoice_number"] == "3000000001")
    assert welt.client.get(f"/api/invoices/{angehaengt_id}").json()["invoice"]["attached_to"]["id"] == haupt_id

    # Remaining 2 arrive → complete, nothing open.
    welt.anmelden(ANNA)
    fertig = welt.client.post(
        f"/api/wareneingaenge/{wareneingang_id}/ankunft", json={"mengen": {str(schuh): "2"}}
    )
    assert fertig.status_code == 200 and fertig.json()["status"] == "eingetroffen"
    assert _bestand(welt) == ["2.00", "3.00", "5.00"]
    assert welt.client.get("/api/wareneingaenge").json()["wareneingaenge"] == []


def test_matching_document_without_choice_is_rejected_new_goods_books_as_before(welt, monkeypatch):
    """Q3: always ask. "new goods" is an explicit choice and books a second receipt."""
    _bestaetigung_importieren(welt, monkeypatch)
    _typ(monkeypatch, "rechnung")
    rechnung = _beleg("3000000002")
    assert importieren(welt.client, rechnung, lagerort_id=str(welt.codes["SF1"])).status_code == 409
    assert _anzahl(welt, Dokument) == 1
    antwort = importieren(welt.client, rechnung, lagerort_id=str(welt.codes["SF1"]), lieferung="neu")
    assert antwort.status_code == 200, antwort.text
    assert _bestand(welt) == ["2.00", "3.00", "5.00"]
    assert _anzahl(welt, Wareneingang) == 2


def test_candidates_endpoint_lists_the_matching_delivery(welt, monkeypatch):
    wareneingang_id = _bestaetigung_importieren(welt, monkeypatch)
    _typ(monkeypatch, "rechnung")
    daten = _kandidaten(welt, _beleg("3000000003"))
    assert daten["wahl_noetig"] is True
    assert [k["wareneingang_id"] for k in daten["kandidaten"]] == [wareneingang_id]
    kandidat = daten["kandidaten"][0]
    assert kandidat["dokument"]["invoice_number"] == "1000000001"
    assert kandidat["dokument"]["typ"] == "auftragsbestaetigung"
    assert (kandidat["treffer"], kandidat["zeilen"]) == (3, 3)
    # Another branch has no such delivery: nothing to choose.
    daten = _kandidaten(welt, _beleg("3000000003"), lagerort="SF2")
    assert daten == {"kandidaten": [], "wahl_noetig": False}


def test_document_without_matching_delivery_imports_normally(welt, monkeypatch):
    """No candidate → no question; an order confirmation itself never asks."""
    _typ(monkeypatch, "rechnung")
    welt.anmelden(CHEF)
    assert importieren(welt.client, _beleg("3000000004"), lagerort_id=str(welt.codes["SF2"])).status_code == 200
    _typ(monkeypatch, "auftragsbestaetigung")
    assert importieren(welt.client, _beleg("1000000005"), lagerort_id=str(welt.codes["SF2"])).status_code == 200


def test_attach_target_must_be_a_delivery_of_the_same_branch(welt, monkeypatch):
    wareneingang_id = _bestaetigung_importieren(welt, monkeypatch)
    _typ(monkeypatch, "rechnung")
    antwort = importieren(
        welt.client, _beleg("3000000005"), lagerort_id=str(welt.codes["SF2"]), lieferung=str(wareneingang_id)
    )
    assert antwort.status_code == 409
    antwort = importieren(
        welt.client, _beleg("3000000006"), lagerort_id=str(welt.codes["SF1"]), lieferung="99999"
    )
    assert antwort.status_code == 409
    assert _anzahl(welt, Dokument) == 1


def test_attached_document_can_be_deleted_but_not_its_delivery_document(welt, monkeypatch):
    wareneingang_id = _bestaetigung_importieren(welt, monkeypatch)
    _typ(monkeypatch, "rechnung")
    antwort = importieren(
        welt.client, _beleg("3000000007"), lagerort_id=str(welt.codes["SF1"]), lieferung=str(wareneingang_id)
    )
    angehaengt_id = antwort.json()["invoice_id"]
    with welt.sessions() as session:
        haupt_id = session.scalar(
            select(Dokument.id).where(
                Dokument.id.not_in(select(DokumentLieferung.dokument_id))
            )
        )

    # The confirmation has an attached document: it is not deleted behind its back.
    assert welt.client.delete(f"/api/invoices/{haupt_id}").status_code == 409
    # The attached document books nothing and may go (preserving nothing but the link).
    assert welt.client.delete(f"/api/invoices/{angehaengt_id}").status_code == 200
    assert _anzahl(welt, Dokument) == 1
    assert welt.client.delete(f"/api/invoices/{haupt_id}").status_code == 200
