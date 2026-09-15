from __future__ import annotations

PRODUCT_NAME = "ANALISYS BETSTOTAL"
LEGACY_PRODUCT_NAMES = ("Betano Live Analyzer", "Betano Analyzer")


OLD_PROFILE_CARD = '''<div class="profile-card"><div class="profile-title"><h2>👤 Usuario</h2><span class="eyebrow">Perfil</span></div><div class="profile-grid"><div class="profile-item">USUARIO<b id="profileUser">LUCIANO</b></div><div class="profile-item">CORREO<b id="profileEmail">WSLUCIANO@HOTMAIL.COM</b></div><div class="profile-item">CLAVE<b>••••••••</b></div><div class="profile-item">ESTADO<b>🟢 ACTIVO</b></div></div><div class="profile-actions"><button class="small-button" onclick="toggleProfile()">✏️ CAMBIAR DATOS</button></div><div id="profileEdit" class="profile-edit"><label>Usuario</label><input id="editUser" value="LUCIANO"><label>Correo</label><input id="editEmail" value="WSLUCIANO@HOTMAIL.COM"><label>Nueva clave</label><input id="editPassword" type="password" placeholder="Dejar vacío para no cambiar"><button onclick="saveProfile()">GUARDAR PERFIL</button></div></div>'''

NEW_CONNECTION_CARD = '''<div class="profile-card"><div class="profile-title"><h2>🔐 Conexión API</h2><span class="eyebrow">OddsPapi</span></div><div class="profile-grid"><div class="profile-item">PROVEEDOR<b>OddsPapi</b></div><div class="profile-item">CONEXIÓN<b>🟢 CONFIGURABLE</b></div><div class="profile-item">API KEY<b>••••••••</b></div><div class="profile-item">ESTADO<b id="apiConnectionStatus">⚪ NO PROBADA</b></div></div><div class="profile-actions"><a class="small-button" href="/provider-accounts" style="display:inline-block;text-decoration:none;background:#172033;color:white;border-radius:9px;padding:8px 10px;font-weight:800">🔐 PROBAR CONEXIÓN</a></div><div class="quote-meta" style="margin-top:9px">Aquí se prueba y administra la conexión real con OddsPapi. La API Key se introduce en el formulario seguro del proveedor.</div></div>'''

OLD_CHECK_FUNCTION = """async function checkAccount(){if(!val('api_key').trim()){show('Escribe la API Key primero.');return}show('Comprobando cuenta...');try{show(await req('/api/v1/provider-accounts/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:val('provider'),label:val('label'),email:val('email'),api_key:val('api_key')})}))}catch(e){show('ERROR: '+e.message)}}"""

NEW_CHECK_FUNCTION = """async function checkAccount(){if(!val('api_key').trim()){show('Escribe la API Key primero.');return}show('Comprobando cuenta...');try{const d=await req('/api/v1/provider-accounts/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:val('provider'),label:val('label'),email:val('email'),api_key:val('api_key')})});if(!d.valid){show('❌ CONEXIÓN NO VÁLIDA\\n\\n'+(d.error||'OddsPapi rechazó la API Key.'));return}const u=d.usage||{};const c=d.account||{};const sports=Array.isArray(c.sports)?c.sports.length:'—';const live=c.has_live_odds?'SÍ':'NO';const props=c.has_player_props?'SÍ':'NO';const ws=(c.websocket_access||c.has_websocket)?'SÍ':'NO';show(`✅ CONEXIÓN EXITOSA\\n\\nPROVEEDOR: OddsPapi\\nPLAN: ${d.plan??'—'}\\nESTADO SUSCRIPCIÓN: ${d.subscription_status??'—'}\\nUSO: ${d.usage_display??'—'}\\nRESTANTE: ${d.quota_remaining??'—'}\\nDEPORTES DISPONIBLES: ${sports}\\nLIVE ODDS: ${live}\\nPLAYER PROPS: ${props}\\nWEBSOCKET: ${ws}\\nVIGENCIA: ${d.valid_from??'—'} → ${d.valid_until??'—'}\\n\\n🔒 La API Key no se muestra ni se devuelve en la respuesta visible.`)}catch(e){show('ERROR: '+e.message)}}"""


def apply_product_branding(html: str) -> str:
    """Apply product branding and improve the main dashboard connection card."""
    for legacy in LEGACY_PRODUCT_NAMES:
        html = html.replace(legacy, PRODUCT_NAME)
    html = html.replace(OLD_PROFILE_CARD, NEW_CONNECTION_CARD)
    html = html.replace(OLD_CHECK_FUNCTION, NEW_CHECK_FUNCTION)
    return html
