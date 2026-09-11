"""Tests for the Final Selector: acceptance criteria, rejection reasons and action labels."""
from betano_analyzer.final_selector import build_final_selection, _rejection_reason


# ---------------------------------------------------------------------------
# Rejection reason unit tests
# ---------------------------------------------------------------------------

def test_rejection_reason_low_score():
    reason = _rejection_reason(
        score=50.0, edge=0.05, ev=0.05, probability=0.60,
        has_fusion=True, books=3, positive=3,
    )
    assert "master_score" in reason
    assert "50.0" in reason


def test_rejection_reason_low_edge():
    reason = _rejection_reason(
        score=75.0, edge=0.01, ev=0.05, probability=0.60,
        has_fusion=True, books=3, positive=3,
    )
    assert "edge" in reason


def test_rejection_reason_low_books():
    reason = _rejection_reason(
        score=75.0, edge=0.05, ev=0.05, probability=0.60,
        has_fusion=True, books=1, positive=3,
    )
    assert "bookmakers" in reason


def test_rejection_reason_insufficient_signals():
    reason = _rejection_reason(
        score=75.0, edge=0.05, ev=0.05, probability=0.60,
        has_fusion=True, books=3, positive=1,
    )
    assert "positive_signals" in reason


def test_rejection_reason_low_probability():
    reason = _rejection_reason(
        score=75.0, edge=0.05, ev=0.05, probability=0.40,
        has_fusion=True, books=3, positive=3,
    )
    assert "fused_probability" in reason


def test_rejection_reason_multiple_failures():
    reason = _rejection_reason(
        score=40.0, edge=0.01, ev=0.01, probability=0.30,
        has_fusion=True, books=1, positive=0,
    )
    # All criteria fail → reason includes multiple parts
    assert ";" in reason


# ---------------------------------------------------------------------------
# Selection pipeline tests (via monkeypatched master_radar)
# ---------------------------------------------------------------------------

def test_final_selector_empty_when_no_candidates(monkeypatch):
    monkeypatch.setattr(
        "betano_analyzer.final_selector.build_master_radar",
        lambda limit=100: {"opportunities": []},
    )
    result = build_final_selection(10)
    assert result["status"] == "NO_BET"
    assert result["count"] == 0
    assert result["rejected_count"] == 0


def test_final_selector_does_not_fill_weak_slots(monkeypatch):
    weak = {
        "match_id": 1,
        "market": "goals",
        "selection": "over 2.5",
        "line": 2.5,
        "master_score": 72,
        "fused_edge": 0.04,
        "fused_ev": 0.04,
        "fused_probability": 0.55,
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
    assert result["opportunities"][0]["rejection_reason"] is None


def test_final_selector_rejects_low_score(monkeypatch):
    low = {
        "match_id": 2,
        "market": "1x2_ft",
        "selection": "home",
        "line": None,
        "master_score": 40.0,   # below 68
        "fused_edge": 0.05,
        "fused_ev": 0.05,
        "fused_probability": 0.60,
        "bookmakers": 3,
        "signals": {"value": True, "consensus": True, "model": True},
    }
    monkeypatch.setattr(
        "betano_analyzer.final_selector.build_master_radar",
        lambda limit=100: {"opportunities": [low]},
    )
    result = build_final_selection(10)
    assert result["count"] == 0
    assert result["status"] == "NO_BET"
    assert result["rejected_count"] == 1
    assert "master_score" in result["rejected"][0]["rejection_reason"]


def test_final_selector_apostar_action_requires_high_thresholds(monkeypatch):
    strong = {
        "match_id": 3,
        "market": "goals_ft",
        "selection": "over",
        "line": 2.5,
        "master_score": 85.0,
        "fused_edge": 0.06,
        "fused_ev": 0.06,
        "fused_probability": 0.62,
        "bookmakers": 5,
        "signals": {
            "value": True, "consensus": True, "model": True,
            "fusion": True, "movement": True, "history": True,
        },
    }
    monkeypatch.setattr(
        "betano_analyzer.final_selector.build_master_radar",
        lambda limit=100: {"opportunities": [strong]},
    )
    result = build_final_selection(10)
    assert result["count"] == 1
    assert result["opportunities"][0]["action"] == "APOSTAR"


def test_final_selector_rejected_list_is_populated(monkeypatch):
    """The rejected[] list must include all non-qualifying candidates with their reasons."""
    candidates = [
        {
            "match_id": i,
            "market": "1x2_ft",
            "selection": "home",
            "line": None,
            "master_score": 30.0,   # all fail
            "fused_edge": 0.01,
            "fused_ev": 0.01,
            "fused_probability": 0.30,
            "bookmakers": 1,
            "signals": {},
        }
        for i in range(5)
    ]
    monkeypatch.setattr(
        "betano_analyzer.final_selector.build_master_radar",
        lambda limit=100: {"opportunities": candidates},
    )
    result = build_final_selection(10)
    assert result["count"] == 0
    assert result["rejected_count"] == 5
    assert all("rejection_reason" in r for r in result["rejected"])
    assert all(r["action"] == "DESCARTADO" for r in result["rejected"])
