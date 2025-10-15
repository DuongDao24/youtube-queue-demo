import os, json, time, re
from collections import deque
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import requests

APP_TITLE      = os.environ.get("APP_TITLE", "YouTube Queue Online")
HOST_API_KEY   = os.environ.get("HOST_API_KEY", "ytq-premium-2025-dxd")
ENV_RATE_LIMIT = int(os.environ.get("RATE_LIMIT_S", "180"))
CONFIG_PATH    = "config.json"
STATE_PATH     = "queue_data.json"
STATIC_DIR     = "static"
ALLOWED_LOGO_EXT = {".png", ".jpg", ".jpeg", ".gif"}

app = Flask(__name__)

queue = deque()
history = deque(maxlen=300)
current = None
last_submit_ts = {}
last_progress = {"videoId": None, "pos": 0, "dur": 0, "ts": 0, "ended": False}

config = {
    "rate_limit_s": ENV_RATE_LIMIT,
    "nick_change_hours": 24,
    "names": {},
    "name_changed_at": {},
    "logo_path": None
}

YOUTUBE_ID_REGEX = re.compile(r"(?:v=|youtu\.be/|youtube\.com/(?:embed/|shorts/|watch\?v=))([A-Za-z0-9_-]{11})")

def extract_youtube_id(url: str):
    u = (url or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", u):
        return u
    m = YOUTUBE_ID_REGEX.search(u)
    if m: return m.group(1)
    try:
        q = parse_qs(urlparse(u).query)
        v = q.get("v", [None])[0]
        if v and re.fullmatch(r"[A-Za-z0-9_-]{11}", v):
            return v
    except Exception:
        pass
    return None

def fetch_title(video_id: str):
    try:
        r = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json", timeout=6)
        if r.ok: return r.json().get("title", video_id)
    except Exception:
        pass
    return video_id

def client_ip():
    xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return xff or (request.remote_addr or "unknown")

def load_state():
    global queue, history, current
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    config.update(data)
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            queue.extend(data.get("queue", []))
            history.extend(data.get("history", []))
            globals()["current"] = data.get("current")
    except Exception as e:
        print("load_state error:", e)

def save_state():
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"queue": list(queue), "history": list(history), "current": current}, f, ensure_ascii=False, indent=2)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_state error:", e)

def get_logo_url():
    if config.get("logo_path"):
        return f"/{config['logo_path']}?t={int(time.time())}"
    return None

def require_host_key():
    if request.headers.get("X-Host-Key") != HOST_API_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return None

@app.route("/")
def page_index():
    return render_template("index.html", app_title=APP_TITLE, rate_limit_s=int(config.get("rate_limit_s", ENV_RATE_LIMIT)), logo_url=get_logo_url())

@app.route("/host")
def page_host():
    return render_template("host.html", app_title=APP_TITLE, logo_url=get_logo_url())

@app.route("/api/state")
def api_state():
    return jsonify({
        "current": current,
        "queue": list(queue),
        "history": list(history),
        "progress": last_progress,
        "config": {
            "rate_limit_s": int(config.get("rate_limit_s", ENV_RATE_LIMIT)),
            "nick_change_hours": int(config.get("nick_change_hours", 24)),
            "logo_url": get_logo_url()
        }
    })

@app.route("/api/add", methods=["POST"])
def api_add():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    name = (data.get("name") or "").strip()
    ip = client_ip()

    now = time.time()
    remain = int(config.get("rate_limit_s", ENV_RATE_LIMIT)) - int(now - last_submit_ts.get(ip, 0))
    if remain > 0:
        return jsonify({"ok": False, "error": f"Please wait {remain}s."}), 429

    vid = extract_youtube_id(url)
    if not vid:
        return jsonify({"ok": False, "error": "Paste a YouTube video link (not playlist)."}), 400

    title = fetch_title(vid)
    item = {"id": vid, "title": title, "by_ip": ip, "by_name": name, "ts": int(now)}
    queue.append(item)
    last_submit_ts[ip] = now

    global current
    if not current:
        current = queue.popleft()

    save_state()
    return jsonify({"ok": True, "item": item})

@app.route("/api/next", methods=["POST"])
def api_next():
    unauth = require_host_key()
    if unauth: return unauth
    global current
    if current: history.appendleft(current)
    current = queue.popleft() if queue else None
    save_state()
    return jsonify({"ok": True, "current": current})

@app.route("/api/prev", methods=["POST"])
def api_prev():
    unauth = require_host_key()
    if unauth: return unauth
    global current
    if history:
        if current: queue.appendleft(current)
        current = history.popleft()
        save_state()
        return jsonify({"ok": True, "current": current})
    return jsonify({"ok": False, "error": "No previous"}), 400

@app.route("/api/play", methods=["POST"])
def api_play():
    unauth = require_host_key()
    if unauth: return unauth
    data = request.get_json(silent=True) or {}
    vid = data.get("videoId")
    global current
    if vid:
        if current: history.appendleft(current)
        current = {"id": vid, "title": fetch_title(vid), "by_ip": "host", "by_name": "Host", "ts": int(time.time())}
    elif not current:
        current = queue.popleft() if queue else None
    save_state()
    return jsonify({"ok": True, "current": current})

@app.route("/api/clear", methods=["POST"])
def api_clear():
    unauth = require_host_key()
    if unauth: return unauth
    queue.clear()
    save_state()
    return jsonify({"ok": True})

@app.route("/api/remove", methods=["POST"])
def api_remove():
    unauth = require_host_key()
    if unauth: return unauth
    data = request.get_json(silent=True) or {}
    vid = data.get("id")
    if not vid: return jsonify({"ok": False}), 400
    from collections import deque as dq
    global queue
    newq, removed = dq(), False
    for it in list(queue):
        if not removed and it["id"] == vid:
            removed = True
            continue
        newq.append(it)
    queue = newq
    save_state()
    return jsonify({"ok": True, "removed": removed})

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify({
            "rate_limit_s": int(config.get("rate_limit_s", ENV_RATE_LIMIT)),
            "nick_change_hours": int(config.get("nick_change_hours", 24)),
            "logo_url": get_logo_url()
        })
    unauth = require_host_key()
    if unauth: return unauth
    data = request.get_json(silent=True) or {}
    try:
        if "rate_limit_s" in data:
            v = max(10, int(data["rate_limit_s"]))
            config["rate_limit_s"] = v
        if "nick_change_hours" in data:
            h = max(1, int(data["nick_change_hours"]))
            config["nick_change_hours"] = h
    except Exception:
        pass
    save_state()
    return jsonify({"ok": True, "config": config})

@app.route("/api/logo", methods=["POST"])
def api_logo():
    unauth = require_host_key()
    if unauth: return unauth
    if "logo" not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    f = request.files["logo"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_LOGO_EXT:
        return jsonify({"ok": False, "error": "Invalid file type"}), 400
    os.makedirs(STATIC_DIR, exist_ok=True)
    # remove older logos
    for old in os.listdir(STATIC_DIR):
        if old.startswith("logo"):
            try: os.remove(os.path.join(STATIC_DIR, old))
            except Exception: pass
    save_name = f"logo{ext}"
    f.save(os.path.join(STATIC_DIR, save_name))
    config["logo_path"] = f"static/{save_name}"
    save_state()
    return jsonify({"ok": True, "logo_url": f"/{config['logo_path']}"})

@app.route("/api/name", methods=["GET", "POST"])
def api_name():
    ip = client_ip()
    if request.method == "GET":
        return jsonify({"ip": ip, "name": config["names"].get(ip), "nick_change_hours": int(config.get("nick_change_hours", 24))})
    data = request.get_json(silent=True) or {}
    new_name = (data.get("name") or "").strip()
    if not (1 <= len(new_name) <= 24):
        return jsonify({"ok": False, "error": "Name must be 1–24 chars."}), 400
    hours = int(config.get("nick_change_hours", 24))
    last  = float(config["name_changed_at"].get(ip) or 0)
    now   = time.time()
    if now - last < hours * 3600:
        remain = int(hours*3600 - (now - last))
        return jsonify({"ok": False, "error": f"Can change in {remain//3600}h{(remain%3600)//60:02d}m."}), 429
    config["names"][ip] = new_name
    config["name_changed_at"][ip] = now
    save_state()
    return jsonify({"ok": True, "name": new_name})

@app.route("/api/progress", methods=["POST"])
def api_progress():
    unauth = require_host_key()
    if unauth: return unauth
    global last_progress, current
    data = request.get_json(silent=True) or {}
    pos   = float(data.get("pos", 0))
    dur   = float(data.get("dur", 0))
    ended = bool(data.get("ended", False))
    vid   = data.get("videoId")
    ts    = time.time()
    last_progress = {"videoId": vid, "pos": pos, "dur": dur, "ts": ts, "ended": ended}
    if ended:
        if current: history.appendleft(current)
        current = queue.popleft() if queue else None
        last_progress["ended"] = False
    save_state()
    return jsonify({"ok": True})

@app.route("/healthz")
def healthz():
    return "ok", 200

# Boot
load_state()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","5000")), debug=False)
