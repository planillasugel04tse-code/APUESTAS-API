from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import re
import socket
import time
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
    rows = payload.get("sources", []) if isinstance(payload, dict) else []
    result: list[TipsterSource] = []
    for item in rows:
        if not isinstance(item, dict) or not item.get("url") or not item.get("name"):
            continue
        try:
            result.append(TipsterSource(**item))
        except TypeError:
            continue
    return result


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
    values = re.findall(r"<(?:title|description|summary|content|h1|h2|h3)[^>]*>(.*?)</(?:title|description|summary|content|h1|h2|h3)>", text, re.I | re.S)
    cleaned: list[str] = []
    for value in values:
        value = re.sub(r"<[^>]+>", " ", value)
        value = html.unescape(value)
        value = " ".join(value.split())
        if len(value) >= 12:
            cleaned.append(value)
    return cleaned[:200]


async def fetch_source(source: TipsterSource) -> list[TipsterPick]:
    if not source.enabled or not _safe_public_url(source.url):
        return []
    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": "ANALISYS-BETSTOTAL/1.0"},
    ) as client:
        response = await client.get(source.url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not any(token in content_type for token in ("text/", "xml", "json")):
            return []
        texts = _extract_feed_items(response.text)
    picks: list[TipsterPick] = []
    seen: set[tuple[str, str, str, float | None, float | None]] = set()
    for text in texts:
        pick = parse_basic_tipster_text(text, source.name, source.source_type, source.url)
        if not pick:
            continue
        key = (pick.event.lower().strip(), pick.market.lower().strip(), pick.selection.lower().strip(), pick.odds, pick.line)
        if key in seen:
            continue
        seen.add(key)
        picks.append(pick)
    return picks


async def collect_public_tipsters() -> dict[str, object]:
    """Collect only from explicitly registered, reachable public sources.

    Sources are isolated so one timeout or malformed feed cannot stop the
    complete collection. Fetching is concurrent with a small semaphore to
    avoid creating an unbounded number of outbound requests.
    """
    sources = [source for source in load_sources() if source.enabled]
    semaphore = asyncio.Semaphore(6)

    async def collect_one(source: TipsterSource) -> tuple[TipsterSource, list[TipsterPick], dict[str, object]]:
        started = time.perf_counter()
        async with semaphore:
            try:
                picks = await fetch_source(source)
                return source, picks, {
                    "source": source.name,
                    "ok": True,
                    "picks": len(picks),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            except Exception as exc:  # source failures must not stop the collector
                return source, [], {
                    "source": source.name,
                    "ok": False,
                    "picks": 0,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "error": str(exc)[:180],
                }

    results = await asyncio.gather(*(collect_one(source) for source in sources))
    all_picks: list[TipsterPick] = []
    statuses: list[dict[str, object]] = []
    seen_global: set[tuple[str, str, str, float | None, float | None]] = set()
    for source, picks, status in results:
        for pick in picks:
            key = (pick.event.lower().strip(), pick.market.lower().strip(), pick.selection.lower().strip(), pick.odds, pick.line)
            if key in seen_global:
                continue
            seen_global.add(key)
            all_picks.append(pick)
        statuses.append(status)
    return {
        "sources": len(sources),
        "enabled_sources": len(sources),
        "picks": all_picks,
        "unique_picks": len(all_picks),
        "statuses": statuses,
    }
