"""Tests for Telegram configuration loading and CLI --check command."""
from __future__ import annotations

import sys

import pytest

from betano_analyzer.telegram.config import TelegramConfig, _channels, load_telegram_config


# ---------------------------------------------------------------------------
# _channels() helper
# ---------------------------------------------------------------------------

def test_channels_none_for_wildcard():
    assert _channels("*") is None
    assert _channels("all") is None
    assert _channels("todos") is None
    assert _channels("") is None
    assert _channels(None) is None


def test_channels_parses_comma_list():
    result = _channels("@chan1, @chan2, @chan3")
    assert result == ["@chan1", "@chan2", "@chan3"]


def test_channels_strips_whitespace_and_empty():
    result = _channels("@a, , @b , ")
    assert result == ["@a", "@b"]


def test_channels_single_channel():
    result = _channels("@tipster_pe")
    assert result == ["@tipster_pe"]


# ---------------------------------------------------------------------------
# TelegramConfig properties
# ---------------------------------------------------------------------------

def test_config_is_not_configured_without_api_id():
    cfg = TelegramConfig(api_id=None, api_hash="abc", phone="+51999", session_name="s", channels=None, enabled=True)
    assert not cfg.is_configured
    assert "TELEGRAM_API_ID" in " ".join(cfg.validation_errors)


def test_config_is_not_configured_without_api_hash():
    cfg = TelegramConfig(api_id=12345, api_hash=None, phone="+51999", session_name="s", channels=None, enabled=True)
    assert not cfg.is_configured
    assert "TELEGRAM_API_HASH" in " ".join(cfg.validation_errors)


def test_config_is_configured_with_all_required():
    cfg = TelegramConfig(api_id=12345, api_hash="abc", phone="+51999", session_name="s", channels=None, enabled=True)
    assert cfg.is_configured
    assert cfg.validation_errors == []


def test_config_disabled_has_no_errors():
    cfg = TelegramConfig(api_id=None, api_hash=None, phone=None, session_name="s", channels=None, enabled=False)
    assert not cfg.is_configured
    assert cfg.validation_errors == []  # disabled → no errors, not misconfigured


def test_config_multiple_errors_when_both_missing():
    cfg = TelegramConfig(api_id=None, api_hash=None, phone=None, session_name="s", channels=None, enabled=True)
    errors = cfg.validation_errors
    assert len(errors) == 2


# ---------------------------------------------------------------------------
# load_telegram_config() reads from environment
# ---------------------------------------------------------------------------

def test_load_config_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "98765")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash_abc")
    monkeypatch.setenv("TELEGRAM_PHONE", "+51999000111")
    monkeypatch.setenv("TELEGRAM_SESSION_NAME", "my_session")
    monkeypatch.setenv("TELEGRAM_CHANNELS", "@ch1,@ch2")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")

    cfg = load_telegram_config()

    assert cfg.api_id == 98765
    assert cfg.api_hash == "hash_abc"
    assert cfg.phone == "+51999000111"
    assert cfg.session_name == "my_session"
    assert cfg.channels == ["@ch1", "@ch2"]
    assert cfg.enabled is True
    assert cfg.is_configured


def test_load_config_disabled_via_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")
    cfg = load_telegram_config()
    assert cfg.enabled is False


def test_load_config_all_channels_wildcard(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHANNELS", "*")
    cfg = load_telegram_config()
    assert cfg.channels is None


def test_load_config_non_numeric_api_id_becomes_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "not_a_number")
    cfg = load_telegram_config()
    assert cfg.api_id is None


# ---------------------------------------------------------------------------
# __main__ --check command
# ---------------------------------------------------------------------------

def test_check_command_configured(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setattr(sys, "argv", ["betano_telegram", "--check"])

    from betano_analyzer.telegram.__main__ import main
    code = main()

    captured = capsys.readouterr()
    assert code == 0
    assert "CONFIGURADO" in captured.out


def test_check_command_incomplete_config(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_API_ID", "")
    monkeypatch.setenv("TELEGRAM_API_HASH", "")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setattr(sys, "argv", ["betano_telegram", "--check"])

    from betano_analyzer.telegram.__main__ import main
    code = main()

    captured = capsys.readouterr()
    assert code == 2
    assert "INCOMPLETA" in captured.out


def test_check_command_disabled(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")
    monkeypatch.setattr(sys, "argv", ["betano_telegram", "--check"])

    from betano_analyzer.telegram.__main__ import main
    code = main()

    captured = capsys.readouterr()
    assert code == 0
    assert "DESACTIVADO" in captured.out
