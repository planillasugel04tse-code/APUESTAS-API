from datetime import date

from betano_analyzer.web_surebet_patch import dashboard_response


def test_surebet_dashboard_has_working_controls_and_empty_message():
    html = dashboard_response(date.today()).body.decode("utf-8")

    assert 'id="surebet-pre-button"' in html
    assert 'id="surebet-live-button"' in html
    assert "/api/v1/arbitrage/pre-match?limit=100" in html or "URLSearchParams({limit:'100'" in html
    # LIVE safety controls are now enforced server-side; the browser exposes
    # only the product-level action rather than an internal match cap.
    assert "hours:'1'" in html or "hours=1" in html or "hours: 1" in html
    assert "No hay surebets en este momento." in html
    assert "Error PRE-PARTIDO" in html
    assert "Error EN VIVO" in html
