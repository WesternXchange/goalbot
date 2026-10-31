import os, time, requests, threading, json
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("SPORTMONKS_TOKEN")
BOT = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")
    def log_message(self, *a): pass

def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
threading.Thread(target=run_server, daemon=True).start()

CACHE_FILE = "/tmp/goal_cache.json" # use /tmp on Render - persists longer
def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            d = json.load(f)
            return {k: set(v) for k, v in d.items()}
    except:
        return {}
def save_cache(c):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({k: list(v) for k, v in c.items()}, f)
    except: pass

cache_goals = load_cache()
cache_started = {}
cache_ht = {}
FIRST_RUN = True  # <--- KEY FIX

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

print("Bot Live - v3 silent startup")
# Don't send startup message if cache exists (avoid spam on restart)
if not cache_goals:
    tg("⚡️ Bot LIVE - v3 no-spam")

while True:
    try:
        r = requests.get("https://api.sportmonks.com/v3/football/livescores/latest",
            params={"api_token": TOKEN, "include": "scores;events;participants;league;state"}, timeout=15)
        if r.status_code == 429:
            time.sleep(60)
            continue
        if r.status_code != 200:
            time.sleep(10)
            continue
        data = r.json().get("data", [])
        if not data:
            time.sleep(15)
            continue

        for f in data:
            fid = str(f["id"])
            league = f["league"]["name"]
            home = next((p["name"] for p in f["participants"] if p["meta"]["location"]=="home"), f["participants"][0]["name"])
            away = next((p["name"] for p in f["participants"] if p["meta"]["location"]=="away"), f["participants"][1]["name"])
            short = str(f.get("state", {}).get("short_state") or "").upper()
            sid = f.get("state", {}).get("id")

            cur = [s for s in f.get("scores", []) if s.get("description")=="CURRENT"]
            hs = next((s["score"]["goals"] for s in cur if s["score"]["participant"]=="home"), None)
            aws = next((s["score"]["goals"] for s in cur if s["score"]["participant"]=="away"), None)
            if hs is None or aws is None:
                continue

            # --- SILENT POPULATE ON FIRST RUN ---
            if FIRST_RUN:
                # Mark all current live games as already started
                is_live = short in ["1H","2H","INPLAY","LIVE","HT"] or sid in [2,3,4,5,22]
                if is_live:
                    cache_started[fid] = True
                if short == "HT" or sid == 3:
                    cache_ht[fid] = True
                # Mark all current goals as already seen
                if fid not in cache_goals:
                    cache_goals[fid] = set()
                for g in [e for e in f.get("events", []) if e.get("type_id")==18]:
                    cache_goals[fid].add(str(g["id"]))
                continue

            # Normal logic after first run
            is_live = short in ["1H","2H","INPLAY","LIVE","HT"] or sid in [2,3,4,5,22]
            if is_live and fid not in cache_started:
                tg(f"🏁 <b>MATCH STARTED! {league}</b>\n{home} vs {away}")
                cache_started[fid] = True

            is_ht = short == "HT" or sid == 3
            if is_ht and fid not in cache_ht:
                tg(f"⏸️ <b>HALF-TIME {league}</b>\n{home} {hs}-{aws} {away}")
                cache_ht[fid] = True

            goals = [e for e in f.get("events", []) if e.get("type_id")==18]
            if fid not in cache_goals:
                cache_goals[fid] = set()
            
            for g in goals:
                gid = str(g["id"])
                if gid in cache_goals[fid]:
                    continue
                if int(hs)+int(aws) == 0:
                    # Score still 0-0, wait
                    continue
                tg(f"🚨 <b>GOAL! {league}</b>\n{home} {hs}-{aws} {away}\n⏱ {g.get('minute',0)}'\n💰 BET NOW")
                cache_goals[fid].add(gid)
                save_cache(cache_goals)

        if FIRST_RUN:
            save_cache(cache_goals)
            FIRST_RUN = False
            print(f"First run done, cached {len(cache_goals)} games")

    except Exception as e:
        print(e)
    time.sleep(6)