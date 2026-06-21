"""
MECOS Phase 4 - Tool Orchestrator
Central coordination layer that registers all tools and routes execution requests.
Integrates: ToolRegistry, CodeExecutor, FileOperations, BrowserAutomation, AppController.
"""

import asyncio
import json
from typing import Any, Optional
from loguru import logger

from config import settings
from tool_registry import ToolRegistry, ToolSpec, ToolPermission
from code_executor import CodeExecutor
from file_operations import FileOperations
from app_controller import AppController
from browser_automation import BrowserAutomation
from agent_reach_bridge import get_bridge


class ToolOrchestrator:
    """
    The central tool orchestration layer for MECOS.
    Manages all available tools and routes execution requests from the action engine.
    """

    def __init__(self, memory_system=None):
        self.registry = ToolRegistry()
        self.code_executor = CodeExecutor()
        self.file_ops = FileOperations()
        self.app_controller = AppController()
        self.browser_automation = BrowserAutomation()
        self.web_perception = None

        self._register_all_tools()
        self._register_browser_tools()
        self._register_agent_reach_tools(memory_system)
        logger.info("ToolOrchestrator ready with full Phase 4 tool suite + Agent-Reach channels.")

    def _register_all_tools(self):
        """Register all available tools into the registry."""

        # ── Terminal / Shell ──────────────────────────────────────────────
        self.registry.register(ToolSpec(
            name="terminal_command",
            description="Execute a safe shell command and return its output.",
            func=self._terminal_command,
            parameters={"command": "The shell command to execute"},
            permissions=ToolPermission(can_execute_code=True),
            category="system",
        ))

        # ── File Operations ───────────────────────────────────────────────
        self.registry.register(ToolSpec(
            name="file_write",
            description="Write text content to a file in the data directory.",
            func=self._file_write,
            parameters={"path": "Relative file path", "content": "Text content to write"},
            permissions=ToolPermission(can_write_files=True),
            category="files",
        ))
        self.registry.register(ToolSpec(
            name="file_read",
            description="Read text content from a file in the data directory.",
            func=self._file_read,
            parameters={"path": "Relative file path"},
            permissions=ToolPermission(),
            category="files",
        ))
        self.registry.register(ToolSpec(
            name="file_append",
            description="Append text content to an existing file.",
            func=self._file_append,
            parameters={"path": "Relative file path", "content": "Text to append"},
            permissions=ToolPermission(can_write_files=True),
            category="files",
        ))
        self.registry.register(ToolSpec(
            name="file_list",
            description="List files in a directory, optionally filtered by glob pattern.",
            func=self._file_list,
            parameters={"path": "Directory path (default: .)", "pattern": "Glob pattern (default: *)"},
            permissions=ToolPermission(),
            category="files",
        ))
        self.registry.register(ToolSpec(
            name="file_search",
            description="Search file contents for a query string.",
            func=self._file_search,
            parameters={"query": "Search query", "path": "Directory to search (default: .)"},
            permissions=ToolPermission(),
            category="files",
        ))
        self.registry.register(ToolSpec(
            name="file_delete",
            description="Delete a file (creates a backup first).",
            func=self._file_delete,
            parameters={"path": "Relative file path"},
            permissions=ToolPermission(can_write_files=True, requires_confirmation=True),
            category="files",
        ))

        # ── Code Execution ────────────────────────────────────────────────
        self.registry.register(ToolSpec(
            name="execute_python",
            description="Execute Python code in a sandboxed subprocess and return output.",
            func=self._execute_python,
            parameters={"code": "Python code to execute", "timeout": "Max execution seconds (default: 30)"},
            permissions=ToolPermission(can_execute_code=True),
            category="code",
        ))
        self.registry.register(ToolSpec(
            name="execute_bash",
            description="Execute a bash script in a sandboxed subprocess.",
            func=self._execute_bash,
            parameters={"code": "Bash script to execute", "timeout": "Max execution seconds (default: 30)"},
            permissions=ToolPermission(can_execute_code=True),
            category="code",
        ))
        self.registry.register(ToolSpec(
            name="run_tests",
            description="Run pytest on a test file and return the results.",
            func=self._run_tests,
            parameters={"test_file": "Path to the test file"},
            permissions=ToolPermission(can_execute_code=True),
            category="code",
        ))

        # ── Web / Browser ─────────────────────────────────────────────────
        self.registry.register(ToolSpec(
            name="web_fetch",
            description="Fetch and extract text content from a URL.",
            func=self._web_fetch,
            parameters={"url": "The URL to fetch"},
            permissions=ToolPermission(can_access_network=True),
            category="web",
        ))
        self.registry.register(ToolSpec(
            name="web_ingest",
            description="Ingest a URL into MECOS memory via the web perception system.",
            func=self._web_ingest,
            parameters={"url": "The URL to ingest"},
            permissions=ToolPermission(can_access_network=True),
            category="web",
        ))
        self.registry.register(ToolSpec(
            name="web_crawl",
            description="Crawl and ingest multiple pages from seed URLs.",
            func=self._web_crawl,
            parameters={
                "seed_urls": "List of starting URLs",
                "max_pages": "Maximum pages to crawl",
                "max_depth": "Link depth from seed URLs",
            },
            permissions=ToolPermission(can_access_network=True),
            category="web",
        ))

        # ── System Info ───────────────────────────────────────────────────
        self.registry.register(ToolSpec(
            name="system_info",
            description="Return current CPU, memory, and disk usage statistics.",
            func=self._system_info,
            parameters={},
            permissions=ToolPermission(),
            category="system",
        ))
        self.registry.register(ToolSpec(
            name="app_map",
            description="Map running processes and installed executables on this machine.",
            func=self._app_map,
            parameters={
                "process_limit": "Maximum running processes in result",
                "executable_limit": "Maximum executables in result",
            },
            permissions=ToolPermission(),
            category="system",
        ))

        # ── Office Automation ──────────────────────────────────────────
        self.registry.register(ToolSpec(
            name="office_write",
            description="Write text to Microsoft Word document.",
            func=self._office_write,
            parameters={"text": "Text content to write", "topic": "Optional topic for essay generation"},
            permissions=ToolPermission(can_launch_apps=True),
            category="office",
        ))
        self.registry.register(ToolSpec(
            name="office_generate_essay",
            description="Generate and write an essay to Word.",
            func=self._office_generate_essay,
            parameters={"topic": "Essay topic", "pages": "Target page count"},
            permissions=ToolPermission(can_launch_apps=True),
            category="office",
        ))

    def _register_browser_tools(self):
        self.registry.register(ToolSpec(
            name="browser_navigate",
            description="Navigate the bundled Playwright browser to a URL.",
            func=self._browser_navigate,
            parameters={"url": "The URL to open"},
            permissions=ToolPermission(can_access_network=True),
            category="web",
        ))
        self.registry.register(ToolSpec(
            name="browser_get_text",
            description="Extract visible text from the current browser page.",
            func=self._browser_get_text,
            parameters={},
            permissions=ToolPermission(can_access_network=True),
            category="web",
        ))
        self.registry.register(ToolSpec(
            name="browser_screenshot",
            description="Take a full-page screenshot in the browser.",
            func=self._browser_screenshot,
            parameters={"filename": "Optional screenshot filename"},
            permissions=ToolPermission(can_access_network=True),
            category="web",
        ))
        self.registry.register(ToolSpec(
            name="browser_extract_links",
            description="Extract all hyperlinks from the current page.",
            func=self._browser_extract_links,
            parameters={},
            permissions=ToolPermission(can_access_network=True),
            category="web",
        ))

    def _register_agent_reach_tools(self, memory_system=None):
        from agent_reach_tools import register_agent_reach_tools
        register_agent_reach_tools(self.registry, memory_system)

    # ── Tool implementations ──────────────────────────────────────────────

    async def _terminal_command(self, command: str) -> str:
        result = await self.app_controller.run_command(command, timeout=30)
        if result["exit_code"] != "0" and result["stderr"]:
            return f"Error (exit {result['exit_code']}): {result['stderr']}"
        return result["stdout"] or f"Command completed (exit {result['exit_code']})"

    async def _file_write(self, path: str, content: str) -> str:
        try:
            written = self.file_ops.write_text(path, content)
            return f"File written: {written}"
        except Exception as e:
            return f"Error writing file: {e}"

    async def _file_read(self, path: str) -> str:
        try:
            return self.file_ops.read_text(path)
        except Exception as e:
            return f"Error reading file: {e}"

    async def _file_append(self, path: str, content: str) -> str:
        try:
            self.file_ops.append_text(path, content)
            return f"Appended to: {path}"
        except Exception as e:
            return f"Error appending to file: {e}"

    async def _file_list(self, path: str = ".", pattern: str = "*") -> str:
        try:
            files = self.file_ops.list_directory(path, pattern)
            return "\n".join(files) if files else "No files found."
        except Exception as e:
            return f"Error listing directory: {e}"

    async def _file_search(self, query: str, path: str = ".") -> str:
        try:
            results = self.file_ops.search_files(query, path)
            if not results:
                return f"No files found containing '{query}'"
            lines = [f"[{r['file']}]: ...{r['snippet']}..." for r in results]
            return "\n".join(lines)
        except Exception as e:
            return f"Error searching files: {e}"

    async def _file_delete(self, path: str) -> str:
        try:
            deleted = self.file_ops.delete_file(path)
            return f"Deleted: {path}" if deleted else f"File not found: {path}"
        except Exception as e:
            return f"Error deleting file: {e}"

    async def _execute_python(self, code: str, timeout: int = 30) -> str:
        result = await self.code_executor.execute_python(code, timeout=int(timeout))
        if result.success:
            return result.stdout or "Execution completed with no output."
        return f"Error (exit {result.exit_code}): {result.stderr}"

    async def _execute_bash(self, code: str, timeout: int = 30) -> str:
        result = await self.code_executor.execute_bash(code, timeout=int(timeout))
        if result.success:
            return result.stdout or "Execution completed with no output."
        return f"Error (exit {result.exit_code}): {result.stderr}"

    async def _run_tests(self, test_file: str) -> str:
        result = await self.code_executor.run_tests(test_file)
        output = result.stdout + ("\n" + result.stderr if result.stderr else "")
        return output or ("Tests passed." if result.success else "Tests failed.")

    async def _web_fetch(self, url: str) -> str:
        if self.web_perception:
            await self.web_perception.ingest_url(url)
            return f"Fetched and stored content from: {url}"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    text = await resp.text()
                    return text[:5000]
        except Exception as e:
            return f"Error fetching {url}: {e}"

    async def _web_ingest(self, url: str) -> str:
        if self.web_perception:
            await self.web_perception.ingest_url(url)
            return f"Ingested: {url}"
        return f"Web perception not available. URL: {url}"

    async def _web_crawl(self, seed_urls: list, max_pages: int = 10, max_depth: int = 1) -> str:
        if not self.web_perception:
            return "Web perception not available."
        result = await self.web_perception.crawl_web(
            seed_urls=seed_urls,
            max_pages=max_pages,
            max_depth=max_depth,
            same_domain_only=True,
        )
        return json.dumps(result)

    async def _system_info(self) -> str:
        info = self.app_controller.get_system_info()
        return "\n".join(f"{k}: {v}" for k, v in info.items())

    async def _app_map(self, process_limit: int = 50, executable_limit: int = 150) -> str:
        machine_map = self.app_controller.map_computer(
            process_limit=int(process_limit),
            executable_limit=int(executable_limit),
        )
        return json.dumps(machine_map)

    async def _office_write(self, text: str, topic: str = "") -> str:
        """Write text to Word document."""
        if not text:
            return "No text provided"
        try:
            from office_automation import OfficeAutomation
            office = OfficeAutomation()
            result = await office.open_word()
            if result["status"] != "ok":
                return f"Could not open Word: {result.get('message', 'unknown error')}"
            write_result = await office.write_to_word(text)
            return f"Written to Word: {write_result.get('chars_written', 0)} chars"
        except Exception as e:
            return f"Office write error: {e}"

    async def _office_generate_essay(self, topic: str, pages: int = 20) -> str:
        """Generate and write essay to Word."""
        try:
            from office_automation import OfficeAutomation
            office = OfficeAutomation()
            result = await office.generate_and_write_essay(topic, int(pages))
            if result["status"] == "ok":
                return f"Essay generated: {result.get('paragraphs_written', 0)} paragraphs on '{topic}'"
            return f"Essay generation failed: {result.get('message', 'unknown error')}"
        except Exception as e:
            return f"Essay generation error: {e}"

    async def _browser_navigate(self, url: str) -> str:
        try:
            ok = await self.browser_automation.navigate(url)
            return f"Navigated to {url}" if ok else f"Navigation failed for {url}"
        except Exception as e:
            return f"Browser navigation error: {e}"

    async def _browser_get_text(self) -> str:
        try:
            text = await self.browser_automation.get_text()
            return text[:5000] if text else "No text extracted."
        except Exception as e:
            return f"Browser text extraction error: {e}"

    async def _browser_screenshot(self, filename: Optional[str] = None) -> str:
        try:
            path = await self.browser_automation.screenshot(filename)
            return f"Screenshot saved: {path}" if path else "Screenshot failed."
        except Exception as e:
            return f"Browser screenshot error: {e}"

    async def _browser_extract_links(self) -> str:
        try:
            links = await self.browser_automation.extract_links()
            return "\n".join(links) if links else "No links found."
        except Exception as e:
            return f"Browser link extraction error: {e}"

    # ── Public interface ──────────────────────────────────────────────────

    async def run_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a registered tool by name with the given arguments."""
        spec = self.registry.get(tool_name)
        if not spec:
            available = [t.name for t in self.registry.list_tools()]
            return f"Unknown tool: '{tool_name}'. Available: {available}"
        if not spec.enabled:
            return f"Tool '{tool_name}' is currently disabled."

        logger.info(f"Orchestrating tool: {tool_name}")
        try:
            result = await spec.func(**kwargs)
            return str(result)
        except TypeError as e:
            return f"Tool argument error for '{tool_name}': {e}"
        except Exception as e:
            logger.error(f"Tool '{tool_name}' raised an exception: {e}")
            return f"Tool execution error: {e}"

    def describe_tools(self) -> str:
        """Return a formatted description of all available tools for the reasoner."""
        return self.registry.describe_all()

    # ── Workflow orchestration ─────────────────────────────────────────

    async def run_workflow(self, steps: list[dict]) -> list:
        results = []
        for step in steps:
            tool = step.get("tool") or step.get("name")
            args = step.get("args") or step.get("parameters") or {}
            logger.info("[workflow] step: {} -> {}", tool, args)

            spec = self.registry.get(tool)
            if not spec:
                results.append({"tool": tool, "status": "error", "error": f"Unknown tool: {tool}"})
                continue
            if not spec.enabled:
                results.append({"tool": tool, "status": "skipped", "error": "disabled"})
                continue

            validated = self._validate_args(spec, args)
            if "error" in validated:
                fallback = step.get("fallback")
                if fallback:
                    logger.info("[workflow] falling back for {} -> {}", tool, fallback)
                    fb = self.registry.get(fallback)
                    if fb and fb.enabled:
                        try:
                            res = await fb.func(**validated.get("fallback_args") or {})
                            results.append({"tool": fallback, "status": "ok", "result": str(res)[:1000]})
                            continue
                        except Exception as exc:
                            results.append({"tool": fallback, "status": "error", "error": str(exc)})
                            continue
                results.append({"tool": tool, "status": "error", "error": validated["error"]})
                continue

            try:
                res = await spec.func(**validated)
                results.append({"tool": tool, "status": "ok", "result": str(res)[:2000]})
            except Exception as exc:
                results.append({"tool": tool, "status": "error", "error": str(exc)})
        return results

    @staticmethod
    def _validate_args(spec, args: dict) -> dict:
        if not args or not spec.parameters:
            return args or {}
        validated = {}
        for key, desc in spec.parameters.items():
            if key not in args:
                continue
            val = args[key]
            if key == "timeout" or key.endswith("_limit") or key == "max_pages":
                try:
                    validated[key] = max(1, int(val))
                except Exception:
                    validated[key] = 30
            elif isinstance(val, str):
                validated[key] = val
            elif isinstance(val, (list, dict)):
                validated[key] = val
            else:
                validated[key] = str(val)
        return validated

    async def run_tool_with_fallback(self, tool_name: str, fallbacks: list[str], **kwargs) -> str:
        last_error = ""
        for name in [tool_name] + fallbacks:
            spec = self.registry.get(name)
            if not spec or not spec.enabled:
                continue
            try:
                return await spec.func(**kwargs)
            except Exception as exc:
                last_error = str(exc)
                logger.debug("Tool '{}' failed: {}", name, exc)
                continue
        return f"All tools failed ({tool_name} + {fallbacks}): {last_error}"

    def available_tools_summary(self) -> str:
        tools = self.registry.list_tools()
        lines = [f"MECOS ToolOrchestrator — {len(tools)} tools registered"]
        cats: dict = {}
        for t in tools:
            cats.setdefault(t.category, []).append(t.name)
        for cat, names in sorted(cats.items()):
            lines.append(f"  [{cat}]: {', '.join(names)}")
        return "\n".join(lines)
