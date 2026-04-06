/* ============================
   HighRoller v2.3 - "Hybrid Capture"
   Restores Popup Window (primary) with Direct Fallback.
   Robust URL extraction.
   ============================ */

console.log('🛠️ HighRoller Content Script Injected!');

// ═══════════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════════
const CONFIG = {
    // Receiver endpoint (for database logging)
    RECEIVER_ENDPOINT: 'https://vengeful-mervin-uncoveting.ngrok-free.dev/bets',
    RECEIVER_TOKEN: 'j6TOV8FDviMFVdyTNzgvHnPjsflfEg2ECSxRPPiAWKg',

    // Thresholds for photo capture (triggers popup capture)
    PHOTO_MIN: { multi: 1000, standard: 14750 },

    // Minimum to log to database
    DB_LOG_MIN: { multi: 500, standard: 5000 },

    EXCLUDED_CURRENCIES: ['MXN', 'IDR', 'TRY'], // Exclude currencies with high nominal values

    STRICT: true  // Only process 5-column tables
};

// ═══════════════════════════════════════════════════════════════
// DEDUPLICATION
// ═══════════════════════════════════════════════════════════════
const seenSlips = new Set();
const SEEN_KEY = 'hr_seen_v4';

try {
    const stored = localStorage.getItem(SEEN_KEY);
    if (stored) JSON.parse(stored).forEach(k => seenSlips.add(k));
} catch { }

function saveSeen() {
    try {
        const arr = Array.from(seenSlips).slice(-2000);
        localStorage.setItem(SEEN_KEY, JSON.stringify(arr));
    } catch { }
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════
function parseAmount(raw) {
    if (!raw) return { value: null, currency: 'UNK' };
    const currency = raw.includes('MX$') ? 'MXN' :
        raw.includes('IDR') ? 'IDR' :
            raw.includes('TRY') ? 'TRY' :
                raw.includes('CA$') ? 'CAD' :
                    raw.includes('$') ? 'USD' :
                        raw.includes('€') ? 'EUR' : 'UNK';
    const cleaned = raw.replace(/[^\d.,]/g, '');
    const commaAsDec = /,\d{1,3}$/.test(cleaned);
    let normalized = commaAsDec ? cleaned.replace(',', '.') : cleaned;
    normalized = normalized.replace(/[.,](?=\d{3}\b)/g, '');
    const value = parseFloat(normalized);
    return { value: Number.isFinite(value) ? value : null, currency };
}

// ═══════════════════════════════════════════════════════════════
// ROW PARSING
// ═══════════════════════════════════════════════════════════════
function parseRow(tr) {
    const tds = tr.querySelectorAll('td');
    if (tds.length === 0) return null;
    if (CONFIG.STRICT && tds.length !== 5) return null;
    if (tds.length < 5) return null;

    const event = tds[0]?.innerText?.trim() || '';
    const user = tds[1]?.innerText?.trim() || '';
    const time = tds[2]?.innerText?.trim() || '';
    const odds = tds[3]?.innerText?.trim() || '';
    const amountRaw = tds[4]?.innerText?.trim() || '';
    const { value: amount, currency } = parseAmount(amountRaw);

    if (!Number.isFinite(amount)) return null;

    // Skip excluded currencies (MXN, IDR, TRY)
    if (CONFIG.EXCLUDED_CURRENCIES.includes(currency)) {
        return null;
    }

    const isMulti = /multi/i.test(event);
    const type = isMulti ? 'multi' : 'standard';

    // Extract slip URL if present
    let slip_url = null;
    const link = tr.querySelector('a[href*="iid="]');
    if (link) {
        try {
            slip_url = new URL(link.getAttribute('href'), location.href).toString();
        } catch { }
    }

    return { event, user, time, odds, amount_raw: amountRaw, amount, currency, type, slip_url };
}

// ═══════════════════════════════════════════════════════════════
// CAPTURE LOGIC
// ═══════════════════════════════════════════════════════════════
async function captureSlipFromRow(node) {
    const tr = node.row || node;

    // Strategy 1: Look for links with IID or Sport ID (v5.1 Logic)
    const links = tr.querySelectorAll("a[href]");
    for (const a of links) {
        const h = a.href;
        if (h.includes('iid=') || h.includes('iid%3D') || h.includes('sport:')) {
            console.log("✅ Found Slip Link (Strategy 1):", h);
            return h;
        }
    }

    // Strategy 2: Button Click + History Check
    const clickable = tr.querySelector("button") || tr.querySelector("td") || tr;
    console.log("🖱️ Strategy 2: Clicking to find URL...");
    try {
        clickable.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
    } catch {
        clickable.click();
    }

    // Wait for URL update OR Modal
    for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 100));

        // 1. URL Check
        const u = location.href;
        if (u.includes('iid=')) {
            console.log("✅ URL Updated (Strategy 2):", u);
            return u;
        }

        // 2. Modal Check (if URL doesn't change, maybe modal has link)
        const modal = document.querySelector('[data-testid="modal"], .modal, [role="dialog"]');
        if (modal) {
            const html = modal.innerHTML;
            const m = html.match(/iid[=:]["']?([^"'&\s]+)/i);
            if (m) {
                const iid = m[1];
                const extracted = `${location.origin}/sports/home?iid=${encodeURIComponent(iid)}&modal=bet`;
                console.log("✅ Extracted ID from Modal:", iid);

                // Close modal to clean up (Escape key)
                document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
                return extracted;
            }
        }
    }
    return null;
}

// ═══════════════════════════════════════════════════════════════
// NETWORK & POPUP
// ═══════════════════════════════════════════════════════════════
async function postToReceiver(parsed) {
    try {
        const payload = {
            type: parsed.slip_url ? 'slip' : 'feed',
            key: `${parsed.event}|${parsed.time}|${parsed.amount}`,
            event: parsed.event,
            user: parsed.user,
            time: parsed.time,
            odds: parsed.odds,
            amount_raw: parsed.amount_raw,
            amount_value: parsed.amount,
            currency: parsed.currency,
            slip_url: parsed.slip_url,
            slip_id: parsed.slip_url ? new URL(parsed.slip_url).searchParams.get('iid') : null,
            detected_at: new Date().toISOString(),
            screenshot: parsed.screenshot || null  // Include screenshot if available
        };

        const response = await fetch(CONFIG.RECEIVER_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-auth-token': CONFIG.RECEIVER_TOKEN,
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            console.log('✅ DB SUCCESS:', parsed.event.substring(0, 25), '$' + parsed.amount);
            return true;
        } else {
            return false;
        }
    } catch (err) {
        return false;
    }
}

function requestPopupCapture(parsed) {
    if (!parsed.slip_url) return;
    console.log('📸 Requesting popup capture:', parsed.event.substring(0, 25));
    chrome.runtime.sendMessage({
        type: 'captureSlipInPopup',
        slipUrl: parsed.slip_url,
        metadata: parsed
    });
}

function needsDbLog(parsed) {
    const min = parsed.type === 'multi' ? CONFIG.DB_LOG_MIN.multi : CONFIG.DB_LOG_MIN.standard;
    return parsed.amount >= min;
}

// ═══════════════════════════════════════════════════════════════
// MAIN LOGIC
// ═══════════════════════════════════════════════════════════════
let isCaptureLocked = false;

async function processNode(node) {
    if (node.nodeType === 1 && node.tagName === 'TR') {
        const parsed = parseRow(node);
        if (!parsed) return;

        const dedupKey = parsed.slip_url || `${parsed.event}|${parsed.time}|${parsed.amount}`;
        if (seenSlips.has(dedupKey)) return;

        seenSlips.add(dedupKey);
        saveSeen();

        // 1. Log to DB
        if (needsDbLog(parsed)) {
            console.log('📤 Sending to DB...', parsed.amount_raw);
            await postToReceiver(parsed);
        }

        // 2. Photo Capture
        const photoMin = parsed.type === 'multi' ? CONFIG.PHOTO_MIN.multi : CONFIG.PHOTO_MIN.standard;
        if (parsed.amount >= photoMin) {
            console.log('🎯 HIGH BET SEEN:', parsed.type.toUpperCase(), '$' + parsed.amount);

            // MUTEX LOCK: Wait if another capture is in progress
            const maxWait = 15000;
            const startWait = Date.now();
            while (isCaptureLocked) {
                if (Date.now() - startWait > maxWait) {
                    console.warn('⚠️ Capture lock timed out, forcing through...');
                    break;
                }
                console.log('⏳ Waiting for capture lock...');
                await new Promise(r => setTimeout(r, 1000));
            }

            isCaptureLocked = true;

            try {
                console.log('🔒 Capture Lock Acquired for:', parsed.event.substring(0, 20));

                // Try to get URL for Popup
                const capturedUrl = await captureSlipFromRow(node);

                if (capturedUrl) {
                    // SUCCESS: Found URL -> Trigger Popup
                    console.log('✅ URL Captured, opening Popup Window:', capturedUrl);
                    parsed.slip_url = capturedUrl;
                    parsed.slip_id = new URL(capturedUrl).searchParams.get('iid');
                    postToReceiver(parsed); // Update DB with URL
                    requestPopupCapture(parsed);
                } else {
                    // FAILURE: No URL -> Fallback to Direct Capture
                    console.warn('⚠️ Could not extract URL/IID. Falling back to Direct Capture.');

                    // Request screenshot from background
                    chrome.runtime.sendMessage({
                        type: 'captureAndSendDirect',
                        metadata: { ...parsed, slip_url: window.location.href, method: 'direct_modal_fallback' }
                    }, async (response) => {
                        if (response && response.success && response.screenshot) {
                            console.log('✅ Screenshot received, sending to server...');
                            // Send to server with screenshot
                            await postToReceiver({ ...parsed, screenshot: response.screenshot });
                        } else {
                            console.error('❌ Screenshot capture failed:', response?.error);
                            // Send without screenshot as fallback
                            await postToReceiver(parsed);
                        }
                    });

                    // Cleanup modal
                    setTimeout(() => {
                        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
                    }, 800);
                }

                // Extra cooldown after capture to let UI settle
                await new Promise(r => setTimeout(r, 1500));

            } finally {
                isCaptureLocked = false;
                console.log('🔓 Capture Lock Released');
            }
        }
    }
}

function startObserver() {
    const table = document.querySelector('table.table-content') || document.querySelector('table');
    if (!table) {
        setTimeout(startObserver, 2000);
        return;
    }

    console.log('👁️ Observer starting...');
    table.querySelectorAll('tr').forEach(processNode);

    new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => processNode(node));
        });
    }).observe(table, { childList: true, subtree: true });

    console.log('✅ Observer running!');
}

setTimeout(startObserver, 2000);

// Test Injection
window.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'HR_TRIGGER_TEST') {
        const testBet = {
            type: 'multi', amount: 50000, amount_raw: '$50,000', event: 'TEST BET',
            time: '12:00', odds: '2.0', currency: 'USD',
            slip_url: 'https://stake.com/sports/home?iid=sport%3A12345&modal=bet'
        };
        console.log('🧪 Test Triggered');
        requestPopupCapture(testBet);
    }
});

const script = document.createElement('script');
script.innerHTML = `window.TEST_SHOT = () => window.postMessage({ type: "HR_TRIGGER_TEST" }, "*"); console.log("✅ TEST_SHOT() ready");`;
document.documentElement.appendChild(script);
