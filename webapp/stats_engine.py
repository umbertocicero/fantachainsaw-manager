"""
Motore di calcolo statistiche per il Consigliere Fanta Asta.

Combina:
- Quotazioni ufficiali (FVM, quotazione d'asta Qt.A) da un file
  "Quotazioni_Fantacalcio_*.xlsx" (foglio "Tutti").
- Statistiche reali di rendimento da uno o più file
  "Voti_Fantacalcio_*_Giornata_N.xlsx" (foglio "Fantacalcio"), con le colonne
  ufficiali: Cod., Ruolo, Nome, Voto, Gf (gol fatti), Gs (gol subiti),
  Rp (rigori parati), Rs (rigori sbagliati), Rf (rigori segnati/fatti),
  Au (autogol), Amm (ammonizioni), Esp (espulsioni), Ass (assist).

Per ogni giocatore viene calcolato un fantavoto per singola partita usando i
classici bonus/malus del fantacalcio (pesi configurabili), poi aggregato in
una "fantamedia" sull'intero storico caricato. Il punteggio finale ("valore")
usato per ordinare i consigli combina questa fantamedia con la quotazione
d'asta (Qt.A), per privilegiare giocatori forti E convenienti.
"""
import json
from pathlib import Path

import openpyxl

RUOLO_NOME = {"P": "Portiere", "D": "Difensore", "C": "Centrocampista", "A": "Attaccante"}
RUOLI = ["P", "D", "C", "A"]

# Pesi di default = bonus/malus "classici" del fantacalcio. Tutti modificabili
# dall'utente nell'app (pannello "Calcolo consigli").
DEFAULT_WEIGHTS = {
    "gol_fatto": 3.0,
    "assist": 1.0,
    "ammonizione": -0.5,
    "espulsione": -1.0,
    "autogol": -2.0,
    "rigore_parato": 3.0,
    "rigore_sbagliato": -3.0,
    "gol_subito_portiere": -1.0,
    "mod_difesa_attivo": True,
    "bonus_rigorista": 0.3,
    "shrink_k": 3.0,
}


def _mod_difesa(gol_subiti):
    """Modificatore difesa (solo Portieri/Difensori): premia il clean sheet e
    penalizza le partite con molti gol subiti. Tabella standard usata dalle
    leghe che adottano questa regola facoltativa:
    0 gol subiti -> +1, 1 gol subito -> 0, poi -1 per ogni gol subito in più.
    """
    gs = gol_subiti or 0
    if gs <= 0:
        return 1.0
    if gs == 1:
        return 0.0
    return -(gs - 1)


def load_quotazioni(path):
    """Legge il file Quotazioni (foglio 'Tutti') -> dict id -> dati base."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb["Tutti"]
        players = {}
        for row in ws.iter_rows(min_row=3, values_only=True):
            if not row or row[0] is None:
                continue
            (pid, ruolo, ruolo_m, nome, squadra, qta, qti, diff, qta_m, qti_m, diff_m, fvm, fvm_m) = row
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                continue
            players[pid] = {
                "id": pid,
                "ruolo": ruolo,
                "ruolo_nome": RUOLO_NOME.get(ruolo, ruolo),
                "ruolo_mantra": ruolo_m,
                "nome": nome,
                "squadra": squadra,
                "qta": qta or 0,
                "qti": qti or 0,
                "fvm": fvm or 0,
                "fvm_m": fvm_m or 0,
            }
        return players
    finally:
        wb.close()


def _parse_voto(raw):
    """Ritorna (voto_float, stimato_bool) oppure (None, False) se non ha
    giocato (cella vuota o 'S.V.')."""
    if raw is None:
        return None, False
    if isinstance(raw, (int, float)):
        return float(raw), False
    testo = str(raw).strip()
    if not testo or testo.upper() in ("S.V.", "SV", "-"):
        return None, False
    stimato = "*" in testo
    testo = testo.replace("*", "").replace(",", ".")
    try:
        return float(testo), stimato
    except ValueError:
        return None, False


def parse_voti_file(path):
    """Legge un file Voti (foglio 'Fantacalcio') e ritorna una lista di righe
    grezze {id, ruolo, voto, stimato, gf, gs, rp, rs, rf, au, amm, esp, ass}."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb["Fantacalcio"] if "Fantacalcio" in wb.sheetnames else wb.worksheets[0]
        righe = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            if not row:
                continue
            cod, ruolo = row[0], row[1]
            if not isinstance(cod, (int, float)) or ruolo not in RUOLI:
                continue  # salta titoli, intestazioni squadra, header e allenatori (ALL)
            voto, stimato = _parse_voto(row[3])
            if voto is None:
                continue  # non ha giocato quella giornata
            righe.append({
                "id": int(cod),
                "ruolo": ruolo,
                "voto": voto,
                "stimato": stimato,
                "gf": row[4] or 0,
                "gs": row[5] or 0,
                "rp": row[6] or 0,
                "rs": row[7] or 0,
                "rf": row[8] or 0,
                "au": row[9] or 0,
                "amm": row[10] or 0,
                "esp": row[11] or 0,
                "ass": row[12] or 0,
            })
        return righe
    finally:
        wb.close()


# Mappatura dei codici numerici "events" del feed live di
# https://github.com/andregri/fantacalcio-voti-live-js (JSON esportato con
# `npx fantacalcio-voti-live <giornata> > giornata.json`), ricavata per
# reverse engineering sul file di esempio del repo (test_data/data.json:
# 8 partite, 269 giocatori) e verificata contro i risultati reali.
#
# Verifiche effettuate:
#  * gol: in tutte e 8 le partite il conteggio dei codici 3 + 9 + 10
#    (autogol accreditato alla squadra avversaria) combacia ESATTAMENTE con
#    goalHome/goalAway. Il codice 3 NON include già i rigori.
#  * gol subito: il codice 4 compare solo sui portieri (34 occorrenze) e
#    combacia sempre con i gol subiti dalla squadra.
#  * assist: i codici 20/21/22/23 cadono nel 100% dei casi (27/27) nello
#    stesso minuto di un gol della propria squadra, non superano mai il
#    numero di gol della squadra e non ricadono mai sul marcatore stesso.
#    Sono quindi varianti dello stesso bonus e vanno contati tutti.
#  * 14/15 = sostituzioni: compaiono 77 volte ciascuno, esattamente sui 77
#    giocatori che hanno il campo `substitutionId`. Ignorati.
#  * 11/12 cadono sempre (7/7) nello stesso minuto di un gol DELLO STESSO
#    giocatore e 17 sempre (3/3) nello stesso minuto della sua sostituzione:
#    sono qualificatori di un evento già conteggiato, vanno ignorati per non
#    contare due volte lo stesso gol.
#  * il codice 16 (1 sola occorrenza) resta non identificato.
#
# Limite noto: nel campione nessun codice non mappato compare su un portiere,
# quindi il codice di "rigore parato" non è deducibile; analogamente non è
# identificabile "rigore sbagliato". Con questa fonte rp/rs restano a 0.
LIVE_EVENT_GOL_FATTO = 3
LIVE_EVENT_GOL_SUBITO = 4  # solo sul portiere
LIVE_EVENT_AMMONIZIONE = 1
LIVE_EVENT_ESPULSIONE = 2
LIVE_EVENT_AUTOGOL = 10
LIVE_EVENT_RIGORE_SEGNATO = 9
# Varianti dello stesso bonus assist (probabilmente distinte per tipo di
# passaggio: azione, calcio piazzato, ecc.). Vanno sommate.
LIVE_EVENT_ASSIST = (20, 21, 22, 23)


def parse_live_json_file(path):
    """Legge un file JSON esportato dal tool 'fantacalcio-voti-live-js'
    (https://github.com/andregri/fantacalcio-voti-live-js), formato
    `{"protoData": [{"playersHome": [...], "playersAway": [...], ...}]}`, e
    lo converte nella stessa struttura a righe usata da parse_voti_file:
    {id, ruolo, voto, stimato, gf, gs, rp, rs, rf, au, amm, esp, ass}.

    Nota: rp (rigori parati) e rs (rigori sbagliati) restano sempre a 0 con
    questa fonte perché non è stato possibile identificare con certezza i
    codici evento corrispondenti (vedi commento sopra a LIVE_EVENT_*)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    righe = []
    for match in data.get("protoData", []):
        for side in ("playersHome", "playersAway"):
            for p in match.get(side, []):
                ruolo = p.get("position")
                if ruolo not in RUOLI:
                    continue  # salta l'allenatore ("ALL")
                voto_raw = p.get("vote")
                if not isinstance(voto_raw, (int, float)) or not (0 < voto_raw <= 10):
                    continue  # non ha giocato o valore anomalo nel feed
                events = p.get("events") or []
                gf = events.count(LIVE_EVENT_GOL_FATTO) + events.count(LIVE_EVENT_RIGORE_SEGNATO)
                righe.append({
                    "id": int(p["id"]),
                    "ruolo": ruolo,
                    "voto": float(voto_raw),
                    "stimato": False,
                    "gf": gf,
                    "gs": events.count(LIVE_EVENT_GOL_SUBITO),
                    "rp": 0,
                    "rs": 0,
                    "rf": events.count(LIVE_EVENT_RIGORE_SEGNATO),
                    "au": events.count(LIVE_EVENT_AUTOGOL),
                    "amm": events.count(LIVE_EVENT_AMMONIZIONE),
                    "esp": events.count(LIVE_EVENT_ESPULSIONE),
                    "ass": sum(events.count(c) for c in LIVE_EVENT_ASSIST),
                })
    return righe


def parse_giornata_file(path):
    """Dispatcher: legge una giornata di voti da .xlsx (export ufficiale) o
    .json (feed live di fantacalcio-voti-live-js), in base all'estensione."""
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return parse_live_json_file(path)
    return parse_voti_file(path)


def _fantavoto_delta(riga, weights):
    """Bonus/malus (senza il voto base) di una singola partita."""
    ruolo = riga["ruolo"]
    delta = (
        riga["gf"] * weights["gol_fatto"]
        + riga["ass"] * weights["assist"]
        + riga["amm"] * weights["ammonizione"]
        + riga["esp"] * weights["espulsione"]
        + riga["au"] * weights["autogol"]
        + riga["rp"] * weights["rigore_parato"]
        + riga["rs"] * weights["rigore_sbagliato"]
    )
    if ruolo == "P":
        delta += riga["gs"] * weights["gol_subito_portiere"]
    if weights.get("mod_difesa_attivo", True) and ruolo in ("P", "D"):
        delta += _mod_difesa(riga["gs"])
    return delta


def aggregate_stats(voti_rows_per_giornata, weights):
    """Aggrega tutte le giornate caricate -> dict id -> statistiche stagionali."""
    agg = {}
    for righe in voti_rows_per_giornata:
        for r in righe:
            pid = r["id"]
            a = agg.setdefault(pid, {
                "ruolo": r["ruolo"], "partite": 0, "somma_voto": 0.0, "somma_delta": 0.0,
                "gol": 0, "assist": 0, "ammonizioni": 0, "espulsioni": 0, "autogol": 0,
                "rigori_parati": 0, "rigori_sbagliati": 0, "rigori_segnati": 0, "gol_subiti": 0,
            })
            a["partite"] += 1
            a["somma_voto"] += r["voto"]
            a["somma_delta"] += _fantavoto_delta(r, weights)
            a["gol"] += r["gf"]
            a["assist"] += r["ass"]
            a["ammonizioni"] += r["amm"]
            a["espulsioni"] += r["esp"]
            a["autogol"] += r["au"]
            a["rigori_parati"] += r["rp"]
            a["rigori_sbagliati"] += r["rs"]
            a["rigori_segnati"] += r["rf"]
            a["gol_subiti"] += r["gs"]
    return agg


def compute_player_value(fantamedia_corretta, gol, assist, qta, partite_valutate=0):
    """Valutazione orientata a vincere il fantacalcio.

    La priorità va alla performance reale (media + gol + assist). Il costo
    riduce solo leggermente il punteggio, così un giocatore forte resta davanti
    a un cheap player mediocre.
    """
    if fantamedia_corretta is None:
        return 0.0

    base = fantamedia_corretta * 12.0 + gol * 18.0 + assist * 7.0
    stability = 1.0 + min(max(partite_valutate, 0), 12) * 0.03
    price_penalty = max(qta, 1) * 0.75
    return round(base * stability - price_penalty, 4)


def build_players(quotazioni_path, voti_paths, weights=None):
    """Funzione principale: legge quotazioni + tutte le giornate di voti e
    ritorna la lista di giocatori con statistiche e punteggio 'valore'."""
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    players = load_quotazioni(quotazioni_path)

    voti_rows_per_giornata = [parse_giornata_file(p) for p in voti_paths]
    agg = aggregate_stats(voti_rows_per_giornata, weights)

    # fantamedia grezza (senza correzione) per calcolare la media di ruolo,
    # usata come "prior" nella correzione bayesiana (shrinkage) per i
    # giocatori con poche partite valutate.
    fantamedia_grezza = {}
    for pid, a in agg.items():
        if a["partite"] > 0:
            fantamedia_grezza[pid] = (a["somma_voto"] + a["somma_delta"]) / a["partite"]

    media_per_ruolo = {}
    for ruolo in RUOLI:
        valori = [fantamedia_grezza[pid] for pid, a in agg.items() if a["ruolo"] == ruolo and pid in fantamedia_grezza]
        media_per_ruolo[ruolo] = sum(valori) / len(valori) if valori else 6.0

    shrink_k = weights.get("shrink_k", 3.0)
    bonus_rigorista = weights.get("bonus_rigorista", 0.0)

    for pid, p in players.items():
        a = agg.get(pid)
        p["partite_valutate"] = a["partite"] if a else 0
        if a and a["partite"] > 0:
            fantamedia = fantamedia_grezza[pid]
            media_ruolo = media_per_ruolo.get(p["ruolo"], 6.0)
            fantamedia_corretta = (fantamedia * a["partite"] + media_ruolo * shrink_k) / (a["partite"] + shrink_k)
            rigorista = a["rigori_segnati"] > 0 or a["rigori_sbagliati"] > 0
            if rigorista:
                fantamedia_corretta += bonus_rigorista

            p["media_voto"] = round(a["somma_voto"] / a["partite"], 2)
            p["fantamedia"] = round(fantamedia, 2)
            p["fantamedia_corretta"] = round(fantamedia_corretta, 2)
            p["gol"] = a["gol"]
            p["assist"] = a["assist"]
            p["ammonizioni"] = a["ammonizioni"]
            p["espulsioni"] = a["espulsioni"]
            p["autogol"] = a["autogol"]
            p["rigori_parati"] = a["rigori_parati"]
            p["rigori_sbagliati"] = a["rigori_sbagliati"]
            p["rigori_segnati"] = a["rigori_segnati"]
            p["gol_subiti"] = a["gol_subiti"]
            p["rigorista"] = rigorista
            p["stima"] = False

            rating_scaled = max((fantamedia_corretta - 4.0) * 20.0, 1.0)
        else:
            # nessun dato reale disponibile (es. nuovo acquisto/svincolato):
            # stima grezza basata solo sulla quotazione FVM ufficiale.
            p["media_voto"] = None
            p["fantamedia"] = None
            p["fantamedia_corretta"] = None
            p["gol"] = p["assist"] = p["ammonizioni"] = p["espulsioni"] = 0
            p["autogol"] = p["rigori_parati"] = p["rigori_sbagliati"] = p["rigori_segnati"] = p["gol_subiti"] = 0
            p["rigorista"] = False
            p["stima"] = True
            rating_scaled = max(p["fvm"], 1.0)

        prezzo = max(p["qta"], 1)
        p["valore"] = compute_player_value(
            p.get("fantamedia_corretta"),
            p.get("gol", 0),
            p.get("assist", 0),
            prezzo,
            p.get("partite_valutate", 0),
        )

    return sorted(players.values(), key=lambda p: -p["valore"])
