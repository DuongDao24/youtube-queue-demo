# -*- coding: utf-8 -*-
"""
YouTube Queue | Web — Core Backend (Flask)
Version: v01.6.2  (Updated 2025-10-18)
Author: Duong – XDigital
CHANGELOG (v01.6.2):
- Introduced persistent storage in /core/data (JSON + CSV) to survive server restarts.
- Added queue/history auto-trim (Queue<=50, History<=20). Auto-clear is DISABLED by default per host decision.
- Implemented CSV activity logging for all key actions.
- Fixed nickname cooldown: when not allowed to change, submissions continue using the LAST allowed nickname.
- Moved backend files into /core to keep repo root clean (README remains at root).

NOTE:
- Keep render.yaml at repo ROOT with startCommand: "python core/app.py".
- If you move this file, update paths accordingly.
"""
import os
import json
import csv
from datetime import datetime, timedelta
from hashlib import sha256
from flask import Flask, request, jsonify, render_template

# -----------------------------
# Constants / Paths
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
QUEUE_FILE = os.path.join(DATA_DIR, "queue.json")
LOG_FILE = os.path.join(DATA_DIR, "activity_log.csv")

MAX_QUEUE = 50
MAX_HISTORY = 20

# -----------------------------
# Utils
# -----------------------------
def _now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

def read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback

def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def log_action(action, user, ip, title="N/A", url="N/A"):
    # Append one line to CSV log
    header = ["timestamp", "action", "user", "ip", "title", "url"]
    exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerow([_now_iso(), action, user, ip, title, url])

def client_ip():
    # X-Forwarded-For for Render/Proxies
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"

def hash_password(pw: str) -> str:
    return sha256(pw.encode("utf-8")).hexdigest()

# -----------------------------
# Load or initialize data
# -----------------------------
ensure_dirs()

default_settings = {
    "system": {
        "password_hash": "",  # set below
        "nickname_cooldown_hours": 1,
        "auto_clear_days": 7,   # configured but NOT enforced (disabled below)
        "theme": "dark",
        "version": "v01.6.2"
    },
    "branding": {
        "logo_url": "/static/logo.png",
        "system_name": "YouTube Queue",
        "slogan": "Office Music Queue"
    }
}

default_users = {}  # ip: {nickname, last_changed}
default_queue = {
    "last_saved": "",  # set below
    "queue": [],
    "history": []
}

# initialize defaults
default_settings["system"]["password_hash"] = hash_password("0000")
default_queue["last_saved"] = _now_iso()

settings = read_json(SETTINGS_FILE, default_settings)
users = read_json(USERS_FILE, default_users)
qstate = read_json(QUEUE_FILE, default_queue)

def save_settings():
    write_json(SETTINGS_FILE, settings)
    log_action("change_setting", "HOST", "0.0.0.0", "settings.json", "N/A")

def save_users():
    write_json(USERS_FILE, users)

def trim_and_save_queue():
    # Trim lengths
    if len(qstate.get("queue", [])) > MAX_QUEUE:
        qstate["queue"] = qstate["queue"][-MAX_QUEUE:]
    if len(qstate.get("history", [])) > MAX_HISTORY:
        qstate["history"] = qstate["history"][-MAX_HISTORY:]
    qstate["last_saved"] = _now_iso()
    write_json(QUEUE_FILE, qstate)

# Auto-clear is intentionally DISABLED as per request.
# If you want to enable later, uncomment this block.
# try:
#     last = datetime.strptime(qstate.get("last_saved", _now_iso()), "%Y-%m-%dT%H:%M:%SZ")
#     days = settings["system"].get("auto_clear_days", 7)
#     if datetime.utcnow() - last > timedelta(days=days):
#         qstate["queue"].clear()
#         qstate["history"].clear()
#         trim_and_save_queue()
#         log_action("auto_clear", "SYSTEM", "0.0.0.0", "queue+history cleared", "N/A")
# except Exception:
#     pass

# -----------------------------
# Flask app
# -----------------------------
app = Flask(__name__)

@app.route("/")
def user_page():
    return render_template("user.html",
                           settings=settings,
                           queue=qstate.get("queue", []),
                           history=qstate.get("history", []),
                           version=settings["system"].get("version", "v01.6.2"))

@app.route("/host")
def host_page():
    return render_template("host.html",
                           settings=settings,
                           users=users,
                           queue=qstate.get("queue", []),
                           history=qstate.get("history", []),
                           version=settings["system"].get("version", "v01.6.2"))

@app.post("/set_nickname")
def set_nickname():
    ip = client_ip()
    data = request.get_json(silent=True) or request.form
    nickname = (data.get("nickname") or "").strip()
    cooldown_h = settings["system"].get("nickname_cooldown_hours", 1)

    # Check cooldown
    allowed = True
    remaining = 0
    old = users.get(ip)
    if old and old.get("last_changed"):
        try:
            last_dt = datetime.strptime(old["last_changed"], "%Y-%m-%dT%H:%M:%SZ")
            delta = datetime.utcnow() - last_dt
            if delta < timedelta(hours=cooldown_h):
                allowed = False
                remaining = int((timedelta(hours=cooldown_h) - delta).total_seconds())
        except Exception:
            pass

    if allowed and nickname:
        users[ip] = {"nickname": nickname, "last_changed": _now_iso()}
        save_users()
        log_action("set_nickname", nickname, ip)
        return jsonify({"ok": True, "message": "Nickname saved."})
    else:
        # Not allowed to change now; keep old nickname and return remaining seconds
        current = (old or {}).get("nickname", "Guest")
        return jsonify({"ok": False, "message": "Cooldown active.", "remaining_seconds": remaining, "current": current}), 429

@app.post("/submit")
def submit():
    ip = client_ip()
    data = request.get_json(silent=True) or request.form
    url = (data.get("url") or "").strip()
    title = (data.get("title") or "").strip()

    if not url:
        return jsonify({"ok": False, "error": "Missing URL"}), 400

    # Resolve nickname
    nickname = users.get(ip, {}).get("nickname", "Guest")

    if not title:
        # lightweight title placeholder; frontend may fetch real title later
        tail = url.split("/")[-1][:12]
        title = f"YouTube Item - {tail}"

    entry = {
        "title": title,
        "url": url,
        "by": nickname,
        "ip": ip,
        "time": _now_iso()
    }
    qstate["queue"].append(entry)
    trim_and_save_queue()
    log_action("submit", nickname, ip, title, url)
    return jsonify({"ok": True, "queued": entry})

@app.post("/played")
def played():
    # Move the first item from queue to history
    if qstate["queue"]:
        item = qstate["queue"].pop(0)
        item["played_at"] = _now_iso()
        qstate["history"].append(item)
        trim_and_save_queue()
        log_action("played", item.get("by",""), item.get("ip",""), item.get("title",""), item.get("url",""))
        return jsonify({"ok": True, "moved": item})
    return jsonify({"ok": False, "error": "Queue empty"}), 400

@app.post("/clear_queue")
def clear_queue():
    qstate["queue"].clear()
    trim_and_save_queue()
    log_action("clear_queue", "HOST", "0.0.0.0")
    return jsonify({"ok": True})

@app.post("/update_settings")
def update_settings():
    data = request.get_json(silent=True) or request.form
    sys = settings.setdefault("system", {})
    brand = settings.setdefault("branding", {})

    # Allowed fields
    if "nickname_cooldown_hours" in data:
        try:
            sys["nickname_cooldown_hours"] = int(data["nickname_cooldown_hours"])
        except Exception:
            pass
    if "theme" in data:
        sys["theme"] = str(data["theme"])
    if "auto_clear_days" in data:
        try:
            sys["auto_clear_days"] = int(data["auto_clear_days"])
        except Exception:
            pass
    if "logo_url" in data:
        brand["logo_url"] = str(data["logo_url"])
    if "system_name" in data:
        brand["system_name"] = str(data["system_name"])
    if "slogan" in data:
        brand["slogan"] = str(data["slogan"])
    if "new_password" in data and data.get("new_password"):
        sys["password_hash"] = hash_password(data["new_password"])

    save_settings()
    return jsonify({"ok": True, "settings": settings})

@app.get("/api/state")
def api_state():
    return jsonify({
        "settings": settings,
        "users": users,
        "queue": qstate.get("queue", []),
        "history": qstate.get("history", []),
        "last_saved": qstate.get("last_saved")
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
