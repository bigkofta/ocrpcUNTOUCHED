#!/usr/bin/env python3

"""
receiver.py

Simple local endpoint that receives parsed bet rows and stores them in bets.jsonl

Run:

    pip install flask flask-cors

    python receiver.py

"""

import json
import os
from dotenv import load_dotenv
load_dotenv()  # Load .env variables natively to bypass stale PowerShell supervisor cache

import time
import threading
import requests
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import sys

# Force UTF-8 for Windows output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ═══════════════════════════════════════════════════════════════
# TELEGRAM CONFIG (Load from environment)
# ═══════════════════════════════════════════════════════════════
# Main Channel (CuriousGeorge)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

# VIP Channel (UpperLevel) - for bets >= $15k
VIP_BOT_TOKEN = os.environ.get("TELEGRAM_VIP_TOKEN", TELEGRAM_BOT_TOKEN)  # Falls back to main
VIP_CHAT_ID = os.environ.get("TELEGRAM_VIP_CHAT_ID", TELEGRAM_CHAT_ID)    # Falls back to main
VIP_THRESHOLD = 15000  # Minimum amount for VIP channel

# Thresholds for Telegram alerts (main channel)
TG_ALERT_MIN = {"multi": 1000, "standard": 14750}

def send_telegram_alert(payload, photo_path=None, target_chat_id=None, bot_token=None):
    """Send alert to Telegram with optional photo (non-blocking)"""
    if not TELEGRAM_ENABLED:
        return
    
    # Use provided or default to main channel
    chat_id = target_chat_id or TELEGRAM_CHAT_ID
    token = bot_token or TELEGRAM_BOT_TOKEN
    
    def _send():
        try:
            event = payload.get("event", "Unknown")
            amount = payload.get("amount_value", 0)
            amount_raw = payload.get("amount_raw", f"${amount}")
            odds = payload.get("odds", "N/A")
            slip_url = payload.get("slip_url", "")
            bet_time = payload.get("time", "")
            bet_type = "Multi" if "multi" in event.lower() else "Standard"
            
            text = f"""🎰 <b>HIGH ROLLER</b> ({bet_type})

<b>Amount:</b> {amount_raw}
<b>Event:</b> {event[:100]}
<b>Odds:</b> {odds}
<b>Time:</b> {bet_time}

🔗 <a href="{slip_url}">View Slip</a>"""

            # Send photo if available, otherwise just text
            if photo_path and os.path.exists(photo_path):
                print(f"📸 Sending photo to Telegram ({chat_id}): {photo_path}")
                with open(photo_path, 'rb') as photo_file:
                    response = requests.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={
                            "chat_id": chat_id,
                            "caption": text,
                            "parse_mode": "HTML"
                        },
                        files={"photo": photo_file},
                        timeout=30
                    )
                if response.status_code == 200:
                    resp_json = response.json()
                    if resp_json.get("ok"):
                        print(f"✅ Photo sent ({chat_id}): {event[:30]}... ${amount}")
                    else:
                        print(f"⚠️ Telegram rejected photo ({chat_id}): {resp_json}")
                else:
                    print(f"⚠️ Photo send HTTP {response.status_code} ({chat_id}): {response.text[:300]}")
            else:
                # Text only fallback
                response = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    print(f"📤 TG text ({chat_id}): {event[:30]}... ${amount}")
                else:
                    print(f"⚠️ TG error ({chat_id}): {response.text[:100]}")
        except Exception as e:
            print(f"⚠️ TG send failed ({chat_id}): {e}")
    
    # Run in background thread
    threading.Thread(target=_send, daemon=True).start()

# Helper for detailed logging
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# Create screenshots directory
os.makedirs('screenshots', exist_ok=True)

print(f"✅ Receiver Starting...")
print(f"📂 CWD: {os.getcwd()}")
print(f"📸 Screenshots directory: {os.path.abspath('screenshots')}")
# --- CORS & Encoding Fix ---
# Azure Event Hubs integration (optional)
EVENT_HUBS_ENABLED = False
eventhub_producer_client = None
eventhub_connection_string = None
eventhub_name = None

try:
    from azure.eventhub import EventHubProducerClient, EventData
    eventhub_connection_string = os.getenv("EVENTHUB_CONNECTION_STRING", "")
    eventhub_name = os.getenv("EVENTHUB_NAME", "bets")
    
    if eventhub_connection_string:
        try:
            eventhub_producer_client = EventHubProducerClient.from_connection_string(
                conn_str=eventhub_connection_string,
                eventhub_name=eventhub_name
            )
            EVENT_HUBS_ENABLED = True
            print(f"✅ Azure Event Hubs enabled: {eventhub_name}")
        except Exception as e:
            print(f"⚠️  Event Hubs connection failed: {e}")
            print("   Continuing with local storage only...")
    else:
        print("ℹ️  Event Hubs not configured (EVENTHUB_CONNECTION_STRING not set)")
        print("   Using local storage only (bets.jsonl)")
except ImportError:
    print("⚠️  azure-eventhub not installed. Install with: pip install azure-eventhub")
    print("   Continuing with local storage only...")

app = Flask(__name__)

# CORS configuration - comprehensive for Extension and Stake.com
CORS(app, resources={
    r"/*": {
        "origins": ["https://stake.com", "*"],
        "methods": ["POST", "GET", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "x-auth-token", "ngrok-skip-browser-warning"],
        "expose_headers": ["*"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

LOGFILE = "bets.jsonl"
MIN_AMOUNT = 2500  # Match browser script FEED_MIN
# Set your secret token here (or via environment variable)
RECEIVER_TOKEN = os.getenv("RECEIVER_TOKEN", "")  # Leave empty to disable token check

# Deduplication: track recent bets by key to avoid duplicates
# Stores: key -> {"ts": timestamp, "has_url": bool, "has_photo": bool}
recent_bets = {} 
DEDUP_WINDOW = 120  # seconds - increased window for enrichment

def send_to_event_hubs_async(payload_data):
    """Send bet data to Azure Event Hubs asynchronously (non-blocking)"""
    if not EVENT_HUBS_ENABLED or not eventhub_producer_client:
        return
    
    def _send():
        try:
            event_data = EventData(json.dumps(payload_data))
            # Send event - producer client is already initialized
            eventhub_producer_client.send_batch([event_data])
        except Exception as e:
            # Log error but don't fail the main request
            print(f"⚠️  Event Hubs send failed: {e}")
    
    # Run in background thread to avoid blocking the HTTP response
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()

@app.route("/export", methods=["GET"])
def export_data():
    """Export all bets as CSV"""
    import csv
    import io
    from flask import make_response

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM bets ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    # Header
    if rows:
        cw.writerow(rows[0].keys())
        # Data
        for row in rows:
             cw.writerow(list(row))
    else:
        cw.writerow(["No data found"])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=highroller_bets.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route("/bets", methods=["POST"])
def bets():
    origin = request.headers.get("Origin", "")
    
    # Validate auth token if set
    if RECEIVER_TOKEN:
        provided_token = request.headers.get("x-auth-token", "")
        if provided_token != RECEIVER_TOKEN:
            return jsonify({"status": "unauthorized"}), 401
    
    data = request.get_json(force=True)

    print(f"Incoming keys: {list(data.keys())}")
    if "screenshot" in data:
        print(f"Screenshot data length: {len(data['screenshot'])}")
    else:
        print("No screenshot field in payload!")

    # Map browser script fields to receiver fields
    # Browser script sends: type, ts, iid, error
    # Receiver expects: detected_at, slip_id, etc.
    detected_at = data.get("detected_at") or data.get("ts")  # Map ts -> detected_at
    slip_id = data.get("slip_id") or data.get("iid")  # Map iid -> slip_id
    
    # Handle screenshot if provided
    screenshot_path = None
    screenshot_data = data.get("screenshot")
    if screenshot_data:
        try:
            # Save screenshot (base64 data URI format: "data:image/png;base64,xxxxx")
            import base64
            from datetime import datetime
            
            # Extract base64 part
            if ',' in screenshot_data:
                screenshot_b64 = screenshot_data.split(',', 1)[1]
            else:
                screenshot_b64 = screenshot_data
            
            if not screenshot_b64 or len(screenshot_b64) < 100:
                print(f"⚠️ Screenshot base64 too short ({len(screenshot_b64)} chars) — skipping save")
            else:
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                import re
                bet_key_safe = re.sub(r'[\\/*?":.<>|]', '_', data.get("key", "unknown")[:50])
                screenshot_filename = f"screenshot_{timestamp}_{bet_key_safe}.png"
                screenshot_path = os.path.join("screenshots", screenshot_filename)
                
                # Decode and save
                screenshot_bytes = base64.b64decode(screenshot_b64)
                if len(screenshot_bytes) == 0:
                    print(f"⚠️ Screenshot decoded to 0 bytes — skipping save")
                    screenshot_path = None # Ensure path is None if save failed
                else:
                    with open(screenshot_path, 'wb') as f:
                        f.write(screenshot_bytes)
                    print(f"📸 Screenshot saved ({len(screenshot_bytes)} bytes): {screenshot_path}")
        except Exception as e:
            print(f"⚠️ Screenshot save error: {e}")
            screenshot_path = None
    
    payload = {
        "type": data.get("type"),  # "feed", "slip", "slip_error"
        "key": data.get("key"),
        "bet_id": data.get("bet_id"),
        "bet_ref": data.get("bet_ref"),
        "slip_id": slip_id,
        "slip_url": data.get("slip_url"),
        "event": data.get("event"),
        "user": data.get("user"),
        "time": data.get("time"),
        "odds": data.get("odds"),
        "amount_raw": data.get("amount_raw"),
        "amount_value": float(data.get("amount_value") or 0),
        "currency": data.get("currency"),
        "detected_at": detected_at,
        "slip_fetched_at": data.get("slip_fetched_at"),
        "forwarded": data.get("forwarded"),
        "forwarded_at": data.get("forwarded_at"),
        "error": data.get("error"),  # For slip_error type
        "cookies": data.get("cookies"), # ✅ Catch Golden Cookies
        "screenshot_path": screenshot_path  # Store path for later use
    }

    # Allow SLIPS even if small amount (so tests work)
    if payload["amount_value"] < MIN_AMOUNT and payload.get("type") != "slip":
        return jsonify({"status": "ignored_small"}), 200

    # Deduplication & Enrichment Logic
    # We want to allow updates if the new payload has more "value" (like a URL/screenshot)
    bet_key = payload.get("key")
    if not bet_key:
        amount_raw_str = str(payload.get('amount_raw', '')).strip()
        bet_key = f"{payload.get('event', '')}|{payload.get('time', '')}|{amount_raw_str}"
        bet_key = bet_key[:240]
        payload["key"] = bet_key
    
    bet_type = payload.get("type", "unknown")
    dedup_key = f"{bet_key}|{bet_type}"
    
    # Check if we should ignore this as a "stale" duplicate or process it as an update
    current_time = time.time()
    is_update = False
    
    if dedup_key in recent_bets:
        last_seen = recent_bets[dedup_key]
        if current_time - last_seen["ts"] < DEDUP_WINDOW:
            # It's within the window. But is it an ENRICHMENT?
            # Enrichments have things like slip_url or screenshot_path that might have been missing
            has_new_info = (payload.get("slip_url") and not last_seen.get("has_url")) or \
                           (payload.get("screenshot_path") and not last_seen.get("has_photo"))
            
            if not has_new_info:
                return jsonify({"status": "duplicate", "key": dedup_key}), 200
            else:
                is_update = True
                print(f"🔄 Processing enrichment for {bet_key[:30]}...")
    
    # Update recent bets tracking with metadata about what we've seen
    recent_bets[dedup_key] = {
        "ts": current_time,
        "has_url": bool(payload.get("slip_url")),
        "has_photo": bool(payload.get("screenshot_path"))
    }
    
    # Clean old entries
    cutoff = current_time - DEDUP_WINDOW
    keys_to_remove = [k for k, v in recent_bets.items() if v["ts"] <= cutoff]
    for k in keys_to_remove:
        recent_bets.pop(k, None)

    # Create output payload with timestamp
    payload_out = {"timestamp": current_time, **payload}
    
    # Database Upsert (SQLite)
    import database
    database.upsert_bet(payload_out)
    
    # Send to Azure Event Hubs asynchronously (non-blocking)
    send_to_event_hubs_async(payload_out)
    
    # ═══════════════════════════════════════════════════════════════
    # TELEGRAM ALERT (Consolidated)
    # ═══════════════════════════════════════════════════════════════
    event_str = str(payload.get("event", "")).lower()
    is_multi = "multi" in event_str
    amount = payload.get("amount_value", 0)
    threshold = TG_ALERT_MIN["multi"] if is_multi else TG_ALERT_MIN["standard"]
    
    # ALERT LOGIC:
    if amount >= threshold:
        if payload.get("screenshot_path"):
            # We have a PHOTO. Send immediately.
            if amount >= VIP_THRESHOLD and VIP_CHAT_ID:
                print(f"🌟 Sending VIP Telegram Alert (PHOTO): {event_str[:20]}... ${amount}")
                send_telegram_alert(payload, photo_path=payload.get("screenshot_path"), target_chat_id=VIP_CHAT_ID, bot_token=VIP_BOT_TOKEN)
            else:
                print(f"📣 Sending Main Telegram Alert (PHOTO): {event_str[:20]}... ${amount}")
                send_telegram_alert(payload, photo_path=payload.get("screenshot_path"))
                
        elif payload.get("type") == "slip":
            # We have the SLIP info but NO photo yet.
            # The extension logs to DB before opening the popup. We'll wait 12s for the photo payload.
            def _delayed_slip_alert():
                time.sleep(12)
                conn = database.get_db_connection()
                c = conn.cursor()
                c.execute("SELECT screenshot_path FROM bets WHERE key = ?", (bet_key,))
                res = c.fetchone()
                conn.close()
                
                if res and res["screenshot_path"]:
                    print(f"🤫 Suppressed redundant text-only SLIP alert (Photo arrived in time!): {event_str[:20]}")
                else:
                    if amount >= VIP_THRESHOLD and VIP_CHAT_ID:
                        print(f"📤 SLIP fallback VIP alert (No Photo Arrived): {event_str[:20]}")
                        send_telegram_alert(payload, target_chat_id=VIP_CHAT_ID, bot_token=VIP_BOT_TOKEN)
                    else:
                        print(f"📤 SLIP fallback Main alert (No Photo Arrived): {event_str[:20]}")
                        send_telegram_alert(payload)
            
            threading.Thread(target=_delayed_slip_alert, daemon=True).start()
            
        elif payload.get("type") == "feed":
            # For 'feed' bets, wait 8 seconds to see if a 'slip' URL gets caught.
            def _delayed_feed_alert():
                time.sleep(8)
                conn = database.get_db_connection()
                c = conn.cursor()
                c.execute("SELECT slip_url, screenshot_path FROM bets WHERE key = ? AND type = 'slip'", (bet_key,))
                res = c.fetchone()
                conn.close()
                
                if not res:
                    if amount >= VIP_THRESHOLD and VIP_CHAT_ID:
                        print(f"📤 Feed fallback VIP alert (No SLIP seen): {event_str[:20]}")
                        send_telegram_alert(payload, target_chat_id=VIP_CHAT_ID, bot_token=VIP_BOT_TOKEN)
                    else:
                        print(f"📤 Feed fallback Main alert (No SLIP seen): {event_str[:20]}")
                        send_telegram_alert(payload)
                else:
                    print(f"🤫 Suppressed redundant FEED alert: {event_str[:20]}")
            
            threading.Thread(target=_delayed_feed_alert, daemon=True).start()
    else:
        # Debug logging for skipped alerts
        skip_reason = []
        if amount < threshold: skip_reason.append(f"Amount ${amount} < ${threshold}")
        # print(f"🔹 Skipped TG: {event_str[:20]}... ({', '.join(skip_reason)})")

    # Create response object
    response = jsonify({"status": "ok"})
    
    # Set mandatory ngrok header to bypass warning page (for free tier)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response, 200


@app.route("/", methods=["GET"])
def index():
    return "Receiver running (SQLite)", 200


@app.route("/query", methods=["GET"])
def query_database():
    """Query the database via HTTP - for when SSH is unavailable"""
    import database
    
    # Get query parameters
    sort_by = request.args.get('sort', 'timestamp')  # timestamp, odds, amount
    order = request.args.get('order', 'desc')  # asc, desc
    limit = min(int(request.args.get('limit', 50)), 100)  # max 100
    min_odds = request.args.get('min_odds', None)
    min_amount = request.args.get('min_amount', None)
    event_search = request.args.get('event', None)

    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        
        # Build query
        query = "SELECT event, amount_value, odds, datetime(timestamp, 'unixepoch') as time, slip_url FROM bets WHERE 1=1"
        params = []
        
        if min_odds:
            query += " AND odds >= ?"
            params.append(float(min_odds))
        if min_amount:
            query += " AND amount_value >= ?"
            params.append(float(min_amount))
        if event_search:
            query += " AND event LIKE ?"
            params.append(f"%{event_search}%")
        
        # Sort
        sort_col = {'odds': 'odds', 'amount': 'amount_value', 'timestamp': 'timestamp'}.get(sort_by, 'timestamp')
        query += f" ORDER BY {sort_col} {'DESC' if order == 'desc' else 'ASC'} LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Format as text for easy reading
        result = f"=== DATABASE QUERY RESULTS ({len(rows)} rows) ===\n"
        result += f"Sort: {sort_by} {order} | Limit: {limit}\n"
        if min_odds: result += f"Min odds: {min_odds}\n"
        if min_amount: result += f"Min amount: ${min_amount}\n"
        if event_search: result += f"Event filter: {event_search}\n"
        result += "=" * 60 + "\n\n"
        
        for row in rows:
            event, amount, odds, time, slip_url = row
            has_url = "✅" if slip_url else "❌"
            result += f"{has_url} {event[:50]:50} | ${amount:>12,.2f} | odds: {odds or 'N/A':>6} | {time}\n"
        
        return result, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route("/view", methods=["GET"])
def view_feed():
    """Live feed viewer - displays recent bets from SQLite"""
    import database
    
    # Get recent bets from DB
    bets = database.get_recent_bets(limit=100)
    
    # Get stats from DB
    stats = database.get_stats()
    
    # Calculate health metrics (reusing existing logic if possible, or simplified)
    # For now, let's just use the bets list for health metrics calculation
    # to keep it compatible with the existing `calculate_health_metrics` function
    # which expects a list of dicts.
    health_metrics = calculate_health_metrics(bets)
    
    # Pass stats to template
    feed_count = stats.get('feed_count', 0)
    slip_count = stats.get('slip_count', 0)
    total_value = stats.get('total_value', 0)
    
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bet Feed - Real Time</title>
    <meta http-equiv="refresh" content="5">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #0a0e27;
            color: #e0e0e0;
            padding: 20px;
            line-height: 1.6;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: #00d9ff;
            margin-bottom: 10px;
            font-size: 2em;
        }
        .stats {
            background: #151a3a;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }
        .filters {
            background: #151a3a;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #00d9ff;
        }
        .filters h2 {
            color: #00d9ff;
            font-size: 1.1em;
            margin-bottom: 12px;
        }
        .filter-row {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }
        .filter-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .filter-group label {
            color: #888;
            font-size: 0.9em;
            white-space: nowrap;
        }
        .filter-group input[type="number"],
        .filter-group input[type="text"] {
            background: #1a1f3f;
            border: 1px solid #252a4a;
            color: #e0e0e0;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 0.9em;
            width: 100px;
        }
        .filter-group input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        .filter-group select {
            background: #1a1f3f;
            border: 1px solid #252a4a;
            color: #e0e0e0;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 0.9em;
            cursor: pointer;
        }
        .filter-btn {
            background: #00d9ff;
            color: #0a0e27;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
            font-size: 0.9em;
        }
        .filter-btn:hover {
            background: #00b8d9;
        }
        .filter-btn.clear {
            background: #6b7280;
        }
        .filter-btn.clear:hover {
            background: #4b5563;
        }
        .health-stats {
            background: #1a1f3f;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #00d9ff;
        }
        .health-stats h2 {
            color: #00d9ff;
            font-size: 1.1em;
            margin-bottom: 10px;
        }
        .health-metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .health-metric {
            display: flex;
            flex-direction: column;
        }
        .health-metric-label {
            color: #888;
            font-size: 0.85em;
            margin-bottom: 4px;
        }
        .health-metric-value {
            color: #00d9ff;
            font-size: 1.1em;
            font-weight: bold;
        }
        .health-metric-value.good {
            color: #4ade80;
        }
        .health-metric-value.warning {
            color: #fbbf24;
        }
        .health-metric-value.error {
            color: #f87171;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 6px;
        }
        .status-indicator.active {
            background: #4ade80;
            box-shadow: 0 0 8px rgba(74, 222, 128, 0.6);
        }
        .status-indicator.inactive {
            background: #f87171;
        }
        .stat {
            display: flex;
            flex-direction: column;
        }
        .stat-label {
            color: #888;
            font-size: 0.9em;
        }
        .stat-value {
            color: #00d9ff;
            font-size: 1.5em;
            font-weight: bold;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: #151a3a;
            border-radius: 8px;
            overflow: hidden;
        }
        thead {
            background: #1a1f3f;
        }
        th {
            padding: 15px;
            text-align: left;
            color: #00d9ff;
            font-weight: 600;
            border-bottom: 2px solid #00d9ff;
        }
        td {
            padding: 14px 15px;
            border-bottom: 1px solid #252a4a;
        }
        tbody tr:nth-child(odd) {
            background: #151a3a;
        }
        tbody tr:nth-child(even) {
            background: #1a1f3f;
        }
        tr:hover {
            background: #1e2340 !important;
        }
        .amount {
            font-weight: bold;
            color: #4ade80;
        }
        .amount.high {
            color: #fbbf24;
        }
        .amount.very-high {
            color: #f87171;
        }
        .odds {
            color: #a78bfa;
        }
        .time-col {
            color: #94a3b8;
            font-size: 0.9em;
        }
        .event {
            max-width: 400px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .timestamp {
            color: #64748b;
            font-size: 0.85em;
        }
        .alert-badge {
            display: inline-block;
            background: #dc2626;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            margin-left: 10px;
            font-weight: bold;
        }
        .type-badge {
            display: inline-block;
            background: #6366f1;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.7em;
            margin-left: 8px;
            font-weight: bold;
        }
        .slip-link {
            color: #60a5fa;
            text-decoration: underline;
            font-size: 0.85em;
        }
        .slip-link:hover {
            color: #93c5fd;
        }
        .auto-refresh {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #00d9ff;
            color: #0a0e27;
            padding: 10px 20px;
            border-radius: 20px;
            border: none;
            cursor: pointer;
            font-weight: bold;
            box-shadow: 0 4px 6px rgba(0, 217, 255, 0.3);
        }
        .auto-refresh:hover {
            background: #00b8d9;
        }
        .auto-refresh.active {
            background: #f87171;
            color: white;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎲 Real-Time Bet Feed</h1>
        
        <div class="stats">
            <div class="stat">
                <span class="stat-label">Total Bets</span>
                <span class="stat-value">{{ bets|length }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Feed Entries</span>
                <span class="stat-value">{{ feed_count }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Slip URLs</span>
                <span class="stat-value">{{ slip_count }}</span>
            </div>
            <div class="stat">
                <span class="stat-label">Total Value</span>
                <span class="stat-value">${{ "%.2f"|format(total_value) }}</span>
            </div>
        </div>
        
        <div class="filters">
            <h2>🔍 Filters</h2>
            <div class="filter-row">
                <div class="filter-group">
                    <input type="checkbox" id="filter-url-only" onchange="applyFilters()">
                    <label for="filter-url-only">URL Only (Big Rollers ≥$14,750)</label>
                </div>
                <div class="filter-group">
                    <label for="filter-min-odds">Min Odds:</label>
                    <input type="number" id="filter-min-odds" step="0.01" min="0" placeholder="1.0" onchange="applyFilters()">
                </div>
                <div class="filter-group">
                    <label for="filter-min-amount">Min Amount:</label>
                    <input type="number" id="filter-min-amount" step="100" min="0" placeholder="0" onchange="applyFilters()">
                </div>
                <div class="filter-group">
                    <label for="filter-type">Type:</label>
                    <select id="filter-type" onchange="applyFilters()">
                        <option value="">All</option>
                        <option value="feed">Feed</option>
                        <option value="slip">Slip</option>
                        <option value="slip_error">Error</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label for="filter-search">Search Event:</label>
                    <input type="text" id="filter-search" placeholder="Event name..." onkeyup="applyFilters()">
                </div>
                <button class="filter-btn clear" onclick="clearFilters()">Clear All</button>
                <span id="filter-count" style="color: #888; font-size: 0.9em; margin-left: auto;"></span>
            </div>
        </div>
        
        <div class="health-stats">
            <h2>📊 Health Status</h2>
            <div class="health-metrics">
                <div class="health-metric">
                    <span class="health-metric-label">Feed Status</span>
                    <span class="health-metric-value {{ health_metrics.status_class }}">
                        <span class="status-indicator {{ health_metrics.status_class }}"></span>
                        {{ health_metrics.feed_status }}
                    </span>
                </div>
                <div class="health-metric">
                    <span class="health-metric-label">Last Bet</span>
                    <span class="health-metric-value">{{ health_metrics.last_bet_time }}</span>
                </div>
                <div class="health-metric">
                    <span class="health-metric-label">Avg Time Between Bets</span>
                    <span class="health-metric-value">{{ health_metrics.avg_bet_interval }}</span>
                </div>
                <div class="health-metric">
                    <span class="health-metric-label">Highest Bet (Last 10 min)</span>
                    <span class="health-metric-value">{{ health_metrics.highest_recent }}</span>
                </div>
                <div class="health-metric">
                    <span class="health-metric-label">Bets in Last 10 min</span>
                    <span class="health-metric-value">{{ health_metrics.recent_count }}</span>
                </div>
                <div class="health-metric">
                    <span class="health-metric-label">URL Capture Rate</span>
                    <span class="health-metric-value {{ health_metrics.url_rate_class }}">{{ health_metrics.url_capture_rate }}</span>
                </div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Timestamp</th>
                    <th>Amount</th>
                    <th>Odds</th>
                    <th>Time</th>
                    <th>Event</th>
                    <th>URL</th>
                </tr>
            </thead>
            <tbody>
                {% if bets %}
                    {% for bet in bets %}
                    <tr data-bet-type="{{ bet.type|default('') }}" data-bet-odds="{{ bet.odds|default('0') }}" data-bet-amount="{{ bet.amount_value|default(0) }}" data-bet-url="{{ 'yes' if bet.slip_url else 'no' }}" data-bet-event="{{ (bet.event or 'N/A')|lower }}">
                        <td>{{ loop.index }}</td>
                        <td class="timestamp">{{ bet.timestamp_formatted }}</td>
                        <td class="amount {% if bet.amount_value and bet.amount_value >= 50000 %}very-high{% elif bet.amount_value and bet.amount_value >= 25000 %}high{% endif %}">
                            {% if bet.amount_raw %}{{ bet.amount_raw }}{% else %}${{ "%.2f"|format(bet.amount_value|default(0)) }}{% endif %}
                            {% if bet.amount_value and bet.amount_value >= 10000 %}<span class="alert-badge">HIGH</span>{% endif %}
                        </td>
                        <td class="odds">{{ bet.odds|default('N/A') }}</td>
                        <td class="time-col">{{ bet.time|default('N/A') }}</td>
                        <td class="event">
                            {% set event_text = bet.event or 'N/A' %}{{ event_text[:60] }}{% if event_text|length > 60 %}...{% endif %}
                            {% if bet.type == 'slip' %}
                                <span class="type-badge">📋 SLIP</span>
                            {% elif bet.type == 'slip_error' %}
                                <span class="type-badge" style="background:#ef4444">❌ ERROR</span>
                            {% elif bet.type == 'feed' %}
                                <span class="type-badge" style="background:#10b981">📥 FEED</span>
                            {% endif %}
                            {% if bet.slip_url %}
                                <br><a href="{{ bet.slip_url }}" target="_blank" class="slip-link">📎 View Slip</a>
                            {% elif bet.amount_value and bet.amount_value >= 14750 and bet.type == 'feed' %}
                                <br><span style="color: #60a5fa; font-size: 0.85em;">⏳ Waiting for URL (≥ $14,750)</span>
                            {% endif %}
                        </td>
                        <td>
                            {% if bet.slip_url %}
                                <a href="{{ bet.slip_url }}" target="_blank" class="slip-link">{{ bet.slip_url[:50] }}...</a>
                            {% else %}
                                -
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                {% else %}
                    <tr>
                        <td colspan="7" style="text-align:center; padding:40px; color:#666;">No bets received yet. Waiting for data...</td>
                    </tr>
                {% endif %}
            </tbody>
        </table>
        
        <button class="auto-refresh" onclick="location.reload()">🔄 Refresh</button>
    </div>
    
    <script>
        // Auto-refresh every 5 seconds
        let autoRefresh = false;
        const btn = document.querySelector('.auto-refresh');
        
        btn.addEventListener('click', function() {
            autoRefresh = !autoRefresh;
            if (autoRefresh) {
                this.classList.add('active');
                this.textContent = '⏸️ Stop Auto-Refresh';
                this.interval = setInterval(() => location.reload(), 5000);
            } else {
                this.classList.remove('active');
                this.textContent = '🔄 Auto-Refresh';
                clearInterval(this.interval);
            }
        });
        
        // Filter functions with localStorage persistence
        function saveFilters() {
            const filters = {
                urlOnly: document.getElementById('filter-url-only').checked,
                minOdds: document.getElementById('filter-min-odds').value,
                minAmount: document.getElementById('filter-min-amount').value,
                filterType: document.getElementById('filter-type').value,
                searchTerm: document.getElementById('filter-search').value
            };
            localStorage.setItem('betFeedFilters', JSON.stringify(filters));
        }
        
        function loadFilters() {
            const saved = localStorage.getItem('betFeedFilters');
            if (saved) {
                try {
                    const filters = JSON.parse(saved);
                    document.getElementById('filter-url-only').checked = filters.urlOnly || false;
                    document.getElementById('filter-min-odds').value = filters.minOdds || '';
                    document.getElementById('filter-min-amount').value = filters.minAmount || '';
                    document.getElementById('filter-type').value = filters.filterType || '';
                    document.getElementById('filter-search').value = filters.searchTerm || '';
                } catch (e) {
                    console.error('Error loading filters:', e);
                }
            }
        }
        
        function applyFilters() {
            const rows = document.querySelectorAll('tbody tr');
            let visibleCount = 0;
            
            // Get filter values
            const urlOnly = document.getElementById('filter-url-only').checked;
            const minOdds = parseFloat(document.getElementById('filter-min-odds').value) || 0;
            const minAmount = parseFloat(document.getElementById('filter-min-amount').value) || 0;
            const filterType = document.getElementById('filter-type').value.toLowerCase();
            const searchTerm = document.getElementById('filter-search').value.toLowerCase().trim();
            
            // Save filters to localStorage
            saveFilters();
            
            rows.forEach(row => {
                let show = true;
                
                // URL only filter
                if (urlOnly && row.dataset.betUrl !== 'yes') {
                    show = false;
                }
                
                // Min odds filter
                if (show && minOdds > 0) {
                    const odds = parseFloat(row.dataset.betOdds) || 0;
                    if (odds === 0 || odds < minOdds) {
                        show = false;
                    }
                }
                
                // Min amount filter
                if (show && minAmount > 0) {
                    const amount = parseFloat(row.dataset.betAmount) || 0;
                    if (amount < minAmount) {
                        show = false;
                    }
                }
                
                // Type filter
                if (show && filterType) {
                    if (row.dataset.betType !== filterType) {
                        show = false;
                    }
                }
                
                // Search filter
                if (show && searchTerm) {
                    const event = row.dataset.betEvent || '';
                    if (!event.includes(searchTerm)) {
                        show = false;
                    }
                }
                
                // Show/hide row
                if (show) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });
            
            // Update count
            const countEl = document.getElementById('filter-count');
            if (urlOnly || minOdds > 0 || minAmount > 0 || filterType || searchTerm) {
                countEl.textContent = `Showing ${visibleCount} of ${rows.length} bets`;
            } else {
                countEl.textContent = '';
            }
        }
        
        function clearFilters() {
            document.getElementById('filter-url-only').checked = false;
            document.getElementById('filter-min-odds').value = '';
            document.getElementById('filter-min-amount').value = '';
            document.getElementById('filter-type').value = '';
            document.getElementById('filter-search').value = '';
            localStorage.removeItem('betFeedFilters');
            applyFilters();
        }
        
        // Load and apply filters on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadFilters();
            applyFilters();
        });
        
        // Re-apply filters after page refresh (for meta refresh)
        window.addEventListener('load', function() {
            loadFilters();
            applyFilters();
        });
    </script>
</body>
</html>
    """
    
    feed_count = sum(1 for b in bets if b.get("type") == "feed")
    slip_count = sum(1 for b in bets if b.get("type") == "slip" and b.get("slip_url"))
    total_value = sum(b.get("amount_value", 0) for b in bets)
    
    return render_template_string(html_template, bets=bets, feed_count=feed_count, slip_count=slip_count, total_value=total_value, health_metrics=health_metrics)


def calculate_health_metrics(bets):
    """Calculate health metrics for the feed"""
    from datetime import datetime, timedelta
    
    if not bets:
        return {
            'feed_status': 'No Data',
            'status_class': 'error',
            'last_bet_time': 'N/A',
            'avg_bet_interval': 'N/A',
            'highest_recent': 'N/A',
            'recent_count': 0,
            'url_capture_rate': 'N/A',
            'url_rate_class': 'error'
        }
    
    now = datetime.now()
    ten_min_ago = now - timedelta(minutes=10)
    
    # Get timestamps from bets
    timestamps = []
    recent_bets = []
    slip_attempts = 0
    slip_successes = 0
    
    for bet in bets:
        # Get timestamp
        ts = None
        if bet.get('timestamp'):
            try:
                ts = datetime.fromtimestamp(bet['timestamp'])
            except:
                pass
        elif bet.get('detected_at'):
            try:
                ts = datetime.fromisoformat(bet['detected_at'].replace('Z', '+00:00'))
                ts = ts.replace(tzinfo=None)
            except:
                pass
        
        if ts:
            timestamps.append(ts)
            if ts >= ten_min_ago:
                recent_bets.append(bet)
                # Count slip attempts (bets >= 14750)
                if bet.get('amount_value', 0) >= 14750:
                    slip_attempts += 1
                    if bet.get('type') == 'slip' and bet.get('slip_url'):
                        slip_successes += 1
    
    # Calculate metrics
    if not timestamps:
        return {
            'feed_status': 'No Timestamps',
            'status_class': 'error',
            'last_bet_time': 'N/A',
            'avg_bet_interval': 'N/A',
            'highest_recent': 'N/A',
            'recent_count': 0,
            'url_capture_rate': 'N/A',
            'url_rate_class': 'error'
        }
    
    # Feed status based on last bet
    last_bet = timestamps[0]  # Already sorted newest first
    seconds_since_last = (now - last_bet).total_seconds()
    
    if seconds_since_last < 60:
        feed_status = 'Active'
        status_class = 'good'
    elif seconds_since_last < 300:  # 5 min
        feed_status = 'Recent'
        status_class = 'warning'
    else:
        feed_status = 'Stale'
        status_class = 'error'
    
    # Last bet time
    if seconds_since_last < 60:
        last_bet_time = f"{int(seconds_since_last)}s ago"
    elif seconds_since_last < 3600:
        last_bet_time = f"{int(seconds_since_last / 60)}m ago"
    else:
        last_bet_time = f"{int(seconds_since_last / 3600)}h ago"
    
    # Average time between bets (last 10 bets)
    if len(timestamps) >= 2:
        intervals = []
        for i in range(min(10, len(timestamps) - 1)):
            interval = (timestamps[i] - timestamps[i + 1]).total_seconds()
            intervals.append(interval)
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            if avg_interval < 60:
                avg_bet_interval = f"{avg_interval:.1f}s"
            else:
                avg_bet_interval = f"{avg_interval / 60:.1f}m"
        else:
            avg_bet_interval = 'N/A'
    else:
        avg_bet_interval = 'N/A'
    
    # Highest bet in last 10 minutes
    if recent_bets:
        highest = max(recent_bets, key=lambda x: x.get('amount_value', 0))
        highest_val = highest.get('amount_value', 0)
        highest_raw = highest.get('amount_raw', f"${highest_val:,.2f}")
        highest_recent = highest_raw
    else:
        highest_recent = 'None'
    
    # URL capture rate
    if slip_attempts > 0:
        url_rate = (slip_successes / slip_attempts) * 100
        url_capture_rate = f"{url_rate:.0f}% ({slip_successes}/{slip_attempts})"
        if url_rate >= 80:
            url_rate_class = 'good'
        elif url_rate >= 50:
            url_rate_class = 'warning'
        else:
            url_rate_class = 'error'
    else:
        url_capture_rate = 'No attempts'
        url_rate_class = 'error'
    
    return {
        'feed_status': feed_status,
        'status_class': status_class,
        'last_bet_time': last_bet_time,
        'avg_bet_interval': avg_bet_interval,
        'highest_recent': highest_recent,
        'recent_count': len(recent_bets),
        'url_capture_rate': url_capture_rate,
        'url_rate_class': url_rate_class
    }


if __name__ == "__main__":
    # Running on HTTP (ngrok handles HTTPS)
    print("=" * 60)
    print("Receiver running on http://127.0.0.1:5001")
    print("=" * 60)
    print("📊 Live feed viewer: http://127.0.0.1:5001/view")
    print("   (Also accessible via ngrok: YOUR_NGROK_URL/view)")
    print("=" * 60)
    print("🚀 STARTING RECEIVER ON 0.0.0.0 (PUBLIC ACCESS ENABLED)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5001, debug=True)

