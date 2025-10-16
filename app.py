import os, time, re, secrets
from flask import Flask, request, jsonify, render_template

APP_TITLE = os.getenv("APP_TITLE", "YouTube Queue Online")
HOST_API_KEY = os.getenv("HOST_API_KEY", "")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY","dev-secret")

YOUTUBE_RE = re.compile(r'(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})')

STATE = {
    "queue": [],         # list of {vid,title,nick,ip}
    "history": [],       # last 20
    "current": None,     # {vid,title,nick,ip,pos,start_ts,playing}
    "rate_limit_s": 60,
    "nick_change_h": 24,
    "ip_last_submit": {},    # ip -> ts
    "nick_last_change": {},  # ip -> ts
    "host_user": "Admin",
    "host_pass": "0000",
    "host_tokens": set(),
}

def extract_vid(url):
    m = YOUTUBE_RE.search(url)
    return m.group(1) if m else None

def now(): return time.time()

def can_submit(ip):
    last = STATE["ip_last_submit"].get(ip, 0)
    return (now() - last) >= STATE["rate_limit_s"]

def can_change_nick(ip):
    last = STATE["nick_last_change"].get(ip, 0)
    return (now() - last) >= STATE["nick_change_h"]*3600

def set_current_from_queue():
    if STATE["queue"]:
        item = STATE["queue"].pop(0)
        STATE["current"] = {
            **item,
            "pos": 0.0,
            "start_ts": now(),
            "playing": True,
        }
        STATE["history"] = STATE["history"][:20]
        return True
    STATE["current"] = None
    return False

@app.get("/")
def page_user():
    return render_template("index.html", app_title=APP_TITLE)

@app.get("/host")
def page_host():
    return render_template("host.html", app_title=APP_TITLE)

@app.get("/api/state")
def api_state():
    cur = STATE["current"]
    # update computed progress
    if cur and cur.get("playing"):
        elapsed = now() - cur.get("start_ts", now())
        cur["pos"] = max(cur.get("pos",0.0), elapsed)
    q = [dict(vid=i["vid"], title=i.get("title"), nick=i.get("nick")) for i in STATE["queue"]]
    h = [dict(vid=i["vid"], title=i.get("title"), nick=i.get("nick")) for i in STATE["history"]]
    resp = {
        "queue": q,
        "history": h,
        "current": dict(cur) if cur else None,
        "rate_limit_s": STATE["rate_limit_s"],
        "nick_change_h": STATE["nick_change_h"],
    }
    # inject progress pct (fake 3m if unknown)
    if resp["current"]:
        dur = resp["current"].get("dur") or 180
        pct = int(100*float(resp["current"].get("pos",0.0))/float(dur))
        resp["current"]["progress_pct"] = max(0, min(100, pct))
    return jsonify(resp)

@app.post("/api/enqueue")
def api_enqueue():
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    nick = (data.get("nickname") or "").strip() or "anonymous"
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if not can_submit(ip):
        return jsonify({"ok": False, "error": f"Please wait {STATE['rate_limit_s']}s between submits."})
    vid = extract_vid(url)
    if not vid:
        return jsonify({"ok": False, "error":"Invalid YouTube URL."})
    item = {"vid": vid, "title": None, "nick": nick, "ip": ip}
    if STATE["current"] is None:
        STATE["queue"].append(item)
        set_current_from_queue()
    else:
        STATE["queue"].append(item)
    STATE["ip_last_submit"][ip] = now()
    return jsonify({"ok": True})

def require_host(f):
    def wrap(*a, **k):
        token = request.headers.get("X-Host-Token","")
        if token not in STATE["host_tokens"]:
            return jsonify({"ok": False, "error":"Not authorized"})
        return f(*a, **k)
    wrap.__name__ = f.__name__
    return wrap

@app.post("/api/host/login")
def api_host_login():
    data = request.get_json(force=True, silent=True) or {}
    user = (data.get("user") or "").strip()
    pw = (data.get("pass") or "")
    if user == STATE["host_user"] and pw == STATE["host_pass"]:
        token = secrets.token_urlsafe(18)
        STATE["host_tokens"].add(token)
        return jsonify({"ok": True, "token": token})
    return jsonify({"ok": False, "error":"Wrong username/password"})

@app.post("/api/toggle")
@require_host
def api_toggle():
    cur = STATE["current"]
    if not cur:
        set_current_from_queue()
        return jsonify({"ok": True})
    cur["playing"] = not cur.get("playing", True)
    if cur["playing"]:
        # resume: shift start_ts so elapsed continues
        cur["start_ts"] = now() - cur.get("pos",0.0)
    return jsonify({"ok": True})

@app.post("/api/next")
@require_host
def api_next():
    # push current to history
    if STATE["current"]:
        STATE["history"].insert(0, STATE["current"])
        STATE["history"] = STATE["history"][:20]
    set_current_from_queue()
    return jsonify({"ok": True})

@app.post("/api/prev")
@require_host
def api_prev():
    # not keeping prev buffer; no-op
    return jsonify({"ok": False, "error":"Prev not available in this build"})

@app.post("/api/clear")
@require_host
def api_clear():
    STATE["queue"].clear()
    return jsonify({"ok": True})

@app.post("/api/settings")
@require_host
def api_settings():
    data = request.get_json(force=True, silent=True) or {}
    rate = int(data.get("rate_limit_s", STATE["rate_limit_s"]))
    nickh = int(data.get("nick_change_h", STATE["nick_change_h"]))
    STATE["rate_limit_s"] = max(5, rate)
    STATE["nick_change_h"] = max(1, nickh)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
