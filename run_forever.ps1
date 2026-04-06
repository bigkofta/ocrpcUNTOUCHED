# HighRoller Supervisor Script (v3.5.5)
# Manages: Receiver, Telegram Bot, Radio Server, and Ngrok
# ========================================================

Write-Host "🔄 HighRoller Master Supervisor v3.5.5 Started" -ForegroundColor Cyan
Write-Host "   Ensuring stability and auto-restart for all services..." -ForegroundColor Gray

# Force UTF-8 for entire PowerShell session (Prevents Emoji crashes)
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Load environment variables from .env file
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Host "📄 Loading environment from .env" -ForegroundColor Gray
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.+)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Cleanup function to kill existing ghost processes
function Cleanup-Ports {
    Write-Host "🧹 Cleaning up existing ports (5001, 5002)..." -ForegroundColor Gray
    # Kill any python processes using our ports
    @ (5001, 5002) | ForEach-Object {
        $port = $_
        $proc = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
        if ($proc) {
            Write-Host "   Stopping process on port $port (PID: $proc)" -ForegroundColor Yellow
            Stop-Process -Id $proc -Force -ErrorAction SilentlyContinue
        }
    }
    # General cleanup for ngrok
    Stop-Process -Name "ngrok" -Force -ErrorAction SilentlyContinue
}

Cleanup-Ports

$pReceiver = $null
$pBot = $null
$pRadio = $null
$pNgrok = $null

while ($true) {
    # 1. Check Receiver (Port 5001)
    if ($null -eq $pReceiver -or $pReceiver.HasExited) {
        Write-Host "⚠️  Receiver stopped. Restarting..." -ForegroundColor Yellow
        $pReceiver = Start-Process python -ArgumentList "-u", "receiver.py" -PassThru -WindowStyle Hidden -RedirectStandardOutput "receiver.log" -RedirectStandardError "receiver_error.log"
        Write-Host "✅ Receiver started (PID: $($pReceiver.Id))" -ForegroundColor Green
    }

    # 2. Check Telegram Bot (Polling & Logic)
    if ($null -eq $pBot -or $pBot.HasExited) {
        Write-Host "⚠️  Bot stopped. Restarting..." -ForegroundColor Yellow
        $pBot = Start-Process python -ArgumentList "-u", "telegram_bot.py" -PassThru -WindowStyle Hidden -RedirectStandardOutput "bot.log" -RedirectStandardError "bot_error.log"
        Write-Host "✅ Bot started (PID: $($pBot.Id))" -ForegroundColor Green
    }

    # 3. Check Radio Server (Port 5002 - WebSockets)
    if ($null -eq $pRadio -or $pRadio.HasExited) {
        Write-Host "⚠️  Radio Server stopped. Restarting..." -ForegroundColor Yellow
        $pRadio = Start-Process python -ArgumentList "-u", "radio_server.py" -PassThru -WindowStyle Hidden -RedirectStandardOutput "radio.log" -RedirectStandardError "radio_error.log"
        Write-Host "✅ Radio started (PID: $($pRadio.Id))" -ForegroundColor Green
    }

    # 4. Check Ngrok Tunnel (External Access)
    if ($null -eq $pNgrok -or $pNgrok.HasExited) {
        Write-Host "⚠️  Ngrok tunnel stopped. Restarting..." -ForegroundColor Yellow
        $pNgrok = Start-Process ngrok -ArgumentList "http --domain=vengeful-mervin-uncoveting.ngrok-free.dev 5001" -PassThru -WindowStyle Hidden
        Write-Host "✅ Ngrok online (PID: $($pNgrok.Id))" -ForegroundColor Green
    }

    Start-Sleep -Seconds 10
}
