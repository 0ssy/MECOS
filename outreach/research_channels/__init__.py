"""
MECOS Outreach - Research Channels
Adapter modules for on-demand social/web research using Agent-Reach.
"""
from .base import ResearchResult
from .reddit import research_reddit
from .twitter import research_twitter
from .web import research_web
from .youtube import research_youtube

__all__ = [
    "ResearchResult",
    "research_twitter",
    "research_youtube",
    "research_reddit",
    "research_web",
]