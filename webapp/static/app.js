const RUOLI = { P: "Portiere", D: "Difensore", C: "Centrocampista", A: "Attaccante" };
let currentRuoloTab = "P";

const WEIGHT_LABELS = {
    gol_fatto: "Gol fatto",
    assist: "Assist",
    ammonizione: "Ammonizione",
    espulsione: "Espulsione",
    autogol: "Autogol",
    rigore_parato: "Rigore parato",
    rigore_sbagliato: "Rigore sbagliato",
    gol_subito_portiere: "Gol subito (portiere)",
    bonus_rigorista: "Bonus rigorista",
    shrink_k: "Prudenza pochi dati (partite 'prior')",
};

async function api(path, options) {
    const res = await fetch(path, options);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

function fmt(n, d = 1) {
    if (n === null || n === undefined) return "-";
    return Number(n).toFixed(d);
}

async function loadSummary() {
    const s = await api("/api/state");
    const grid = document.getElementById("summary-grid");
    grid.innerHTML = `
        <div class="summary-card"><div class="value">${s.budget_rimanente}</div><div class="label">Budget residuo</div></div>
        <div class="summary-card"><div class="value">${s.speso}</div><div class="label">Speso</div></div>
        <div class="summary-card"><div class="value">${s.slot_rimanenti.P}</div><div class="label">Portieri da prendere</div></div>
        <div class="summary-card"><div class="value">${s.slot_rimanenti.D}</div><div class="label">Difensori da prendere</div></div>
        <div class="summary-card"><div class="value">${s.slot_rimanenti.C}</div><div class="label">Centrocampisti da prendere</div></div>
        <div class="summary-card"><div class="value">${s.slot_rimanenti.A}</div><div class="label">Attaccanti da prendere</div></div>
    `;
    document.getElementById("cfg-budget").value = s.budget_totale;
    document.getElementById("cfg-P").value = s.slot_per_ruolo.P;
    document.getElementById("cfg-D").value = s.slot_per_ruolo.D;
    document.getElementById("cfg-C").value = s.slot_per_ruolo.C;
    document.getElementById("cfg-A").value = s.slot_per_ruolo.A;
}

async function loadSuggestions() {
    const data = await api(`/api/suggestions?ruolo=${currentRuoloTab}&limit=8`);
    const list = data.suggerimenti[currentRuoloTab] || [];
    const container = document.getElementById("suggestions-list");
    if (list.length === 0) {
        container.innerHTML = `<p style="color:var(--muted)">Nessun consiglio disponibile: hai già completato questo reparto o non ci sono giocatori liberi.</p>`;
        return;
    }
    container.innerHTML = list.map(p => `
        <div class="card">
            <span class="badge ${p.alla_portata ? "" : "no"}">${p.alla_portata ? "Alla portata" : "Costoso"}</span>
            <h3>${p.nome}</h3>
            <div class="meta">${p.squadra} · <span class="pill ${p.ruolo}">${p.ruolo}</span></div>
            <div class="stats">
                <span>FVM<b>${p.fvm}</b></span>
                <span>Qt.A<b>${p.qta}</b></span>
                <span>Fantamedia<b>${fmt(p.fantamedia_corretta, 2)}</b></span>
                <span>Gol/Ass<b>${p.gol ?? 0}/${p.assist ?? 0}</b></span>
                <span>Valore<b>${fmt(p.valore, 2)}</b></span>
            </div>
            <div class="tags">
                ${p.rigorista ? '<span class="tag rigorista">Rigorista</span>' : ""}
                ${p.stima ? '<span class="tag stima">Stima da FVM</span>' : `<span class="tag ok">${p.partite_valutate} partite valutate</span>`}
            </div>
            <div class="row-actions">
                <input type="number" class="price-input" placeholder="crediti" id="price-${p.id}" min="0">
                <button class="small" onclick="draftPlayer(${p.id}, 'me')">Prendo io</button>
                <button class="small secondary" onclick="draftPlayer(${p.id}, 'altri')">Preso da altri</button>
            </div>
        </div>
    `).join("");
}

async function loadPlayers() {
    const q = document.getElementById("search").value;
    const ruolo = document.getElementById("filter-ruolo").value;
    const liberi = document.getElementById("filter-liberi").checked ? "1" : "0";
    const params = new URLSearchParams({ q, ruolo, liberi });
    const players = await api(`/api/players?${params.toString()}`);
    const tbody = document.getElementById("players-tbody");
    tbody.innerHTML = players.map(p => {
        let rowClass = "";
        if (p.preso_da === "me") rowClass = "preso-me";
        else if (p.preso_da === "altri") rowClass = "preso-altri";
        let azioni;
        if (p.preso_da) {
            azioni = `<button class="small secondary" onclick="undraftPlayer(${p.id})">Libera</button>`;
        } else {
            azioni = `
                <div class="row-actions">
                    <input type="number" class="price-input" placeholder="crediti" id="tprice-${p.id}" min="0">
                    <button class="small" onclick="draftPlayer(${p.id}, 'me', true)">Io</button>
                    <button class="small secondary" onclick="draftPlayer(${p.id}, 'altri', true)">Altri</button>
                </div>`;
        }
        const stato = p.preso_da === "me" ? `Mio (${p.prezzo_pagato})` : p.preso_da === "altri" ? "Preso da altri" : "Libero";
        return `<tr class="${rowClass}">
            <td><span class="pill ${p.ruolo}">${p.ruolo}</span></td>
            <td>${p.nome}${p.rigorista ? ' <span class="tag rigorista">R</span>' : ""}</td>
            <td>${p.squadra}</td>
            <td>${p.qta}</td>
            <td>${p.fvm}</td>
            <td>${fmt(p.fantamedia_corretta, 2)}${p.stima ? ' <span class="tag stima">stima</span>' : ""}</td>
            <td>${p.partite_valutate ?? 0}</td>
            <td>${p.gol ?? 0}</td>
            <td>${p.assist ?? 0}</td>
            <td>${fmt(p.valore, 2)}</td>
            <td>${stato}</td>
            <td>${azioni}</td>
        </tr>`;
    }).join("");
}

async function refreshAll() {
    await Promise.all([loadSummary(), loadSuggestions(), loadPlayers()]);
}

async function draftPlayer(id, da, fromTable = false) {
    let prezzo = 0;
    if (da === "me") {
        const input = document.getElementById(fromTable ? `tprice-${id}` : `price-${id}`);
        prezzo = parseInt(input?.value || "0", 10) || 0;
    }
    await api("/api/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, da, prezzo }),
    });
    await refreshAll();
}

async function undraftPlayer(id) {
    await api("/api/undraft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
    });
    await refreshAll();
}

document.getElementById("btn-save-config").addEventListener("click", async () => {
    await api("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            budget_totale: parseInt(document.getElementById("cfg-budget").value, 10),
            slot: {
                P: parseInt(document.getElementById("cfg-P").value, 10),
                D: parseInt(document.getElementById("cfg-D").value, 10),
                C: parseInt(document.getElementById("cfg-C").value, 10),
                A: parseInt(document.getElementById("cfg-A").value, 10),
            },
        }),
    });
    await refreshAll();
});

document.getElementById("btn-reset").addEventListener("click", async () => {
    if (!confirm("Azzerare tutti i giocatori presi finora?")) return;
    await api("/api/reset", { method: "POST" });
    await refreshAll();
});

document.querySelectorAll("#suggestion-tabs .tab").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll("#suggestion-tabs .tab").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentRuoloTab = btn.dataset.ruolo;
        loadSuggestions();
    });
});

document.getElementById("search").addEventListener("input", debounce(loadPlayers, 250));
document.getElementById("filter-ruolo").addEventListener("change", loadPlayers);
document.getElementById("filter-liberi").addEventListener("change", loadPlayers);

function debounce(fn, ms) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), ms);
    };
}

// ---- Pannello dati e calcolo (upload file + pesi) ----

async function loadFiles() {
    const data = await api("/api/files");
    document.getElementById("quotazioni-info").textContent = data.quotazioni.personalizzata
        ? `File personalizzato: ${data.quotazioni.nome}`
        : `File di default: ${data.quotazioni.nome}`;

    const votiList = document.getElementById("voti-list");
    votiList.innerHTML = data.voti.map(v => `
        <li>${v.nome} (${Math.round(v.dimensione / 1024)} KB)
            <button class="small secondary" onclick="deleteVotiFile('${v.nome}')">Rimuovi</button>
        </li>
    `).join("") || "<li>Nessuna giornata caricata</li>";

    renderWeights(data.pesi);
}

function renderWeights(pesi) {
    const grid = document.getElementById("weights-grid");
    const numerici = Object.keys(WEIGHT_LABELS).map(key => `
        <label>${WEIGHT_LABELS[key]}
            <input type="number" step="0.1" id="weight-${key}" value="${pesi[key]}">
        </label>
    `).join("");
    grid.innerHTML = numerici + `
        <label class="checkbox">
            <input type="checkbox" id="weight-mod_difesa_attivo" ${pesi.mod_difesa_attivo ? "checked" : ""}>
            Modificatore difesa attivo (Portieri/Difensori)
        </label>
    `;
}

function collectWeights() {
    const pesi = {};
    for (const key of Object.keys(WEIGHT_LABELS)) {
        pesi[key] = parseFloat(document.getElementById(`weight-${key}`).value);
    }
    pesi.mod_difesa_attivo = document.getElementById("weight-mod_difesa_attivo").checked;
    return pesi;
}

async function uploadFile(tipo) {
    const input = document.getElementById(tipo === "quotazioni" ? "file-quotazioni" : "file-voti");
    const file = input.files[0];
    if (!file) {
        alert(tipo === "quotazioni" ? "Seleziona prima un file .xlsx" : "Seleziona prima un file .xlsx o .json");
        return;
    }
    const form = new FormData();
    form.append("tipo", tipo);
    form.append("file", file);
    await fetch("/api/upload", { method: "POST", body: form });
    input.value = "";
    await loadFiles();
    await recompute();
}

async function deleteVotiFile(nome) {
    await api("/api/files/voti/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome }),
    });
    await loadFiles();
    await recompute();
}

async function resetQuotazioni() {
    await api("/api/files/quotazioni/reset", { method: "POST" });
    await loadFiles();
    await recompute();
}

async function scaricaGiornataLive() {
    const input = document.getElementById("live-giornata");
    const giornata = parseInt(input.value, 10);
    if (!giornata || giornata < 1) {
        alert("Inserisci un numero di giornata valido");
        return;
    }
    const status = document.getElementById("recompute-status");
    status.textContent = `Scaricamento giornata ${giornata} in corso...`;
    const res = await fetch("/api/live/scarica", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ giornata }),
    });
    const data = await res.json();
    if (!res.ok) {
        status.textContent = "";
        alert(data.errore || "Download non riuscito");
        return;
    }
    status.textContent = `Importata giornata live: ${data.file_importato}`;
    await loadFiles();
    await refreshAll();
}

async function recompute() {
    const status = document.getElementById("recompute-status");
    status.textContent = "Ricalcolo in corso...";
    const meta = await api("/api/recompute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pesi: collectWeights() }),
    });
    status.textContent = `Calcolati ${meta.n_giocatori} giocatori su ${meta.n_giornate} giornate di voti.`;
    await refreshAll();
}

document.getElementById("btn-recompute").addEventListener("click", recompute);
document.getElementById("btn-pesi-reset").addEventListener("click", async () => {
    const meta = await api("/api/pesi/reset", { method: "POST" });
    document.getElementById("recompute-status").textContent =
        `Pesi ripristinati. Calcolati ${meta.n_giocatori} giocatori su ${meta.n_giornate} giornate di voti.`;
    await loadFiles();
    await refreshAll();
});

loadFiles();
refreshAll();
