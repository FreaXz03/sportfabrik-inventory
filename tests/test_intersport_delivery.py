"""Synthetic delivery layout and opt-in private PDF regression."""
import os
from pathlib import Path
import pytest
import pymupdf
from app.services.parsers import detect_parser, read_document
from app.services.parsers import intersport


def delivery_pdf(rotation=0, quantity='4', article='220646.001'):
    doc = pymupdf.open()
    page = doc.new_page(width=842,height=595)
    def text(x,y,value):
        page.insert_text((x,y),value,fontsize=9)
    text(25,35,'INTERSPORT Lieferschein Nr. 900-734224')
    text(25,55,'Lieferdatum 04.09.2026')
    for x,value in [(25,'Art. Nr.'),(90,'FEDAS'),(130,'Lief. Art. Nr.'),(220,'Barcode'),(300,'Marke'),(375,'Bezeichnung'),(705,'Menge'),(745,'MEH'),(800,'UVP')]:
        text(x,100,value)
    for y in (125,145):
        for x,value in [(25,article),(90,'315921'),(130,'GZ5920'),(220,'||||||||'),(300,'adidas'),(375,'SHOWER (BLACK/WHITE)/10'),(725,quantity),(745,'PAA'),(795,'30.00')]:
            text(x,y,value)
    text(25,180,'Total Liefermenge 8')
    page.set_rotation(rotation)
    return doc.tobytes()


def test_delivery_retains_duplicates_and_ignores_barcode_strokes():
    document=read_document(delivery_pdf())
    assert detect_parser(document) is intersport
    result=intersport.parse(document)
    assert result['document_type']=='lieferschein'
    assert result['invoice_number']=='900-734224'
    assert result['item_count']==2
    assert result['warnings']==[]
    assert result['rows_with_warnings']==0
    for item in result['items']:
        assert (item['ean'],item['quantity'],item['size'],item['color'],item['ek'])==('','4','10','BLACK/WHITE',None)
    assert str(intersport.dates(document)['document_date'])=='2026-09-04'


def test_uncertain_values_and_total_mismatch_block_import():
    result=intersport.parse(read_document(delivery_pdf(quantity='?',article='22064?.001')))
    assert result['warnings']
    assert result['rows_with_warnings']==2
    assert result['items'][0]['quantity'] is None


def test_rotated_words_use_display_coordinates():
    doc=pymupdf.open()
    page=doc.new_page(width=595,height=842)
    page.insert_text((100,200),'ROTATED',fontsize=10,rotate=90)
    page.set_rotation(90)
    result=read_document(doc.tobytes()).pages[0]
    assert result.height==595
    assert result.words[0][0]>600
    assert result.words[0][1]<110


@pytest.mark.skipif(not os.environ.get('INTERSPORT_DELIVERY_PDF'),reason='Explicit private PDF path required')
def test_private_adidas_delivery():
    document=read_document(Path(os.environ['INTERSPORT_DELIVERY_PDF']).read_bytes())
    result=intersport.parse(document)
    assert result['pages']==47
    assert result['item_count']==1060
    assert result['barcode_ean_count'] > 0
    from app.services.ean import pruefziffer_stimmt
    assert all(pruefziffer_stimmt(i['ean']) for i in result['items'] if i['ean'])
    print('Private delivery:', result['item_count'], 'positions,', result['barcode_ean_count'], 'EANs,', result['rows_with_warnings'], 'warnings')
    assert result['invoice_number']=='900-734224'
    assert result['rows_with_warnings']>0
    assert result['warnings'] == []  # Column OCR reconciles the printed quantity total.
    assert str(intersport.dates(document)['document_date'])=='2026-09-04'


def test_corrections_recompute_delivery_total_and_identifier_warnings():
    from app.services.corrections import apply_corrections
    parsed=intersport.parse(read_document(delivery_pdf(quantity='I',article='22064?.001')))
    fixed=apply_corrections(parsed, {str(n):{'quantity':'4','article_no':'220646.001'} for n in (1,2)})
    assert fixed['warnings']==[]
    assert fixed['rows_with_warnings']==0
    invalid=apply_corrections(parsed, {str(n):{'quantity':'4','article_no':'still wrong'} for n in (1,2)})
    assert invalid['rows_with_warnings']==2


def test_delivery_numeric_ocr_and_negative_values():
    from app.services.parsers.intersport_delivery import numeric_text, normalize_size
    assert numeric_text('6s.00') == '65.00'
    assert numeric_text(',I') == '1'
    assert numeric_text('-1') == '-1'
    assert numeric_text('?') == '?'
    assert normalize_size('ZXL') == '2XL'
    assert normalize_size('1 O') == '10'
    assert normalize_size('Ao') == 'Ao'


def test_delivery_supplier_recovery_requires_repeated_unique_evidence():
    from app.services.parsers.intersport_delivery import corroborate_identifiers
    def row(code):
        return dict(article_no='378230.004', supplier_article_no=code)
    items = [row('JD2704'), row('JD2704'), row(')D2704'), row('JD2705')]
    corroborate_identifiers(items)
    assert items[2]['supplier_article_no'] == 'JD2704'
    assert items[3]['supplier_article_no'] == 'JD2705'
    uncertain = [row('JD2704'), row(')D2704')]
    corroborate_identifiers(uncertain)
    assert uncertain[1]['supplier_article_no'] == ')D2704'


def test_quantity_drift_and_tall_ocr_box_do_not_shift_rows():
    from dataclasses import replace
    from app.services.parsers.intersport_delivery import parse
    document = read_document(delivery_pdf())
    page = document.pages[0]
    words = []
    count = 0
    for word in page.words:
        if word[4] == '4':
            # Quantity starts slightly right of the header boundary and its
            # invisible text box extends upwards into the preceding row.
            count += 1
            word = (742, word[1]-8, 748, word[3], str(count+1), *word[5:])
        words.append(word)
    result = parse(replace(document, pages=[replace(page, words=words)]))
    assert [item['quantity'] for item in result['items']] == ['2', '3']


def test_first_quantity_box_is_not_part_of_table_header():
    from dataclasses import replace
    document = read_document(delivery_pdf())
    page = document.pages[0]
    words = []
    for word in page.words:
        if word[4] == '4' and word[1] < 130:
            # Hidden OCR text reaches up to the header and down past the
            # brand: it must not move the table boundary below the first row.
            word = (word[0], 95, word[2], 140, *word[4:])
        words.append(word)
    result = intersport.parse(replace(document, pages=[replace(page, words=words)]))
    assert result['item_count'] == 2


def test_delivery_ocr_does_not_touch_native_digital_pdf(monkeypatch):
    import pytesseract
    def unexpected(*args, **kwargs):
        raise AssertionError('Digital documents must not run OCR')
    monkeypatch.setattr(pytesseract, 'image_to_data', unexpected)
    result = intersport.parse(read_document(delivery_pdf()))
    assert result['item_count'] == 2
    assert result['warnings'] == []


@pytest.mark.parametrize('confidence', [20, 95])
def test_scanned_delivery_ocr_requires_confident_cell_evidence(monkeypatch, confidence):
    import pytesseract
    from PIL import Image
    from app.services.parsers.intersport_delivery import parse
    doc = pymupdf.open(stream=delivery_pdf(quantity='?'), filetype='pdf')
    page = doc[0]
    # A full-page raster with hidden text models a scanned delivery note.
    page.insert_image(page.rect, pixmap=pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0,0,10,10), False), overlay=False)
    document = read_document(doc.tobytes())
    words = document.pages[0].words
    header_y = next(w[1] for w in words if w[4]=='Bezeichnung')
    labels = {'FEDAS','Barcode','Marke','Bezeichnung','Menge','MEH','UVP'}
    top = max(w[3] for w in words if w[4] in labels and abs(w[1]-header_y)<12)-3
    texts = iter((
        ['220646.001 315921 GZ5920']*2,
        ['SHOWER (BLACK/WHITE)/10']*2,
        ['4 PAA 30.00']*2,
    ))
    def recognize(image, **kwargs):
        values = next(texts)
        return dict(text=values,top=[int((y-top)*4)-4 for y in (122,142)],
                    left=[0,0],height=[8,8],conf=[confidence,confidence])
    monkeypatch.setattr(pytesseract,'image_to_data',recognize)
    result = parse(document)
    if confidence == 95:
        assert [row['quantity'] for row in result['items']] == ['4','4']
        assert result['warnings'] == []
        assert all(row['raw_lines'] and '?' in row['raw_lines'][0] for row in result['items'])
    else:
        assert all(row['quantity'] is None for row in result['items'])
        assert result['warnings']


def test_supplier_consensus_uses_distinct_rows_and_rejects_ambiguity():
    from app.services.parsers.intersport_delivery import corroborate_identifiers
    def row(readings):
        return dict(article_no='297876.004',supplier_article_no='t87796',
                    _ocr_supplier_readings=readings)
    single = [row(['IB7796','IB7796']),row([])]
    corroborate_identifiers(single)
    assert single[1]['supplier_article_no']=='t87796'
    repeated = [row(['IB7796']),row(['IB7796']),row([])]
    corroborate_identifiers(repeated)
    assert all(i['supplier_article_no']=='IB7796' for i in repeated)
    ambiguous = [row(['IB7796','JB7796']),row(['IB7796','JB7796']),row([])]
    corroborate_identifiers(ambiguous)
    assert ambiguous[2]['supplier_article_no']=='t87796'


def test_numeric_size_normalization_keeps_clothing_letters():
    from app.services.parsers.intersport_delivery import normalize_size
    assert normalize_size("'I64")=='164'
    assert normalize_size('1sz')=='152'
    assert normalize_size('8.s')=='8.5'
    assert normalize_size('S')=='S'
    assert normalize_size('XS')=='XS'


def delivery_with_barcode(ean='4065419735048', second_ean=None):
    import zxingcpp
    doc = pymupdf.open(stream=delivery_pdf(), filetype='pdf')
    page = doc[0]
    page.add_redact_annot(pymupdf.Rect(215,108,299,150))
    page.apply_redactions()
    svg = zxingcpp.create_barcode(ean,zxingcpp.BarcodeFormat.Code128).to_svg()
    vector = pymupdf.open(stream=svg.encode(),filetype='svg')
    barcode = pymupdf.open(stream=vector.convert_to_pdf(),filetype='pdf')
    page.show_pdf_page(pymupdf.Rect(215,113,297,125),barcode,0)
    if second_ean:
        second_svg=zxingcpp.create_barcode(second_ean,zxingcpp.BarcodeFormat.Code128).to_svg()
        vector=pymupdf.open(stream=second_svg.encode(),filetype='svg')
        barcode=pymupdf.open(stream=vector.convert_to_pdf(),filetype='pdf')
    page.show_pdf_page(pymupdf.Rect(215,133,297,145),barcode,0)
    return doc.tobytes()


def test_delivery_reads_checksum_validated_barcode_and_retains_duplicate_rows():
    result=intersport.parse(read_document(delivery_with_barcode()))
    assert result['item_count']==2
    assert [row['ean'] for row in result['items']]==['4065419735048']*2
    assert result['duplicate_eans']=={'4065419735048':2}
    assert result['warnings']==[]
    assert not any('Keine EAN' in hint for row in result['items'] for hint in row['hints'])


def test_delivery_rejects_code128_with_invalid_ean_check_digit():
    result=intersport.parse(read_document(delivery_with_barcode('4065419735049')))
    assert all(row['ean']=='' for row in result['items'])


def test_delivery_adjacent_barcodes_keep_their_own_rows():
    result=intersport.parse(read_document(delivery_with_barcode(second_ean='4065419734942')))
    assert [row['ean'] for row in result['items']]==['4065419735048','4065419734942']


def test_barcode_consensus_rejects_conflicts_and_single_readings():
    from app.services.parsers.intersport_delivery_barcodes import confirmed_ean,valid_ean
    a,b='4065419735048','4065419734942'
    assert confirmed_ean([[a,a],[]])==('',False)
    assert confirmed_ean([[a],[a]])==(a,False)
    assert confirmed_ean([[a],[a],[b]])==('',True)
    assert not valid_ean('4065419735049')
    assert not valid_ean('123')
    assert not valid_ean('40654197350O8')


def test_barcode_conflict_clears_only_after_explicit_ean_review():
    from app.services.corrections import apply_corrections
    from app.core.i18n import translate
    parsed=intersport.parse(read_document(delivery_pdf()))
    warning=translate('errors.parser.barcode_ambiguous')
    parsed['items'][0]['warnings'].append(warning)
    assert warning in apply_corrections(parsed,{'1':{'quantity':'4'}})['items'][0]['warnings']
    assert warning in apply_corrections(parsed,{'1':{'ean':'4065419735049'}})['items'][0]['warnings']
    assert warning not in apply_corrections(parsed,{'1':{'ean':'4065419735048'}})['items'][0]['warnings']
    assert warning not in apply_corrections(parsed,{'1':{'ean':''}})['items'][0]['warnings']


def test_decoded_ean_is_saved_on_import_for_new_variant():
    import hashlib
    from conftest import neue_datenbank
    from sqlalchemy import select
    from app.core.models import Lagerort,Variante
    from app.services.importer import import_invoice
    sessions=neue_datenbank()
    pdf=delivery_with_barcode()
    with sessions() as session:
        location=session.scalar(select(Lagerort.id).where(Lagerort.code=='SF1'))
    import_invoice(pdf,'synthetic-barcode.pdf',hashlib.sha256(pdf).hexdigest(),sessions,location)
    with sessions() as session:
        variants=session.scalars(select(Variante)).all()
        assert len(variants)==1
        assert variants[0].ean=='4065419735048'
        assert variants[0].ean_intern is False
