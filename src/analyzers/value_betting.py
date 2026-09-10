from typing import List, Dict, Any
from src.calculators.probability import ProbabilityCalculator
from src.calculators.roi import ROICalculator
from src.calculators.stakes import StakeCalculator

class ValueBettingAnalyzer:
    """
    VALUE BETTING ANALYZER MODULE
    Compares model estimated probabilities against bookmaker market odds
    to identify positive expected value (EV) betting opportunities.
    """

    @staticmethod
    def analyze_event(
        event: Dict[str, Any],
        historical_matches: List[Dict[str, Any]],
        min_edge_percentage: float = 2.0,
        default_bankroll: float = 100.0
    ) -> List[Dict[str, Any]]:
        """
        Detect value bets for an event.
        Model estimates probability -> Fair odds = 1 / P.
        If Bookmaker Odds > Fair Odds => Value Bet exists.
        """
        opportunities = []
        bookmakers = event.get("bookmakers", [])
        if not bookmakers:
            return opportunities

        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        market = event.get("market", "1X2")

        # Estimate Poisson or empirical probabilities based on history
        model_probs = ValueBettingAnalyzer._estimate_model_probabilities(home_team, away_team, historical_matches)

        for bm in bookmakers:
            bm_name = bm.get("name", "Unknown")
            odds_dict = bm.get("odds", {})

            for selection, market_odds in odds_dict.items():
                if selection not in model_probs or market_odds <= 1.0:
                    continue

                prob = model_probs[selection]
                fair_odds = ProbabilityCalculator.calculate_fair_odds(prob)
                val_calc = ROICalculator.calculate_value_edge(prob, market_odds)

                if val_calc["is_value"] and val_calc["edge_percentage"] >= min_edge_percentage:
                    kelly_info = StakeCalculator.calculate_kelly_stake(
                        bankroll=default_bankroll,
                        model_probability=prob,
                        odds=market_odds,
                        fraction=0.25
                    )

                    opp_id = f"value_{event['event_id']}_{bm_name.replace(' ', '_')}_{selection}"

                    opportunities.append({
                        "opportunity_id": opp_id,
                        "type": "valuebet",
                        "event_id": event["event_id"],
                        "sport": event["sport"],
                        "league": event["league"],
                        "home_team": home_team,
                        "away_team": away_team,
                        "market": market,
                        "roi": val_calc["edge_percentage"],
                        "probability": round(prob * 100, 2),
                        "timestamp": event.get("timestamp", ""),
                        "details": {
                            "selection": selection,
                            "bookmaker": bm_name,
                            "bookmaker_odds": market_odds,
                            "fair_odds": fair_odds,
                            "model_probability": round(prob * 100, 2),
                            "edge_percentage": val_calc["edge_percentage"],
                            "recommended_stake": kelly_info["recommended_stake"],
                            "kelly_fraction": kelly_info["kelly_fraction"]
                        }
                    })

        return opportunities

    @staticmethod
    def _estimate_model_probabilities(home_team: str, away_team: str, historical_matches: List[Dict[str, Any]]) -> Dict[str, float]:
        """Estimate model probabilities using historical Poisson match analysis"""
        home_goals = []
        away_goals = []

        for m in historical_matches:
            if m.get("home_team", "").lower() == home_team.lower():
                home_goals.append(m.get("home_goals", 1))
            if m.get("away_team", "").lower() == away_team.lower():
                away_goals.append(m.get("away_goals", 1))

        avg_home = (sum(home_goals) / len(home_goals)) if home_goals else 1.8
        avg_away = (sum(away_goals) / len(away_goals)) if away_goals else 1.2

        matrix = ProbabilityCalculator.poisson_goals_matrix(avg_home, avg_away)
        return {
            "home_win": matrix["home_win"],
            "draw": matrix["draw"],
            "away_win": matrix["away_win"],
            "over_2.5": matrix["over_2.5"],
            "under_2.5": matrix["under_2.5"]
        }
