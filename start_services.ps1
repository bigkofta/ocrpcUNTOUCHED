
# Start Services Script
# Starts receiver and telegram bot in background (Hidden Window)
# Logs redirected to receiver.log and bot.log

Write-Host "🛑 Stopping existing python processes..." -ForegroundColor Yellow
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "🚀 Starting Receiver (Hidden)..." -ForegroundColor Cyan
Write-Host "🚀 Starting Receiver (Hidden)..." -ForegroundColor Cyan
$receiverArgs = "-c", "import sys; from subprocess import Popen; Popen(['python', '-u', 'receiver.py'], shell=True, creationflags=0x08000000)"
Start-Process python -ArgumentList "-u", "receiver.py" -WindowStyle Hidden -RedirectStandardOutput "receiver.log" -RedirectStandardError "receiver_error.log" -WorkingDirectory $PSScriptRoot

Write-Host "🚀 Starting Telegram Bot (Hidden)..." -ForegroundColor Cyan
Start-Process python -ArgumentList "-u", "telegram_bot.py" -WindowStyle Hidden -RedirectStandardOutput "bot.log" -RedirectStandardError "bot_error.log" -WorkingDirectory $PSScriptRoot

Write-Host "✅ Services started in background!" -ForegroundColor Green
Write-Host "   - Receiver Log: receiver.log"
Write-Host "   - Bot Log:      bot.log"
Write-Host ""
Write-Host "ℹ️  To check status, run: Get-Process python"
Write-Host "ℹ️  To stop, run: Stop-Process -Name python -Force"
