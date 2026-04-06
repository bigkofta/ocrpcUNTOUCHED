#!/bin/bash

# HighRoller VPS Setup Script
# Run this on your fresh VPS (Ubuntu/Debian)

echo "🚀 Starting HighRoller VPS Setup..."

# 1. Update system
echo "📦 Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Docker & Docker Compose
echo "🐳 Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    echo "✅ Docker installed."
else
    echo "✅ Docker already installed."
fi

# 3. Setup directory
echo "Tb Setting up directory..."
mkdir -p highroller
cd highroller

# 4. Copy files (You will need to upload these manually or git clone)
# For now, we assume this script is run where the files are, or we create placeholders
# In a real scenario, you'd git clone here.

echo "⚠️  IMPORTANT: Make sure you have uploaded the following files to this folder:"
echo "   - Dockerfile"
echo "   - docker-compose.yml"
echo "   - requirements.txt"
echo "   - receiver.py"
echo "   - database.py"
echo "   - bets.db (if migrating data)"

# 5. Start Service
echo "🔥 Starting Receiver..."
# Check if docker-compose plugin is installed or use legacy docker-compose
if docker compose version &> /dev/null; then
    sudo docker compose up -d --build
else
    sudo docker-compose up -d --build
fi

echo "✅ Service started!"
echo "   Receiver running on port 5001"
echo "   Check logs with: docker compose logs -f"
