import os, time, requests, threading, json
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("SPORTMONKS_TOKEN")
BOT = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

# --- Keep Render alive ---
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

# --- Persistent cache to stop repeats after restart ---
CACHE_FILE = "goal_cache.json"
def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            # convert lists back to sets
            return {k: set(v) for k, v in data.items()}
    except:
        return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w") as f:
            # sets not json serializable
            json.dump({k: list(v) for k, v in cache.items()}, f)
    except: pass

cache_goals = load_cache()  # fid -> set(event_ids)
cache_started = {}
cache_ht = {}
interval = 6

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

print("Bot Live - FIXED v2")
tg("⚡️ Bot LIVE - FIXED - No duplicates")

while True:
    try:
        url = "https://api.sportmonks.com/v3/football/livescores/latest"
        params = {"api_token": TOKEN, "include": "scores;events;participants;league;state"}
        r = requests.get(url, params=params, timeout=15)
        
        if r.status_code == 429:
            time.sleep(60)
            continue
        if r.status_code != 200:
            time.sleep(10)
            continue
            
        data = r.json().get("data", [])
        if not data:
            interval = min(30, interval + 3)
            time.sleep(interval)
            continue
        else:
            interval = 6

        for f in data:
            fid = str(f["id"])
            league = f["league"]["name"]
            home = next((p["name"] for p in f["participants"] if p["meta"]["location"]=="home"), f["participants"][0]["name"])
            away = next((p["name"] for p in f["participants"] if p["meta"]["location"]=="away"), f["participants"][1]["name"])
            
            state = f.get("state", {})
            short = str(state.get("short_state") or state.get("state") or "").upper()
            sid = state.get("id")

            cur = [s for s in f.get("scores", []) if s.get("description")=="CURRENT"]
            hs = next((s["score"]["goals"] for s in cur if s["score"]["participant"]=="home"), None)
            aws = next((s["score"]["goals"] for s in cur if s["score"]["participant"]=="away"), None)
            if hs is None or aws is None:
                continue # score not ready yet, skip

            # 1. STARTED
            is_live = short in ["1H","2H","INPLAY","LIVE","HT"] or sid in [2,3,4,5,22]
            if is_live and fid not in cache_started:
                tg(f"🏁 <b>MATCH STARTED! {league}</b>\n{home} vs {away}")
                cache_started[fid] = True

            # 2. HALF-TIME
            is_ht = short == "HT" or sid == 3
            if is_ht and fid not in cache_ht:
                tg(f"⏸️ <b>HALF-TIME {league}</b>\n{home} {hs}-{aws} {away}")
                cache_ht[fid] = True

            # 3. GOALS - FIXED LOGIC
            goals = [e for e in f.get("events", []) if e.get("type_id") == 18]
            
            if fid not in cache_goals:
                cache_goals[fid] = set()

            for g in goals:
                gid = str(g["id"])
                if gid in cache_goals[fid]:
                    continue # Already sent, skip

                # --- FIX FOR 0-0 FAKE GOALS ---
                # Don't alert if score is still 0-0 but we have a goal event (score hasn't updated yet)
                total_goals = int(hs) + int(aws)
                if total_goals == 0:
                    # If score says 0-0, but event exists, wait for next poll when score updates
                    continue

                minute = g.get("minute", 0)
                tg(f"🚨 <b>GOAL! {league}</b>\n{home} {hs}-{aws} {away}\n⏱ {minute}'\n💰 BET NOW")
                cache_goals[fid].add(gid)
                save_cache(cache_goals)
                time.sleep(0.5) # avoid telegram flood

    except Exception as e:
        print("Error:", e)
    time.sleep(interval)