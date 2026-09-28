"""Phone access (decision 28.09.2026): a login from a phone may only use the
agreed phone features. The server enforces this; hiding buttons is not enough."""

from decimal import Decimal

from conftest import ANNA, PASSWOERTER, ZENTRALE

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
