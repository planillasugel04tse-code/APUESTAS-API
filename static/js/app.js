document.addEventListener("DOMContentLoaded", () => {
    console.log("Betting Opportunity Analyzer client initialized.");

    // Interactive Bankroll Calculator
    const bankrollInput = document.getElementById("bankroll-input");
    const bankrollDisplay = document.getElementById("bankroll-display");

    if (bankrollInput && bankrollDisplay) {
        bankrollInput.addEventListener("input", (e) => {
            const val = parseFloat(e.target.value) || 100;
            bankrollDisplay.textContent = `S/${val.toFixed(2)}`;
            updateCalculations(val);
        });
    }

    document.querySelectorAll("[data-bankroll]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = document.getElementById("calc-bankroll");
            if (input) input.value = button.getAttribute("data-bankroll") || "100";
        });
    });
});

function updateCalculations(bankroll) {
    const stakeElements = document.querySelectorAll("[data-stake-percentage]");
    stakeElements.forEach((el) => {
        const pct = parseFloat(el.getAttribute("data-stake-percentage")) || 0;
        const stakeVal = (bankroll * (pct / 100)).toFixed(2);
        el.textContent = `S/${stakeVal}`;
    });
}

// API Simulation Calculator Call
async function calculateCustomStake() {
    const bankroll = parseFloat(document.getElementById("calc-bankroll")?.value || 100);
    const oddsStr = document.getElementById("calc-odds")?.value || "2.15, 3.40, 3.60";
    const odds = oddsStr.split(",").map((o) => parseFloat(o.trim())).filter((o) => !isNaN(o));

    const resultBox = document.getElementById("calc-result-box");
    if (!resultBox) return;

    try {
        const response = await fetch("/api/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bankroll, odds, type: "surebet" })
        });

        const data = await response.json();
        if (data.success && data.result) {
            const res = data.result;
            let html = `<div style="padding: 1rem; background: rgba(15,23,42,0.8); border-radius: 8px;">`;
            html += `<h4 style="color: #10b981; margin-bottom: 0.5rem;">${res.is_surebet ? '¡Surebet Detectada!' : 'Sin Arbitraje'}</h4>`;
            html += `<p><strong>ROI:</strong> ${res.roi_percentage}%</p>`;
            html += `<p><strong>Beneficio Proyectado:</strong> S/${res.profit || 0}</p>`;
            if (res.stakes && res.stakes.length > 0) {
                html += `<ul style="margin-top: 0.5rem; padding-left: 1.2rem;">`;
                res.stakes.forEach((s) => {
                    html += `<li>Cuota ${s.odds}: Stake S/${s.stake} (${s.percentage}%) - Retorno: S/${s.payout}</li>`;
                });
                html += `</ul>`;
            }
            html += `</div>`;
            resultBox.innerHTML = html;
        } else {
            resultBox.innerHTML = `<p style="color: #f43f5e;">Error: ${data.error || 'Cálculo fallido'}</p>`;
        }
    } catch (err) {
        resultBox.innerHTML = `<p style="color: #f43f5e;">Error de conexión con la API local.</p>`;
    }
}

async function refreshRealOdds() {
    const resultBox = document.getElementById("refresh-result-box");
    if (resultBox) {
        resultBox.innerHTML = `<div style="padding: 1rem; background: rgba(15,23,42,0.8); border-radius: 8px;">Actualizando cuotas reales. Esto consume 1 request de OddsPapi.</div>`;
    }

    try {
        const response = await fetch("/api/refresh", { method: "POST" });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || "No se pudo actualizar");
        }
        const report = data.report || {};
        if (resultBox) {
            resultBox.innerHTML = `<div style="padding: 1rem; background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.35); border-radius: 8px;">Actualización completada: ${report.total_events || 0} eventos y ${report.total_opportunities || 0} oportunidades. Recargando dashboard...</div>`;
        }
        window.setTimeout(() => window.location.reload(), 900);
    } catch (err) {
        if (resultBox) {
            resultBox.innerHTML = `<p style="color: #f43f5e;">Error al actualizar cuotas reales. Revisa tu API key y cuota disponible.</p>`;
        }
    }
}
