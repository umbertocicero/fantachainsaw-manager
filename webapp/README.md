# Consigliere Fanta Asta

Semplice web app (Flask) che consiglia quali giocatori scegliere durante
un'asta del fantacalcio, basandosi su:

- **Quotazioni_Fantacalcio_Stagione_2026_27.xlsx** (FVM e quotazione d'asta)
- **Voti_Fantacalcio_Stagione_2026_27_Giornata_5.xlsx** (voto dell'ultima giornata, come indicatore di forma)

Il manuale `ManualeFantaAstaLive2025.pdf` descrive solo il funzionamento dello
strumento d'asta di Fantacalcio.it (non contiene strategie di scelta), quindi
i consigli qui si basano sui dati di quotazione/voto reali.

## Come funziona

1. Imposta budget totale e numero di slot per ruolo (Portieri/Difensori/Centrocampisti/Attaccanti).
2. Nella sezione "Consigliati per te" trovi, ruolo per ruolo, i migliori giocatori
   ancora liberi, ordinati per un punteggio "valore" che combina FVM, prezzo
   d'asta e forma recente (FVM^1.5 / prezzo, con bonus/malus dal voto).
3. Man mano che l'asta procede, segna ogni giocatore come "Preso da te" (con il
   prezzo pagato) o "Preso da altri": budget, slot residui e consigli si
   aggiornano automaticamente.

## Avvio

```powershell
cd webapp
python build_data.py   # rigenera data/players.json dai file Excel
python app.py           # avvia il server su http://127.0.0.1:5050
```

Lo stato dell'asta (giocatori presi) viene salvato in `data/state.json`;
cancella il file (o usa il pulsante "Azzera asta" nell'interfaccia) per
ricominciare da zero.
