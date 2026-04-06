# HighRoller V3.5 - Developer Guide 🎲

**Current Branch:** `stable-enhanced-v3.5`

## 🐳 Docker "Pick up and Play"
The system is now fully containerized for easy deployment on any machine (VPS, Linux, Mac, Windows).
- **Run with Docker:** `docker compose up -d`
- **Requires:** `.env` file with your Telegram/Ngrok credentials.

## 🗺️ System Map
This repository contains a **Hybrid OCR Betting System** that captures live bets from Stake.com via a Chrome Extension and processes them locally on Windows or via Docker.

### 🌐 LIVE DATA DASHBOARD
**👉 [https://vengeful-mervin-uncoveting.ngrok-free.dev/view](https://vengeful-mervin-uncoveting.ngrok-free.dev/view)**
*(This connects to the live generic VPS database, not your local empty one)*

### 📂 Folder Structure
*   **Root (`/`)**: Core runtime files.
    *   `receiver.py`: Flask backend (Port 5001). Receives bets, deduplicates, saves to DB.
    *   `telegram_bot.py`: Polling logic & Radio broadcaster.
    *   `radio_server.py`: Live audio streaming server (Port 5002).
    *   `run_forever.ps1`: **Master Supervisor**. Auto-restarts everything natively.
    *   `Dockerfile` & `docker-compose.yml`: Containerization logic.
    *   `bets.db`: The SQLite database (Single Source of Truth).
*   **`chrome_extension/`**: The browser extension source code.
    *   `content.js`: Main logic (Scraping, Filtering, Sending to Ngrok HTTPS).
    *   `manifest.json`: Extension config.
*   **`config/`**: Configuration files (`.env`, `setup_*.sh`).
*   **`logs/`**: Log files (`receiver.log`, `bot.log`). *Note: Active logs may spawn in root during runtime.*
*   **`archive/`**: Old/Reference code.

---

## 🚀 How It Works (The Flow)

1.  **Capture (Browser):**
    *   User installs **HighRoller Direct-Fire** extension.
    *   `content.js` scrapes the "High Rollers" table on Stake.com.
    *   **Logic Thresholds:**
        *   **Multi Bets:** Capture if ≥ **$1,000**.
        *   **Standard Bets:** Capture if ≥ **$14,750**.
    *   **Capture Strategy ("Double Tap"):**
        1.  **Direct Link:** Checks hidden direct links.
        2.  **Row Click (Silent):** Simulates clicking the row (native behavior).
        3.  **Button Backup:** If row click fails, clicks "Bet Preview" explicitly.
        4.  **Side Drawer:** Checks `[data-testid="betslip-drawer"]` if modal doesn't appear.

2.  **Process (Local Backend):**
    *   `receiver.py` receives the JSON payload.
    *   **Deduplication:** Checks memory cache (unique bet ID) to prevent duplicates.
    *   **Storage:** Inserts valid bets into `bets.db`.

3.  **Data Access:**
    *   **Live Dashboard:** `https://vengeful-mervin-uncoveting.ngrok-free.dev/view` (or `http://localhost:5001/view` if accessing locally)
    *   **Export Data:** Click "Export CSV" on the dashboard or visit `/export` to download `bets.csv`.
    *   **Raw Database:** Open `bets.db` using **DB Browser for SQLite** to inspect direct rows.
    *   **Note:** The Chrome extension uses the ngrok HTTPS URL by default (required because stake.com is HTTPS and blocks mixed content to localhost).

4.  **Alert (Telegram):**
    *   `telegram_bot.py` polls `bets.db` every 10 seconds.
    *   New high-value bets trigger a Telegram message to the configured Channel.

---

## 🛠️ Developer Cheatsheet

### 1. Starting the System
Always use the PowerShell script to ensure environment variables and paths are correct:
```powershell
.\start_services.ps1
```

### 2. Monitoring
*   **Logs:** check `receiver.log` and `bot.log`.
*   **Browser:** Open `https://vengeful-mervin-uncoveting.ngrok-free.dev/view` for the live dashboard (or `http://localhost:5001/view` locally).
*   **Telegram:** Check the bot DM or channel.

### 3. Key Configurations
*   **Min Amounts:** `receiver.py` (lines ~138) and `content.js` (lines ~20).
*   **Endpoints:** `content.js` must match the running ngrok address.

### 4. Common Issues
*   **Ghost Windows:** If python windows pop up, use `start_services.ps1` (it handles `-WindowStyle Hidden`).
*   **Missing Data in DB:** Ensure `receiver.py` is running in the project root so it writes to the correct `bets.db`.
*   **Unicode/Emoji Crash:** Windows Console hates emojis. Keep logs clean or force UTF-8 (patched in V5).

---

## 🔗 Related Docs
*   [`docs/ARCHITECTURE_V3.5.md`](docs/ARCHITECTURE_V3.5.md): Detailed amnesia-proof explanation of the v3.5 Direct-Fire Telegram photo pipeline.
*   [`docs/TROUBLESHOOTING_FIXES.md`](docs/TROUBLESHOOTING_FIXES.md): Details recent critical fixes (Ghost Window, Mixed Content, etc).
