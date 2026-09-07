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
        "mes": (today - timedelta(days=30), today),
        "3-meses": (today - timedelta(days=90), today),
        "6-meses": (today - timedelta(days=180), today),
        "todos": (None, None),
    }


def dashboard_html(today: date) -> str:
    buttons = "".join(
        f'<button class="tab" data-period="{key}">{label}</button>'
        for key, label in [
            ("dia", "HOY"),
            ("lunes-viernes", "LUNES A VIERNES"),
            ("sabado-domingo", "SÁBADO Y DOMINGO"),
            ("mes", "MES"),
            ("3-meses", "3 MESES"),
            ("6-meses", "6 MESES"),
            ("todos", "TODOS"),
        ]
    )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Betano Live Analyzer</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f7fb;margin:0;color:#172033}}
header{{background:#101827;color:white;padding:22px 28px}} h1{{margin:0 0 5px}} .sub{{opacity:.75}}
main{{max-width:1300px;margin:25px auto;padding:0 18px}} .tabs{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}}
.tab{{border:0;border-radius:10px;padding:12px 15px;background:white;cursor:pointer;font-weight:700;box-shadow:0 1px 5px #0001}}
.tab.active{{background:#172033;color:white}} .card{{background:white;border-radius:14px;padding:20px;box-shadow:0 2px 10px #0001;margin-bottom:18px}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:18px}} .metric b{{font-size:25px;display:block;margin-top:6px}}
.filters{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}} select,input{{padding:10px;border:1px solid #ccd3df;border-radius:8px}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:10px;border-bottom:1px solid #e7eaf0;text-align:left;font-size:14px}} th{{background:#f8f9fc}}
.badge{{padding:5px 8px;border-radius:7px;font-weight:700}} .fuerte{{background:#dff6e5;color:#176b35}} .interesante{{background:#fff0c7;color:#8a6100}}
.edge{{font-weight:700}} .muted{{color:#697386}} .notice{{padding:12px;border-radius:10px;background:#fff8e6;margin-top:12px}}
@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,1fr)}} table{{display:block;overflow-x:auto;white-space:nowrap}}}}
</style></head><body>
<header><h1>⚽ Betano Live Analyzer</h1><div class="sub">Radar futuro + rendimiento histórico</div></header>
<main>
<div class="tabs">{buttons}</div>
<div class="card"><div class="filters"><strong>Radar futuro</strong><label>Máximo <input id="limit" type="number" min="1" max="100" value="20" style="width:70px"></label><button class="tab" onclick="loadRadar()">Actualizar radar</button></div></div>
<div id="radar"></div>
<div class="card"><h2>Rendimiento de apuestas</h2><div id="performance" class="grid"></div></div>
<div class="notice">⚠️ El radar es un filtro analítico. No garantiza ganancias. Las oportunidades solo aparecen cuando existen datos suficientes de pronóstico/cuota y pasan los filtros.</div>
</main>
<script>
let currentPeriod='dia';
const labels={{'dia':'HOY','lunes-viernes':'LUNES A VIERNES','sabado-domingo':'SÁBADO A DOMINGO','mes':'MES','3-meses':'3 MESES','6-meses':'6 MESES','todos':'TODOS'}};
document.querySelectorAll('.tab[data-period]').forEach(x=>x.addEventListener('click',()=>{{currentPeriod=x.dataset.period;document.querySelectorAll('.tab[data-period]').forEach(y=>y.classList.toggle('active',y===x));loadPerformance();}}));
document.querySelector('.tab[data-period="dia"]').classList.add('active');
async function loadRadar(){{
 const limit=document.getElementById('limit').value;
 const data=await fetch('/api/v1/opportunities?limit='+limit).then(r=>r.json());
 if(!data.opportunities.length){{document.getElementById('radar').innerHTML='<div class="card"><h2>Radar</h2><p class="muted">No hay oportunidades calificadas con los datos disponibles.</p></div>';return;}}
 let rows=data.opportunities.map(o=>`<tr><td>${{o.competition}}</td><td><strong>${{o.match}}</strong><br><span class="muted">${{o.kickoff}}</span></td><td>${{o.market}}</td><td>${{o.selection}}</td><td>${{o.odds}}</td><td>${{(o.model_probability*100).toFixed(1)}}%</td><td class="edge">${{(o.edge*100).toFixed(1)}}%</td><td>${{o.consensus}}</td><td><span class="badge ${{o.rating}}">${{o.rating.toUpperCase()}}</span></td></tr>`).join('');
 document.getElementById('radar').innerHTML=`<div class="card"><h2>🎯 Próximas oportunidades (${{data.count}})</h2><table><thead><tr><th>Competición</th><th>Partido</th><th>Mercado</th><th>Selección</th><th>Cuota</th><th>Prob.</th><th>Edge</th><th>Consenso</th><th>Rating</th></tr></thead><tbody>${{rows}}</tbody></table></div>`;
}}
async function loadPerformance(){{
 const data=await fetch('/api/v1/bets/summary?period='+currentPeriod).then(r=>r.json());
 document.getElementById('performance').innerHTML=`<div class="metric">Apuestas<b>${{data.bets}}</b></div><div class="metric">Ganadas<b>${{data.wins}}</b></div><div class="metric">Perdidas<b>${{data.losses}}</b></div><div class="metric">Neto<b>S/ ${{data.net.toFixed(2)}}</b></div><div class="metric">ROI<b>${{(data.roi*100).toFixed(2)}}%</b></div>`;
}}
loadRadar();loadPerformance();
</script></body></html>"""


def dashboard_response(today: date) -> HTMLResponse:
    return HTMLResponse(dashboard_html(today))
