import os, time, re, base64
from flask import Flask, request, jsonify, render_template, session, send_file, abort
from io import BytesIO

APP_TITLE = os.getenv("APP_TITLE", "YouTube Queue Online")
HOST_API_KEY = os.getenv("HOST_API_KEY", "ytq-premium-2025-dxd")
RATE_LIMIT_S = int(os.getenv("RATE_LIMIT_S", "180"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

app = Flask(__name__)
app.secret_key = SECRET_KEY

YT = re.compile(r"(youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})")
now = lambda: int(time.time())

STATE = {
  "queue": [], "history": [], "current": None,
  "progress": {"pos":0,"dur":0},
  "settings":{"rate_limit": RATE_LIMIT_S, "nick_hours":24},
  "nicknames":{}, "last_submit":{},
  "logo_b64": None,
  "host_auth":{"username":"Admin","password":"0000"}
}

def is_host(): return bool(session.get("host_ok"))
def require_host():
  if not is_host(): abort(401)
def vid(url):
  m = YT.search(url or ""); return m.group(2) if m else None

@app.get("/")
def index(): return render_template("index.html", app_title=APP_TITLE, logo_url=("/logo" if STATE["logo_b64"] else None))
@app.get("/host")
def host(): return render_template("host.html", app_title=APP_TITLE, logo_url=("/logo" if STATE["logo_b64"] else None))

@app.get("/logo")
def logo():
  if not STATE["logo_b64"]: abort(404)
  return send_file(BytesIO(base64.b64decode(STATE["logo_b64"])), mimetype="image/png")

@app.post("/api/login")
def login():
  d=request.get_json(silent=True) or {}; u=d.get("username",""); p=d.get("password","")
  if u==STATE["host_auth"]["username"] and p==STATE["host_auth"]["password"]:
    session["host_ok"]=True; return jsonify(ok=True)
  return jsonify(ok=False,error="Not authorized"),401

@app.post("/api/logout")
def logout(): session.clear(); return jsonify(ok=True)

@app.get("/api/check_host")
def check_host(): return jsonify(ok=is_host())

@app.get("/api/state")
def state():
  ip=request.headers.get("X-Forwarded-For", request.remote_addr) or "0.0.0.0"
  rl=STATE["settings"]["rate_limit"]; last=STATE["last_submit"].get(ip,0)
  remain=max(0, rl-(now()-last)) if last else 0
  return jsonify(queue=STATE["queue"], history=STATE["history"], current=STATE["current"], progress=STATE["progress"], settings=STATE["settings"], rate_remaining=remain)

@app.post("/api/submit")
def submit():
  d=request.get_json(silent=True) or {}; url=(d.get("url") or "").strip(); name=(d.get("nickname") or "").strip()
  if not url or not name: return jsonify(ok=False,error="Nickname and URL are required."),400
  if "youtu" not in url: return jsonify(ok=False,error="Please submit a valid YouTube link."),400
  v=vid(url); 
  if not v: return jsonify(ok=False,error="Invalid YouTube URL."),400
  ip=request.headers.get("X-Forwarded-For", request.remote_addr) or "0.0.0.0"
  rl=STATE["settings"]["rate_limit"]; last=STATE["last_submit"].get(ip,0)
  if last and now()-last<rl: return jsonify(ok=False,error=f"Please wait {rl-(now()-last)}s before next submit."),429
  if ip not in STATE["nicknames"]: STATE["nicknames"][ip]={"name":name,"changed_at":now()}
  item={"id":f"{now()}_{len(STATE['queue'])+1}","url":url,"vid":v,"title":url,"by":STATE["nicknames"][ip]["name"],"at":now()}
  STATE["queue"].append(item); STATE["last_submit"][ip]=now()
  if STATE["current"] is None:
    STATE["current"]=STATE["queue"].pop(0); STATE["progress"]={"pos":0,"dur":0}
  return jsonify(ok=True,item=item)

@app.post("/api/progress")
def progress():
  require_host()
  d=request.get_json(silent=True) or {}; pos=float(d.get("pos") or 0); dur=float(d.get("dur") or 0)
  STATE["progress"]={"pos":max(0,pos),"dur":max(0,dur)}; return jsonify(ok=True)

@app.post("/api/next")
def nxt():
  require_host()
  if STATE["current"]: STATE["history"].insert(0,STATE["current"])
  STATE["current"]=STATE["queue"].pop(0) if STATE["queue"] else None
  STATE["progress"]={"pos":0,"dur":0}; return jsonify(ok=True,current=STATE["current"])

@app.post("/api/prev")
def prev():
  require_host()
  if STATE["history"]:
    prev=STATE["history"].pop(0)
    if STATE["current"]: STATE["queue"].insert(0,STATE["current"])
    STATE["current"]=prev; STATE["progress"]={"pos":0,"dur":0}
  return jsonify(ok=True,current=STATE["current"])

@app.post("/api/clear")
def clear(): require_host(); STATE["queue"].clear(); return jsonify(ok=True)

@app.post("/api/save_settings")
def save_settings():
  require_host(); d=request.get_json(silent=True) or {}
  try:
    rl=int(d.get("rate_limit")); nh=int(d.get("nick_hours"))
    if rl<0 or nh<1: raise ValueError
    STATE["settings"]["rate_limit"]=rl; STATE["settings"]["nick_hours"]=nh
    return jsonify(ok=True,settings=STATE["settings"])
  except: return jsonify(ok=False,error="Invalid settings"),400

@app.post("/api/host_auth")
def host_auth():
  d=request.get_json(silent=True) or {}
  key=(d.get("host_api_key") or "").strip()
  if key!=HOST_API_KEY: return jsonify(ok=False,error="Invalid HOST_API_KEY"),403
  u=(d.get("username") or "").strip(); p=(d.get("password") or "").strip()
  if not u or not p: return jsonify(ok=False,error="Missing username/password"),400
  STATE["host_auth"]={"username":u,"password":p}; return jsonify(ok=True)

@app.post("/api/upload_logo")
def upload_logo():
  require_host()
  if "file" not in request.files: return jsonify(ok=False,error="No file"),400
  data=request.files["file"].read(); STATE["logo_b64"]=base64.b64encode(data).decode("ascii")
  return jsonify(ok=True)

@app.get("/healthz")
def healthz(): return "ok"

if __name__=="__main__":
  app.run(host="0.0.0.0", port=5000, debug=True)
