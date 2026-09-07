from test_catalog import client
from app.routers.dashboard import router


def test_dashboard_sums_quantities_instead_of_rows(client):
    client.app.include_router(router)
    response = client.get('/api/dashboard')
    assert response.status_code == 200
    data = response.json()
    assert data['products'] == 2
    assert data['positions'] == 3
    assert data['delivered_quantity'] == '6.00'
