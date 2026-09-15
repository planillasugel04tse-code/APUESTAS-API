from __future__ import annotations

from betano_analyzer.provider_accounts import _redact_sensitive


def test_redact_sensitive_removes_nested_provider_credentials():
    payload = {
        "apiKey": "REAL-KEY",
        "subscription": {"token": "SECRET", "status": "active"},
        "sports": [{"name": "football", "api_key": "OTHER-KEY"}],
        "public": "ok",
    }

    clean = _redact_sensitive(payload)

    assert clean["apiKey"] == "[REDACTED]"
    assert clean["subscription"]["token"] == "[REDACTED]"
    assert clean["sports"][0]["api_key"] == "[REDACTED]"
    assert clean["public"] == "ok"
