# 🚀 HighRoller VPS Deployment Guide

## 1. Purchase VPS (Privacy-Focused)
Since you need to avoid fraud flags (VPN usage) and prefer crypto/privacy:

**Option A: DigitalOcean (Standard)**
- **Why**: Reliable, easy to use, $6/mo.
- **Go to**: `cloud.digitalocean.com`
- **Create**: Droplet -> Region (New York) -> OS (Ubuntu 24.04) -> Size (Basic, Regular, $6/mo).

**Option B: BitLaunch (Privacy)**
- **Why**: You can pay with Crypto. They resell DigitalOcean/Linode/Vultr but *they* handle the account.
- **Go to**: `bitlaunch.io`

**Option C: Hostinger**
- **Why**: Accepts crypto, generally easier sign-up.
- **Go to**: `hostinger.com` (VPS KVM 1).

**Specs Needed:**
- **OS**: Ubuntu 24.04 (or 22.04)
- **Size**: Smallest available (1 CPU, 1GB RAM) is plenty.

## 2. Connect to VPS
Open your local terminal and run:
```bash
ssh root@<YOUR_VPS_IP_ADDRESS>
# Enter the password you set (or use SSH key)
```

## 3. Upload Files
You need to get the project files onto the VPS.
**Option A: Copy-Paste (Easiest for small files)**
Run these commands on the VPS to create the files:

1.  **Create Directory:**
    ```bash
    mkdir -p highroller
    cd highroller
    ```

2.  **Create `docker-compose.yml`:**
    ```bash
    nano docker-compose.yml
    # Paste the content of docker-compose.yml here
    # Press Ctrl+X, then Y, then Enter to save
    ```

3.  **Create `Dockerfile`:**
    ```bash
    nano Dockerfile
    # Paste the content of Dockerfile here
    # Save and exit
    ```

4.  **Create `requirements.txt`:**
    ```bash
    nano requirements.txt
    # Paste:
    # flask
    # flask-cors
    # Save and exit
    ```

5.  **Create `receiver.py`:**
    ```bash
    nano receiver.py
    # Paste content of receiver.py
    # Save and exit
    ```

6.  **Create `database.py`:**
    ```bash
    nano database.py
    # Paste content of database.py
    # Save and exit
    ```

7.  **Create `telegram_bot.py`:**
    ```bash
    nano telegram_bot.py
    # Paste content of telegram_bot.py
    # Save and exit
    ```

**Option B: SCP (If you have the files locally)**
Run this from your **LOCAL** terminal (not the VPS):
```bash
scp -r receiver.py database.py telegram_bot.py Dockerfile docker-compose.yml requirements.txt root@<YOUR_VPS_IP>:/root/highroller/
```

## 4. Run Setup Script
On the VPS:
1.  Create the script:
    ```bash
    nano setup_vps.sh
    # Paste content of setup_vps.sh
    # Save and exit
    ```
2.  Run it:
    ```bash
    chmod +x setup_vps.sh
    ./setup_vps.sh
    ```

## 5. Verify
1.  Open your browser to: `http://<YOUR_VPS_IP>:5001/view`
2.  You should see the "Real-Time Bet Feed" page.

## 6. Update Browser Script
1.  Edit your local `highroller_v5.1_strict_fixed.js`.
2.  Update `CONFIG.ENDPOINT`:
    ```javascript
    ENDPOINT: "http://<YOUR_VPS_IP>:5001/bets",
    ```
    *(Note: If you want HTTPS, we'll need to set up Nginx/LetsEncrypt, but HTTP is fine for testing)*.
3.  Reload the script in the Stake console.

## ✅ Done!
Your receiver is now running 24/7 in the cloud. You can close your laptop, and it will keep receiving data (as long as the browser tab with the script is running somewhere).
