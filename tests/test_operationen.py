"""Package 2 (2026-10-01): retry protection and the stale-count check.

* A deliberate action carries an operation ID (header `X-Operation-Id`). The
  same ID again returns the stored result and books nothing; a new ID is a new
  booking. The ID is optional on the API (decision 2026-10-01).
* A count starts with a marker (latest movement of the variant at the branch).
  If stock moved since, the server asks for a recount instead of booking
  silently (Q4). A count without a difference is recorded, too.
"""

from conftest import CHEF
from sqlalchemy import func, select

from app.core.models import Bestand, Lagerbewegung, Wareneingang, WareneingangPosition, Zaehlung

EAN = "4006632041233"


def _op(nummer):
    return {"X-Operation-Id": f"op-{nummer:04d}-aaaa-bbbb-cccc-dddddddddddd"}


def _bestand_anlegen(welt, menge="5", lagerort="SF1", ean=EAN):
    welt.anmelden(CHEF)
    antwort = welt.client.post(
        "/api/erfassen",
        json={
            "lagerort_id": welt.codes[lagerort],
            "positionen": [
                {"marke": "Nike", "bezeichnung": "Polo", "menge": menge, "uvp": "39.90", "ean": ean}
            ],
        },
    )
    assert antwort.status_code == 200, antwort.text
    return welt.client.get(f"/api/articles?ean={ean}").json()["items"][0]["id"]


def _saldo(welt, varianten_id, lagerort="SF1"):
    with welt.sessions() as session:
        bestand = session.get(Bestand, (varianten_id, welt.codes[lagerort]))
        return None if bestand is None else str(bestand.menge)


def _anzahl(welt, modell):
    with welt.sessions() as session:
        return session.scalar(select(func.count()).select_from(modell))


def _verkauf(welt, varianten_id, headers=None, lagerort="SF1"):
    return welt.client.post(
        "/api/ausbuchen",
        headers=headers or {},
        json={"grund": "verkauf", "varianten_id": varianten_id, "lagerort_id": welt.codes[lagerort]},
    )


# --- retry protection ------------------------------------------------------


def test_sale_retry_with_same_operation_id_books_once_new_id_books_again(welt):
    v = _bestand_anlegen(welt)
    erste = _verkauf(welt, v, _op(1))
    assert erste.status_code == 200 and erste.json()["bestand_nachher"] == "4.00"
    assert "wiederholt" not in erste.json()

    # Response lost, the phone retries with the same ID: one sale, same answer.
    wieder = _verkauf(welt, v, _op(1))
    assert wieder.status_code == 200, wieder.text
    assert wieder.json()["wiederholt"] is True
    assert wieder.json()["bewegung_id"] == erste.json()["bewegung_id"]
    assert _saldo(welt, v) == "4.00"

    # A second intentional scan carries a new ID: a second sale.
    assert _verkauf(welt, v, _op(2)).json()["bestand_nachher"] == "3.00"
    # Without an ID nothing is protected (optional on the API).
    _verkauf(welt, v)
    _verkauf(welt, v)
    assert _saldo(welt, v) == "1.00"


def test_operation_id_reused_for_other_content_or_user_is_rejected(welt):
    v = _bestand_anlegen(welt)
    assert _verkauf(welt, v, _op(1)).status_code == 200
    # Same ID, different request.
    anders = welt.client.post(
        "/api/ausbuchen",
        headers=_op(1),
        json={"grund": "defekt", "varianten_id": v, "lagerort_id": welt.codes["SF1"]},
    )
    assert anders.status_code == 409
    assert _saldo(welt, v) == "4.00"
    # Same ID by another user.
    from conftest import ANNA

    welt.anmelden(ANNA)
    assert _verkauf(welt, v, _op(1)).status_code == 409
    assert _saldo(welt, v) == "4.00"


def test_malformed_operation_id_is_rejected(welt):
    v = _bestand_anlegen(welt)
    for kaputt in ("x", "a b c d e f g h", "../../etc/x", "a" * 100):
        antwort = _verkauf(welt, v, {"X-Operation-Id": kaputt})
        assert antwort.status_code == 422, kaputt
    assert _saldo(welt, v) == "5.00"


def test_rejected_attempt_is_not_remembered(welt):
    """A refused request stores nothing: the same ID may be used again once the
    cause is fixed."""
    v = _bestand_anlegen(welt)
    falsch = welt.client.post(
        "/api/ausbuchen", headers=_op(1), json={"grund": "unbekannt", "varianten_id": v, "lagerort_id": welt.codes["SF1"]}
    )
    assert falsch.status_code == 409
    assert _verkauf(welt, v, _op(1)).status_code == 200
    assert _saldo(welt, v) == "4.00"


def test_count_transfer_arrival_and_entry_retries_book_once(welt):
    v = _bestand_anlegen(welt, "5")

    # Manual entry retried: stock stays 5 + 2, not 5 + 4.
    eintrag = {
        "lagerort_id": welt.codes["SF1"],
        "positionen": [{"marke": "Nike", "bezeichnung": "Polo", "menge": "2", "uvp": "39.90", "ean": EAN}],
    }
    assert welt.client.post("/api/erfassen", headers=_op(10), json=eintrag).status_code == 200
    wieder = welt.client.post("/api/erfassen", headers=_op(10), json=eintrag)
    assert wieder.status_code == 200 and wieder.json()["wiederholt"] is True
    assert _saldo(welt, v) == "7.00"

    # Count retried: one correction movement.
    zaehlung = {"varianten_id": v, "lagerort_id": welt.codes["SF1"], "gezaehlt": "6", "grund": "inventur"}
    erste = welt.client.post("/api/korrektur", headers=_op(11), json=zaehlung)
    assert erste.status_code == 200 and erste.json()["differenz"] == "-1.00"
    wieder = welt.client.post("/api/korrektur", headers=_op(11), json=zaehlung)
    assert wieder.json()["wiederholt"] is True and wieder.json()["bewegung_id"] == erste.json()["bewegung_id"]
    assert _saldo(welt, v) == "6.00"

    # Transfer retried: 3 leave once, one expected receipt.
    umlagerung = {
        "quelle_id": welt.codes["SF1"],
        "ziel_id": welt.codes["SF2"],
        "positionen": [{"varianten_id": v, "menge": "3"}],
    }
    erste = welt.client.post("/api/umlagerung", headers=_op(12), json=umlagerung)
    assert erste.status_code == 200, erste.text
    wieder = welt.client.post("/api/umlagerung", headers=_op(12), json=umlagerung)
    assert wieder.json()["wiederholt"] is True
    assert wieder.json()["wareneingang_id"] == erste.json()["wareneingang_id"]
    assert _saldo(welt, v) == "3.00"
    with welt.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Wareneingang).where(Wareneingang.status == "erwartet")) == 1

    # Partial arrival retried: 2 arrive once.
    we_id = erste.json()["wareneingang_id"]
    with welt.sessions() as session:
        position = session.scalar(
            select(WareneingangPosition.id).where(WareneingangPosition.wareneingang_id == we_id)
        )
    ankunft = {"mengen": {str(position): "2"}}
    erste = welt.client.post(f"/api/wareneingaenge/{we_id}/ankunft", headers=_op(13), json=ankunft)
    assert erste.status_code == 200, erste.text
    wieder = welt.client.post(f"/api/wareneingaenge/{we_id}/ankunft", headers=_op(13), json=ankunft)
    assert wieder.status_code == 200 and wieder.json()["wiederholt"] is True
    assert _saldo(welt, v, "SF2") == "2.00"


# --- stale-count check -----------------------------------------------------


def _marker(welt, varianten_id, lagerort="SF1"):
    zeilen = welt.client.get(f"/api/bestand?nur_vorhanden=false&lagerort_id={welt.codes[lagerort]}&limit=500").json()
    zeile = next(z for z in zeilen["zeilen"] if z["varianten_id"] == varianten_id)
    return zeile["letzte_bewegung_id"], zeile


def _zaehlen(welt, varianten_id, gezaehlt, marker=None, **extra):
    body = {
        "varianten_id": varianten_id,
        "lagerort_id": welt.codes["SF1"],
        "gezaehlt": gezaehlt,
        "grund": "inventur",
        **extra,
    }
    if marker is not None:
        body["stand_bewegung_id"] = marker
    return welt.client.post("/api/korrektur", json=body)


def test_count_after_stock_moved_asks_for_a_recount_and_books_nothing(welt):
    """Count 7, a colleague sells 1, submit 7 → no extra unit appears silently."""
    v = _bestand_anlegen(welt, "8")
    marker, zeile = _marker(welt, v)
    assert zeile["menge"] == "8.00"
    assert _verkauf(welt, v).status_code == 200  # colleague sells one: 7 now

    antwort = _zaehlen(welt, v, "7", marker)
    assert antwort.status_code == 409, antwort.text
    daten = antwort.json()
    assert daten["code"] == "bestand_geaendert"
    assert daten["bestand_jetzt"] == "7.00"
    assert [(b["typ"], b["menge"]) for b in daten["seit_zaehlbeginn"]] == [("verkauf", "-1.00")]
    assert daten["stand_bewegung_id"] > marker
    # Nothing booked, nothing recorded.
    assert _saldo(welt, v) == "7.00"
    assert _anzahl(welt, Zaehlung) == 0
    assert _anzahl(welt, Lagerbewegung) == 2


def test_explicit_confirmation_books_against_the_current_stock(welt):
    v = _bestand_anlegen(welt, "8")
    marker, _ = _marker(welt, v)
    _verkauf(welt, v)  # 7 now
    antwort = _zaehlen(welt, v, "6", marker, bestaetigt=True)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["differenz"] == "-1.00" and antwort.json()["gebucht"] is True
    assert _saldo(welt, v) == "6.00"
    with welt.sessions() as session:
        zaehlung = session.scalar(select(Zaehlung))
        assert zaehlung.bestaetigt_trotz_aenderung is True


def test_fresh_count_books_normally_and_missing_marker_skips_the_check(welt):
    v = _bestand_anlegen(welt, "8")
    marker, _ = _marker(welt, v)
    assert _zaehlen(welt, v, "7", marker).status_code == 200
    assert _saldo(welt, v) == "7.00"
    _verkauf(welt, v)  # moved again, but this client sends no marker (optional)
    assert _zaehlen(welt, v, "5").status_code == 200
    assert _saldo(welt, v) == "5.00"


def test_count_without_difference_is_recorded(welt):
    v = _bestand_anlegen(welt, "8")
    marker, _ = _marker(welt, v)
    antwort = _zaehlen(welt, v, "8", marker)
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["gebucht"] is False and daten["bewegung_id"] is None and daten["zaehlung_id"]
    assert _anzahl(welt, Lagerbewegung) == 1  # only the receipt: no movement for "no difference"
    with welt.sessions() as session:
        zaehlung = session.get(Zaehlung, daten["zaehlung_id"])
        assert (str(zaehlung.gezaehlt), str(zaehlung.bestand_vorher), str(zaehlung.differenz)) == ("8.00", "8.00", "0.00")
        assert zaehlung.bewegung_id is None
        assert zaehlung.benutzer_kassennummer == CHEF


def test_count_with_difference_is_recorded_and_linked_to_its_movement(welt):
    v = _bestand_anlegen(welt, "8")
    antwort = _zaehlen(welt, v, "6")
    with welt.sessions() as session:
        zaehlung = session.scalar(select(Zaehlung))
        assert zaehlung.bewegung_id == antwort.json()["bewegung_id"]
        assert str(zaehlung.differenz) == "-2.00"
