# YouTube Queue Online — v08.3 (Final, Render-ready)

- User page: submit YT link (not playlist), nickname required (cached in browser).
- Host page: protected login popup (default credentials: **Admin / 0000**). Defaults are **not shown** in UI.
- Controls: **Pause/Resume** (center), **Prev**, **Next**, **Clear**.
- Settings: **Submit limit (seconds)**, **Nickname change (hours)**. Save reliably; fields won't jump back.
- Upload logo (png/jpg/gif).
- Auto-next with **10s** countdown; resume playing after host refresh.
- Queue/History and "Now playing" sync to user page every 2s.

## Deploy
1) Create a new Render Web Service from this repo (Python).  
2) Keep defaults or use `render.yaml`.  
3) Environment (optional):
   - `HOST_API_KEY` (string) – required to change host username/password.
   - `APP_TITLE` (string) – title on pages.

## Endpoints
- `/` – User page
- `/host` – Host dashboard (login popup)
- `/api/*` – JSON APIs

> Tip: if you change default admin credentials inside Host settings, you must provide the correct `HOST_API_KEY` to confirm the change.
