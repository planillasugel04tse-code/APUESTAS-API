from typing import List, Dict, Any
from scipy.stats import poisson
import math
from src.statistics.corners import CornersStatistics
from src.calculators.roi import ROICalculator

class RangeStrategyAnalyzer:
    """
    RANGE STRATEGY ANALYZER MODULE
    Detects line gaps and overlaps across bookmakers for range-based markets
    (e.g., Corners Over/Under, Goals Total Lines).
    Calculates historical gap probabilities, risk levels, and expected ROI.
    """

    @staticmethod
    def analyze_event(
        event: Dict[str, Any],
        historical_matches: List[Dict[str, Any]],
        default_bankroll: float = 100.0
    ) -> List[Dict[str, Any]]:
        """
        Analyze line differences across bookmakers for gaps or coverage.
        Example:
          Bookmaker A: Under 7.0 @ 2.25
          Bookmaker B: Over 8.0 @ 2.35
          Gap outcomes: Exactly 7 or 8 corners.
        """
        opportunities = []
        bookmakers = event.get("bookmakers", [])
        if len(bookmakers) < 2:
            return opportunities

        market = event.get("market", "")
        if "range" not in market.lower() and "corners" not in market.lower() and "over/under" not in market.lower():
            return opportunities

        # Extract lines and odds from bookmakers
        lines_info = RangeStrategyAnalyzer._extract_lines(bookmakers)
        if len(lines_info) < 2:
            return opportunities

        home_stats = CornersStatistics.analyze_team_corners(historical_matches, event.get("home_team", ""))
        away_stats = CornersStatistics.analyze_team_corners(historical_matches, event.get("away_team", ""))
        expected_corners = CornersStatistics.calculate_match_expected_corners(home_stats, away_stats)

        # Compare pair of lines
        for i in range(len(lines_info)):
            for j in range(i + 1, len(lines_info)):
                bm_a = lines_info[i]
                bm_b = lines_info[j]

                # Compare Under line on A vs Over line on B
                if "under" in bm_a["selection"] and "over" in bm_b["selection"]:
                    opp = RangeStrategyAnalyzer._evaluate_range_pair(
                        event=event,
                        under_bm=bm_a,
                        over_bm=bm_b,
                        expected_corners=expected_corners,
                        default_bankroll=default_bankroll
                    )
                    if opp:
                        opportunities.append(opp)
                elif "under" in bm_b["selection"] and "over" in bm_a["selection"]:
                    opp = RangeStrategyAnalyzer._evaluate_range_pair(
                        event=event,
                        under_bm=bm_b,
                        over_bm=bm_a,
                        expected_corners=expected_corners,
                        default_bankroll=default_bankroll
                    )
                    if opp:
                        opportunities.append(opp)

        return opportunities

    @staticmethod
    def _extract_lines(bookmakers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract line threshold, outcome type, and odds from bookmakers"""
        extracted = []
        for bm in bookmakers:
            bm_name = bm.get("name", "Unknown")
            for sel, price in bm.get("odds", {}).items():
                parts = sel.lower().split("_")
                if len(parts) >= 2:
                    outcome_type = parts[0]  # 'under' or 'over'
                    try:
                        line_val = float(parts[1])
                        extracted.append({
                            "bookmaker": bm_name,
                            "selection": sel,
                            "type": outcome_type,
                            "line": line_val,
                            "odds": float(price)
                        })
                    except ValueError:
                        continue
        return extracted

    @staticmethod
    def _evaluate_range_pair(
        event: Dict[str, Any],
        under_bm: Dict[str, Any],
        over_bm: Dict[str, Any],
        expected_corners: float,
        default_bankroll: float
    ) -> Dict[str, Any]:
        """Evaluate a pair of Under and Over lines across bookmakers"""
        under_line = under_bm["line"]
        over_line = over_bm["line"]

        # Inverse sum for arbitrage check
        inv_sum = (1.0 / under_bm["odds"]) + (1.0 / over_bm["odds"])

        under_covered = RangeStrategyAnalyzer._covered_under_outcomes(under_line)
        over_covered = RangeStrategyAnalyzer._covered_over_outcomes(over_line)
        observable_outcomes = set(range(0, 41))
        gap_outcomes = sorted(observable_outcomes - under_covered - over_covered)
        gap_outcomes = [g for g in gap_outcomes if min(under_line, over_line) - 1 <= g <= max(under_line, over_line) + 1]

        if gap_outcomes:
            status = "Uncovered Gap"
            gap_prob = 0.0
            for g in gap_outcomes:
                gap_prob += float(poisson.pmf(g, expected_corners))
            risk_level = "High" if gap_prob > 0.25 else "Medium"
        elif under_line > over_line:
            status = "Middle Overlap (Double Win Possible)"
            gap_prob = 0.0
            risk_level = "Low (Positive Synergy)"
        else:
            status = "Fully Covered"
            gap_prob = 0.0
            risk_level = "Low"

        # Expected ROI estimation
        raw_roi = round(((1.0 / inv_sum) - 1.0) * 100, 2)
        adjusted_roi = round(raw_roi - (gap_prob * 100), 2)

        if under_bm["bookmaker"] == over_bm["bookmaker"]:
            return None

        opp_id = f"range_{event['event_id']}_{under_bm['bookmaker']}_{over_bm['bookmaker']}"

        return {
            "opportunity_id": opp_id,
            "type": "range",
            "event_id": event["event_id"],
            "sport": event["sport"],
            "league": event["league"],
            "home_team": event["home_team"],
            "away_team": event["away_team"],
            "market": event["market"],
            "roi": adjusted_roi,
            "probability": round((1.0 - gap_prob) * 100, 2),
            "timestamp": event.get("timestamp", ""),
            "details": {
                "status": status,
                "under_leg": {
                    "bookmaker": under_bm["bookmaker"],
                    "line": under_line,
                    "odds": under_bm["odds"]
                },
                "over_leg": {
                    "bookmaker": over_bm["bookmaker"],
                    "line": over_line,
                    "odds": over_bm["odds"]
                },
                "gap_outcomes": gap_outcomes,
                "gap_probability_percentage": round(gap_prob * 100, 2),
                "risk_level": risk_level,
                "raw_roi": raw_roi,
                "expected_corners": expected_corners
            }
        }

    @staticmethod
    def _covered_under_outcomes(line: float) -> set[int]:
        """Return integer outcomes covered by an under selection."""
        if line.is_integer():
            return set(range(0, int(line)))
        return set(range(0, math.floor(line) + 1))

    @staticmethod
    def _covered_over_outcomes(line: float) -> set[int]:
        """Return integer outcomes covered by an over selection."""
        if line.is_integer():
            return set(range(int(line) + 1, 41))
        return set(range(math.floor(line) + 1, 41))
