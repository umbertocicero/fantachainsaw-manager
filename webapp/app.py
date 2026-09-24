"""
Fanta Asta Live - Consigliere
Semplice web app Flask che, a partire dalle quotazioni ufficiali e dalle
statistiche reali di voto (gol, assist, cartellini, rigori, modificatore
difesa), consiglia quali giocatori scegliere durante un'asta del
fantacalcio, tenendo conto di budget residuo e ruoli ancora da riempire.
"""
import json
import shutil
import threading
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

import stats_engine

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_FILE = BASE_DIR / "data" / "players.json"
STATE_FILE = BASE_DIR / "data" / "state.json"
PESI_FILE = BASE_DIR / "data" / "pesi.json"
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR = BASE_DIR / "uploads"
VOTI_DIR = UPLOAD_DIR / "voti"
UPLOAD_QUOTAZIONI = UPLOAD_DIR / "quotazioni.xlsx"
UPLOAD_DIR.mkdir(exist_ok=True)
VOTI_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_QUOTAZIONI_FILE = ROOT_DIR / "Quotazioni_Fantacalcio_Stagione_2026_27.xlsx"
DEFAULT_VOTI_FILE = ROOT_DIR / "Voti_Fantacalcio_Stagione_2026_27_Giornata_5.xlsx"

# Al primo avvio, copia la giornata di voti già presente nel repo nella
# cartella upload, così compare da subito nell'elenco "giornate caricate" e
# l'utente può aggiungerne altre senza perdere quella di partenza.
if not any(VOTI_DIR.iterdir()) and DEFAULT_VOTI_FILE.exists():
    shutil.copy(DEFAULT_VOTI_FILE, VOTI_DIR / DEFAULT_VOTI_FILE.name)

RUOLI = ["P", "D", "C", "A"]
DEFAULT_CONFIG = {
    "budget_totale": 500,
    "slot": {"P": 3, "D": 8, "C": 8, "A": 6},
}

app = Flask(__name__)
_lock = threading.Lock()


def load_pesi():
    if PESI_FILE.exists():
        with open(PESI_FILE, encoding="utf-8") as f:
            return {**stats_engine.DEFAULT_WEIGHTS, **json.load(f)}
    return dict(stats_engine.DEFAULT_WEIGHTS)


def save_pesi(pesi):
    with open(PESI_FILE, "w", encoding="utf-8") as f:
        json.dump(pesi, f, ensure_ascii=False, indent=1)


def quotazioni_path():
    return UPLOAD_QUOTAZIONI if UPLOAD_QUOTAZIONI.exists() else DEFAULT_QUOTAZIONI_FILE


def voti_paths():
    file_list = sorted(list(VOTI_DIR.glob("*.xlsx")) + list(VOTI_DIR.glob("*.json")))
    return file_list if file_list else [DEFAULT_VOTI_FILE]


def rebuild_players(pesi_override=None):
    """Ricalcola players.json usando i file attualmente caricati (upload o
    default) e i pesi correnti (eventualmente aggiornati)."""
    global PLAYERS
    pesi = load_pesi()
    if pesi_override:
        pesi.update(pesi_override)
        save_pesi(pesi)
    with _lock:
        out = stats_engine.build_players(quotazioni_path(), voti_paths(), pesi)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        PLAYERS = {p["id"]: p for p in out}
    return {
        "n_giocatori": len(out),
        "n_giornate": len(voti_paths()),
        "giornate": [p.name for p in voti_paths()],
        "quotazioni_personalizzate": UPLOAD_QUOTAZIONI.exists(),
        "pesi": pesi,
    }


PLAYERS = {}
if DATA_FILE.exists():
    with open(DATA_FILE, encoding="utf-8") as f:
        PLAYERS = {p["id"]: p for p in json.load(f)}

# Ricalcola subito all'avvio, così lo schema dei dati (fantamedia, gol,
# assist, rigorista, ecc.) è sempre allineato al motore corrente anche se
# players.json era stato generato da una versione precedente.
try:
    rebuild_players()
except Exception as exc:  # pragma: no cover - non deve mai bloccare l'avvio
    print(f"Attenzione: ricalcolo iniziale fallito ({exc}), uso i dati salvati.")




def _default_state():
    return {"config": DEFAULT_CONFIG, "draft": {}}  # draft: {id: {"da": "me"/"altri", "prezzo": int}}


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return _default_state()


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def compute_summary(state):
    """Calcola budget/slot residui per la squadra 'me'."""
    config = state["config"]
    draft = state["draft"]
    speso = 0
    presi_per_ruolo = {r: 0 for r in RUOLI}
    for pid_str, info in draft.items():
        if info["da"] != "me":
            continue
        pid = int(pid_str)
        speso += info.get("prezzo", 0)
        ruolo = PLAYERS[pid]["ruolo"]
        presi_per_ruolo[ruolo] = presi_per_ruolo.get(ruolo, 0) + 1

    budget_rimanente = config["budget_totale"] - speso
    slot_rimanenti = {r: max(config["slot"][r] - presi_per_ruolo.get(r, 0), 0) for r in RUOLI}
    slot_rimanenti_totali = sum(slot_rimanenti.values())

    return {
        "budget_totale": config["budget_totale"],
        "speso": speso,
        "budget_rimanente": budget_rimanente,
        "presi_per_ruolo": presi_per_ruolo,
        "slot_per_ruolo": config["slot"],
        "slot_rimanenti": slot_rimanenti,
        "slot_rimanenti_totali": slot_rimanenti_totali,
    }


def player_with_state(p, draft):
    d = dict(p)
    info = draft.get(str(p["id"]))
    d["preso_da"] = info["da"] if info else None
    d["prezzo_pagato"] = info.get("prezzo") if info else None
    return d


@app.get("/")
def index():
    from flask import render_template

    return render_template("index.html")


@app.get("/api/players")
def api_players():
    state = load_state()
    draft = state["draft"]
    ruolo = request.args.get("ruolo")
    q = request.args.get("q", "").strip().lower()
    solo_liberi = request.args.get("liberi") == "1"

    items = list(PLAYERS.values())
    if ruolo:
        items = [p for p in items if p["ruolo"] == ruolo]
    if q:
        items = [p for p in items if q in p["nome"].lower() or q in p["squadra"].lower()]
    result = [player_with_state(p, draft) for p in items]
    if solo_liberi:
        result = [p for p in result if p["preso_da"] is None]
    result.sort(key=lambda p: -p["valore"])
    return jsonify(result)


@app.get("/api/state")
def api_state():
    state = load_state()
    return jsonify(compute_summary(state))


@app.post("/api/config")
def api_config():
    body = request.get_json(force=True)
    with _lock:
        state = load_state()
        budget = int(body.get("budget_totale", state["config"]["budget_totale"]))
        slot = state["config"]["slot"].copy()
        for r in RUOLI:
            if r in body.get("slot", {}):
                slot[r] = int(body["slot"][r])
        state["config"] = {"budget_totale": budget, "slot": slot}
        save_state(state)
        return jsonify(compute_summary(state))


@app.post("/api/draft")
def api_draft():
    body = request.get_json(force=True)
    pid = int(body["id"])
    da = body.get("da", "me")
    prezzo = int(body.get("prezzo", 0) or 0)
    if pid not in PLAYERS:
        return jsonify({"errore": "giocatore non trovato"}), 404
    with _lock:
        state = load_state()
        state["draft"][str(pid)] = {"da": da, "prezzo": prezzo if da == "me" else 0}
        save_state(state)
        return jsonify(compute_summary(state))


@app.post("/api/undraft")
def api_undraft():
    body = request.get_json(force=True)
    pid = str(int(body["id"]))
    with _lock:
        state = load_state()
        state["draft"].pop(pid, None)
        save_state(state)
        return jsonify(compute_summary(state))


@app.post("/api/reset")
def api_reset():
    with _lock:
        state = load_state()
        state["draft"] = {}
        save_state(state)
        return jsonify(compute_summary(state))


@app.get("/api/suggestions")
def api_suggestions():
    """Consiglia i migliori giocatori ancora liberi, per ruolo, in base alla
    fantamedia calcolata sulle giornate caricate (voto + gol, assist,
    ammonizioni/espulsioni, autogol, rigori, modificatore difesa, bonus
    rigoristi) rapportata alla quotazione d'asta, e al budget/slot residui."""
    state = load_state()
    draft = state["draft"]
    summary = compute_summary(state)
    ruolo = request.args.get("ruolo")
    limit = int(request.args.get("limit", 8))

    slot_rimanenti_totali = max(summary["slot_rimanenti_totali"], 1)
    # riserva almeno 1 credito per ogni altro slot da riempire
    budget_rimanente = summary["budget_rimanente"]

    ruoli_da_considerare = [ruolo] if ruolo else [r for r in RUOLI if summary["slot_rimanenti"][r] > 0]

    risposta = {}
    for r in ruoli_da_considerare:
        liberi = [p for p in PLAYERS.values() if p["ruolo"] == r and str(p["id"]) not in draft]
        altri_slot_rimanenti = max(slot_rimanenti_totali - (1 if summary["slot_rimanenti"].get(r, 0) > 0 else 0), 0)
        prezzo_massimo = max(budget_rimanente - altri_slot_rimanenti, 1)
        liberi.sort(key=lambda p: -p["valore"])
        consigliati = []
        for p in liberi:
            if len(consigliati) >= limit:
                break
            d = dict(p)
            d["alla_portata"] = p["qta"] <= prezzo_massimo
            consigliati.append(d)
        risposta[r] = consigliati
    return jsonify({"suggerimenti": risposta, "prezzo_massimo_stimato": budget_rimanente})


@app.get("/api/files")
def api_files():
    """Elenco dei file attualmente usati per il calcolo (per la UI upload)."""
    return jsonify({
        "quotazioni": {
            "nome": quotazioni_path().name,
            "personalizzata": UPLOAD_QUOTAZIONI.exists(),
        },
        "voti": [
            {"nome": p.name, "dimensione": p.stat().st_size}
            for p in voti_paths()
        ],
        "pesi": load_pesi(),
    })


@app.post("/api/upload")
def api_upload():
    """Carica un file: tipo='quotazioni' richiede un .xlsx (sostituisce
    l'attuale) oppure tipo='voti' richiede un .xlsx (export ufficiale) o un
    .json (feed live di fantacalcio-voti-live-js) e si aggiunge come nuova
    giornata, o sostituisce quella con lo stesso nome file. Non ricalcola
    automaticamente: chiama /api/recompute dopo aver caricato tutti i file
    desiderati."""
    tipo = request.form.get("tipo")
    file = request.files.get("file")
    nome_originale = file.filename.lower() if file else ""
    if tipo == "quotazioni":
        if not nome_originale.endswith(".xlsx"):
            return jsonify({"errore": "carica un file .xlsx valido"}), 400
        file.save(UPLOAD_QUOTAZIONI)
    elif tipo == "voti":
        if not (nome_originale.endswith(".xlsx") or nome_originale.endswith(".json")):
            return jsonify({"errore": "carica un file .xlsx o .json valido"}), 400
        nome = secure_filename(file.filename)
        if not nome:
            return jsonify({"errore": "nome file non valido"}), 400
        file.save(VOTI_DIR / nome)
    else:
        return jsonify({"errore": "tipo non valido (usa 'quotazioni' o 'voti')"}), 400
    return jsonify({"ok": True})


@app.post("/api/files/voti/delete")
def api_files_voti_delete():
    body = request.get_json(force=True)
    nome = secure_filename(body.get("nome", ""))
    path = VOTI_DIR / nome
    if not nome or not path.exists() or path.resolve().parent != VOTI_DIR.resolve():
        return jsonify({"errore": "file non trovato"}), 404
    path.unlink()
    return jsonify({"ok": True})


@app.post("/api/files/quotazioni/reset")
def api_files_quotazioni_reset():
    """Torna a usare il file di quotazioni di default del repo."""
    if UPLOAD_QUOTAZIONI.exists():
        UPLOAD_QUOTAZIONI.unlink()
    return jsonify({"ok": True})


@app.post("/api/recompute")
def api_recompute():
    """Rilancia il calcolo di players.json con i file/pesi correnti.
    Body JSON opzionale: {"pesi": {...override...}}."""
    body = request.get_json(silent=True) or {}
    meta = rebuild_players(body.get("pesi"))
    return jsonify(meta)


@app.post("/api/pesi/reset")
def api_pesi_reset():
    """Ripristina i pesi di default (bonus/malus classici del fantacalcio) e
    ricalcola."""
    if PESI_FILE.exists():
        PESI_FILE.unlink()
    meta = rebuild_players()
    return jsonify(meta)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
