from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .tipster_intelligence import TipsterPick, parse_basic_tipster_text


DATA_DIR = Path("data")
SOURCES_FILE = DATA_DIR / "tipster_sources.json"
DEFAULT_SOURCES = {
    "sources": [],
    "notes": "Register public RSS/Atom/HTML sources here. Telegram channels are handled by the Telegram listener."
}


@dataclass(frozen=True)
class TipsterSource:
    name: str
    url: str
    source_type: str = "web"
    enabled: bool = True
    sport: str = ""
    country: str = ""


def load_sources() -> list[TipsterSource]:
    if not SOURCES_FILE.exists():
        return []
    try:
        payload = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [TipsterSource(**item) for item in payload.get("sources", []) if item.get("url")]


def save_sources(sources: list[TipsterSource]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_FILE.write_text(json.dumps({"sources": [asdict(s) for s in sources]}, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = socket.getaddrinfo(host, None)
        for item in addresses:
            address = ipaddress.ip_address(item[4][0])
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
                return False
    except (OSError, ValueError):
        return False
    return True


def _extract_feed_items(text: str) -> list[str]:
    # RSS/Atom titles/descriptions plus common HTML article headings.
    values = re.findall(r"<(?:title|description|summary|h1|h2|h3)[^>]*>(.*?)</(?:title|description|summary|h1|h2|h3)>", text, re.I | re.S)
    cleaned: list[str] = []
    for value in values:
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"&(?:amp|nbsp|quot|lt|gt);", " ", value)
        value = " ".join(value.split())
        if len(value) >= 12:
            cleaned.append(value)
    return cleaned[:200]


async def fetch_source(source: TipsterSource) -> list[TipsterPick]:
    if not source.enabled or not _safe_public_url(source.url):
        return []
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False, headers={"User-Agent": "ANALISYS-BETSTOTAL/1.0"}) as client:
        response = await client.get(source.url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not any(token in content_type for token in ("text/", "xml", "json")):
            return []
        texts = _extract_feed_items(response.text)
    picks: list[TipsterPick] = []
    for text in texts:
        pick = parse_basic_tipster_text(text, source.name, source.source_type, source.url)
        if pick:
            picks.append(pick)
    return picks


async def collect_public_tipsters() -> dict[str, object]:
    sources = load_sources()
    all_picks: list[TipsterPick] = []
    statuses: list[dict[str, object]] = []
    for source in sources:
        try:
            picks = await fetch_source(source)
            all_picks.extend(picks)
            statuses.append({"source": source.name, "ok": True, "picks": len(picks)})
        except Exception as exc:  # source failures must not stop the collector
            statuses.append({"source": source.name, "ok": False, "picks": 0, "error": str(exc)[:180]})
    return {"sources": len(sources), "picks": all_picks, "statuses": statuses}
