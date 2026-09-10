"""Telegram is an input/source adapter for the core Betano Analyzer engines."""

from .parser import ParsedTelegramPick, parse_telegram_message
from .service import process_telegram_signal

__all__ = ["ParsedTelegramPick", "parse_telegram_message", "process_telegram_signal"]
