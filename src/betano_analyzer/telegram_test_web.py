from __future__ import annotations

from fastapi.responses import HTMLResponse


def telegram_test_page() -> HTMLResponse:
    html = '''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Telegram Test · Betano Live Analyzer</title>
<style>body{font-family:Arial,sans-serif;background:#f5f7fb;color:#172033;margin:0}main{max-width:1000px;margin:30px auto;padding:0 18px}.card{background:#fff;border-radius:14px;padding:22px;margin-bottom:18px;box-shadow:0 2px 10px #0001}h1{margin-top:0}label{display:block;font-weight:700;margin:12px 0 6px}input,textarea{box-sizing:border-box;width:100%;padding:11px;border:1px solid #ccd2dc;border-radius:8px;font:inherit}textarea{min-height:150px;resize:vertical}button{border:0;border-radius:9px;padding:11px 16px;background:#172033;color:#fff;font-weight:700;cursor:pointer;margin-top:14px}.secondary{background:#e9edf3;color:#172033}.result{white-space:pre-wrap;background:#f7f8fa;border-radius:9px;padding:14px;overflow:auto;margin-top:15px}.ok{border-left:4px solid #198754}.error{border-left:4px solid #dc3545}.muted{color:#697386}</style></head>
<body><main>
<div class="card"><h1>📩 Prueba Telegram · Betano Live Analyzer</h1><p class="muted">Prueba el pipeline Telegram → parser → matching → Analyzer/Radar/Surebet sin subir credenciales.</p>
<label>Canal</label><input id="channel" value="prueba">
<label>ID del mensaje</label><input id="message_id" value="test-1">
<label>Tipster (opcional)</label><input id="tipster" placeholder="Nombre del tipster">
<label>Mensaje de Telegram</label><textarea id="text" placeholder="Ej.: Liverpool vs Arsenal Over 2.5 goles cuota 1.85"></textarea>
<button onclick="sendSignal()">PROBAR MENSAJE</button> <button class="secondary" onclick="checkConfig()">COMPROBAR CONFIGURACIÓN TELEGRAM</button>
<div id="result" class="result">Esperando una prueba...</div></div>
<script>
async function sendSignal(){const result=document.getElementById('result');result.textContent='Procesando...';result.className='result';const payload={channel:channel.value,message_id:message_id.value,text:text.value,tipster:tipster.value||null};try{const r=await fetch('/api/v1/telegram/signals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();result.textContent=JSON.stringify(d,null,2);result.className='result '+(r.ok?'ok':'error')}catch(e){result.textContent='Error de conexión: '+e;result.className='result error'}}
async function checkConfig(){const result=document.getElementById('result');result.textContent='Comprobando...';result.className='result';try{const r=await fetch('/api/v1/telegram/config');const d=await r.json();result.textContent=JSON.stringify(d,null,2);result.className='result '+(r.ok?'ok':'error')}catch(e){result.textContent='Error: '+e;result.className='result error'}}
</script></main></body></html>'''
    return HTMLResponse(html)
