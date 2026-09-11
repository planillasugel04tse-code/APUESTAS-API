"""Command-line entry point for the live Telegram collector."""

from __future__ import annotations

import argparse
import sys

from .collector import start_telegram_listener
from .config import load_telegram_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Betano Live Analyzer - Telegram collector")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate local Telegram configuration without connecting",
    )
    args = parser.parse_args()

    config = load_telegram_config()
    if args.check:
        if not config.enabled:
            print("Telegram: DESACTIVADO (TELEGRAM_ENABLED=false)")
            return 0
        errors = config.validation_errors
        if errors:
            print("Telegram: CONFIGURACION INCOMPLETA")
            for error in errors:
                print(f"- {error}")
            return 2
        channels = "todos los chats accesibles" if config.channels is None else ", ".join(config.channels)
        print("Telegram: CONFIGURADO")
        print(f"- session: {config.session_name}")
        print(f"- channels: {channels}")
        print("- credenciales: presentes (no se muestran por seguridad)")
        return 0

    if config.validation_errors:
        print("Telegram: CONFIGURACION INCOMPLETA", file=sys.stderr)
        for error in config.validation_errors:
            print(f"- {error}", file=sys.stderr)
        print("Usa 'python -m betano_analyzer.telegram --check' para revisar la configuracion.", file=sys.stderr)
        return 2

    start_telegram_listener()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
