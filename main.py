import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("SPORTMONKS_TOKEN")
BOT = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

# Dummy web server to satisfy Render Web Service
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")
    def log_message(self, *args): pass

def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

cache = {}
interval = 6

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

print("Bot Live - Starter 5 leagues")
tg("⚡️ Bot LIVE - 5 Slowest Leagues - 6sec - GOALS ONLY - Port Fixed")

while True:
    try:
        url = "https://api.sportmonks.com/v3/football/livescores/latest"
        params = {"api_token": TOKEN, "include": "scores;events;participants;league;state"}
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 429:
            time.sleep(30)
            continue
        if r.status_code != 200:
            time.sleep(10)
            continue
        data = r.json().get("data", [])
        if not data:
            interval = min(30, interval + 6)
            time.sleep(interval)
            continue
        else:
            interval = 6
        for f in data:
            fid = f["id"]
            goals = [e for e in f.get("events", []) if e.get("type_id") == 18]
            count = len(goals)
            old = cache.get(fid, None)
            if old is None:
                cache[fid] = count
                continue
            if count > old:
                last = goals[-1]
                league = f["league"]["name"]
                home = next((p["name"] for p in f["participants"] if p["meta"]["location"]=="home"), f["participants"][0]["name"])
                away = next((p["name"] for p in f["participants"] if p["meta"]["location"]=="away"), f["participants"][1]["name"])
                minute = last.get("minute", 0)
                cur = [s for s in f.get("scores", []) if s.get("description")=="CURRENT"]
                hs = next((s["score"]["goals"] for s in cur if s["score"]["participant"]=="home"), "?")
                aws = next((s["score"]["goals"] for s in cur if s["score"]["participant"]=="away"), "?")
                msg = f"🚨 <b>GOAL! {league}</b>\n{home} {hs}-{aws} {away}\n⏱ {minute}'\n💰 BET NOW"
                tg(msg)
            cache[fid] = count
    except Exception as e:
        print(e)
    time.sleep(interval)