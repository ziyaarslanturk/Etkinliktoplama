"""
Ticketmaster API Scraper.
Returns [] immediately if TICKETMASTER_API_KEY is missing.
"""

import logging
from typing import List, Dict, Any
from pipeline.config import get_ticketmaster_key

logger = logging.getLogger("pipeline.scrapers.ticketmaster")

def scrape_ticketmaster() -> List[Dict[str, Any]]:
    key = get_ticketmaster_key()
    if not key:
        logger.info("Ticketmaster API key is not configured. Skipping Ticketmaster scraper cleanly.")
        return []

    return []
