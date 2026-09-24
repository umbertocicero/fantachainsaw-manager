# Fanta Asta Live - Consigliere

Web app (Flask) che consiglia quali giocatori scegliere durante un'asta del
fantacalcio, basandosi su statistiche reali (voti, gol, assist, cartellini,
autogol, rigori, modificatore di difesa) invece che sulla sola quotazione.

Il file `ManualeFantaAstaLive2025.pdf` descrive il funzionamento dello
strumento d'asta live di Fantacalcio.it; i consigli di questa app si basano
sui dati di quotazione e voto reali, non sul manuale.

## Funzionalità

- **Motore di calcolo trasparente** (`webapp/stats_engine.py`): per ogni
  partita calcola un fantavoto (voto base + bonus/malus) e lo aggrega in una
  fantamedia corretta con shrinkage statistico verso la media di ruolo, un
  bonus per i rigoristi e un indice di "valore" che rapporta il rendimento
  al prezzo d'asta.
- **Pesi configurabili**: dall'interfaccia puoi modificare il peso di ogni
  bonus/malus (gol, assist, cartellini, rigori, ecc.) e ricalcolare al volo.
- **Upload dei file**: puoi caricare una nuova quotazione ufficiale e più
  giornate di voti, in due formati:
  - export ufficiale Fantacalcio.it in `.xlsx`;
  - feed live in `.json` generato con
    [fantacalcio-voti-live-js](https://github.com/andregri/fantacalcio-voti-live-js)
    (`npx fantacalcio-voti-live <giornata> > giornata.json`).
- **Download automatico della giornata live**: in alternativa all'upload
  manuale, il pulsante "Scarica giornata live" nell'interfaccia lancia lo
  stesso tool (`fantacalcio-voti-live-js`) direttamente dal server e importa
  subito il risultato. Funziona solo mentre quella giornata è effettivamente
  in corso (il servizio esterno risponde 404 fuori da una partita live) e
  richiede Node.js installato (vedi Requisiti).
- **Gestione asta**: budget totale e slot per ruolo configurabili, segna i
  giocatori come "presi da te" (con prezzo) o "presi da altri" e i consigli
  si aggiornano tenendo conto del budget e degli slot residui.

## Requisiti

- Python 3.11+ (sviluppato e testato con Python 3.14)
- Le dipendenze in [requirements.txt](requirements.txt): Flask, openpyxl, pypdf
- Facoltativo: [Node.js](https://nodejs.org/) (per il pulsante "Scarica
  giornata live"; senza Node.js l'app funziona comunque con l'upload manuale
  dei file)

## Installazione

```powershell
# dalla cartella del repo
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Avvio

```powershell
.venv\Scripts\Activate.ps1
cd webapp
python app.py
```

Poi apri [http://127.0.0.1:5050](http://127.0.0.1:5050) nel browser.

Al primo avvio l'app:
- usa `Quotazioni_Fantacalcio_Stagione_2026_27.xlsx` e
  `Voti_Fantacalcio_Stagione_2026_27_Giornata_5.xlsx` presenti nella root
  del repo come dati di partenza;
- genera automaticamente `webapp/data/players.json` (non versionato).

Da lì in poi, tutti i file caricati tramite l'interfaccia finiscono in
`webapp/uploads/` (anch'essa non versionata) e sostituiscono/affiancano i
dati di partenza.

### Uso da riga di comando (senza server web)

Per rigenerare `webapp/data/players.json` una tantum, usando solo i file
Excel di default della root del repo:

```powershell
cd webapp
python build_data.py
```

## Come usare l'app

1. Imposta budget totale e slot per ruolo (Portieri/Difensori/Centrocampisti/
   Attaccanti) nel pannello di configurazione.
2. Nel pannello "Dati e calcolo consigli" puoi caricare nuove quotazioni o
   nuove giornate di voti (`.xlsx` o `.json`), scaricare automaticamente la
   giornata live in corso (se Node.js è installato), modificare i pesi dei
   bonus/malus e premere "Ricalcola".
3. Nella sezione "Consigliati per te" trovi, ruolo per ruolo, i migliori
   giocatori ancora liberi e compatibili col budget residuo.
4. Man mano che l'asta procede, segna ogni giocatore come "Preso da te" (con
   il prezzo pagato) o "Preso da altri": budget, slot residui e consigli si
   aggiornano automaticamente.

Lo stato dell'asta (giocatori presi, budget) viene salvato in
`webapp/data/state.json`; usa il pulsante "Azzera asta" nell'interfaccia (o
cancella il file) per ricominciare da zero.

## Struttura del progetto

```
webapp/
  app.py             API Flask, upload, persistenza dello stato dell'asta
  stats_engine.py     motore di calcolo (parsing file + punteggi), no Flask
  build_data.py       CLI per rigenerare players.json senza avviare il server
  templates/          index.html
  static/              app.js, style.css
  data/               (generato) players.json, state.json, pesi.json
  uploads/            (generato) file caricati dall'utente
```
