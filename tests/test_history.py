from test_catalog import client


def test_invoice_list(client):
    data = client.get("/api/invoices").json()
    assert data["total"] == 2
    assert [i["invoice_number"] for i in data["items"]] == ["new", "old"]
    assert [i["item_count"] for i in data["items"]] == [1, 2]
    assert client.get("/api/invoices?q=new").json()["total"] == 1
    assert client.get("/api/invoices?q=%").json()["total"] == 0
    assert (
        client.get("/api/invoices?page_size=1&page=2").json()["items"][0][
            "invoice_number"
        ]
        == "old"
    )


def test_invoice_positions(client):
    listing = client.get("/api/invoices?q=old").json()
    invoice_id = listing["items"][0]["id"]
    data = client.get(f"/api/invoices/{invoice_id}").json()
    assert data["total"] == 2
    assert [i["quantity"] for i in data["items"]] == ["3.00", "1.00"]
    assert data["items"][0]["source_available"] is False
    assert data["items"][0]["ean"] == "0012345678901"


def test_history_order_and_paging(client):
    product_id = client.get("/api/articles?brand=Hoka").json()["items"][0]["id"]
    url = f"/api/articles/{product_id}/history"
    data = client.get(url).json()
    assert data["total"] == 3
    assert [i["invoice_number"] for i in data["items"]] == ["new", "old", "old"]
    assert (
        client.get(url + "?page_size=1&page=2").json()["items"][0]["quantity"] == "3.00"
    )


def test_not_found_and_validation(client):
    assert client.get("/api/invoices/9999").status_code == 404
    assert client.get("/api/articles/9999/history").status_code == 404
    assert client.get("/api/invoices?page=0").status_code == 422
    assert client.get("/api/invoices/1?page_size=101").status_code == 422
    for path in ["/invoices", "/invoices/1", "/articles/1/history"]:
        assert client.get(path).status_code == 200


def test_snapshot_preserved(client):
    from app.core.database import get_session
    from app.core.models import InvoiceItemSource, InvoiceItem
    from sqlalchemy import select

    dependency = client.app.dependency_overrides[get_session]
    generator = dependency()
    session = next(generator)
    try:
        item = session.scalar(select(InvoiceItem).order_by(InvoiceItem.id))
        session.add(
            InvoiceItemSource(
                item_id=item.id,
                data={
                    "description": "Originalbezeichnung",
                    "row_number": 7,
                    "page": 2,
                    "raw_lines": ["Originaltext"],
                },
            )
        )
        session.commit()
        data = client.get(f"/api/invoices/{item.invoice_id}").json()["items"][0]
        assert data["description"] == "Originalbezeichnung"
        assert data["source_available"] is True
        assert data["row_number"] == 7 and data["page"] == 2
        assert data["raw_lines"] == ["Originaltext"]
    finally:
        generator.close()
