"""Topluluk / manuel JSON havuzu: community_events/*.json (geliştirici onaylı).

Dosya: standart şemada etkinlik listesi veya {"events": [...]}. '_' ile başlayan dosyalar yok sayılır.
"""
from __future__ import annotations

import json

from .. import config
from ..context import Context
from ..httpclient import log
from ..normalize import make_event

NAME = "community"


def from_schema(d: dict, source: str = NAME) -> dict | None:
    c, s, loc, det, lk = (d.get("classification") or {}), (d.get("schedule") or {}), (d.get("location") or {}), \
        (d.get("details") or {}), (d.get("links") or {})
    part = det.get("participants") or {}
    meta = d.get("meta") or {}
    return make_event(
        source=source, title=d.get("title"), interest=c.get("interest"), sub_type=c.get("sub_type"),
        start_date=s.get("start_date"), end_date=s.get("end_date"), start_time=s.get("start_time"),
        end_time=s.get("end_time"), timezone=s.get("timezone"),
        country_code=loc.get("country_code"), city=loc.get("city"), venue=loc.get("venue_name"),
        address=loc.get("address"), lat=loc.get("lat"), lng=loc.get("lng"),
        poster_url=d.get("poster_url"), summary=det.get("summary"), organizer=det.get("organizer"),
        guests=det.get("guests"), target_audience=part.get("target_audience"),
        exhibitors=part.get("exhibitors_or_brands"), capacity=part.get("estimated_capacity"),
        entry_fee=det.get("entry_fee"), tags=det.get("tags"),
        official_url=lk.get("official_url"), ticket_url=lk.get("ticket_or_register_url"),
        verified=meta.get("verified", True) is not False,
    )


def fetch(ctx: Context) -> list[dict]:
    out: dict[str, dict] = {}
    for path in sorted(config.COMMUNITY_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:  # bozuk bir dosya diğerlerini etkilemez
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log(f"community/{path.name} okunamadı: {type(exc).__name__}")
            continue
        items = data.get("events") if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        for item in items:
            try:
                e = from_schema(item) if isinstance(item, dict) else None
            except Exception:
                e = None
            if e:
                out[e["id"]] = e
    return list(out.values())
