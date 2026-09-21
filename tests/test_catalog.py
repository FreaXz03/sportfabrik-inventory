from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.lagerorte import seed_lagerorte
from app.core.models import (
    Artikel,
    Base,
    Dokument,
    Lagerort,
    Lieferant,
    Variante,
    Wareneingang,
    WareneingangPosition,
)
from app.routers.auth import require_login_api, require_login_page
from app.routers.catalog import router
from app.core.database import get_session


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as s:
        seed_lagerorte(s)
        s.flush()
        sf1_id = s.scalar(select(Lagerort.id).where(Lagerort.code == "SF1"))
        lieferant = Lieferant(name="INTERSPORT Schweiz AG", typ="intersport", parser_key="intersport")
        s.add(lieferant)
        s.flush()
        artikel_hoka = Artikel(
            lieferant_id=lieferant.id,
            marke="Hoka",
            lieferanten_artikelnr="SUP-9",
            bezeichnung="Bondi 9",
        )
        artikel_nike = Artikel(
            lieferant_id=lieferant.id,
            marke="Nike",
            lieferanten_artikelnr=None,
            bezeichnung="100%_Cotton",
        )
        s.add_all([artikel_hoka, artikel_nike])
        s.flush()
        variante_hoka = Variante(artikel_id=artikel_hoka.id, ean="0012345678901")
        variante_nike = Variante(artikel_id=artikel_nike.id, ean="2222222222222")
        s.add_all([variante_hoka, variante_nike])
        s.flush()
        newer = Dokument(
            lieferant_id=lieferant.id,
            lagerort_id=sf1_id,
            typ="rechnung",
            dokumentnummer="new",
            dokumentdatum=date(2026, 8, 5),
            hochgeladen_am=datetime.now(timezone.utc),
        )
        older = Dokument(
            lieferant_id=lieferant.id,
            lagerort_id=sf1_id,
            typ="rechnung",
            dokumentnummer="old",
            dokumentdatum=date(2026, 7, 5),
            hochgeladen_am=datetime.now(timezone.utc),
        )
        s.add_all([newer, older])
        s.flush()
        newer_we = Wareneingang(
            dokument_id=newer.id, lagerort_id=sf1_id, status="eingetroffen", eingangsdatum=date(2026, 8, 5)
        )
        older_we = Wareneingang(
            dokument_id=older.id, lagerort_id=sf1_id, status="eingetroffen", eingangsdatum=date(2026, 7, 5)
        )
        s.add_all([newer_we, older_we])
        s.flush()
        s.add_all(
            [
                WareneingangPosition(
                    wareneingang_id=newer_we.id,
                    varianten_id=variante_hoka.id,
                    menge=Decimal("2"),
                    einheit="PAA",
                    uvp=Decimal("200"),
                ),
                WareneingangPosition(
                    wareneingang_id=older_we.id,
                    varianten_id=variante_hoka.id,
                    menge=Decimal("3"),
                    einheit="PAA",
                    uvp=Decimal("180"),
                ),
                WareneingangPosition(
                    wareneingang_id=older_we.id,
                    varianten_id=variante_hoka.id,
                    menge=Decimal("1"),
                    einheit="STK",
                    uvp=Decimal("180"),
                ),
            ]
        )
    app = FastAPI()
    app.include_router(router)
    from app.routers.history import router as history_router

    app.include_router(history_router)
    # Diese Tests prüfen Katalog-/Historie-Logik, nicht die Zugriffsrechte (siehe tests/test_auth.py).
    app.dependency_overrides[require_login_api] = lambda: None
    app.dependency_overrides[require_login_page] = lambda: None

    def session():
        with sessions() as s:
            yield s

    app.dependency_overrides[get_session] = session
    with TestClient(app) as c:
        yield c
    engine.dispose()


def test_aggregates_and_latest_price(client):
    response = client.get("/api/articles", params={"ean": "0012345678901"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["ean"] == "0012345678901"
    assert item["latest_uvp"] == "200.00"
    assert item["uvp_date"] == "2026-08-05"
    assert {d["unit"]: d["quantity"] for d in item["delivered"]} == {
        "PAA": "5.00",
        "STK": "1.00",
    }


@pytest.mark.parametrize(
    "params",
    [
        {"q": "bondi"},
        {"supplier_article_no": "SUP-9"},
        {"brand": "Hoka", "description": "BOND"},
        {"description": "%_"},
    ],
)
def test_filters(client, params):
    assert client.get("/api/articles", params=params).json()["total"] == 1


def test_combined_no_match(client):
    assert (
        client.get("/api/articles", params={"brand": "Nike", "q": "Bondi"}).json()[
            "total"
        ]
        == 0
    )


def test_pages(client):
    one = client.get("/api/articles?page_size=1").json()
    two = client.get("/api/articles?page_size=1&page=2").json()
    assert one["total"] == two["total"] == 2
    assert one["items"][0]["id"] != two["items"][0]["id"]
    assert two["items"][0]["latest_uvp"] is None
    assert client.get("/api/articles?page=0").status_code == 422
    assert client.get("/api/articles?page_size=101").status_code == 422


def test_page_and_brands(client):
    assert client.get("/articles").status_code == 200
    assert client.get("/api/brands").json() == ["Hoka", "Nike"]


@pytest.mark.parametrize(
    "sort_dir,expected", [("asc", ["Hoka", "Nike"]), ("desc", ["Nike", "Hoka"])]
)
def test_sort_by_brand(client, sort_dir, expected):
    data = client.get(
        "/api/articles", params={"sort_by": "brand", "sort_dir": sort_dir}
    ).json()
    assert [item["brand"] for item in data["items"]] == expected
    assert data["sort_by"] == "brand" and data["sort_dir"] == sort_dir


def test_sort_by_description_desc(client):
    data = client.get(
        "/api/articles", params={"sort_by": "description", "sort_dir": "desc"}
    ).json()
    assert [item["description"] for item in data["items"]] == ["Bondi 9", "100%_Cotton"]


def test_sort_invalid_column_rejected(client):
    assert (
        client.get("/api/articles", params={"sort_by": "latest_uvp"}).status_code == 422
    )
    assert (
        client.get("/api/articles", params={"sort_dir": "sideways"}).status_code == 422
    )


def test_sort_default_unchanged(client):
    # No sort params given: behaviour matches the previous default ordering.
    data = client.get("/api/articles").json()
    assert [item["brand"] for item in data["items"]] == ["Hoka", "Nike"]


def test_last_delivery_date_filter(client):
    from app.core.database import get_session
    generator = client.app.dependency_overrides[get_session]()
    session = next(generator)
    try:
        session.get(Variante, 1).last_seen = date(2026, 8, 5)
        session.get(Variante, 2).last_seen = date(2026, 7, 5)
        session.commit()
    finally:
        generator.close()
    url = '/api/articles'
    result = client.get(url, params={'last_delivery_from':'2026-08-05', 'last_delivery_to':'2026-08-05'}).json()
    assert result['total'] == 1 and result['items'][0]['id'] == 1
    assert client.get(url, params={'last_delivery_to':'2026-07-31'}).json()['items'][0]['id'] == 2
    assert client.get(url, params={'last_delivery_from':'2027-01-01'}).json()['total'] == 0
    assert client.get(url, params={'last_delivery_from':'2026-09-01','last_delivery_to':'2026-01-01'}).status_code == 422
    assert client.get(url, params={'last_delivery_from':'invalid'}).status_code == 422
    assert client.get(url).json()['total'] == 2


def test_search_and_export_with_empty_date_fields(client):
    params = {'supplier_article_no': 'SUP-9', 'last_delivery_from': '', 'last_delivery_to': ''}
    response = client.get('/api/articles', params=params)
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert client.get('/api/articles/export', params=params).status_code == 200
