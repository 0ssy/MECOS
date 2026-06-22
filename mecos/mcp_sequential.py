"""MCP Sequential Thinking Server - standalone MCP-compatible tool provider."""
import json

def handle_request(request):
    method = request.get("method", "")
    params = request.get("params", {})
    
    if method == "callTool":
        tool = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if tool == "sequential_think":
            thought = arguments.get("thought", "")
            next_steps = arguments.get("next_steps", [])
            reasoning = {
                "thought": thought,
                "steps": next_steps,
                "chain_id": hash(thought) % 10000,
            }
            return {"content": [{"text": json.dumps(reasoning)}]}
        
        elif tool == "think_step":
            step = arguments.get("step", "")
            return {"content": [{"text": f"Step: {step}"}]}
    
    elif method == "listTools":
        return {
            "tools": [
                {"name": "sequential_think", "description": "Multi-step reasoning chain", "inputSchema": {"type": "object", "properties": {"thought": {"type": "string"}, "next_steps": {"type": "array"}}}},
                {"name": "think_step", "description": "Single reasoning step", "inputSchema": {"type": "object", "properties": {"step": {"type": "string"}}}},
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