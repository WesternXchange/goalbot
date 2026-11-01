import os, time, requests, threading, json
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("SPORTMONKS_TOKEN")
BOT = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")
UP_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UP_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot v5 Redis")
    def log_message(self, *a): pass

def run_server():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), Handler).serve_forever()
threading.Thread(target=run_server, daemon=True).start()

def redis_get():
    try:
        r = requests.post(f"{UP_URL}", 
            headers={"Authorization": f"Bearer {UP_TOKEN}"},
            json=["GET", "goalbot_v5"], timeout=5)
        val = r.json().get("result")
        if val:
            return json.loads(val)
    except: pass
    return {"goals_score": {}, "started": [], "ht": [], "last_score": {}}

def redis_save(d):
    try:
        requests.post(f"{UP_URL}",
            headers={"Authorization": f"Bearer {UP_TOKEN}"},
            json=["SET", "goalbot_v5", json.dumps(d)], timeout=5)
    except: pass

CACHE = redis_get()
FIRST_RUN = len(CACHE["goals_score"]) == 0

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

print(f"Bot v5 Redis - FIRST_RUN={FIRST_RUN} - cache={len(CACHE['goals_score'])} games")
if FIRST_RUN:
    tg("⚡️ v5 REDIS LIVE - no more duplicates even after restart")

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

            if FIRST_RUN:
                if fid not in CACHE["started"] and (short in ["1H","2H","INPLAY","LIVE","HT"] or sid in [2,3,4,5,22]):
                    CACHE["started"].append(fid)
                if (short=="HT" or sid==3) and fid not in CACHE["ht"]:
                    CACHE["ht"].append(fid)
                score_key = f"{hs}-{aws}"
                if fid not in CACHE["goals_score"]: CACHE["goals_score"][fid]=[]
                if score_key!="0-0" and score_key not in CACHE["goals_score"][fid]:
                    CACHE["goals_score"][fid].append(score_key)
                CACHE["last_score"][fid]=int(hs)+int(aws)
                continue

            is_live = short in ["1H","2H","INPLAY","LIVE","HT"] or sid in [2,3,4,5,22]
            if is_live and fid not in CACHE["started"]:
                tg(f"🏁 <b>MATCH STARTED! {league}</b>\n{home} vs {away}")
                CACHE["started"].append(fid)
                redis_save(CACHE)

            is_ht = short=="HT" or sid==3
            if is_ht and fid not in CACHE["ht"]:
                tg(f"⏸️ <b>HALF-TIME {league}</b>\n{home} {hs}-{aws} {away}")
                CACHE["ht"].append(fid)
                redis_save(CACHE)

            score_key = f"{hs}-{aws}"
            total = int(hs)+int(aws)
            if total==0 or total <= CACHE["last_score"].get(fid,0):
                continue
            if fid in CACHE["goals_score"] and score_key in CACHE["goals_score"][fid]:
                CACHE["last_score"][fid]=total
                continue

            goals = [e for e in f.get("events", []) if e.get("type_id")==18]
            if not goals: continue
            minute = goals[-1].get("minute",0)

            tg(f"🚨 <b>GOAL! {league}</b>\n{home} {hs}-{aws} {away}\n⏱ {minute}'\n💰 BET NOW")
            if fid not in CACHE["goals_score"]: CACHE["goals_score"][fid]=[]
            CACHE["goals_score"][fid].append(score_key)
            CACHE["last_score"][fid]=total
            redis_save(CACHE)
            time.sleep(0.6)

        if FIRST_RUN:
            redis_save(CACHE)
            FIRST_RUN=False
            print("First run saved to Redis")

    except Exception as e:
        print("ERR", e)
    time.sleep(5)