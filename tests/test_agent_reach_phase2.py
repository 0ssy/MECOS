"""
MECOS Outreach - Agent-Reach Phase 2 Tests
"""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def research_orchestrator():
    from outreach.research_orchestrator import ResearchOrchestrator
    return ResearchOrchestrator()


def test_discover_lead_signals_returns_empty_when_all_backends_fail(
    research_orchestrator,
):
    with (
        patch(
            "outreach.research_orchestrator.research_twitter",
            new_callable=AsyncMock,
            return_value={"ok": False, "text": "", "error": "fail"},
        ),
        patch(
            "outreach.research_orchestrator.research_youtube",
            new_callable=AsyncMock,
            return_value={"ok": False, "text": "", "error": "fail"},
        ),
        patch(
            "outreach.research_orchestrator.research_reddit",
            new_callable=AsyncMock,
            return_value={"ok": False, "text": "", "error": "fail"},
        ),
        patch(
            "outreach.research_orchestrator.research_web",
            new_callable=AsyncMock,
            return_value={"ok": False, "text": "", "error": "fail"},
        ),
    ):
        candidates = research_orchestrator.discover_lead_signals(["automation needed"])
        assert candidates == []


def test_discover_lead_signals_creates_valid_leads_with_jina_fallback(
    research_orchestrator,
):
    pain_text = (
        "We are frustrated with manual data entry and looking for automation. "
        "Our small business is growing fast and we need help with workflow bottleneck."
    )

    def make_ok_result(platform):
        return {
            "ok": True,
            "text": pain_text,
            "link": f"https://{platform}.example.com/post/123",
            "source": f"{platform}_jina",
        }

    with (
        patch(
            "outreach.research_orchestrator.research_twitter",
            new_callable=AsyncMock,
            return_value=make_ok_result("twitter"),
        ),
        patch(
            "outreach.research_orchestrator.research_youtube",
            new_callable=AsyncMock,
            return_value=make_ok_result("youtube"),
        ),
        patch(
            "outreach.research_orchestrator.research_reddit",
            new_callable=AsyncMock,
            return_value=make_ok_result("reddit"),
        ),
        patch(
            "outreach.research_orchestrator.research_web",
            new_callable=AsyncMock,
            return_value=make_ok_result("web"),
        ),
    ):
        candidates = research_orchestrator.discover_lead_signals(["automation needed"])
        assert len(candidates) == 4

        for c in candidates:
            assert "url" in c
            assert "domain" in c
            assert "text_excerpt" in c
            assert "source_platform" in c
            assert "total_score" in c
            assert c["total_score"] >= 2
            assert c["domain"] != ""
            assert c["url"].startswith("https://")
            assert "matched_terms" in c
            assert "signals" in c
            assert "content_hash" in c


def test_run_research_cycle_integration():
    os.environ["MECOS_ENABLE_OUTREACH"] = "true"

    from memory_system import MemorySystem
    from outreach.outreach_agent import OutreachAgent

    memory = MemorySystem()
    agent = OutreachAgent(memory=memory)
    agent.scanner.leads = []
    agent.scanner.scanned_urls = set()
    agent.scanner.scanned_content_hashes = set()

    mock_candidates = [
        {
            "url": "https://example.com/post/1",
            "domain": "example.com",
            "text_excerpt": "We need automation for manual data entry.",
            "source_platform": "web",
            "total_score": 3,
            "matched_terms": ["manual data entry"],
            "signals": {
                "inefficiency_markers": 0,
                "pain_points": 1,
                "organic_intent": 0,
                "revenue_fit": 0,
            },
            "content_hash": "hash1",
        }
    ]

    mock_orchestrator = MagicMock()
    mock_orchestrator.discover_lead_signals.return_value = mock_candidates

    with patch(
        "outreach.outreach_agent.ResearchOrchestrator",
        return_value=mock_orchestrator,
    ):
        result = asyncio.run(agent._run_research_cycle())

    assert result["discovered"] == 1
    assert result["new_leads"] == 1
    assert len(agent.scanner.leads) == 1
    assert agent.scanner.leads[0]["url"] == "https://example.com/post/1"
