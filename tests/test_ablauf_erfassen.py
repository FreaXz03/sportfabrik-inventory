"""Ablauf „Ware ohne Beleg": von Hand erfassen → EAN nachtragen oder intern
erzeugen → Etikett → Kategorie von Hand → Artikel suchen → Fehleintrag löschen.

Deckt D10, D23–D25, D27, Regel 4, 5, 7, 9, B8 und die Artikellöschung vom
24.09.2026 über die echte App mit Anmeldung ab.
"""

from datetime import date
from decimal import Decimal

from conftest import ANNA, CHEF, ZENTRALE
from sqlalchemy import select
from testbelege import importieren, rechnung_pdf

from app.core.i18n import translate
from app.core.models import Bestand, Lagerbewegung, Variante, Wareneingang


def _position(**felder):
    return {"marke": "Nike", "bezeichnung": "Poloshirt Court", "menge": "3", "uvp": "39.90", **felder}


def _variante_id(client, ean):
    antwort = client.get(f"/api/erfassen/variante?ean={ean}").json()
    assert antwort["gefunden"], ean
    return antwort["variante"]["varianten_id"]


def test_erfassen_ean_etikett_kategorie(welt):
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    welt.anmelden(ANNA)

    # Stammdaten: alle Lagerorte buchbar (D26), je Lieferantengruppe ein Eintrag.
    stamm = client.get("/api/erfassen/stammdaten").json()
    assert stamm["lagerort_aktiv"] == codes["SF1"]
    assert {e["code"] for e in stamm["lieferanten"]} == {"111", "555", "333", "999", "444"}

    # Pflicht sind nur Marke, Bezeichnung, Menge, UVP (D23). Eine falsche
    # Position bucht nichts, auch nicht die richtigen daneben.
    for feld in ("marke", "bezeichnung", "menge", "uvp"):
        antwort = client.post("/api/erfassen", json={"positionen": [_position(**{feld: ""})]})
        assert antwort.status_code == 409, feld
    abgelehnt = client.post(
        "/api/erfassen",
        json={"positionen": [_position(), _position(ean="1234")]},  # keine EAN
    )
    assert abgelehnt.status_code == 409
    assert client.post("/api/erfassen", json={"positionen": [_position(preis="1")]}).status_code == 422

    # Mitarbeiterin erfasst (Regel 9/D21): eine Position mit EAN, eine ohne,
    # Komma als Dezimaltrennzeichen. Kein Beleg (D27), sofort Bestand.
    antwort = client.post(
        "/api/erfassen",
        json={
            "positionen": [
                _position(ean="4006632041234", groesse="M", farbe="Weiss"),
                _position(marke="CMP", bezeichnung="Regenjacke", menge="1", uvp="89,90", groesse="152"),
            ],
            "lagerort_id": codes["SF1"],
        },
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["positionen"] == 2
    assert antwort.json()["eingangsdatum"] == date.today().isoformat()
    with sessions() as session:
        assert session.scalar(select(Wareneingang.dokument_id)) is None
        bewegungen = session.scalars(select(Lagerbewegung)).all()
        assert {b.benutzer_name for b in bewegungen} == {"Anna"}
        assert sorted(b.menge for b in bewegungen) == [Decimal("1"), Decimal("3")]

    # Zweite Erfassung derselben EAN: gleiche Variante, Bestand wächst.
    polo = _variante_id(client, "4006632041234")
    client.post("/api/erfassen", json={"positionen": [_position(ean="4006632041234", menge="2")]})
    with sessions() as session:
        assert session.get(Bestand, (polo, codes["SF1"])).menge == Decimal("5")
        jacke = session.scalar(select(Variante.id).where(Variante.groesse == "152"))

    # Ohne Verkauf (GEWA) kein Eingangsdatum, rückwirkendes Datum erlaubt,
    # Datum in der Zukunft nicht (Regel 6).
    gewa = client.post(
        "/api/erfassen", json={"positionen": [_position()], "lagerort_id": codes["GEWA"]}
    )
    assert gewa.status_code == 200 and gewa.json()["eingangsdatum"] is None
    assert client.post(
        "/api/erfassen", json={"positionen": [_position()], "eingangsdatum": "2099-01-01"}
    ).status_code == 409

    # EAN nachtragen: Prüfziffer muss stimmen, sonst intern erzeugen (D10/D24).
    assert client.post(f"/api/varianten/{jacke}/ean", json={"ean": "5901234123458"}).status_code == 409
    intern = client.post(f"/api/varianten/{jacke}/ean", json={"generieren": True})
    assert intern.status_code == 200, intern.text
    assert intern.json()["ean_intern"] is True and intern.json()["ean"].startswith("2")
    assert client.post(f"/api/varianten/{jacke}/ean", json={"generieren": True}).status_code == 409

    # Etikett (D25): Jahrgang, Lieferantencode, UVP, Stufe, Strichcode.
    etikett = client.get(f"/api/varianten/{jacke}/etikett").json()
    assert etikett["uvp"] == "89.90"
    assert etikett["jahrgang"] == date.today().year
    assert etikett["barcode"] is True
    assert etikett["ean"] == intern.json()["ean"]
    pdf = client.get(f"/api/varianten/{jacke}/etikett.pdf?reduktion=30&anzahl=2")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/varianten/{jacke}/etikett.pdf?reduktion=40").status_code == 422
    # Regel 7: Fehlermeldungen in der Sprache des Kontos.
    client.post("/api/language", json={"language": "fr"})
    fehlt = client.get("/api/varianten/999999/etikett")
    assert fehlt.status_code == 404
    assert fehlt.json()["detail"] == translate("errors.etikett.variante_not_found", "fr", id=999999)
    client.post("/api/language", json={"language": "de"})

    # Kategorie von Hand (B8): erst ohne, dann gewählt, Filter „ohne Kategorie".
    ohne = client.get("/api/articles?kategorie_fehlt=true").json()
    assert ohne["total"] == 3
    kategorien = client.get("/api/kategorien").json()["items"]
    schuhe_winter = next(
        k["id"] for k in kategorien if (k["hauptgruppe"], k["sportbereich"]) == ("Schuhe", "Winter")
    )
    gesetzt = client.put(f"/api/articles/{jacke}/kategorie", json={"kategorie_id": schuhe_winter})
    assert gesetzt.status_code == 200, gesetzt.text
    stand = client.get(f"/api/articles/{jacke}/kategorie").json()
    assert stand["kategorie"]["id"] == schuhe_winter and stand["manuell"] is True
    assert client.get("/api/articles?kategorie_fehlt=true").json()["total"] == 2

    # Suche nach EAN und Marke.
    assert client.get("/api/articles?ean=4006632041234").json()["total"] == 1
    assert client.get("/api/articles?brand=CMP").json()["total"] == 1

    # Ohne Anmeldung nichts.
    client.post("/logout")
    assert client.post("/api/erfassen", json={"positionen": [_position()]}).status_code == 401
    seite = client.get("/erfassen", follow_redirects=False)
    assert seite.status_code == 303 and seite.headers["location"] == "/login?next=/erfassen"


def test_nur_von_hand_erfasste_artikel_sind_loeschbar(welt):
    """Entscheid 24.09.2026: Filialleiter/Zentrale dürfen einen von Hand
    erfassten Artikel ohne Beleg ganz löschen; Artikel aus Belegen bleiben."""
    client, sessions = welt.client, welt.sessions
    welt.anmelden(CHEF)
    assert importieren(client, rechnung_pdf()).status_code == 200
    beleg = _variante_id(client, "4006632041234")
    client.post("/api/erfassen", json={"positionen": [_position(bezeichnung="Falsch getippt", ean="5901234123457")]})
    manuell = _variante_id(client, "5901234123457")

    welt.anmelden(ANNA)
    assert client.get("/api/articles?nur_manuell=true").json()["total"] == 1
    assert client.delete(f"/api/articles/{manuell}").status_code == 403

    welt.anmelden(ZENTRALE)
    assert client.get(f"/api/articles/{manuell}/history").json()["product"]["manuell"] is True
    assert client.delete(f"/api/articles/{beleg}").status_code == 409
    welt.anmelden(CHEF)
    assert client.delete(f"/api/articles/{manuell}").status_code == 200
    with sessions() as session:
        assert session.get(Variante, manuell) is None
        assert session.get(Variante, beleg) is not None
