# fix_kelly_permanent.ps1
# Permanently fixes _kelly_fraction is not defined
# by finding EVERY reference to _kelly_fraction in trading_agent.py
# and replacing with inline math directly.
#
# Run from MECOS folder: .\fix_kelly_permanent.ps1

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "Permanently fixing _kelly_fraction..." -ForegroundColor Cyan

$Path = "trading\trading_agent.py"
Copy-Item $Path "$Path.bak" -Force

$lines = Get-Content $Path -Encoding UTF8
$newLines = @()
$fixed = 0

foreach ($line in $lines) {
    # Replace any line that calls _kelly_fraction(...)
    if ($line -match "_kelly_fraction\(") {
        # Extract indentation
        $indent = ($line -replace "^(\s*).*", '$1')
        # Replace with inline calculation
        $newLines += "${indent}_kelly = float(__import__('numpy').clip(0.5 * (_edge * _conf) / max(_vol, 0.01), 0.01, 0.20)) if _edge > 0 and _conf > 0 else 0.01"
        $fixed++
        Write-Host "  [FIX] Replaced _kelly_fraction call at: $($line.Trim())" -ForegroundColor Yellow
    } else {
        $newLines += $line
    }
}

Set-Content $Path $newLines -Encoding UTF8
Write-Host "  [OK]  Fixed $fixed occurrence(s)" -ForegroundColor Green

# Also verify _edge, _conf, _vol are defined before the kelly line
# by checking surrounding context
$content = Get-Content $Path -Raw
if ($content -notmatch "_edge\s*=\s*float\(fused\.get") {
    Write-Host "  [WARN] _edge assignment not found — checking for alternative patterns" -ForegroundColor Yellow
    # Try to find where fused is used and inject variables
    $content = $content -replace `
        "(fused\[.kelly_fraction.\]\s*=)", `
        '_edge = float(fused.get("edge", 0.0))
            _conf = float(fused.get("confidence", 0.0))
            _vol  = max(float(features.get("realized_volatility", 0.02)), 0.01)
            _kelly = float(__import__("numpy").clip(0.5 * (_edge * _conf) / max(_vol, 0.01), 0.01, 0.20)) if _edge > 0 and _conf > 0 else 0.01
            $1'
    Set-Content $Path $content -Encoding UTF8
    Write-Host "  [OK]  Variables injected before kelly assignment" -ForegroundColor Green
}

Write-Host ""
Write-Host "Run: python main.py" -ForegroundColor Yellow
Write-Host "The '_kelly_fraction is not defined' error should be gone." -ForegroundColor Gray
Write-Host ""
