from __future__ import annotations

import re
from datetime import date
from fastapi.responses import HTMLResponse
from .provider_accounts import active_account
from .provider_accounts_panel import provider_accounts_page
from .web import dashboard_html
from .web_surebet_patch import _CARD, _JS, _PROVIDER_CARD, _PROVIDER_JS

_CSS = '''.metric{background:#f4f6fa;border-radius:10px;padding:10px}.metric span{display:block;font-size:10px;color:#68758a;font-weight:800}.metric b{font-size:19px;display:block;margin-top:4px}.surebet-scope{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.surebet-scope button{border:1px solid #dfe5ee;border-radius:9px;padding:9px 12px;background:white;font-weight:800;cursor:pointer}.surebet-scope button.active{border:2px solid #2563eb;background:#eff6ff}.surebet-filters{margin:10px 0}.surebet-filters select{padding:8px;border-radius:8px;border:1px solid #ccd6e5}.surebet-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0}.surebet-opportunity{border:1px solid #dfe5ee;border-radius:14px;padding:16px;margin:14px 0;background:#fff}.opp-head{display:flex;justify-content:space-between;gap:15px}.opp-head h3{margin:5px 0;font-size:20px}.margin-box{background:#ecfdf5;border-radius:10px;padding:10px;text-align:center;min-width:120px}.margin-box small{display:block;font-size:10px}.margin-box strong{font-size:23px;color:#0f8a62}.odds-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}.odd-card{border:1px solid #e5eaf1;border-radius:10px;padding:11px;background:#f8fafc}.odd-card span,.odd-card small{display:block}.odd-card b{display:block;font-size:23px;margin:3px 0}.calc-box{border-top:1px solid #e5eaf1;padding-top:12px}.calc-title{font-size:12px;font-weight:900;margin:10px 0 7px}.calc-table th,.calc-table td{font-size:12px;padding:7px}.opp-footer{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:12px;font-size:12px}.empty-surebet{padding:20px;border:1px dashed #ccd6e5;border-radius:12px;text-align:center}.provider-status-card .small-button{display:inline-block;text-decoration:none;border:1px solid #dfe5ee;border-radius:9px;padding:8px 10px;color:#172033;background:#fff;font-weight:800}@media(max-width:700px){.surebet-summary,.odds-grid{grid-template-columns:1fr}.opp-head,.opp-footer{flex-direction:column;align-items:stretch}}'''

def _base_nav() -> str:
    return '<nav class="main-nav"><a class="primary" href="/">🏠 PANEL PRINCIPAL</a><a class="live" href="/surebet">💰 SUREBET</a><a href="/telegram-test">📨 TELEGRAM</a><a href="/provider-accounts">🔐 CONEXIÓN API</a><a href="/bookmakers">🏦 CASAS</a><a href="/panel">⚙️ CONFIGURACIÓN</a><a href="/docs">📚 API</a></nav>'

def dashboard_fixed(today: date) -> HTMLResponse:
    if not active_account():
        return provider_accounts_page()
    html = dashboard_html(today)
    html = re.sub(r'<div class="card" id="surebet-section">.*?</div>\n<div class="card" id="final-section">', '<div class="card" id="final-section">', html, count=1, flags=re.S)
    html = re.sub(r'<a class="live" href="#surebet-section">.*?</a>', '<a class="live" href="/surebet">💰 SUREBET</a>', html, count=1, flags=re.S)
    html = re.sub(r'<a class="quick surebet" href="#surebet-section">.*?</a>', '', html, count=1, flags=re.S)
    html = re.sub(r'<div class="quick-title">ACCESOS RÁPIDOS</div><div class="quick-grid">', '<div class="quick-title">ACCESOS RÁPIDOS</div><div class="quick-grid">', html, count=1)
    html = re.sub(r'<div class="profile-card">.*?</div></section>', _PROVIDER_CARD + '</section>', html, count=1, flags=re.S)
    html = html.replace('</script>', _PROVIDER_JS + '\nloadProviderStatus();\n</script>', 1)
    html = html.replace('</style>', _CSS + '</style>', 1)
    return HTMLResponse(html)

def surebet_page() -> HTMLResponse:
    return HTMLResponse(f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SUREBET · ANALISYS BETSTOTAL</title><style>:root{{--bg:#f3f6fb;--ink:#172033;--line:#dfe5ee;--primary:#101827}}*{{box-sizing:border-box}}body{{font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--bg);margin:0;color:var(--ink)}}header{{background:linear-gradient(135deg,#0b1220,#1c3157 65%,#2563eb);color:white;padding:26px 28px}}main{{max-width:1500px;margin:22px auto;padding:0 18px}}.main-nav{{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:16px}}.main-nav a{{border:1px solid var(--line);border-radius:11px;padding:10px 14px;text-decoration:none;background:white;color:var(--ink);font-weight:800}}.main-nav a.primary{{background:var(--primary);color:white}}.main-nav a.live{{background:#fff1f2;color:#a51d2d}}.card{{background:white;border-radius:14px;padding:20px;border:1px solid #e5eaf1}}.muted{{color:#697386}}button{{border:1px solid #dfe5ee;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer}}</style>{_CSS}</head><body><header><h1>💰 SUREBET</h1><p>Centro de oportunidades · PRE-MATCH y LIVE</p></header><main>{_base_nav()}<div class="card">{_CARD}</div></main><script>{_JS}</script></body></html>''')
