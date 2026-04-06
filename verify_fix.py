import sqlite3
import datetime

conn = sqlite3.connect('/root/highroller/bets.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 70)
print("DATA INTEGRITY CHECK")
print("=" * 70)

# Check 1: Duplicate URLs (same URL for different events)
print("\n1. DUPLICATE URLs (same URL, different events):")
c.execute("""
    SELECT slip_url, GROUP_CONCAT(DISTINCT event) as events, COUNT(*) as cnt
    FROM bets 
    WHERE slip_url IS NOT NULL AND slip_url != ''
    GROUP BY slip_url
    HAVING COUNT(DISTINCT event) > 1
    ORDER BY cnt DESC
    LIMIT 10
""")
dupes = c.fetchall()
if dupes:
    for r in dupes:
        print(f"  URL: ...{r['slip_url'][-40:]}")
        print(f"  Events: {r['events'][:80]}...")
        print(f"  Count: {r['cnt']}")
        print()
else:
    print("  ✅ No duplicate URLs with different events found!")

# Check 2: Recent captures (last 30 min)
print("\n2. RECENT CAPTURES (last 30 min):")
c.execute("""
    SELECT event, amount_value, slip_url IS NOT NULL as has_url,
           datetime(timestamp, 'unixepoch') as time
    FROM bets 
    WHERE timestamp > strftime('%s', 'now', '-30 minutes')
    ORDER BY timestamp DESC
    LIMIT 15
""")
recent = c.fetchall()
for r in recent:
    url_icon = "✅" if r['has_url'] else "❌"
    print(f"  {url_icon} ${r['amount_value']:,.0f} | {r['event'][:40]} | {r['time']}")

print("\n3. URL DISTRIBUTION (last hour):")
c.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT slip_url) as unique_urls,
        COUNT(slip_url) as with_url
    FROM bets 
    WHERE timestamp > strftime('%s', 'now', '-1 hour')
""")
stats = c.fetchone()
print(f"  Total bets: {stats['total']}")
print(f"  With URL: {stats['with_url']}")
print(f"  Unique URLs: {stats['unique_urls']}")
if stats['with_url'] > 0:
    dupe_rate = (stats['with_url'] - stats['unique_urls']) / stats['with_url'] * 100
    print(f"  Duplicate rate: {dupe_rate:.1f}%")

print("\n" + "=" * 70)
conn.close()
