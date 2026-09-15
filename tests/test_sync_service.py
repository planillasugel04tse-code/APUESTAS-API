"""Tests for sync_service: SyncSummary fields, _rematch_pending_telegram resilience."""
from __future__ import annotations

import pytest

from betano_analyzer.sync_service import SyncSummary, _rematch_pending_telegram


# ---------------------------------------------------------------------------
# SyncSummary fields
# ---------------------------------------------------------------------------

def test_sync_summary_fields_match_constructor():
    s = SyncSummary(leagues=5, matches_seen=10, matches_saved=3,
                    odds_seen=200, odds_saved=150,
                    live_matches_seen=2, live_matches_saved=2)
    assert s.leagues == 5
    assert s.matches_seen == 10
    assert s.matches_saved == 3
    assert s.odds_seen == 200
    assert s.odds_saved == 150
    assert s.live_matches_seen == 2
    assert s.live_matches_saved == 2


def test_sync_summary_defaults_for_live_fields():
    s = SyncSummary(8, 0, 0, 0, 0)
    assert s.live_matches_seen == 0
    assert s.live_matches_saved == 0


def test_sync_summary_is_immutable():
    s = SyncSummary(1, 2, 3, 4, 5)
    with pytest.raises((AttributeError, TypeError)):
        s.leagues = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _rematch_pending_telegram() resilience — must never propagate exceptions
# ---------------------------------------------------------------------------

def test_rematch_swallows_import_errors(monkeypatch):
    """If the Telegram full pipeline is unavailable, the sync must still succeed."""
    import betano_analyzer.telegram.full_pipeline as full_pipeline

    def _broken_retry():
        raise RuntimeError("Telegram service unavailable")

    monkeypatch.setattr(full_pipeline, "retry_pending_matches_full", _broken_retry)
    _rematch_pending_telegram()


def test_rematch_swallows_db_errors(monkeypatch):
    """Database errors during full rematch must not propagate to the caller."""
    import betano_analyzer.telegram.full_pipeline as full_pipeline

    def _db_fail():
        raise Exception("SQLITE_BUSY: database is locked")

    monkeypatch.setattr(full_pipeline, "retry_pending_matches_full", _db_fail)
    _rematch_pending_telegram()


def test_rematch_calls_full_pipeline(monkeypatch):
    """Sync rematching must use the canonical Telegram enrichment pipeline."""
    import betano_analyzer.telegram.full_pipeline as full_pipeline
    calls = []

    def _ok_retry():
        calls.append(1)
        return {"resolved": 0, "still_pending": 0, "total": 0}

    monkeypatch.setattr(full_pipeline, "retry_pending_matches_full", _ok_retry)
    _rematch_pending_telegram()
    assert calls == [1]


# ---------------------------------------------------------------------------
# sync_oddspapi_betano_pe input validation
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_sync_oddspapi_rejects_invalid_hours():
    from betano_analyzer.sync_service import sync_oddspapi_betano_pe
    with pytest.raises(ValueError, match="hours"):
        await sync_oddspapi_betano_pe(hours=0)


@pytest.mark.anyio
async def test_sync_oddspapi_rejects_invalid_limit_matches():
    from betano_analyzer.sync_service import sync_oddspapi_betano_pe
    with pytest.raises(ValueError, match="limit_matches"):
        await sync_oddspapi_betano_pe(limit_matches=0)
