"""
MECOS Outreach - Twenty CRM Bridge
GraphQL integration for persistent lead, brief, draft, and payment storage.
"""
from outreach.twenty.schema import ALL_OBJECTS, ObjectDef
from outreach.twenty.setup_twenty import TwentySetup
from outreach.twenty.twenty_bridge import TwentyBridge

__all__ = ["ALL_OBJECTS", "ObjectDef", "TwentyBridge", "TwentySetup"]
