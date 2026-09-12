from __future__ import annotations

PRODUCT_NAME = "ANALISYS BETSTOTAL"
LEGACY_PRODUCT_NAMES = ("Betano Live Analyzer", "Betano Analyzer")


OLD_PROFILE_CARD = '''<div class="profile-card"><div class="profile-title"><h2>👤 Usuario</h2><span class="eyebrow">Perfil</span></div><div class="profile-grid"><div class="profile-item">USUARIO<b id="profileUser">LUCIANO</b></div><div class="profile-item">CORREO<b id="profileEmail">WSLUCIANO@HOTMAIL.COM</b></div><div class="profile-item">CLAVE<b>••••••••</b></div><div class="profile-item">ESTADO<b>🟢 ACTIVO</b></div></div><div class="profile-actions"><button class="small-button" onclick="toggleProfile()">✏️ CAMBIAR DATOS</button></div><div id="profileEdit" class="profile-edit"><label>Usuario</label><input id="editUser" value="LUCIANO"><label>Correo</label><input id="editEmail" value="WSLUCIANO@HOTMAIL.COM"><label>Nueva clave</label><input id="editPassword" type="password" placeholder="Dejar vacío para no cambiar"><button onclick="saveProfile()">GUARDAR PERFIL</button></div></div>'''

NEW_CONNECTION_CARD = '''<div class="profile-card"><div class="profile-title"><h2>🔐 Conexión API</h2><span class="eyebrow">OddsPapi</span></div><div class="profile-grid"><div class="profile-item">PROVEEDOR<b>OddsPapi</b></div><div class="profile-item">CONEXIÓN<b>🟢 CONFIGURABLE</b></div><div class="profile-item">API KEY<b>••••••••</b></div><div class="profile-item">ESTADO<b id="apiConnectionStatus">⚪ NO PROBADA</b></div></div><div class="profile-actions"><a class="small-button" href="/provider-accounts" style="display:inline-block;text-decoration:none;background:#172033;color:white;border-radius:9px;padding:8px 10px;font-weight:800">🔐 PROBAR CONEXIÓN</a></div><div class="quote-meta" style="margin-top:9px">Aquí se prueba y administra la conexión real con OddsPapi. La API Key se introduce en el formulario seguro del proveedor.</div></div>'''


def apply_product_branding(html: str) -> str:
    """Apply product branding and improve the main dashboard connection card."""
    for legacy in LEGACY_PRODUCT_NAMES:
        html = html.replace(legacy, PRODUCT_NAME)
    html = html.replace(OLD_PROFILE_CARD, NEW_CONNECTION_CARD)
    return html
