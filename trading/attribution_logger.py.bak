# trading/attribution_logger.py
import json
import time


def _json_default(value):
    # Handle numpy arrays/scalars and similar objects without hard dependency.
    if hasattr(value, 'tolist'):
        try:
            return value.tolist()
        except Exception:
            pass

    # Handle datetime/date-like objects.
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except Exception:
            pass

    return str(value)

class AttributionLogger:
    def __init__(self, path='trade_attribution.jsonl'):
        self.path = path

    def log(self, attribution_dict):
        entry = dict(attribution_dict)
        entry['timestamp'] = time.time()
        # Remove or fix any keys that cause serialization errors (e.g., missing 'entry')
        if 'entry' in entry and not isinstance(entry['entry'], (str, int, float, dict, list)):
            entry['entry'] = str(entry['entry'])
        # Remove any keys that are not serializable
        try:
            with open(self.path, 'a') as f:
                f.write(json.dumps(entry, default=_json_default) + '\n')
        except Exception as e:
            # Fallback: remove problematic keys and retry
            safe_entry = {k: (str(v) if not isinstance(v, (str, int, float, dict, list)) else v) for k, v in entry.items()}
            with open(self.path, 'a') as f:
                f.write(json.dumps(safe_entry, default=_json_default) + '\n')
