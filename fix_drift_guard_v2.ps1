# fix_drift_guard_v2.ps1
# Run from your MECOS folder:
#   .\fix_drift_guard_v2.ps1

$ErrorActionPreference = "Stop"
$DriftGuardPath = "runtime\drift_guard.py"

Write-Host ""
Write-Host "Fixing DriftGuard.evaluate() return type..." -ForegroundColor Cyan

# Read current content
$content = Get-Content $DriftGuardPath -Raw

# Remove the old alias if it exists (from previous fix)
$oldAlias = @'

    def evaluate(self, current_scores: Dict[str, float]) -> List[DriftEvent]:
        """Alias for check() — kept for compatibility with main.py."""
        return self.check(current_scores)
'@

$content = $content.Replace($oldAlias, "")

# Append the correct evaluate() method that returns what main.py expects
$correctMethod = @'

    def evaluate(self, current_scores: Dict[str, float]) -> dict:
        """
        Compatible with main.py — returns a dict with:
          drift_detected: bool
          average_delta:  float
          events:         list of DriftEvent dicts
        """
        events = self.check(current_scores)
        regressions = [e for e in events if e.direction == "REGRESSION"]
        average_delta = (
            sum(e.delta for e in regressions) / len(regressions)
            if regressions else 0.0
        )
        return {
            "drift_detected": len(regressions) > 0,
            "average_delta": average_delta,
            "regression_count": len(regressions),
            "improvement_count": len([e for e in events if e.direction == "IMPROVEMENT"]),
            "events": [asdict(e) for e in events],
        }
'@

# Write back
Set-Content -Path $DriftGuardPath -Value ($content + $correctMethod) -Encoding UTF8

Write-Host "[OK] evaluate() fixed — now returns dict compatible with main.py" -ForegroundColor Green
Write-Host ""
Write-Host "Now run: python main.py" -ForegroundColor Yellow
Write-Host ""
