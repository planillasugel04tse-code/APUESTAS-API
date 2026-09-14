from datetime import date

from betano_analyzer.web_surebet_patch import dashboard_response


def test_surebet_dashboard_has_working_controls_and_empty_message():
    html = dashboard_response(date.today()).body.decode("utf-8")

    assert 'id="surebet-pre-button"' in html
    assert 'id="surebet-live-button"' in html
    assert "/api/v1/arbitrage/pre-match?limit=100" in html or "URLSearchParams({limit:'100'" in html
    assert "hours:'1'" in html
    assert "limit_matches:'20'" in html  # internal safety control remains invisible to product wording
    assert "No hay surebets en este momento." in html
    assert "Error PRE-PARTIDO" in html
    assert "Error EN VIVO" in html
