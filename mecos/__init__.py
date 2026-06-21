"""MECOS MCP module - standalone MCP servers."""
from .mcp_sqlite import handle_request as sqlite_handle
from .mcp_memory import handle_request as memory_handle
from .mcp_sequential import handle_request as sequential_handle