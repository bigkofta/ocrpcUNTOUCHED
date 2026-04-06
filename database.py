import sqlite3
import json
import time
import os
from datetime import datetime

DB_FILE = "bets.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with the bets table."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create bets table
    # We use a composite primary key or a unique constraint to prevent duplicates
    # The 'key' field from the browser script + 'type' is our unique identifier logic
    c.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            type TEXT,
            event TEXT,
            user TEXT,
            time_str TEXT,
            odds TEXT,
            amount_raw TEXT,
            amount_value REAL,
            currency TEXT,
            detected_at TEXT,
            slip_url TEXT,
            slip_id TEXT,
            iid TEXT,
            bet_id TEXT,
            bet_ref TEXT,
            slip_fetched_at TEXT,
            forwarded BOOLEAN,
            forwarded_at TEXT,
            error TEXT,
            timestamp REAL,
            cookies TEXT, -- ✅ New column for Golden Cookie
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Simple migration: try to add the column if it doesn't exist
    try:
        c.execute("ALTER TABLE bets ADD COLUMN cookies TEXT")
    except sqlite3.OperationalError:
        pass # Column likely exists
    
    # Create index for faster lookups
    c.execute('CREATE INDEX IF NOT EXISTS idx_key_type ON bets (key, type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON bets (timestamp)')
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DB_FILE}")

def insert_bet(bet_data):
    """
    Insert a bet into the database.
    Returns True if inserted, False if duplicate (based on key+type logic).
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # Extract fields with defaults
    key = bet_data.get('key')
    bet_type = bet_data.get('type')
    timestamp = bet_data.get('timestamp', time.time())
    
    # Serialize cookies if present
    cookies_json = None
    if bet_data.get('cookies'):
        try:
            cookies_json = json.dumps(bet_data.get('cookies'))
        except:
            cookies_json = None

    try:
        with open("debug_db.txt", "a", encoding="utf-8") as f:
             f.write(f"DB: Inserting {key}...\n")
        # print statement removed to avoid console encoding issues
        c.execute('''
            INSERT INTO bets (
                key, type, event, user, time_str, odds, amount_raw, amount_value,
                currency, detected_at, slip_url, slip_id, iid, bet_id, bet_ref,
                slip_fetched_at, forwarded, forwarded_at, error, timestamp, cookies
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            key,
            bet_type,
            bet_data.get('event'),
            bet_data.get('user'),
            bet_data.get('time'),
            bet_data.get('odds'),
            bet_data.get('amount_raw'),
            bet_data.get('amount_value'),
            bet_data.get('currency'),
            bet_data.get('detected_at'),
            bet_data.get('slip_url'),
            bet_data.get('slip_id'),
            bet_data.get('iid'),
            bet_data.get('bet_id'),
            bet_data.get('bet_ref'),
            bet_data.get('slip_fetched_at'),
            bet_data.get('forwarded'),
            bet_data.get('forwarded_at'),
            bet_data.get('error'),
            timestamp,
            cookies_json # ✅ Insert cookies
        ))
        conn.commit()
        with open("debug_db.txt", "a", encoding="utf-8") as f:
             f.write(f"DB: Committed {key}!\n")
        return True
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    finally:
        conn.close()

def get_recent_bets(limit=100):
    """Get recent bets for the viewer."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT * FROM bets ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    
    # Convert to list of dicts
    bets = []
    for row in rows:
        bet = dict(row)
        # Map time_str back to time for compatibility
        bet['time'] = bet['time_str']
        
        # Format timestamp
        ts = bet['timestamp']
        if ts:
            dt = datetime.fromtimestamp(ts)
            bet['timestamp_formatted'] = dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            bet['timestamp_formatted'] = 'N/A'
            
        bets.append(bet)
        
    return bets

def get_stats():
    """Get statistics for the dashboard."""
    conn = get_db_connection()
    c = conn.cursor()
    
    stats = {}
    
    # Total count
    c.execute('SELECT COUNT(*) FROM bets')
    stats['total_count'] = c.fetchone()[0]
    
    # Feed count
    c.execute('SELECT COUNT(*) FROM bets WHERE type = "feed"')
    stats['feed_count'] = c.fetchone()[0]
    
    # Slip count (successful)
    c.execute('SELECT COUNT(*) FROM bets WHERE type = "slip" AND slip_url IS NOT NULL')
    stats['slip_count'] = c.fetchone()[0]
    
    # Total value
    c.execute('SELECT SUM(amount_value) FROM bets')
    val = c.fetchone()[0]
    stats['total_value'] = val if val else 0
    
    conn.close()
    return stats
