"""Receipt EAN boundary: persist master/expectation, then receive selected rows."""
from decimal import Decimal

from conftest import ANNA, CHEF
from sqlalchemy import select
from testbelege import POSITIONEN, importieren, rechnung_pdf

from app.core.models import Bestand, Lagerbewegung, Variante, Wareneingang, WareneingangPosition


def _manual(welt):
    welt.anmelden(ANNA)
    response = welt.client.post('/api/erfassen', json={'positionen': [
        {'marke': 'Test', 'bezeichnung': 'Known', 'lieferanten_artikelnr': 'A', 'groesse': 'M', 'ean': '4006632041234', 'menge': '2', 'uvp': '10'},
        {'marke': 'Test', 'bezeichnung': 'Missing', 'lieferanten_artikelnr': 'B', 'groesse': 'L', 'menge': '3', 'uvp': '20'},
    ]})
    assert response.status_code == 200, response.text
    return response.json()


def test_manual_mixed_persists_then_partial_correction_and_retry(welt):
    result = _manual(welt)
    assert result['receipt_blocked'] is True
    with welt.sessions() as session:
        receipt = session.get(Wareneingang, result['wareneingang_id'])
        assert receipt.status == 'erwartet' and receipt.eingangsdatum is None
        assert not session.scalars(select(Lagerbewegung)).all()
        assert not session.scalars(select(Bestand)).all()
        positions = session.scalars(select(WareneingangPosition).order_by(WareneingangPosition.id)).all()
        valid, missing = positions
        ids = valid.id, missing.id, missing.varianten_id
    url = f"/api/wareneingaenge/{result['wareneingang_id']}/ankunft"
    blocked = welt.client.post(url, json={'mengen': {str(ids[0]): '2', str(ids[1]): '1'}})
    assert blocked.status_code == 409
    with welt.sessions() as session:
        assert not session.scalars(select(Lagerbewegung)).all()
        assert all(p.menge_eingetroffen == 0 for p in session.scalars(select(WareneingangPosition)))
    # A future row without EAN must not block a selected valid partial receipt.
    assert welt.client.post(url, json={'mengen': {str(ids[0]): '2'}}).status_code == 200
    generated = welt.client.post(f'/api/varianten/{ids[2]}/ean', json={'generieren': True})
    assert generated.status_code == 200
    assert welt.client.post(f'/api/varianten/{ids[2]}/eans', json={'ean': '5901234123457'}).status_code == 200
    assert welt.client.post(url, json={'mengen': {str(ids[1]): '3'}}).status_code == 200
    assert welt.client.post(url, json={'mengen': {str(ids[1]): '3'}}).status_code == 409
    with welt.sessions() as session:
        assert sum(session.scalars(select(Bestand.menge))) == Decimal('5')


def test_import_mixed_persists_without_any_stock_and_duplicate_stays_blocked(welt):
    welt.anmelden(CHEF)
    rows = [row.copy() for row in POSITIONEN]
    rows[2][4] = ''
    pdf = rechnung_pdf(rows=rows)
    response = importieren(welt.client, pdf, lagerort_id=str(welt.codes['SF1']))
    assert response.status_code == 200, response.text
    assert response.json()['receipt_blocked'] is True
    with welt.sessions() as session:
        assert len(session.scalars(select(Variante)).all()) == 3
        assert not session.scalars(select(Lagerbewegung)).all()
        assert not session.scalars(select(Bestand)).all()
        assert session.scalar(select(Wareneingang)).status == 'erwartet'
    assert importieren(welt.client, pdf, lagerort_id=str(welt.codes['SF1'])).status_code == 409


def test_missing_source_ean_reuses_unique_variant_and_new_original_complements_internal(welt):
    _manual(welt)
    with welt.sessions() as session:
        missing = session.scalar(select(Variante).where(Variante.groesse == 'L'))
        vid = missing.id
    assert welt.client.post(f'/api/varianten/{vid}/ean', json={'generieren': True}).status_code == 200
    body = {'positionen': [{'marke': 'Test', 'bezeichnung': 'Missing',
            'lieferanten_artikelnr': 'B', 'groesse': 'L', 'menge': '1', 'uvp': '20'}]}
    response = welt.client.post('/api/erfassen', json=body)
    assert response.status_code == 200 and response.json()['receipt_blocked'] is False
    body['positionen'][0]['ean'] = '5901234123457'
    assert welt.client.post('/api/erfassen', json=body).status_code == 200
    for ean in ('5901234123457',):
        found = welt.client.get('/api/erfassen/variante', params={'ean': ean}).json()
        assert found['variante']['varianten_id'] == vid
    with welt.sessions() as session:
        assert len(session.scalars(select(Variante)).all()) == 2
        assert session.get(Bestand, (vid, welt.codes['SF1'])).menge == 2


def test_blocked_manual_retry_does_not_duplicate_pending_receipt(welt):
    from test_operationen import _op
    welt.anmelden(ANNA)
    body = {'positionen': [{'marke': 'Test', 'bezeichnung': 'Missing', 'menge': '1', 'uvp': '10'}]}
    first = welt.client.post('/api/erfassen', json=body, headers=_op(600))
    retry = welt.client.post('/api/erfassen', json=body, headers=_op(600))
    assert first.status_code == retry.status_code == 200
    assert retry.json()['wiederholt'] is True
    assert first.json()['wareneingang_id'] == retry.json()['wareneingang_id']
    with welt.sessions() as session:
        assert len(session.scalars(select(Wareneingang)).all()) == 1
        assert not session.scalars(select(Lagerbewegung)).all()


def test_ambiguous_missing_identifier_rejected_without_new_stock(welt):
    from app.core.models import Artikel
    _manual(welt)
    with welt.sessions.begin() as session:
        article = session.scalar(select(Artikel).where(Artikel.lieferanten_artikelnr == 'B'))
        session.add(Variante(artikel_id=article.id, groesse='L', ean='5901234123457'))
    response = welt.client.post('/api/erfassen', json={'positionen': [
        {'marke': 'Test', 'bezeichnung': 'Missing', 'lieferanten_artikelnr': 'B', 'groesse': 'L', 'menge': '1', 'uvp': '20'}]})
    assert response.status_code == 409
    with welt.sessions() as session:
        assert not session.scalars(select(Lagerbewegung)).all()


def test_invalid_stored_identifier_blocks_arrival_without_status_or_date_changes(welt):
    result = _manual(welt)
    with welt.sessions.begin() as session:
        variante = session.scalar(select(Variante).where(Variante.groesse == 'L'))
        variante.ean = 'invalid'
        positions = session.scalars(select(WareneingangPosition)).all()
        quantities = {str(p.id): '1' for p in positions}
    response = welt.client.post(f"/api/wareneingaenge/{result['wareneingang_id']}/ankunft",
                               json={'mengen': quantities, 'eingangsdatum': '2026-10-20'})
    assert response.status_code == 409
    assert 'Missing' in response.json()['detail'] and 'L' in response.json()['detail']
    with welt.sessions() as session:
        receipt = session.get(Wareneingang, result['wareneingang_id'])
        assert receipt.status == 'erwartet' and receipt.eingangsdatum is None
        assert not session.scalars(select(Lagerbewegung)).all()


def test_expected_order_without_ean_stays_available_and_zero_row_does_not_block(welt, monkeypatch):
    from app.services import importer
    original = importer.parse_with_parser
    def order(*args, **kwargs):
        parsed = original(*args, **kwargs)
        parsed['document_type'] = 'auftragsbestaetigung'
        parsed['items'][2]['ean'] = ''
        return parsed
    monkeypatch.setattr(importer, 'parse_with_parser', order)
    welt.anmelden(CHEF)
    assert importieren(welt.client, rechnung_pdf()).status_code == 200
    pending = welt.client.get('/api/wareneingaenge').json()['wareneingaenge'][0]
    quantities = {str(p['id']): ('0' if p['ean_fehlt'] else '1') for p in pending['positionen']}
    assert welt.client.post(f"/api/wareneingaenge/{pending['id']}/ankunft", json={'mengen': quantities}).status_code == 200
    with welt.sessions() as session:
        assert sum(session.scalars(select(Bestand.menge))) == 2
        assert session.get(Wareneingang, pending['id']).status == 'erwartet'


def test_deferred_manual_markdown_and_dates_apply_only_on_actual_receipt(welt):
    from app.core.models import ReduktionManuell
    from datetime import date
    from app.services.ean import setze_ean
    welt.anmelden(ANNA)
    result = welt.client.post('/api/erfassen', json={'eingangsdatum': '2026-10-20', 'positionen': [
        {'marke': 'Test', 'bezeichnung': 'Deferred', 'menge': '2', 'uvp': '20', 'reduktion': 50}
    ]}).json()
    with welt.sessions() as session:
        variant = session.scalar(select(Variante))
        vid, aid = variant.id, variant.artikel_id
        assert variant.first_seen is None and variant.last_seen is None
        assert session.scalar(select(ReduktionManuell)) is None
    setze_ean(vid, welt.sessions, generieren=True)
    pending = welt.client.get('/api/wareneingaenge').json()['wareneingaenge'][0]
    position = pending['positionen'][0]['id']
    headers = {'X-Operation-Id': 'op-0601-aaaa-bbbb-cccc-dddddddddddd'}
    url = f"/api/wareneingaenge/{result['wareneingang_id']}/ankunft"
    body = {'mengen': {str(position): '2'}, 'eingangsdatum': '2026-10-21'}
    assert welt.client.post(url, json=body, headers=headers).status_code == 200
    retry = welt.client.post(url, json=body, headers=headers)
    assert retry.status_code == 200 and retry.json()['wiederholt'] is True
    with welt.sessions() as session:
        assert session.scalar(select(ReduktionManuell.prozent)) == 50
        assert session.get(Variante, vid).first_seen == date(2026, 10, 21)
        assert session.get(Bestand, (vid, welt.codes['SF1'])).menge == 2


def test_blocked_receipt_preserves_existing_stock_and_delivery_dates(welt):
    welt.anmelden(ANNA)
    known = {'marke': 'Test', 'bezeichnung': 'Known', 'ean': '4006632041234',
             'menge': '4', 'uvp': '10'}
    assert welt.client.post('/api/erfassen', json={'positionen': [known],
                            'eingangsdatum': '2026-10-01'}).status_code == 200
    with welt.sessions() as session:
        original = session.scalar(select(Variante))
        vid, first, last = original.id, original.first_seen, original.last_seen
    blocked = welt.client.post('/api/erfassen', json={'positionen': [known,
        {'marke': 'Test', 'bezeichnung': 'Missing', 'menge': '1', 'uvp': '10'}]})
    assert blocked.status_code == 200 and blocked.json()['receipt_blocked'] is True
    with welt.sessions() as session:
        assert session.get(Bestand, (vid, welt.codes['SF1'])).menge == 4
        assert len(session.scalars(select(Lagerbewegung)).all()) == 1
        variant = session.get(Variante, vid)
        assert (variant.first_seen, variant.last_seen) == (first, last)


def test_original_ean_does_not_attach_to_ambiguous_internal_identity(welt):
    from app.services.ean import setze_ean
    _manual(welt)
    with welt.sessions() as session:
        variant = session.scalar(select(Variante).where(Variante.groesse == 'L'))
        vid, aid = variant.id, variant.artikel_id
    setze_ean(vid, welt.sessions, generieren=True)
    with welt.sessions.begin() as session:
        session.add(Variante(artikel_id=aid, groesse='L', ean='4006632041258'))
    response = welt.client.post('/api/erfassen', json={'positionen': [
        {'marke': 'Test', 'bezeichnung': 'Missing', 'lieferanten_artikelnr': 'B',
         'groesse': 'L', 'ean': '5901234123457', 'menge': '1', 'uvp': '20'}]})
    assert response.status_code == 409
    with welt.sessions() as session:
        assert not session.scalars(select(Lagerbewegung)).all()


def test_later_document_original_ean_complements_internal_variant(welt):
    from testbelege import kopf
    from app.services.ean import setze_ean
    from app.services.artikel import finde_variante_per_ean
    welt.anmelden(CHEF)
    row = POSITIONEN[2].copy()
    row[4] = ''
    first = importieren(welt.client, rechnung_pdf(rows=[row]))
    assert first.status_code == 200 and first.json()['receipt_blocked'] is True
    with welt.sessions() as session:
        vid = session.scalar(select(Variante.id))
    generated = setze_ean(vid, welt.sessions, generieren=True)
    row[4] = '5901234123457'
    second = importieren(welt.client, rechnung_pdf(rows=[row], header_lines=kopf(nummer='9000000099')), lieferung='neu')
    assert second.status_code == 200 and second.json()['receipt_blocked'] is False
    with welt.sessions() as session:
        assert len(session.scalars(select(Variante)).all()) == 1
        assert finde_variante_per_ean(session, row[4]).id == vid
        assert finde_variante_per_ean(session, generated['ean']).id == vid
        assert session.get(Bestand, (vid, welt.codes['SF1'])).menge == 2


def test_bulk_receipt_eans_scoped_idempotent_and_no_stock(welt):
    from conftest import BEAT
    from app.services.ean import pruefziffer_stimmt
    result = _manual(welt)
    rid = result['wareneingang_id']
    with welt.sessions() as session:
        positions = session.scalars(select(WareneingangPosition).order_by(WareneingangPosition.id)).all()
        known, missing = positions
        ids = known.id, missing.id, missing.varianten_id
    url = f'/api/wareneingaenge/{rid}/eans/generieren'
    body = {'mengen': {str(ids[0]): '2', str(ids[1]): '0'}}
    assert welt.client.post(url, json=body).json()['generated'] == 0
    welt.anmelden(BEAT)
    body['mengen'][str(ids[1])] = '1'
    assert welt.client.post(url, json=body).status_code == 403
    welt.anmelden(ANNA)
    assert welt.client.post(url, json={'mengen': {'999999': '1'}}).status_code == 409
    assert welt.client.post(url, json=body).json()['generated'] == 1
    assert welt.client.post(url, json=body).json()['generated'] == 0
    with welt.sessions() as session:
        variant = session.get(Variante, ids[2])
        assert variant.ean_intern and pruefziffer_stimmt(variant.ean)
        assert not session.scalars(select(Lagerbewegung)).all()
        assert not session.scalars(select(Bestand)).all()
        assert session.get(Wareneingang, rid).eingangsdatum is None
        assert all(p.menge_eingetroffen == 0 for p in session.scalars(select(WareneingangPosition)))
    assert welt.client.post(f'/api/wareneingaenge/{rid}/ankunft', json=body).status_code == 200


def test_bulk_receipt_eans_collision_rolls_back(welt):
    from app.services.ean import interne_ean
    result = _manual(welt)
    with welt.sessions.begin() as session:
        variants = session.scalars(select(Variante).order_by(Variante.id)).all()
        known, missing = variants
        known.ean = None
        session.add(Variante(artikel_id=known.artikel_id, groesse="Outside receipt", ean=interne_ean(missing.id)))
        known_id, missing_id = known.id, missing.id
        positions = session.scalars(select(WareneingangPosition)).all()
        body = {'mengen': {str(p.id): '1' for p in positions}}
    response = welt.client.post(f"/api/wareneingaenge/{result['wareneingang_id']}/eans/generieren", json=body)
    assert response.status_code == 409
    with welt.sessions() as session:
        assert session.get(Variante, missing_id).ean is None
        assert session.get(Variante, known_id).ean is None
