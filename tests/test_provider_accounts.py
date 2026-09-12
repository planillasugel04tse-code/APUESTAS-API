import json

from fastapi.testclient import TestClient

import betano_analyzer.provider_accounts as accounts_module
from betano_analyzer.main import app


client = TestClient(app)


def test_provider_accounts_page_and_api_are_exposed():
    page = client.get("/provider-accounts")
    assert page.status_code == 200
    assert "API Key" in page.text
    assert "No pongas aquí la contraseña" in page.text

    response = client.get("/api/v1/provider-accounts")
    assert response.status_code == 200
    assert "accounts" in response.json()


def test_save_account_masks_key_and_keeps_it_local(tmp_path, monkeypatch):
    accounts_file = tmp_path / "provider_accounts.json"
    env_file = tmp_path / ".env.local"
    monkeypatch.setattr(accounts_module, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(accounts_module, "LOCAL_ENV_FILE", env_file)
    monkeypatch.setattr(accounts_module, "DATA_DIR", tmp_path)

    saved = accounts_module.save_account(
        "oddspapi", "Gratis Perú", "usuario@example.com", "abcdefghijklmnop1234"
    )
    assert saved["api_key_masked"].startswith("abcd")
    assert "1234" in saved["api_key_masked"]
    assert "abcdefghijklmnop1234" not in json.dumps(saved)

    accounts = accounts_module._read_accounts()
    assert accounts[0]["api_key"] == "abcdefghijklmnop1234"

    activated = accounts_module.activate_account(saved["id"])
    assert activated["active"] is True
    assert "ODDSPAPI_KEY=abcdefghijklmnop1234" in env_file.read_text(encoding="utf-8")
    assert "ODDSPAPI_ENABLED=true" in env_file.read_text(encoding="utf-8")
