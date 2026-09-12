from fastapi.testclient import TestClient

from betano_analyzer.main import app

client = TestClient(app)


def test_provider_accounts_page_has_scanner_and_global_buttons():
    response = client.get("/provider-accounts")
    assert response.status_code == 200
    html = response.text
    assert "ESCANEAR CATÁLOGO" in html
    assert "ESCANEO PROFUNDO CONTROLADO" in html
    assert "SUREBET MUNDIAL PRE-PARTIDO" in html
    assert "SUREBET MUNDIAL LIVE" in html


def test_global_surebet_endpoint_has_global_scope():
    response = client.get("/api/v1/oddspapi/global-surebet")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "global"
    assert "sin filtro Perú" in payload["scope"]
