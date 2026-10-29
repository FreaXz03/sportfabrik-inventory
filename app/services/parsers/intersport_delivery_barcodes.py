"""Decode printed row barcodes locally; never interpret OCR strokes as digits.

A Code 128 symbol can contain an EAN. Both the symbol checksum (ZXing) and
GS1 check digit must pass, and two render/binarization variants must agree.
No EAN is copied from an adjacent row or inferred from an article number.
"""
from collections import Counter, defaultdict
from math import ceil, floor
import re


def valid_ean(value):
    """Pure GS1 check, independent of database/application initialization."""
    return bool(re.fullmatch(r'(?:[0-9]{8}|[0-9]{12,14})',value or '') and
                sum(int(d)*(1 if n%2==0 else 3) for n,d in enumerate(reversed(value)))%10==0)


def confirmed_ean(readings):
    """Each reading is one independent rendering/binarization configuration.

    Duplicate detections within one image count once. Any competing valid
    number leaves the row unassigned, even if a majority favours another.
    """
    counts = Counter(code for reading in readings for code in set(reading) if valid_ean(code))
    if len(counts)==1:
        code,count = next(iter(counts.items()))
        if count>=2:
            return code,False
    return '',len(counts)>1


def recover(document,items,language):
    if not document.pdf_data:
        return
    import pymupdf
    import zxingcpp
    from PIL import Image
    from ...core.i18n import translate
    formats = (zxingcpp.BarcodeFormat.Code128,zxingcpp.BarcodeFormat.EAN13,
               zxingcpp.BarcodeFormat.EAN8,zxingcpp.BarcodeFormat.UPCA,
               zxingcpp.BarcodeFormat.ITF)
    pages = defaultdict(list)
    for item in items:
        pages[item['page']].append(item)
    with pymupdf.open(stream=document.pdf_data,filetype='pdf') as pdf:
        for number,rows in pages.items():
            page = pdf[number-1]
            cols = rows[0]['_columns']
            # Leave quiet zones on both sides, but exclude the brand column.
            clip = pymupdf.Rect(max(0,cols['bar']-14),cols['top'],
                                cols['brand']-1,cols['stop'])
            readings = {id(row):[] for row in rows}
            for scale in (6,8,10):
                pix = page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),
                                     clip=clip,colorspace=pymupdf.csGRAY)
                strip = Image.frombytes('L',(pix.width,pix.height),pix.samples)
                for row in rows:
                    lower,upper = row['_bounds']
                    image = strip.crop((0,max(0,floor(lower*scale)-pix.y),
                                        pix.width,min(pix.height,ceil(upper*scale)-pix.y)))
                    variants = (image,image.point(lambda v:0 if v<110 else 255),
                                image.point(lambda v:0 if v<180 else 255))
                    for variant in variants:
                        # return_errors=False rejects symbol checksum errors.
                        decoded = zxingcpp.read_barcodes(variant,formats=formats,
                                                        try_downscale=False,return_errors=False)
                        values = set()
                        for barcode in decoded:
                            position = barcode.position
                            center = sum(p.y for p in (position.top_left,position.top_right,
                                                       position.bottom_left,position.bottom_right))/4
                            # Reject a neighbouring symbol visible only at the
                            # crop edge: its centre must lie inside this row.
                            if barcode.valid and 2*scale <= center <= image.height-2*scale and valid_ean(barcode.text):
                                values.add(barcode.text)
                        readings[id(row)].append(values)
            for row in rows:
                code,conflict = confirmed_ean(readings[id(row)])
                if code:
                    row['ean'] = code
                    row['hints'].append(translate('hints.parser.barcode_recovered',language))
                elif conflict:
                    row['warnings'].append(translate('errors.parser.barcode_ambiguous',language))
