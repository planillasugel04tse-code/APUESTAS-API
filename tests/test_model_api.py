from fastapi.testclient import TestClient

from betano_analyzer.main import app


def test_model_endpoints_are_exposed():
    client = TestClient(app)

    poisson = client.get('/api/v1/model/poisson', params={'home_goals': 1.4, 'away_goals': 1.1})
    assert poisson.status_code == 200
    assert abs(poisson.json()['home_win'] + poisson.json()['draw'] + poisson.json()['away_win'] - 1) < 1e-9

    elo = client.get('/api/v1/model/elo', params={'home_rating': 1550, 'away_rating': 1500})
    assert elo.status_code == 200
    assert abs(elo.json()['home_win'] + elo.json()['draw'] + elo.json()['away_win'] - 1) < 1e-9

    mc = client.get('/api/v1/model/monte-carlo', params={'home_goals': 1.4, 'away_goals': 1.1, 'simulations': 1000})
    assert mc.status_code == 200
    assert abs(mc.json()['home_win'] + mc.json()['draw'] + mc.json()['away_win'] - 1) < 0.001


def test_oddspapi_endpoints_are_exposed():
    paths = {route.path for route in app.routes}
    assert '/api/v1/oddspapi/account' in paths
    assert '/api/v1/oddspapi/sync' in paths
