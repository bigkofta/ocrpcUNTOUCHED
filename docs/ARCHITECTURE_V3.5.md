# HighRoller Direct-Fire Architecture (Stable Enhanced v3.5)

## 📌 Overview & Amnesia Guide
**What is this system?**
HighRoller is a standalone, hybrid background-capture system that monitors high-stakes sports bets on Stake.com. When a "whale" bet is placed, the system spots it, takes a perfectly cropped screenshot of the slip, and instantly sends it to a Telegram channel. It also logs every bet in a local SQLite database for historical querying.

**Why v3.5 "Direct-Fire"?**
Historically, the Chrome extension sent the screenshot Base64 string through `ngrok` to a Python (`receiver.py`) backend, which *then* sent it to Telegram. This failed constantly because large images choked the connection. 
In **v3.5**, the Chrome Extension handles taking the photo and sending it **DIRECTLY** to Telegram's API within 3 seconds, bypassing the Python backend entirely for the photo delivery. The Python backend is now strictly used as a pure database logger.

---

## 🧩 The Core Components

### 1. The Chrome Extension (`chrome_extension/`)
*The active listener running in your browser.*
- **`content.js`**: Re-injected dynamically. It quietly monitors the live rolling High Roller table. When it spots a qualifying bet (e.g., $15,000+ Standard or $1,000+ Multi), it triggers the capture.
- **`background.js` (Service Worker)**: The engine. 
  1. Opens a hidden popup window of the specific betslip URL.
  2. Uses `chrome.tabs.captureVisibleTab` to screenshot the popup.
  3. Uses `OffscreenCanvas` to crop the image to the exact modal dimensions (700px width).
  4. **Direct-Fire**: Evaluates if the bet is VIP (>= $15k). It POSTs the raw image bytes *directly* to `api.telegram.org` (using either the Main or VIP Bot Token).
  5. **Data Logger**: POSTs the text payload to the local Python receiver via `ngrok` so the data is permanently saved in the local DB.

### 2. Local Python Receiver (`receiver.py`)
*The Local Memory Bank / Database Manager.*
- A Flask server running locally on Windows port `5001`.
- It accepts POST requests from the extension (routed securely through Ngrok).
- Validates the data, prevents duplicate records, and saves the details into `bets.db`.
- **Self-Healing Base64**: If the extension *does* happen to send an image payload here, the receiver has strict logic to ensure 0-byte images are rejected to prevent DB corruption.

### 3. Telegram Poller (`telegram_bot.py`)
*The Safety Net.*
- Polls `bets.db` constantly. Used primarily for fallback or text-only logic. Since the photo pipeline is now fully operational in the browser extension, this handles secondary/fallback alerting.

---

## 📸 Example Lifespan of a Whale Bet 
*(Exactly what happens step-by-step)*

1. **Scrape**: Stake shows a $25,000 bet. `content.js` identifies it, checks deduplication cache, and extracts the `iid` (the hidden ID of the slip).
2. **Popup Request**: `content.js` tells `background.js` to open a Chrome popup window holding that specific slip.
3. **Capture**: `background.js` waits ~3 seconds for the popup UI to load, takes a screenshot, and crops it exactly to the bet slip.
4. **Evaluate Routing**: Since $25,000 >= $15,000, `background.js` flags this as VIP.
5. **Telegram Dispatch**: `background.js` POSTs the cropped image straight to Telegram via `VIP_BOT_TOKEN` to `VIP_CHAT_ID`. (If it was $5,000, it would go to the Main channel).
6. **DB Archive**: `background.js` sends an HTTP POST containing the bet text to your `ngrok` URL. 
7. **Save**: `receiver.py` receives the ngrok payload, assigns a timestamp, and saves it into `bets.db`.

---

## 🚀 How to Start from Scratch (Amnesia Check)
If the PC restarts or you forget how to launch:
1. Double-click `launch_highroller.bat` (which triggers `start_services.ps1`).
2. This quietly launches `receiver.py`, `telegram_bot.py`, and `ngrok` in the background.
3. Make sure the Chrome Extension (`HighRoller Direct-Fire`) is enabled in your browser on `stake.com`.
4. Ensure the `.env` file exists and has your configured `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_VIP_TOKEN`, and `TELEGRAM_VIP_CHAT_ID`.

That's it. The system is entirely autonomic.
