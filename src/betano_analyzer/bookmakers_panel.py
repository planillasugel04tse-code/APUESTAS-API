from __future__ import annotations

from fastapi.responses import HTMLResponse


def bookmakers_panel_page() -> HTMLResponse:
    html = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Casas de apuestas Perú · Betano Live Analyzer</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#f3f6fb;color:#172033;margin:0}header{background:#111b2e;color:#fff;padding:24px}main{max-width:1100px;margin:auto;padding:20px}.card{background:#fff;border:1px solid #dde5f0;border-radius:16px;padding:20px;margin-bottom:16px;box-shadow:0 5px 18px #1720330d}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.book{border:1px solid #d9e2ef;border-radius:10px;padding:12px}.book small{display:block;color:#68758a;margin-top:4px}.actions{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}button{border:0;border-radius:9px;padding:10px 14px;background:#17233a;color:#fff;font-weight:700;cursor:pointer}button.success{background:#0f8a62}button.warn{background:#b77900}.result{background:#0b1220;color:#d9e6fb;border-radius:10px;padding:14px;white-space:pre-wrap;font:12px/1.5 monospace;min-height:40px}a{color:#1268a3;font-weight:700}@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style></head>
<body><header><h1>🇵🇪 Casas de apuestas · Perú</h1><p>Selector real de casas disponibles para tu cuenta del proveedor de cuotas.</p></header>
<main>
<div class="card"><p><strong>Importante:</strong> el sistema consulta al proveedor configurado para saber qué casas están disponibles y seleccionadas. No se conecta a cuentas de las casas ni realiza apuestas.</p><div class="actions"><button onclick="loadCatalog()">ACTUALIZAR CASAS</button><button class="success" onclick="sync(true)">🔴 SINCRONIZAR LIVE</button><button onclick="sync(false)">SINCRONIZAR PRE-PARTIDO</button><a href="/panel">← Volver al panel</a></div><div id="grid" class="grid"></div></div>
<div class="card"><h2>Resultado</h2><div id="result" class="result">Pulsa ACTUALIZAR CASAS.</div></div>
</main>
<script>
const $=id=>document.getElementById(id);let available=[];
async function req(url,opts={}){const r=await fetch(url,opts);let d;try{d=await r.json()}catch{d=await r.text()}if(!r.ok)throw new Error(typeof d==='object'?(d.detail||JSON.stringify(d)):d);return d}
async function loadCatalog(){ $('result').textContent='Consultando proveedor...';try{const d=await req('/api/v1/bookmakers/peru');available=d.available_peru_bookmakers||[];$('grid').innerHTML=(d.priority_bookmakers||[]).map(x=>`<label class="book"><input type="checkbox" value="${x.name}" ${x.available?'checked':''} ${x.available?'':'disabled'}> <strong>${x.name}</strong><small>${x.available?'Disponible en el proveedor':'No disponible para esta cuenta/proveedor'}</small></label>`).join('');$('result').textContent=JSON.stringify(d,null,2)}catch(e){$('result').textContent='ERROR: '+e.message}}
function selected(){return [...document.querySelectorAll('input[type=checkbox]:checked')].map(x=>x.value)}
async function sync(live){const books=selected();if(!books.length){$('result').textContent='Selecciona al menos una casa.';return}if(books.length>30){$('result').textContent='Máximo 30 casas por lote.';return}$('result').textContent='Sincronizando '+books.length+' casas...';try{const q=new URLSearchParams({bookmakers:books.join(','),include_live:String(live),limit_per_league:'20'});$('result').textContent=JSON.stringify(await req('/api/v1/sync/odds?'+q.toString(),{method:'POST'}),null,2)}catch(e){$('result').textContent='ERROR: '+e.message}}
loadCatalog();
</script></body></html>'''
    return HTMLResponse(html)
