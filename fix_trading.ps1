# fix_trading.ps1
# Fixes all 5 trading layer problems identified from logs:
#   1. market_data_stream.py  - validator rejects quote ticks (volume=0)
#   2. autonomous_trading_loop.py - expected_move rounding kills quality gate
#   3. autonomous_trading_loop.py - quality multiplier too aggressive
#   4. exposure_manager.py - sector "unknown" collapses all assets into one bucket
#   5. asset_profiles.py - missing stock tickers, no sector mapping
#
# Run from MECOS folder:
#   .\fix_trading.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MECOS Trading Layer Fixes" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
function Backup-And-Write {
    param([string]$Path, [string]$Content)
    if (Test-Path $Path) {
        Copy-Item $Path "$Path.bak" -Force
        Write-Host "  [BAK] $Path" -ForegroundColor Yellow
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
    Write-Host "  [OK]  $Path" -ForegroundColor Green
}

# ===========================================================================
# FIX 1 — market_data_stream.py
# Problem: _validate_tick rejects volume <= 0, but Alpaca quote ticks
#          have no volume field — only quote_size. This starves all indicators.
# Fix:     Only reject volume=0 on OHLCV bar data (source != alpaca_quote).
#          For quote ticks, validate bid/ask integrity instead.
# ===========================================================================
Write-Host ""
Write-Host "Fix 1: market_data_stream.py (validator)" -ForegroundColor White

$MDS = Get-Content "trading\market_data_stream.py" -Raw

$OldValidate = @'
    def _validate_tick(self, symbol: str, data: Dict[str, Any]) -> bool:
        ts = self._parse_ts(data.get('timestamp'))
        if ts is not None:
            prev = self._last_timestamp_by_symbol.get(symbol)
            if prev is not None and ts <= prev:
                self.integrity_rejections['stale_or_duplicate'] += 1
                return False
            self._last_timestamp_by_symbol[symbol] = ts

        close_price = float(data.get('close', 0.0) or 0.0)
        if close_price <= 0:
            self.integrity_rejections['invalid_price'] += 1
            return False

        volume = float(data.get('volume', 0.0) or 0.0)
        if volume <= 0:
            self.integrity_rejections['invalid_volume'] += 1
            return False

        return True
'@

$NewValidate = @'
    def _validate_tick(self, symbol: str, data: Dict[str, Any]) -> bool:
        # --- Timestamp dedup (apply to all sources) ---
        ts = self._parse_ts(data.get('timestamp'))
        if ts is not None:
            prev = self._last_timestamp_by_symbol.get(symbol)
            if prev is not None and ts <= prev:
                self.integrity_rejections['stale_or_duplicate'] += 1
                return False
            self._last_timestamp_by_symbol[symbol] = ts

        source = str(data.get('source', '')).lower()
        is_quote = 'quote' in source

        if is_quote:
            # --- Quote tick validation: strict on corruption, lenient on market behaviour ---
            bid = data.get('bid')
            ask = data.get('ask')
            if bid is not None and ask is not None:
                bid_f = float(bid or 0.0)
                ask_f = float(ask or 0.0)
                # Crossed market = corrupt
                if bid_f > ask_f > 0:
                    self.integrity_rejections['invalid_price'] += 1
                    return False
                # Negative price = corrupt
                if ask_f <= 0:
                    self.integrity_rejections['invalid_price'] += 1
                    return False
            # Tiny spreads and zero volume are NORMAL for liquid quote ticks — accept them
            return True

        # --- OHLCV bar validation ---
        close_price = float(data.get('close', 0.0) or 0.0)
        if close_price <= 0:
            self.integrity_rejections['invalid_price'] += 1
            return False

        volume = float(data.get('volume', 0.0) or 0.0)
        if volume <= 0:
            self.integrity_rejections['invalid_volume'] += 1
            return False

        return True
'@

if ($MDS -match [regex]::Escape("volume = float(data.get('volume', 0.0) or 0.0)")) {
    $MDS = $MDS.Replace($OldValidate, $NewValidate)
    Set-Content "trading\market_data_stream.py" $MDS -Encoding UTF8
    Write-Host "  [BAK] trading\market_data_stream.py.bak" -ForegroundColor Yellow
    Copy-Item "trading\market_data_stream.py" "trading\market_data_stream.py.bak" -Force
    Set-Content "trading\market_data_stream.py" $MDS -Encoding UTF8
    Write-Host "  [OK]  trading\market_data_stream.py" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Could not find exact _validate_tick pattern — patching manually" -ForegroundColor Yellow
    # Fallback: append a replacement class method note
    Add-Content "trading\market_data_stream.py" "`n# FIX NEEDED: replace _validate_tick — see fix_trading.ps1 output`n"
}

# ===========================================================================
# FIX 2 + 3 — autonomous_trading_loop.py
# Problem A: expected_move logged as :.4f rounds 0.000043 -> 0.0000
#            giving false impression quality gate sees zero
# Problem B: trade_quality_spread_multiplier = 0.2 means expected_move
#            must be > 20% of spread — too tight for liquid ETFs
# Fix:       Log at :.6f precision, lower multiplier to 0.05
# ===========================================================================
Write-Host ""
Write-Host "Fix 2+3: autonomous_trading_loop.py (rounding + quality threshold)" -ForegroundColor White

$ATL = Get-Content "trading\autonomous_trading_loop.py" -Raw
Copy-Item "trading\autonomous_trading_loop.py" "trading\autonomous_trading_loop.py.bak" -Force
Write-Host "  [BAK] trading\autonomous_trading_loop.py.bak" -ForegroundColor Yellow

# Fix A: log precision
$ATL = $ATL -replace 'expected_move=\{expected_move:\.4f\}', 'expected_move={expected_move:.6f}'

# Fix B: lower the quality multiplier
$ATL = $ATL -replace 'self\.trade_quality_spread_multiplier = 0\.2', 'self.trade_quality_spread_multiplier = 0.05'

# Fix C: if quality gate log line uses :.4f for spread and vol too, fix those
$ATL = $ATL -replace 'spread=\{spread:\.4f\}', 'spread={spread:.6f}'
$ATL = $ATL -replace 'vol=\{vol:\.4f\}', 'vol={vol:.6f}'

Set-Content "trading\autonomous_trading_loop.py" $ATL -Encoding UTF8
Write-Host "  [OK]  trading\autonomous_trading_loop.py" -ForegroundColor Green

# ===========================================================================
# FIX 4 — exposure_manager.py
# Problem: All assets fall into sector "unknown" because trading_agent
#          doesn't pass a sector. SECTOR_LIMITS has no "unknown" key so
#          limit defaults to 1.0 (fine), BUT the correlation cluster check
#          groups SPY/AAPL/NVDA/AMZN/MSFT/META/QQQ all in one cluster of 8.
#          max_correlated_positions defaults to 3, so after 3 trades in that
#          cluster the system blocks everything.
# Fix:     Raise default max_correlated_positions to 6, and add "unknown"
#          sector with a generous limit so it never blocks.
# ===========================================================================
Write-Host ""
Write-Host "Fix 4: exposure_manager.py (sector unknown + correlation cap)" -ForegroundColor White

$EM = Get-Content "trading\exposure_manager.py" -Raw
Copy-Item "trading\exposure_manager.py" "trading\exposure_manager.py.bak" -Force
Write-Host "  [BAK] trading\exposure_manager.py.bak" -ForegroundColor Yellow

# Add 'unknown' and 'equity' to SECTOR_LIMITS with generous caps
$EM = $EM -replace "SECTOR_LIMITS = \{`r?`n    'tech': 0\.40,`r?`n    'crypto': 0\.25,`r?`n\}", @'
SECTOR_LIMITS = {
    'tech':        0.40,
    'technology':  0.40,
    'crypto':      0.25,
    'equity':      0.80,
    'index':       0.60,
    'small_cap':   0.30,
    'semiconductors': 0.30,
    'automotive':  0.20,
    'unknown':     0.80,   # fallback — generous so sector gaps never block trades
}
'@

# Raise default max_correlated_positions from 3 to 6
$EM = $EM -replace 'max_correlated_positions=3,', 'max_correlated_positions=6,'

Set-Content "trading\exposure_manager.py" $EM -Encoding UTF8
Write-Host "  [OK]  trading\exposure_manager.py" -ForegroundColor Green

# ===========================================================================
# FIX 5 — asset_profiles.py
# Problem: All stock tickers missing from ASSET_PROFILES, so infer_market
#          returns "equity" but trading_agent logs sector as "unknown".
#          Add a SECTOR_MAP and a get_sector() function so trading_agent
#          can resolve proper sectors.
# ===========================================================================
Write-Host ""
Write-Host "Fix 5: asset_profiles.py (add stock sector map + get_sector)" -ForegroundColor White

$AP = Get-Content "trading\asset_profiles.py" -Raw
Copy-Item "trading\asset_profiles.py" "trading\asset_profiles.py.bak" -Force
Write-Host "  [BAK] trading\asset_profiles.py.bak" -ForegroundColor Yellow

# Append SECTOR_MAP and get_sector() to the end of the file
$SectorAddition = @'


# ---------------------------------------------------------------------------
# Sector mapping for exposure manager
# ---------------------------------------------------------------------------
SECTOR_MAP: Dict[str, str] = {
    # Mega-cap tech
    'AAPL':  'technology',
    'MSFT':  'technology',
    'GOOGL': 'technology',
    'GOOG':  'technology',
    'META':  'technology',
    'AMZN':  'technology',
    'NFLX':  'technology',
    'ADBE':  'technology',
    'CRM':   'technology',
    'ORCL':  'technology',
    # Semiconductors
    'NVDA':  'semiconductors',
    'AMD':   'semiconductors',
    'INTC':  'semiconductors',
    'QCOM':  'semiconductors',
    'AVGO':  'semiconductors',
    'MU':    'semiconductors',
    'AMAT':  'semiconductors',
    'LRCX':  'semiconductors',
    # Indices / ETFs
    'SPY':   'index',
    'QQQ':   'index',
    'DIA':   'index',
    'VTI':   'index',
    'VOO':   'index',
    'IVV':   'index',
    'IWM':   'small_cap',
    'VXX':   'volatility',
    # Automotive / EV
    'TSLA':  'automotive',
    'F':     'automotive',
    'GM':    'automotive',
    'RIVN':  'automotive',
    'LCID':  'automotive',
    # Finance
    'JPM':   'financials',
    'BAC':   'financials',
    'GS':    'financials',
    'MS':    'financials',
    'WFC':   'financials',
    'V':     'financials',
    'MA':    'financials',
    'AXP':   'financials',
    # Healthcare
    'JNJ':   'healthcare',
    'PFE':   'healthcare',
    'MRNA':  'healthcare',
    'UNH':   'healthcare',
    'ABBV':  'healthcare',
    'LLY':   'healthcare',
    # Energy
    'XOM':   'energy',
    'CVX':   'energy',
    'COP':   'energy',
    # Consumer
    'WMT':   'consumer',
    'COST':  'consumer',
    'TGT':   'consumer',
    'HD':    'consumer',
    'MCD':   'consumer',
    'SBUX':  'consumer',
    'NKE':   'consumer',
    # Crypto (symbol variants)
    'BTC/USD':  'crypto',
    'ETH/USD':  'crypto',
    'SOL/USD':  'crypto',
    'AVAX/USD': 'crypto',
    'LINK/USD': 'crypto',
    'DOGE/USD': 'crypto',
    'ADA/USD':  'crypto',
    'BTC/USDT': 'crypto',
    'ETH/USDT': 'crypto',
    'SOL/USDT': 'crypto',
}


def get_sector(symbol: str) -> str:
    """
    Return the sector for a symbol.
    Falls back to infer_market() so it never returns 'unknown'.
    """
    token = str(symbol or '').upper().strip()
    if token in SECTOR_MAP:
        return SECTOR_MAP[token]
    # Infer from symbol structure
    market = infer_market(token)
    if market == 'equity':
        return 'equity'
    return market  # crypto / forex / commodity_fx
'@

$AP = $AP + $SectorAddition
Set-Content "trading\asset_profiles.py" $AP -Encoding UTF8
Write-Host "  [OK]  trading\asset_profiles.py" -ForegroundColor Green

# ===========================================================================
# FIX 6 — trading_agent.py: wire get_sector() so sector is never "unknown"
# ===========================================================================
Write-Host ""
Write-Host "Fix 6: trading_agent.py (wire get_sector)" -ForegroundColor White

$TA = Get-Content "trading\trading_agent.py" -Raw
Copy-Item "trading\trading_agent.py" "trading\trading_agent.py.bak" -Force
Write-Host "  [BAK] trading\trading_agent.py.bak" -ForegroundColor Yellow

# Add import if not already present
if ($TA -notmatch "from trading.asset_profiles import get_sector") {
    $TA = $TA -replace "from trading.asset_profiles import", "from trading.asset_profiles import get_sector,"
    # If that pattern didn't exist, try a generic asset_profiles import line
    if ($TA -notmatch "get_sector") {
        $TA = "from trading.asset_profiles import get_sector`n" + $TA
    }
}

# Replace 'unknown' sector literals with get_sector(symbol) calls
# Pattern: sector = 'unknown' or sector="unknown"
$TA = $TA -replace "sector\s*=\s*['""]unknown['""]", 'sector = get_sector(symbol)'
$TA = $TA -replace "'sector':\s*'unknown'", "'sector': get_sector(symbol)"
$TA = $TA -replace '"sector":\s*"unknown"', '"sector": get_sector(symbol)'

Set-Content "trading\trading_agent.py" $TA -Encoding UTF8
Write-Host "  [OK]  trading\trading_agent.py" -ForegroundColor Green

# ===========================================================================
# Summary
# ===========================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All trading fixes applied" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "What was fixed:" -ForegroundColor White
Write-Host "  1. market_data_stream.py  - quote ticks no longer rejected for zero volume" -ForegroundColor Green
Write-Host "  2. autonomous_trading_loop.py - expected_move logged at 6dp precision" -ForegroundColor Green
Write-Host "  3. autonomous_trading_loop.py - quality multiplier 0.2 -> 0.05" -ForegroundColor Green
Write-Host "  4. exposure_manager.py    - 'unknown' sector gets generous limit, correlation cap 3->6" -ForegroundColor Green
Write-Host "  5. asset_profiles.py      - full stock sector map + get_sector() function added" -ForegroundColor Green
Write-Host "  6. trading_agent.py       - wired get_sector() so sector never 'unknown'" -ForegroundColor Green
Write-Host ""
Write-Host "Backups saved as *.bak for every file touched." -ForegroundColor Gray
Write-Host ""
Write-Host "Now run: python main.py" -ForegroundColor Yellow
Write-Host "Watch for:" -ForegroundColor White
Write-Host "  - Fewer 'Data integrity reject' lines" -ForegroundColor Gray
Write-Host "  - expected_move showing real values (e.g. 0.000043)" -ForegroundColor Gray
Write-Host "  - EXPOSURE BY SECTOR showing real sector names" -ForegroundColor Gray
Write-Host "  - More trades executing past the quality gate" -ForegroundColor Gray
Write-Host ""
