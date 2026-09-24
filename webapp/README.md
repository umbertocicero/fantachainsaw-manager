# webapp

Codice dell'applicazione Flask "Fanta Asta Live - Consigliere".

Per la descrizione del progetto, i requisiti e le istruzioni di avvio vedi il
[README principale del repo](../README.md).

## File principali

- `app.py` — API Flask: upload dei file, ricalcolo, gestione asta
  (draft/undraft/reset), configurazione budget e slot, persistenza in `data/`.
- `stats_engine.py` — motore di calcolo puro (nessuna dipendenza da Flask):
  parsing di quotazioni/voti (`.xlsx` e feed live `.json`) e calcolo di
  fantamedia corretta, bonus rigorista e indice di valore.
- `build_data.py` — CLI che rigenera `data/players.json` dai soli file Excel
  di default nella root del repo, senza avviare il server:

  ```powershell
  python build_data.py
  ```

- `templates/index.html`, `static/app.js`, `static/style.css` — interfaccia.

## Avvio rapido

```powershell
python app.py
```

Server su [http://127.0.0.1:5050](http://127.0.0.1:5050).

