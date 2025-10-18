# YouTube Queue — v01.6.2 (Clean Layout)

Author: Duong – XDigital  
Updated: 2025-10-18

This repository keeps the root clean: **only README.md**.  
All code and assets live under **/app/**.

## Structure
```
app/
  core/
    app.py
    requirements.txt
    data/
      settings.json
      users.json
      queue.json
      activity_log.csv
  templates/
  static/
```

## Run locally
```bash
pip install -r app/core/requirements.txt
python app/core/app.py
# open http://localhost:5000
```

## Deploy on Render (no render.yaml at root)
Set these in the service settings:
- **Build Command:** `pip install -r app/core/requirements.txt`
- **Start Command:** `python app/core/app.py`
