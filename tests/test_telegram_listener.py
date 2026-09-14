from __future__ import annotations

from types import SimpleNamespace

import pytest

from betano_analyzer.telegram import listener


def test_channel_allowed_accepts_username_and_at_username():
    event = SimpleNamespace(chat=SimpleNamespace(username="tipster_live", title="Tipster Live"))
    assert listener._channel_allowed(["@tipster_live"], event)
    assert listener._channel_allowed(["tipster_live"], event)


def test_channel_allowed_accepts_title():
    event = SimpleNamespace(chat=SimpleNamespace(username=None, title="Mis Picks"))
    assert listener._channel_allowed(["mis picks"], event)


def test_channel_allowed_rejects_unconfigured_channel():
    event = SimpleNamespace(chat=SimpleNamespace(username="other", title="Other"))
    assert not listener._channel_allowed(["@tipster_live"], event)


def test_channel_allowed_none_means_all_channels():
    event = SimpleNamespace(chat=SimpleNamespace(username="anything", title="Anything"))
    assert listener._channel_allowed(None, event)


def test_build_client_rejects_missing_configuration(monkeypatch):
    monkeypatch.setattr(listener, "load_telegram_config", lambda: SimpleNamespace(is_configured=False, validation_errors=["faltan credenciales"]))
    with pytest.raises(RuntimeError, match="faltan credenciales"):
        listener.build_client()
