from datetime import date

from betano_analyzer.web_surebet_patch import dashboard_response


def test_surebet_dashboard_has_working_controls_and_empty_message():
    html = dashboard_response(date.today()).body.decode("utf-8")

    assert 'id="surebet-pre-button"' in html
    assert 'id="surebet-live-button"' in html
    assert "/api/v1/arbitrage/pre-match?limit=100" in html
    assert "/api/v1/arbitrage/live?limit=100&hours=1&limit_matches=20" in html
    assert "NO HAY SUREBET EN ESTE MOMENTO" in html
    assert "Error PRE-PARTIDO" in html
    assert "Error EN VIVO" in html
