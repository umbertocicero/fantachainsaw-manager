"""
Rigenera webapp/data/players.json dai file Excel presenti nella cartella
principale del repo (quotazioni + voti dell'ultima giornata disponibile).

Per ricalcolare usando più giornate di voti, pesi personalizzati o file
caricati dall'utente, usa invece l'app web (pannello "Calcolo consigli" ->
"Ricalcola"), che si appoggia allo stesso motore in stats_engine.py.

Esegui con:
    python build_data.py
"""
import json
from pathlib import Path

import stats_engine

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

QUOTAZIONI_FILE = ROOT / "Quotazioni_Fantacalcio_Stagione_2026_27.xlsx"
VOTI_FILE = ROOT / "Voti_Fantacalcio_Stagione_2026_27_Giornata_5.xlsx"


def main():
    out = stats_engine.build_players(QUOTAZIONI_FILE, [VOTI_FILE], stats_engine.DEFAULT_WEIGHTS)
    with open(DATA_DIR / "players.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Scritti {len(out)} giocatori in {DATA_DIR / 'players.json'}")


if __name__ == "__main__":
    main()
