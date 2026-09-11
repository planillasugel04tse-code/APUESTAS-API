from fastapi.testclient import TestClient

from betano_analyzer.db import initialize
from betano_analyzer.main import app


initialize()
client = TestClient(app)


def test_visual_panel_is_available():
    response = client.get("/panel")
    assert response.status_code == 200
    assert "Betano Live Analyzer" in response.text
    assert "CREAR PARTIDO" in response.text
    assert "/telegram-test" in response.text


def test_versioned_health_is_available():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "betano-live-analyzer"}


def test_telegram_config_status_does_not_expose_secrets():
    response = client.get("/api/v1/telegram/config")
    assert response.status_code == 200
    body = response.json()
    assert "has_api_hash" in body
    assert "has_api_id" in body
    assert "has_phone" in body
    assert "api_hash" not in body
    assert "api_id" not in body
