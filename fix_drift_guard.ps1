# fix_drift_guard.ps1
# Run from your MECOS folder:
#   .\fix_drift_guard.ps1

$ErrorActionPreference = "Stop"
$DriftGuardPath = "runtime\drift_guard.py"

Write-Host ""
Write-Host "Fixing DriftGuard evaluate() alias..." -ForegroundColor Cyan

# Read current content
$content = Get-Content $DriftGuardPath -Raw

# Check if already fixed
if ($content -match "def evaluate") {
    Write-Host "[SKIP] evaluate() already exists in drift_guard.py" -ForegroundColor Yellow
    exit
}

# Append the alias method after the check() method
$alias = @'

    def evaluate(self, current_scores: Dict[str, float]) -> List[DriftEvent]:
        """Alias for check() — kept for compatibility with main.py."""
        return self.check(current_scores)
'@

Add-Content -Path $DriftGuardPath -Value $alias -Encoding UTF8
Write-Host "[OK] evaluate() alias added to DriftGuard" -ForegroundColor Green
Write-Host ""
Write-Host "Now run: python main.py" -ForegroundColor Yellow
Write-Host ""
