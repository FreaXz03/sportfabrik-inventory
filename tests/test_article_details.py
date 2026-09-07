from types import SimpleNamespace
from test_catalog import client
from app.routers.article_details import router
from app.routers.auth import require_login_api


def setup(client):
    client.app.include_router(router)
    user = SimpleNamespace(id=1, role="mitarbeiter", name="Anna", kassennummer="11")
    client.app.dependency_overrides[require_login_api] = lambda: user
    return user


def test_prices_chronological_and_units(client):
    setup(client)
    rows = client.get("/api/articles/1/prices").json()["items"]
    assert [r["date"] for r in rows] == ["2026-07-05", "2026-07-05", "2026-08-05"]
    assert {r["unit"] for r in rows} == {"PAA", "STK"}
    assert rows[-1]["uvp"] == "200.00"
    assert client.get("/api/articles/2/prices").json() == {"items": []}
    assert client.get("/api/articles/999/prices").status_code == 404


def test_notes_permissions_conflict_and_article_isolation(client):
    user = setup(client)
    url = "/api/articles/1/notes"
    response = client.post(url, json={"body": "  Für Stammkundin reservieren  "})
    assert response.status_code == 201
    note = response.json()
    assert note["body"] == "Für Stammkundin reservieren"
    assert note["author_name"] == "Anna" and note["created_at"]
    target = f"{url}/{note['id']}"
    assert client.put(target, json={"body": "Neu", "version": 1}).json()["version"] == 2
    assert (
        client.put(target, json={"body": "Veraltet", "version": 1}).status_code == 409
    )
    assert client.get(url).json()["items"][0]["body"] == "Neu"
    assert (
        client.put(
            f"/api/articles/2/notes/{note['id']}", json={"body": "Falsch", "version": 2}
        ).status_code
        == 404
    )
    user.id = 2
    assert not client.get(url).json()["items"][0]["can_edit"]
    assert client.put(target, json={"body": "Fremd", "version": 2}).status_code == 403
    user.role = "chef"
    user.name = "Chef"
    edited = client.put(target, json={"body": "Freigegeben", "version": 2}).json()
    assert edited["updated_by"] == "Chef" and edited["author_name"] == "Anna"
    assert client.get("/api/articles/2/notes").json()["total"] == 0


def test_note_validation_and_pagination(client):
    setup(client)
    url = "/api/articles/1/notes"
    for body in ["", "   ", "x" * 2001]:
        assert client.post(url, json={"body": body}).status_code == 422
    assert (
        client.post("/api/articles/999/notes", json={"body": "Test"}).status_code == 404
    )
    for i in range(21):
        assert client.post(url, json={"body": str(i)}).status_code == 201
    assert len(client.get(url).json()["items"]) == 20
    assert len(client.get(url + "?page=2").json()["items"]) == 1
    assert client.get(url).json()["total"] == 21


def test_delete_note_permissions_version_and_isolation(client):
    user = setup(client)
    url = "/api/articles/1/notes"
    note = client.post(url, json={"body": "Test"}).json()
    target = f"{url}/{note['id']}?version=1"
    assert (
        client.delete(f"/api/articles/2/notes/{note['id']}?version=1").status_code
        == 404
    )
    user.id = 2
    assert client.delete(target).status_code == 403
    user.id = 1
    assert (
        client.put(
            f"{url}/{note['id']}", json={"body": "Neu", "version": 1}
        ).status_code
        == 200
    )
    assert client.delete(target).status_code == 409
    assert client.get(url).json()["total"] == 1
    assert client.delete(target.replace("version=1", "version=2")).status_code == 204
    assert client.get(url).json()["total"] == 0
    assert client.delete(target).status_code == 404
    note = client.post(url, json={"body": "Weitere Notiz"}).json()
    user.id = 2
    user.role = "chef"
    assert client.delete(f"{url}/{note['id']}?version=1").status_code == 204


def test_supplier_group_variants_prices_and_notes(client):
    from app.core.database import get_session
    from app.core.models import Product, InvoiceItem
    setup(client)
    generator = client.app.dependency_overrides[get_session]()
    session = next(generator)
    try:
        variant = Product(brand='Hoka', supplier_article_no='SUP-9', ean='333', size='42')
        unrelated = Product(brand='Other', supplier_article_no='SUP-9', ean='444')
        blank = Product(brand='Nike', supplier_article_no='', ean='555')
        session.add_all([variant, unrelated, blank]); session.flush()
        variant_id, other_id, blank_id = variant.id, unrelated.id, blank.id
        session.add_all([InvoiceItem(product_id=p.id, invoice_id=1, quantity=1, unit='PAA', uvp=200) for p in [variant, unrelated, blank]])
        session.commit()
    finally:
        generator.close()
    for pid in [1, variant_id]:
        history = client.get(f'/api/articles/{pid}/history').json()
        assert history['total'] == 4
        assert {i['product_id'] for i in history['items']} == {1, variant_id}
        assert history['product']['supplier_article_no'] == 'SUP-9'
        prices = client.get(f'/api/articles/{pid}/prices').json()['items']
        assert prices[-1]['positions'] == 2
    assert client.get(f'/api/articles/{other_id}/history').json()['total'] == 1
    assert client.get('/api/articles/2/history').json()['total'] == 0
    assert client.get(f'/api/articles/{blank_id}/history').json()['total'] == 1
    note = client.post('/api/articles/1/notes', json={'body':'Alle Grössen'}).json()
    assert client.get(f'/api/articles/{variant_id}/notes').json()['items'][0]['id'] == note['id']
    assert client.put(f"/api/articles/{variant_id}/notes/{note['id']}", json={'body':'Gemeinsam', 'version':1}).status_code == 200
    assert client.delete(f"/api/articles/{variant_id}/notes/{note['id']}?version=2").status_code == 204
