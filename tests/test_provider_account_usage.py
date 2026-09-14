from betano_analyzer.provider_accounts import _extract_account_metrics


def test_extract_nested_usage_and_limit():
    payload = {"account": {"requests": {"used": 8, "limit": 250}}}
    metrics = _extract_account_metrics(payload, {})
    assert metrics["used"] == 8
    assert metrics["limit"] == 250
    assert metrics["remaining"] == 242
    assert metrics["display"] == "8 / 250"


def test_extract_rate_limit_headers_when_body_has_no_quota():
    payload = {"plan": "Free"}
    headers = {"x-ratelimit-used": "8", "x-ratelimit-limit": "250"}
    metrics = _extract_account_metrics(payload, headers)
    assert metrics["used"] == 8
    assert metrics["limit"] == 250
    assert metrics["display"] == "8 / 250"
