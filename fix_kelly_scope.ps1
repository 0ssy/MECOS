# fix_kelly_scope.ps1
# Fixes: name '_kelly_fraction' is not defined
# The function was appended to trading_agent.py but the injection point
# inside _analyze_symbol calls it before Python sees it at module level.
# Fix: move the import-safe call inside the fused block directly.
#
# Run from MECOS folder: .\fix_kelly_scope.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Fixing _kelly_fraction scoping..." -ForegroundColor Cyan

$Path = "trading\trading_agent.py"
Copy-Item $Path "$Path.bak" -Force
Write-Host "  [BAK] $Path.bak" -ForegroundColor Yellow

$content = Get-Content $Path -Raw

# Remove the old injected block that references _kelly_fraction by name
# and replace with an inline lambda that doesn't depend on module-level scope
$OldBlock = @'
            # --- QuantSignalFusion: regime-aware Bayesian fusion ---
            fused = self.quant_fusion.fuse(
                orchestrated_signals=orchestrated,
                features=features,
                regime=regime,
            )
            # Kelly-fraction position sizing
            edge   = float(fused.get("edge", 0.0))
            conf   = float(fused.get("confidence", 0.0))
            vol    = float(features.get("realized_volatility", 0.02))
            kelly  = _kelly_fraction(edge, conf, vol)
            fused["kelly_fraction"] = kelly
            fused["allocation"]     = kelly
            orchestrated = {**orchestrated, **fused}
'@

$NewBlock = @'
            # --- QuantSignalFusion: regime-aware Bayesian fusion ---
            fused = self.quant_fusion.fuse(
                orchestrated_signals=orchestrated,
                features=features,
                regime=regime,
            )
            # Kelly-fraction position sizing (inline to avoid scope issues)
            import numpy as _np
            _edge = float(fused.get("edge", 0.0))
            _conf = float(fused.get("confidence", 0.0))
            _vol  = max(float(features.get("realized_volatility", 0.02)), 0.01)
            _kelly = float(_np.clip(0.5 * (_edge * _conf) / _vol, 0.01, 0.20)) if _edge > 0 and _conf > 0 else 0.01
            fused["kelly_fraction"] = _kelly
            fused["allocation"]     = _kelly
            orchestrated = {**orchestrated, **fused}
'@

if ($content -match [regex]::Escape("kelly  = _kelly_fraction(edge, conf, vol)")) {
    $content = $content.Replace($OldBlock, $NewBlock)
    Write-Host "  [OK]  Replaced _kelly_fraction call with inline calculation" -ForegroundColor Green
} else {
    # Try partial match - just replace the _kelly_fraction call line
    $content = $content -replace `
        'kelly\s*=\s*_kelly_fraction\(edge,\s*conf,\s*vol\)', `
        'import numpy as _np; kelly = float(_np.clip(0.5 * (edge * conf) / max(vol, 0.01), 0.01, 0.20)) if edge > 0 and conf > 0 else 0.01'
    Write-Host "  [OK]  Patched _kelly_fraction line directly" -ForegroundColor Green
}

Set-Content $Path $content -Encoding UTF8

Write-Host ""
Write-Host "Now run: python main.py" -ForegroundColor Yellow
Write-Host "Let it run for 5+ minutes without stopping." -ForegroundColor Gray
Write-Host "You should see SIGNAL lines appearing once buffers fill (50 bars ~2-3 min)" -ForegroundColor Gray
Write-Host ""
Write-Host "What to watch for:" -ForegroundColor White
Write-Host "  - No more '_kelly_fraction is not defined' errors" -ForegroundColor Green
Write-Host "  - SIGNAL lines: conf=0.xxx (raw=0.xxx) | edge=0.xxx" -ForegroundColor Green  
Write-Host "  - MetaOrchestrator confidence 0.4+ when trend is clear" -ForegroundColor Green
Write-Host "  - Trades executing with real sector names" -ForegroundColor Green
Write-Host ""
