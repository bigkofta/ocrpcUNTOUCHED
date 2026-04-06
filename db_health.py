import sqlite3
import datetime

conn = sqlite3.connect('bets.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 60)
print("DATABASE HEALTH CHECK")
print("=" * 60)

# Total count
c.execute("SELECT COUNT(*) as total FROM bets")
total = c.fetchone()['total']
print(f"\n📊 Total bets in DB: {total}")

# With slip URL
c.execute("SELECT COUNT(*) as count FROM bets WHERE slip_url IS NOT NULL AND slip_url != ''")
with_url = c.fetchone()['count']
print(f"🔗 Bets with slip URL: {with_url} ({100*with_url/max(total,1):.1f}%)")

# Total value
c.execute("SELECT SUM(amount_value) as total FROM bets")
total_value = c.fetchone()['total'] or 0
print(f"💰 Total bet value: ${total_value:,.2f}")

# Last 5 bets
print("\n📋 LAST 5 BETS:")
c.execute("SELECT timestamp, event, amount_value, slip_url, type FROM bets ORDER BY id DESC LIMIT 5")
for r in c.fetchall():
    ts = datetime.datetime.fromtimestamp(r['timestamp']) if r['timestamp'] else "N/A"
    event = r['event'][:35] if r['event'] else 'N/A'
    amount = r['amount_value'] or 0
    has_url = "✅" if r['slip_url'] else "❌"
    print(f"  [{ts}] ${amount:,.0f} {has_url} {event}")

# Last bet with URL
c.execute("SELECT timestamp, event, slip_url FROM bets WHERE slip_url IS NOT NULL ORDER BY id DESC LIMIT 1")
last_with_url = c.fetchone()
if last_with_url:
    ts = datetime.datetime.fromtimestamp(last_with_url['timestamp'])
    print(f"\n🔗 Last bet with URL: {ts}")
    print(f"   {last_with_url['slip_url']}")
else:
    print("\n⚠️ No bets with slip URL found")

conn.close()
print("\n" + "=" * 60)
