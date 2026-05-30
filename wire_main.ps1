# wire_main.ps1
# Wires advanced layers into main.py
# Run from MECOS folder: .\wire_main.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Wiring advanced layers into main.py..." -ForegroundColor Cyan

$MainPath = "main.py"
Copy-Item $MainPath "$MainPath.bak2" -Force
Write-Host "  [BAK] main.py.bak2" -ForegroundColor Yellow

$lines = Get-Content $MainPath -Encoding UTF8

# ---------------------------------------------------------------------------
# Step 1: Add imports after "from web_perception import WebPerception"
# ---------------------------------------------------------------------------
$importLine = "from web_perception import WebPerception"
$newImports = @(
    "",
    "# --- Advanced Layer Imports ---",
    "try:",
    "    from runtime.message_bus import MessageBus, get_bus",
    "    from runtime.process_manager import ProcessManager, WorkerSpec",
    "    from knowledge_compressor import KnowledgeCompressor",
    "    from workers.research_worker import run_research_worker",
    "    from workers.memory_worker import run_memory_worker",
    "    from workers.evolution_worker import run_evolution_worker",
    "    _ADVANCED_LAYERS = True",
    "except ImportError as _adv_err:",
    "    _ADVANCED_LAYERS = False"
)

$alreadyHasImports = $lines | Where-Object { $_ -match "from runtime.message_bus import" }
if (-not $alreadyHasImports) {
    $newLines = @()
    foreach ($line in $lines) {
        $newLines += $line
        if ($line -match [regex]::Escape($importLine)) {
            $newLines += $newImports
        }
    }
    $lines = $newLines
    Write-Host "  [OK]  Imports added" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] Imports already present" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 2: Add new instance variables to __init__
# after: self._runtime_cognition_task: Optional[asyncio.Task] = None
# ---------------------------------------------------------------------------
$initMarker = "self._runtime_cognition_task: Optional[asyncio.Task] = None"
$newInitVars = @(
    "        # --- Advanced layer instances ---",
    "        self.message_bus = None",
    "        self.process_manager = None",
    "        self.knowledge_compressor = None",
    "        self._compressor_task: Optional[asyncio.Task] = None",
    "        self._dreaming_task: Optional[asyncio.Task] = None"
)

$alreadyHasInit = $lines | Where-Object { $_ -match "self.message_bus = None" }
if (-not $alreadyHasInit) {
    $newLines = @()
    foreach ($line in $lines) {
        $newLines += $line
        if ($line -match [regex]::Escape($initMarker)) {
            $newLines += $newInitVars
        }
    }
    $lines = $newLines
    Write-Host "  [OK]  Instance variables added" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] Instance variables already present" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 3: Add helper methods before "async def shutdown"
# ---------------------------------------------------------------------------
$shutdownMarker = "    async def shutdown(self):"
$helperMethods = @(
    "    # --- Advanced layer helpers ---",
    "    async def _compression_loop(self):",
    "        while True:",
    "            try:",
    "                await asyncio.sleep(300)",
    "                if self.knowledge_compressor:",
    "                    await self.knowledge_compressor.compress_cycle()",
    "            except asyncio.CancelledError:",
    "                break",
    "            except Exception as _ce:",
    "                logger.error(f'Compression loop error: {_ce}')",
    "",
    "    async def _dreaming_loop(self, dreaming_engine):",
    "        while True:",
    "            try:",
    "                await asyncio.sleep(600)",
    "                goal = await dreaming_engine.generate_self_goal()",
    "                if goal:",
    "                    orchestrator = self.components.get('runtime_orchestrator')",
    "                    if orchestrator:",
    "                        await orchestrator.run_goal(goal)",
    "            except asyncio.CancelledError:",
    "                break",
    "            except Exception as _de:",
    "                logger.error(f'Dreaming loop error: {_de}')",
    "",
    "    def _on_research_result(self, worker_id: str, payload):",
    "        topic = payload.get('topic', 'unknown')",
    "        logger.debug(f'[ProcessManager] Research result from {worker_id}: {topic}')",
    "",
    "    async def _start_advanced_layers(self):",
    "        if not _ADVANCED_LAYERS:",
    "            logger.warning('Advanced layers not available - check imports')",
    "            return",
    "        try:",
    "            self.message_bus = MessageBus()",
    "            await self.message_bus.start_dispatch()",
    "            logger.info('MessageBus started')",
    "        except Exception as _e:",
    "            logger.warning(f'MessageBus failed: {_e}')",
    "        try:",
    "            kg  = self.components.get('runtime_knowledge_graph')",
    "            llm = self.components.get('reasoning')",
    "            if self.memory and kg:",
    "                self.knowledge_compressor = KnowledgeCompressor(",
    "                    memory=self.memory, knowledge_graph=kg, llm=llm",
    "                )",
    "                self._compressor_task = asyncio.create_task(self._compression_loop())",
    "                logger.info('KnowledgeCompressor started')",
    "        except Exception as _e:",
    "            logger.warning(f'KnowledgeCompressor failed: {_e}')",
    "        try:",
    "            from dreaming_engine import DreamingEngine",
    "            dreaming = DreamingEngine(self.memory)",
    "            self._dreaming_task = asyncio.create_task(self._dreaming_loop(dreaming))",
    "            logger.info('DreamingEngine started')",
    "        except Exception as _e:",
    "            logger.warning(f'DreamingEngine failed: {_e}')",
    "        try:",
    "            self.process_manager = ProcessManager()",
    "            self.process_manager.register(WorkerSpec(",
    "                worker_id='research_worker',",
    "                target_fn=run_research_worker,",
    "                cycle_interval=45.0,",
    "                max_restarts=10,",
    "            ))",
    "            self.process_manager.register(WorkerSpec(",
    "                worker_id='memory_worker',",
    "                target_fn=run_memory_worker,",
    "                cycle_interval=120.0,",
    "                max_restarts=5,",
    "            ))",
    "            self.process_manager.register(WorkerSpec(",
    "                worker_id='evolution_worker',",
    "                target_fn=run_evolution_worker,",
    "                cycle_interval=180.0,",
    "                max_restarts=5,",
    "            ))",
    "            self.process_manager.register_result_handler(",
    "                'research_result', self._on_research_result",
    "            )",
    "            self.process_manager.start_all()",
    "            asyncio.create_task(self.process_manager.monitor_loop())",
    "            logger.info('Distributed worker processes started')",
    "        except Exception as _e:",
    "            logger.warning(f'ProcessManager failed: {_e}')",
    ""
)

$alreadyHasHelpers = $lines | Where-Object { $_ -match "_compression_loop" }
if (-not $alreadyHasHelpers) {
    $newLines = @()
    $inserted = $false
    foreach ($line in $lines) {
        if (-not $inserted -and $line -match "    async def shutdown\(self\):") {
            $newLines += $helperMethods
            $inserted = $true
        }
        $newLines += $line
    }
    $lines = $newLines
    Write-Host "  [OK]  Helper methods added" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] Helper methods already present" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 4: Call _start_advanced_layers at end of startup()
# Find "Unified MECOS startup complete" log line and inject call before it
# ---------------------------------------------------------------------------
$startupMarker = "Unified MECOS startup complete"
$startupCall   = "        await self._start_advanced_layers()"

$alreadyHasCall = $lines | Where-Object { $_ -match "_start_advanced_layers" }
if (-not $alreadyHasCall) {
    $newLines = @()
    foreach ($line in $lines) {
        if ($line -match [regex]::Escape($startupMarker)) {
            $newLines += $startupCall
        }
        $newLines += $line
    }
    $lines = $newLines
    Write-Host "  [OK]  _start_advanced_layers() call injected into startup()" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] startup call already present" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 5: Write final file
# ---------------------------------------------------------------------------
Set-Content $MainPath -Value $lines -Encoding UTF8
Write-Host ""
Write-Host "  [OK]  main.py updated" -ForegroundColor Green
Write-Host ""
Write-Host "Run: python main.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "Look for these lines on startup:" -ForegroundColor White
Write-Host "  MessageBus started" -ForegroundColor Gray
Write-Host "  KnowledgeCompressor started" -ForegroundColor Gray
Write-Host "  DreamingEngine started" -ForegroundColor Gray
Write-Host "  Worker started: research_worker (pid=XXXX)" -ForegroundColor Gray
Write-Host "  Worker started: memory_worker (pid=XXXX)" -ForegroundColor Gray
Write-Host "  Worker started: evolution_worker (pid=XXXX)" -ForegroundColor Gray
Write-Host ""
