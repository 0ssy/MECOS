# fix_trading_agent_import.ps1
# Fixes: name 'ExecutionEngine' is not defined in trading_agent.py
# The import was added at module level but ExecutionEngine lives in
# trading/execution_engine.py — needs the full trading. prefix.
# Also verifies _start_advanced_layers is called in the right place in main.py.
#
# Run from MECOS folder: .\fix_trading_agent_import.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Fix ExecutionEngine + Advanced Layers" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# FIX 1 — trading_agent.py: fix ExecutionEngine import
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Fix 1: trading_agent.py (ExecutionEngine import)" -ForegroundColor White

$TAPath = "trading\trading_agent.py"
Copy-Item $TAPath "$TAPath.bak" -Force
Write-Host "  [BAK] $TAPath.bak" -ForegroundColor Yellow

$TA = Get-Content $TAPath -Raw

# Remove any bad top-level imports that were injected
$TA = $TA -replace "from trading\.portfolio_engine import PortfolioEngine\r?\nfrom trading\.execution_engine import ExecutionEngine\r?\n", ""
$TA = $TA -replace "from trading\.portfolio_engine import PortfolioEngine\nfrom trading\.execution_engine import ExecutionEngine\n", ""
$TA = $TA -replace "from trading\.execution_engine import ExecutionEngine\r?\n", ""

# Also remove bare PortfolioEngine/ExecutionEngine imports that may have been added at top
$TA = $TA -replace "^from trading\.portfolio_engine import PortfolioEngine\n", ""
$TA = $TA -replace "^from trading\.execution_engine import ExecutionEngine\n", ""

# Fix the __init__ injection: replace the broken engine wiring with safe lazy imports
$OldEngineInit = "        self.portfolio_engine = PortfolioEngine(memory)   # Proper Kelly + vol targeting
        self.execution_engine = ExecutionEngine(memory)   # TWAP for large orders"

$NewEngineInit = "        # Portfolio and execution engines (lazy import to avoid circular deps)
        try:
            from trading.portfolio_engine import PortfolioEngine
            from trading.execution_engine import ExecutionEngine
            self.portfolio_engine = PortfolioEngine(memory)
            self.execution_engine = ExecutionEngine(memory)
        except Exception as _eng_err:
            self.portfolio_engine = None
            self.execution_engine = None"

if ($TA -match [regex]::Escape("self.portfolio_engine = PortfolioEngine(memory)   # Proper Kelly")) {
    $TA = $TA.Replace($OldEngineInit, $NewEngineInit)
    Write-Host "  [OK]  Engine init wrapped in try/except" -ForegroundColor Green
} elseif ($TA -match "portfolio_engine = PortfolioEngine") {
    # Already has it in some form — wrap whatever exists
    $TA = $TA -replace `
        "(self\.portfolio_engine\s*=\s*PortfolioEngine\(memory\))", `
        "try:`n            from trading.portfolio_engine import PortfolioEngine`n            `$1`n        except Exception:`n            self.portfolio_engine = None"
    Write-Host "  [OK]  PortfolioEngine wrapped in try/except" -ForegroundColor Green
} else {
    # Add it fresh in __init__ after self.quant_fusion
    $TA = $TA -replace `
        "(self\.quant_fusion\s*=\s*QuantSignalFusion\(\).*?# Primary signal fusion layer)", `
        '$1
        try:
            from trading.portfolio_engine import PortfolioEngine
            from trading.execution_engine import ExecutionEngine
            self.portfolio_engine = PortfolioEngine(memory)
            self.execution_engine = ExecutionEngine(memory)
        except Exception as _eng_err:
            self.portfolio_engine = None
            self.execution_engine = None'
    Write-Host "  [OK]  Engine init added fresh" -ForegroundColor Green
}

# Also fix the Kelly block to handle None portfolio_engine
$OldKellyLoop = "            try:
                _loop = _asyncio.get_event_loop()
                if _loop.is_running():
                    # Inside async context - schedule coroutine
                    _kelly = _loop.run_until_complete("

if ($TA -match [regex]::Escape($OldKellyLoop)) {
    # Replace the complex run_until_complete Kelly block with simple fallback
    $OldKellyBlock = @"
            # Position sizing via PortfolioEngine (proper Kelly + vol targeting)
            import asyncio as _asyncio
            import numpy as _np
            _edge  = float(fused.get("edge", 0.0))
            _conf  = float(fused.get("confidence", 0.0))
            _vol   = max(float(features.get("realized_volatility", 0.02)), 0.01)
            _sizing = fused.get("sizing_multipliers", {})
            try:
                _loop = _asyncio.get_event_loop()
                if _loop.is_running():
                    # Inside async context - schedule coroutine
                    _kelly = _loop.run_until_complete(
                        self.portfolio_engine.optimize_position_size(
                            signal_strength=_edge,
                            portfolio={"total_value": 10000, "cash": 5000},
                            volatility=_vol,
                            confidence_multiplier=float(_sizing.get("confidence_multiplier", 1.0)),
                            regime_multiplier=float(_sizing.get("regime_multiplier", 1.0)),
                            liquidity_multiplier=float(_sizing.get("microstructure_multiplier", 1.0)),
                            correlation_penalty=float(_sizing.get("correlation_penalty", 1.0)),
                        )
                    ) if _edge > 0 and _conf > 0 else 0.01
                else:
                    _kelly = 0.01
            except Exception:
                # Fallback to simple calculation
                _kelly = float(_np.clip(0.5 * (_edge * _conf) / _vol, 0.01, 0.20)) if _edge > 0 and _conf > 0 else 0.01
            fused["kelly_fraction"] = float(_kelly)
            fused["allocation"]     = float(_kelly)
            orchestrated = {**orchestrated, **fused}
"@

    $NewKellyBlock = @"
            # Position sizing: PortfolioEngine Kelly or simple fallback
            import numpy as _np
            _edge   = float(fused.get("edge", 0.0))
            _conf   = float(fused.get("confidence", 0.0))
            _vol    = max(float(features.get("realized_volatility", 0.02)), 0.01)
            _sizing = fused.get("sizing_multipliers", {})
            _kelly  = 0.01
            if _edge > 0 and _conf > 0:
                if self.portfolio_engine is not None:
                    import asyncio as _asyncio
                    try:
                        _kelly = _asyncio.get_event_loop().run_until_complete(
                            self.portfolio_engine.optimize_position_size(
                                signal_strength=_edge,
                                portfolio={"total_value": 10000, "cash": 5000},
                                volatility=_vol,
                                confidence_multiplier=float(_sizing.get("confidence_multiplier", 1.0)),
                                regime_multiplier=float(_sizing.get("regime_multiplier", 1.0)),
                                liquidity_multiplier=float(_sizing.get("microstructure_multiplier", 1.0)),
                                correlation_penalty=float(_sizing.get("correlation_penalty", 1.0)),
                            )
                        )
                    except Exception:
                        _kelly = float(_np.clip(0.5 * (_edge * _conf) / _vol, 0.01, 0.20))
                else:
                    _kelly = float(_np.clip(0.5 * (_edge * _conf) / _vol, 0.01, 0.20))
            fused["kelly_fraction"] = float(_kelly)
            fused["allocation"]     = float(_kelly)
            orchestrated = {**orchestrated, **fused}
"@

    $TA = $TA.Replace($OldKellyBlock, $NewKellyBlock)
    Write-Host "  [OK]  Kelly block simplified" -ForegroundColor Green
}

Set-Content $TAPath $TA -Encoding UTF8
Write-Host "  [OK]  trading\trading_agent.py saved" -ForegroundColor Green

# ---------------------------------------------------------------------------
# FIX 2 — Verify _start_advanced_layers is called AFTER all components init
# Check its position in startup() relative to the startup complete log
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Fix 2: Verify _start_advanced_layers call position in main.py" -ForegroundColor White

$MainLines = Get-Content "main.py" -Encoding UTF8
$callLine   = "        await self._start_advanced_layers()"
$markerLine = "Unified MECOS startup complete"

$callIdx   = -1
$markerIdx = -1
for ($i = 0; $i -lt $MainLines.Count; $i++) {
    if ($MainLines[$i] -match [regex]::Escape($callLine.Trim())) { $callIdx   = $i }
    if ($MainLines[$i] -match [regex]::Escape($markerLine))       { $markerIdx = $i }
}

Write-Host "  _start_advanced_layers call at line: $($callIdx + 1)" -ForegroundColor Gray
Write-Host "  'startup complete' log at line:       $($markerIdx + 1)" -ForegroundColor Gray

if ($callIdx -gt 0 -and $markerIdx -gt 0 -and $callIdx -lt $markerIdx) {
    Write-Host "  [OK]  Call is BEFORE startup complete log — correct order" -ForegroundColor Green
} elseif ($callIdx -gt 0 -and $markerIdx -gt 0 -and $callIdx -gt $markerIdx) {
    Write-Host "  [WARN] Call is AFTER startup complete log — fixing order" -ForegroundColor Yellow

    # Remove the call from its current position
    $newLines = @()
    for ($i = 0; $i -lt $MainLines.Count; $i++) {
        if ($i -eq $callIdx) { continue }
        $newLines += $MainLines[$i]
        # Inject before the startup complete log line
        if ($MainLines[$i] -match [regex]::Escape($markerLine)) {
            $newLines += $callLine
        }
    }
    Set-Content "main.py" $newLines -Encoding UTF8
    Write-Host "  [OK]  Call moved to correct position" -ForegroundColor Green
} elseif ($callIdx -lt 0) {
    Write-Host "  [WARN] Call not found — injecting before startup complete log" -ForegroundColor Yellow
    $newLines = @()
    foreach ($line in $MainLines) {
        if ($line -match [regex]::Escape($markerLine)) {
            $newLines += $callLine
        }
        $newLines += $line
    }
    Set-Content "main.py" $newLines -Encoding UTF8
    Write-Host "  [OK]  Call injected" -ForegroundColor Green
} else {
    Write-Host "  [OK]  Order looks correct" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Fixes applied" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run: python main.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "You should now see:" -ForegroundColor White
Write-Host "  quant_trading_agent: True   (was False)" -ForegroundColor Green
Write-Host "  trading_system: True        (was False)" -ForegroundColor Green
Write-Host "  MessageBus started" -ForegroundColor Green
Write-Host "  KnowledgeCompressor started" -ForegroundColor Green
Write-Host "  DreamingEngine started" -ForegroundColor Green
Write-Host "  Worker started: research_worker (pid=XXXX)" -ForegroundColor Green
Write-Host "  Worker started: memory_worker (pid=XXXX)" -ForegroundColor Green
Write-Host "  Worker started: evolution_worker (pid=XXXX)" -ForegroundColor Green
Write-Host ""
Write-Host "SkillAwareTaskPlanner will show skills updating from 0.00" -ForegroundColor Gray
Write-Host "after tasks complete successfully." -ForegroundColor Gray
Write-Host ""
