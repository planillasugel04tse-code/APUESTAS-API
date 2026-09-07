from __future__ import annotations

from datetime import date, timedelta
from fastapi.responses import HTMLResponse


def _periods(today: date) -> dict[str, tuple[date | None, date | None]]:
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    saturday = monday + timedelta(days=5)
    sunday = monday + timedelta(days=6)
    return {
        "dia": (today, today),
        "lunes-viernes": (monday, friday),
        "sabado-domingo": (saturday, sunday),
        "todos": (None, None),
    }


def dashboard_html(today: date) -> str:
    buttons = "".join(
        f'<button class="tab" data-period="{key}">{label}</button>'
        for key, label in [
            ("dia", "Día"),
            ("lunes-viernes", "Lunes a viernes"),
            ("sabado-domingo", "Sábado y domingo"),
            ("todos", "Todos"),
        ]
    )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Betano Live Analyzer</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f7fb;margin:0;color:#172033}}
header{{background:#101827;color:white;padding:22px 28px}} h1{{margin:0 0 5px}} .sub{{opacity:.75}}
main{{max-width:1200px;margin:25px auto;padding:0 18px}} .tabs{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}}
.tab{{border:0;border-radius:10px;padding:13px 18px;background:white;cursor:pointer;font-weight:700;box-shadow:0 1px 5px #0001}}
.tab.active{{background:#172033;color:white}} .card{{background:white;border-radius:14px;padding:22px;box-shadow:0 2px 10px #0001}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}} .metric b{{font-size:28px;display:block;margin-top:6px}}
.notice{{margin-top:15px;padding:13px;border-radius:10px;background:#fff8e6}} @media(max-width:800px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body>
<header><h1>⚽ Betano Live Analyzer</h1><div class="sub">Panel de oportunidades y rendimiento</div></header>
<main><div class="tabs">{buttons}</div><div id="content"></div></main>
<script>
const periods = {str(_periods(today)).replace("'", '"')};
function render(period){{
 document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.period===period));
 const labels={{'dia':'Día de hoy','lunes-viernes':'Lunes a viernes','sabado-domingo':'Sábado y domingo','todos':'Todos los registros'}};
 const range=periods[period];
 document.getElementById('content').innerHTML=`<div class="card"><h2>${{labels[period]}}</h2>
 <div class="grid"><div class="metric">Partidos candidatos<b>0</b></div><div class="metric">Pronósticos<b>0</b></div><div class="metric">Apuestas<b>0</b></div><div class="metric">ROI<b>—</b></div></div>
 <p>El filtro está preparado para recibir los datos reales del motor. No se muestran apuestas inventadas.</p>
 <div class="notice">📌 Cuando conectemos las fuentes, esta pantalla se llenará automáticamente según el período seleccionado.</div></div>`;
}}
document.querySelectorAll('.tab').forEach(x=>x.addEventListener('click',()=>render(x.dataset.period))); render('dia');
</script></body></html>"""


def dashboard_response(today: date) -> HTMLResponse:
    return HTMLResponse(dashboard_html(today))
