# fix_executor_bug.ps1
# Fixes: name 'signal' is not defined in paper_trading_executor.py
# The generate_exit_signal method uses signal.get() but signal doesn't exist in that scope.
# In generate_exit_signal, the side is always EXIT/SELL so we hardcode "SELL".
#
# Run from MECOS folder: .\fix_executor_bug.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Fixing paper_trading_executor.py..." -ForegroundColor Cyan

$Path = "trading\paper_trading_executor.py"
Copy-Item $Path "$Path.bak" -Force
Write-Host "  [BAK] $Path.bak" -ForegroundColor Yellow

$content = Get-Content $Path -Raw

# Fix 1: generate_exit_signal uses signal.get("decision") but signal doesn't exist
# In exit context the side is always SELL
$content = $content -replace `
    'current_price = _realistic_fill_price\(tick, signal\.get\("decision", "BUY"\), slippage_bps=5\.0\)(\s+if current_price <= 0:)', `
    'current_price = _realistic_fill_price(tick, "SELL", slippage_bps=5.0)  # exits always sell$1'

# Fix 2: any other place in the file where signal.get() is used outside execute_signal scope
# Replace with safe fallback using tick data
$content = $content -replace `
    '_realistic_fill_price\(tick, signal\.get\(["\x27]decision["\x27],\s*["\x27]BUY["\x27]\)', `
    '_realistic_fill_price(tick, signal.get("decision", "BUY") if isinstance(signal, dict) else "BUY"'

Set-Content $Path $content -Encoding UTF8
Write-Host "  [OK]  paper_trading_executor.py fixed" -ForegroundColor Green

Write-Host ""
Write-Host "Now run: python main.py" -ForegroundColor Yellow
Write-Host "Let it run for at least 5 minutes and paste the status block." -ForegroundColor Gray
Write-Host ""
