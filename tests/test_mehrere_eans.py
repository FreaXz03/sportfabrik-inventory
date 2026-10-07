"""Punkt 8 (2026-10-01): einer Variante lässt sich später eine zweite EAN
nachtragen (z. B. die Original-EAN neben der internen). Beide führen zur selben
Variante; eine bleibt die Etiketten-EAN, die interne bleibt als intern markiert
(Regel 5)."""

from conftest import ANNA
from sqlalchemy import select

from app.core.models import Bestand, Variante, VarianteEan

ORIGINAL = "5901234123457"  # gültige Prüfziffer
ANDERE = "4006632041234"


def _position(**felder):
    return {"marke": "Nike", "bezeichnung": "Poloshirt Court", "menge": "3", "uvp": "39.90", **felder}


def test_zweite_ean_fuehrt_zur_selben_variante(welt):
    client, sessions, codes = welt.client, welt.sessions, welt.codes
    welt.anmelden(ANNA)
    client.post("/api/erfassen", json={"positionen": [_position(groesse="M"), _position(groesse="L", ean=ANDERE)]})
    with sessions() as session:
        polo = session.scalar(select(Variante.id).where(Variante.groesse == "M"))
        anderes = session.scalar(select(Variante.id).where(Variante.ean == ANDERE))
    intern = client.post(f"/api/varianten/{polo}/ean", json={"generieren": True}).json()

    # Nachtragen: die Original-EAN kommt zur internen dazu, ersetzt sie nicht.
    antwort = client.post(f"/api/varianten/{polo}/eans", json={"ean": ORIGINAL})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["ean"] == ORIGINAL and antwort.json()["ean_intern"] is False
    etikett = client.get(f"/api/varianten/{polo}/etikett").json()
    assert etikett["ean"] == intern["ean"]  # Etiketten-EAN bleibt die erste
    assert [e["ean"] for e in etikett["weitere_eans"]] == [ORIGINAL]

    # Scan, Erfassung und Suche finden die Variante über jede der beiden.
    assert client.get(f"/api/erfassen/variante?ean={ORIGINAL}").json()["variante"]["varianten_id"] == polo
    assert client.get(f"/api/erfassen/variante?ean={intern['ean']}").json()["variante"]["varianten_id"] == polo
    assert client.post("/api/ausbuchen", json={"ean": ORIGINAL, "grund": "verkauf"}).status_code == 200
    with sessions() as session:
        assert session.get(Bestand, (polo, codes["SF1"])).menge == 2
    assert client.get(f"/api/articles?ean={ORIGINAL}").json()["items"] != []
    assert client.get(f"/api/articles?q={ORIGINAL[:9]}").json()["items"] != []

    # Abgelehnt: gleiche EAN nochmals, EAN einer anderen Variante, falsche Prüfziffer,
    # und die Original-EAN gehört danach nicht mehr als Hauptnummer einer anderen Variante.
    assert client.post(f"/api/varianten/{polo}/eans", json={"ean": ORIGINAL}).status_code == 409
    assert client.post(f"/api/varianten/{polo}/eans", json={"ean": intern["ean"]}).status_code == 409
    assert client.post(f"/api/varianten/{polo}/eans", json={"ean": ANDERE}).status_code == 409
    assert client.post(f"/api/varianten/{anderes}/eans", json={"ean": ORIGINAL}).status_code == 409
    assert client.post(f"/api/varianten/{polo}/eans", json={"ean": "5901234123458"}).status_code == 409
    assert client.post(f"/api/varianten/999999/eans", json={"ean": "4006632041258"}).status_code == 404
    with sessions() as session:
        assert session.scalars(select(VarianteEan.ean)).all() == [ORIGINAL]


def test_variante_ohne_hauptean_bekommt_die_nachgetragene_als_hauptnummer(welt):
    client, sessions = welt.client, welt.sessions
    welt.anmelden(ANNA)
    client.post("/api/erfassen", json={"positionen": [_position(groesse="XL")]})
    with sessions() as session:
        variante = session.scalar(select(Variante.id).where(Variante.groesse == "XL"))
    assert client.post(f"/api/varianten/{variante}/eans", json={"ean": ORIGINAL}).status_code == 200
    with sessions() as session:
        assert session.get(Variante, variante).ean == ORIGINAL
        assert session.scalars(select(VarianteEan)).all() == []
