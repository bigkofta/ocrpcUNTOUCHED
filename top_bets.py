import sqlite3
import datetime

conn = sqlite3.connect('/root/highroller/bets.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get bets from last 24 hours ordered by amount
c.execute("""
    SELECT event, amount_value, datetime(timestamp, 'unixepoch') as time, 
           slip_url IS NOT NULL as has_url
    FROM bets 
    WHERE timestamp > strftime('%s', 'now', '-24 hours')
    ORDER BY amount_value DESC 
    LIMIT 30
""")
rows = c.fetchall()

print("=" * 70)
print("TOP BETS - LAST 24 HOURS")
print("=" * 70)
print(f"{'Amount':>15} | {'Event':<40} | Has URL")
print("-" * 70)

for r in rows:
    event = r['event'][:38] if r['event'] else 'N/A'
    amount = r['amount_value'] or 0
    has_url = "✅" if r['has_url'] else "❌"
    print(f"${amount:>13,.0f} | {event:<40} | {has_url}")

print("-" * 70)
print(f"Total bets in last 24h: {len(rows)}")
conn.close()
