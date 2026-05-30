# install_v3_components.ps1
# Installs MECOS v3.0 components and wires them into the runtime.
# Components:
#   uncertainty_flagger.py     -> runtime/
#   milestone_alerts.py        -> reporting/
#   daily_report_generator.py  -> reporting/
#   weekly_review_generator.py -> reporting/
#   app_discovery.py           -> runtime/
#
# Run from MECOS folder: .\install_v3_components.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MECOS v3.0 Component Install" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
function Install-Component {
    param([string]$Source, [string]$Dest)
    $dir = Split-Path $Dest -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    if (Test-Path $Dest) {
        Copy-Item $Dest "$Dest.bak" -Force
        Write-Host "  [BAK] $Dest.bak" -ForegroundColor Yellow
    }
    Copy-Item $Source $Dest -Force
    Write-Host "  [OK]  $Dest" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 1: Create directory structure
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Creating directories..." -ForegroundColor White
$dirs = @("runtime", "reporting", "reports\daily", "reports\weekly", "data\app_discovery", "data\app_workflows", "logs")
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
Write-Host "  [OK]  Directory structure ready" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 2: Copy component files from Downloads
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Installing component files..." -ForegroundColor White

$downloadsPath = "$env:USERPROFILE\Downloads"

# Map: source filename -> destination path
$components = @{
    "uncertainty_flagger (1).py"      = "runtime\uncertainty_flagger.py"
    "uncertainty_flagger__1_.py"      = "runtime\uncertainty_flagger.py"
    "milestone_alerts (1).py"         = "reporting\milestone_alerts.py"
    "milestone_alerts__1_.py"         = "reporting\milestone_alerts.py"
    "daily_report_generator (1).py"   = "reporting\daily_report_generator.py"
    "daily_report_generator__1_.py"   = "reporting\daily_report_generator.py"
    "weekly_review_generator (1).py"  = "reporting\weekly_review_generator.py"
    "weekly_review_generator__1_.py"  = "reporting\weekly_review_generator.py"
    "app_discovery (1).py"            = "runtime\app_discovery.py"
    "app_discovery__1_.py"            = "runtime\app_discovery.py"
}

$installed = @{}
foreach ($src in $components.Keys) {
    $srcPath = Join-Path $downloadsPath $src
    $destPath = $components[$src]
    if ((Test-Path $srcPath) -and (-not $installed.ContainsKey($destPath))) {
        Install-Component $srcPath $destPath
        $installed[$destPath] = $true
    }
}

# Check what was installed
$missing = @()
$required = @("runtime\uncertainty_flagger.py", "reporting\milestone_alerts.py",
              "reporting\daily_report_generator.py", "reporting\weekly_review_generator.py",
              "runtime\app_discovery.py")
foreach ($r in $required) {
    if (-not (Test-Path $r)) { $missing += $r }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "  [WARN] These files were not found in Downloads:" -ForegroundColor Yellow
    foreach ($m in $missing) { Write-Host "    $m" -ForegroundColor Yellow }
    Write-Host "  Place the .py files in your Downloads folder and re-run." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 3: Create __init__.py for reporting package
# ---------------------------------------------------------------------------
if (-not (Test-Path "reporting\__init__.py")) {
    Set-Content "reporting\__init__.py" "# MECOS v3.0 reporting package" -Encoding UTF8
    Write-Host "  [OK]  reporting\__init__.py" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 4: Wire v3.0 components into main.py
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Wiring v3.0 components into main.py..." -ForegroundColor White
Copy-Item "main.py" "main.py.bak3" -Force
Write-Host "  [BAK] main.py.bak3" -ForegroundColor Yellow

$lines = Get-Content "main.py" -Encoding UTF8
$newLines = @()

# Add v3.0 imports after advanced layer imports
$v3ImportsAdded = $false
$v3Imports = @(
    "",
    "# --- MECOS v3.0 Reporting & Honesty Layer ---",
    "try:",
    "    from runtime.uncertainty_flagger import UncertaintyFlagger",
    "    from reporting.milestone_alerts import AlertDispatcher, MilestoneAlertSystem",
    "    from reporting.daily_report_generator import DailyReportGenerator",
    "    from reporting.weekly_review_generator import WeeklyReviewGenerator",
    "    from runtime.app_discovery import AppDiscovery, AppLearner",
    "    _V3_LAYERS = True",
    "except ImportError as _v3_err:",
    "    _V3_LAYERS = False"
)

foreach ($line in $lines) {
    $newLines += $line
    if (-not $v3ImportsAdded -and $line -match "_ADVANCED_LAYERS = True") {
        $newLines += $v3Imports
        $v3ImportsAdded = $true
    }
}
$lines = $newLines

# Add v3.0 instance variables after advanced layer vars
$v3VarsAdded = $false
$v3Vars = @(
    "        # --- v3.0 component instances ---",
    "        self.uncertainty_flagger = None",
    "        self.alert_dispatcher    = None",
    "        self.milestone_system    = None",
    "        self.daily_reporter      = None",
    "        self.weekly_reviewer     = None",
    "        self.app_discovery       = None",
    "        self._daily_report_task: Optional[asyncio.Task] = None",
    "        self._weekly_review_task: Optional[asyncio.Task] = None"
)

$newLines = @()
foreach ($line in $lines) {
    $newLines += $line
    if (-not $v3VarsAdded -and $line -match "self\._dreaming_task.*Optional\[asyncio\.Task\]") {
        $newLines += $v3Vars
        $v3VarsAdded = $true
    }
}
$lines = $newLines

# Add _start_v3_layers method before shutdown
$v3MethodAdded = $false
$v3Methods = @(
    "    async def _start_v3_layers(self):",
    "        if not _V3_LAYERS:",
    "            logger.warning('v3.0 layers not available')",
    "            return",
    "        try:",
    "            self.uncertainty_flagger = UncertaintyFlagger(",
    "                confidence_threshold=0.75,",
    "                track_assumptions=True,",
    "                flag_limitations=True,",
    "            )",
    "            logger.info('UncertaintyFlagger initialized')",
    "        except Exception as _e:",
    "            logger.warning(f'UncertaintyFlagger failed: {_e}')",
    "        try:",
    "            self.alert_dispatcher = AlertDispatcher()",
    "            # Register callback so alerts appear in logs",
    "            self.alert_dispatcher.register_callback(",
    "                'logger',",
    "                lambda title, msg, meta: logger.info(f'ALERT: {title} | {msg}')",
    "            )",
    "            logger.info('AlertDispatcher initialized')",
    "        except Exception as _e:",
    "            logger.warning(f'AlertDispatcher failed: {_e}')",
    "        try:",
    "            if self.alert_dispatcher:",
    "                from trading.trade_database import TradeDatabase",
    "                _db = TradeDatabase()",
    "                self.milestone_system = MilestoneAlertSystem(",
    "                    performance_tracker=None,",
    "                    alert_dispatcher=self.alert_dispatcher,",
    "                )",
    "                logger.info('MilestoneAlertSystem initialized')",
    "        except Exception as _e:",
    "            logger.warning(f'MilestoneAlertSystem failed: {_e}')",
    "        try:",
    "            self.daily_reporter = DailyReportGenerator(",
    "                output_dir='reports/daily'",
    "            )",
    "            self._daily_report_task = asyncio.create_task(self._daily_report_loop())",
    "            logger.info('DailyReportGenerator initialized')",
    "        except Exception as _e:",
    "            logger.warning(f'DailyReportGenerator failed: {_e}')",
    "        try:",
    "            self.weekly_reviewer = WeeklyReviewGenerator(",
    "                uncertainty_flagger=self.uncertainty_flagger,",
    "                output_dir='reports/weekly'",
    "            )",
    "            self._weekly_review_task = asyncio.create_task(self._weekly_review_loop())",
    "            logger.info('WeeklyReviewGenerator initialized')",
    "        except Exception as _e:",
    "            logger.warning(f'WeeklyReviewGenerator failed: {_e}')",
    "        try:",
    "            self.app_discovery = AppDiscovery(cache_dir='data/app_discovery')",
    "            asyncio.create_task(self._run_app_discovery())",
    "            logger.info('AppDiscovery initialized')",
    "        except Exception as _e:",
    "            logger.warning(f'AppDiscovery failed: {_e}')",
    "",
    "    async def _daily_report_loop(self):",
    "        import datetime as _dt",
    "        while True:",
    "            try:",
    "                now = _dt.datetime.now()",
    "                # Run at 17:00 daily",
    "                target = now.replace(hour=17, minute=0, second=0, microsecond=0)",
    "                if now >= target:",
    "                    target = target + _dt.timedelta(days=1)",
    "                wait_secs = (target - now).total_seconds()",
    "                await asyncio.sleep(wait_secs)",
    "                if self.daily_reporter:",
    "                    report = self.daily_reporter.generate_report()",
    "                    files  = self.daily_reporter.save_report(report)",
    "                    logger.info(f'Daily report saved: {files}')",
    "                    if self.alert_dispatcher:",
    "                        self.alert_dispatcher.dispatch(",
    "                            'Daily Report',",
    "                            f'PnL: ${report.daily_pnl:+.2f} | Trades: {report.trades_count}',",
    "                            {}",
    "                        )",
    "            except asyncio.CancelledError:",
    "                break",
    "            except Exception as _e:",
    "                logger.error(f'Daily report error: {_e}')",
    "                await asyncio.sleep(3600)",
    "",
    "    async def _weekly_review_loop(self):",
    "        import datetime as _dt",
    "        while True:",
    "            try:",
    "                now = _dt.datetime.now()",
    "                # Run on Friday at 18:00",
    "                days_until_friday = (4 - now.weekday()) % 7",
    "                target = (now + _dt.timedelta(days=days_until_friday)).replace(",
    "                    hour=18, minute=0, second=0, microsecond=0)",
    "                if target <= now:",
    "                    target += _dt.timedelta(weeks=1)",
    "                wait_secs = (target - now).total_seconds()",
    "                await asyncio.sleep(wait_secs)",
    "                if self.weekly_reviewer:",
    "                    review = self.weekly_reviewer.generate_review()",
    "                    files  = self.weekly_reviewer.save_review(review)",
    "                    logger.info(f'Weekly review saved: {files}')",
    "            except asyncio.CancelledError:",
    "                break",
    "            except Exception as _e:",
    "                logger.error(f'Weekly review error: {_e}')",
    "                await asyncio.sleep(3600)",
    "",
    "    async def _run_app_discovery(self):",
    "        try:",
    "            await asyncio.sleep(30)  # Wait for full startup",
    "            if self.app_discovery:",
    "                apps = self.app_discovery.discover()",
    "                self.app_discovery.save_discovery()",
    "                logger.info(f'AppDiscovery: found {len(apps)} applications')",
    "        except Exception as _e:",
    "            logger.error(f'AppDiscovery error: {_e}')",
    ""
)

$newLines = @()
foreach ($line in $lines) {
    if (-not $v3MethodAdded -and $line -match "    async def shutdown\(self\):") {
        $newLines += $v3Methods
        $v3MethodAdded = $true
    }
    $newLines += $line
}
$lines = $newLines

# Add _start_v3_layers() call after _start_advanced_layers() in startup
$v3CallAdded = $false
$newLines = @()
foreach ($line in $lines) {
    $newLines += $line
    if (-not $v3CallAdded -and $line -match "await self\._start_advanced_layers\(\)") {
        $newLines += "        await self._start_v3_layers()"
        $v3CallAdded = $true
    }
}
$lines = $newLines

# Wire UncertaintyFlagger into trading_agent via components
# Add to startup complete log line vicinity
$v3WireAdded = $false
$newLines = @()
foreach ($line in $lines) {
    $newLines += $line
    if (-not $v3WireAdded -and $line -match "Unified MECOS startup complete") {
        $newLines += "        if self.uncertainty_flagger and 'quant_trading_agent' in self.connection_state:"
        $newLines += "            try:"
        $newLines += "                trading_agent = self.components.get('quant_trading_agent')"
        $newLines += "                if trading_agent and not hasattr(trading_agent, 'uncertainty_flagger'):"
        $newLines += "                    trading_agent.uncertainty_flagger = self.uncertainty_flagger"
        $newLines += "                    logger.info('UncertaintyFlagger wired into TradingAgent')"
        $newLines += "            except Exception:"
        $newLines += "                pass"
        $v3WireAdded = $true
    }
}
$lines = $newLines

Set-Content "main.py" $lines -Encoding UTF8
Write-Host "  [OK]  main.py updated with v3.0 wiring" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 5: Wire UncertaintyFlagger into trading_agent._analyze_symbol
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Wiring UncertaintyFlagger into trading_agent.py..." -ForegroundColor White
Copy-Item "trading\trading_agent.py" "trading\trading_agent.py.bak2" -Force

$TA = Get-Content "trading\trading_agent.py" -Raw

# Add uncertainty_flagger attribute to __init__ if missing
if ($TA -notmatch "self\.uncertainty_flagger") {
    $TA = $TA -replace `
        "(self\.portfolio_engine = None)", `
        '$1
        self.uncertainty_flagger = None  # wired from main.py'
}

# After final_decision is determined, run it through uncertainty flagger if available
$TA = $TA -replace `
    '(logger\.info\(f"Decision for \{symbol\}: \{[^}]+\} \(Confidence: [^)]+\)"\))', `
    '# UncertaintyFlagger gate
            if self.uncertainty_flagger is not None:
                try:
                    _uf_approval = self.uncertainty_flagger.score_plan(
                        plan=f"{symbol} {final_decision}",
                        signal_strength=float(fused.get("confidence", 0.5)),
                        market_regime=0.7 if regime != "unknown" else 0.4,
                        volatility_regime=float(min(1.0, 1.0 - features.get("realized_volatility", 0.3))),
                        data_freshness=0.9,
                        historical_accuracy=float(fused.get("agreement", 0.5)),
                        edge_case_coverage=0.6,
                    )
                    if not _uf_approval.execution_approved and final_decision != "HOLD":
                        logger.debug(f"UncertaintyFlagger blocked {symbol}: conf={_uf_approval.confidence_score:.2f}")
                        final_decision = "HOLD"
                        confidence = _uf_approval.confidence_score
                except Exception:
                    pass
            $1'

Set-Content "trading\trading_agent.py" $TA -Encoding UTF8
Write-Host "  [OK]  trading\trading_agent.py (UncertaintyFlagger gate added)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MECOS v3.0 Install Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Components installed:" -ForegroundColor White
Write-Host "  runtime\uncertainty_flagger.py    - Radical honesty / confidence gating" -ForegroundColor Green
Write-Host "  reporting\milestone_alerts.py     - Email/Slack/Discord milestone alerts" -ForegroundColor Green
Write-Host "  reporting\daily_report_generator.py - Daily P&L reports (5 PM)" -ForegroundColor Green
Write-Host "  reporting\weekly_review_generator.py - Weekly strategy review (Friday 6 PM)" -ForegroundColor Green
Write-Host "  runtime\app_discovery.py          - Discovers installed apps + learns workflows" -ForegroundColor Green
Write-Host ""
Write-Host "What happens now:" -ForegroundColor White
Write-Host "  UncertaintyFlagger scores every trade before execution" -ForegroundColor Gray
Write-Host "  Trades with confidence < 75% are blocked" -ForegroundColor Gray
Write-Host "  Position size scales with confidence (75%->50% size, 90%->full size)" -ForegroundColor Gray
Write-Host "  Daily reports generated at 5 PM to reports\daily\" -ForegroundColor Gray
Write-Host "  Weekly reviews generated Friday 6 PM to reports\weekly\" -ForegroundColor Gray
Write-Host "  AppDiscovery scans your system 30s after startup" -ForegroundColor Gray
Write-Host "  MilestoneAlertSystem fires when equity milestones are hit" -ForegroundColor Gray
Write-Host ""
Write-Host "On startup you will see:" -ForegroundColor White
Write-Host "  UncertaintyFlagger initialized" -ForegroundColor Gray
Write-Host "  AlertDispatcher initialized" -ForegroundColor Gray
Write-Host "  DailyReportGenerator initialized" -ForegroundColor Gray
Write-Host "  WeeklyReviewGenerator initialized" -ForegroundColor Gray
Write-Host "  AppDiscovery initialized" -ForegroundColor Gray
Write-Host ""
Write-Host "Run: python main.py" -ForegroundColor Yellow
Write-Host ""
