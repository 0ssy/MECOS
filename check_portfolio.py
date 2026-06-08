import json
from pathlib import Path
data = json.loads(Path('data/portfolio_snapshot.json').read_text())
print(json.dumps(data, indent=2))
