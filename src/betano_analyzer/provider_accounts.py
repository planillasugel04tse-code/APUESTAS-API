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


async def check_oddspapi(api_key: str) -> dict[str, Any]:
    key = api_key.strip()
    if not key:
        raise ValueError("La API Key es obligatoria")
    url = "https://api.oddspapi.com/v4/account"
    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        response = await client.get(url, params={"apiKey": key}, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        return {"valid": True, "account": payload}
    return {"valid": True, "account": payload, "quota_call": "no debería consumir solicitudes de cuotas"}
