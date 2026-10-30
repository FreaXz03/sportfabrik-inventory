"""Synthetic winter size matrices and atomic order revisions; no private fixtures."""
import hashlib
from decimal import Decimal

import pymupdf
import pytest
from sqlalchemy import select, func
from conftest import CHEF, ANNA
from test_bestellplan import plan
from app.core.models import Artikel, Variante, Wareneingang, WareneingangPosition, Lagerbewegung
from app.services.importer import import_invoice, ImportRejected
from app.services.parsers import parse_document


def size_pdf(branch='SF1', quantities=(8, 12), name='Head Edge 7 W HV R102mm'):
    with pymupdf.open() as doc:
        left = doc.new_page(width=1190.5, height=841.9)
        for x,y,text in [(20,60,f'Bestellung Winter HW {branch}'),(944,76,branch),(985,76,'Total'),
                         (1040,76,'EP Total'),(80,96,'Skischuhe Lady'),(232,96,'VP'),(274,96,'EP'),
                         (320,96,'23/23.5'),(362,96,'24'),(40,120,name),(232,120,'335'),(274,120,'103'),
                         (320,120,str(quantities[0])),(362,120,str(quantities[1])),(945,120,str(sum(quantities))),
                         (985,120,str(sum(quantities))),(1040,120,str(sum(quantities)*103)),
                         (80,145,'Total pro Grösse'),(320,145,str(quantities[0])),(362,145,str(quantities[1])),
                         (945,145,str(sum(quantities))),(985,145,str(sum(quantities)))]:
            left.insert_text((x,y),text,fontsize=8)
        right=doc.new_page(width=1190.5,height=841.9)
        for x,y,text in [(49,76,'VP Total'),(150,76,'VP-30%'),(218,76,'Liefertermin'),(286,76,'Art. Nr.'),
                         (49,120,str(sum(quantities)*335)),(150,120,str(sum(quantities)*Decimal('234.5'))),
                         (223,120,'15.09.2025'),(287,120,'TEST-123')]:
            right.insert_text((x,y),text,fontsize=8)
        return doc.tobytes()


def setup_order(welt):
    welt.anmelden(CHEF)
    pdf=plan()
    import_invoice(pdf,'synthetic.pdf',hashlib.sha256(pdf).hexdigest(),welt.sessions,welt.codes['SF1'])
    with welt.sessions() as s:
        return s.scalar(select(Wareneingang.id).where(Wareneingang.lagerort_id==welt.codes['SF1']))


def preview(welt,rid,pdf,**values):
    return welt.client.post(f'/api/winter-abgleich/{rid}/vorschau',files={'file':('synthetic.pdf',pdf,'application/pdf')},data=values)


def apply(welt,rid,pdf,view,**values):
    import json
    group=view['groups'][0]
    return welt.client.post(f'/api/winter-abgleich/{rid}/uebernehmen',files={'file':('synthetic.pdf',pdf,'application/pdf')},data={
        'confirmed':'true','fingerprint':view['fingerprint'],'selection':json.dumps({group['key']:group['target_id']}),**values})


def test_size_parser_preserves_combined_sizes_and_original_identity():
    result=parse_document(size_pdf())
    assert result['winter_sizes'] is True and result['branch_code']=='SF1'
    assert [(i['size'],i['quantity']) for i in result['items']]==[('23/23.5','8'),('24','12')]
    assert result['items'][0]['supplier_article_no']=='Head Edge 7 W HV R102mm'
    assert result['groups'][0]['printed_article_no']=='TEST-123'
    assert not result['warnings']


def test_reconciliation_reuses_article_keeps_history_and_other_branches(welt):
    rid=setup_order(welt); pdf=size_pdf()
    response=preview(welt,rid,pdf); assert response.status_code==200,response.text
    view=response.json(); assert view['groups'][0]['target_id']
    with welt.sessions() as s:
        before=s.scalar(select(func.count()).select_from(Artikel))
        old=s.scalar(select(WareneingangPosition).where(WareneingangPosition.wareneingang_id==rid))
        old_id=old.id
    result=apply(welt,rid,pdf,view); assert result.status_code==200,result.text
    assert apply(welt,rid,pdf,view).json()['repeated'] is True
    with welt.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Artikel))==before
        assert not s.scalars(select(Lagerbewegung)).all()
        assert s.get(WareneingangPosition,old_id).ersetzt_durch_abgleich_id
        positions=s.scalars(select(WareneingangPosition).where(WareneingangPosition.wareneingang_id==rid,WareneingangPosition.ersetzt_durch_abgleich_id.is_(None))).all()
        assert sum(p.menge for p in positions)==20
        assert {s.get(Variante,p.varianten_id).groesse for p in positions}=={'23/23.5','24'}
        assert all(s.get(Variante,p.varianten_id).ean is None for p in positions)
    # Superseded ONESIZE positions cannot be received using stale inputs.
    assert welt.client.post(f'/api/wareneingaenge/{rid}/ankunft',json={'mengen':{str(old_id):'1'}}).status_code==409
    with welt.sessions() as s:
        other=s.scalar(select(Wareneingang.id).where(Wareneingang.lagerort_id==welt.codes['SF2']))
        assert sum(s.scalars(select(WareneingangPosition.menge).where(WareneingangPosition.wareneingang_id==other)))==30


def test_reconciliation_rejects_wrong_branch_stale_preview_and_quantity_change(welt):
    rid=setup_order(welt)
    assert preview(welt,rid,size_pdf(branch='SF2')).status_code==409
    pdf=size_pdf(quantities=(7,12));view=preview(welt,rid,pdf).json()
    assert apply(welt,rid,pdf,view).status_code==409
    pdf=size_pdf();view=preview(welt,rid,pdf).json()
    with welt.sessions.begin() as s:
        p=s.scalar(select(WareneingangPosition).where(WareneingangPosition.wareneingang_id==rid));p.menge=21
    assert apply(welt,rid,pdf,view).status_code==409
    welt.anmelden(ANNA)
    assert preview(welt,rid,pdf).status_code==403


def test_size_matrix_cannot_be_imported_as_a_second_order(welt):
    pdf=size_pdf()
    with pytest.raises(ImportRejected):
        import_invoice(pdf,'synthetic.pdf',hashlib.sha256(pdf).hexdigest(),welt.sessions,welt.codes['SF1'])


def test_explicit_quantity_revision_requires_reason_and_keeps_audit(welt):
    from app.core.models import WinterAbgleich
    rid=setup_order(welt); pdf=size_pdf(quantities=(7,12)); view=preview(welt,rid,pdf).json()
    assert apply(welt,rid,pdf,view,revise_quantities='true',reason='short').status_code==409
    result=apply(welt,rid,pdf,view,revise_quantities='true',reason='Explicit synthetic order correction')
    assert result.status_code==200,result.text
    with welt.sessions() as s:
        audit=s.scalar(select(WinterAbgleich))
        assert audit.data['reason']=='Explicit synthetic order correction'
        assert sum(Decimal(r['quantity']) for r in audit.data['after'])==19
        assert sum(Decimal(r['expected']) for r in audit.data['before'])==20
        assert not s.scalars(select(Lagerbewegung)).all()


def test_preview_bound_to_source_and_received_orders_protected(welt):
    rid=setup_order(welt); pdf=size_pdf(); view=preview(welt,rid,pdf).json()
    altered=size_pdf(quantities=(9,11))
    assert apply(welt,rid,altered,view).status_code==409
    with welt.sessions.begin() as s:
        p=s.scalar(select(WareneingangPosition).where(WareneingangPosition.wareneingang_id==rid));p.menge_eingetroffen=1
    view=preview(welt,rid,pdf).json()
    assert view['originals'][0]['blocked']
    assert apply(welt,rid,pdf,view).status_code==409


def test_ambiguous_name_needs_explicit_mapping_and_does_not_create_new_article(welt):
    import json
    rid=setup_order(welt);pdf=size_pdf(name='Head Changed Model')
    view=preview(welt,rid,pdf).json();assert view['groups'][0]['target_id'] is None
    assert apply(welt,rid,pdf,view).status_code==409
    view['groups'][0]['target_id']=view['originals'][0]['id']
    assert apply(welt,rid,pdf,view).status_code==200
    with welt.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Artikel))==2


def test_private_winter_matrix_opt_in():
    import os
    from pathlib import Path
    path=os.environ.get('WINTER_SIZE_PDF')
    if not path:pytest.skip('Private winter matrix not supplied')
    r=parse_document(Path(path).read_bytes())
    assert r['winter_sizes'] and r['branch_code'] in {'SF1','SF2','SF3','SF4'}
    assert sum(Decimal(g['quantity']) for g in r['groups'])==sum(Decimal(i['quantity']) for i in r['items'])
    assert all(g['paired_page']>g['page'] for g in r['groups'])


def test_matrix_rounding_and_missing_partner_are_rejected():
    # Quantity cells and row totals must reconcile, with neither inferred rows nor dropped columns.
    pdf=size_pdf()
    with pymupdf.open(stream=pdf,filetype='pdf') as doc:
        doc[0].insert_text((404,120),'1',fontsize=8)
        damaged=doc.tobytes()
    from app.services.parsers import DocumentParseError
    with pytest.raises(DocumentParseError):parse_document(damaged)
    with pymupdf.open(stream=pdf,filetype='pdf') as doc:
        doc[1].delete_pages() if False else None
        doc.delete_page(1)
        damaged=doc.tobytes()
    with pytest.raises(DocumentParseError):parse_document(damaged)


def test_partial_same_file_can_apply_remaining_groups_once(welt):
    from copy import deepcopy
    from app.services.winter_reconciliation import snapshot,apply_revision,ReconciliationRejected
    rid=setup_order(welt)
    with welt.sessions() as s:
        rid=s.scalar(select(Wareneingang.id).where(Wareneingang.lagerort_id==welt.codes['SF2']))
    parsed=parse_document(size_pdf(branch='SF2',quantities=(8,10)))
    second=deepcopy(parsed['groups'][0]);second.update(key='1:2',name='Tecnica Mach 1 LV 130 TD2 98mm',quantity='12',sizes={'25':'6','26':'6'},uvp='650',ek='260')
    parsed['groups'].append(second)
    allowed={welt.codes['SF2']};digest='a'*64
    with welt.sessions() as s:view=snapshot(s,rid,parsed,allowed,'de')
    g1,g2=view['groups']; selection={g1['key']:g1['target_id']}
    result=apply_revision(welt.sessions,rid,parsed,digest,'synthetic.pdf',view['fingerprint'],selection,allowed,{},'de')
    with welt.sessions() as s:view2=snapshot(s,rid,parsed,allowed,'de')
    assert view2['groups'][0]['applied'] and not view2['groups'][1]['applied']
    selection2={g2['key']:g2['target_id']}
    assert apply_revision(welt.sessions,rid,parsed,digest,'synthetic.pdf',view2['fingerprint'],selection2,allowed,{},'de')['id']!=result['id']
    with welt.sessions() as s:
        positions=s.scalars(select(WareneingangPosition).where(WareneingangPosition.wareneingang_id==rid,WareneingangPosition.ersetzt_durch_abgleich_id.is_(None))).all()
        assert sum(p.menge for p in positions)==30
    assert apply_revision(welt.sessions,rid,parsed,digest,'synthetic.pdf',view2['fingerprint'],selection2,allowed,{},'de')['repeated']


def test_replaced_onesize_lines_are_not_counted_twice_in_totals(welt):
    rid=setup_order(welt)
    base=Decimal(welt.client.get('/api/dashboard').json()['delivered_quantity'])
    pdf=size_pdf();view=preview(welt,rid,pdf).json()
    assert apply(welt,rid,pdf,view).status_code==200
    # SF1 had 20 expected pieces before and has 20 after; the replaced line must not add a second 20.
    assert Decimal(welt.client.get('/api/dashboard').json()['delivered_quantity'])==base
