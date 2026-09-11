"""Command-line entry point for the live Telegram collector."""

from .collector import start_telegram_listener


if __name__ == "__main__":
    start_telegram_listener()
