@echo off
cd /d "c:\Users\poo\highrollerocr-1"
echo Starting HighRoller Supervisor...
powershell -ExecutionPolicy Bypass -File .\run_forever.ps1
pause
