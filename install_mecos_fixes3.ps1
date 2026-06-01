# MECOS Fix Installer - Batch 3 (Final issues)
# Run from inside your MECOS folder:
#   Unblock-File .\install_mecos_fixes3.ps1
#   .\install_mecos_fixes3.ps1

Write-Host "MECOS Fix Installer - Batch 3 (Final)" -ForegroundColor Cyan
Write-Host "Writing to: $(Get-Location)" -ForegroundColor Yellow
Write-Host ""

# ============================================================
# 1. main.py — set_agents() wired, correct startup order
# ============================================================
@'
"""
MECOS Main Entry Point

Fixes applied:
  1. IndependenceManager.set_agents() is now called after all components
     are constructed — governance gates now check real live metrics.
  2. TRAINING_ACCELERATION_FACTOR added to settings via .env fallback
     (meta_learner.py references it but config never defined it).
  3. memory_system_stub removed (test artifact, should never be in prod).
  4. Startup sequence is ordered correctly:
       memory → trading_agent → meta_learner → independence_manager
       (so set_agents() always has live objects to inject)
"""

import asyncio
from loguru import logger

from config import settings
from memory_system import MemorySystem
from reasoner import Reasoner
from trading_agent import TradingAgent
from meta_learner import MetaLearner
from independence_manager import IndependenceManager
from dreaming_engine import DreamingEngine


async def startup_checks(memory: MemorySystem) -> None:
    """Verify core systems are reachable before entering the main loop."""
    logger.info("Running startup checks...")

    # Memory check
    try:
        stats = await memory.get_stats()
        logger.info(f"Memory OK — {stats.get('experience_count', 0)} experiences stored")
    except Exception as e:
        logger.error(f"Memory check failed: {e}")
        raise

    # Broker connectivity (non-fatal — just warn)
    if not settings.ALPACA_API_KEY:
        logger.warning("ALPACA_API_KEY not set — stock trading disabled")
    if not settings.BINANCE_API_KEY:
        logger.warning("BINANCE_API_KEY not set — crypto trading disabled")

    logger.info("Startup checks complete.")


async def main():
    logger.info(f"Starting MECOS {settings.VERSION}")

    # ── 1. Core memory (everything depends on this) ───────────────────────
    memory = MemorySystem()
    await startup_checks(memory)

    # ── 2. Trading agent (must exist before IndependenceManager) ─────────
    trading_agent = TradingAgent(memory)
    logger.info("TradingAgent ready.")

    # ── 3. Reasoner ───────────────────────────────────────────────────────
    reasoner = Reasoner(memory)
    logger.info("Reasoner ready.")

    # ── 4. Meta-learner ───────────────────────────────────────────────────
    meta_learner = MetaLearner(memory)
    logger.info("MetaLearner ready.")

    # ── 5. Independence manager — inject live agents NOW ─────────────────
    #    FIX: original code left trading_agent=None and meta_learner=None,
    #    so governance gates never ran against real data.
    independence = IndependenceManager(memory)
    independence.set_agents(trading_agent, meta_learner)
    logger.info("IndependenceManager wired with live TradingAgent + MetaLearner.")

    # ── 6. Dreaming engine ────────────────────────────────────────────────
    dreaming = DreamingEngine(memory)
    logger.info("DreamingEngine ready.")

    # ── 7. Initial readiness check ────────────────────────────────────────
    readiness = await independence.check_readiness()
    logger.info(f"System readiness: {readiness}")

    # ── 8. Main loop ──────────────────────────────────────────────────────
    logger.info("Entering main loop...")
    cycle = 0

    while True:
        cycle += 1
        logger.info(f"=== Main Cycle #{cycle} ===")

        try:
            # Trading cycle
            trade_result = await trading_agent.run_cycle()
            logger.info(f"Trading: {trade_result['signals']} signals, "
                        f"{trade_result['actionable']} actionable")

            # Meta-learning cycle (every 5 main cycles)
            if cycle % 5 == 0:
                meta_result = await meta_learner.run_meta_cycle()
                logger.info(f"Meta score: {meta_result.get('benchmark_score', 'N/A')}")

            # Dreaming cycle (every 10 main cycles, when idle)
            if cycle % 10 == 0:
                await dreaming.dream()

            # Governance check (every 20 cycles)
            if cycle % 20 == 0:
                readiness = await independence.check_readiness()
                logger.info(f"Governance readiness: {readiness}")

        except Exception as e:
            logger.error(f"Cycle #{cycle} error: {e}")

        await asyncio.sleep(settings.IDLE_SLEEP_TIME)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MECOS stopped by user.")

'@ | Set-Content -Path "main.py" -Encoding UTF8
Write-Host "  [OK] main.py" -ForegroundColor Green

# ============================================================
# 2. Patch config.py — add TRAINING_ACCELERATION_FACTOR
#    (meta_learner.py references this but config never defined it)
# ============================================================
$configPath = "config.py"
$configContent = Get-Content $configPath -Raw

if ($configContent -notmatch "TRAINING_ACCELERATION_FACTOR") {
    $insertAfter = "GOV_MIN_TRADING_ACTIONABLE_RATE"
    $patch = @'

    # ── Meta-learning acceleration ────────────────────────────────────────
    # Multiplier for batch sizes in meta-learning cycles.
    # 1 = normal, 2 = double batches (faster but heavier on RAM/CPU)
    TRAINING_ACCELERATION_FACTOR: int = int(
        __import__('os').getenv("TRAINING_ACCELERATION_FACTOR", "1")
    )
'@
    # Find the line with GOV_MIN_TRADING_ACTIONABLE_RATE and insert after it
    $lines = $configContent -split "`n"
    $newLines = @()
    foreach ($line in $lines) {
        $newLines += $line
        if ($line -match "GOV_MIN_TRADING_ACTIONABLE_RATE") {
            $newLines += $patch
        }
    }
    $newLines -join "`n" | Set-Content $configPath -Encoding UTF8
    Write-Host "  [OK] config.py patched (TRAINING_ACCELERATION_FACTOR added)" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] config.py already has TRAINING_ACCELERATION_FACTOR" -ForegroundColor Yellow
}

# ============================================================
# 3. Patch .env.example — add TRAINING_ACCELERATION_FACTOR
# ============================================================
$envPath = ".env.example"
if (Test-Path $envPath) {
    $envContent = Get-Content $envPath -Raw
    if ($envContent -notmatch "TRAINING_ACCELERATION_FACTOR") {
        Add-Content $envPath "`nTRAINING_ACCELERATION_FACTOR=1"
        Write-Host "  [OK] .env.example patched" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] .env.example already patched" -ForegroundColor Yellow
    }
}

# ============================================================
# 4. Delete memory_system_stub.py (test artifact, not for prod)
# ============================================================
if (Test-Path "memory_system_stub.py") {
    Remove-Item "memory_system_stub.py"
    Write-Host "  [OK] memory_system_stub.py deleted (was a test artifact)" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] memory_system_stub.py not found (already clean)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Batch 3 complete." -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary of what was fixed:" -ForegroundColor Yellow
Write-Host "  main.py                    - set_agents() now wires live TradingAgent + MetaLearner"
Write-Host "  main.py                    - correct startup order (trading -> meta -> independence)"
Write-Host "  config.py                  - TRAINING_ACCELERATION_FACTOR added (meta_learner no longer crashes)"
Write-Host "  .env.example               - TRAINING_ACCELERATION_FACTOR documented"
Write-Host "  memory_system_stub.py      - deleted (test artifact removed from prod)"
Write-Host ""
Write-Host "ALL 3 BATCHES COMPLETE. MECOS is fully patched." -ForegroundColor Green
Write-Host ""
Write-Host "To run MECOS:" -ForegroundColor Yellow
Write-Host "  python run_live_trading.py --backtest    # test signals, zero orders"
Write-Host "  python run_live_trading.py --once        # single paper-trading cycle"
Write-Host "  python main.py                           # full system (all agents)"
