"""
ECC Skills Integration for MECOS
Imports ECC skills from libs/ECC/skills/ into ToolRegistry with 'ecc:' prefix.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from tool_registry import ToolRegistry, ToolSpec, ToolPermission


class ECCSkillLoader:
    """Load and register ECC skills as MECOS tools."""

    ECC_SKILLS_DIR = Path(__file__).parent / "libs" / "ECC" / "skills"

    RELEVANT_CATEGORIES = {
        "email-ops", "crm", "workspace-surface-audit", "connections-optimizer",
        "social-graph-ranker", "email-sequence", "linkedin-outreach",
        "follow-up-agent", "lead-intelligence", "outreach",
    }

    def __init__(self, registry: ToolRegistry = None):
        self.registry = registry

    def discover_skills(self) -> List[Dict[str, Any]]:
        """Find all ECC skills with YAML frontmatter."""
        skills = []
        if not self.ECC_SKILLS_DIR.exists():
            logger.warning(f"ECC skills directory not found: {self.ECC_SKILLS_DIR}")
            return skills

        for skill_file in self.ECC_SKILLS_DIR.glob("**/SKILL.md"):
            try:
                content = skill_file.read_text(encoding="utf-8")
                if not content.startswith("---"):
                    continue
                parts = content.split("---", 2)
                if len(parts) < 3:
                    continue
                frontmatter = yaml.safe_load(parts[1])
                if not frontmatter or "name" not in frontmatter:
                    continue
                skills.append({
                    "name": frontmatter.get("name"),
                    "path": str(skill_file),
                    "description": frontmatter.get("description", ""),
                    "body": parts[2].strip(),
                    "category": frontmatter.get("metadata", {}).get("category", "general"),
                })
            except Exception as e:
                logger.debug(f"Skipping ECC skill {skill_file}: {e}")
        return skills

    def register_skill(self, skill: Dict[str, Any]) -> Optional[str]:
        """Register a single ECC skill with 'ecc:' prefix."""
        if not self.registry:
            return None

        skill_name = skill["name"]
        tool_name = f"ecc:{skill_name.replace(' ', '-').lower()}"

        async def skill_func(query: str = "", args: dict = None) -> dict:
            """Execute the ECC skill via LLM."""
            from mecos_llm import get_mecos_llm
            args = args or {}
            llm = get_mecos_llm()

            skill_prompt = f"""You are applying the {skill_name} ECC skill.

{skill['body']}

User query: {query}
Extra args: {json.dumps(args)}

Apply the skill and return actionable results. For workflow skills, provide step-by-step guidance."""
            try:
                result = await llm.think_and_act(
                    skill_prompt,
                    system_prompt=f"You are applying the {skill_name} ECC skill. Follow its guidance.",
                )
                return {"status": "skill_executed", "name": tool_name, "result": result.get("response", "")}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        self.registry.register(ToolSpec(
            name=tool_name,
            description=skill["description"],
            func=skill_func,
            parameters={"query": "Goal or query to process", "args": "Optional arguments dict"},
            permissions=ToolPermission(can_execute_code=False, can_access_network=False),
            category=skill["category"],
            source_module=skill["path"],
            is_skill=True,
        ))
        return tool_name

    def import_all_skills(self) -> int:
        """Import all ECC skills into registry. Returns count registered."""
        skills = self.discover_skills()
        count = 0
        for skill in skills:
            registered = self.register_skill(skill)
            if registered:
                logger.info(f"Registered ECC skill: {registered}")
                count += 1
        return count


def import_ecc_skills(registry: ToolRegistry = None) -> int:
    """Convenience function - import all ECC skills."""
    loader = ECCSkillLoader(registry)
    return loader.import_all_skills()


if __name__ == "__main__":
    from tool_registry import ToolRegistry
    registry = ToolRegistry()
    count = import_ecc_skills(registry)
    print(f"Imported {count} ECC skills as MECOS tools")