import os
import time
import requests

TOKEN = os.getenv("SPORTMONKS_TOKEN")
BOT = os.getenv("BOT_TOKEN")
CHAT = os.getenv("CHAT_ID")

# No league IDs needed - your account is already limited to the 5 you saved:
# Tunisia, Egypt, Algeria, SA PSL, Morocco
cache = {} # Logic Step 2: cache tracked fields
interval = 6  # Logic Step 1: 6000ms - screenshot says min 5-8 sec

def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT}/sendMessage",
            json={"chat_id": CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"TG error {e}")

print("Bot Live - Starter 5 leagues")
tg("⚡️ Bot LIVE - 5 Slowest Leagues (Tunisia, Egypt, Algeria, SA, Morocco) - 6sec - GOALS ONLY")

while True:
    try:
        # Screenshot Best Practice: Use includes to combine data
        url = "https://api.sportmonks.com/v3/football/livescores/latest"
        params = {
            "api_token": TOKEN,
            "include": "scores;events;participants;league;state"
        }
        r = requests.get(url, params=params, timeout=15)

        # Handle 429
        if r.status_code == 429:
            print("429 - backing off 30s")
            time.sleep(30)
            continue
        if r.status_code != 200:
            print(f"API {r.status_code} {r.text[:200]}")
            time.sleep(10)
            continue

        data = r.json().get("data", [])

        # Logic Step 4: If empty, back off to preserve calls
        if not data:
            interval = min(30, interval + 6)
            print(f"No live games in your 5 leagues - back off to {interval}s")
            time.sleep(interval)
            continue
        else:
            interval = 6

        # Logic Step 3: Compare against local cache - skip if unchanged
        for f in data:
            fid = f["id"]
            # Only GOAL events - type_id 18 = goal
            goal_events = [e for e in f.get("events", []) if e.get("type_id") == 18]
            count = len(goal_events)
            old_count = cache.get(fid, None)

            # First time we see fixture, just cache it, don't alert
            if old_count is None:
                cache[fid] = count
                continue

            # New goal detected
            if count > old_count:
                last = goal_events[-1]
                league = f["league"]["name"]
                # participants order can vary
                home = next((p["name"] for p in f["participants"] if p["meta"]["location"]=="home"), f["participants"][0]["name"])
                away = next((p["name"] for p in f["participants"] if p["meta"]["location"]=="away"), f["participants"][1]["name"])
                minute = last.get("minute", 0)
                scorer = last.get("player_name", "Goal")

                # Current score
                scores = f.get("scores", [])
                cur = [s for s in scores if s.get("description")=="CURRENT"]
                hs = next((s["score"]["goals"] for s in cur if s["score"]["participant"]=="home"), "?")
                aws = next((s["score"]["goals"] for s in cur if s["score"]["participant"]=="away"), "?")

                msg = f"🚨 <b>GOAL! {league}</b>\n{home} {hs}-{aws} {away}\n⏱ {minute}' - {scorer}\n💰 BET NOW on SportyBet"
                tg(msg)
                print(msg)

            # Update cache
            cache[fid] = count

    except Exception as e:
        print(f"Loop error {e}")

    time.sleep(interval)