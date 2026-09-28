"""Phone access (decision 28.09.2026): a login from a phone may only use the
agreed phone features. The server enforces this; hiding buttons is not enough."""

from decimal import Decimal

from conftest import ANNA, CHEF, PASSWOERTER, ZENTRALE

from app.core.i18n import translate

IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)
ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36"
)
ANDROID_TABLET = (
    "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)
MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Safari/605.1.15"
)
BLOCKED = translate("errors.phone.not_available", "de")


def _login(welt, kassennummer, user_agent):
    welt.client.post("/logout")
    daten = {"kassennummer": kassennummer}
    if PASSWOERTER[kassennummer]:
        daten["password"] = PASSWOERTER[kassennummer]
    antwort = welt.client.post("/login", data=daten, headers={"User-Agent": user_agent})
    assert antwort.status_code == 200, antwort.text


def test_which_devices_count_as_phone():
    from app.core.handy import is_phone

    assert is_phone(IPHONE) and is_phone(ANDROID)
    # Tablets get the desktop version (iPadOS reports itself as a Mac anyway).
    assert not is_phone(ANDROID_TABLET) and not is_phone(MAC)
    assert not is_phone(None) and not is_phone("")


def test_phone_only_reaches_the_agreed_features(welt):
    _login(welt, ZENTRALE, IPHONE)
    c = welt.client
    antwort = c.post("/api/active-lagerort", json={"lagerort_id": welt.codes["SF1"]},
                     headers={"User-Agent": IPHONE})
    assert antwort.status_code == 200, antwort.text

    for url in ("/api/me", "/api/bestand", "/api/articles", "/api/dashboard",
                "/api/wareneingaenge", "/api/korrektur/gruende", "/api/reduktionen"):
        assert c.get(url, headers={"User-Agent": IPHONE}).status_code == 200, url

    blocked_api = [
        ("GET", "/api/konten"), ("GET", "/api/statistik"), ("GET", "/api/invoices"),
        ("GET", "/api/articles/export"), ("POST", "/upload-preview"),
        ("POST", "/api/ausbuchen/1/storno"), ("DELETE", "/api/articles/1"),
        ("POST", "/api/empfehlungen"), ("PUT", "/api/schnellzugriffe"),
    ]
    for method, url in blocked_api:
        antwort = c.request(method, url, headers={"User-Agent": IPHONE})
        assert antwort.status_code == 403, (method, url)
        assert antwort.json()["detail"] == BLOCKED, (method, url)

    for url in ("/", "/statistiken", "/konten", "/preview", "/articles"):
        antwort = c.get(url, headers={"User-Agent": IPHONE}, follow_redirects=False)
        assert antwort.status_code == 303 and antwort.headers["location"] == "/m", url

    # "Request desktop site" after logging in does not unlock anything.
    assert c.get("/api/konten", headers={"User-Agent": MAC}).status_code == 403

    # The same account on a computer keeps everything.
    _login(welt, ZENTRALE, MAC)
    assert c.get("/api/konten", headers={"User-Agent": MAC}).status_code == 200


def test_session_from_before_the_phone_rule_is_limited_on_a_phone(welt):
    _login(welt, ZENTRALE, MAC)
    antwort = welt.client.get("/api/konten", headers={"User-Agent": ANDROID})
    assert antwort.status_code == 403 and antwort.json()["detail"] == BLOCKED


def test_roles_still_apply_on_the_phone(welt):
    _login(welt, ANNA, ANDROID)
    c = welt.client
    assert c.get("/api/korrektur/gruende", headers={"User-Agent": ANDROID}).status_code == 200
    antwort = c.post("/api/umlagerung", json={}, headers={"User-Agent": ANDROID})
    assert antwort.status_code == 403
    assert antwort.json()["detail"] == translate("errors.auth.chef_required", "de")


def test_login_page_and_static_files_work_on_the_phone(welt):
    c = welt.client
    c.post("/logout")
    assert c.get("/login", headers={"User-Agent": IPHONE}).status_code == 200
    assert c.get("/static/css/app.css", headers={"User-Agent": IPHONE}).status_code == 200


def test_every_allowed_phone_route_exists():
    from fastapi.routing import APIRoute

    from app.core.handy import PHONE_ROUTES
    from app.main import app

    def api_routes(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
            elif hasattr(route, "original_router"):  # included router (FastAPI >= 0.140)
                yield from api_routes(route.original_router.routes)

    existing = {(m, r.path) for r in api_routes(app.routes) for m in r.methods}
    assert len(existing) > 50
    assert PHONE_ROUTES - existing == set()


def test_phone_home_needs_login_and_can_be_installed(welt):
    c = welt.client
    c.post("/logout")
    antwort = c.get("/m", headers={"User-Agent": IPHONE}, follow_redirects=False)
    assert antwort.status_code == 303 and antwort.headers["location"] == "/login?next=/m"

    _login(welt, ANNA, IPHONE)
    antwort = c.get("/m", headers={"User-Agent": IPHONE})
    assert antwort.status_code == 200 and 'rel="manifest"' in antwort.text
    assert c.get("/m/suche", headers={"User-Agent": IPHONE}).status_code == 200

    manifest = c.get("/static/manifest.webmanifest").json()
    assert manifest["start_url"] == "/m" and manifest["display"] == "standalone"
    for icon in manifest["icons"]:
        assert c.get(icon["src"]).status_code == 200, icon["src"]


def test_count_and_correct_on_the_phone(welt):
    _login(welt, ANNA, IPHONE)
    c = welt.client
    h = {"User-Agent": IPHONE}
    assert c.get("/m/zaehlen", headers=h).status_code == 200

    # Employees may book goods in by hand in their own store (rule 9) - on the
    # phone too, and that gives us something to count.
    antwort = c.post("/api/erfassen", headers=h, json={
        "lagerort_id": welt.codes["SF1"],
        "positionen": [{"marke": "Nike", "bezeichnung": "Polo", "menge": "3", "uvp": "39.90", "ean": "4006632041233"}],
    })
    assert antwort.status_code == 200, antwort.text
    variante = c.get("/api/articles?ean=4006632041233", headers=h).json()["items"][0]["id"]

    antwort = c.post("/api/korrektur", headers=h, json={
        "varianten_id": variante, "lagerort_id": welt.codes["SF1"], "gezaehlt": "1", "grund": "inventur",
    })
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["gebucht"] and Decimal(antwort.json()["differenz"]) == -2

    antwort = c.post("/api/korrektur", headers=h, json={
        "varianten_id": variante, "lagerort_id": welt.codes["SF2"], "gezaehlt": "5", "grund": "inventur",
    })
    assert antwort.status_code == 403


def _erwartete_lieferung(welt, lagerort_code="SF1"):
    """Creates an expected delivery (order confirmation, not yet arrived) directly
    in the test database - manual entry (used elsewhere in this file) always
    books immediately and never leaves anything `erwartet` (D27)."""
    from datetime import date

    from app.core.models import Artikel, Dokument, Variante, Wareneingang, WareneingangPosition

    with welt.sessions.begin() as session:
        dokument = Dokument(typ="auftragsbestaetigung", dokumentnummer="AB-1001", dokumentdatum=date(2026, 9, 1))
        session.add(dokument)
        session.flush()
        artikel = Artikel(marke="Nike", lieferanten_artikelnr="DH0857-100", bezeichnung="Poloshirt Court")
        session.add(artikel)
        session.flush()
        variante = Variante(artikel_id=artikel.id, farbe="Weiss", groesse="M", ean="4006632041233")
        session.add(variante)
        session.flush()
        wareneingang = Wareneingang(dokument_id=dokument.id, lagerort_id=welt.codes[lagerort_code], status="erwartet")
        session.add(wareneingang)
        session.flush()
        position = WareneingangPosition(wareneingang_id=wareneingang.id, varianten_id=variante.id, menge="5")
        session.add(position)
        session.flush()
        return wareneingang.id, position.id


def test_confirm_goods_arrival_on_the_phone(welt):
    wareneingang_id, position_id = _erwartete_lieferung(welt)
    _login(welt, ANNA, IPHONE)
    c = welt.client
    h = {"User-Agent": IPHONE}
    assert c.get("/m/lieferungen", headers=h).status_code == 200

    liste = c.get("/api/wareneingaenge", headers=h).json()["wareneingaenge"]
    assert len(liste) == 1 and liste[0]["id"] == wareneingang_id

    # Partial arrival: 3 of 5 pieces.
    antwort = c.post(f"/api/wareneingaenge/{wareneingang_id}/ankunft", headers=h,
                      json={"mengen": {str(position_id): "3"}, "eingangsdatum": "2026-09-15"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["status"] == "erwartet"

    rest = c.get("/api/wareneingaenge", headers=h).json()["wareneingaenge"][0]["positionen"][0]
    assert rest["menge_offen"] == "2.00"

    # The rest: fully booked, no longer listed.
    antwort = c.post(f"/api/wareneingaenge/{wareneingang_id}/ankunft", headers=h,
                      json={"mengen": {str(position_id): "2"}})
    assert antwort.status_code == 200 and antwort.json()["status"] == "eingetroffen"
    assert c.get("/api/wareneingaenge", headers=h).json()["wareneingaenge"] == []


def test_transfer_on_the_phone_is_reserved_for_managers(welt):
    """Rule 9: transferring is reserved for branch managers and head office -
    on the phone too, and the page itself redirects employees away."""
    _login(welt, CHEF, IPHONE)
    c = welt.client
    h = {"User-Agent": IPHONE}

    antwort = c.post("/api/erfassen", headers=h, json={
        "lagerort_id": welt.codes["SF1"],
        "positionen": [{"marke": "Nike", "bezeichnung": "Polo", "menge": "5", "uvp": "39.90", "ean": "4006632041233"}],
    })
    assert antwort.status_code == 200, antwort.text
    variante = c.get("/api/articles?ean=4006632041233", headers=h).json()["items"][0]["id"]

    antwort = c.get("/m/umlagern", headers=h, follow_redirects=False)
    assert antwort.status_code == 200

    stamm = c.get("/api/umlagerung/stammdaten", headers=h).json()
    assert stamm["ziel_aktiv"] == welt.codes["SF1"]

    antwort = c.post("/api/umlagerung", headers=h, json={
        "quelle_id": welt.codes["SF1"], "ziel_id": welt.codes["SF2"],
        "positionen": [{"varianten_id": variante, "menge": "2"}],
    })
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["ziel"]["code"] == "SF2" and antwort.json()["stueck"] == "2.00"

    _login(welt, ANNA, IPHONE)
    assert c.get("/m/umlagern", headers=h, follow_redirects=False).status_code == 303
    assert c.get("/api/umlagerung/stammdaten", headers=h).status_code == 403
    assert c.post("/api/umlagerung", headers=h, json={
        "quelle_id": welt.codes["SF1"], "ziel_id": welt.codes["SF2"], "positionen": [],
    }).status_code == 403


def test_write_off_on_the_phone_is_reserved_for_managers(welt):
    """Rule 9: booking out a sale/removal is reserved for branch managers and
    head office. Each tap books exactly one piece (F15); the negative-stock
    warning (F9) works as on desktop."""
    _login(welt, CHEF, IPHONE)
    c = welt.client
    h = {"User-Agent": IPHONE}

    antwort = c.post("/api/erfassen", headers=h, json={
        "lagerort_id": welt.codes["SF1"],
        "positionen": [{"marke": "Nike", "bezeichnung": "Polo", "menge": "1", "uvp": "39.90", "ean": "4006632041233"}],
    })
    assert antwort.status_code == 200, antwort.text
    variante = c.get("/api/articles?ean=4006632041233", headers=h).json()["items"][0]["id"]

    assert c.get("/m/ausbuchen", headers=h, follow_redirects=False).status_code == 200

    stamm = c.get("/api/ausbuchen/stammdaten", headers=h).json()
    assert stamm["lagerort_aktiv"] == welt.codes["SF1"]
    assert "verkauf" in stamm["gruende"]

    erste = c.post("/api/ausbuchen", headers=h, json={
        "grund": "verkauf", "varianten_id": variante, "lagerort_id": welt.codes["SF1"],
    })
    assert erste.status_code == 200, erste.text
    assert erste.json()["bestand_nachher"] == "0.00" and not erste.json()["bestand_reicht_nicht"]

    zweite = c.post("/api/ausbuchen", headers=h, json={
        "grund": "verkauf", "varianten_id": variante, "lagerort_id": welt.codes["SF1"],
    })
    assert zweite.status_code == 200
    assert zweite.json()["bestand_nachher"] == "-1.00" and zweite.json()["bestand_reicht_nicht"]

    # Cancelling stays on the computer - not offered on the phone.
    assert c.post(f"/api/ausbuchen/{erste.json()['bewegung_id']}/storno", headers=h).status_code == 403

    # Employees may book sales - only sales, only in their stores (28.09.2026).
    _login(welt, ANNA, IPHONE)
    assert c.get("/m/ausbuchen", headers=h, follow_redirects=False).status_code == 200
    assert c.get("/api/ausbuchen/stammdaten", headers=h).json()["gruende"] == ["verkauf"]
    assert c.post("/api/ausbuchen", headers=h, json={"grund": "verkauf", "varianten_id": variante}).status_code == 200
    assert c.post("/api/ausbuchen", headers=h, json={"grund": "defekt", "varianten_id": variante}).status_code == 403


def test_manual_goods_entry_on_the_phone(welt):
    """Rule 9: employees may book in by hand, but only in their own stores
    (D21); branch managers and head office may book to any location."""
    _login(welt, ANNA, IPHONE)
    c = welt.client
    h = {"User-Agent": IPHONE}

    assert c.get("/m/erfassen", headers=h, follow_redirects=False).status_code == 200
    stamm = c.get("/api/erfassen/stammdaten", headers=h).json()
    assert stamm["lagerort_aktiv"] == welt.codes["SF1"]
    assert {lo["id"] for lo in stamm["lagerorte"]} == {welt.codes["SF1"]}

    antwort = c.post("/api/erfassen", headers=h, json={
        "lagerort_id": welt.codes["SF1"],
        "positionen": [{"marke": "Nike", "bezeichnung": "Poloshirt", "menge": "3", "uvp": "39.90",
                         "farbe": "Weiss", "groesse": "M", "ean": "4006632041233"}],
    })
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["positionen"] == 1

    # A known EAN is looked up and pre-fills the suggestion.
    treffer = c.get("/api/erfassen/variante?ean=4006632041233", headers=h).json()
    assert treffer["gefunden"] and treffer["variante"]["marke"] == "Nike"

    # An employee cannot book to a store they are not assigned to.
    abgelehnt = c.post("/api/erfassen", headers=h, json={
        "lagerort_id": welt.codes["SF3"],
        "positionen": [{"marke": "Nike", "bezeichnung": "Poloshirt", "menge": "1", "uvp": "39.90"}],
    })
    assert abgelehnt.status_code == 403

    # A branch manager may book to any location.
    _login(welt, CHEF, IPHONE)
    manager = c.post("/api/erfassen", headers=h, json={
        "lagerort_id": welt.codes["GEWA"],
        "positionen": [{"marke": "Nike", "bezeichnung": "Poloshirt", "menge": "1", "uvp": "39.90"}],
    })
    assert manager.status_code == 200, manager.text


def test_reductions_on_the_phone(welt):
    """Rule 6/D5: mark-down list with a "Done" button, plus manual reduction
    30/50/70% - open to everyone, but only in the employee's own stores."""
    from datetime import date

    from testbelege import importieren, kopf, rechnung_pdf

    from app.core.models import Artikel
    from app.services.uebersicht import _monate_zurueck
    from sqlalchemy import select

    heute = date.today()
    c = welt.client

    # Setup: a document import is desktop-only (rule 9) - done from a
    # desktop session, before switching to the phone for the actual test.
    welt.anmelden(CHEF)
    eingang = _monate_zurueck(heute, 40)
    pdf = rechnung_pdf(
        header_lines=kopf(nummer="9100000001", datum=eingang.strftime("%d.%m.%Y")),
        rows=[["Nike", "224100", "A1", "1", "4006632041234", "Poloshirt", "5", "Stk", "49.90", "20.00"]],
    )
    assert importieren(c, pdf, lagerort_id=str(welt.codes["SF1"])).status_code == 200, "setup import failed"

    _login(welt, CHEF, IPHONE)
    h = {"User-Agent": IPHONE}

    assert c.get("/m/runterschreiben", headers=h, follow_redirects=False).status_code == 200
    liste = c.get("/api/reduktionen", headers=h).json()
    assert liste["lagerort"]["code"] == "SF1"
    assert [(a["lieferanten_artikelnr"], a["stand"], a["stufe"]) for a in liste["artikel"]] == [("A1", "faellig", 70)]

    with welt.sessions() as session:
        polo_id = session.scalar(select(Artikel.id).where(Artikel.lieferanten_artikelnr == "A1"))

    # Mark the due model as done -> it drops off the due list.
    bestaetigt = c.post("/api/reduktionen/bestaetigen", headers=h, json={
        "artikel_id": polo_id, "lagerort_id": welt.codes["SF1"], "stufe": 70,
    })
    assert bestaetigt.status_code == 200, bestaetigt.text
    assert c.get("/api/reduktionen", headers=h).json()["artikel"] == []

    # Manual reduction: an employee may set it only in their own store.
    variante = c.get("/api/articles?ean=4006632041234", headers=h).json()["items"][0]["id"]
    _login(welt, ANNA, IPHONE)
    gesetzt = c.put("/api/reduktion/manuell", headers=h, json={
        "varianten_id": variante, "lagerort_id": welt.codes["SF1"], "prozent": 50,
    })
    assert gesetzt.status_code == 200, gesetzt.text
    assert gesetzt.json()["manuell"] == 50 and gesetzt.json()["wirksam"] == 50

    verboten = c.put("/api/reduktion/manuell", headers=h, json={
        "varianten_id": variante, "lagerort_id": welt.codes["SF2"], "prozent": 50,
    })
    assert verboten.status_code == 403
