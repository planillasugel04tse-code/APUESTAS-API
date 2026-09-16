from __future__ import annotations

# UI/behavior layer inspired by the documented scanner capabilities of
# BetBurger, SureBet.com, RebelBetting, OddsJam and BetHero.  It deliberately
# stays provider-agnostic: PREMATCH and LIVE remain separate API flows.

SUREBET_MARKET_GROUPS = {
    "1X2": {"1x2", "moneyline", "match_winner", "win_draw_win"},
    "DOBLE OPORTUNIDAD": {"double_chance", "dc"},
    "DNB": {"dnb", "draw_no_bet"},
    "HÁNDICAP": {"asian_handicap", "european_handicap", "ah", "handicap", "spread"},
    "TOTALES": {"total", "goals", "over_under"},
    "BTTS": {"btts", "both_teams_to_score"},
    "TEAM TOTAL": {"team_total"},
    "CÓRNERS": {"corners"},
    "TARJETAS": {"cards"},
}


def market_group(market: object) -> str:
    text = str(market or "").strip().lower().replace(" ", "_")
    for group, aliases in SUREBET_MARKET_GROUPS.items():
        if text in aliases or any(text.startswith(alias + "_") for alias in aliases):
            return group
    return "OTROS"


_SCANNER_JS = r'''(()=>{
const F={market:'ALL',bookmaker:'ALL',minProfit:0,sort:'profit',excludeQuarter:false,excludeRefund:false,required:[]};
const q=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>\'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function marketGroup(m){const x=String(m||'').toLowerCase().replaceAll(' ','_');if(/1x2|moneyline|match_winner|win_draw_win/.test(x))return '1X2';if(/double_chance|^dc/.test(x))return 'DOBLE OPORTUNIDAD';if(/dnb|draw_no_bet/.test(x))return 'DNB';if(/asian_handicap|european_handicap|^ah|handicap|spread/.test(x))return 'HÁNDICAP';if(/total|goals|over_under/.test(x))return 'TOTALES';if(/btts|both_teams/.test(x))return 'BTTS';if(/team_total/.test(x))return 'TEAM TOTAL';if(/corner/.test(x))return 'CÓRNERS';if(/card/.test(x))return 'TARJETAS';return 'OTROS'}
function inject(){const host=q('#surebet-section');if(!host||q('#scanner-filters'))return;const el=document.createElement('div');el.id='scanner-filters';el.className='scanner-filters';el.innerHTML=`<div class="scanner-filter-title">🔎 FILTROS AVANZADOS</div><div class="scanner-filter-grid"><label>MERCADO<select id="sf-market"><option value="ALL">TODOS</option><option>1X2</option><option>DOBLE OPORTUNIDAD</option><option>DNB</option><option>HÁNDICAP</option><option>TOTALES</option><option>BTTS</option><option>TEAM TOTAL</option><option>CÓRNERS</option><option>TARJETAS</option><option>OTROS</option></select></label><label>CASA<select id="sf-book"><option value="ALL">TODAS</option></select></label><label>BENEFICIO MÍNIMO %<input id="sf-profit" type="number" min="0" step="0.1" value="0"></label><label>ORDEN<select id="sf-sort"><option value="profit">Mayor beneficio</option><option value="league">Liga</option><option value="market">Mercado</option></select></label><label class="check"><input id="sf-quarter" type="checkbox"> Excluir líneas cuartos</label><label class="check"><input id="sf-refund" type="checkbox"> Excluir posibles reembolsos</label></div><div class="scanner-filter-actions"><button id="sf-apply">APLICAR FILTROS</button><button id="sf-reset">RESTABLECER</button><span id="sf-count" class="muted"></span></div>`;const ref=q('.surebet-filters');(ref||host).insertAdjacentElement('afterend',el);['sf-market','sf-book','sf-profit','sf-sort','sf-quarter','sf-refund'].forEach(id=>q('#'+id)?.addEventListener('change',apply));q('#sf-apply')?.addEventListener('click',apply);q('#sf-reset')?.addEventListener('click',()=>{['sf-market','sf-book','sf-sort'].forEach(id=>q('#'+id).value=id==='sf-book'||id==='sf-market'?'ALL':'profit');q('#sf-profit').value='0';q('#sf-quarter').checked=false;q('#sf-refund').checked=false;apply()});}
function populateBooks(rows){const s=q('#sf-book');if(!s)return;const vals=[...new Set(rows.flatMap(o=>Object.values(o.outcomes||{}).map(x=>x.bookmaker).filter(Boolean)))].sort();const old=s.value;s.innerHTML='<option value="ALL">TODAS</option>'+vals.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');if(vals.includes(old))s.value=old}
function filtered(rows){const m=q('#sf-market')?.value||'ALL',b=q('#sf-book')?.value||'ALL',min=Number(q('#sf-profit')?.value||0)/100,eq=q('#sf-quarter')?.checked,er=q('#sf-refund')?.checked;let out=rows.filter(o=>{const p=Number(o.profit_margin||0),mg=marketGroup(o.market),books=Object.values(o.outcomes||{}).map(x=>String(x.bookmaker||''));if(p<min)return false;if(m!=='ALL'&&mg!==m)return false;if(b!=='ALL'&&!books.includes(b))return false;if(eq&&/\.25|\.75|quarter/i.test(String(o.line??'')))return false;if(er&&/dnb|double_chance|refund|push/i.test(String(o.market||'')))return false;return true});const s=q('#sf-sort')?.value||'profit';out.sort((a,z)=>s==='profit'?Number(z.profit_margin||0)-Number(a.profit_margin||0):s==='league'?String(a.competition||'').localeCompare(String(z.competition||'')):String(a.market||'').localeCompare(String(z.market||'')));return out}
function apply(){if(!window.SB||!SB.data)return;const rows=Array.isArray(SB.data.opportunities)?SB.data.opportunities.slice():[];populateBooks(rows);const out=filtered(rows);const c=q('#sf-count');if(c)c.textContent=`Mostrando ${out.length} de ${rows.length}`;const old=SB.data.opportunities;SB.data.opportunities=out;window.renderSurebet(SB.data);SB.data.opportunities=old}
function liveRefresh(){if(!window.SB||SB.data?.mode!=='live')return;if(document.visibilityState==='hidden')return;window.loadSurebetLive?.()}
window.addEventListener('DOMContentLoaded',()=>{inject();setTimeout(()=>apply(),400);setInterval(()=>{if(window.SB?.data?.mode==='live')liveRefresh()},10000)});
new MutationObserver(()=>inject()).observe(document.documentElement,{childList:true,subtree:true});
})();'''

_SCANNER_CSS = '''.scanner-filters{border:1px solid #dfe5ee;background:#f8fafc;border-radius:12px;padding:13px;margin:12px 0}.scanner-filter-title{font-size:12px;font-weight:900;margin-bottom:10px}.scanner-filter-grid{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:9px}.scanner-filter-grid label{font-size:10px;font-weight:900;color:#596579}.scanner-filter-grid select,.scanner-filter-grid input[type=number]{display:block;width:100%;margin-top:4px;padding:8px;border:1px solid #ccd6e5;border-radius:8px;background:white}.scanner-filter-grid .check{display:flex;align-items:center;gap:6px;padding-top:19px}.scanner-filter-grid .check input{width:auto}.scanner-filter-actions{display:flex;gap:8px;align-items:center;margin-top:10px}.scanner-filter-actions button{background:white}.scanner-filter-actions button:first-child{background:#101827;color:white}.scanner-filter-actions .muted{font-size:11px}@media(max-width:900px){.scanner-filter-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.scanner-filter-grid{grid-template-columns:1fr}}'''


def scanner_css() -> str:
    return _SCANNER_CSS


def scanner_js() -> str:
    return _SCANNER_JS
