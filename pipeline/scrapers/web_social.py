"""
Web, Forum and Open Portal Scraper for Events.
Collects events from public websites, outdoor/camping forums, RSS feeds, and municipal culture portals.
Requires ZERO API keys. Completely free and resilient.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
from pipeline.httpclient import fetch_url, fetch_json
from pipeline.taxonomy import classify_event

logger = logging.getLogger("pipeline.scrapers.web_social")

OPEN_WEB_SOURCES = [
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
    },
    {
        "name": "Doğa ve Kamp Etkinlik Akışı",
        "url": "https://www.gezenbilir.com/forums/-/index.rss",
        "type": "rss"
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
    Scrapes events from open web portals, culture feeds, RSS feeds, and forums.
    Requires no API keys.
    """
    events = []

    for src in OPEN_WEB_SOURCES:
        try:
            url = src.get("url", "")
            stype = src.get("type", "")
            name = src.get("name", "Açık Web")

            if stype == "wordpress":
                data = fetch_json(url)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            ev = _parse_wordpress_post(item, name)
                            if ev:
                                events.append(ev)
            elif stype == "json":
                data = fetch_json(url)
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
            elif stype == "rss":
                raw_xml = fetch_url(url)
                if raw_xml:
                    parsed_rss = _parse_rss_feed(raw_xml, name)
                    events.extend(parsed_rss)

        except Exception as e:
            logger.warning(f"Error scraping open source {src.get('name')}: {e}")

    logger.info(f"Scraped {len(events)} events from open web and forums.")
    return events

def _parse_wordpress_post(post: Dict[str, Any], source_name: str) -> Optional[Dict[str, Any]]:
    try:
        title = _clean_html(_safe_str(post.get("title")))
        if not title:
            return None

        link = _safe_str(post.get("link"))
        post_id = f"wp-{_safe_str(post.get('id')) or hash(title)}"
        summary = _clean_html(_safe_str(post.get("excerpt")) or _safe_str(post.get("content")))[:300]

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
                "venue_name": "Kültür Merkezi / Açık Alan",
                "city": "Türkiye",
                "country_code": "TR"
            },
            "details": {
                "organizer": source_name,
                "summary": summary,
                "entry_fee": "Açık Etkinlik / Detay Sitede"
            },
            "links": {
                "official_url": link,
                "ticket_or_register_url": link
            }
        }
    except Exception:
        return None

def _parse_generic_json_event(item: Dict[str, Any], source_name: str) -> Optional[Dict[str, Any]]:
    try:
        title = _clean_html(_safe_str(item.get("adi") or item.get("title") or item.get("name")))
        if not title:
            return None

        event_id = _safe_str(item.get("id")) or str(hash(title))
        summary = _clean_html(_safe_str(item.get("aciklama") or item.get("summary") or item.get("description")))[:300]

        date_raw = _safe_str(item.get("baslangicTarihi") or item.get("start_date") or item.get("tarih"))
        start_date = date_raw[:10] if (len(date_raw) >= 10 and re.match(r'^\d{4}-\d{2}-\d{2}', date_raw[:10])) else datetime.now().strftime("%Y-%m-%d")

        city = _safe_str(item.get("sehir") or item.get("city")) or "Türkiye"
        venue = _safe_str(item.get("mekan") or item.get("venue")) or "Kültür Merkezi / Etkinlik Alanı"
        link = _safe_str(item.get("url") or item.get("link"))

        interest, sub_type = classify_event(title, summary)

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
                "summary": summary,
                "entry_fee": _safe_str(item.get("ucret")) or "Açık Etkinlik"
            },
            "links": {
                "official_url": link,
                "ticket_or_register_url": link
            }
        }
    except Exception:
        return None

def _parse_rss_feed(xml_text: str, source_name: str) -> List[Dict[str, Any]]:
    events = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")

            title = _clean_html(title_elem.text if title_elem is not None else "")
            if not title:
                continue

            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            summary = _clean_html(desc_elem.text if desc_elem is not None else "")[:300]

            interest, sub_type = classify_event(title, summary)
            today_str = datetime.now().strftime("%Y-%m-%d")

            events.append({
                "id": f"rss-{hash(title)}",
                "title": title,
                "poster_url": "",
                "classification": {
                    "interest": interest,
                    "sub_type": sub_type
                },
                "schedule": {
                    "start_date": today_str,
                    "start_time": "10:00",
                    "end_date": today_str,
                    "timezone": "Europe/Istanbul"
                },
                "location": {
                    "venue_name": "Forum / Etkinlik Duyurusu",
                    "city": "Türkiye",
                    "country_code": "TR"
                },
                "details": {
                    "organizer": source_name,
                    "summary": summary,
                    "entry_fee": "Forum Paylaşımı"
                },
                "links": {
                    "official_url": link,
                    "ticket_or_register_url": link
                }
            })
    except Exception as e:
        logger.debug(f"Error parsing RSS: {e}")
    return events
