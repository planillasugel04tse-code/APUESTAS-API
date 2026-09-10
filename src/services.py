from typing import List, Dict, Any, Optional
from src.config import config
from src.database import db
from src.providers.demo_provider import DemoProvider
from src.providers.api_provider import APIProvider
from src.analyzers.surebet import SurebetAnalyzer
from src.analyzers.value_betting import ValueBettingAnalyzer
from src.analyzers.range_strategy import RangeStrategyAnalyzer

class OpportunityService:
    """Orchestrates Providers, Analyzers, and SQLite Data persistence"""

    def __init__(self):
        self.provider_mode = config.PROVIDER_MODE
        if self.provider_mode == "API":
            self.provider = APIProvider()
        else:
            self.provider = DemoProvider()

    def refresh_and_analyze_all(self, bankroll: float = 100.0) -> Dict[str, Any]:
        """
        Fetch events from active provider, run all analyzers,
        store in SQLite, and return consolidated report.
        """
        events = self.provider.get_events()
        if not events:
            if self.provider_mode == "API":
                db.clear_snapshot()
            return {
                "total_events": 0,
                "total_opportunities": 0,
                "surebets_count": 0,
                "valuebets_count": 0,
                "ranges_count": 0,
                "opportunities": [],
                "provider_status": self.get_provider_status()
            }

        # Save events to database. API mode replaces the whole snapshot so old
        # demo rows never hide a failed or empty real refresh.
        if self.provider_mode == "API":
            db.replace_events(events)
        else:
            db.save_events(events)

        historical_matches = []
        if isinstance(self.provider, DemoProvider):
            historical_matches = self.provider.get_all_historical_matches()

        all_opportunities: List[Dict[str, Any]] = []

        # Run analyzers for each event
        for event in events:
            # 1. Surebet Analyzer
            surebets = SurebetAnalyzer.analyze_event(event, default_bankroll=bankroll)
            all_opportunities.extend(surebets)

            # 2. Value Betting Analyzer
            valuebets = ValueBettingAnalyzer.analyze_event(
                event=event,
                historical_matches=historical_matches,
                min_edge_percentage=1.0,
                default_bankroll=bankroll
            )
            all_opportunities.extend(valuebets)

            # 3. Range Strategy Analyzer
            ranges = RangeStrategyAnalyzer.analyze_event(
                event=event,
                historical_matches=historical_matches,
                default_bankroll=bankroll
            )
            all_opportunities.extend(ranges)

        # Persist a fresh opportunity snapshot to avoid stale or duplicated rows.
        db.replace_opportunities(all_opportunities)

        surebet_count = len([o for o in all_opportunities if o["type"] == "surebet"])
        valuebet_count = len([o for o in all_opportunities if o["type"] == "valuebet"])
        range_count = len([o for o in all_opportunities if o["type"] == "range"])

        return {
            "total_events": len(events),
            "total_opportunities": len(all_opportunities),
            "surebets_count": surebet_count,
            "valuebets_count": valuebet_count,
            "ranges_count": range_count,
            "opportunities": all_opportunities,
            "provider_status": self.get_provider_status()
        }

    def get_filtered_opportunities(
        self,
        opp_type: Optional[str] = None,
        sport: Optional[str] = None,
        min_roi: Optional[float] = None,
        bookmaker: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve and filter opportunities from SQLite database"""
        opportunities = db.get_opportunities(opp_type=opp_type)
        if not opportunities and self.provider_mode != "API":
            self.refresh_and_analyze_all()
            opportunities = db.get_opportunities(opp_type=opp_type)

        filtered = []
        for opp in opportunities:
            if sport and sport.lower() != "all" and opp["sport"].lower() != sport.lower():
                continue
            if min_roi is not None and opp["roi"] < min_roi:
                continue
            if bookmaker and bookmaker.lower() != "all":
                details = opp.get("details", {})
                legs = details.get("legs", [])
                bm_match = any(bm.get("bookmaker", "").lower() == bookmaker.lower() for bm in legs)
                if not bm_match and details.get("bookmaker", "").lower() != bookmaker.lower():
                    continue
            filtered.append(opp)
        return filtered

    def get_summary(self) -> Dict[str, Any]:
        """Build a dashboard summary from the current SQLite snapshot."""
        opportunities = db.get_opportunities()
        return {
            "total_events": db.count_events(),
            "total_opportunities": len(opportunities),
            "surebets_count": len([o for o in opportunities if o["type"] == "surebet"]),
            "valuebets_count": len([o for o in opportunities if o["type"] == "valuebet"]),
            "ranges_count": len([o for o in opportunities if o["type"] == "range"]),
            "opportunities": opportunities,
            "provider_status": self.get_provider_status(),
        }

    def get_provider_status(self) -> Dict[str, Any]:
        """Return provider diagnostics when supported."""
        if hasattr(self.provider, "get_provider_status"):
            return self.provider.get_provider_status()
        return {"mode": self.provider_mode, "configured": True}

service = OpportunityService()
