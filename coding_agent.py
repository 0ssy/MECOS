"""
MECOS Phase 5 - Coding Agent
Syntax tree parsing, code generation from specs, bug detection and fixing,
test generation, code refactoring, dependency analysis, and documentation generation.
"""

import ast
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

from memory_system import MemorySystem
from tool_orchestrator import ToolOrchestrator
from engineer import SandboxExecutor
from openai import OpenAI
from config import settings


class SyntaxAnalyzer:
    """Analyzes Python source code using the AST module."""

    def analyze(self, code: str) -> Dict[str, Any]:
        """Parse Python code and extract structural information."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"error": str(e), "valid": False}

        functions = []
        classes = []
        imports = []
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "line": node.lineno,
                    "has_docstring": (
                        isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant) and
                        isinstance(node.body[0].value.value, str)
                    ) if node.body else False,
                })
            elif isinstance(node, ast.ClassDef):
                classes.append({"name": node.name, "line": node.lineno})
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                else:
                    imports.append(node.module or "")

        # Basic issue detection
        for func in functions:
            if not func["has_docstring"]:
                issues.append(f"Function '{func['name']}' (line {func['line']}) missing docstring")

        return {
            "valid": True,
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "issues": issues,
            "line_count": len(code.splitlines()),
        }

    def find_bugs(self, code: str) -> List[str]:
        """Identify common Python anti-patterns and potential bugs."""
        bugs = []
        lines = code.splitlines()

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Bare except
            if stripped == "except:":
                bugs.append(f"Line {i}: Bare 'except:' clause — catches all exceptions including SystemExit")
            # Mutable default argument
            if re.search(r"def \w+\(.*=\s*[\[\{]", line):
                bugs.append(f"Line {i}: Possible mutable default argument")
            # == None comparison
            if "== None" in line:
                bugs.append(f"Line {i}: Use 'is None' instead of '== None'")
            # print without logging
            if stripped.startswith("print(") and "debug" not in line.lower():
                bugs.append(f"Line {i}: Consider using logging instead of print()")

        return bugs


class CodingAgent:
    """
    Full-featured coding intelligence agent.
    Generates, analyzes, tests, debugs, and refactors code.
    """

    def __init__(
        self,
        memory: MemorySystem,
        orchestrator: ToolOrchestrator,
        sandbox_executor: Optional[SandboxExecutor] = None,
    ):
        self.memory = memory
        self.orchestrator = orchestrator
        self.sandbox_executor = sandbox_executor or SandboxExecutor()
        self.syntax_analyzer = SyntaxAnalyzer()
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        logger.info("CodingAgent initialized.")

    async def generate_code(self, requirement: str, language: str = "python") -> str:
        """Generate code from a natural language requirement."""
        logger.info(f"Generating {language} code for: {requirement[:80]}")

        # Retrieve relevant code patterns from memory
        context_results = await self.memory.retrieve_context(requirement)
        context = "\n".join(context_results.get("documents", [[]])[0][:3]) if context_results else ""

        prompt = f"""You are an expert {language} developer. Generate clean, well-documented code.

Requirement: {requirement}

Relevant context from memory:
{context}

Rules:
- Write production-quality code with docstrings
- Include error handling
- Add type hints (Python)
- Keep it concise and readable

Return ONLY the code, no explanations."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            code = response.choices[0].message.content
            # Strip markdown code blocks if present
            code = re.sub(r"^```\w*\n?", "", code.strip())
            code = re.sub(r"\n?```$", "", code.strip())

            await self.memory.add_experience(
                f"CODE GENERATED [{language}]: {requirement[:100]}\n{code[:300]}",
                source="coding_agent",
            )
            logger.info(f"Code generated ({len(code)} chars)")
            return code
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return f"# Error generating code: {e}"

    async def analyze_code(self, code: str) -> Dict[str, Any]:
        """Analyze code structure and identify issues."""
        analysis = self.syntax_analyzer.analyze(code)
        bugs = self.syntax_analyzer.find_bugs(code)
        analysis["potential_bugs"] = bugs

        await self.memory.add_experience(
            f"CODE ANALYSIS: {len(analysis.get('functions', []))} functions, "
            f"{len(bugs)} potential issues found",
            source="coding_agent",
        )
        return analysis

    async def debug_code(self, code: str, error: str) -> str:
        """Analyze an error and suggest a fix."""
        logger.info(f"Debugging code. Error: {error[:100]}")

        prompt = f"""You are an expert debugger. Fix the following code error.

Code:
```python
{code}
```

Error:
{error}

Provide:
1. Root cause explanation (1-2 sentences)
2. Fixed code

Return the fixed code only (no markdown blocks)."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            fix = response.choices[0].message.content
            fix = re.sub(r"^```\w*\n?", "", fix.strip())
            fix = re.sub(r"\n?```$", "", fix.strip())

            await self.memory.add_experience(
                f"CODE DEBUG: Error='{error[:100]}' → Fix applied",
                source="coding_agent",
            )
            return fix
        except Exception as e:
            logger.error(f"Debug failed: {e}")
            return f"# Debug failed: {e}\n{code}"

    async def generate_tests(self, code: str, framework: str = "pytest") -> str:
        """Generate unit tests for the given code."""
        logger.info(f"Generating {framework} tests")

        prompt = f"""Generate comprehensive {framework} unit tests for this code.

Code to test:
```python
{code}
```

Requirements:
- Test all functions/methods
- Include edge cases
- Use descriptive test names
- Add docstrings to tests

Return ONLY the test code."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            tests = response.choices[0].message.content
            tests = re.sub(r"^```\w*\n?", "", tests.strip())
            tests = re.sub(r"\n?```$", "", tests.strip())

            await self.memory.add_experience(
                f"TESTS GENERATED: {len(tests)} chars of {framework} tests",
                source="coding_agent",
            )
            return tests
        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            return f"# Test generation failed: {e}"

    async def run_tests(self, test_file: str) -> str:
        """Run tests using the orchestrator's test runner."""
        result = await self.orchestrator.run_tool("run_tests", test_file=test_file)
        await self.memory.add_experience(
            f"TESTS RUN: {test_file}\nResult: {result[:300]}",
            source="coding_agent",
        )
        return result

    async def refactor_code(self, code: str, instructions: str) -> str:
        """Refactor code according to given instructions."""
        prompt = f"""Refactor the following code according to these instructions: {instructions}

Code:
```python
{code}
```

Return ONLY the refactored code."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            refactored = response.choices[0].message.content
            refactored = re.sub(r"^```\w*\n?", "", refactored.strip())
            refactored = re.sub(r"\n?```$", "", refactored.strip())
            return refactored
        except Exception as e:
            logger.error(f"Refactoring failed: {e}")
            return code

    async def generate_documentation(self, code: str) -> str:
        """Generate markdown documentation for the given code."""
        prompt = f"""Generate comprehensive Markdown documentation for this code.

Include:
- Module/class/function descriptions
- Parameters and return types
- Usage examples
- Any important notes

Code:
```python
{code}
```"""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"# Documentation generation failed: {e}"

    async def execute_and_validate(self, code: str, expected_output: Optional[str] = None) -> Dict[str, Any]:
        """Execute code and optionally validate against expected output."""
        sandbox_result = self.sandbox_executor.execute_code(code, "runtime_execution.py")
        success = bool(sandbox_result.get("success", False))
        result_str = sandbox_result.get("stdout", "") if success else sandbox_result.get("error", sandbox_result.get("stderr", ""))
        validated = None
        if expected_output and success:
            validated = expected_output.strip() in result_str.strip()

        return {
            "output": result_str,
            "success": success,
            "validated": validated,
        }

    async def build_module(self, name: str, requirements: str) -> str:
        """Build and sandbox-validate a small runtime module."""
        module_name = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_") or "generated_module"
        code = (
            f"def {module_name}_function():\n"
            f"    return 'Generated for: {requirements}'\n\n"
            "if __name__ == '__main__':\n"
            f"    print({module_name}_function())\n"
        )
        result = self.sandbox_executor.execute_code(code, f"{module_name}.py")
        if not result.get("success", False):
            logger.error(f"Generated module failed sandbox: {result.get('stderr') or result.get('error')}")
            return ""
        return code
