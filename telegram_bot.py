import time
import sqlite3
import requests
import os
import json
from datetime import datetime
from gtts import gTTS

# Configuration
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8292074725:AAE9Asxr8aSDh-wxS7tNjMcEm_jQBmwLqqc")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6258896163")
UPPER_LEVEL_TOKEN = os.environ.get("UPPER_LEVEL_TOKEN", "8539630550:AAHm4gcWb9KUU2kDf5sDiSvRvSh7xE6AVcc")
UPPER_LEVEL_CHAT_ID = os.environ.get("UPPER_LEVEL_CHAT_ID", "6258896163")
UPPER_LEVEL_MIN = 15000
DB_PATH = "bets.db"
POLL_INTERVAL = 10  # Seconds
RADIO_SERVER_URL = os.environ.get("RADIO_SERVER_URL", "http://localhost:5002")

# Thresholds for alerts
FEED_ALERT_MIN = 5000  # Alert for feeds > $5k
SLIP_ALERT_MIN = 10000 # Alert for slips > $10k

def send_telegram_message(text, token=None, chat_id=None):
    t = token or TOKEN
    c = chat_id or CHAT_ID
    url = f"https://api.telegram.org/bot{t}/sendMessage"
    payload = {
        "chat_id": c,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.json().get("ok"):
            print(f"❌ Telegram error: {r.json().get('description')}")
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")

def send_telegram_voice(text):
    """Generate TTS audio and send it to our local live radio WebRTC server."""
    try:
        # Generate audio
        tts = gTTS(text=text, lang='en')
        audio_path = "temp_alert.ogg"
        tts.save(audio_path)
        
        # Send to the local Radio Broadcast Server rather than Telegram Voice
        url = f"{RADIO_SERVER_URL}/broadcast"
        with open(audio_path, 'rb') as audio_file:
            # We don't need chat ID anymore, we just send the file
            files = {"audio": audio_file}
            response = requests.post(url, files=files, timeout=5)
            
        # Clean up
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        if response.status_code != 200:
            print(f"❌ Failed to broadcast to radio server: {response.text}")
        else:
            print("📻 AUDIO BROADCAST SUCCESSFUL!")
    except Exception as e:
        print(f"❌ Error broadcasting to radio: {e}")

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ Database connection error: {e}")
        return None

def format_bet_message(bet):
    """Format the bet data into a readable Telegram message."""
    
    bet_type = bet['type']
    event = bet['event'] or "Unknown Event"
    amount = bet['amount_value'] or 0
    odds = bet['odds'] or "N/A"
    time_str = bet.get('time_str') or bet.get('time') or "N/A"
    url = bet['slip_url']
    
    # Emoji based on type and amount
    if bet_type == 'slip':
        emoji = "🎫 <b>SLIP CAPTURED</b>"
    elif amount >= 10000:
        emoji = "🚨 <b>HIGH ROLLER</b>"
    else:
        emoji = "💰 <b>NEW BET</b>"

    msg = f"{emoji}\n\n"
    msg += f"<b>Event:</b> {event}\n"
    msg += f"<b>Amount:</b> ${amount:,.2f}\n"
    msg += f"<b>Odds:</b> {odds}\n"
    msg += f"<b>Time:</b> {time_str}\n"
    
    if url:
        msg += f"\n🔗 <a href='{url}'>View Slip</a>"
    
    return msg

def format_amount(amount):
    """Format amount as Xk or X.Xk — clean and immediate."""
    k = amount / 1000
    if k == int(k):
        return f"{int(k)}k"
    return f"{k:.1f}k"


def shorten_event(event):
    """
    Strip event down to the minimum recognisable signal.
    Player vs Player: surnames only — "Sekulic, Eqbal"
    Team vs Team: first meaningful word(s) — "Real Madrid, Bayern"
    Multi/Parlay: "Multi"
    """
    if not event:
        return ""

    event = event.strip()

    if event.lower().startswith("multi"):
        return "Multi"

    if " - " in event:
        parts = event.split(" - ", 1)
        names = []
        for part in parts:
            part = part.strip()
            if "," in part:
                # Player format: "Lastname, Firstname" — take surname only
                names.append(part.split(",")[0].strip())
            else:
                # Team format — take first two words
                words = part.split()
                names.append(" ".join(words[:2]))
        return ", ".join(names)

    # Fallback — first three words
    return " ".join(event.split()[:3])


def build_scanner_call(bet):
    """
    Build the radio call. Format: "[amount]. [event]. [odds]."
    No preamble. No labels. Pure signal.
    """
    amount = bet.get('amount_value') or 0
    event = bet.get('event') or ''
    odds = bet.get('odds') or ''

    parts = [format_amount(amount)]

    event_short = shorten_event(event)
    if event_short:
        parts.append(event_short)

    if odds:
        parts.append(str(odds))

    return ". ".join(parts) + "."


def radio_is_healthy():
    """Check radio server is up before attempting broadcast."""
    try:
        r = requests.get(f"{RADIO_SERVER_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def run_bot():
    print("🤖 Telegram Bot Started...")
    print(f"   Target Chat ID: {CHAT_ID}")

    last_check_time = time.time()
    seen_keys = set()  # Deduplication — tracks key+type within this session

    while True:
        conn = get_db_connection()
        if not conn:
            time.sleep(POLL_INTERVAL)
            continue

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bets WHERE timestamp > ? ORDER BY timestamp ASC",
                (last_check_time,)
            )
            rows = cursor.fetchall()

            for row in rows:
                bet = dict(row)
                timestamp = bet['timestamp']
                amount = bet['amount_value'] or 0
                bet_type = bet['type']
                dedup_key = f"{bet.get('key','')}-{bet_type}"

                if timestamp > last_check_time:
                    last_check_time = timestamp

                # Skip anything already processed this session
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                # Keep seen_keys from growing unbounded
                if len(seen_keys) > 2000:
                    seen_keys.clear()

                # Telegram text — feed type only (slip is handled by extension photo)
                should_alert = (bet_type == 'feed' and amount >= FEED_ALERT_MIN)

                # Radio — feed type only, no slip duplicates
                should_broadcast = (amount >= FEED_ALERT_MIN and bet_type == 'feed')

                if should_alert:
                    msg = format_bet_message(bet)
                    send_telegram_message(msg)
                    print(f"✅ {bet['event']} (${amount})")

                if should_alert and amount >= UPPER_LEVEL_MIN:
                    send_telegram_message(msg, token=UPPER_LEVEL_TOKEN, chat_id=UPPER_LEVEL_CHAT_ID)
                    print(f"🌟 UPPER LEVEL {bet['event']} (${amount})")

                if should_broadcast:
                    if radio_is_healthy():
                        call = build_scanner_call(bet)
                        print(f"📻 {call}")
                        send_telegram_voice(call)
                    else:
                        print(f"⚠️  Radio down — skipped broadcast for {bet['event']}")

                time.sleep(0.5)

        except Exception as e:
            print(f"❌ Error in bot loop: {e}")
        finally:
            conn.close()

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    # Wait for DB to be created if it doesn't exist
    while not os.path.exists(DB_PATH):
        print("⏳ Waiting for database...", end='\r')
        time.sleep(5)
    
    run_bot()
