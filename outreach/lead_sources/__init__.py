"""
MECOS Outreach - Lead Sources
Industry-specific scrapers for high-visibility communities.
"""

from .saas import SaaSLeadSource
from .ecommerce import EcommerceLeadSource
from .agencies import AgencyLeadSource
from .creators import CreatorLeadSource
from .solopreneurs import SolopreneurLeadSource

INDUSTRY_SOURCES = {
    "saas": SaaSLeadSource,
    "ecommerce": EcommerceLeadSource,
    "agencies": AgencyLeadSource,
    "creators": CreatorLeadSource,
    "solopreneurs": SolopreneurLeadSource,
}