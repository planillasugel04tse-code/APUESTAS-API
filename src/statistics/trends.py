from typing import List, Dict, Any

class PerformanceTrends:
    """Analyzes performance trends across historical matches"""

    @staticmethod
    def calculate_recent_form(historical_matches: List[Dict[str, Any]], team_name: str, matches_count: int = 5) -> Dict[str, Any]:
        """Compute form stats for the last N matches"""
        team_matches = [
            m for m in historical_matches
            if m.get("home_team", "").lower() == team_name.lower() or m.get("away_team", "").lower() == team_name.lower()
        ]
        
        recent = team_matches[-matches_count:] if len(team_matches) >= matches_count else team_matches
        
        if not recent:
            return {"team": team_name, "wins": 0, "draws": 0, "losses": 0, "form_string": "N/A"}

        wins = 0
        draws = 0
        losses = 0
        form_seq = []

        for m in recent:
            is_home = m.get("home_team", "").lower() == team_name.lower()
            h_goals = m.get("home_goals", 0)
            a_goals = m.get("away_goals", 0)

            if h_goals == a_goals:
                draws += 1
                form_seq.append("D")
            elif (is_home and h_goals > a_goals) or (not is_home and a_goals > h_goals):
                wins += 1
                form_seq.append("W")
            else:
                losses += 1
                form_seq.append("L")

        return {
            "team": team_name,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "form_string": "".join(form_seq)
        }


    @staticmethod
    def evaluate_signals_backtest(signals: List[Dict[str, Any]], historical_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Backtest historical Telegram signals against actual historical match results.
        Calculates settled win/loss, hit rate %, total profit, and ROI %.
        """
        if not signals or not historical_matches:
            return {
                "total_signals": len(signals) if signals else 0,
                "settled_signals": 0,
                "wins": 0,
                "losses": 0,
                "hit_rate_percentage": 0.0,
                "total_staked": 0.0,
                "total_payout": 0.0,
                "profit": 0.0,
                "roi_percentage": 0.0,
                "details": []
            }

        total_staked = 0.0
        total_payout = 0.0
        wins = 0
        losses = 0
        details = []

        for sig in signals:
            home = sig.get("home_team", "").lower()
            away = sig.get("away_team", "").lower()
            m_found = next((m for m in historical_matches if m.get("home_team", "").lower() == home and m.get("away_team", "").lower() == away), None)

            if not m_found:
                continue

            h_goals = m_found.get("home_goals", 0)
            a_goals = m_found.get("away_goals", 0)
            market = sig.get("market", "1x2").lower()
            selection = str(sig.get("selection", "1")).lower()
            odds = float(sig.get("betano_current_odds") or sig.get("tipster_odds", 1.0))
            stake = float(sig.get("stake", 1.0))

            won = False
            if market == "1x2":
                if selection in ("1", "home_win") and h_goals > a_goals: won = True
                elif selection in ("x", "draw") and h_goals == a_goals: won = True
                elif selection in ("2", "away_win") and a_goals > h_goals: won = True
            elif market == "goals":
                tot = h_goals + a_goals
                if "over 2.5" in selection and tot > 2.5: won = True
                elif "under 2.5" in selection and tot < 2.5: won = True
            elif market == "btts":
                if selection in ("yes", "si") and h_goals > 0 and a_goals > 0: won = True
                elif selection in ("no", "falso") and (h_goals == 0 or a_goals == 0): won = True

            total_staked += stake
            if won:
                wins += 1
                payout = stake * odds
                total_payout += payout
                details.append({"signal_id": sig.get("signal_id"), "result": "WON", "stake": stake, "payout": payout, "profit": payout - stake})
            else:
                losses += 1
                details.append({"signal_id": sig.get("signal_id"), "result": "LOST", "stake": stake, "payout": 0.0, "profit": -stake})

        settled = wins + losses
        profit = total_payout - total_staked
        hit_rate = round((wins / settled) * 100, 2) if settled > 0 else 0.0
        roi = round((profit / total_staked) * 100, 2) if total_staked > 0 else 0.0

        return {
            "total_signals": len(signals),
            "settled_signals": settled,
            "wins": wins,
            "losses": losses,
            "hit_rate_percentage": hit_rate,
            "total_staked": round(total_staked, 2),
            "total_payout": round(total_payout, 2),
            "profit": round(profit, 2),
            "roi_percentage": roi,
            "details": details
        }
