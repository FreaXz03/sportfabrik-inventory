"""Buchungsrechte vom 24.09.2026 über echte Anmeldung und HTTP prüfen."""
import pytest
from sqlalchemy import select, func, delete
from conftest import ANNA, BEAT, CHEF, ZENTRALE
from app.core.models import Variante, Lagerbewegung, BenutzerLagerort, User

POSITION = {"marke": "Test", "bezeichnung": "Rechte", "menge": "3", "uvp": "20"}

@pytest.mark.parametrize("konto,eigene", [(ANNA, "SF1"), (BEAT, "SF2")])
def test_mitarbeiter_nur_eigene_filiale_ohne_abgang_storno_umlagerung(welt, konto, eigene):
    c, codes = welt.client, welt.codes
    welt.anmelden(CHEF)
    assert c.post('/api/erfassen', json={"positionen": [POSITION]}).status_code == 200
    with welt.sessions() as s:
        variante = s.scalar(select(Variante.id))
    verkauf = c.post('/api/ausbuchen', json={"varianten_id": variante, "grund": "verkauf"}).json()
    welt.anmelden(konto)
    assert [lo['code'] for lo in c.get('/api/erfassen/stammdaten').json()['lagerorte']] == [eigene]
    for pfad in ('/ausbuchen', '/umlagern'):
        assert c.get(pfad, follow_redirects=False).status_code == 303
    with welt.sessions() as s:
        vorher = s.scalar(select(func.count()).select_from(Lagerbewegung))
    for code, ort in codes.items():
        assert c.post('/api/ausbuchen', json={"varianten_id": variante, "grund": "verkauf", "lagerort_id": ort}).status_code == 403
        assert c.post('/api/ausbuchen', json={"varianten_id": variante, "grund": "defekt", "lagerort_id": ort}).status_code == 403
        assert c.post('/api/umlagerung', json={"quelle_id": codes['GEWA'], "ziel_id": ort, "positionen": [{"varianten_id": variante, "menge": "1"}]}).status_code == 403
        if code != eigene:
            assert c.post('/api/erfassen', json={"positionen": [POSITION], "lagerort_id": ort}).status_code == 403
            assert c.post('/api/korrektur', json={"varianten_id": variante, "lagerort_id": ort, "gezaehlt": "9", "grund": "inventur"}).status_code == 403
    assert c.post(f"/api/ausbuchen/{verkauf['bewegung_id']}/storno").status_code == 403
    with welt.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Lagerbewegung)) == vorher
    for ziel in ({}, {"lagerort_id": codes[eigene]}):
        assert c.post('/api/erfassen', json={"positionen": [POSITION], **ziel}).status_code == 200
        assert c.post('/api/korrektur', json={"varianten_id": variante, "gezaehlt": "7", "grund": "inventur", **ziel}).status_code == 200
    assert c.get('/api/bestand?alle=true').status_code == 200
    assert c.get('/api/ausbuchungen?alle=true').status_code == 200
    # Auch ohne Zuordnung darf kein fremdes Ziel gebucht werden.
    with welt.sessions.begin() as s:
        uid = s.scalar(select(User.id).where(User.kassennummer == konto))
        s.execute(delete(BenutzerLagerort).where(BenutzerLagerort.user_id == uid))
    assert c.post('/api/erfassen', json={"positionen": [POSITION]}).status_code == 400
    assert c.post('/api/erfassen', json={"positionen": [POSITION], "lagerort_id": codes[eigene]}).status_code == 403

@pytest.mark.parametrize('konto', [CHEF, ZENTRALE])
def test_leitung_bucht_weiter_filialuebergreifend(welt, konto):
    c, codes = welt.client, welt.codes
    welt.anmelden(konto)
    assert len(c.get('/api/erfassen/stammdaten').json()['lagerorte']) == len(codes)
    assert c.post('/api/erfassen', json={"positionen": [POSITION], "lagerort_id": codes['SF3']}).status_code == 200
    with welt.sessions() as s:
        variante = s.scalar(select(Variante.id))
    verkauf = c.post('/api/ausbuchen', json={"varianten_id": variante, "grund": "verkauf", "lagerort_id": codes['SF3']})
    assert verkauf.status_code == 200
    assert c.post(f"/api/ausbuchen/{verkauf.json()['bewegung_id']}/storno").status_code == 200
    assert c.post('/api/korrektur', json={"varianten_id": variante, "lagerort_id": codes['SF3'], "gezaehlt": "9", "grund": "inventur"}).status_code == 200
    assert c.post('/api/umlagerung', json={"quelle_id": codes['SF3'], "ziel_id": codes['GEWA'], "positionen": [{"varianten_id": variante, "menge": "1"}]}).status_code == 200
