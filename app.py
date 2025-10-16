import os, time, re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session

# ---------------------------
# App & basic config
# ---------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "ytq-secret-2025")

APP_TITLE = os.environ.get("APP_TITLE", "YouTube Queue Online")
HOST_API_KEY = os.environ.get("HOST_API_KEY", "ytq-premium-2025-dxd")
DEFAULT_HOST_USER = os.environ.get("HOST_USER", "Admin")
DEFAULT_HOST_PASS = os.environ.get("HOST_PASS", "0000")

# ---------------------------
# In-memory store
# ---------------------------
queue = []            # [{url, by_ip, by_name, ts}]
history = []          # [{url, by_ip, by_name, ts}]
current = None        # {url, started_at, progress_sec}
settings = {
    "rate_limit_s": int(os.environ.get("RATE_LIMIT_S", "60")),
    "nick_change_hours": int(os.environ.get("NICK_CHANGE_HOURS", "24")),
    "host_user": DEFAULT_HOST_USER,
    "host_pass": DEFAULT_HOST_PASS,
}

# track last submit + nickname cache
last_submit = {}      # {ip: epoch_sec}
nick_cache = {}       # {ip: {"name": "XD", "until": epoch_sec}}

YOUTUBE_RE = re.compile(r"(youtu\.be/|youtube\.com/watch\?v=)")

# ---------------------------
# Helpers
# ---------------------------
def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()

def now():
    return int(time.time())

def valid_youtube_url(url: str) -> bool:
    if not url:
        return False
    return bool(YOUTUBE_RE.search(url))

# ---------------------------
# Pages
# ---------------------------
@app.route("/")
def page_user():
    return render_template("index.html", app_title=APP_TITLE, settings=settings)

@app.route("/host")
def page_host():
    return render_template("host.html", app_title=APP_TITLE, settings=settings, is_host=bool(session.get("host_ok")))

# ---------------------------
# APIs: get state
# ---------------------------
@app.get("/api/state")
def api_state():
    ip = client_ip()
    nick = ""
    if ip in nick_cache and nick_cache[ip]["until"] > now():
        nick = nick_cache[ip]["name"]

    return jsonify({
        "ok": True,
        "app_title": APP_TITLE,
        "settings": settings,
        "queue": queue,
        "history": history[-20:][::-1],
        "current": current,
        "me": {"ip": ip, "nickname": nick},
    })

# ---------------------------
# APIs: set nickname
# ---------------------------
@app.post("/api/nick")
def api_nick():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Nickname required."}), 400

    ip = client_ip()
    if ip in nick_cache and nick_cache[ip]["until"] > now():
        if nick_cache[ip]["name"]:
            return jsonify({"ok": False, "error": "You can change nickname later."}), 429

    ttl = now() + settings["nick_change_hours"] * 3600
    nick_cache[ip] = {"name": name[:32], "until": ttl}
    return jsonify({"ok": True, "nickname": nick_cache[ip]})

# ---------------------------
# APIs: add to queue
# ---------------------------
@app.post("/api/add")
def api_add():
    global current  # 🔧 moved up to avoid SyntaxError
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not valid_youtube_url(url):
        return jsonify({"ok": False, "error": "Invalid YouTube URL."}), 400

    ip = client_ip()
    last = last_submit.get(ip, 0)
    if now() - last < settings["rate_limit_s"]:
        return jsonify({"ok": False, "error": "Please wait before submitting again."}), 429
    last_submit[ip] = now()

    by_name = ""
    if ip in nick_cache and nick_cache[ip]["until"] > now():
        by_name = nick_cache[ip]["name"]

    item = {
        "url": url,
        "by_ip": ip,
        "by_name": by_name,
        "ts": now(),
    }
    queue.append(item)

    # auto start if nothing playing
    if current is None:
        current = {"url": url, "started_at": now(), "progress_sec": 0}
        queue.pop(0)

    return jsonify({"ok": True, "queue_len": len(queue)})

# ---------------------------
# Host auth
# ---------------------------
@app.post("/api/host/login")
def api_host_login():
    data = request.get_json(silent=True) or {}
    user = (data.get("user") or "").strip()
    pw = (data.get("pass") or "").strip()
    if user == settings["host_user"] and pw == settings["host_pass"]:
        session["host_ok"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Sai tài khoản hoặc mật khẩu."}), 401

@app.post("/api/host/logout")
def api_host_logout():
    session.pop("host_ok", None)
    return jsonify({"ok": True})

def require_host():
    return bool(session.get("host_ok"))

# ---------------------------
# Host controls
# ---------------------------
@app.post("/api/host/next")
def api_host_next():
    global current
    if not require_host():
        return jsonify({"ok": False, "error": "Not authorized"}), 401

    if queue:
        if current:
            history.append({"url": current["url"], "by_ip": "", "by_name": "", "ts": now()})
        nxt = queue.pop(0)
        current = {"url": nxt["url"], "started_at": now(), "progress_sec": 0}
        return jsonify({"ok": True, "current": current, "queue_len": len(queue)})

    if current:
        history.append({"url": current["url"], "by_ip": "", "by_name": "", "ts": now()})
    current = None
    return jsonify({"ok": True, "current": None})

@app.post("/api/host/prev")
def api_host_prev():
    global current
    if not require_host():
        return jsonify({"ok": False, "error": "Not authorized"}), 401
    if history:
        prev = history.pop()
        if current:
            queue.insert(0, {"url": current["url"], "by_ip": "", "by_name": "", "ts": now()})
        current = {"url": prev["url"], "started_at": now(), "progress_sec": 0}
        return jsonify({"ok": True, "current": current})
    return jsonify({"ok": False})

@app.post("/api/host/clear")
def api_host_clear():
    if not require_host():
        return jsonify({"ok": False, "error": "Not authorized"}), 401
    queue.clear()
    return jsonify({"ok": True})

# ---------------------------
# Video progress + auto next
# ---------------------------
@app.post("/api/progress")
def api_progress():
    global current  # 🔧 moved up to avoid SyntaxError
    data = request.get_json(silent=True) or {}
    status = data.get("status")

    if status == "ended":
        if queue:
            nxt = queue.pop(0)
            if current:
                history.append({"url": current["url"], "by_ip": "", "by_name": "", "ts": now()})
            current = {"url": nxt["url"], "started_at": now(), "progress_sec": 0}
        else:
            if current:
                history.append({"url": current["url"], "by_ip": "", "by_name": "", "ts": now()})
            current = None

    return jsonify({"ok": True})

# ---------------------------
# Host: save settings
# ---------------------------
@app.post("/api/host/save_settings")
def api_save_settings():
    if not require_host():
        return jsonify({"ok": False, "error": "Not authorized"}), 401
    data = request.get_json(silent=True) or {}
    try:
        rs = int(data.get("rate_limit_s", settings["rate_limit_s"]))
        nh = int(data.get("nick_change_hours", settings["nick_change_hours"]))
        settings["rate_limit_s"] = max(1, min(3600, rs))
        settings["nick_change_hours"] = max(1, min(168, nh))
        return jsonify({"ok": True, "settings": settings})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

# ---------------------------
# Host: change auth
# ---------------------------
@app.post("/api/host/change_auth")
def api_change_auth():
    if not require_host():
        return jsonify({"ok": False, "error": "Not authorized"}), 401
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    if key != HOST_API_KEY:
        return jsonify({"ok": False, "error": "HOST_API_KEY invalid"}), 401

    new_user = (data.get("user") or "").strip() or settings["host_user"]
    new_pass = (data.get("pass") or "").strip() or settings["host_pass"]
    settings["host_user"] = new_user
    settings["host_pass"] = new_pass
    return jsonify({"ok": True})

# ---------------------------
# Run local
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
