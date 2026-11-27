"""
Recreation.gov (RIDB) API Scraper.
Returns [] immediately if RIDB_API_KEY is missing.
"""

import logging
from typing import List, Dict, Any
from pipeline.config import get_ridb_key

logger = logging.getLogger("pipeline.scrapers.recreation_gov")

def scrape_recreation_gov() -> List[Dict[str, Any]]:
    key = get_ridb_key()
    if not key:
        logger.info("RIDB API key is not configured. Skipping Recreation.gov scraper cleanly.")
        return []

    return []
