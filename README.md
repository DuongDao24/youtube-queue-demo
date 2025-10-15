# YouTube Queue Online — v08.1 (Root Ready, Render-ready)

**Features**
- Submit YouTube link → shared queue
- Auto-next (host tab open) with 3–2–1 countdown
- Nickname per user (saved in browser), rate limit per IP
- Host dashboard: play/next/prev/clear, remove item, upload logo
- Settings: submit limit (seconds), nickname change (hours)
- Works on Render Free

**Endpoints**
- `/` user page
- `/host` host page (enter `HOST_API_KEY` once)

**Deploy to Render**
- Build: `pip install -r requirements.txt`
- Start: `gunicorn -w 1 -k gevent -b 0.0.0.0:$PORT app:app`
- Env: `APP_TITLE`, `HOST_API_KEY`, `RATE_LIMIT_S`, `PYTHON_VERSION=3.11.9`
