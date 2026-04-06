import sqlite3
import datetime

conn = sqlite3.connect('bets.db')
c = conn.cursor()
try:
    c.execute("SELECT timestamp, event, amount_raw, type FROM bets ORDER BY id DESC LIMIT 5")
    rows = c.fetchall()
    print("--- LAST 5 BETS IN LOCAL DB ---")
    for r in rows:
        ts = datetime.datetime.fromtimestamp(r[0]) if r[0] else "N/A"
        print(f"[{ts}] {r[1]} ({r[2]}) - {r[3]}")
except Exception as e:
    print(e)
finally:
    conn.close()
