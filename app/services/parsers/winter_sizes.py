"""Local branch winter matrix reader. Never infer identifiers from neighbouring rows."""
import hashlib
import re
from decimal import Decimal

from .base import DocumentParseError, ergebnis, pruefe_position
from .bestellplan import _zeilen
from ...core.i18n import translate

TITLE = re.compile(r'Bestellung\s+Winter\s+\S+\s+(SF[1-4])\b')


def is_layout(document):
    all_branches = {'SF1','SF2','SF3','SF4'} <= {w[4] for w in document.pages[0].words}
    return not all_branches and bool(TITLE.search(document.pages[0].text)) and 'Art.' in document.text and 'Liefertermin' in document.text


def _number(value):
    return Decimal(value.replace('’', '').replace("'", ''))


def parse(document, language='de'):
    def error():
        raise DocumentParseError(translate('winter.invalid_layout', language))
    title = TITLE.search(document.pages[0].text)
    if not title or document.page_count % 2 or document.ocr_used:
        error()
    half = document.page_count // 2
    if not any('Art.' in p.text and 'Liefertermin' in p.text for p in document.pages[half:]):
        error()
    groups, items, warnings = [], [], []
    labels, section, price_order = {}, '', ('VP', 'EP')
    section_totals = [Decimal(0)] * 15
    ep_total = Decimal(0)
    for left, right in zip(document.pages[:half], document.pages[half:]):
        right_rows = _zeilen(right.words)
        for row in _zeilen(left.words):
            name = ' '.join(w[4] for w in row if w[0] < 220)
            first = [w[4] for w in row if 220 <= w[0] < 260]
            second = [w[4] for w in row if 260 <= w[0] < 300]
            sf = [w[4] for w in row if 935 <= w[0] < 978]
            total = [w[4] for w in row if 978 <= w[0] < 1020]
            amount = [w[4] for w in row if w[0] >= 1020]
            cells = {}
            for w in row:
                if 300 <= w[0] < 935:
                    col = round(((w[0] + w[2]) / 2 - 323.1) / 41.9)
                    if not 0 <= col < 15:
                        error()
                    cells.setdefault(col, []).append(w[4])
            cells = {k: ' '.join(v) for k,v in cells.items()}
            if first and second and {first[0],second[0]} == {'EP','VP'}:
                if any(section_totals):
                    error()  # A section must close with its printed subtotal.
                section, price_order = name, (first[0],second[0])
                labels = {k: ('ONESIZE' if v.casefold() == 'one size' else v) for k,v in cells.items()}
                if not labels or len(set(labels.values())) != len(labels):
                    error()
                continue
            if name.startswith('Total pro Grösse'):
                try:
                    actual = [_number(cells.get(i,'0')) for i in range(15)]
                    if actual != section_totals or not total or sum(actual) != _number(total[0]):
                        error()
                except (ValueError, ArithmeticError):
                    error()
                section_totals = [Decimal(0)] * 15
                continue
            numeric = lambda vs: bool(vs) and bool(re.fullmatch(r'\d+(?:\.\d+)?',vs[0]))
            if not (name and numeric(first) and numeric(second) and numeric(sf) and numeric(total)):
                # Reject numeric-looking table rows instead of dropping unreadable products.
                if name and numeric(total):
                    error()
                continue
            if not labels or not section:
                error()
            y = sum((w[1]+w[3])/2 for w in row)/len(row)
            partners = [r for r in right_rows if abs(sum((w[1]+w[3])/2 for w in r)/len(r)-y) <= 2]
            if len(partners) != 1:
                error()
            partner = partners[0]
            refs = [w[4] for w in partner if 270 < (w[0]+w[2])/2 < 335]
            if len(refs)>1:
                error()
            quantities = {}
            try:
                for i,value in cells.items():
                    q = _number(value)
                    if q < 0 or q != q.to_integral_value() or q >= 100000000:
                        error()
                    if q and i not in labels:
                        error()
                    section_totals[i] += q
                    if q:
                        quantities[labels[i]] = q
                count = _number(total[0])
                if count != sum(quantities.values()) or count != _number(sf[0]) or not amount:
                    error()
                line_ep = _number(amount[0]); ep_total += line_ep
                prices = dict(zip(price_order, (_number(first[0]),_number(second[0]))))
                vp_totals = [w[4] for w in partner if w[0] < 110]
                price_ok = prices['EP']*count == line_ep and len(vp_totals)==1 and _number(vp_totals[0]) == prices['VP']*count
            except (ValueError, ArithmeticError, KeyError):
                error()
            raw = ' '.join(w[4] for w in row)
            row_key = f'{left.number}:{len(groups)+1}'
            row_warnings = [] if price_ok else [translate('winter.price_conflict',language)]
            if 'ONESIZE' in labels.values() and any(size.isdigit() and int(size)<10 for size in quantities):
                row_warnings.append(translate('winter.ambiguous_size',language))
            group = dict(key=row_key, name=name, section=section, quantity=str(count), sizes={k:str(v) for k,v in quantities.items()},
                         printed_article_no=refs[0] if refs else None, page=left.number, paired_page=right.number,
                         row_y=y, raw_lines=[raw,' '.join(w[4] for w in partner)], warnings=row_warnings,
                         uvp=str(prices['VP']),ek=str(prices['EP']))
            groups.append(group)
            brand = next((b for b in ('Body Glove','Gizmo Riders','Alpen Gaudi','Nordic Grip') if name.casefold().startswith(b.casefold()+' ')),name.split()[0])
            for size,quantity in quantities.items():
                item = pruefe_position(dict(brand=brand, supplier_article_no=name,article_no=name,ean='',
                    description=name[len(brand):].strip() or name,color=None,size=size,quantity=str(quantity),unit='Stk',
                    uvp=str(prices['VP']),ek=str(prices['EP']),page=left.number,raw_lines=group['raw_lines'],
                    lagerort_code=title[1],winter_row=row_key,section=section,printed_article_no=group['printed_article_no']),language)
                items.append(item)
    if any(section_totals) or not groups or not items:
        error()
    footers = re.findall(r'CHF\s+([\d’\'.]+)', '\n'.join(p.text for p in document.pages[:half]))
    if footers and (len(footers)!=1 or _number(footers[0])!=ep_total):
        error()
    result = ergebnis(document,items,warnings,'bestellung','Winter-Groessen-'+hashlib.sha256(document.text.encode()).hexdigest()[:16],language)
    return {**result,'winter_sizes':True,'branch_code':title[1],'groups':groups}
