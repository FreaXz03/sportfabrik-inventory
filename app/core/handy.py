"""Phone access (decision 28.09.2026, docs/handynutzung.md).

A login from a phone may only use the agreed phone features. The server
enforces this in `app.routers.auth.phone_gate`; roles and branch limits
apply on top, unchanged. Tablets get the desktop version.
"""

import re

_PHONE_USER_AGENT = re.compile(r"iPhone|iPod|Mobi|Windows Phone", re.IGNORECASE)

PHONE_PAGE_PREFIX = "/m"

# (method, route path) exactly as registered in the routers.
PHONE_ROUTES = {
    # sign-in, branch, language
    ("GET", "/login"),
    ("POST", "/login"),
    ("POST", "/logout"),
    ("GET", "/api/me"),
    ("POST", "/api/active-lagerort"),
    ("POST", "/api/language"),
    # search and article info (price, size, colour, stock in all branches)
    ("GET", "/api/articles"),
    ("GET", "/api/bestand"),
    ("GET", "/api/articles/{product_id}/prices"),
    ("GET", "/api/articles/{varianten_id}/reduktion"),
    # count and correct
    ("GET", "/api/korrektur/gruende"),
    ("POST", "/api/korrektur"),
    # confirm goods arrival
    ("GET", "/api/wareneingaenge"),
    ("POST", "/api/wareneingaenge/{wareneingang_id}/ankunft"),
    # transfer
    ("GET", "/api/umlagerung/stammdaten"),
    ("POST", "/api/umlagerung"),
    # write off (cancelling stays on the computer)
    ("GET", "/api/ausbuchen/stammdaten"),
    ("POST", "/api/ausbuchen"),
    # manual goods entry
    ("GET", "/api/erfassen/stammdaten"),
    ("GET", "/api/erfassen/variante"),
    ("POST", "/api/erfassen"),
    # manual reduction and "reduction done"
    ("PUT", "/api/reduktion/manuell"),
    ("DELETE", "/api/reduktion/manuell"),
    ("GET", "/api/reduktionen"),
    ("POST", "/api/reduktionen/bestaetigen"),
    # recent activity and notices
    ("GET", "/api/dashboard"),
}


def is_phone(user_agent: str | None) -> bool:
    return bool(user_agent) and _PHONE_USER_AGENT.search(user_agent) is not None


def phone_may_use(method: str, route_path: str) -> bool:
    if route_path == PHONE_PAGE_PREFIX or route_path.startswith(PHONE_PAGE_PREFIX + "/"):
        return method in ("GET", "HEAD")
    if method == "HEAD":
        method = "GET"
    return (method, route_path) in PHONE_ROUTES
