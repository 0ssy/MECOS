"""MCP SQLite Server - standalone MCP-compatible tool provider."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/mecos.db")

def handle_request(request):
    """Handle MCP JSON-RPC requests."""
    method = request.get("method", "")
    params = request.get("params", {})
    
    if method == "callTool":
        tool = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if tool == "sqlite_query":
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute(arguments.get("query", ""))
            rows = cursor.fetchall()
            conn.close()
            return {"content": [{"text": json.dumps(rows)}]}
        
        elif tool == "sqlite_execute":
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute(arguments.get("statement", ""))
            conn.commit()
            conn.close()
            return {"content": [{"text": "OK"}]}
        
        elif tool == "sqlite_tables":
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return {"content": [{"text": json.dumps(tables)}]}
    
    elif method == "listTools":
        return {
            "tools": [
                {"name": "sqlite_query", "description": "Execute a SQL query", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}},
                {"name": "sqlite_execute", "description": "Execute a SQL statement", "inputSchema": {"type": "object", "properties": {"statement": {"type": "string"}}}},
                {"name": "sqlite_tables", "description": "List all tables", "inputSchema": {"type": "object"}},
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