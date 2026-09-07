from betano_analyzer.final_selector import build_final_selection


def test_final_selector_empty_when_no_candidates(monkeypatch):
    monkeypatch.setattr(
        "betano_analyzer.final_selector.build_master_radar",
        lambda limit=100: {"opportunities": []},
    )
    result = build_final_selection(10)
    assert result["status"] == "NO_BET"
    assert result["count"] == 0


def test_final_selector_does_not_fill_weak_slots(monkeypatch):
    weak = {
        "match_id": 1,
        "market": "goals",
        "selection": "over 2.5",
        "line": 2.5,
        "master_score": 72,
        "edge": 0.04,
        "ev": 0.04,
        "bookmakers": 2,
        "signals": {"value": True, "consensus": True, "model": False},
    }
    monkeypatch.setattr(
        "betano_analyzer.final_selector.build_master_radar",
        lambda limit=100: {"opportunities": [weak]},
    )
    result = build_final_selection(10)
    assert result["count"] == 1
    assert result["opportunities"][0]["action"] == "VIGILAR"
