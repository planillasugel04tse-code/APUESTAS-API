from __future__ import annotations

PRODUCT_NAME = "ANALISYS BETSTOTAL"
LEGACY_PRODUCT_NAMES = ("Betano Live Analyzer", "Betano Analyzer")


def apply_product_branding(html: str) -> str:
    """Replace legacy visible product names in generated HTML."""
    for legacy in LEGACY_PRODUCT_NAMES:
        html = html.replace(legacy, PRODUCT_NAME)
    return html
