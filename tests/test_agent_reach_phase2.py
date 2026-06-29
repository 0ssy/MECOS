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


@pytest.fixture
def delivery_agent():
    from outreach.delivery_agent import DeliveryAgent
    return DeliveryAgent()


def test_research_lead_returns_shape_when_all_backends_fail(
    research_orchestrator,
):
    """Test Task 5: ResearchOrchestrator.research_lead() returns expected shape when all backends down."""
    high_score_lead = {
        "total_score": 6,
        "domain": "test.com",
        "matched_terms": ["automation needed"],
        "pain_points": ["manual work"],
    }

    with (
        patch(
            "outreach.research_orchestrator.research_twitter",
            new_callable=AsyncMock,
            return_value={"ok": False, "text": "", "error": "backend_unavailable"},
        ),
        patch(
            "outreach.research_orchestrator.research_youtube",
            new_callable=AsyncMock,
            return_value={"ok": False, "text": "", "error": "backend_unavailable"},
        ),
        patch(
            "outreach.research_orchestrator.research_reddit",
            new_callable=AsyncMock,
            return_value={"ok": False, "text": "", "error": "backend_unavailable"},
        ),
        patch(
            "outreach.research_orchestrator.research_web",
            new_callable=AsyncMock,
            return_value={"ok": False, "text": "", "error": "backend_unavailable"},
        ),
    ):
        signals = asyncio.run(research_orchestrator.research_lead(high_score_lead))

    assert "twitter" in signals
    assert "youtube" in signals
    assert "reddit" in signals
    assert "web" in signals
    for platform in ["twitter", "youtube", "reddit", "web"]:
        assert "ok" in signals[platform]
        assert signals[platform]["ok"] is False


def test_draft_email_includes_personalization_when_research_summary_present(
    delivery_agent,
):
    """Test Task 5: draft_email() includes personalization when research_summary is present."""
    brief_with_research = {
        "domain": "testcompany.com",
        "pain_points": ["manual data entry"],
        "contacts": {"emails": ["test@testcompany.com"]},
        "recommended_package": {
            "description": "Custom bot build",
            "delivery": "1 week",
            "price_range": "$500",
        },
        "research_summary": "Recent Twitter discussion mentions automation challenges.",
    }

    draft = delivery_agent.draft_email(brief_with_research)
    assert "Recent Twitter discussion" in draft["body"]


def test_draft_email_omits_personalization_when_research_summary_absent(
    delivery_agent,
):
    """Test Task 5: draft_email() omits personalization when research_summary is absent."""
    brief_without_research = {
        "domain": "testcompany.com",
        "pain_points": ["manual data entry"],
        "contacts": {"emails": ["test@testcompany.com"]},
        "recommended_package": {
            "description": "Custom bot build",
            "delivery": "1 week",
            "price_range": "$500",
        },
    }

    draft = delivery_agent.draft_email(brief_without_research)
    assert "Recent Twitter discussion" not in draft["body"]


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
            "url": "https://localplumbing.com/contact",
            "domain": "localplumbing.com",
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
    assert agent.scanner.leads[0]["url"] == "https://localplumbing.com/contact"


def test_ceo_approve_drafts_auto_sends_high_confidence_local():
    """Test: approve_drafts() approves high-confidence local business drafts."""
    os.environ["MECOS_ENABLE_OUTREACH"] = "true"

    from ceo_agent import CeoAgent
    from memory_system import MemorySystem
    from outreach.outreach_agent import OutreachAgent

    memory = MemorySystem()
    outreach = OutreachAgent(memory=memory)
    ceo = CeoAgent(memory=memory, revenue_ledger=outreach.revenue_ledger)
    ceo.attach_outreach(outreach)

    for f in outreach.delivery_agent.outbox_dir.glob("*.json"):
        f.unlink()

    high_confidence_draft = {
        "type": "email",
        "to": "owner@localplumbing.com",
        "subject": "Quick automation idea for localplumbing.com",
        "body": ("Hi there, I noticed your local plumbing business might benefit from automated scheduling "
                 "and customer notifications. This is a test email to verify CEO approval rules work "
                 "correctly for high-confidence local business prospects seeking automation solutions."),
        "status": "pending_review",
        "lead_brief": {
            "url": "https://localplumbing.com",
            "domain": "localplumbing.com",
            "contacts": {
                "emails": ["owner@localplumbing.com"],
                "email_source": "website_scrape",
                "email_confidence": "high",
            },
            "local_business_score": 5,
            "enterprise_penalty": 0,
        },
    }

    outreach.delivery_agent.save_draft(high_confidence_draft)
    result = asyncio.run(ceo.approve_drafts())

    assert len(result["auto_send"]) == 1
    assert result["auto_send"][0]["status"] == "pending_send"


def test_ceo_approve_drafts_flags_low_confidence():
    """Test: approve_drafts() flags low-confidence drafts for review."""
    os.environ["MECOS_ENABLE_OUTREACH"] = "true"

    from ceo_agent import CeoAgent
    from memory_system import MemorySystem
    from outreach.outreach_agent import OutreachAgent

    memory = MemorySystem()
    outreach = OutreachAgent(memory=memory)
    ceo = CeoAgent(memory=memory, revenue_ledger=outreach.revenue_ledger)
    ceo.attach_outreach(outreach)

    for f in outreach.delivery_agent.outbox_dir.glob("*.json"):
        f.unlink()

    low_confidence_draft = {
        "type": "email",
        "to": "owner@localplumbing.com",
        "subject": "Quick automation idea",
        "body": ("Hi there, this is a test email with low confidence email source that needs manual "
                 "review before sending. The body is intentionally long enough to pass the minimum "
                 "length requirement but the source is pattern_guess so it should be flagged."),
        "status": "pending_review",
        "lead_brief": {
            "url": "https://localplumbing.com",
            "domain": "localplumbing.com",
            "contacts": {
                "emails": ["owner@localplumbing.com"],
                "email_source": "pattern_guess",
                "email_confidence": "low",
            },
            "local_business_score": 5,
            "enterprise_penalty": 0,
        },
    }

    outreach.delivery_agent.save_draft(low_confidence_draft)
    result = asyncio.run(ceo.approve_drafts())

    assert len(result["flag_review"]) == 1


def test_ceo_approve_drafts_rejects_aggregator_domain():
    """Test: approve_drafts() rejects drafts to aggregator domains."""
    os.environ["MECOS_ENABLE_OUTREACH"] = "true"

    from ceo_agent import CeoAgent
    from memory_system import MemorySystem
    from outreach.outreach_agent import OutreachAgent

    memory = MemorySystem()
    outreach = OutreachAgent(memory=memory)
    ceo = CeoAgent(memory=memory, revenue_ledger=outreach.revenue_ledger)
    ceo.attach_outreach(outreach)

    for f in outreach.delivery_agent.outbox_dir.glob("*.json"):
        f.unlink()

    aggregator_draft = {
        "type": "email",
        "to": "user@reddit.com",
        "subject": "Test subject",
        "body": ("This is a test email body with sufficient length for validation purposes "
                 "and meets the minimum 200 character requirement for CEO approval rules "
                 "testing aggregator domain rejection in the outreach system."),
        "status": "pending_review",
        "lead_brief": {
            "url": "https://reddit.com/r/somepost",
            "domain": "reddit.com",
            "contacts": {
                "emails": ["user@reddit.com"],
                "email_source": "website_scrape",
                "email_confidence": "high",
            },
            "local_business_score": 5,
            "enterprise_penalty": 0,
        },
    }

    outreach.delivery_agent.save_draft(aggregator_draft)
    result = asyncio.run(ceo.approve_drafts())

    assert len(result["reject"]) == 1
    assert result["reject"][0]["status"] == "skipped_bad_lead"


def test_scheduler_respects_circuit_breaker():
    """Test: scheduler skips batch when CEO circuit breaker is active."""
    os.environ["MECOS_ENABLE_OUTREACH"] = "true"

    from ceo_agent import CeoAgent
    from memory_system import MemorySystem
    from outreach.outreach_agent import OutreachAgent
    from outreach.scheduler import OutreachScheduler

    memory = MemorySystem()
    outreach = OutreachAgent(memory=memory)
    ceo = CeoAgent(memory=memory, revenue_ledger=outreach.revenue_ledger)
    ceo.attach_outreach(outreach)
    ceo.outreach_paused = True

    scheduler = OutreachScheduler(outreach_agent=outreach, ceo_agent=ceo)
    result = asyncio.run(scheduler._run_batch())

    assert result["status"] == "skipped"
    assert "circuit_breaker" in result.get("reason", "")


def test_scheduler_rates_records_sends():
    """Test: scheduler tracks hourly send rate limits."""
    os.environ["MECOS_ENABLE_OUTREACH"] = "true"

    from outreach.scheduler import OutreachScheduler

    scheduler = OutreachScheduler.__new__(OutreachScheduler)
    scheduler._sent_timestamps = []
    scheduler.hourly_limit = 3

    assert scheduler._can_send() is True
    scheduler._record_send()
    scheduler._record_send()
    scheduler._record_send()
    assert scheduler._can_send() is False


def test_scrapling_adapter_fetch_returns_ok_on_success():
    """Test: scrapling_adapter.fetch returns ok=True on successful scrape."""
    import sys
    from unittest.mock import MagicMock, patch

    mock_response = MagicMock()
    mock_response.get_text.return_value = "Contact us at test@example.com"
    mock_response.get_page_html.return_value = "<html><body>Contact us at test@example.com</body></html>"
    mock_response.status_code = 200

    mock_fetcher = MagicMock()
    mock_fetcher.fetch.return_value = mock_response

    mock_scrapling = MagicMock()
    mock_scrapling.Fetcher = MagicMock(return_value=mock_fetcher)

    with patch.dict(sys.modules, {"scrapling": mock_scrapling}):
        if "outreach.scrapling_adapter" in sys.modules:
            del sys.modules["outreach.scrapling_adapter"]

        from outreach.scrapling_adapter import ScraplingAdapter
        adapter = ScraplingAdapter()
        adapter._fetcher = None
        result = adapter.fetch("https://example.com")

        assert result["ok"] is True
        assert "test@example.com" in result["text"]


def test_scrapling_adapter_fallback_to_requests_on_scrapling_failure():
    """Test: scrapling_adapter falls back to requests when scrapling fails."""
    import sys
    from unittest.mock import MagicMock, patch

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Fallback content</body></html>"

    mock_fetcher = MagicMock()
    mock_fetcher.fetch.side_effect = Exception("Scrapling failed")

    mock_scrapling = MagicMock()
    mock_scrapling.Fetcher = MagicMock(return_value=mock_fetcher)

    with patch.dict(sys.modules, {"scrapling": mock_scrapling}):
        if "outreach.scrapling_adapter" in sys.modules:
            del sys.modules["outreach.scrapling_adapter"]

        with patch("outreach.scrapling_adapter.requests.get", return_value=mock_response):
            from outreach.scrapling_adapter import ScraplingAdapter
            adapter = ScraplingAdapter()
            adapter._fetcher = None
            result = adapter.fetch("https://example.com")

            assert result["ok"] is True


def test_scrapling_adapter_returns_false_on_all_failures():
    """Test: scrapling_adapter returns ok=False when both methods fail."""
    import sys
    from unittest.mock import MagicMock, patch

    mock_fetcher = MagicMock()
    mock_fetcher.fetch.side_effect = Exception("Scrapling failed")

    mock_scrapling = MagicMock()
    mock_scrapling.Fetcher = MagicMock(return_value=mock_fetcher)

    with patch.dict(sys.modules, {"scrapling": mock_scrapling}):
        if "outreach.scrapling_adapter" in sys.modules:
            del sys.modules["outreach.scrapling_adapter"]

        with patch("outreach.scrapling_adapter.requests.get", side_effect=Exception("Network error")):
            from outreach.scrapling_adapter import ScraplingAdapter
            adapter = ScraplingAdapter()
            adapter._fetcher = None
            result = adapter.fetch("https://example.com")

            assert result["ok"] is False
            assert "error" in result


def test_scrapling_adapter_singleton_returns_same_instance():
    """Test: scrapling_adapter singleton pattern returns same instance."""
    from outreach.scrapling_adapter import ScraplingAdapter

    adapter1 = ScraplingAdapter()
    adapter2 = ScraplingAdapter()

    assert adapter1 is adapter2
