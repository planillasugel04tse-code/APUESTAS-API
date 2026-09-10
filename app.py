from flask import Flask, render_template, request, jsonify
from pydantic import ValidationError
from src.config import config
from src.services import service
from src.database import db
from src.calculators.stakes import StakeCalculator
from src.calculators.roi import ROICalculator
from src.statistics.goals import GoalsStatistics
from src.statistics.corners import CornersStatistics
from src.models import CalculationRequest

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY

# Prime database with initial demo opportunities on startup. In API mode the
# user must refresh manually to preserve the monthly request quota.
if config.PROVIDER_MODE != "API":
    try:
        service.refresh_and_analyze_all()
    except Exception as e:
        print(f"Startup analysis warning: {e}")

# Mandatory Disclaimer text required across all views/footers
DISCLAIMER = (
    "Los cálculos son estimaciones matemáticas. Las cuotas pueden cambiar, "
    "existir límites de apuesta y variar las reglas de liquidación de cada operador."
)

@app.context_processor
def inject_global_vars():
    """Inject global variables to all Jinja2 templates"""
    return {
        "disclaimer": DISCLAIMER,
        "provider_mode": config.PROVIDER_MODE
    }

# ==========================================
# WEB VIEW ROUTES
# ==========================================

@app.route("/")
def dashboard():
    """Main Dashboard View"""
    report = service.refresh_and_analyze_all() if config.PROVIDER_MODE != "API" else service.get_summary()
    opps = service.get_filtered_opportunities()
    
    top_opportunity = opps[0] if opps else None
    avg_roi = round(sum(o["roi"] for o in opps) / len(opps), 2) if opps else 0.0

    return render_template(
        "dashboard.html",
        summary=report,
        top_opportunity=top_opportunity,
        avg_roi=avg_roi,
        opportunities=opps[:5]
    )

@app.route("/opportunities")
def opportunities():
    """All Detected Opportunities View"""
    sport = request.args.get("sport", "all")
    min_roi = request.args.get("min_roi", type=float)
    bookmaker = request.args.get("bookmaker", "all")

    opps = service.get_filtered_opportunities(sport=sport, min_roi=min_roi, bookmaker=bookmaker)
    return render_template("opportunities.html", opportunities=opps)

@app.route("/surebets")
def surebets():
    """Surebet Analyzer Dedicated View"""
    surebets_list = service.get_filtered_opportunities(opp_type="surebet")
    return render_template("surebets.html", opportunities=surebets_list)

@app.route("/valuebets")
def valuebets():
    """Value Betting Dedicated View"""
    valuebets_list = service.get_filtered_opportunities(opp_type="valuebet")
    return render_template("valuebets.html", opportunities=valuebets_list)

@app.route("/range")
def range_strategy():
    """Range Strategy Dedicated View"""
    range_list = service.get_filtered_opportunities(opp_type="range")
    return render_template("range.html", opportunities=range_list)

@app.route("/odds")
def odds_view():
    """Stored odds/events view for provider diagnostics."""
    events = db.get_events()
    return render_template("odds.html", events=events, provider_status=service.get_provider_status())

@app.route("/history")
def history():
    """History and Simulations View"""
    history_logs = db.get_history()
    return render_template("history.html", history=history_logs)

@app.route("/settings")
def settings():
    """System Settings View"""
    return render_template("settings.html", config=config)

# ==========================================
# LOCAL API ENDPOINTS
# ==========================================

@app.route("/api/events", methods=["GET"])
def api_events():
    """Get all events from provider"""
    events = service.provider.get_events() if config.PROVIDER_MODE != "API" else db.get_events()
    if config.PROVIDER_MODE == "API":
        return jsonify({
            "success": True,
            "message": "API mode uses /api/refresh to fetch real odds and preserve quota.",
            "count": len(events),
            "events": events
        })
    return jsonify({"success": True, "count": len(events), "events": events})

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Fetch provider data, analyze all modules, and store the fresh snapshot."""
    if config.PROVIDER_MODE == "API" and not config.EXTERNAL_API_KEY:
        return jsonify({"success": False, "error": "EXTERNAL_API_KEY is required when PROVIDER_MODE=API"}), 400
    report = service.refresh_and_analyze_all()
    return jsonify({"success": True, "provider_mode": config.PROVIDER_MODE, "report": report})

@app.route("/api/account", methods=["GET"])
def api_account():
    """Get safe account/quota details from the active API provider."""
    if not hasattr(service.provider, "get_account"):
        return jsonify({"success": False, "error": "Account endpoint is only available in API mode"}), 400
    return jsonify({"success": True, "account": service.provider.get_account()})

@app.route("/api/bookmakers", methods=["GET"])
def api_bookmakers():
    """Get available bookmakers from the active API provider."""
    if not hasattr(service.provider, "get_bookmakers"):
        return jsonify({"success": False, "error": "Bookmakers endpoint is only available in API mode"}), 400
    bookmakers = service.provider.get_bookmakers()
    return jsonify({"success": True, "count": len(bookmakers), "bookmakers": bookmakers})

@app.route("/api/tournaments", methods=["GET"])
def api_tournaments():
    """Get OddsPapi tournaments for the configured sport."""
    if not hasattr(service.provider, "get_tournaments"):
        return jsonify({"success": False, "error": "Tournaments endpoint is only available in API mode"}), 400
    tournaments = service.provider.get_tournaments()
    query = request.args.get("q", "").lower().strip()
    if query:
        tournaments = [
            t for t in tournaments
            if query in str(t.get("tournamentName", "")).lower()
            or query in str(t.get("tournamentSlug", "")).lower()
            or query in str(t.get("categoryName", "")).lower()
            or query in str(t.get("categorySlug", "")).lower()
        ]
    return jsonify({"success": True, "count": len(tournaments), "tournaments": tournaments})

@app.route("/api/fixtures", methods=["GET"])
def api_fixtures():
    """Get upcoming OddsPapi fixtures for configured bookmakers."""
    if not hasattr(service.provider, "get_fixtures"):
        return jsonify({"success": False, "error": "Fixtures endpoint is only available in API mode"}), 400
    fixtures = service.provider.get_fixtures()
    return jsonify({"success": True, "count": len(fixtures), "fixtures": fixtures})

@app.route("/api/provider/status", methods=["GET"])
def api_provider_status():
    """Return safe diagnostics about the current provider and last refresh."""
    return jsonify({"success": True, "status": service.get_provider_status()})

@app.route("/api/opportunities", methods=["GET"])
def api_opportunities():
    """Get all analyzed opportunities with optional filters"""
    opp_type = request.args.get("type")
    sport = request.args.get("sport")
    min_roi = request.args.get("min_roi", type=float)
    bookmaker = request.args.get("bookmaker")

    opps = service.get_filtered_opportunities(
        opp_type=opp_type, sport=sport, min_roi=min_roi, bookmaker=bookmaker
    )
    return jsonify({"success": True, "count": len(opps), "opportunities": opps})

@app.route("/api/surebets", methods=["GET"])
def api_surebets():
    """Get active Surebets"""
    opps = service.get_filtered_opportunities(opp_type="surebet")
    return jsonify({"success": True, "count": len(opps), "surebets": opps})

@app.route("/api/valuebets", methods=["GET"])
def api_valuebets():
    """Get active Value Bets"""
    opps = service.get_filtered_opportunities(opp_type="valuebet")
    return jsonify({"success": True, "count": len(opps), "valuebets": opps})

@app.route("/api/ranges", methods=["GET"])
def api_ranges():
    """Get active Range Strategy opportunities"""
    opps = service.get_filtered_opportunities(opp_type="range")
    return jsonify({"success": True, "count": len(opps), "ranges": opps})

@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    """
    Calculator Endpoint for custom stake/ROI simulations
    Body format:
    {
      "bankroll": 500,
      "odds": [2.15, 3.40, 3.60],
      "type": "surebet"
    }
    """
    data = request.get_json() or {}
    try:
        calc_request = CalculationRequest(**data)
    except ValidationError as exc:
        return jsonify({"success": False, "error": "Invalid calculation request", "details": exc.errors()}), 400

    bankroll = float(calc_request.bankroll)
    odds = [float(o) for o in calc_request.odds]
    calc_type = calc_request.type

    if not odds or any(float(o) <= 1.0 for o in odds):
        return jsonify({"success": False, "error": "Invalid odds provided. Odds must be > 1.0"}), 400

    if calc_type == "surebet":
        res = StakeCalculator.calculate_surebet_stakes(bankroll, odds)
        res["currency"] = "S/"
        return jsonify({"success": True, "result": res})
    elif calc_type == "valuebet":
        model_prob = float(data.get("model_probability", 0.5))
        if model_prob <= 0.0 or model_prob >= 1.0:
            return jsonify({"success": False, "error": "model_probability must be between 0 and 1"}), 400
        bookmaker_odds = odds[0]
        val_res = ROICalculator.calculate_value_edge(model_prob, bookmaker_odds)
        kelly_res = StakeCalculator.calculate_kelly_stake(bankroll, model_prob, bookmaker_odds)
        return jsonify({"success": True, "currency": "S/", "value_analysis": val_res, "stake_analysis": kelly_res})

    return jsonify({"success": False, "error": "Unsupported calculation type"}), 400

@app.route("/api/statistics", methods=["GET"])
def api_statistics():
    """Get team statistics endpoint"""
    team_name = request.args.get("team", "Arsenal")
    if hasattr(service.provider, "get_all_historical_matches"):
        matches = service.provider.get_all_historical_matches()
        goals_stat = GoalsStatistics.analyze_team_goals(matches, team_name)
        corners_stat = CornersStatistics.analyze_team_corners(matches, team_name)
        return jsonify({"success": True, "goals": goals_stat, "corners": corners_stat})
    return jsonify({"success": False, "error": "Statistics not available in current provider mode"})


@app.route("/api/telegram/signals", methods=["GET"])
def api_telegram_signals():
    """Get all processed Telegram signals with analysis results."""
    signals = db.get_telegram_signals()
    return jsonify({"success": True, "count": len(signals), "signals": signals})

@app.route("/api/telegram/message", methods=["POST"])
def api_telegram_message():
    """
    Ingest and process a raw Telegram message text through end-to-end pipeline:
    Telegram message -> Parser -> Betano matching -> Odds consultation -> EV Analysis -> SQLite
    Body format:
    {
        "raw_text": "Real Madrid vs Barcelona\nGana Local @ 1.85\nStake 3/10",
        "channel": "@TeleBetVIP",
        "message_id": "optional-id",
        "tipster": "optional-tipster"
    }
    """
    data = request.get_json() or {}
    raw_text = data.get("raw_text")
    if not raw_text:
        return jsonify({"success": False, "error": "raw_text is required"}), 400

    channel = data.get("channel", "@TeleBetChannel")
    message_id = data.get("message_id")
    tipster = data.get("tipster")

    from src.telegram.pipeline import process_telegram_message
    result = process_telegram_message(
        raw_text=raw_text,
        channel=channel,
        message_id=message_id,
        tipster_name=tipster
    )
    return jsonify({"success": True, "result": result})



@app.route("/api/telegram/backtest", methods=["GET"])
def api_telegram_backtest():
    """
    Run backtest analysis on historical Telegram signals against historical match data.
    Uses PerformanceTrends.evaluate_signals_backtest engine.
    """
    signals = db.get_telegram_signals()
    historical_matches = service.provider.get_all_historical_matches() if hasattr(service.provider, "get_all_historical_matches") else []
    
    from src.statistics.trends import PerformanceTrends
    report = PerformanceTrends.evaluate_signals_backtest(signals, historical_matches)
    return jsonify({"success": True, "report": report})


if __name__ == "__main__":
    # Run application on local server
    print("=" * 60)
    print(f"  BETTING OPPORTUNITY ANALYZER - Running in {config.PROVIDER_MODE} mode")
    print("  Access local server at http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="127.0.0.1", port=config.PORT, debug=config.FLASK_DEBUG)
