from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone

import httpx

from src.config import config
from src.providers.base_provider import OddsProvider


class APIProvider(OddsProvider):
    """
    OddsPapi v4 provider.

    This class is the only place that talks to the external odds API. Flask
    routes must call it through the service layer or explicit local endpoints.
    """

    def __init__(self, api_key: str = config.EXTERNAL_API_KEY, api_url: str = config.EXTERNAL_API_URL):
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.sport_id = config.ODDSPAPI_SPORT_ID
        self.language = config.ODDSPAPI_LANGUAGE
        self.odds_format = config.ODDSPAPI_ODDS_FORMAT
        self.bookmakers = config.ODDSPAPI_BOOKMAKERS
        self.use_tournaments = config.ODDSPAPI_USE_TOURNAMENTS
        self.tournament_ids = config.ODDSPAPI_TOURNAMENT_IDS
        self.fixture_days = config.ODDSPAPI_FIXTURE_DAYS
        self.max_fixtures = config.ODDSPAPI_MAX_FIXTURES
        self.last_status: Dict[str, Any] = self._empty_status()

    def get_events(self) -> List[Dict[str, Any]]:
        """Fetch real odds from OddsPapi and convert them to the internal event schema."""
        self.last_status = self._empty_status()
        self.last_status["requested_at"] = datetime.now(timezone.utc).isoformat()
        self.last_status["mode"] = "API"
        self.last_status["endpoint"] = "odds-by-tournaments" if self.use_tournaments and self.tournament_ids else "fixtures+odds"
        if not self.api_key:
            self.last_status["error"] = "EXTERNAL_API_KEY is not configured"
            return []

        try:
            if self.use_tournaments and self.tournament_ids:
                raw_data = self._request(
                    "odds-by-tournaments",
                    {
                        "tournamentIds": self.tournament_ids,
                        "bookmakers": self.bookmakers,
                        "language": self.language,
                        "oddsFormat": self.odds_format,
                    },
                )
            else:
                raw_data = self._get_odds_by_limited_fixtures()
        except httpx.HTTPStatusError as exc:
            self.last_status["error"] = f"HTTP {exc.response.status_code}: {exc.response.text[:500]}"
            return []
        except httpx.HTTPError as exc:
            self.last_status["error"] = str(exc)
            return []

        return self._normalize_oddspapi_response(raw_data)

    def get_odds(self, event_id: str) -> List[Dict[str, Any]]:
        """Return bookmakers and odds for a single normalized event."""
        for event in self.get_events():
            if event["event_id"] == event_id:
                return event.get("bookmakers", [])
        return []

    def get_statistics(self, team_name: str) -> Dict[str, Any]:
        """External statistics are not enabled in this phase."""
        return {"team": team_name, "matches_played": 0, "avg_goals": 0.0, "avg_corners": 0.0}

    def get_account(self) -> Dict[str, Any]:
        """Fetch account and quota information. OddsPapi documents this as unmetered."""
        if not self.api_key:
            return {"configured": False, "error": "EXTERNAL_API_KEY is not configured"}
        try:
            account = self._request("account", {})
            account.pop("api_key", None)
            account["configured"] = True
            return account
        except httpx.HTTPError as exc:
            return {"configured": True, "error": str(exc)}

    def get_bookmakers(self) -> List[Dict[str, Any]]:
        """Fetch available bookmakers from OddsPapi."""
        if not self.api_key:
            return []

    def get_tournaments(self) -> List[Dict[str, Any]]:
        """Fetch tournaments for the configured sport. Useful to find Peru tournament IDs."""
        if not self.api_key:
            return []
        try:
            return self._as_list(self._request("tournaments", {"sportId": self.sport_id, "language": self.language}))
        except httpx.HTTPError:
            return []

    def get_fixtures(self) -> List[Dict[str, Any]]:
        """Fetch upcoming fixtures with odds for configured bookmakers."""
        if not self.api_key:
            return []
        try:
            return self._fetch_limited_fixtures()
        except httpx.HTTPError:
            return []

    def get_provider_status(self) -> Dict[str, Any]:
        """Return safe local diagnostic details for the last OddsPapi refresh."""
        return {
            **self.last_status,
            "configured": bool(self.api_key),
            "api_url": self.api_url,
            "sport_id": self.sport_id,
            "bookmakers": self.bookmakers,
            "language": self.language,
            "odds_format": self.odds_format,
            "use_tournaments": self.use_tournaments,
            "tournament_ids": self.tournament_ids,
            "fixture_days": self.fixture_days,
            "max_fixtures": self.max_fixtures,
        }

    def _get_odds_by_limited_fixtures(self) -> List[Dict[str, Any]]:
        """
        Correct OddsPapi fallback flow.

        /v4/odds requires fixtureId, so first fetch upcoming fixtures and then
        request odds for a small configurable number of fixture IDs.
        """
        fixtures = self._fetch_limited_fixtures()
        self.last_status["fixtures_found"] = len(fixtures)
        selected = fixtures[: self.max_fixtures]
        self.last_status["fixtures_requested_for_odds"] = len(selected)

        odds_responses = []
        for fixture in selected:
            fixture_id = fixture.get("fixtureId")
            if not fixture_id:
                self._increment_discard("fixture_without_fixtureId")
                continue
            odds_data = self._request(
                "odds",
                {
                    "fixtureId": fixture_id,
                    "bookmakers": self.bookmakers,
                    "language": self.language,
                    "oddsFormat": self.odds_format,
                    "verbosity": 3,
                },
            )
            odds_responses.append(odds_data)

        return odds_responses

    def _fetch_limited_fixtures(self) -> List[Dict[str, Any]]:
        """Fetch upcoming fixtures using the documented /v4/fixtures filters."""
        now = datetime.now(timezone.utc)
        later = now + timedelta(days=max(self.fixture_days, 1))
        raw = self._request(
            "fixtures",
            {
                "sportId": self.sport_id,
                "from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": later.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "statusId": 0,
                "hasOdds": "true",
                "bookmakers": self.bookmakers,
                "language": self.language,
            },
        )
        return self._as_list(raw)
        try:
            return self._as_list(self._request("bookmakers", {}))
        except httpx.HTTPError:
            return []

    def _request(self, endpoint: str, params: Dict[str, Any]) -> Any:
        """Make an authenticated OddsPapi request and raise for HTTP errors."""
        request_params = {**params, "apiKey": self.api_key}
        response = httpx.get(f"{self.api_url}/{endpoint.lstrip('/')}", params=request_params, timeout=20.0)
        response.raise_for_status()
        return response.json()

    def _normalize_oddspapi_response(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Convert OddsPapi odds response to the internal event format."""
        fixtures = self._extract_fixtures(raw_data)
        self.last_status["raw_response_type"] = type(raw_data).__name__
        self.last_status["raw_fixtures_received"] = len(fixtures)
        events: List[Dict[str, Any]] = []

        for fixture in fixtures:
            base = self._fixture_base(fixture)
            grouped_bookmakers: Dict[str, Dict[str, Any]] = {}
            if not fixture.get("bookmakerOdds"):
                self._increment_discard("fixture_without_bookmakerOdds")

            for bookmaker_slug, bookmaker_data in fixture.get("bookmakerOdds", {}).items():
                if not isinstance(bookmaker_data, dict):
                    self._increment_discard("invalid_bookmaker_node")
                    continue
                if bookmaker_data.get("bookmakerIsActive") is False or bookmaker_data.get("suspended") is True:
                    self._increment_discard("inactive_or_suspended_bookmaker")
                    continue

                bookmaker_name = self._bookmaker_display_name(bookmaker_slug)
                markets = bookmaker_data.get("markets", {})
                if not markets:
                    self._increment_discard("bookmaker_without_markets")
                for market_data in markets.values():
                    if not isinstance(market_data, dict) or market_data.get("marketActive") is False:
                        self._increment_discard("inactive_or_invalid_market")
                        continue

                    market_name, odds = self._extract_market_odds(market_data)
                    if len(odds) < 2:
                        self._increment_discard("unsupported_or_incomplete_market")
                        continue

                    key = f"{base['event_id']}::{market_name}"
                    if key not in grouped_bookmakers:
                        grouped_bookmakers[key] = {
                            "event": {**base, "market": market_name, "bookmakers": []},
                            "bookmakers": [],
                        }
                    grouped_bookmakers[key]["bookmakers"].append(
                        {"name": bookmaker_name, "country": "Global", "odds": odds}
                    )

            for item in grouped_bookmakers.values():
                event = item["event"]
                event["event_id"] = f"{event['event_id']}_{self._slug(event['market'])}"
                event["bookmakers"] = item["bookmakers"]
                events.append(event)

        self.last_status["normalized_events"] = len(events)
        return events

    def _extract_market_odds(self, market_data: Dict[str, Any]) -> tuple[str, Dict[str, float]]:
        """Extract supported market odds from an OddsPapi market node."""
        odds: Dict[str, float] = {}
        raw_market_id = str(market_data.get("bookmakerMarketId", "")).lower()
        outcomes = market_data.get("outcomes", {})
        self._sample_market(raw_market_id, outcomes)

        for outcome_data in outcomes.values():
            player = self._first_active_player(outcome_data)
            if not player:
                continue
            price = player.get("price")
            if price is None or float(price) <= 1.0:
                continue

            selection = self._selection_key(player.get("bookmakerOutcomeId"), raw_market_id)
            if selection:
                odds[selection] = float(price)

        if {"home_win", "draw", "away_win"}.issubset(odds):
            return "1X2", odds
        if any(k.startswith("over_") for k in odds) and any(k.startswith("under_") for k in odds):
            if "corner" in raw_market_id:
                return "Corners Over/Under", odds
            return "Over/Under Goals", odds
        if {"home_win", "away_win"}.issubset(odds):
            return "Moneyline", odds
        return "Unsupported", {}

    def _first_active_player(self, outcome_data: Any) -> Optional[Dict[str, Any]]:
        """Return the first active player/price object for a standard market outcome."""
        if not isinstance(outcome_data, dict):
            return None
        players = outcome_data.get("players", {})
        if not isinstance(players, dict):
            return None
        for player in players.values():
            if isinstance(player, dict) and player.get("active") is not False:
                return player
        return None

    def _selection_key(self, bookmaker_outcome_id: Any, market_id: str) -> Optional[str]:
        """Map bookmaker outcome labels to internal analyzer selection keys."""
        label = str(bookmaker_outcome_id or "").strip().lower()
        if label in {"home", "1"}:
            return "home_win"
        if label in {"draw", "x"}:
            return "draw"
        if label in {"away", "2"}:
            return "away_win"

        normalized = label.replace("/", "_").replace(" ", "_")
        parts = [p for p in normalized.split("_") if p]
        if len(parts) >= 2:
            line = next((p for p in parts if self._is_number(p)), None)
            side = next((p for p in parts if p in {"over", "under"}), None)
            if line and side:
                return f"{side}_{line}"

        if "moneyline" in market_id:
            return None
        return None

    def _fixture_base(self, fixture: Dict[str, Any]) -> Dict[str, Any]:
        """Build common internal event fields from an OddsPapi fixture."""
        participants = fixture.get("participants", {}) if isinstance(fixture.get("participants"), dict) else {}
        home_name = fixture.get("participant1Name") or fixture.get("participant1ShortName")
        away_name = fixture.get("participant2Name") or fixture.get("participant2ShortName")
        home_name = home_name or participants.get("home", {}).get("name", "Home")
        away_name = away_name or participants.get("away", {}).get("name", "Away")

        return {
            "event_id": str(fixture.get("fixtureId") or fixture.get("id") or ""),
            "sport": fixture.get("sportName") or "Soccer",
            "league": fixture.get("tournamentName") or fixture.get("tournamentSlug") or "OddsPapi",
            "home_team": home_name,
            "away_team": away_name,
            "market": "1X2",
            "timestamp": fixture.get("startTime") or fixture.get("commence_time") or "",
        }

    def _extract_fixtures(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Support both documented array responses and wrapped {data: [...]} responses."""
        if isinstance(raw_data, list):
            return [item for item in raw_data if isinstance(item, dict)]
        if isinstance(raw_data, dict):
            data = raw_data.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                nested = data.get("fixtures") or data.get("odds") or data.get("events")
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]
            for key in ("fixtures", "odds", "events"):
                if isinstance(raw_data.get(key), list):
                    return [item for item in raw_data[key] if isinstance(item, dict)]
            if "fixtureId" in raw_data or "bookmakerOdds" in raw_data:
                return [raw_data]
        return []

    def _bookmaker_display_name(self, slug: str) -> str:
        """Make common Peru-facing bookmaker names readable while preserving slugs."""
        names = {
            "apuestatotal": "Apuesta Total",
            "betano.pe": "Betano PE",
            "inkabet": "Inkabet",
            "pinnacle": "Pinnacle",
        }
        return names.get(slug, slug)

    def _as_list(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Normalize list or wrapped-list API responses."""
        if isinstance(raw_data, list):
            return [item for item in raw_data if isinstance(item, dict)]
        if isinstance(raw_data, dict) and isinstance(raw_data.get("data"), list):
            return [item for item in raw_data["data"] if isinstance(item, dict)]
        return []

    def _is_number(self, value: str) -> bool:
        """Return True when a label token is a decimal line."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _slug(self, value: str) -> str:
        """Create a compact ASCII identifier from a market name."""
        return "_".join(value.lower().replace("/", " ").split())

    def _empty_status(self) -> Dict[str, Any]:
        """Build a fresh safe diagnostic status object."""
        return {
            "requested_at": None,
            "mode": "API",
            "endpoint": None,
            "error": None,
            "raw_response_type": None,
            "raw_fixtures_received": 0,
            "fixtures_found": 0,
            "fixtures_requested_for_odds": 0,
            "normalized_events": 0,
            "discard_reasons": {},
            "sample_markets": [],
        }

    def _increment_discard(self, reason: str) -> None:
        """Track why provider data was not converted to an internal event."""
        reasons = self.last_status.setdefault("discard_reasons", {})
        reasons[reason] = reasons.get(reason, 0) + 1

    def _sample_market(self, market_id: str, outcomes: Any) -> None:
        """Store a small safe sample of market ids and outcome labels for debugging."""
        samples = self.last_status.setdefault("sample_markets", [])
        if len(samples) >= 8 or not isinstance(outcomes, dict):
            return

        labels = []
        for outcome_data in outcomes.values():
            player = self._first_active_player(outcome_data)
            if player:
                labels.append(str(player.get("bookmakerOutcomeId")))
            if len(labels) >= 4:
                break
        samples.append({"bookmakerMarketId": market_id, "outcome_labels": labels})
