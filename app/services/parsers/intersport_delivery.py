"""Local coordinate parser for INTERSPORT delivery notes with printed barcodes.

Barcode graphics are decoded separately; OCR strokes are never EAN digits.
Duplicate printed rows are retained.
Uncertain identifiers are never repaired by guessing.
"""
import re
from .base import DocumentParseError, datum, ergebnis, gleiche_summe, joined, pruefe_position
from ...core.i18n import DEFAULT_LANGUAGE, translate

NUMBER = re.compile(r'Lieferschein\s+N\s*r\.?\s*([0-9O]{3})\s*-\s*([0-9O ]{6,9})', re.I)


def detect(document):
    return bool(NUMBER.search(document.text) and all(
        label in document.text for label in ('FEDAS', 'Barcode', 'Bezeichnung', 'MEH', 'UVP')
    ))


def parse(document, language=DEFAULT_LANGUAGE):
    numbers = {a.replace('O', '0').replace('o', '0') + '-' + b.replace(' ', '').replace('O', '0').replace('o', '0')
               for a, b in NUMBER.findall(document.text)}
    if len(numbers) != 1:
        raise DocumentParseError(translate('errors.parser.mixed_invoice_numbers', language))
    items, warnings = [], []
    for page in document.pages:
        heads = [w for w in page.words if w[4] == 'Bezeichnung']
        if len(heads) != 1:
            raise DocumentParseError(translate('errors.parser.missing_table_header', language, page=page.number, hint=''))
        head = heads[0]
        header = {w[4]: w for w in page.words if abs(w[1] - head[1]) < 12}
        if not all(k in header for k in ('FEDAS', 'Barcode', 'Marke', 'Menge', 'MEH', 'UVP')):
            raise DocumentParseError(translate('errors.parser.missing_table_header', language, page=page.number, hint=''))
        top = max(header[k][3] for k in ('FEDAS', 'Barcode', 'Marke', 'Bezeichnung', 'Menge', 'MEH', 'UVP'))
        stop = min([w[1] for w in page.words if w[1] > top and w[4] in ('INTERSPORT', 'Total')] or [page.height - 35])
        # Brands provide a stable row anchor even when article IDs wrap or drift.
        anchors = sorted([w for w in page.words if top < w[1] < stop and
                          header['Marke'][0]-8 <= w[0] < head[0]-8], key=lambda w:w[1])
        qty_left = header['Menge'][0] - 12
        qty_right = header['MEH'][0]
        for idx, anchor in enumerate(anchors):
            center = (anchor[1]+anchor[3])/2
            lower = top if idx == 0 else (center+(anchors[idx-1][1]+anchors[idx-1][3])/2)/2
            upper = stop if idx+1 == len(anchors) else (center+(anchors[idx+1][1]+anchors[idx+1][3])/2)/2
            row = [w for w in page.words if lower <= (w[1]+w[3])/2 < upper]
            def cell(left, right):
                return joined(sorted([w for w in row if left <= w[0] < right], key=lambda w:w[0]))
            fed, bar, brand, desc, qty, unit = [header[k][0]-4 for k in ('FEDAS','Barcode','Marke','Bezeichnung','Menge','MEH')]
            # Supplier article starts at "Lief."; the internal article is first.
            supplier = next((w[0]-3 for w in header.values() if w[4]=='Lief.'), fed+45)
            uvp_start = header['MEH'][2]+3
            item = dict(article_no=re.sub(r'\s+', '', cell(0,fed)), fedas_code=re.sub(r'\s+', '',cell(fed,supplier)),
                        supplier_article_no=re.sub(r'\s+', '',cell(supplier,bar)), ean='',
                        brand=cell(brand,desc), description=cell(desc,qty-8), quantity=cell(qty-8,unit),
                        unit=cell(unit,uvp_start), uvp=cell(uvp_start,float('inf')), ek=None,
                        color=None,size=None,variant_raw=None,page=page.number,source_y=round(anchor[1],2),
                        raw_lines=[joined(sorted(row,key=lambda w:w[0]))],warnings=[],hints=[],ocr_used=page.ocr_used)
            # Match quantity boxes by their baseline, not their oversized OCR
            # centre; allow horizontal scan skew while excluding unit labels.
            quantity_words = [w for w in page.words if lower <= w[3]-6 < upper
                              and qty_left <= w[0] < qty_right+8
                              and w[4] not in ('STK', 'PAA')]
            item['quantity'] = joined(sorted(quantity_words,key=lambda w:w[0]))

            item['_bounds'] = (lower, upper)
            item['_columns'] = dict(bar=bar,brand=brand,fed=fed,supplier=supplier,desc=desc,qty=qty,top=top,stop=stop)
            items.append(item)
    from .intersport_delivery_ocr import recover
    recover(document, items, language)
    from .intersport_delivery_barcodes import recover as recover_barcodes
    recover_barcodes(document, items, language)
    for item in items:
        item.pop('_bounds', None)
        item.pop('_columns', None)
        finalize_item(item, language)
    corroborate_identifiers(items)
    for item in items:
        item.pop('_ocr_supplier_readings', None)
        validate_codes(item, language)
        pruefe_position(item, language)
    total = re.search(r'Total\s+Liefermenge\s+(\d+)',document.text)
    warnings.extend(gleiche_summe(total[1] if total else None,items,language))
    if total is None:
        warnings.append(translate('errors.parser.total_mismatch',language,summe='?',beleg='?'))
    result = ergebnis(document,items,warnings,'lieferschein',numbers.pop(),language)
    result['barcode_ean_count'] = sum(bool(i['ean']) for i in items)
    result['delivery_total'] = int(total[1]) if total else None
    result['ocr_pages'] = sorted(set(document.ocr_pages) | {i['page'] for i in items if i['ocr_used']})
    result['ocr_used'] = bool(result['ocr_pages'])
    return result


def dates(document, language=DEFAULT_LANGUAGE):
    values = re.findall(r'Lieferdatum\s+(\d{2}\.\d{2}\.\d{4})',document.text)
    dates_ = {datum(v) for v in values}
    if len(dates_) != 1 or None in dates_:
        raise DocumentParseError(translate('errors.importer.invoice_date_missing_or_ambiguous',language))
    value = dates_.pop()
    return dict(invoice_date=value,document_date=value)


def validate_codes(item, language=DEFAULT_LANGUAGE):
    for field, pattern in (('article_no',r'\d{6}\.\d{3}'),('supplier_article_no',r'[A-Z][A-Z0-9]{5}' if item.get('brand','').lower() in ('adidas','adldas') else r'[A-Z0-9]{5,12}')):
        if not re.fullmatch(pattern, item.get(field) or ''):
            item['warnings'].append(translate('errors.parser.invalid_value',language,
                field=translate(f'fields.{field}',language),value=item.get(field) or '?'))


def numeric_text(value):
    """Normalize OCR glyphs only inside strictly numeric columns.

    A minus sign remains a minus sign: never turn negative stock into positive.
    """
    value = value.strip()
    if re.fullmatch(r"[,.']?[1IiIl]", value):
        return '1'
    if re.fullmatch(r"'[0-9]+", value):
        return value[1:]
    return value.translate(str.maketrans({'s':'5','O':'0'}))


def normalize_size(value):
    value = value.lstrip("'’")
    compact = value.replace(' ', '')
    if re.fullmatch(r'[zZ2]X[Ll|]', compact):
        return '2XL'
    if re.search(r'[0-9IOl]', value) and re.fullmatch(r'[0-9IOlsSzZ ]+(?:\.[05sS])?', value):
        return compact.translate(str.maketrans({'I':'1','l':'1','O':'0','s':'5','S':'5','z':'2','Z':'2'}))
    return value


def corroborate_identifiers(items):
    """Recover an invalid OCR code only from repeated matching article rows.

    Require a unique, repeated valid spelling within the same internal article
    family and matching OCR glyphs. Fresh per-cell readings must occur on
    at least two different rows. Never change already valid codes.
    """
    from collections import Counter, defaultdict
    groups = defaultdict(Counter)
    for item in items:
        code = item['supplier_article_no']
        family = item['article_no'].split('.')[0]
        if re.fullmatch(r'\d{6}', family):
            evidence = set(item.get('_ocr_supplier_readings', []))
            if re.fullmatch(r'[A-Z][A-Z0-9]{5}', code):
                evidence.add(code)
            for candidate in evidence:
                groups[family][candidate] += 1
    for item in items:
        code = item['supplier_article_no']
        if re.fullmatch(r'[A-Z][A-Z0-9]{5}', code):
            continue
        candidates = [c for c,n in groups[item['article_no'].split('.')[0]].items()
                      if n >= 2 and (
                          (len(c)==len(code) and sum(a!=b for a,b in zip(c,code)) == 1)
                          or (item.get('_ocr_supplier_readings') is not None
                              and c[-4:]==code[-4:] and len(c)==6 and 4<=len(code)<=9))]
        if len(candidates)==1:
            # Preserve the original OCR spelling in raw_lines for review.
            item['supplier_article_no'] = candidates[0]


def finalize_item(item, language):
    item['quantity'] = numeric_text(item['quantity'])
    item['uvp'] = numeric_text(item['uvp'])
    if not re.fullmatch(r'\d+', item['quantity']):
        item['warnings'].append(translate('errors.parser.invalid_value',language,
            field=translate('fields.quantity',language),value=item['quantity']))
        item['quantity'] = ''
    variant = re.fullmatch(r'(.*?)\s*\((.*)\)\s*/\s*(.+)',item['description'])
    if variant:
        item.update(description=variant[1].strip(),color=variant[2].strip(),size=variant[3].strip(),variant_raw=variant[0])
        item['size'] = normalize_size(item['size'])
        # Whitespace within numeric sizes is an OCR artefact.
        if re.fullmatch(r'[\d .]+', item['size']):
            item['size']=item['size'].replace(' ','')
        if not re.fullmatch(r'(?:\d+(?:\.5)?|[2-6]?X?[SML]|XX[SL]|OS [A-Z ]+|NO SIZE)(?:/\d+)?',item['size']):
            item['warnings'].append(translate('errors.parser.color_size_ambiguous',language))
    else:
        item['warnings'].append(translate('errors.parser.color_size_ambiguous',language))
