"""MCP Memory Server - standalone MCP-compatible tool provider."""
import json
from pathlib import Path

MEMORY_DB = Path("data/mcp_memory.json")

def _load_store():
    if MEMORY_DB.exists():
        return json.loads(MEMORY_DB.read_text())
    return {}

def _save_store(store):
    MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_DB.write_text(json.dumps(store))

def handle_request(request):
    method = request.get("method", "")
    params = request.get("params", {})
    
    if method == "callTool":
        tool = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if tool == "memory_store":
            store = _load_store()
            key = arguments.get("key", "")
            value = arguments.get("value", "")
            store[key] = value
            _save_store(store)
            return {"content": [{"text": "stored"}]}
        
        elif tool == "memory_retrieve":
            store = _load_store()
            key = arguments.get("key", "")
            return {"content": [{"text": json.dumps(store.get(key, None))}]}
        
        elif tool == "memory_search":
            store = _load_store()
            query = arguments.get("query", "").lower()
            matches = {k: v for k, v in store.items() if query in str(k).lower() or query in str(v).lower()}
            return {"content": [{"text": json.dumps(matches)}]}
    
    elif method == "listTools":
        return {
            "tools": [
                {"name": "memory_store", "description": "Store a key-value pair", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}},
                {"name": "memory_retrieve", "description": "Retrieve a value by key", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}},
                {"name": "memory_search", "description": "Search memory by query", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
            ]
        }
    
    return {"error": {"code": -1, "message": "Unknown method"}}

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        request = json.loads(line.strip())
        response = handle_request(request)
        response["id"] = request.get("id")
        print(json.dumps(response), flush=True)