"""Ham veriyi standart şemaya çevirir ve doğrular. Zorunlu alan eksikse None döner (sessizce atlanır)."""
from __future__ import annotations

import hashlib
import html
import re
from datetime import date, datetime
from urllib.parse import urlparse

from .config import now_iso, today_utc
from .taxonomy import ISO_COUNTRIES, is_valid_class

_TAG_RX = re.compile(r"<[^>]+>")
_WS_RX = re.compile(r"\s+")


def clean_text(v, limit: int | None = None) -> str | None:
    if v is None:
        return None
    s = html.unescape(_TAG_RX.sub(" ", str(v)))
    s = _WS_RX.sub(" ", s).strip()
    if not s:
        return None
    if limit and len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return s


def parse_date(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})", str(v))
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    except ValueError:
        return None


def parse_time(v) -> str | None:
    """HH:MM döndürür. Yalnızca tarih içeren veya tam 00:00 olan değerler None sayılır (uydurma saat yok)."""
    if v is None:
        return None
    m = re.search(r"(?:^|[T\s])(\d{2}):(\d{2})", str(v))
    if not m:
        return None
    h, mi = int(m[1]), int(m[2])
    if h > 23 or mi > 59 or (h == 0 and mi == 0):
        return None
    return f"{h:02d}:{mi:02d}"


def valid_url(u) -> str | None:
    if not u or not isinstance(u, str):
        return None
    u = u.strip()
    p = urlparse(u)
    if p.scheme in ("http", "https") and p.netloc and " " not in u:
        return u
    return None


def _num(v, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if lo <= f <= hi else None


def make_id(country: str, start: str, title: str) -> str:
    norm = re.sub(r"[^a-z0-9]+", "", title.casefold())
    return hashlib.sha256(f"{country}|{start}|{norm}".encode("utf-8")).hexdigest()[:20]


def _list(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        v = [v]
    out = []
    for x in v:
        t = clean_text(x, 120)
        if t and t not in out:
            out.append(t)
    return out


def make_event(*, source: str, title, interest, sub_type=None, start_date, end_date=None,
               country_code, official_url, city=None, venue=None, address=None, lat=None, lng=None,
               start_time=None, end_time=None, timezone=None, poster_url=None, summary=None,
               organizer=None, guests=None, target_audience=None, exhibitors=None, capacity=None,
               entry_fee=None, tags=None, ticket_url=None, verified=False, updated_at=None) -> dict | None:
    """Standart şemada etkinlik üretir; zorunlu alan yok/geçersizse None."""
    try:
        title = clean_text(title, 200)
        start = parse_date(start_date)
        end = parse_date(end_date) or start
        cc = str(country_code).strip().upper() if country_code else None
        official = valid_url(official_url)
        if not (title and start and end and cc and official):
            return None
        if cc not in ISO_COUNTRIES or end < start:
            return None
        if not is_valid_class(interest, sub_type if sub_type else None):
            if is_valid_class(interest, None):
                sub_type = None
            else:
                return None
        cap = None
        try:
            if capacity is not None and int(capacity) > 0:
                cap = int(capacity)
        except (TypeError, ValueError):
            cap = None
        la, ln = _num(lat, -90, 90), _num(lng, -180, 180)
        if la is None or ln is None:
            la = ln = None
        return {
            "id": make_id(cc, start, title),
            "title": title,
            "classification": {"interest": interest, "sub_type": sub_type or None},
            "poster_url": valid_url(poster_url),
            "schedule": {
                "start_date": start,
                "end_date": end,
                "start_time": parse_time(start_time),
                "end_time": parse_time(end_time),
                "timezone": clean_text(timezone, 64) or "UTC",
            },
            "location": {
                "country_code": cc,
                "city": clean_text(city, 120),
                "venue_name": clean_text(venue, 160),
                "address": clean_text(address, 240),
                "lat": la,
                "lng": ln,
            },
            "details": {
                "summary": clean_text(summary, 300),
                "organizer": clean_text(organizer, 160),
                "guests": _list(guests),
                "participants": {
                    "target_audience": _list(target_audience),
                    "exhibitors_or_brands": _list(exhibitors),
                    "estimated_capacity": cap,
                },
                "entry_fee": clean_text(entry_fee, 120),
                "tags": _list(tags),
            },
            "links": {"official_url": official, "ticket_or_register_url": valid_url(ticket_url)},
            "meta": {"source": source, "verified": bool(verified), "updated_at": updated_at or now_iso()},
        }
    except Exception:
        return None


def validate_event_dict(ev) -> bool:
    """Daha önce üretilmiş (ör. önceki yayından taşınan) bir kaydın şemaya uyup uymadığını denetler."""
    try:
        e = make_event(
            source=ev["meta"]["source"], title=ev["title"],
            interest=ev["classification"]["interest"], sub_type=ev["classification"]["sub_type"],
            start_date=ev["schedule"]["start_date"], end_date=ev["schedule"]["end_date"],
            country_code=ev["location"]["country_code"], official_url=ev["links"]["official_url"],
        )
        return e is not None and e["id"] == ev.get("id")
    except Exception:
        return False


def is_expired(ev: dict, today: date | None = None) -> bool:
    today = today or today_utc()
    s = ev["schedule"]
    last = s.get("end_date") or s.get("start_date")
    return last < today.isoformat()


def richness(ev: dict) -> int:
    """Yinelenen kayıtlardan hangisinin saklanacağını seçmek için doluluk puanı."""
    score = 0

    def walk(x):
        nonlocal score
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif x not in (None, "", [], False):
            score += 1

    walk(ev)
    return score
