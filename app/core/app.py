# -*- coding: utf-8 -*-
"""
YouTube Queue | Web — Core Backend (Flask)
Version: v01.6.2e (Secure + Full Compat)
Author: Duong – XDigital

What's new in v01.6.2e:
- Secure: /api/host/change_password now requires HOST_KEY.
- Nickname POST accepts FormData (request.form / request.values).
- Full compat routes for current frontend (/api/...).
- Render-safe IP detection, atomic JSON writes with logs.
- Persistent JSON storage + CSV activity log; trim Queue<=50, History<=20.
"""

import os
import json
import csv
from datetime import datetime, timedelta
from hashlib import sha256
from flask import Flask, request, jsonify, render_template

# ----- Paths -----
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.abspath(os.path.join(CORE_DIR, os.pardir))
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")
STATIC_DIR = os.path.join(APP_DIR, "static")
DATA_DIR = os.path.join(CORE_DIR, "data")

SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
QUEUE_FILE = os.path.join(DATA_DIR, "queue.json")
LOG_FILE = os.path.join(DATA_DIR, "activity_log.csv")

MAX_QUEUE = 50
MAX_HISTORY = 20


# ----- Utils -----
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
    """Atomic write + log so we can see success in Render Logs."""
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        print(f"[INFO] JSON written successfully: {path}")
    except Exception as e:
        print(f"[WARN] Could not write file {path}: {e}")


def log_action(action, user, ip, title="N/A", url="N/A"):
    header = ["timestamp", "action", "user", "ip", "title", "url"]
    exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerow([_now_iso(), action, user, ip, title, url])


def client_ip():
    """Robust IP detection behind proxies (Render)."""
    try:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.remote_addr or "0.0.0.0"
        if not ip or ip == "None":
            ip = "0.0.0.0"
        return ip
    except Exception:
        return "0.0.0.0"


def hash_password(pw: str) -> str:
    return sha256(pw.encode("utf-8")).hexdigest()


# ----- Init data -----
ensure_dirs()

default_settings = {
    "system": {
        "password_hash": hash_password("0000"),   # default host pass
        "host_key": "HOST_KEY",                   # security key required to change password
        "nickname_cooldown_hours": 1,
        "auto_clear_days": 7,                     # configured (not enforced here)
        "theme": "dark",
        "version": "v01.6.2e",
    },
    "branding": {
        "logo_url": "/static/logo.png",
        "system_name": "YouTube Queue",
        "slogan": "Office Music Queue",
    },
}
default_users = {}  # ip -> {nickname, last_changed}
default_queue = {"last_saved": _now_iso(), "queue": [], "history": []}

settings = read_json(SETTINGS_FILE, default_settings)
users = read_json(USERS_FILE, default_users)
qstate = read_json(QUEUE_FILE, default_queue)


def save_settings():
    write_json(SETTINGS_FILE, settings)
    log_action("change_setting", "HOST", "0.0.0.0", "settings.json", "N/A")


def save_users():
    write_json(USERS_FILE, users)


def trim_and_save_queue():
    if len(qstate.get("queue", [])) > MAX_QUEUE:
        qstate["queue"] = qstate["queue"][-MAX_QUEUE:]
    if len(qstate.get("history", [])) > MAX_HISTORY:
        qstate["history"] = qstate["history"][-MAX_HISTORY:]
    qstate["last_saved"] = _now_iso()
    write_json(QUEUE_FILE, qstate)


# ----- Flask app -----
app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)


# ===== Core routes (defined first) =====

@app.post("/verify_host")
def verify_host():
    data = request.get_json(silent=True) or request.form or request.values
    pw = (data.get("password") or "").strip()
    if hash_password(pw) == settings["system"]["password_hash"]:
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 403


@app.route("/")
def user_page():
    return render_template(
        "user.html",
        settings=settings,
        queue=qstate.get("queue", []),
        history=qstate.get("history", []),
        version=settings["system"].get("version", "v01.6.2e"),
    )


@app.route("/host")
def host_page():
    return render_template(
        "host.html",
        settings=settings,
        users=users,
        queue=qstate.get("queue", []),
        history=qstate.get("history", []),
        version=settings["system"].get("version", "v01.6.2e"),
    )


@app.post("/set_nickname")
def set_nickname():
    ip = client_ip()
    data = request.get_json(silent=True) or request.form or request.values
    nickname = (data.get("nickname") or "").strip()
    cooldown_h = settings["system"].get("nickname_cooldown_hours", 1)

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
        current = (old or {}).get("nickname", "Guest")
        return jsonify(
            {
                "ok": False,
                "message": "Cooldown active.",
                "remaining_seconds": remaining,
                "current": current,
            }
        ), 429


@app.post("/submit")
def submit():
    ip = client_ip()
    data = request.get_json(silent=True) or request.form or request.values
    url = (data.get("url") or "").strip()
    title = (data.get("title") or "").strip()

    if not url:
        return jsonify({"ok": False, "error": "Missing URL"}), 400

    nickname = users.get(ip, {}).get("nickname", "Guest")
    if not title:
        tail = url.split("/")[-1][:12]
        title = f"YouTube Item - {tail}"

    entry = {"title": title, "url": url, "by": nickname, "ip": ip, "time": _now_iso()}
    qstate["queue"].append(entry)
    trim_and_save_queue()
    log_action("submit", nickname, ip, title, url)
    return jsonify({"ok": True, "queued": entry})


@app.post("/played")
def played():
    if qstate["queue"]:
        item = qstate["queue"].pop(0)
        item["played_at"] = _now_iso()
        qstate["history"].append(item)
        trim_and_save_queue()
        log_action(
            "played",
            item.get("by", ""),
            item.get("ip", ""),
            item.get("title", ""),
            item.get("url", ""),
        )
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
    data = request.get_json(silent=True) or request.form or request.values
    sys = settings.setdefault("system", {})
    brand = settings.setdefault("branding", {})

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
    return jsonify(
        {
            "settings": settings,
            "users": users,
            "queue": qstate.get("queue", []),
            "history": qstate.get("history", []),
            "last_saved": qstate.get("last_saved"),
        }
    )


# ===== Compatibility routes for current frontend (/api/...) =====

@app.post("/api/host/verify")
def api_verify_host():
    data = request.get_json(silent=True) or request.form or request.values
    pw = (data.get("password") or "").strip()
    if hash_password(pw) == settings["system"]["password_hash"]:
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 403


@app.get("/api/nickname")
def api_nickname_get():
    ip = client_ip()
    cooldown_h = settings["system"].get("nickname_cooldown_hours", 1)
    limit_mins = cooldown_h * 60
    u = users.get(ip)
    valid = False
    remain_mins = 0
    name = None
    if u and u.get("last_changed"):
        try:
            last_dt = datetime.strptime(u["last_changed"], "%Y-%m-%dT%H:%M:%SZ")
            delta = datetime.utcnow() - last_dt
            remain = timedelta(hours=cooldown_h) - delta
            if remain.total_seconds() > 0:
                valid = True
                remain_mins = max(0, int(remain.total_seconds() // 60))
                name = u.get("nickname")
        except Exception:
            pass
    return jsonify({"ok": True, "valid": valid, "name": name, "remain_mins": remain_mins, "limit_mins": limit_mins})


@app.post("/api/nickname")
def api_nickname_post():
    # Reuse exact logic of /set_nickname
    return set_nickname()


@app.post("/api/add")
def api_add():
    # Reuse submit() logic and adapt the response shape if needed by UI
    resp = submit()
    if isinstance(resp, tuple):
        payload, status = resp
        try:
            data = payload.get_json()
        except Exception:
            return resp
        if data and data.get("ok"):
            item = data.get("queued")
            return jsonify({"ok": True, "item": item, "queued": item}), status
        return resp
    else:
        try:
            data = resp.get_json()
        except Exception:
            return resp
        if data and data.get("ok"):
            item = data.get("queued")
            return jsonify({"ok": True, "item": item, "queued": item})
        return resp


@app.post("/api/update_settings")
def api_update_settings():
    return update_settings()


@app.post("/api/logo")
def api_logo():
    # host.js uploads FormData with key "logo"
    f = request.files.get("logo")
    if not f:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    uploads_dir = os.path.join(STATIC_DIR, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    ext = os.path.splitext(f.filename or "")[1] or ".png"
    fname = f"logo_{int(datetime.utcnow().timestamp())}{ext}"
    save_path = os.path.join(uploads_dir, fname)
    f.save(save_path)

    settings.setdefault("branding", {})["logo_url"] = f"/static/uploads/{fname}"
    save_settings()
    return jsonify({"ok": True, "logo_url": settings["branding"]["logo_url"]})


@app.post("/api/config")
def api_config():
    data = request.get_json(silent=True) or request.form or request.values
    sys = settings.setdefault("system", {})
    if "rate_limit_s" in data:
        try:
            sys["rate_limit_s"] = int(data["rate_limit_s"])
        except Exception:
            pass
    if "nickname_valid_minutes" in data:
        try:
            mins = int(data["nickname_valid_minutes"])
            # keep backend canonical hours but also store minutes for UI convenience
            sys["nickname_cooldown_hours"] = max(1, int(round(mins / 60.0)))
            sys["nickname_valid_minutes"] = mins
        except Exception:
            pass
    save_settings()
    return jsonify({
        "ok": True,
        "rate_limit_s": sys.get("rate_limit_s", 180),
        "nickname_valid_minutes": sys.get("nickname_valid_minutes", sys.get("nickname_cooldown_hours", 1) * 60),
    })


@app.post("/api/host/change_password")
def api_host_change_password():
    data = request.get_json(silent=True) or request.form or request.values
    old_pw = (data.get("old_password") or "").strip()
    new_pw = (data.get("new_password") or "").strip()
    host_key = (data.get("key") or "").strip()

    sys = settings.setdefault("system", {})
    stored_hash = sys.get("password_hash")
    stored_key = sys.get("host_key", "HOST_KEY")

    if not new_pw:
        return jsonify({"ok": False, "error": "New password required"}), 400
    if hash_password(old_pw) != stored_hash:
        return jsonify({"ok": False, "error": "Old password incorrect"}), 403
    if host_key != stored_key:
        return jsonify({"ok": False, "error": "Invalid HOST_KEY"}), 403

    sys["password_hash"] = hash_password(new_pw)
    save_settings()
    return jsonify({"ok": True})


# ----- Entrypoint -----
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
