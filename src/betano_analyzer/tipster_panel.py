from __future__ import annotations

from fastapi.responses import HTMLResponse


def tipster_panel_page() -> HTMLResponse:
    html = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ANALISYS BETSTOTAL · Tipsters & IA</title>
<style>
body{font-family:Arial,sans-serif;background:#0b1220;color:#e5e7eb;margin:0}.wrap{max-width:1200px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}.card{background:#111827;border:1px solid #243244;border-radius:14px;padding:18px}h1,h2{margin-top:0}.pill{display:inline-block;padding:6px 10px;border-radius:999px;background:#172554;margin:3px}.ok{color:#86efac}.warn{color:#fde68a}.danger{color:#fca5a5}label{display:block;margin:10px 0 5px}input,textarea,button{width:100%;box-sizing:border-box;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#fff;padding:10px}button{cursor:pointer;margin-top:10px;background:#1d4ed8}.result{white-space:pre-wrap;background:#020617;padding:12px;border-radius:8px;margin-top:10px;min-height:80px}.rule{font-size:14px;color:#cbd5e1}
</style></head><body><div class="wrap">
<h1>🧠 ANALISYS BETSTOTAL · INTELIGENCIA DE TIPSTERS</h1>
<p>Recolecta fuentes públicas, Telegram, pronósticos de IA y Betmains; normaliza, contrasta estadísticas/cuotas y solo deja oportunidades dentro de las reglas de riesgo.</p>
<div class="grid">
<section class="card"><h2>🌐 Fuentes automáticas</h2><p class="rule">Las fuentes públicas se registran en <code>data/tipster_sources.json</code>. El colector consulta RSS/Atom/HTML permitido y no inventa pronósticos.</p><button onclick="post('/api/v1/tipsters/collect-web','web')">🔄 ACTUALIZAR TIPSTERS WEB</button><div id="web" class="result"></div></section>
<section class="card"><h2>📨 Telegram</h2><p class="rule">El listener de Telegram existente normaliza los mensajes y los envía al mismo motor de análisis. No publica ni realiza apuestas.</p><span class="pill">AUTOMÁTICO</span><span class="pill">NORMALIZADO</span><span class="pill">HISTÓRICO</span></section>
<section class="card"><h2>🤖 Pronósticos IA</h2><label>Fuente IA</label><input id="aisource" value="ANALISYS BETSTOTAL IA"><label>Pronóstico</label><textarea id="aitext" placeholder="Ej.: Alianza Lima vs ... Over 2.5 @ 1.75"></textarea><button onclick="ai()">ANALIZAR IA</button><div id="ai" class="result"></div></section>
<section class="card"><h2>📷 Betmains</h2><p class="rule">No se asume acceso a una cuenta privada. Si la integración autenticada no está disponible, la imagen queda como entrada manual de respaldo.</p><form id="bm" enctype="multipart/form-data"><input type="file" name="image" accept="image/*" required><input name="note" placeholder="Nota opcional"><button>SUBIR JUGADA</button></form><div id="bmout" class="result"></div></section>
<section class="card"><h2>🛡️ Motor de seguridad</h2><div class="pill">Máx. 3 selecciones</div><div class="pill">Preferencia 1.40–2.10</div><div class="pill">Límite duro 2.50</div><div class="pill">Valor + estadísticas</div><div class="pill">Árbitro si hay dato</div><p class="rule">Una transformación como “gana local” → “1X” o “Over 3” → “Over 2” se presenta como alternativa más conservadora, nunca como garantía.</p></section>
</div></div>
<script>
async function post(url,id){const r=await fetch(url,{method:'POST'});document.getElementById(id).textContent=JSON.stringify(await r.json(),null,2)}
async function ai(){const r=await fetch('/api/v1/tipsters/ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:document.getElementById('aisource').value,text:document.getElementById('aitext').value})});document.getElementById('ai').textContent=JSON.stringify(await r.json(),null,2)}
document.getElementById('bm').onsubmit=async e=>{e.preventDefault();const r=await fetch('/api/v1/tipsters/betmains/photo',{method:'POST',body:new FormData(e.target)});document.getElementById('bmout').textContent=JSON.stringify(await r.json(),null,2)};
</script></body></html>"""
    return HTMLResponse(html)
