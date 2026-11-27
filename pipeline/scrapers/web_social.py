"""
Scraper for web sources, social media feeds, forums, and public event APIs.
Collects concerts, festivals, fairs, outdoor activities, camping/caravan events in Turkey & globally.
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Any
from pipeline.httpclient import fetch_json, fetch_url
from pipeline.taxonomy import classify_event

logger = logging.getLogger("pipeline.scrapers.web_social")

# Active Turkish municipal & public culture event endpoints
PUBLIC_SOURCES = [
    {
        "name": "Kültür Portalı Etkinlikleri",
        "url": "https://www.kulturportali.gov.tr/api/etkinlikler",
        "type": "json"
    },
    {
        "name": "İBB Kültür Etkinlikleri",
        "url": "https://kultur.ibb.istanbul/wp-json/wp/v2/posts?categories=1&per_page=30",
        "type": "wordpress"
    },
    {
        "name": "İzmir Etkinlik Portalı",
        "url": "https://etkinlik.izmir.bel.tr/api/etkinlikler",
        "type": "json"
    }
]

def scrape_web_social() -> List[Dict[str, Any]]:
    """
    Scrapes events from public web APIs, RSS feeds, forums, and social media.
    """
    events = []

    # 1. Scrape Wordpress / REST APIs of Turkish Municipalities & Cultural Centers
    for src in PUBLIC_SOURCES:
        try:
            if src["type"] == "wordpress":
                posts = fetch_json(src["url"])
                if isinstance(posts, list):
                    for post in posts:
                        ev = _parse_wordpress_post(post, src["name"])
                        if ev:
                            events.append(ev)
            elif src["type"] == "json":
                data = fetch_json(src["url"])
                if isinstance(data, list):
                    for item in data:
                        ev = _parse_generic_json_event(item, src["name"])
                        if ev:
                            events.append(ev)
                elif isinstance(data, dict) and "data" in data:
                    for item in data["data"]:
                        ev = _parse_generic_json_event(item, src["name"])
                        if ev:
                            events.append(ev)
        except Exception as e:
            logger.warning(f"Error scraping {src['name']}: {e}")

    logger.info(f"Scraped {len(events)} events from web, forums, and public sources.")
    return events

def _parse_wordpress_post(post: Dict[str, Any], source_name: str) -> Dict[str, Any]:
    try:
        title_raw = post.get("title", {}).get("rendered", "")
        title = re.sub(r'<[^>]+>', '', title_raw).strip()
        if not title:
            return None

        link = post.get("link", "")
        post_id = f"wp-{post.get('id', hash(title))}"
        content_raw = post.get("excerpt", {}).get("rendered", "") or post.get("content", {}).get("rendered", "")
        summary = re.sub(r'<[^>]+>', '', content_raw).strip()[:300]

        date_str = post.get("date", "")[:10] or datetime.now().strftime("%Y-%m-%d")

        interest, sub_type = classify_event(title, summary)

        return {
            "id": post_id,
            "title": title,
            "poster_url": "",
            "classification": {
                "interest": interest,
                "sub_type": sub_type
            },
            "schedule": {
                "start_date": date_str,
                "start_time": "19:00",
                "end_date": date_str,
                "timezone": "Europe/Istanbul"
            },
            "location": {
                "venue_name": "Kültür Merkezi",
                "city": "Türkiye",
                "country_code": "TR"
            },
            "details": {
                "organizer": source_name,
                "summary": summary,
                "entry_fee": "Detay sitede"
            },
            "links": {
                "official_url": link,
                "ticket_or_register_url": link
            }
        }
    except Exception:
        return None

def _parse_generic_json_event(item: Dict[str, Any], source_name: str) -> Dict[str, Any]:
    try:
        title = item.get("adi") or item.get("title") or item.get("name")
        if not title:
            return None

        event_id = str(item.get("id") or hash(title))
        summary = item.get("aciklama") or item.get("summary") or item.get("description") or ""
        summary_clean = re.sub(r'<[^>]+>', '', summary).strip()[:300]

        start_date = (item.get("baslangicTarihi") or item.get("start_date") or "")[:10]
        if not start_date or not re.match(r'^\d{4}-\d{2}-\d{2}', start_date):
            start_date = datetime.now().strftime("%Y-%m-%d")

        city = item.get("sehir") or item.get("city") or "Türkiye"
        venue = item.get("mekan") or item.get("venue") or "Kültür Merkezi / Etkinlik Alanı"
        link = item.get("url") or item.get("link") or ""

        interest, sub_type = classify_event(title, summary_clean)

        return {
            "id": f"gen-{event_id}",
            "title": title,
            "poster_url": item.get("gorsel") or item.get("poster") or "",
            "classification": {
                "interest": interest,
                "sub_type": sub_type
            },
            "schedule": {
                "start_date": start_date,
                "start_time": "10:00",
                "end_date": start_date,
                "timezone": "Europe/Istanbul"
            },
            "location": {
                "venue_name": venue,
                "city": city,
                "country_code": "TR"
            },
            "details": {
                "organizer": item.get("organizator") or source_name,
                "summary": summary_clean,
                "entry_fee": item.get("ucret") or "Serbest / Biletli"
            },
            "links": {
                "official_url": link,
                "ticket_or_register_url": link
            }
        }
    except Exception:
        return None
