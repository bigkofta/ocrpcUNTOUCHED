#!/bin/bash

# 1. Enable Docker to start on boot
echo "🐳 Enabling Docker on boot..."
systemctl enable docker
systemctl start docker

# 2. Create Ngrok Systemd Service
echo "🔗 Configuring Ngrok persistence..."

# Define the service file content
SERVICE_CONTENT="[Unit]
Description=Ngrok Tunnel
After=network.target

[Service]
ExecStart=/snap/bin/ngrok http --domain=vengeful-mervin-uncoveting.ngrok-free.dev 5001
Restart=always
User=root

[Install]
WantedBy=multi-user.target"

# Write it to /etc/systemd/system/ngrok.service
echo "$SERVICE_CONTENT" > /etc/systemd/system/ngrok.service

# 3. Reload and Start Ngrok
echo "🚀 Starting Ngrok service..."
systemctl daemon-reload
systemctl enable ngrok
systemctl start ngrok

# 4. Check Status
echo "✅ Checking status..."
systemctl status ngrok --no-pager | head -n 10

echo ""
echo "🎉 DONE! Your VPS will now auto-start HighRoller and Ngrok if it reboots."
