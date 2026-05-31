"""
MECOS v3.5 foundational engines.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


@dataclass
class LanguageProfile:
    name: str
    mastery_level: float = 0.0
    compiler_path: Optional[str] = None
    best_practices: List[str] = field(default_factory=list)
    common_patterns: List[str] = field(default_factory=list)


@dataclass
class AppCapability:
    name: str
    is_learned: bool = False
    driver_path: Optional[str] = None
    api_type: str = "CLI"
    confidence_score: float = 0.0


class PolyglotCodingAgent:
    """Learns programming languages and practices coding challenges."""

    def __init__(self, workspace: str = "sandbox") -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.languages: Dict[str, LanguageProfile] = {
            "python": LanguageProfile(name="python", mastery_level=0.95),
            "javascript": LanguageProfile(name="javascript"),
            "rust": LanguageProfile(name="rust"),
            "go": LanguageProfile(name="go"),
            "cpp": LanguageProfile(name="cpp"),
        }

    def learn_language(self, language: str) -> LanguageProfile:
        token = str(language).strip().lower()
        if token not in self.languages:
            self.languages[token] = LanguageProfile(name=token)
        profile = self.languages[token]
        profile.mastery_level = min(1.0, profile.mastery_level + 0.1)
        logger.info(f"[Polyglot] {token} mastery -> {profile.mastery_level:.2f}")
        return profile

    def solve_challenge(self, language: str, challenge_id: str) -> Path:
        token = str(language).strip().lower()
        challenge = str(challenge_id).strip()
        file_ext = {"python": "py", "rust": "rs", "cpp": "cpp", "go": "go", "javascript": "js"}
        ext = file_ext.get(token, "txt")
        target_file = self.workspace / f"challenge_{challenge}.{ext}"
        target_file.write_text(
            f"# MECOS auto-generated {token} solution stub for {challenge}\n",
            encoding="utf-8",
        )
        logger.info(f"[Polyglot] challenge generated -> {target_file}")
        return target_file


class GlobalAppIntelligence:
    """Learns unknown applications and tracks generated control capabilities."""

    def __init__(self, registry_path: str = "data\\app_registry.json") -> None:
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.learned_apps: Dict[str, AppCapability] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            return
        payload = json.loads(self.registry_path.read_text(encoding="utf-8") or "{}")
        self.learned_apps = {k: AppCapability(**v) for k, v in payload.items()}

    def _save_registry(self) -> None:
        serialized = {k: asdict(v) for k, v in self.learned_apps.items()}
        self.registry_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def discover_app(self, app_name: str) -> AppCapability:
        token = str(app_name).strip()
        known = self.learned_apps.get(token)
        if known and known.is_learned:
            logger.info(f"[AppIntel] '{token}' already learned")
            return known
        return self.teach_self_app(token)

    def teach_self_app(self, app_name: str) -> AppCapability:
        token = str(app_name).strip()
        capability = AppCapability(
            name=token,
            is_learned=True,
            driver_path=f"drivers\\{token.lower().replace(' ', '_')}_driver.py",
            confidence_score=0.85,
        )
        self.learned_apps[token] = capability
        self._save_registry()
        logger.info(f"[AppIntel] learned '{token}' -> {capability.driver_path}")
        return capability
