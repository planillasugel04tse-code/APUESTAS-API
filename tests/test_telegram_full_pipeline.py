from __future__ import annotations

from types import SimpleNamespace

from betano_analyzer.telegram import full_pipeline


class _FakeDb:
    def __init__(self):
        self.analysis = '{"status":"success"}'
        self.updated = None

    def execute(self, sql, params=()):
        if sql.startswith("SELECT analysis_result"):
            return self
        if sql.startswith("UPDATE telegram_signals"):
            self.updated = params
            return self
        raise AssertionError(f"unexpected SQL: {sql}")

    def fetchone(self):
        return {"analysis_result": self.analysis}

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_process_telegram_signal_full_runs_canonical_enrichment(monkeypatch):
    parsed = SimpleNamespace(
        is_valid=True,
        tipster="TestTipster",
        home_team="Home",
        away_team="Away",
        market="goals",
        selection="Over 1.5",
        odds=1.70,
        line=1.5,
        sport="football",
        competition="Test League",
        published_at=None,
        confidence=0.8,
    )
    serialized = {"analysis": {"status": "VALUE"}, "market": {}, "statistics": {}}
    db = _FakeDb()

    monkeypatch.setattr(
        full_pipeline,
        "process_telegram_signal",
        lambda *args, **kwargs: {
            "status": "success",
            "signal_id": "tg-test",
            "match_id": 7,
            "analysis": {},
        },
    )
    monkeypatch.setattr(full_pipeline, "parse_telegram_message", lambda *args, **kwargs: parsed)
    monkeypatch.setattr(full_pipeline, "enrich_tipster_pick", lambda *args, **kwargs: object())
    monkeypatch.setattr(full_pipeline, "serialize_enriched", lambda result: serialized)
    monkeypatch.setattr(full_pipeline, "connect", lambda: db)

    result = full_pipeline.process_telegram_signal_full(
        "Home vs Away Over 1.5 @1.70",
        channel="test_channel",
        message_id="1",
    )

    assert result["analysis"]["tipster_pipeline"] == serialized
    assert db.updated is not None
    assert "tipster_pipeline" in db.updated[0]


def test_process_telegram_signal_full_leaves_pending_signal_untouched(monkeypatch):
    monkeypatch.setattr(
        full_pipeline,
        "process_telegram_signal",
        lambda *args, **kwargs: {"status": "pending_match", "signal_id": "tg-pending"},
    )
    called = {"enrich": False}
    monkeypatch.setattr(
        full_pipeline,
        "enrich_tipster_pick",
        lambda *args, **kwargs: called.__setitem__("enrich", True),
    )

    result = full_pipeline.process_telegram_signal_full(
        "Home vs Away Over 1.5 @1.70",
        channel="test_channel",
        message_id="2",
    )

    assert result["status"] == "pending_match"
    assert called["enrich"] is False
