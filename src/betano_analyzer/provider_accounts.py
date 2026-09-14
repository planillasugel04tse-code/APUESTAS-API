from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ACCOUNTS_FILE = DATA_DIR / "provider_accounts.json"
LOCAL_ENV_FILE = ROOT / ".env.local"


def _read_accounts() -> list[dict[str, Any]]:
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        payload = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _write_accounts(accounts: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ACCOUNTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ACCOUNTS_FILE)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * max(4, len(value) - 8) + value[-4:]


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "provider": row["provider"],
        "label": row.get("label", ""),
        "email": row.get("email", ""),
        "api_key_masked": _mask(row.get("api_key", "")),
        "active": bool(row.get("active", False)),
    }


def list_accounts() -> list[dict[str, Any]]:
    return [_public(row) for row in _read_accounts()]


def _write_local_env(api_key: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = LOCAL_ENV_FILE.read_text(encoding="utf-8") if LOCAL_ENV_FILE.exists() else ""
    lines = [line for line in existing.splitlines() if not line.startswith("ODDSPAPI_KEY=") and not line.startswith("ODDSPAPI_ENABLED=")]
    lines.extend([f"ODDSPAPI_KEY={api_key}", "ODDSPAPI_ENABLED=true"])
    LOCAL_ENV_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.environ["ODDSPAPI_KEY"] = api_key
    os.environ["ODDSPAPI_ENABLED"] = "true"


def save_account(provider: str, label: str, email: str, api_key: str, account_id: str | None = None) -> dict[str, Any]:
    provider = provider.strip().lower()
    if provider != "oddspapi":
        raise ValueError("Por ahora el gestor admite OddsPapi")
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("La API Key es obligatoria")

    accounts = _read_accounts()
    account_id = account_id or f"oddspapi-{len(accounts) + 1}"
    found = next((row for row in accounts if row.get("id") == account_id), None)
    if found:
        found.update({"provider": provider, "label": label.strip(), "email": email.strip(), "api_key": api_key})
    else:
        accounts.append({"id": account_id, "provider": provider, "label": label.strip(), "email": email.strip(), "api_key": api_key, "active": False})
    _write_accounts(accounts)
    return _public(next(row for row in accounts if row["id"] == account_id))


def activate_account(account_id: str) -> dict[str, Any]:
    accounts = _read_accounts()
    selected = next((row for row in accounts if row.get("id") == account_id), None)
    if not selected:
        raise ValueError("Cuenta no encontrada")
    for row in accounts:
        row["active"] = row is selected
    _write_accounts(accounts)
    _write_local_env(str(selected["api_key"]))
    return _public(selected)


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        raw = value.strip().replace(",", "")
        try:
            return float(raw) if "." in raw else int(raw)
        except ValueError:
            return None
    return None


def _find_pair(payload: Any, used_keys: set[str], limit_keys: set[str]) -> tuple[int | float | None, int | float | None]:
    """Find used/limit values anywhere in a nested OddsPapi account payload."""
    if isinstance(payload, dict):
        used = None
        limit = None
        for key, value in payload.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in used_keys or normalized.endswith("_used") or normalized.endswith("_usage"):
                used = _number(value)
            if normalized in limit_keys or normalized.endswith("_limit") or normalized.endswith("_quota"):
                limit = _number(value)
        if used is not None or limit is not None:
            return used, limit
        for value in payload.values():
            found_used, found_limit = _find_pair(value, used_keys, limit_keys)
            if found_used is not None or found_limit is not None:
                return found_used, found_limit
    elif isinstance(payload, list):
        for value in payload:
            found_used, found_limit = _find_pair(value, used_keys, limit_keys)
            if found_used is not None or found_limit is not None:
                return found_used, found_limit
    return None, None


def _extract_account_metrics(account: Any, headers: httpx.Headers) -> dict[str, Any]:
    used, limit = _find_pair(
        account,
        {"used", "usage", "requests_used", "request_used", "calls_used", "api_calls_used", "consumed"},
        {"limit", "requests_limit", "request_limit", "calls_limit", "api_calls_limit", "quota", "max_requests"},
    )
    if used is None:
        for key in ("x-ratelimit-used", "x-rate-limit-used", "x-ratelimit-usage"):
            if key in headers:
                used = _number(headers.get(key))
                break
    if limit is None:
        for key in ("x-ratelimit-limit", "x-rate-limit-limit", "x-ratelimit-quota"):
            if key in headers:
                limit = _number(headers.get(key))
                break

    remaining = max(0, limit - used) if used is not None and limit is not None else None

    def first(keys: tuple[str, ...]) -> Any:
        if not isinstance(account, dict):
            return None
        for key in keys:
            if key in account and account[key] not in (None, ""):
                return account[key]
        return None

    plan = first(("plan", "planName", "subscriptionPlan", "tier"))
    subscription = first(("subscription", "subscriptionStatus", "status"))
    valid_from = first(("validFrom", "valid_from", "startDate", "startsAt"))
    valid_until = first(("validUntil", "valid_until", "endDate", "expiresAt", "expirationDate"))
    last_used = first(("lastUsed", "last_use", "lastApiUse", "lastRequestAt", "lastUsedAt"))

    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "display": f"{used:g} / {limit:g}" if used is not None and limit is not None else None,
        "plan": plan,
        "subscription_status": subscription,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "last_api_use": last_used,
        "source": "OddsPapi account endpoint / rate-limit headers",
    }


async def check_oddspapi(api_key: str) -> dict[str, Any]:
    key = api_key.strip()
    if not key:
        raise ValueError("La API Key es obligatoria")
    url = "https://api.oddspapi.io/v4/account"
    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        response = await client.get(url, params={"apiKey": key}, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        metrics = _extract_account_metrics(payload, response.headers)

    return {
        "valid": True,
        "account": payload,
        "usage": metrics,
        "requests_used": metrics["used"],
        "request_limit": metrics["limit"],
        "quota_remaining": metrics["remaining"],
        "usage_display": metrics["display"],
        "plan": metrics["plan"],
        "subscription_status": metrics["subscription_status"],
        "valid_from": metrics["valid_from"],
        "valid_until": metrics["valid_until"],
        "last_api_use": metrics["last_api_use"],
        "quota_call": "no debería consumir solicitudes de cuotas",
    }
