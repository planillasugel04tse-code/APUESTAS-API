from datetime import date

import betano_analyzer.web_surebet_patch as surebet_web


def test_surebet_dashboard_has_working_controls_and_empty_message(monkeypatch):
    monkeypatch.setattr(surebet_web, "oddspapi_connected", lambda: True)
    html = surebet_web.dashboard_response(date.today()).body.decode("utf-8")

    assert 'id="surebet-pre-button"' in html
    assert 'id="surebet-live-button"' in html
    assert "/api/v1/arbitrage/pre-match?limit=100" in html or "URLSearchParams({limit:'100'" in html
    assert "hours:'1'" in html or "hours=1" in html or "hours: 1" in html
    assert "No hay surebet válida en este momento." in html
    assert "Error PRE-PARTIDO" in html
    assert "Error EN VIVO" in html
    assert "target_profits" in html
    assert "GANANCIA GARANTIZADA" in html


def test_surebet_dashboard_requires_oddspapi_connection(monkeypatch):
    monkeypatch.setattr(surebet_web, "oddspapi_connected", lambda: False)
    html = surebet_web.dashboard_response(date.today()).body.decode("utf-8")

    assert "CONEXIÓN API" in html
    assert "CONECTAR Y ACTIVAR" in html
    assert 'id="surebet-pre-button"' not in html
