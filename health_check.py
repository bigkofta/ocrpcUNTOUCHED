import sqlite3
import datetime

conn = sqlite3.connect('/root/highroller/bets.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

now = datetime.datetime.utcnow()
print("=" * 70)
print(f"HEALTH SNAPSHOT - {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print("=" * 70)

# 1. Total bets ever
c.execute("SELECT COUNT(*) as cnt FROM bets")
total = c.fetchone()['cnt']
print(f"\n📊 TOTAL BETS IN DB: {total}")

# 2. Bets in last 10 min
c.execute("""
    SELECT COUNT(*) as cnt FROM bets 
    WHERE timestamp > strftime('%s', 'now', '-10 minutes')
""")
recent_10 = c.fetchone()['cnt']
print(f"📥 BETS IN LAST 10 MIN: {recent_10}")

# 3. Last bet timestamp
c.execute("""
    SELECT datetime(MAX(timestamp), 'unixepoch') as last_time 
    FROM bets
""")
last = c.fetchone()['last_time']
print(f"⏰ LAST BET RECEIVED: {last} UTC")

# 4. High-value bets in last 10 min
c.execute("""
    SELECT COUNT(*) as cnt FROM bets 
    WHERE timestamp > strftime('%s', 'now', '-10 minutes')
    AND amount_value >= 10000
""")
high_value = c.fetchone()['cnt']
print(f"💰 HIGH-VALUE (>$10k) IN LAST 10 MIN: {high_value}")

# 5. URL capture rate in last 10 min
c.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(slip_url) as with_url,
        COUNT(DISTINCT slip_url) as unique_urls
    FROM bets 
    WHERE timestamp > strftime('%s', 'now', '-10 minutes')
""")
urls = c.fetchone()
if urls['total'] > 0:
    capture_rate = (urls['with_url'] / urls['total']) * 100
    print(f"🔗 URL CAPTURE RATE (last 10 min): {capture_rate:.1f}%")
    print(f"   Total: {urls['total']}, With URL: {urls['with_url']}, Unique: {urls['unique_urls']}")
else:
    print("🔗 URL CAPTURE RATE (last 10 min): No bets to measure")

# 6. Check for duplicate URLs in last 10 min
c.execute("""
    SELECT slip_url, COUNT(*) as cnt, GROUP_CONCAT(DISTINCT event) as events
    FROM bets 
    WHERE timestamp > strftime('%s', 'now', '-10 minutes')
    AND slip_url IS NOT NULL
    GROUP BY slip_url
    HAVING COUNT(DISTINCT event) > 1
""")
dupes = c.fetchall()
if dupes:
    print(f"\n⚠️ DUPLICATE URLs DETECTED (same URL, different events):")
    for d in dupes[:5]:
        print(f"   - {d['events'][:50]}... (count: {d['cnt']})")
else:
    print("\n✅ NO DUPLICATE URLs IN LAST 10 MIN!")

# 7. Latest 5 high-value bets
print("\n📋 LATEST HIGH-VALUE BETS:")
c.execute("""
    SELECT event, amount_value, slip_url IS NOT NULL as has_url,
           datetime(timestamp, 'unixepoch') as time
    FROM bets 
    WHERE amount_value >= 10000
    ORDER BY timestamp DESC
    LIMIT 5
""")
for r in c.fetchall():
    icon = "✅" if r['has_url'] else "❌"
    print(f"   {icon} ${r['amount_value']:,.0f} | {r['event'][:35]} | {r['time']}")

print("\n" + "=" * 70)
print(f"[Snapshot taken at {now.strftime('%Y-%m-%d %H:%M:%S')} UTC]")
print("Run again later to compare!")
print("=" * 70)

conn.close()
