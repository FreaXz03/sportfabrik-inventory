from collections import Counter
from pathlib import Path
import os
import re

import pymupdf
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.preview import router
from app.parser import InvoiceParseError, decimal_value, parse_invoice

app = FastAPI()
app.include_router(router)


@pytest.fixture
def invoice():
    path = os.environ.get('INTERSPORT_TEST_PDF')
    if not path:
        pytest.skip('INTERSPORT_TEST_PDF auf die Originalrechnung setzen')
    return Path(path).read_bytes()


def test_original_complete(invoice):
    result = parse_invoice(invoice)
    with pymupdf.open(stream=invoice, filetype='pdf') as doc:
        # Independent text-stream check: article identifier followed by EAN.
        # Supplier identifiers can also contain 12 digits and are not EANs.
        eans = [ean for page in doc for ean in re.findall(
            r'(?m)^\d{6}\.\d+\s*\n(\d{12,13})\s*$', page.get_text())]
    assert Counter(eans) == Counter(i['ean'] for i in result['items'])
    assert result['pages'] == 21
    assert result['item_count'] == 217
    assert result['page_item_counts'] == [7] + [11]*19 + [1]
    assert result['rows_with_warnings'] == 0
    assert result['warnings'] == []
    assert result['items'][7]['brand'] == 'Red Bull Spect Eyewear'
    assert result['items'][4]['size'] == 'S 51-55 CM'
    assert result['items'][4]['color'] == 'matte white/silver fade'
    assert result['items'][11]['description'].endswith('Short-Sl')
    assert result['duplicate_eans']['0725882069647'] == 4
    assert result['items'][-1]['article_no'] == '419291.002'
    assert all(i['color'] is not None and i['size'] is not None for i in result['items'])


def test_missing_ean_is_retained(invoice):
    with pymupdf.open(stream=invoice, filetype='pdf') as doc:
        page = doc[0]
        for rect in page.search_for('7613709480726'):
            page.add_redact_annot(rect)
        page.apply_redactions()
        result = parse_invoice(doc.tobytes())
    assert result['item_count'] == 217
    assert result['items'][0]['ean'] == ''
    assert result['items'][0]['warnings']


def test_api_preview(invoice):
    response = TestClient(app).post('/upload-preview', files={'file': ('invoice.pdf', invoice, 'application/pdf')})
    assert response.status_code == 200
    assert response.json()['preview_only'] is True
    assert response.json()['item_count'] == 217


@pytest.mark.parametrize('data', [b'', b'not a pdf', b'%PDF-broken'])
def test_invalid_pdf(data):
    with pytest.raises(InvoiceParseError):
        parse_invoice(data)
    assert TestClient(app).post('/upload-preview', files={'file': ('bad.pdf', data)}).status_code == 422


def test_unknown_layout():
    with pymupdf.open() as doc:
        doc.new_page().insert_text((30, 30), 'An unrelated document')
        with pytest.raises(InvoiceParseError, match='Tabellenkopf'):
            parse_invoice(doc.tobytes())


@pytest.mark.parametrize(('value', 'expected'), [('1’234.50','1234.50'), ('-2','-2'), ('1,5','1.5'), ('0.00','0.00')])
def test_decimal(value, expected):
    assert decimal_value(value) == expected


def test_upload_limit(monkeypatch):
    monkeypatch.setattr('app.preview.MAX_UPLOAD_BYTES', 4)
    assert TestClient(app).post('/upload-preview', files={'file': ('large.pdf', b'12345')}).status_code == 413
