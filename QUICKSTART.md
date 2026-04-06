# HighRoller OCR - Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Prerequisites
- Chrome browser
- VPS running (Hostinger at `31.97.215.169`)
- Ngrok running on VPS

---

## 1. Load Chrome Extension

```
1. Open Chrome → chrome://extensions
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select: c:\Users\poo\highrollerocr-1\chrome_extension
5. Extension icon should appear
```

---

## 2. Verify VPS is Running

```powershell
# SSH into VPS
ssh root@31.97.215.169
# Password in .env file

# Check containers
docker ps

# Should see:
# - highroller_receiver (port 5001)
# - highroller_bot
```

---

## 3. Verify Ngrok Tunnel

Open in browser: https://vengeful-mervin-uncoveting.ngrok-free.dev/view

- If it loads → ✅ Ngrok working
- If not → Need to restart ngrok on VPS

---

## 4. Test Detection

1. Go to stake.com → Sports → High Rollers
2. Open browser console (F12)
3. Look for: `🚀 HighRoller Content Script Injected!`
4. Wait for bets to appear → Should see log entries

---

## 5. Force Full Scan (Optional)

```javascript
// Run in console to clear cache and re-scan all visible bets
localStorage.removeItem('hr_seen_v4');
location.reload();
```

---

## Common Issues

| Issue | Fix |
|-------|-----|
| No bets detected | Clear localStorage and reload |
| No slip URLs | Button click fix needed - check `.cursorrules` |
| Dashboard won't load | Restart ngrok on VPS |
| Not saving to DB | Check Docker containers running |

---

## Important Files

| File | Location |
|------|----------|
| Extension | `chrome_extension/` |
| VPS Receiver | `/root/highroller/receiver.py` |
| Database (LIVE) | VPS: `/root/highroller/bets.db` |
| Secrets | `.env` |
| Full docs | `.cursorrules` |
