import os, time, requests, threading, json
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("SPORTMONKS_TOKEN")
BOT = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot v4")
    def log_message(self, *a): pass

def run_server():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), Handler).serve_forever()
threading.Thread(target=run_server, daemon=True).start()

CACHE_FILE = "/tmp/cache_v4.json"

def load_all():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"goals_score": {}, "goals_id": {}, "started": [], "ht": [], "last_score": {}}

def save_all(d):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(d, f)
    except: pass

CACHE = load_all()
FIRST_RUN = len(CACHE["goals_score"]) == 0

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

print(f"Bot v4 - FIRST_RUN={FIRST_RUN}")
if FIRST_RUN:
    tg("⚡️ v4 LIVE - silent first run, no spam")

while True:
    try:
        r = requests.get("https://api.sportmonks.com/v3/football/livescores/latest",
            params={"api_token": TOKEN, "include": "scores;events;participants;league;state"}, timeout=15)
        if r.status_code == 429:
            print("Rate limited - wait 60s")
            time.sleep(60)
            continue
        if r.status_code != 200:
            time.sleep(10)
            continue
            
        data = r.json().get("data", [])

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

            # --- FIRST RUN: SILENTLY LEARN EVERYTHING ---
            if FIRST_RUN:
                CACHE["started"].append(fid) if fid not in CACHE["started"] else None
                if short == "HT" or sid == 3:
                    if fid not in CACHE["ht"]: CACHE["ht"].append(fid)
                score_key = f"{hs}-{aws}"
                if fid not in CACHE["goals_score"]:
                    CACHE["goals_score"][fid] = []
                if score_key not in CACHE["goals_score"][fid] and score_key != "0-0":
                    CACHE["goals_score"][fid].append(score_key)
                CACHE["last_score"][fid] = int(hs)+int(aws)
                # also save event ids
                if fid not in CACHE["goals_id"]:
                    CACHE["goals_id"][fid] = []
                for g in [e for e in f.get("events", []) if e.get("type_id")==18]:
                    if str(g["id"]) not in CACHE["goals_id"][fid]:
                        CACHE["goals_id"][fid].append(str(g["id"]))
                continue

            # --- NORMAL RUN ---
            # 1. STARTED - persisted!
            is_live = short in ["1H","2H","INPLAY","LIVE","HT"] or sid in [2,3,4,5,22]
            if is_live and fid not in CACHE["started"]:
                tg(f"🏁 <b>MATCH STARTED! {league}</b>\n{home} vs {away}")
                CACHE["started"].append(fid)
                save_all(CACHE)

            # 2. HALF-TIME - persisted!
            is_ht = short == "HT" or sid == 3
            if is_ht and fid not in CACHE["ht"]:
                tg(f"⏸️ <b>HALF-TIME {league}</b>\n{home} {hs}-{aws} {away}")
                CACHE["ht"].append(fid)
                save_all(CACHE)

            # 3. GOAL - DOUBLE PROTECTION
            score_key = f"{hs}-{aws}"
            total = int(hs)+int(aws)
            last_total = CACHE["last_score"].get(fid, 0)

            # Only if total goals increased
            if total <= last_total or total == 0:
                continue

            # Only if we never sent this exact score for this game
            if fid in CACHE["goals_score"] and score_key in CACHE["goals_score"][fid]:
                # Already sent 1-0, don't send again
                CACHE["last_score"][fid] = total
                continue

            # Find newest event minute for this score
            goals = [e for e in f.get("events", []) if e.get("type_id")==18]
            if not goals:
                continue
            minute = goals[-1].get("minute", 0)

            # EVENT ID CHECK TOO
            new_ids = [str(g["id"]) for g in goals if str(g["id"]) not in CACHE["goals_id"].get(fid, [])]
            if not new_ids and fid in CACHE["goals_id"]:
                # No new event id, but score increased? Could be correction, still skip if score already sent
                pass

            tg(f"🚨 <b>GOAL! {league}</b>\n{home} {hs}-{aws} {away}\n⏱ {minute}'\n💰 BET NOW")
            
            if fid not in CACHE["goals_score"]: CACHE["goals_score"][fid] = []
            CACHE["goals_score"][fid].append(score_key)
            if fid not in CACHE["goals_id"]: CACHE["goals_id"][fid] = []
            for nid in new_ids: CACHE["goals_id"][fid].append(nid)
            CACHE["last_score"][fid] = total
            save_all(CACHE)
            time.sleep(0.6)

        if FIRST_RUN:
            save_all(CACHE)
            FIRST_RUN = False
            print(f"First run saved {len(CACHE['started'])} games")
            # Don't spam, just log

    except Exception as e:
        print("ERR:", e)
    time.sleep(6)