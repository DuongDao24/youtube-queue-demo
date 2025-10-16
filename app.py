import os, re, time, json, secrets
from urllib.parse import urlparse, parse_qs
import requests
from flask import Flask, request, jsonify, session, render_template, abort

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

# -------- Runtime settings (đổi ở trang host) ----------
SETTINGS = {
    "rate_limit_s": int(os.environ.get("RATE_LIMIT_S", "60")),      # giới hạn submit / IP
    "nick_change_hours": int(os.environ.get("NICK_CHANGE_HOURS", "24")),
}

# -------- Host auth ----------
HOST_USER = os.environ.get("HOST_USER", "Admin")
HOST_PASS = os.environ.get("HOST_PASS", "0000")
HOST_API_KEY = os.environ.get("HOST_API_KEY", "ytq-premium-2025-dxd")  # để đổi user/pass

# -------- State ----------
STATE = {
    "queue": [],           # [{id,url,title,thumb,by_ip,by_name,ts}]
    "current": None,       # index trong queue
    "history": [],         # các item đã phát xong
    "nick_map": {},        # ip -> {name,last_change}
    "rate_ip": {},         # ip -> last_submit_epoch
}

YT_REGEX = re.compile(r'(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|embed/))([A-Za-z0-9_-]{6,})')

def _now(): return int(time.time())
def _ip():
    xff = request.headers.get('X-Forwarded-For')
    return xff.split(',')[0].strip() if xff else (request.remote_addr or '0.0.0.0')

def _need_host():
    if not session.get("host_ok"): abort(401, description="host_not_logged")

def _extract_id(url: str):
    m = YT_REGEX.search(url or "")
    if m: return m.group(1)
    try:
        qs = parse_qs(urlparse(url).query)
        if 'v' in qs: return qs['v'][0]
    except: pass
    return None

def _fetch_meta(url: str):
    try:
        r = requests.get("https://www.youtube.com/oembed",
                         params={"url": url, "format": "json"}, timeout=6)
        if r.ok:
            j = r.json()
            return j.get("title", "YouTube Video"), j.get("thumbnail_url")
    except: pass
    return "YouTube Video", None

# -------- Pages ----------
@app.get("/")
def page_user(): return render_template("index.html", app_title="YouTube Queue Online")

@app.get("/host")
def page_host(): return render_template("host.html", app_title="YouTube Queue Online — Host")

# -------- Auth ----------
@app.post("/api/login")
def api_login():
    d = request.get_json() or {}
    if d.get("username")==HOST_USER and d.get("password")==HOST_PASS:
        session["host_ok"] = True
        return jsonify(ok=True)
    return jsonify(ok=False, err="bad_credentials"), 401

@app.post("/api/host_auth")
def api_host_auth():
    d = request.get_json() or {}
    if d.get("host_api_key") != HOST_API_KEY:
        return jsonify(ok=False, err="not_authorized"), 401
    global HOST_USER, HOST_PASS
    HOST_USER = d.get("new_user") or HOST_USER
    HOST_PASS = d.get("new_pass") or HOST_PASS
    return jsonify(ok=True, user=HOST_USER)

# -------- Settings ----------
@app.get("/api/settings")
def api_get_settings(): return jsonify(ok=True, settings=SETTINGS)

@app.post("/api/settings")
def api_save_settings():
    _need_host()
    d = request.get_json() or {}
    try:
        SETTINGS["rate_limit_s"] = max(5, min(3600, int(d.get("rate_limit_s", SETTINGS["rate_limit_s"]))))
        SETTINGS["nick_change_hours"] = max(1, min(168, int(d.get("nick_change_hours", SETTINGS["nick_change_hours"]))))
        return jsonify(ok=True, settings=SETTINGS)
    except:
        return jsonify(ok=False, err="invalid"), 400

# -------- Nickname ----------
@app.post("/api/nick")
def api_nick():
    ip = _ip()
    d = request.get_json() or {}
    name = (d.get("name") or "").strip()
    if not name: return jsonify(ok=False, err="empty_nick"), 400

    info = STATE["nick_map"].get(ip)
    now = _now()
    if info:
        elapsed_h = (now - info.get("last_change",0))/3600.0
        if elapsed_h < SETTINGS["nick_change_hours"]:
            return jsonify(ok=False, err="cooldown",
                           next_change=int(info["last_change"]+SETTINGS["nick_change_hours"]*3600))
    STATE["nick_map"][ip] = {"name": name, "last_change": now}
    return jsonify(ok=True, name=name)

def _nick(ip): 
    info = STATE["nick_map"].get(ip)
    return info["name"] if info and info.get("name") else "Guest"

# -------- Queue ----------
@app.get("/api/state")
def api_state():
    q = [{
        "idx": i+1, "id": it["id"], "title": it["title"], "thumb": it.get("thumb"),
        "by": it.get("by_name") or "Guest"
    } for i,it in enumerate(STATE["queue"])]

    cur = None
    if STATE["current"] is not None and 0 <= STATE["current"] < len(STATE["queue"]):
        x = STATE["queue"][STATE["current"]]
        cur = {"id": x["id"], "title": x["title"], "thumb": x.get("thumb")}

    return jsonify(ok=True, queue=q, current=cur, settings=SETTINGS,
                   host=bool(session.get("host_ok")),
                   history=[{"title":h["title"], "by":h.get("by_name","Guest")} for h in STATE["history"]])

@app.post("/api/add")
def api_add():
    ip = _ip()
    if ip not in STATE["nick_map"] or not STATE["nick_map"][ip].get("name"):
        return jsonify(ok=False, err="need_nick"), 400

    last = STATE["rate_ip"].get(ip, 0)
    if _now()-last < SETTINGS["rate_limit_s"]:
        return jsonify(ok=False, err="rate_limited",
                       wait=SETTINGS["rate_limit_s"]-(_now()-last)), 429

    d = request.get_json() or {}
    url = (d.get("url") or "").strip()
    vid = _extract_id(url)
    if not vid: return jsonify(ok=False, err="bad_url"), 400

    title, thumb = _fetch_meta(url)
    item = {"id":vid, "url":url, "title":title, "thumb":thumb,
            "by_ip":ip, "by_name":_nick(ip), "ts":_now()}
    STATE["queue"].append(item)
    STATE["rate_ip"][ip] = _now()

    # Auto start nếu đang idle
    if STATE["current"] is None: STATE["current"] = 0
    return jsonify(ok=True, item={"id":vid, "title":title})

# -------- Host control ----------
@app.post("/api/next")
def api_next():
    _need_host()
    if STATE["current"] is None: return jsonify(ok=True)
    idx = STATE["current"]
    if 0 <= idx < len(STATE["queue"]):
        STATE["history"].append(STATE["queue"][idx])
        del STATE["queue"][idx]
    STATE["current"] = 0 if STATE["queue"] else None
    return jsonify(ok=True)

@app.post("/api/prev")
def api_prev():
    _need_host()
    # Không back – để trống cho đúng layout
    return jsonify(ok=True)

@app.post("/api/clear")
def api_clear():
    _need_host()
    STATE["queue"].clear()
    STATE["current"] = None
    return jsonify(ok=True)

# -------- favicon (optional) ----------
@app.get("/favicon.ico")
def fav(): abort(404)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
