from __future__ import annotations

from fastapi.responses import HTMLResponse

from .control_panel import control_panel_page



def control_panel_with_provider_accounts() -> HTMLResponse:
    html = control_panel_page().body.decode("utf-8")
    marker = '<a class="primary" href="/panel">🎛️ Panel</a>'
    link = marker + '<a href="/provider-accounts">🔐 Cuentas API</a>'
    if marker in html and 'href="/provider-accounts"' not in html:
        html = html.replace(marker, link, 1)
    return HTMLResponse(html)
