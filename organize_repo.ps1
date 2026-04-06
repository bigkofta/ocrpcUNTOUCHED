
# Create directories
New-Item -ItemType Directory -Force -Path 'scripts'
New-Item -ItemType Directory -Force -Path 'config'
New-Item -ItemType Directory -Force -Path 'logs'
New-Item -ItemType Directory -Force -Path 'docs'
New-Item -ItemType Directory -Force -Path 'archive\v5_debug'

# Move Documentation
Move-Item 'ARCHITECTURE.md', 'DEPLOYMENT.md', 'TROUBLESHOOTING_FIXES.md' 'docs' -ErrorAction SilentlyContinue

# Move Config (Scripts only)
Move-Item 'setup_*.sh' 'config' -ErrorAction SilentlyContinue

# Move Logs
Move-Item 'receiver.log', 'receiver_error.log' 'logs' -ErrorAction SilentlyContinue
Move-Item 'bot.log', 'bot_error.log' 'logs' -ErrorAction SilentlyContinue

# Archive Debug/Test Scripts
$debugScripts = @(
    'validate_pipeline.py',
    'test_viewer.ps1',
    'test_trigger.py',
    'send_debug_photo.py',
    'search_bets.py',
    'migrate_data.py',
    'inspect_*.py',
    'get_url.py',
    'debug_*.py',
    'simulate_extension.py',
    'check_db.py',
    'cleanup_db.py'
)
foreach ($script in $debugScripts) {
    Move-Item $script 'archive\v5_debug' -ErrorAction SilentlyContinue
}

# Archive Images
Move-Item '*.png' 'archive\v5_debug' -ErrorAction SilentlyContinue

# Move Source JS (Reference)
Move-Item 'highroller_v5.1_strict_fixed.js' 'archive\v5_debug' -ErrorAction SilentlyContinue

# Clean up empty files
Remove-Item 'debug_db.txt' -ErrorAction SilentlyContinue

Write-Host "✅ Cleanup Complete!"
