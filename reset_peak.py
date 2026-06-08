import json
from pathlib import Path
snapshot = json.loads(Path('data/portfolio_snapshot.json').read_text())
snapshot['total_value'] = snapshot['equity']
Path('data/portfolio_snapshot.json').write_text(json.dumps(snapshot, indent=2))
print('Peak reset to current equity:', snapshot['equity'])
