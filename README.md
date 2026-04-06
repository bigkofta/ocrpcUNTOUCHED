# HighRoller OCR

Real-time bet detection system for Stake.com with Telegram alerts.

## Quick Start

```powershell
# Start all services (receiver + bot + ngrok)
.\launch_highroller.bat
```

## Environment Setup

Copy `.env.example` to `.env` and fill in your tokens:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_VIP_TOKEN=your_vip_bot_token  # Optional
TELEGRAM_VIP_CHAT_ID=your_vip_chat_id  # Optional
NGROK_AUTHTOKEN=your_ngrok_token
```

## Architecture

```
[Chrome Extension] → [Ngrok] → [Receiver] → [SQLite] → [Telegram Bot] → [Your Phone]
```

## Key Files

| File | Purpose |
|------|---------|
| `receiver.py` | Flask API, saves bets, sends photos to Telegram |
| `telegram_bot.py` | Polling bot for additional alerts |
| `run_forever.ps1` | Auto-restart supervisor |
| `chrome_extension/` | Browser extension for bet detection |
| `.env` | **Secrets** (never commit!) |

## Thresholds

| Type | Photo Alert | DB Log |
|------|-------------|--------|
| Multi | ≥ $1,000 | ≥ $500 |
| Standard | ≥ $14,750 | ≥ $5,000 |

## Dashboard

- **Local:** http://localhost:5001/view
- **Public:** https://vengeful-mervin-uncoveting.ngrok-free.dev/view

## Troubleshooting

1. **No alerts?** → Run `.\launch_highroller.bat`
2. **Extension not working?** → Reload in `brave://extensions`
3. **Check logs:** `Get-Content receiver.log -Tail 50`

## Security

- All tokens loaded from `.env` (not hardcoded)
- `.env` is in `.gitignore`
- Never commit secrets
