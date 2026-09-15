from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ACCOUNTS_FILE = DATA_DIR / "provider_accounts.json"

# Secrets intentionally live only in the running process. Closing/restarting the
# application clears this dictionary and requires the key again.
_SESSION_KEYS: dict[str, str] = {}


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
    # Never persist API keys or other secrets.
    safe = []
    for row in accounts:
        safe.append({k: v for k, v in row.items() if k not in {"api_key", "secret", "token", "password"}})
    tmp.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ACCOUNTS_FILE)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * max(4, len(value) - 8) + value[-4:]


def _public(row: dict[str, Any]) -> dict[str, Any]:
    key = _SESSION_KEYS.get(str(row.get("id", "")), "")
    return {
        "id": row["id"],
        "provider": row["provider"],
        "label": row.get("label", ""),
        "email": row.get("email", ""),
        "base_url": row.get("base_url", ""),
        "auth_location": row.get("auth_location", "query"),
        "auth_name": row.get("auth_name", "apiKey"),
        "test_path": row.get("test_path", "/account"),
        "api_key_masked": _mask(key),
        "connected": bool(key),
        "active": bool(row.get("active", False)) and bool(key),
    }


def list_accounts() -> list[dict[str, Any]]:
    return [_public(row) for row in _read_accounts()]


def _session_key_for(account_id: str) -> str:
    return _SESSION_KEYS.get(account_id, "")


def active_account() -> dict[str, Any] | None:
    for row in _read_accounts():
        if row.get("active") and _session_key_for(str(row.get("id", ""))):
            return _public(row)
    return None


def session_key(provider: str = "oddspapi") -> str:
    for row in _read_accounts():
        if row.get("active") and str(row.get("provider", "")).lower() == provider.lower():
            return _session_key_for(str(row.get("id", "")))
    return ""


def clear_session() -> None:
    _SESSION_KEYS.clear()
    os.environ.pop("ODDSPAPI_KEY", None)
    os.environ.pop("ODDSPAPI_ENABLED", None)


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower().replace(" ", "-")


def save_account(
    provider: str,
    label: str,
    email: str,
    api_key: str,
    account_id: str | None = None,
    base_url: str | None = None,
    auth_location: str = "query",
    auth_name: str = "apiKey",
    test_path: str = "/account",
) -> dict[str, Any]:
    provider = _normalize_provider(provider)
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("La API Key es obligatoria")
    if auth_location not in {"query", "header"}:
        raise ValueError("La autenticación debe ser por query o header")
    if not base_url:
        base_url = "https://api.oddspapi.io/v4" if provider == "oddspapi" else ""
    if not base_url:
        raise ValueError("La URL base del proveedor es obligatoria")
    account_id = account_id or f"{provider}-{uuid.uuid4().hex[:8]}"

    accounts = _read_accounts()
    found = next((row for row in accounts if row.get("id") == account_id), None)
    row = {
        "id": account_id,
        "provider": provider,
        "label": label.strip() or provider.upper(),
        "email": email.strip(),
        "base_url": base_url.rstrip("/"),
        "auth_location": auth_location,
        "auth_name": auth_name.strip() or "apiKey",
        "test_path": test_path.strip() or "/account",
        "active": bool(found.get("active", False)) if found else False,
    }
    if found:
        found.update(row)
    else:
        accounts.append(row)
    _write_accounts(accounts)
    _SESSION_KEYS[account_id] = api_key
    return _public(row)


def activate_account(account_id: str) -> dict[str, Any]:
    accounts = _read_accounts()
    selected = next((row for row in accounts if row.get("id") == account_id), None)
    if not selected:
        raise ValueError("Proveedor no encontrado")
    key = _session_key_for(account_id)
    if not key:
        raise ValueError("La API Key de este proveedor no está disponible en esta sesión. Vuelve a conectarlo.")
    for row in accounts:
        row["active"] = row is selected
    _write_accounts(accounts)
    # Only the current process receives the secret.
    clear_session()
    _SESSION_KEYS[account_id] = key
    if str(selected.get("provider")) == "oddspapi":
        os.environ["ODDSPAPI_KEY"] = key
        os.environ["ODDSPAPI_ENABLED"] = "true"
    return _public(selected)


def remove_account(account_id: str) -> None:
    accounts = _read_accounts()
    remaining = [row for row in accounts if row.get("id") != account_id]
    if len(remaining) == len(accounts):
        raise ValueError("Proveedor no encontrado")
    _SESSION_KEYS.pop(account_id, None)
    _write_accounts(remaining)
    if not any(row.get("active") for row in remaining):
        clear_session()


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
    if isinstance(payload, dict):
        used = limit = None
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
                used = _number(headers.get(key)); break
    if limit is None:
        for key in ("x-ratelimit-limit", "x-rate-limit-limit", "x-ratelimit-quota"):
            if key in headers:
                limit = _number(headers.get(key)); break
    remaining = max(0, limit - used) if used is not None and limit is not None else None

    def first(keys: tuple[str, ...]) -> Any:
        if not isinstance(account, dict): return None
        for key in keys:
            if key in account and account[key] not in (None, ""):
                return account[key]
        return None

    return {
        "used": used, "limit": limit,
        "remaining": remaining,
        "display": f"{used:g} / {limit:g}" if used is not None and limit is not None else None,
        "plan": first(("plan", "planName", "subscriptionPlan", "tier")),
        "subscription_status": first(("subscription", "subscriptionStatus", "status")),
        "valid_from": first(("validFrom", "valid_from", "startDate", "startsAt")),
        "valid_until": first(("validUntil", "valid_until", "endDate", "expiresAt", "expirationDate")),
        "last_api_use": first(("lastUsed", "last_use", "lastApiUse", "lastRequestAt", "lastUsedAt")),
        "source": "provider account endpoint / rate-limit headers",
    }


def _redact_sensitive(value: Any) -> Any:
    sensitive_fragments = ("apikey", "api_key", "api-key", "secret", "token", "password", "authorization")
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if any(f in str(k).lower().replace("-", "_") for f in sensitive_fragments) else _redact_sensitive(v) for k, v in value.items()}
    if isinstance(value, list): return [_redact_sensitive(v) for v in value]
    return value


async def check_provider(provider: str, api_key: str, base_url: str | None = None, auth_location: str = "query", auth_name: str = "apiKey", test_path: str = "/account") -> dict[str, Any]:
    provider = _normalize_provider(provider)
    key = api_key.strip()
    if not key: raise ValueError("La API Key es obligatoria")
    base_url = (base_url or ("https://api.oddspapi.io/v4" if provider == "oddspapi" else "")).rstrip("/")
    if not base_url: raise ValueError("La URL base del proveedor es obligatoria")
    url = base_url + "/" + test_path.lstrip("/")
    params = {auth_name: key} if auth_location == "query" else None
    headers = {"Accept": "application/json", auth_name: key} if auth_location == "header" else {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
        metrics = _extract_account_metrics(payload, response.headers) if provider == "oddspapi" else {"source": "provider test endpoint"}
    return {"valid": True, "account": _redact_sensitive(payload), "usage": metrics, "plan": metrics.get("plan"), "subscription_status": metrics.get("subscription_status"), "valid_from": metrics.get("valid_from"), "valid_until": metrics.get("valid_until")}


async def check_oddspapi(api_key: str) -> dict[str, Any]:
    return await check_provider("oddspapi", api_key)
