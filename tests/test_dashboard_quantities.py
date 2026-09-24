from test_catalog import client
from app.routers.auth import get_active_lagerort
from app.routers.dashboard import router


def test_dashboard_sums_quantities_instead_of_rows(client):
    client.app.include_router(router)
    # Die Test-App ersetzt die Anmeldung durch `None` - ohne Filiale gibt es
    # keine Filialkennzahlen, nur die Stammzahlen.
    client.app.dependency_overrides[get_active_lagerort] = lambda: None
    response = client.get('/api/dashboard')
    assert response.status_code == 200
    data = response.json()
    assert data['products'] == 2
    assert data['positions'] == 3
    assert data['delivered_quantity'] == '6.00'
    assert data['filiale'] is None
