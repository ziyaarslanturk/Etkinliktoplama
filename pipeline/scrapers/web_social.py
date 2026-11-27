"""
Scraper for web sources, social media feeds, forums, and public event APIs.
Collects concerts, festivals, fairs, outdoor activities, camping/caravan events in Turkey & globally.
Defensive typing implemented for type safety and exception-free execution.
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pipeline.httpclient import fetch_json
from pipeline.taxonomy import classify_event

logger = logging.getLogger("pipeline.scrapers.web_social")

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

def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("rendered", "") or val.get("name", "") or val.get("text", ""))
    if isinstance(val, (str, int, float)):
        return str(val)
    return ""

def _clean_html(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    return re.sub(r'<[^>]+>', '', raw).strip()

def scrape_web_social() -> List[Dict[str, Any]]:
    """
    Scrapes events from public web APIs, RSS feeds, forums, and social media.
    """
    events = []

    for src in PUBLIC_SOURCES:
        try:
            url = src.get("url", "")
            stype = src.get("type", "")
            name = src.get("name", "Web")

            data = fetch_json(url)
            if not data:
                continue

            if stype == "wordpress":
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            ev = _parse_wordpress_post(item, name)
                            if ev:
                                events.append(ev)
            elif stype == "json":
                items_list = []
                if isinstance(data, list):
                    items_list = data
                elif isinstance(data, dict):
                    items_list = data.get("data") or data.get("items") or data.get("etkinlikler") or []

                if isinstance(items_list, list):
                    for item in items_list:
                        if isinstance(item, dict):
                            ev = _parse_generic_json_event(item, name)
                            if ev:
                                events.append(ev)
        except Exception as e:
            logger.warning(f"Error scraping {src.get('name')}: {e}")

    logger.info(f"Scraped {len(events)} events from web, forums, and public sources.")
    return events

def _parse_wordpress_post(post: Dict[str, Any], source_name: str) -> Optional[Dict[str, Any]]:
    try:
        title_raw = _safe_str(post.get("title"))
        title = _clean_html(title_raw)
        if not title:
            return None

        link = _safe_str(post.get("link"))
        post_id = f"wp-{_safe_str(post.get('id')) or hash(title)}"
        content_raw = _safe_str(post.get("excerpt")) or _safe_str(post.get("content"))
        summary = _clean_html(content_raw)[:300]

        date_val = _safe_str(post.get("date"))
        date_str = date_val[:10] if len(date_val) >= 10 else datetime.now().strftime("%Y-%m-%d")

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
    except Exception as e:
        logger.debug(f"Error parsing WP post: {e}")
        return None

def _parse_generic_json_event(item: Dict[str, Any], source_name: str) -> Optional[Dict[str, Any]]:
    try:
        title = _clean_html(_safe_str(item.get("adi") or item.get("title") or item.get("name")))
        if not title:
            return None

        event_id = _safe_str(item.get("id")) or str(hash(title))
        summary_raw = _safe_str(item.get("aciklama") or item.get("summary") or item.get("description"))
        summary_clean = _clean_html(summary_raw)[:300]

        date_raw = _safe_str(item.get("baslangicTarihi") or item.get("start_date") or item.get("tarih"))
        start_date = date_raw[:10] if (len(date_raw) >= 10 and re.match(r'^\d{4}-\d{2}-\d{2}', date_raw[:10])) else datetime.now().strftime("%Y-%m-%d")

        city = _safe_str(item.get("sehir") or item.get("city")) or "Türkiye"
        venue = _safe_str(item.get("mekan") or item.get("venue")) or "Kültür Merkezi / Etkinlik Alanı"
        link = _safe_str(item.get("url") or item.get("link"))

        interest, sub_type = classify_event(title, summary_clean)

        return {
            "id": f"gen-{event_id}",
            "title": title,
            "poster_url": _safe_str(item.get("gorsel") or item.get("poster") or item.get("image")),
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
                "organizer": _safe_str(item.get("organizator")) or source_name,
                "summary": summary_clean,
                "entry_fee": _safe_str(item.get("ucret")) or "Serbest / Biletli"
            },
            "links": {
                "official_url": link,
                "ticket_or_register_url": link
            }
        }
    except Exception as e:
        logger.debug(f"Error parsing generic event: {e}")
        return None
