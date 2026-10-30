"""Explicit, branch-scoped, preview-bound revisions of unreceived winter orders."""
import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from ..core.models import (Artikel, Dokument, Lagerort, Lieferant, Variante, Wareneingang,
    WareneingangPosition, WareneingangPositionQuelle, WinterAbgleich, Lagerbewegung, LieferungDifferenz)
from ..core.i18n import translate
from .wareneingang import ADVISORY_LOCK_ID


class ReconciliationRejected(ValueError):
    pass


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC',value or '').casefold().split())


def reject(key, language):
    raise ReconciliationRejected(translate('winter.'+key,language))


def candidates(session, allowed):
    return [dict(id=r.id,number=d.dokumentnummer,branch=l.code) for r,d,l in session.execute(
        select(Wareneingang,Dokument,Lagerort).join(Dokument,Dokument.id==Wareneingang.dokument_id)
        .join(Lagerort,Lagerort.id==Wareneingang.lagerort_id).join(Lieferant,Lieferant.id==Dokument.lieferant_id)
        .where(Wareneingang.status=='erwartet',Dokument.status=='aktiv',Dokument.typ=='bestellung',
               Lieferant.parser_key=='bestellplan',Wareneingang.lagerort_id.in_(allowed)))]


def _numbers(value):
    return sorted(re.findall(r'\d+(?:\.\d+)?', normalized(value)))


def suggest(entries, old):
    """Propose an existing open article for each new group (never applied automatically).

    confidence: exact (same name), high (very similar, same numbers, unambiguous), medium (similar but
    uncertain: reasons say why), none (nothing similar; a new article is proposed). Articles with received
    goods are never proposed and every old article is proposed at most once."""
    taken = {e['target_id'] for e in entries if e.get('target_id')}
    pool = [o for o in old.values() if o['id'] not in taken and not o['blocked']]
    scores = {}
    for e in entries:
        if e.get('target_id'):
            continue
        ranked = sorted(((SequenceMatcher(None, normalized(e['name']), normalized(o['name'])).ratio(), o['id']) for o in pool), reverse=True)
        scores[e['key']] = [r for r in ranked if r[0] >= 0.75]
    assigned = {}
    for ratio, key, oid in sorted(((r, k, i) for k, rs in scores.items() for r, i in rs), reverse=True):
        if key not in assigned and oid not in {v[0] for v in assigned.values()}:
            assigned[key] = (oid, ratio)
    for e in entries:
        e.update(suggested_id=e.get('target_id'), confidence='exact' if e.get('target_id') else 'none',
                 similarity=1.0 if e.get('target_id') else 0.0, reasons=[], alternatives=[])
        if e.get('target_id') or e['key'] not in assigned:
            continue
        oid, ratio = assigned[e['key']]
        ranked = scores[e['key']]
        others = [i for r, i in ranked if i != oid and ratio - r < 0.04]
        reasons = []
        if _numbers(e['name']) != _numbers(old[oid]['name']):
            reasons.append('number')
        if others:
            reasons.append('ambiguous')
        e.update(suggested_id=oid, similarity=round(ratio, 2), reasons=reasons,
                 alternatives=[old[i]['name'] for i in others[:2]],
                 confidence='high' if ratio >= 0.93 and not reasons else 'medium')


def snapshot(session, receipt_id, parsed, allowed, language):
    receipt = session.get(Wareneingang,receipt_id)
    if receipt is None or receipt.lagerort_id not in allowed:
        reject('forbidden',language)
    doc=session.get(Dokument,receipt.dokument_id) if receipt.dokument_id else None
    supplier=session.get(Lieferant,doc.lieferant_id) if doc else None
    location=session.get(Lagerort,receipt.lagerort_id)
    if not doc or doc.status!='aktiv' or doc.typ!='bestellung' or not supplier or supplier.parser_key!='bestellplan' or receipt.status!='erwartet' or receipt.herkunft_lagerort_id:
        reject('not_open',language)
    if not parsed.get('winter_sizes') or location.code!=parsed['branch_code']:
        reject('wrong_branch',language)
    rows=session.execute(select(WareneingangPosition,Variante,Artikel)
        .join(Variante,Variante.id==WareneingangPosition.varianten_id).join(Artikel,Artikel.id==Variante.artikel_id)
        .where(WareneingangPosition.wareneingang_id==receipt_id,WareneingangPosition.ersetzt_durch_abgleich_id.is_(None))
        .order_by(WareneingangPosition.id)).all()
    state=[dict(id=p.id,variant_id=v.id,article_id=a.id,name=a.lieferanten_artikelnr,brand=a.marke,
                description=a.bezeichnung,color=v.farbe,size=v.groesse,ean=v.ean,expected=str(p.menge or 0),
                arrived=str(p.menge_eingetroffen or 0),unit=p.einheit,uvp=str(p.uvp),ek=str(p.ek)) for p,v,a in rows]
    ids=[p.id for p,v,a in rows]
    differences=session.execute(select(LieferungDifferenz.id,LieferungDifferenz.art,LieferungDifferenz.menge,
        LieferungDifferenz.aufgeloest_am).where(LieferungDifferenz.wareneingang_position_id.in_(ids))).all()
    movements=session.scalars(select(Lagerbewegung.id).where(Lagerbewegung.wareneingang_position_id.in_(ids))).all()
    payload=dict(receipt=receipt_id,location=receipt.lagerort_id,document=doc.id,status=receipt.status,
                 document_status=doc.status,date=str(receipt.eingangsdatum),rows=state,source=parsed["groups"],
                 differences=[list(d) for d in differences],movements=list(movements))
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    old={}
    for p,v,a in rows:
        entry=old.setdefault(a.id,dict(id=a.id,name=a.lieferanten_artikelnr or a.bezeichnung,
            quantity=Decimal(0),position_ids=[],sizes={},blocked=False))
        entry['quantity']+=p.menge or 0;entry['position_ids'].append(p.id)
        entry['sizes'][v.groesse or '']=str(Decimal(entry['sizes'].get(v.groesse or '',0))+(p.menge or 0))
        entry['blocked'] |= bool(p.menge_eingetroffen or any(d for d in differences) or movements)
    new={}
    for row in parsed['groups']:
        key=hashlib.sha256(normalized(row['name']).encode()).hexdigest()
        entry=new.setdefault(key,dict(key=key,name=row['name'],quantity=Decimal(0),sizes=defaultdict(Decimal),rows=[],warnings=[]))
        entry['quantity']+=Decimal(row['quantity']);entry['rows'].append(row)
        entry['warnings'].extend(row['warnings'])
        for size,amount in row['sizes'].items():entry['sizes'][size]+=Decimal(amount)
    for entry in new.values():
        matches=[o['id'] for o in old.values() if normalized(o['name'])==normalized(entry['name'])]
        entry['target_id']=matches[0] if len(matches)==1 else None
        entry['quantity']=str(entry['quantity']);entry['sizes']={k:str(v) for k,v in entry['sizes'].items()}
    suggest(list(new.values()),old)
    audits=list(session.scalars(select(WinterAbgleich).where(WinterAbgleich.wareneingang_id==receipt_id).order_by(WinterAbgleich.id)))
    consumed={key for a in audits if a.data["source"]==parsed["groups"] for key in a.data["selection"]}
    for entry in new.values():
        entry["applied"]=entry["key"] in consumed
    history=[dict(id=a.id,filename=a.dateiname,date=a.zeitpunkt.isoformat(),actor=a.benutzer_name,
                  before=a.data['before'],after=a.data['after'],reason=a.data.get('reason'))
             for a in audits]
    return dict(fingerprint=fingerprint,branch=location.code,number=doc.dokumentnummer,groups=list(new.values()),
                originals=[{**o,'quantity':str(o['quantity'])} for o in old.values()],before=state,history=history,
                original_total=str(sum(o['quantity'] for o in old.values())),new_total=str(sum(Decimal(n['quantity']) for n in new.values())))


def _article_for(session, supplier_id, row):
    """Reuse the shared article with the same brand/name, otherwise create it like a document import."""
    from .artikel import artikel_group_key, finde_artikel
    from .importer import _resolve_kategorie_id
    key=artikel_group_key(row.get('brand'),row['name'])
    article=finde_artikel(session,supplier_id,key)
    if article is None:
        article=Artikel(lieferant_id=supplier_id,marke=row.get('brand'),lieferanten_artikelnr=row['name'],
            bezeichnung=row.get('description'),fedas_code=None,
            kategorie_id=_resolve_kategorie_id(session,{},None,row.get('description'),None))
        session.add(article);session.flush()
    return article


def apply_revision(session_factory, receipt_id, parsed, digest, filename, fingerprint, selection,
                   allowed, actor, language='de', revise_quantities=False, reason='', withdraw=()):
    # Selection value 0 creates/reuses a new article; `withdraw` removes unlisted open articles.
    withdraw=sorted(set(withdraw))
    if not isinstance(selection,dict) or any(type(v) is not int for v in selection.values()) \
            or any(type(v) is not int for v in withdraw) or not (selection or withdraw):
        reject('selection_required',language)
    with session_factory() as session,session.begin():
        if session.bind.dialect.name=='postgresql':
            session.execute(text(f'SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})'))
        request_hash=hashlib.sha256(json.dumps([receipt_id,digest,selection,revise_quantities,reason,withdraw],sort_keys=True).encode()).hexdigest()
        receipt=session.get(Wareneingang,receipt_id)
        if receipt is None or receipt.lagerort_id not in allowed:reject('forbidden',language)
        prior=session.scalar(select(WinterAbgleich).where(WinterAbgleich.anfrage_hash==request_hash))
        if prior:
            return dict(id=prior.id,repeated=True)
        previous=session.scalars(select(WinterAbgleich).where(WinterAbgleich.datei_hash==digest)).all()
        if any(a.wareneingang_id!=receipt_id or set(a.data['selection']) & set(selection) for a in previous):
            reject('already_used',language)
        view=snapshot(session,receipt_id,parsed,allowed,language)
        if view['fingerprint']!=fingerprint:reject('stale',language)
        supplier_id=session.get(Dokument,receipt.dokument_id).lieferant_id
        new={g['key']:g for g in view['groups']};old={g['id']:g for g in view['originals']}
        targets=defaultdict(list);created_groups=[]
        for key,aid in selection.items():
            if key not in new or (aid and aid not in old):reject('selection_required',language)
            if new[key]['warnings']:reject('source_error',language)
            if not aid:
                created_groups.append(new[key]);continue
            if old[aid]['blocked']:reject('already_received',language)
            targets[aid].append(new[key])
        for aid in withdraw:
            if aid not in old or aid in targets:reject('selection_required',language)
            if old[aid]['blocked']:reject('already_received',language)
        if (created_groups or withdraw) and not (revise_quantities and len(reason.strip())>=10):
            reject('quantity_conflict',language)
        for aid,groups in targets.items():
            amount=sum(Decimal(g['quantity']) for g in groups)
            if amount!=Decimal(old[aid]['quantity']) and not (revise_quantities and len(reason.strip())>=10):
                reject('quantity_conflict',language)
        # Never change a receipt price from a size matrix; price discrepancies require review.
        before=[r for r in view['before'] if r['article_id'] in targets or r['article_id'] in withdraw]
        revised=revise_quantities and len(reason.strip())>=10
        new_prices={}
        for aid,groups in targets.items():
            if revised:
                # Explicit order revision: the new list's prices apply to the new lines (old lines stay as history).
                listed={(Decimal(r['uvp']),Decimal(r['ek'])) for g in groups for r in g['rows']}
                if len(listed)!=1:reject('price_conflict',language)
                new_prices[aid]=next(iter(listed));continue
            prices={(r['uvp'],r['ek'],r['unit']) for r in before if r['article_id']==aid}
            if len(prices)!=1:reject('price_conflict',language)
            old_vp,old_ep,_=next(iter(prices))
            if any(Decimal(row['uvp'])!=Decimal(old_vp) or (old_ep!='None' and Decimal(row['ek'])!=Decimal(old_ep)) for g in groups for row in g['rows']):
                reject('price_conflict',language)
        audit=WinterAbgleich(wareneingang_id=receipt_id,datei_hash=digest,anfrage_hash=request_hash,dateiname=(filename or 'winter.pdf')[:500],
            benutzer_kassennummer=actor.get('kassennummer'),benutzer_name=actor.get('name'),zeitpunkt=datetime.now(timezone.utc),
            data=dict(before=before,after=[],selection=selection,withdrawn=withdraw,revise_quantities=revise_quantities,reason=reason,source=parsed['groups']))
        session.add(audit);session.flush()
        created=[]
        for aid,groups in targets.items():
            quantities=defaultdict(Decimal)
            for g in groups:
                for size,q in g['sizes'].items():quantities[size]+=Decimal(q)
            original=next(r for r in before if r['article_id']==aid)
            # Existing item master and prices stay; size variants may already exist in another branch.
            color=original['color']
            if any(r['color']!=color for r in before if r['article_id']==aid):reject('selection_required',language)
            for size,quantity in quantities.items():
                if not quantity:continue
                variants=session.scalars(select(Variante).where(Variante.artikel_id==aid,Variante.groesse==size,
                    Variante.farbe==color)).all()
                if len(variants)>1:reject('selection_required',language)
                if variants:variant=variants[0]
                else:
                    variant=Variante(artikel_id=aid,groesse=size,farbe=color,ean=None,ean_intern=False)
                    session.add(variant);session.flush()
                position=WareneingangPosition(wareneingang_id=receipt_id,varianten_id=variant.id,menge=quantity,
                    menge_eingetroffen=0,einheit=original['unit'],
                    uvp=new_prices[aid][0] if aid in new_prices else Decimal(original['uvp']),
                    ek=new_prices[aid][1] if aid in new_prices else (None if original['ek']=='None' else Decimal(original['ek'])))
                session.add(position);session.flush()
                source=dict(winter_reconciliation_id=audit.id,replaced_position_ids=old[aid]['position_ids'],
                    size=size,quantity=str(quantity),source_rows=[r for g in groups for r in g['rows']])
                session.add(WareneingangPositionQuelle(position_id=position.id,data=source))
                created.append(dict(position_id=position.id,article_id=aid,variant_id=variant.id,size=size,quantity=str(quantity)))
            for pid in old[aid]['position_ids']:
                p=session.get(WareneingangPosition,pid)
                p.ersetzt_durch_abgleich_id=audit.id
                # Original expected quantities and immutable source snapshots remain as history.
        for group in created_groups:
            prices={(Decimal(r['uvp']),Decimal(r['ek'])) for r in group['rows']}
            if len(prices)!=1:reject('price_conflict',language)
            uvp,ek=next(iter(prices));row=group['rows'][0]
            artikel=_article_for(session,supplier_id,row)
            for size,q in group['sizes'].items():
                quantity=Decimal(q)
                if not quantity:continue
                variants=session.scalars(select(Variante).where(Variante.artikel_id==artikel.id,Variante.groesse==size,Variante.farbe.is_(None))).all()
                if len(variants)>1:reject('selection_required',language)
                variant=variants[0] if variants else Variante(artikel_id=artikel.id,groesse=size,farbe=None,ean=None,ean_intern=False)
                if not variants:session.add(variant);session.flush()
                position=WareneingangPosition(wareneingang_id=receipt_id,varianten_id=variant.id,menge=quantity,menge_eingetroffen=0,
                    einheit='Stk',uvp=uvp,ek=ek)
                session.add(position);session.flush()
                session.add(WareneingangPositionQuelle(position_id=position.id,data=dict(winter_reconciliation_id=audit.id,
                    replaced_position_ids=[],size=size,quantity=str(quantity),new_article=True,source_rows=group['rows'])))
                created.append(dict(position_id=position.id,article_id=artikel.id,variant_id=variant.id,size=size,quantity=str(quantity),new_article=True))
        for aid in withdraw:
            for pid in old[aid]['position_ids']:
                session.get(WareneingangPosition,pid).ersetzt_durch_abgleich_id=audit.id
        audit.data={**audit.data,'after':created}
        return dict(id=audit.id,repeated=False,positions=len(created))
