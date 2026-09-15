from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACCOUNTS_FILE = ROOT / "data" / "provider_accounts.json"


def oddspapi_connected() -> bool:
    """Check only the persisted active-account flag; never expose credentials."""
    try:
        payload = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, list):
        return False
    return any(
        isinstance(row, dict)
        and str(row.get("provider", "")).lower() == "oddspapi"
        and bool(row.get("active"))
        for row in payload
    )
