"""Recreation.gov RIDB /events (RIDB_API_KEY yoksa atlanır). ABD federal alanları.

Alan adları RIDB belgelerinde sürüme göre değişebildiği için birden çok aday ad denenir;
başlık, başlangıç tarihi ve resmî URL bulunamayan kayıtlar atlanır.
"""
from __future__ import annotations

from ..context import Context, SkipSource
from ..httpclient import fetch_json, log
from ..normalize import make_event
from ..taxonomy import classify

NAME = "recreation_gov"
BASE = "https://ridb.recreation.gov/api/v1/events"
LIMIT = 50
MAX_PAGES = 40  # hız sınırı: dakikada 50 istek


def pick(d: dict, *names):
    for n in names:
        v = d.get(n)
        if v not in (None, ""):
            return v
    return None


def map_event(r: dict) -> dict | None:
    title = pick(r, "EventName", "Name", "EventTitle")
    desc = pick(r, "EventDescription", "Description")
    cls = classify(f"{title or ''} {desc or ''}") if title else None
    if not cls:
        return None
    return make_event(
        source=NAME, title=title, interest=cls[0], sub_type=cls[1],
        start_date=pick(r, "EventStartDate", "StartDate", "EventDate", "EventDateStart"),
        end_date=pick(r, "EventEndDate", "EndDate", "EventDateEnd"),
        start_time=pick(r, "EventStartDate", "StartDate", "EventDate"),
        country_code="US", city=pick(r, "EventCity", "City"), venue=pick(r, "EventLocation", "FacilityName"),
        lat=pick(r, "EventLatitude", "Latitude"), lng=pick(r, "EventLongitude", "Longitude"),
        summary=desc, organizer=pick(r, "OrgName", "Organization"),
        entry_fee=pick(r, "EventFee", "Fee"),
        official_url=pick(r, "EventURL", "EventUrl", "URL", "Url", "Link"), verified=True,
    )


def fetch(ctx: Context) -> list[dict]:
    key = ctx.secret("RIDB_API_KEY")
    if not key:
        raise SkipSource("RIDB_API_KEY tanımlı değil")
    out: dict[str, dict] = {}
    offset = 0
    for _ in range(MAX_PAGES):
        if ctx.expired():
            break
        data = fetch_json(BASE, params={"limit": LIMIT, "offset": offset}, headers={"apikey": key}, pause=1.3)
        if not isinstance(data, dict):
            break
        rows = data.get("RECDATA") or []
        for r in rows:
            try:
                e = map_event(r) if isinstance(r, dict) else None
            except Exception as exc:
                log(f"recreation_gov kayıt hatası: {type(exc).__name__}")
                continue
            if e:
                out[e["id"]] = e
        total = ((data.get("METADATA") or {}).get("RESULTS") or {}).get("TOTAL_COUNT") or 0
        offset += LIMIT
        if not rows or offset >= int(total):
            break
    return list(out.values())
