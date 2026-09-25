"""Ablauf „Statistik" (Anforderung 9, 24.09.2026): verkaufte Stück je
Kassenkategorie, geschätzte Einnahmen und eine Bestellempfehlung, je Zeitraum
(Tag/Woche/Monat/Jahr/Insgesamt). Nur Filialleiter/Zentrale (Regel 9,
Anforderung: "Statistikenseite nur für Filialleiter und Zentrale").

Die Einnahmen sind ausdrücklich eine **Schätzung** (Entscheid 24.09.2026):
UVP zum Verkaufszeitpunkt (gültiger Preis, sonst der früheste bekannte) mal
der zu dem Zeitpunkt geltenden automatischen Reduktionsstufe (Regel 6). Eine
stornierte Buchung zählt nicht mit.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from conftest import ANNA, CHEF, ZENTRALE
from sqlalchemy import select
from testbelege import importieren, kopf, rechnung_pdf

from app.core.models import Variante
from app.services.ausbuchung import buche_bewegung


def _zeile(art, nr, fedas, ean, bezeichnung, menge, uvp):
    return ["Nike", fedas, art, nr, ean, bezeichnung, menge, "Stk", uvp, "20.00"]


POLO_EAN = "4006632041234"
SCHUH_EAN = "4006632041258"


def test_statistik_je_zeitraum_und_kategorie(welt):
    client, codes = welt.client, welt.codes
    heute = date.today()
    welt.anmelden(CHEF)

    # Heutiger Wareneingang: Poloshirt (Textil × Tennis) und Laufschuh
    # (Schuhe × Tennis) in SF1 - keine Reduktion fällig, die Uhr läuft ab
    # heute, darum entspricht die Schätzung genau dem UVP.
    pdf = rechnung_pdf(
        header_lines=kopf(nummer="9100000001", datum=heute.strftime("%d.%m.%Y"), belegdatum=heute.strftime("%d.%m.%Y")),
        rows=[
            _zeile("P1", "1", "224100", POLO_EAN, "Poloshirt", "10", "49.90"),
            _zeile("S1", "2", "324100", SCHUH_EAN, "Laufschuh", "10", "129.00"),
        ],
    )
    assert importieren(client, pdf, lagerort_id=str(codes["SF1"])).status_code == 200

    # 3 Poloshirts und 1 Laufschuh heute verkauft.
    for _ in range(3):
        assert client.post("/api/ausbuchen", json={"ean": POLO_EAN, "grund": "verkauf"}).status_code == 200
    assert client.post("/api/ausbuchen", json={"ean": SCHUH_EAN, "grund": "verkauf"}).status_code == 200

    # Ein vierter Verkauf wird sofort storniert - zählt nicht mit.
    storno_kandidat = client.post("/api/ausbuchen", json={"ean": POLO_EAN, "grund": "verkauf"})
    assert storno_kandidat.status_code == 200
    assert client.post(f"/api/ausbuchen/{storno_kandidat.json()['bewegung_id']}/storno").status_code == 200

    # Zusätzlicher Verkauf vor 40 Tagen (ausserhalb des Monats, innerhalb des
    # Jahres) - direkt gebucht, weil die API kein Datum entgegennimmt.
    with welt.sessions() as session, session.begin():
        polo_variante = session.scalar(select(Variante.id).where(Variante.ean == POLO_EAN))
        buche_bewegung(
            session,
            lagerort_id=codes["SF1"],
            varianten_id=polo_variante,
            typ="verkauf",
            menge=-Decimal("2"),
            grund="verkauf",
            benutzer=None,
            zeitpunkt=datetime.now(timezone.utc) - timedelta(days=40),
        )

    # Mitarbeiter sehen die Statistik nicht (Anforderung: nur Filialleiter/Zentrale).
    welt.anmelden(ANNA)
    assert client.get("/statistiken", follow_redirects=False).status_code == 303
    assert client.get("/api/statistik?zeitraum=monat").status_code == 403

    welt.anmelden(ZENTRALE)
    assert client.get("/statistiken").status_code == 200

    monat = client.get("/api/statistik?zeitraum=monat").json()
    assert monat["zeitraum"]["schluessel"] == "monat"
    kategorien = {(k["hauptgruppe"], k["sportbereich"]): k["stueck"] for k in monat["kategorien"]}
    assert kategorien[("Textil", "Tennis")] == "3.00"
    assert kategorien[("Schuhe", "Tennis")] == "1.00"
    assert monat["einnahmen_geschaetzt"] == "278.70"
    assert monat["einnahmen_ist_schaetzung"] is True
    empfehlung = [(a["lieferanten_artikelnr"], a["verkauft"]) for a in monat["bestellempfehlung"]]
    assert empfehlung[0] == ("P1", "3.00")

    gesamt = client.get("/api/statistik?zeitraum=gesamt").json()
    kategorien_gesamt = {(k["hauptgruppe"], k["sportbereich"]): k["stueck"] for k in gesamt["kategorien"]}
    assert kategorien_gesamt[("Textil", "Tennis")] == "5.00"
    assert gesamt["einnahmen_geschaetzt"] == "378.50"

    # Alle fünf Zeiträume laufen ohne Fehler.
    for schluessel in ("tag", "woche", "monat", "jahr", "gesamt"):
        antwort = client.get(f"/api/statistik?zeitraum={schluessel}")
        assert antwort.status_code == 200, antwort.text
        assert antwort.json()["zeitraum"]["schluessel"] == schluessel

    assert client.get("/api/statistik?zeitraum=quartal").status_code == 422

    # Nur SF1 gefiltert bleibt gleich (der ganze Umsatz ist dort).
    sf1 = client.get(f"/api/statistik?zeitraum=gesamt&lagerort_id={codes['SF1']}").json()
    assert sf1["einnahmen_geschaetzt"] == "378.50"
    leer = client.get(f"/api/statistik?zeitraum=gesamt&lagerort_id={codes['SF2']}").json()
    assert leer["einnahmen_geschaetzt"] == "0.00"
    assert leer["kategorien"] == []

    client.post("/logout")
    assert client.get("/api/statistik?zeitraum=monat").status_code == 401
