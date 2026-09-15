from __future__ import annotations

PRODUCT_NAME = "ANALISYS BETSTOTAL"
LEGACY_PRODUCT_NAMES = ("Betano Live Analyzer", "Betano Analyzer")


OLD_PROFILE_CARD = '''<div class="profile-card"><div class="profile-title"><h2>👤 Usuario</h2><span class="eyebrow">Perfil</span></div><div class="profile-grid"><div class="profile-item">USUARIO<b id="profileUser">LUCIANO</b></div><div class="profile-item">CORREO<b id="profileEmail">WSLUCIANO@HOTMAIL.COM</b></div><div class="profile-item">CLAVE<b>••••••••</b></div><div class="profile-item">ESTADO<b>🟢 ACTIVO</b></div></div><div class="profile-actions"><button class="small-button" onclick="toggleProfile()">✏️ CAMBIAR DATOS</button></div><div id="profileEdit" class="profile-edit"><label>Usuario</label><input id="editUser" value="LUCIANO"><label>Correo</label><input id="editEmail" value="WSLUCIANO@HOTMAIL.COM"><label>Nueva clave</label><input id="editPassword" type="password" placeholder="Dejar vacío para no cambiar"><button onclick="saveProfile()">GUARDAR PERFIL</button></div></div>'''

NEW_CONNECTION_CARD = '''<div class="profile-card"><div class="profile-title"><h2>🔐 Conexión API</h2><span class="eyebrow">OddsPapi</span></div><p class="quote-meta">Antes de consultar o analizar cuotas, conecta aquí tu API Key de OddsPapi. La clave se valida contra el endpoint de cuenta y, solo si es válida, queda activada para el Analyzer.</p><label style="font-size:12px;font-weight:800;color:#4d5a70">API KEY</label><input id="dashboardApiKey" type="password" placeholder="Pega aquí tu API Key de OddsPapi" autocomplete="off" style="width:100%;border:1px solid #ccd6e5;border-radius:9px;padding:10px;margin:6px 0 8px;font:inherit;box-sizing:border-box"><div class="profile-actions"><button class="small-button" id="connectOddsButton" onclick="connectOddsPapi()" style="background:#0f8a62;color:white">🔌 PROBAR Y CONECTAR</button><a class="small-button" href="/provider-accounts" style="display:inline-block;text-decoration:none;background:#172033;color:white;border-radius:9px;padding:8px 10px;font-weight:800">⚙️ ADMINISTRAR</a></div><div id="apiConnectionStatus" class="quote-meta" style="margin-top:9px">⚪ API NO CONECTADA · Las consultas de surebet están bloqueadas hasta conectar una clave válida.</div></div>'''

OLD_CHECK_FUNCTION = """async function checkAccount(){if(!val('api_key').trim()){show('Escribe la API Key primero.');return}show('Comprobando cuenta...');try{show(await req('/api/v1/provider-accounts/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:val('provider'),label:val('label'),email:val('email'),api_key:val('api_key')})}))}catch(e){show('ERROR: '+e.message)}}"""

NEW_CHECK_FUNCTION = """async function checkAccount(){if(!val('api_key').trim()){show('Escribe la API Key primero.');return}show('Comprobando cuenta...');try{const d=await req('/api/v1/provider-accounts/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:val('provider'),label:val('label'),email:val('email'),api_key:val('api_key')})});if(!d.valid){show('❌ CONEXIÓN NO VÁLIDA\\n\\n'+(d.error||'OddsPapi rechazó la API Key.'));return}show(`✅ CONEXIÓN EXITOSA\\n\\nPLAN: ${d.plan??'—'}\\nUSO: ${d.usage_display??'—'}\\nRESTANTE: ${d.quota_remaining??'—'}\\nVIGENCIA: ${d.valid_from??'—'} → ${d.valid_until??'—'}\\n\\n🔒 La API Key no se muestra.`)}catch(e){show('ERROR: '+e.message)}}"""

DASHBOARD_CONNECTION_SCRIPT = '''<script>
async function connectOddsPapi(){
  const input=document.getElementById('dashboardApiKey');
  const button=document.getElementById('connectOddsButton');
  const status=document.getElementById('apiConnectionStatus');
  const key=(input?.value||'').trim();
  if(!key){status.textContent='⚠️ Pega primero tu API Key de OddsPapi.';return}
  button.disabled=true;button.textContent='⏳ VALIDANDO...';status.textContent='🔄 Validando la API Key con OddsPapi...';
  try{
    const response=await fetch('/api/v1/provider-accounts/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:'oddspapi',label:'Panel principal',email:'',api_key:key})});
    let data={};try{data=await response.json()}catch(_){data={}}
    if(!response.ok)throw new Error(data.detail||'No se pudo conectar OddsPapi');
    input.value='';
    status.textContent='🟢 API CONECTADA · OddsPapi validado y activo. Ya puedes consultar y analizar Surebet.';
    enableSurebetControls(true);
    const u=data.usage||{};
    if(u.display) status.textContent+=' · Uso: '+u.display;
  }catch(error){
    status.textContent='🔴 CONEXIÓN FALLIDA · '+error.message;
    enableSurebetControls(false);
  }finally{button.disabled=false;button.textContent='🔌 PROBAR Y CONECTAR'}
}
function surebetButtons(){
  const ids=['surebet-pre-button','surebet-live-button'];
  const found=ids.map(id=>document.getElementById(id)).filter(Boolean);
  if(found.length)return found;
  return Array.from(document.querySelectorAll('button')).filter(b=>/SUREBET (PRE|EN VIVO|LIVE)/i.test(b.textContent||''));
}
function enableSurebetControls(connected){
  surebetButtons().forEach(b=>{b.disabled=!connected;b.style.opacity=connected?'1':'.55';b.title=connected?'':'Conecta primero la API Key de OddsPapi'});
}
async function refreshOddsPapiConnection(){
  try{
    const r=await fetch('/api/v1/provider-accounts',{cache:'no-store'});const d=await r.json();
    const active=(d.accounts||[]).find(a=>a.provider==='oddspapi'&&a.active);
    const status=document.getElementById('apiConnectionStatus');
    if(active){if(status)status.textContent='🟢 API CONECTADA · '+(active.api_key_masked||'clave activa');enableSurebetControls(true)}
    else enableSurebetControls(false);
  }catch(_){enableSurebetControls(false)}
}
if(document.getElementById('dashboardApiKey'))refreshOddsPapiConnection();
</script>'''


def apply_product_branding(html: str) -> str:
    """Apply product branding and enforce an explicit OddsPapi connection gate."""
    for legacy in LEGACY_PRODUCT_NAMES:
        html = html.replace(legacy, PRODUCT_NAME)
    html = html.replace(OLD_PROFILE_CARD, NEW_CONNECTION_CARD)
    html = html.replace(OLD_CHECK_FUNCTION, NEW_CHECK_FUNCTION)
    if 'id="dashboardApiKey"' in html and 'function connectOddsPapi()' not in html:
        html = html.replace('</body>', DASHBOARD_CONNECTION_SCRIPT + '</body>')
    return html
