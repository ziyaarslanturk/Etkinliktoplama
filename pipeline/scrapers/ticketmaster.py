"""Ticketmaster Discovery API (TICKETMASTER_API_KEY yoksa atlanır)."""
from __future__ import annotations

import time

from ..context import Context, SkipSource
from ..httpclient import fetch_json, log
from ..normalize import make_event
from ..taxonomy import classify

NAME = "ticketmaster"
BASE = "https://app.ticketmaster.com/discovery/v2/events.json"
KEYWORDS = ["camping", "camp festival", "caravan", "motorhome", "tiny house", "bushcraft", "trail running",
            "trekking", "hiking festival", "climbing festival", "outdoor festival", "music camp",
            "outdoor concert", "open air"]
PAGE_SIZE = 200
MAX_PAGES = 4  # Discovery API: size * page < 1000


def _best_image(images) -> str | None:
    best, w = None, -1
    for im in images or []:
        try:
            if im.get("ratio") in ("16_9", "3_2") and int(im.get("width", 0)) > w:
                best, w = im.get("url"), int(im.get("width", 0))
        except (TypeError, ValueError, AttributeError):
            continue
    return best


def map_event(ev: dict) -> dict | None:
    name = ev.get("name")
    cls = classify(name)
    if not cls:
        return None
    dates = ev.get("dates") or {}
    start = dates.get("start") or {}
    end = dates.get("end") or {}
    venues = ((ev.get("_embedded") or {}).get("venues")) or [{}]
    v = venues[0] or {}
    loc = v.get("location") or {}
    price = (ev.get("priceRanges") or [None])[0]
    fee = None
    if isinstance(price, dict) and price.get("min") is not None:
        fee = f"{price.get('min')}-{price.get('max', price.get('min'))} {price.get('currency', '')}".strip()
    promoter = (ev.get("promoter") or {}).get("name")
    tags = []
    for c in ev.get("classifications") or []:
        for k in ("segment", "genre", "subGenre"):
            n = (c.get(k) or {}).get("name")
            if n and n.lower() != "undefined":
                tags.append(n)
    return make_event(
        source=NAME, title=name, interest=cls[0], sub_type=cls[1],
        start_date=start.get("localDate"), end_date=end.get("localDate"),
        start_time=start.get("localTime"), timezone=dates.get("timezone"),
        country_code=((v.get("country") or {}).get("countryCode")),
        city=(v.get("city") or {}).get("name"), venue=v.get("name"),
        address=(v.get("address") or {}).get("line1"),
        lat=loc.get("latitude"), lng=loc.get("longitude"),
        poster_url=_best_image(ev.get("images")), summary=ev.get("info") or ev.get("pleaseNote"),
        organizer=promoter, entry_fee=fee, tags=tags,
        official_url=ev.get("url"), ticket_url=ev.get("url"), verified=True,
    )


def fetch(ctx: Context) -> list[dict]:
    key = ctx.secret("TICKETMASTER_API_KEY")
    if not key:
        raise SkipSource("TICKETMASTER_API_KEY tanımlı değil")
    out: dict[str, dict] = {}
    for kw in KEYWORDS:
        for page in range(MAX_PAGES):
            if ctx.expired():
                return list(out.values())
            data = fetch_json(BASE, params={
                "apikey": key, "keyword": kw, "size": PAGE_SIZE, "page": page, "sort": "date,asc",
                "startDateTime": ctx.today.isoformat() + "T00:00:00Z"}, pause=0.3)
            if not isinstance(data, dict):
                break
            items = ((data.get("_embedded") or {}).get("events")) or []
            for raw in items:
                try:
                    e = map_event(raw)
                except Exception as exc:
                    log(f"ticketmaster kayıt hatası: {type(exc).__name__}")
                    continue
                if e:
                    out[e["id"]] = e
            total_pages = int(((data.get("page") or {}).get("totalPages")) or 0)
            if page + 1 >= total_pages:
                break
    return list(out.values())
