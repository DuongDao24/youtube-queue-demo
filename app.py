# app.py — YouTube Queue Online (v02.3 root-ready, Render OK)
from flask import Flask, request, jsonify, render_template
from urllib.parse import urlparse, parse_qs
import os, time, threading

app = Flask(__name__)

HOST_API_KEY = os.environ.get("HOST_API_KEY", "ytq-premium-2025-dxd")
DEFAULT_HOST_USER = "Admin"
DEFAULT_HOST_PASS = "0000"

state_lock = threading.Lock()

STATE = {
    "queue": [],
    "history": [],
    "playing": None,
    "progress": {"pos": 0.0, "dur": 0.0, "ts": 0.0, "videoId": None},
    "settings": {"submit_limit_s": 60, "nick_change_hours": 24},
    "host_auth": {"user": DEFAULT_HOST_USER, "pass": DEFAULT_HOST_PASS},
    "nick_map": {},
    "rate_limit": {}
}

def yt_id_from_url(url: str):
    try:
        u = urlparse(url); q = parse_qs(u.query)
        if "v" in q: return q["v"][0]
        if u.netloc and u.netloc.endswith("youtu.be"):
            return (u.path or "").strip("/").split("/")[0] or None
    except Exception: pass
    return None

def add_history(item):
    STATE["history"].insert(0, item)
    if len(STATE["history"]) > 30: STATE["history"].pop()

def now(): return time.time()

@app.route("/")
def page_user(): return render_template("index.html", app_title="YouTube Queue Online")

@app.route("/host")
def page_host(): return render_template("host.html", app_title="YouTube Queue Online — Host")

@app.route("/api/state")
def api_state():
    hide_ip = request.args.get("host") != "1"
    s = {
        "queue": STATE["queue"],
        "history": STATE["history"],
        "playing": STATE["playing"],
        "progress": STATE["progress"],
        "settings": STATE["settings"],
    }
    if hide_ip:
        def strip_ip(x):
            y = dict(x); y.pop("ip", None); return y
        s["queue"] = [strip_ip(x) for x in s["queue"]]
        s["history"] = [strip_ip(x) for x in s["history"]]
    return jsonify(s)

@app.route("/api/nick", methods=["POST"])
def api_nick():
    data = request.get_json(silent=True) or {}
    nick = (data.get("nick") or "").strip()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    ttl = max(1, int(STATE["settings"]["nick_change_hours"])) * 3600
    STATE["nick_map"][ip] = {"name": nick[:30] or "Guest", "until": now()+ttl}
    return jsonify({"ok": True})

@app.route("/api/enqueue", methods=["POST"])
def api_enqueue():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    # rate limit
    wait_s = int(STATE["settings"]["submit_limit_s"])
    nxt = STATE["rate_limit"].get(ip, 0)
    if now() < nxt:
        return jsonify({"ok": False, "error": "RATE_LIMIT", "retry_in": int(nxt - now())}), 429
    vid = yt_id_from_url(url)
    if not vid: return jsonify({"ok": False, "error": "BAD_URL"}), 400
    who = STATE["nick_map"].get(ip, {"name": "Guest"})["name"]
    item = {
        "id": vid, "url": url,
        "title": f"#{vid}",
        "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "who": who, "ip": ip
    }
    STATE["queue"].append(item)
    STATE["rate_limit"][ip] = now() + wait_s
    if STATE["playing"] is None:
        STATE["playing"] = STATE["queue"].pop(0)
    return jsonify({"ok": True, "added": item})

def host_guard(req):
    creds = req.headers.get("X-Host-Auth", "")
    if ":" not in creds: return False
    u, p = creds.split(":", 1)
    return (u == STATE["host_auth"]["user"] and p == STATE["host_auth"]["pass"])

def host_login_ok(req):
    data = req.get_json(silent=True) or {}
    u = data.get("_user") or ""
    p = data.get("_pass") or ""
    return (u == STATE["host_auth"]["user"] and p == STATE["host_auth"]["pass"])

@app.route("/api/next", methods=["POST"])
def api_next():
    if not host_guard(request): return jsonify({"ok": False, "error": "UNAUTHORIZED"}), 401
    if STATE["playing"]: add_history(STATE["playing"])
    if STATE["queue"]: STATE["playing"] = STATE["queue"].pop(0)
    else: STATE["playing"] = None
    STATE["progress"] = {"pos": 0.0, "dur": 0.0, "ts": now(), "videoId": STATE["playing"]["id"] if STATE["playing"] else None}
    return jsonify({"ok": True, "playing": STATE["playing"]})

@app.route("/api/prev", methods=["POST"])
def api_prev():
    if not host_guard(request): return jsonify({"ok": False, "error": "UNAUTHORIZED"}), 401
    if STATE["history"]:
        prev_item = STATE["history"].pop(0)
        if STATE["playing"]: STATE["queue"].insert(0, STATE["playing"])
        STATE["playing"] = prev_item
        STATE["progress"] = {"pos": 0.0, "dur": 0.0, "ts": now(), "videoId": prev_item["id"]}
        return jsonify({"ok": True, "playing": STATE["playing"]})
    return jsonify({"ok": False, "error": "NO_PREV"}), 400

@app.route("/api/clear", methods=["POST"])
def api_clear():
    if not host_guard(request): return jsonify({"ok": False, "error": "UNAUTHORIZED"}), 401
    STATE["queue"].clear()
    return jsonify({"ok": True})

@app.route("/api/progress", methods=["POST"])
def api_progress():
    if not host_guard(request): return jsonify({"ok": False, "error": "UNAUTHORIZED"}), 401
    data = request.get_json(silent=True) or {}
    STATE["progress"] = {
        "pos": float(data.get("pos") or 0.0),
        "dur": float(data.get("dur") or 0.0),
        "ts": now(),
        "videoId": data.get("videoId")
    }
    if data.get("ended"): return api_next()
    return jsonify({"ok": True})

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET": return jsonify({"ok": True, "settings": STATE["settings"]})
    if not host_login_ok(request): return jsonify({"ok": False, "error": "UNAUTHORIZED"}), 401
    data = request.get_json(silent=True) or {}
    try:
        if "submit_limit_s" in data: STATE["settings"]["submit_limit_s"] = max(1, int(data["submit_limit_s"]))
        if "nick_change_hours" in data: STATE["settings"]["nick_change_hours"] = max(1, int(data["nick_change_hours"]))
    except Exception: return jsonify({"ok": False, "error": "BAD_VALUE"}), 400
    return jsonify({"ok": True, "settings": STATE["settings"]})

@app.route("/api/host_auth_update", methods=["POST"])
def api_host_auth_update():
    data = request.get_json(silent=True) or {}
    key = data.get("host_api_key") or ""
    if key != HOST_API_KEY: return jsonify({"ok": False, "error": "KEY_MISMATCH"}), 401
    user = (data.get("user") or "").strip() or DEFAULT_HOST_USER
    pwd  = (data.get("pass") or "").strip() or DEFAULT_HOST_PASS
    STATE["host_auth"]["user"] = user[:40]
    STATE["host_auth"]["pass"] = pwd[:40]
    return jsonify({"ok": True})

@app.route("/api/host_login", methods=["POST"])
def api_host_login():
    data = request.get_json(silent=True) or {}
    u = data.get("user") or ""
    p = data.get("pass") or ""
    ok = (u == STATE["host_auth"]["user"] and p == STATE["host_auth"]["pass"])
    return jsonify({"ok": ok})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
