import json
from pathlib import Path
snapshots = list(Path('data').rglob('*.json'))
for s in snapshots:
    print(s)
