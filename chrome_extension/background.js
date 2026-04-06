/* ============================
   HighRoller Background Service Worker
   Handles screenshot capture in SEPARATE popup window
   ============================ */

// Telegram tokens for direct photo sending
const CONFIG = {
    BOT_TOKEN: '8292074725:AAE9Asxr8aSDh-wxS7tNjMcEm_jQBmwLqqc',
    CHAT_ID: '6258896163',
    VIP_BOT_TOKEN: '8539630550:AAHm4gcWb9KUU2kDf5sDiSvRvSh7xE6AVcc',
    VIP_CHAT_ID: '6258896163',
    RECEIVER_ENDPOINT: 'https://vengeful-mervin-uncoveting.ngrok-free.dev/bets',
    RECEIVER_TOKEN: 'j6TOV8FDviMFVdyTNzgvHnPjsflfEg2ECSxRPPiAWKg'
};

// Queue for screenshot requests
let captureQueue = [];
let isCapturing = false;

// Listen for messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    // Clear capture queue from content script reload
    if (request.type === "clearCaptureQueue") {
        console.log('🧹 Force clearing background capture queue (Page Reload)');
        captureQueue = [];
        sendResponse({ success: true });
        return true;
    }

    // Legacy: Direct screen capture from current tab
    if (request.type === "captureScreen") {
        const windowId = sender.tab ? sender.tab.windowId : chrome.windows.WINDOW_ID_CURRENT;
        chrome.tabs.captureVisibleTab(windowId, { format: 'png', quality: 90 }, (dataUrl) => {
            if (chrome.runtime.lastError) {
                sendResponse({ error: chrome.runtime.lastError.message });
            } else {
                sendResponse({ dataUrl: dataUrl });
            }
        });
        return true;
    }

    // Capture from CURRENT TAB and send directly to Telegram
    if (request.type === "captureAndSend" || request.type === "captureAndSendDirect") {
        console.log('📸 Capturing from current tab:', request.metadata?.event?.substring(0, 30));
        const windowId = sender.tab ? sender.tab.windowId : chrome.windows.WINDOW_ID_CURRENT;

        // Extract modal coords from current tab BEFORE capture
        chrome.scripting.executeScript({
            target: { tabId: sender.tab.id },
            func: async () => {
                // 1. Wait for actual bet content to appear (positive detection)
                const waitForContent = async (maxMs = 8000) => {
                    const start = Date.now();
                    while (Date.now() - start < maxMs) {
                        const modal = document.querySelector('[data-testid="modal"], .modal, [role="dialog"]');
                        if (modal && (modal.innerText || '').length > 100) return true;
                        await new Promise(r => setTimeout(r, 300));
                    }
                    return false;
                };

                await waitForContent();

                // 2. Find Modal and get dimensions
                const modal = document.querySelector('[data-testid="modal"], .modal, [role="dialog"]');
                if (modal) {
                    const rect = modal.getBoundingClientRect();
                    return {
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height,
                        devicePixelRatio: window.devicePixelRatio
                    };
                }
                return null;
            }
        }).then(async (injectionResults) => {
            const coords = injectionResults[0].result;

            chrome.tabs.captureVisibleTab(windowId, { format: 'png', quality: 90 }, async (dataUrl) => {
                if (chrome.runtime.lastError) {
                    console.error('❌ Capture error:', chrome.runtime.lastError.message);
                    sendResponse({ success: false, error: chrome.runtime.lastError.message });
                } else {
                    console.log('✅ Screenshot captured, checking for crop...');

                    let finalDataUrl = dataUrl;
                    if (coords) {
                        try {
                            const cropped = await cropImage(dataUrl, coords);
                            if (cropped) {
                                finalDataUrl = cropped;
                                console.log('✂️ Direct capture cropped');
                            }
                        } catch (e) {
                            console.warn('Crop failed in direct capture:', e.message);
                        }
                    }

                    await sendPhotoToTelegram(finalDataUrl, request.metadata);
                    sendResponse({ success: true, screenshot: finalDataUrl }); // Return screenshot for local processing if needed
                }
            });
        });
        return true;
    }

    // Popup capture (legacy - may trigger Cloudflare)
    if (request.type === "captureSlipInPopup") {
        console.log('📸 Received capture request:', request.metadata?.event?.substring(0, 30));

        // Ensure timestamp exists
        if (!request.timestamp) request.timestamp = Date.now();

        // Prevent queue from blowing up
        if (captureQueue.length > 5) {
            console.warn('⚠️ Queue too long, dropping request:', request.metadata?.event);
            sendResponse({ queued: false, error: 'Queue full' });
            return true;
        }

        captureQueue.push(request);
        if (!isCapturing) {
            processNextCapture();
        }
        sendResponse({ queued: true });
        return true;
    }
});

async function getModalCoords(tabId) {
    const modalRect = await chrome.scripting.executeScript({
        target: { tabId },
        func: async () => {
            const isSlipReady = (node) => {
                if (!node) return false;
                const text = (node.innerText || '').trim();
                if (text.length < 120) return false;
                const hasOdds = /Odds/i.test(text);
                const hasStake = /Stake/i.test(text);
                const hasPayout = /Est\.?\s*Payout|Payout|Return/i.test(text);
                const noLoading = !/loading|please wait|placing bet/i.test(text);
                const rect = node.getBoundingClientRect();
                return rect.width >= 320 && rect.height >= 260 && hasOdds && hasStake && hasPayout && noLoading;
            };

            const rectIsStable = async (node) => {
                const r1 = node.getBoundingClientRect();
                await new Promise(r => setTimeout(r, 120));
                const r2 = node.getBoundingClientRect();
                return Math.abs(r1.x - r2.x) < 3 &&
                    Math.abs(r1.y - r2.y) < 3 &&
                    Math.abs(r1.width - r2.width) < 4 &&
                    Math.abs(r1.height - r2.height) < 4;
            };

            const findSlipContainer = () => {
                const modalBet = document.querySelector('[data-testid="modal-bet"]');
                if (modalBet) {
                    const cardCandidates = Array.from(modalBet.querySelectorAll('div'))
                        .map((node) => {
                            const rect = node.getBoundingClientRect();
                            const text = (node.innerText || '').trim();
                            const className = typeof node.className === 'string' ? node.className : '';
                            return { node, rect, text, className };
                        })
                        .filter(({ rect, text, className }) =>
                            rect.width >= 420 &&
                            rect.width <= 760 &&
                            rect.height >= 360 &&
                            text.length > 120 &&
                            /Odds/i.test(text) &&
                            /Stake/i.test(text) &&
                            /rounded|overflow-hidden|bg-grey/i.test(className)
                        )
                        // Pick the OUTER slip card, not inner market panels
                        .sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height));

                    if (cardCandidates.length > 0) {
                        return cardCandidates[0].node;
                    }
                }

                const selectors = [
                    '[data-testid="betslip-drawer"]',
                    '[data-testid*="betslip"]',
                    '[data-testid*="bet-slip"]',
                    '[class*="betslip"]',
                    '[class*="bet-slip"]',
                    '[class*="drawer"]',
                    '[data-testid="modal"]',
                    '.modal',
                    '[role="dialog"]'
                ];

                for (const selector of selectors) {
                    const node = document.querySelector(selector);
                    if (!node) continue;
                    const rect = node.getBoundingClientRect();
                    const text = (node.innerText || '').trim();
                    if (rect.width > 220 && rect.height > 140 && text.length > 20) {
                        return node;
                    }
                }
                return null;
            };

            // Expand multi-leg slips before measuring
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                if (btn.innerText && btn.innerText.toLowerCase().includes('show more')) {
                    btn.click();
                    break;
                }
            }

            // Wait until slip is ready and position-stable (up to 5s)
            const start = Date.now();
            let slip = null;
            while (Date.now() - start < 5000) {
                slip = findSlipContainer();
                if (slip && isSlipReady(slip) && await rectIsStable(slip)) {
                    break;
                }
                slip = null;
                await new Promise(r => setTimeout(r, 120));
            }

            if (!slip) return null;

            const rect = slip.getBoundingClientRect();
            return {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
                devicePixelRatio: window.devicePixelRatio
            };
        }
    });

    return modalRect[0]?.result || null;
}

async function processNextCapture() {
    if (isCapturing || captureQueue.length === 0) return;

    // Purge stale requests (> 120 seconds old)
    const now = Date.now();
    while (captureQueue.length > 0 && (now - captureQueue[0].timestamp) > 120000) {
        console.warn('🗑️ Discarding stale capture request:', captureQueue[0].metadata?.event);
        captureQueue.shift();
    }

    if (captureQueue.length === 0) return;
    isCapturing = true;

    const request = captureQueue.shift();
    const { slipUrl, metadata } = request;

    console.log(`🖼️ Opening popup for: ${metadata?.event?.substring(0, 30)}`);

    try {
        // Open slip URL in a new popup window
        const popup = await chrome.windows.create({
            url: slipUrl,
            type: 'popup',
            width: 900,
            height: 1100,
            focused: true,
            top: 0,
            left: 0
        });

        const popupTabId = popup.tabs[0].id;

        // Initial wait for page bootstrap
        await new Promise(resolve => setTimeout(resolve, 3500));

        // Find precise slip card dimensions
        try {
            const coords = await getModalCoords(popupTabId);
            if (coords) {
                console.log('📐 Modal coords:', coords);
                request.coords = coords;
            } else {
                console.warn('⚠️ Modal coords unavailable, falling back to full-window screenshot');
            }
            await new Promise(resolve => setTimeout(resolve, 2000));
        } catch (e) {
            console.warn('Could not determine modal bounds:', e.message);
        }

        // Capture screenshot from popup
        let dataUrl = await chrome.tabs.captureVisibleTab(popup.id, { format: 'png', quality: 90 });
        console.log('📸 Screenshot captured in popup');

        // Apply Cropping if coords exist
        if (request.coords) {
            try {
                const croppedDataUrl = await cropImage(dataUrl, request.coords);
                if (croppedDataUrl) {
                    dataUrl = croppedDataUrl;
                    console.log(`✂️ Image cropped successfully. Length: ${dataUrl.length}`);
                }
            } catch (cropErr) {
                console.error('❌ Crop failed, using original:', cropErr.message);
            }
        }

        // Close popup immediately
        await chrome.windows.remove(popup.id);
        console.log('❌ Popup closed');

        // Send to Telegram
        await sendPhotoToTelegram(dataUrl, metadata);

    } catch (err) {
        console.error('❌ Capture error:', err.message);
        // Try to clean up popup if it exists
        try {
            const windows = await chrome.windows.getAll();
            for (const w of windows) {
                if (w.type === 'popup') {
                    await chrome.windows.remove(w.id);
                }
            }
        } catch { }
    } finally {
        isCapturing = false;

        // AGGRESSIVE CLEANUP: Close ALL popup windows to prevent leak
        try {
            const allWindows = await chrome.windows.getAll();
            for (const w of allWindows) {
                if (w.type === 'popup') {
                    console.log('🧹 Cleaning up leftover popup:', w.id);
                    await chrome.windows.remove(w.id).catch(() => { });
                }
            }
        } catch (cleanupErr) {
            console.warn('Cleanup error (safe to ignore):', cleanupErr.message);
        }

        // Process next in queue after cooldown
        setTimeout(() => {
            if (captureQueue.length > 0) {
                processNextCapture();
            }
        }, 2000);
    }
}

// Helper: Convert base64 to Blob
function base64ToBlob(base64, mime) {
    const byteChars = atob(base64);
    const byteNums = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
        byteNums[i] = byteChars.charCodeAt(i);
    }
    return new Blob([new Uint8Array(byteNums)], { type: mime });
}

// Send photo to Telegram AND Local Receiver
async function sendPhotoToTelegram(dataUrl, metadata) {
    console.log(`📤 Sending photo directly to Telegram... (base64 length: ${dataUrl.length})`);

    const amount = metadata.amount || 0;
    const isVip = amount >= 15000;
    const caption = `🎰 <b>HIGH ROLLER</b> (${metadata.type === 'multi' ? 'Multi' : 'Standard'})\n\n<b>Amount:</b> ${metadata.amount_raw}\n<b>Event:</b> ${(metadata.event || '').substring(0, 100)}\n<b>Odds:</b> ${metadata.odds}\n\n🔗 <a href="${metadata.slip_url || ''}">View Slip</a>`;

    // Extract raw base64 (strip data URI prefix if present)
    let b64 = dataUrl;
    if (dataUrl.includes(',')) b64 = dataUrl.split(',')[1];
    const mimeType = dataUrl.startsWith('data:image/png') ? 'image/png' : 'image/jpeg';
    const blob = base64ToBlob(b64, mimeType);

    // PRIMARY: Send directly to Telegram
    if (isVip && CONFIG.VIP_BOT_TOKEN && CONFIG.VIP_CHAT_ID) {
        console.log(`🌟 Sending VIP photo directly to Telegram (${CONFIG.VIP_CHAT_ID})`);
        await sendToChat(CONFIG.VIP_CHAT_ID, blob, caption, CONFIG.VIP_BOT_TOKEN);
    } else {
        console.log(`📣 Sending Main photo directly to Telegram (${CONFIG.CHAT_ID})`);
        await sendToChat(CONFIG.CHAT_ID, blob, caption, CONFIG.BOT_TOKEN);
    }

    // SECONDARY: Also POST to receiver.py for DB storage (best-effort)
    try {
        const payload = {
            type: 'slip',
            key: `${metadata.event}|${metadata.time}|${metadata.amount}`,
            event: metadata.event,
            user: metadata.user,
            time: metadata.time,
            odds: metadata.odds,
            amount_raw: metadata.amount_raw,
            amount_value: metadata.amount,
            currency: metadata.currency,
            slip_url: metadata.slip_url,
            slip_id: metadata.slip_url ? new URL(metadata.slip_url).searchParams.get('iid') : null,
            screenshot: dataUrl,
            source: 'popup_capture'
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
            console.log('✅ Also forwarded to receiver.py for DB storage');
        } else {
            console.warn('⚠️ receiver.py DB storage failed:', response.status);
        }
    } catch (e) {
        console.warn('⚠️ Could not forward to receiver.py (DB only, photo already sent):', e.message);
    }
}


async function sendToChat(chatId, blob, caption, token) {
    const formData = new FormData();
    formData.append('chat_id', chatId);
    formData.append('photo', blob, 'bet-slip.png');
    formData.append('caption', caption);
    formData.append('parse_mode', 'HTML');

    try {
        const response = await fetch(`https://api.telegram.org/bot${token}/sendPhoto`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (result.ok) {
            console.log(`✅ Photo sent to ID ${chatId}!`);
        } else {
            console.error(`❌ Telegram error (${chatId}):`, result.description);
        }
    } catch (e) {
        console.error(`❌ Send failed (${chatId}):`, e.message);
    }
}

// Image Cropping Utility using OffscreenCanvas
// Produces a FIXED-WIDTH centered output so Telegram columns stay consistent.
async function cropImage(dataUrl, coords) {
    const { x, y, width, height, devicePixelRatio } = coords;

    // Scale modal bounds by device pixel ratio
    const sX = Math.round(x * devicePixelRatio);
    const sY = Math.round(y * devicePixelRatio);
    const sW = Math.round(width * devicePixelRatio);
    const sH = Math.round(height * devicePixelRatio);

    // Fixed output width — all slips will be this wide in Telegram
    const TARGET_W = 700;
    const PADDING_V = 24; // vertical padding (px) above and below modal
    const scale = TARGET_W / sW;
    const scaledH = Math.round(sH * scale);
    const OUTPUT_H = scaledH + PADDING_V * 2;

    try {
        const response = await fetch(dataUrl);
        const blob = await response.blob();
        const imgBitmap = await createImageBitmap(blob);

        const canvas = new OffscreenCanvas(TARGET_W, OUTPUT_H);
        const ctx = canvas.getContext('2d');

        // Fill a dark background (matches Stake's dark UI so edges blend clean)
        ctx.fillStyle = '#1a1d2e';
        ctx.fillRect(0, 0, TARGET_W, OUTPUT_H);

        // Draw modal scaled to fixed width, centered vertically with padding
        ctx.drawImage(
            imgBitmap,
            sX, sY, sW, sH,     // source: modal region on screenshot
            0, PADDING_V, TARGET_W, scaledH  // dest: fill full width, padded top
        );

        // Convert back to Data URL
        const croppedBlob = await canvas.convertToBlob({ type: 'image/png' });
        const arrayBuffer = await croppedBlob.arrayBuffer();

        const bytes = new Uint8Array(arrayBuffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const base64 = btoa(binary);
        return `data:image/png;base64,${base64}`;
    } catch (err) {
        console.error('cropImage Error:', err);
        return null;
    }
}

console.log('🚀 HighRoller Background Service Worker Ready (Precision Crop & Server-Side Photo Mode)');
