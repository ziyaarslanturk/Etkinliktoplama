"""
Event normalization module for Etkinliktoplama data pipeline.
Normalizes raw event items from scrapers into standardized JSON schema.
Provides normalize_event, normalize_item, normalize_record, and normalize.
"""

import re
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

from .config import now_iso, today_utc
from .taxonomy import (
    ISO_COUNTRIES,
    VALID_INTERESTS,
    is_valid_class,
    classify_event,
    normalize_interest,
    normalize_subtype
)

def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (str, int, float)):
        return re.sub(r'\s+', ' ', str(val)).strip()
    return ""

def _format_date(date_raw: Any) -> str:
    val = _clean_str(date_raw)
    if not val:
        return today_utc()
    # Match YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', val)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return today_utc()

def normalize_event(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalizes a raw event dictionary into standardized pipeline event schema.
    Returns None if essential fields (title) are missing.
    """
    if not isinstance(raw, dict):
        return None

    title = _clean_str(raw.get("title") or raw.get("name") or raw.get("adi"))
    if not title:
        return None

    # Schedule
    sch = raw.get("schedule") if isinstance(raw.get("schedule"), dict) else {}
    start_date = _format_date(sch.get("start_date") or raw.get("start_date") or raw.get("baslangicTarihi") or raw.get("date"))
    end_date = _format_date(sch.get("end_date") or raw.get("end_date") or start_date)
    start_time = _clean_str(sch.get("start_time") or raw.get("start_time") or "10:00")
    timezone = _clean_str(sch.get("timezone") or raw.get("timezone") or "Europe/Istanbul")

    # ID
    event_id = _clean_str(raw.get("id"))
    if not event_id:
        hash_seed = f"{title}-{start_date}".encode('utf-8')
        event_id = f"ev-{hashlib.md5(hash_seed).hexdigest()[:12]}"

    # Classification
    cls = raw.get("classification") if isinstance(raw.get("classification"), dict) else {}
    interest = _clean_str(cls.get("interest") or raw.get("category") or raw.get("interest")).lower()
    sub_type = _clean_str(cls.get("sub_type") or raw.get("sub_type"))

    if not interest or interest not in VALID_INTERESTS:
        summary_text = _clean_str(raw.get("details", {}).get("summary") if isinstance(raw.get("details"), dict) else raw.get("summary"))
        interest, inferred_subtype = classify_event(title, summary_text)
        if not sub_type:
            sub_type = inferred_subtype

    interest = normalize_interest(interest)
    sub_type = normalize_subtype(sub_type)

    # Location
    loc = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    venue_name = _clean_str(loc.get("venue_name") or raw.get("venue") or raw.get("mekan") or "Etkinlik Alanı")
    city = _clean_str(loc.get("city") or raw.get("city") or raw.get("sehir") or "Türkiye")
    country_code = _clean_str(loc.get("country_code") or raw.get("country_code") or "TR").upper()
    if country_code not in ISO_COUNTRIES:
        country_code = "TR"

    # Details
    det = raw.get("details") if isinstance(raw.get("details"), dict) else {}
    organizer = _clean_str(det.get("organizer") or raw.get("organizer") or raw.get("organizator") or "Düzenleyici")
    summary = _clean_str(det.get("summary") or raw.get("summary") or raw.get("aciklama"))[:500]
    entry_fee = _clean_str(det.get("entry_fee") or raw.get("entry_fee") or raw.get("ucret") or "Biletli / Detay Sitede")

    # Links
    lk = raw.get("links") if isinstance(raw.get("links"), dict) else {}
    official_url = _clean_str(lk.get("official_url") or raw.get("url") or raw.get("link"))
    ticket_url = _clean_str(lk.get("ticket_or_register_url") or raw.get("ticket_url") or official_url)

    # Poster
    poster_url = _clean_str(raw.get("poster_url") or raw.get("image") or raw.get("gorsel"))

    return {
        "id": event_id,
        "title": title,
        "poster_url": poster_url,
        "classification": {
            "interest": interest,
            "sub_type": sub_type
        },
        "schedule": {
            "start_date": start_date,
            "start_time": start_time if start_time else "10:00",
            "end_date": end_date,
            "timezone": timezone if timezone else "Europe/Istanbul"
        },
        "location": {
            "venue_name": venue_name,
            "city": city,
            "country_code": country_code
        },
        "details": {
            "organizer": organizer,
            "summary": summary,
            "entry_fee": entry_fee
        },
        "links": {
            "official_url": official_url,
            "ticket_or_register_url": ticket_url
        }
    }

# Aliases for backwards compatibility
normalize_item = normalize_event
normalize_record = normalize_event
normalize = normalize_event
