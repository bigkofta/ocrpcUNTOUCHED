import sqlite3

conn = sqlite3.connect('/root/highroller/bets.db')
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT event, amount_value, slip_url 
    FROM bets 
    WHERE slip_url IS NOT NULL AND slip_url != '' 
    ORDER BY amount_value DESC 
    LIMIT 15
""").fetchall()

for r in rows:
    print(f"${r['amount_value']:,.0f} | {r['event'][:35]}")
    print(f"   {r['slip_url']}")
    print()
conn.close()
