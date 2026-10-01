"""Package 1, step 1 (2026-10-01): a posted document is cancelled with
counter-movements instead of being deleted (hard rule 2). Document, source
snapshot and prices stay; only a document without any posted movement may
still be deleted.
"""

from conftest import ANNA, CHEF
from sqlalchemy import func, select
from testbelege import LIEFERADRESSE_CONTHEY, importieren, kopf, rechnung_pdf

from app.core.models import (
    Bestand,
    Dokument,
    Lagerbewegung,
    Preis,
    Variante,
    Wareneingang,
    WareneingangPosition,
    WareneingangPositionQuelle,
)


def _importiere(welt, lagerort="SF2"):
    welt.anmelden(CHEF)
    pdf = rechnung_pdf(header_lines=kopf() + LIEFERADRESSE_CONTHEY)
    antwort = importieren(welt.client, pdf, lagerort_id=str(welt.codes[lagerort]))
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["invoice_id"]


def _saldo(welt, lagerort="SF2"):
    with welt.sessions() as session:
        return sorted(
            str(menge)
            for menge in session.scalars(
                select(Bestand.menge).where(Bestand.lagerort_id == welt.codes[lagerort])
            )
        )


def _verkaufe(welt, varianten_id, anzahl, lagerort="SF2"):
    for _ in range(anzahl):
        antwort = welt.client.post(
            "/api/ausbuchen",
            json={"grund": "verkauf", "varianten_id": varianten_id, "lagerort_id": welt.codes[lagerort]},
        )
        assert antwort.status_code == 200, antwort.text


def _variante_mit_menge(welt, menge):
    with welt.sessions() as session:
        return session.scalar(
            select(WareneingangPosition.varianten_id).where(WareneingangPosition.menge == menge)
        )


def test_cancel_receipt_after_sale_keeps_history_and_shows_negative_balance(welt):
    """Acceptance (a): receive 10 (5+3+2), sell 3 of the 5-piece variant, cancel
    the receipt → original and counter-movements stay, the 5-piece variant is
    at −3, nothing is deleted."""
    beleg_id = _importiere(welt)
    fuenf = _variante_mit_menge(welt, 5)
    _verkaufe(welt, fuenf, 3)

    vorschau = welt.client.get(f"/api/invoices/{beleg_id}/cancel-preview")
    assert vorschau.status_code == 200, vorschau.text
    daten = vorschau.json()
    zeile = next(z for z in daten["zeilen"] if z["varianten_id"] == fuenf)
    assert (zeile["bestand_jetzt"], zeile["wareneingang"], zeile["bestand_danach"]) == (
        "2.00", "5.00", "-3.00",
    )
    assert zeile["spaetere_bewegungen"] is True
    assert daten["hat_negativen_bestand"] is True

    antwort = welt.client.post(f"/api/invoices/{beleg_id}/cancel")
    assert antwort.status_code == 200, antwort.text

    with welt.sessions() as session:
        dokument = session.get(Dokument, beleg_id)
        assert dokument.status == "storniert"
        assert dokument.storniert_von_name == "Chef" and dokument.storniert_am is not None
        # Nothing deleted: document, receipt, positions, snapshots, prices, variants.
        assert session.scalar(select(func.count()).select_from(WareneingangPosition)) == 3
        assert session.scalar(select(func.count()).select_from(WareneingangPositionQuelle)) == 3
        assert session.scalar(select(func.count()).select_from(Preis)) > 0
        assert session.scalar(select(func.count()).select_from(Variante)) == 3
        assert session.scalar(select(Wareneingang.status)) == "storniert"
        # Original 3 receipts + 3 sales + 3 counter-movements.
        bewegungen = session.scalars(select(Lagerbewegung).order_by(Lagerbewegung.id)).all()
        assert len(bewegungen) == 9
        gegen = [b for b in bewegungen if b.grund and b.grund.startswith("storno:")]
        assert sorted(str(b.menge) for b in gegen) == ["-2.00", "-3.00", "-5.00"]
    assert _saldo(welt) == ["-3.00", "0.00", "0.00"]


def test_cancel_twice_is_rejected_and_changes_nothing(welt):
    beleg_id = _importiere(welt)
    assert welt.client.post(f"/api/invoices/{beleg_id}/cancel").status_code == 200
    zweite = welt.client.post(f"/api/invoices/{beleg_id}/cancel")
    assert zweite.status_code == 409
    with welt.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 6


def test_cancel_resets_the_markdown_clock_to_the_remaining_receipts(welt):
    """A cancelled receipt no longer counts as a delivery: the variant has no
    oldest receipt date left and no first/last seen."""
    beleg_id = _importiere(welt)
    welt.client.post(f"/api/invoices/{beleg_id}/cancel")
    with welt.sessions() as session:
        for bestand in session.scalars(select(Bestand)):
            assert bestand.aeltestes_eingangsdatum is None
        for variante in session.scalars(select(Variante)):
            assert variante.first_seen is None and variante.last_seen is None


def test_posted_document_cannot_be_deleted_only_cancelled(welt):
    beleg_id = _importiere(welt)
    antwort = welt.client.delete(f"/api/invoices/{beleg_id}")
    assert antwort.status_code == 409
    with welt.sessions() as session:
        assert session.get(Dokument, beleg_id) is not None
        assert session.scalar(select(func.count()).select_from(Lagerbewegung)) == 3


def test_cancel_is_reserved_for_managers_and_head_office(welt):
    beleg_id = _importiere(welt)
    welt.anmelden(ANNA)
    assert welt.client.get(f"/api/invoices/{beleg_id}/cancel-preview").status_code == 403
    assert welt.client.post(f"/api/invoices/{beleg_id}/cancel").status_code == 403


def test_cancelled_document_is_listed_with_its_status(welt):
    beleg_id = _importiere(welt)
    welt.client.post(f"/api/invoices/{beleg_id}/cancel")
    liste = welt.client.get("/api/invoices").json()["items"]
    assert [(i["id"], i["status"]) for i in liste] == [(beleg_id, "storniert")]
    assert welt.client.get(f"/api/invoices/{beleg_id}").json()["invoice"]["status"] == "storniert"


def test_cancel_keeps_an_older_oldest_receipt_date_that_came_from_elsewhere(welt):
    """A transfer can bring an older date (rule 6, D17). Cancelling an unrelated
    receipt must not replace it with the later date of the remaining receipt."""
    from datetime import date

    beleg_id = _importiere(welt, "SF1")
    with welt.sessions.begin() as session:
        for bestand in session.scalars(select(Bestand).where(Bestand.lagerort_id == welt.codes["SF1"])):
            bestand.aeltestes_eingangsdatum = date(2024, 1, 15)  # carried in by a transfer
    assert welt.client.post(f"/api/invoices/{beleg_id}/cancel").status_code == 200
    with welt.sessions() as session:
        daten = {b.aeltestes_eingangsdatum for b in session.scalars(select(Bestand))}
    assert daten == {date(2024, 1, 15)}


def test_non_ascii_digit_as_delivery_choice_is_rejected_not_a_server_error(welt):
    from testbelege import importieren, kopf, rechnung_pdf

    welt.anmelden(CHEF)
    antwort = importieren(
        welt.client,
        rechnung_pdf(header_lines=kopf(nummer="9100000002")),
        lagerort_id=str(welt.codes["SF1"]),
        lieferung="²",
    )
    assert antwort.status_code == 409, antwort.text
