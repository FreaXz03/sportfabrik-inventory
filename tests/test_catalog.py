from datetime import date
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.models import Base, Product, Invoice, InvoiceItem
from app.routers.auth import require_login_api, require_login_page
from app.routers.catalog import router
from app.core.database import get_session

@pytest.fixture
def client():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions=sessionmaker(engine)
    with sessions.begin() as s:
        p=Product(brand='Hoka',description='Bondi 9',ean='0012345678901',article_no='333.01',supplier_article_no='SUP-9')
        other=Product(brand='Nike',description='100%_Cotton',ean='2222222222222')
        s.add_all([p,other]);s.flush()
        newer=Invoice(invoice_number='new',invoice_date=date(2026,8,5))
        older=Invoice(invoice_number='old',invoice_date=date(2026,7,5))
        s.add_all([newer,older]);s.flush()
        s.add_all([InvoiceItem(product_id=p.id,invoice_id=newer.id,quantity=Decimal('2'),unit='PAA',uvp=Decimal('200')),
                   InvoiceItem(product_id=p.id,invoice_id=older.id,quantity=Decimal('3'),unit='PAA',uvp=Decimal('180')),
                   InvoiceItem(product_id=p.id,invoice_id=older.id,quantity=Decimal('1'),unit='STK',uvp=Decimal('180'))])
    app=FastAPI();app.include_router(router)
    from app.routers.history import router as history_router
    app.include_router(history_router)
    # Diese Tests prüfen Katalog-/Historie-Logik, nicht die Zugriffsrechte (siehe tests/test_auth.py).
    app.dependency_overrides[require_login_api] = lambda: None
    app.dependency_overrides[require_login_page] = lambda: None
    def session():
        with sessions() as s: yield s
    app.dependency_overrides[get_session]=session
    with TestClient(app) as c: yield c
    engine.dispose()

def test_aggregates_and_latest_price(client):
    response=client.get('/api/articles',params={'ean':'0012345678901'})
    assert response.status_code==200
    data=response.json();assert data['total']==1
    item=data['items'][0]
    assert item['ean']=='0012345678901'
    assert item['latest_uvp']=='200.00'
    assert item['uvp_date']=='2026-08-05'
    assert {d['unit']:d['quantity'] for d in item['delivered']}=={'PAA':'5.00','STK':'1.00'}

@pytest.mark.parametrize('params',[{'q':'bondi'},{'article_no':'SUP-9'},{'brand':'Hoka','description':'BOND'},{'description':'%_'}])
def test_filters(client,params):
    assert client.get('/api/articles',params=params).json()['total']==1

def test_combined_no_match(client):
    assert client.get('/api/articles',params={'brand':'Nike','q':'Bondi'}).json()['total']==0

def test_pages(client):
    one=client.get('/api/articles?page_size=1').json()
    two=client.get('/api/articles?page_size=1&page=2').json()
    assert one['total']==two['total']==2
    assert one['items'][0]['id']!=two['items'][0]['id']
    assert two['items'][0]['latest_uvp'] is None
    assert client.get('/api/articles?page=0').status_code==422
    assert client.get('/api/articles?page_size=101').status_code==422

def test_page_and_brands(client):
    assert client.get('/articles').status_code==200
    assert client.get('/api/brands').json()==['Hoka','Nike']

@pytest.mark.parametrize('sort_dir,expected',[('asc',['Hoka','Nike']),('desc',['Nike','Hoka'])])
def test_sort_by_brand(client,sort_dir,expected):
    data=client.get('/api/articles',params={'sort_by':'brand','sort_dir':sort_dir}).json()
    assert [item['brand'] for item in data['items']]==expected
    assert data['sort_by']=='brand' and data['sort_dir']==sort_dir

def test_sort_by_description_desc(client):
    data=client.get('/api/articles',params={'sort_by':'description','sort_dir':'desc'}).json()
    assert [item['description'] for item in data['items']]==['Bondi 9','100%_Cotton']

def test_sort_invalid_column_rejected(client):
    assert client.get('/api/articles',params={'sort_by':'latest_uvp'}).status_code==422
    assert client.get('/api/articles',params={'sort_dir':'sideways'}).status_code==422

def test_sort_default_unchanged(client):
    # No sort params given: behaviour matches the previous default ordering.
    data=client.get('/api/articles').json()
    assert [item['brand'] for item in data['items']]==['Hoka','Nike']
