# YouTube Queue — Core Backend (v01.6.2)

Author: Duong – XDigital  
Updated: 2025-10-18

## What's in here?
- `app.py` — Flask app with persistent JSON storage and CSV logging
- `data/` — settings.json, users.json, queue.json, activity_log.csv
- `requirements.txt` — Python deps

## Run locally
```bash
pip install -r core/requirements.txt
python core/app.py
# open http://localhost:5000
```

> Auto-clear is **disabled** per decision. Queue<=50, History<=20 are enforced.
