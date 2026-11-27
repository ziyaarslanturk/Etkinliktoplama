"""
Main entry point for Etkinliktoplama data collection pipeline.
Runs enabled scrapers, normalizes collected raw data, and writes output files.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Any

from pipeline.config import load_sources_config, get_output_dir
from pipeline.normalize import normalize_event
from pipeline.scrapers import (
    scrape_community,
    scrape_federations,
    scrape_local_official,
    scrape_pages,
    scrape_recreation_gov,
    scrape_ticketmaster,
    scrape_wikidata,
    scrape_web_social,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pipeline.main")

SCRAPER_MAP = {
    "community": scrape_community,
    "web_social": scrape_web_social,
    "ticketmaster": scrape_ticketmaster,
    "recreation_gov": scrape_recreation_gov,
    "wikidata": scrape_wikidata,
    "local_official": scrape_local_official,
    "federations": scrape_federations,
    "pages": scrape_pages,
}

def run_pipeline():
    logger.info("Starting Etkinliktoplama data collection pipeline...")
    sources = load_sources_config()
    all_raw_events: List[Dict[str, Any]] = []

    for src in sources:
        sid = src.get("id")
        if not src.get("enabled", True):
            logger.info(f"Skipping disabled source: {sid}")
            continue

        scraper_func = SCRAPER_MAP.get(sid)
        if not scraper_func:
            logger.warning(f"No scraper implementation registered for source: {sid}")
            continue

        logger.info(f"Running scraper for: {sid}")
        try:
            items = scraper_func()
            logger.info(f"Source '{sid}' returned {len(items)} items.")
            all_raw_events.extend(items)
        except Exception as e:
            logger.error(f"Error executing scraper '{sid}': {e}", exc_info=True)

    logger.info(f"Total raw events gathered: {len(all_raw_events)}")

    # Normalize events
    normalized_events: List[Dict[str, Any]] = []
    seen_ids = set()

    for raw in all_raw_events:
        norm = normalize_event(raw)
        if not norm:
            continue

        eid = norm.get("id")
        if eid in seen_ids:
            continue

        seen_ids.add(eid)
        normalized_events.append(norm)

    logger.info(f"Total normalized unique events: {len(normalized_events)}")

    # Sort events by start_date
    normalized_events.sort(key=lambda x: (x.get("schedule", {}).get("start_date", ""), x.get("schedule", {}).get("start_time", "")))

    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    # Write global events.json
    main_output = os.path.join(output_dir, "events.json")
    with open(main_output, "w", encoding="utf-8") as f:
        json.dump({"events": normalized_events, "generated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)

    logger.info(f"Wrote {len(normalized_events)} events to {main_output}")

    # Group events by country code (events/<CC>.json)
    by_country: Dict[str, List[Dict[str, Any]]] = {}
    for ev in normalized_events:
        cc = (ev.get("location", {}).get("country_code") or "TR").upper()
        by_country.setdefault(cc, []).append(ev)

    events_dir = os.path.join(output_dir, "events")
    os.makedirs(events_dir, exist_ok=True)

    for cc, ev_list in by_country.items():
        cc_file = os.path.join(events_dir, f"{cc}.json")
        with open(cc_file, "w", encoding="utf-8") as f:
            json.dump({"events": ev_list, "generated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        logger.info(f"Wrote {len(ev_list)} events to {cc_file}")

    logger.info("Pipeline completed successfully!")

if __name__ == "__main__":
    run_pipeline()
