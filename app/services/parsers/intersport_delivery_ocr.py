"""Local column OCR for scanned INTERSPORT delivery notes.

The original text and coordinates remain the row anchors and audit source.
Barcodes are deliberately excluded from all recognition regions.
"""
import re
from collections import defaultdict


def recover(document, items, language):
    import pymupdf
    from ...core.i18n import translate
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return
    if not document.pdf_data:
        return
    by_page = defaultdict(list)
    for item in items:
        by_page[item['page']].append(item)
    with pymupdf.open(stream=document.pdf_data, filetype='pdf') as pdf:
        for number, rows in by_page.items():
            page = pdf[number-1]
            # Native digital documents need no expensive second pass. A
            # full-page raster plus hidden text indicates an existing scan.
            if not any(pymupdf.Rect(info['bbox']).get_area() > page.rect.get_area()*.65
                       for info in page.get_image_info()):
                continue
            bounds = rows[0]['_columns']
            crops = ((0, bounds['bar']-5, 'ids'),
                     (bounds['desc']-5, bounds['qty']-12, 'description'),
                     (bounds['qty']-12, page.rect.width, 'numbers'))
            candidates = {id(row): {} for row in rows}
            for left, right, kind in crops:
                # Include the very first row, whose tall invisible text box
                # can start above the printed table header's bottom.
                clip = pymupdf.Rect(left, bounds['top']-3, right, bounds['stop'])
                pix = page.get_pixmap(matrix=pymupdf.Matrix(4,4), clip=clip)
                image = Image.frombytes('RGB', (pix.width,pix.height),pix.samples)
                try:
                    data = pytesseract.image_to_data(image, config='--psm 6',
                        output_type=pytesseract.Output.DICT, timeout=30)
                except (RuntimeError, pytesseract.TesseractNotFoundError):
                    continue
                grouped = defaultdict(list)
                for i, text in enumerate(data['text']):
                    if not text.strip():
                        continue
                    y = clip.y0 + (data['top'][i]+data['height'][i]/2)/4
                    row = next((r for r in rows if r['_bounds'][0] <= y < r['_bounds'][1]), None)
                    if row is not None:
                        grouped[id(row)].append((i,data['left'][i],text,float(data['conf'][i])))
                for row in rows:
                    words = grouped[id(row)]
                    # Require a minimum confidence for every token; no guesses
                    # from a page total or a neighbouring size run.
                    if words and min(w[3] for w in words) >= 55:
                        text = ' '.join(w[2] for w in sorted(words))
                        candidates[id(row)][kind] = text
            for row in rows:
                values = candidates[id(row)]
                recovered = {}
                row['_ocr_supplier_readings'] = []
                # Anchoring to printed rows is independent of original IDs,
                # so wrapped/misassigned article numbers can be recovered too.
                match = re.fullmatch(r'(\d{6})[.,](\d{3})\s+(\d{6})\s+([A-Z][A-Z0-9]{5})',values.get('ids',''))
                if match:
                    recovered.update(article_no=match[1]+'.'+match[2],fedas_code=match[3],supplier_article_no=match[4])
                    row['_ocr_supplier_readings'].append(match[4])
                match = re.fullmatch(r'(\d+)\.?\s+(STK|PAA)\s+(\d+\.\d{2})',values.get('numbers',''))
                if match:
                    recovered.update(quantity=match[1],unit=match[2],uvp=match[3])
                desc = values.get('description','')
                if re.fullmatch(r'.+\s*\(.+\)\s*/\s*(?:\d+(?:\.5)?|[2-6]?X?[SML]|XX[SL]|OS [A-Z ]+|NO SIZE)(?:/\d+)?',desc):
                    recovered['description'] = desc
                if any(row.get(k)!=v for k,v in recovered.items()):
                    row.update(recovered)
                    row['hints'].append(translate('hints.parser.local_ocr_recovered',language))
                row['ocr_used'] = True
                for field, left, right, pattern, whitelist in (
                    ('article_no', 0, bounds['fed']-2, r'\d{6}\.\d{3}', '0123456789.'),
                    ('supplier_article_no', bounds['supplier']-4, bounds['bar']-5,
                     r'[A-Z][A-Z0-9]{5}', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
                ):
                    if re.fullmatch(pattern, row[field]):
                        continue
                    y0, y1 = row['_bounds']
                    clip = pymupdf.Rect(left, y0+.5, right, y1-.5)
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(6,6),clip=clip)
                    image = Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                    readings = []
                    for psm in (7,13):
                        try:
                            value = pytesseract.image_to_string(image,
                                config=f'--psm {psm} -c tessedit_char_whitelist={whitelist}',
                                timeout=10).strip().replace(' ', '')
                        except (RuntimeError,pytesseract.TesseractNotFoundError):
                            break
                        readings.append(value)
                        if field=='supplier_article_no' and re.fullmatch(pattern,value):
                            row['_ocr_supplier_readings'].append(value)
                    if len(readings)==2 and readings[0]==readings[1] and re.fullmatch(pattern,readings[0]):
                        row[field] = readings[0]
                        hint = translate('hints.parser.local_ocr_recovered',language)
                        if hint not in row['hints']:
                            row['hints'].append(hint)
