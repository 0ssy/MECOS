import json
from pathlib import Path
for f in ['data/runtime_state.json', 'data/state.json']:
    try:
        data = json.loads(Path(f).read_text())
        print(f"=== {f} ===")
        print(json.dumps(data, indent=2)[:2000])
    except Exception as e:
        print(f"{f}: {e}")
