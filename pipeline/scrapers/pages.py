"""Yapılandırılmış (config/sources.json) sayfa kaynaklarını JSON-LD / iCal ile tarayan ortak yardımcı."""
from __future__ import annotations

from .. import feeds
from ..context import Context
from ..httpclient import fetch_text, log
from ..normalize import make_event
from ..taxonomy import classify


def _to_event(rec: dict, entry: dict, source: str, page_url: str) -> dict | None:
    title = rec.get("title")
    text = f"{title or ''} {rec.get('summary') or ''}"
    cls = classify(text)
    if not cls and entry.get("default_interest"):
        cls = (entry["default_interest"], entry.get("default_sub_type"))
    if not cls:
        return None
    return make_event(
        source=source, title=title, interest=cls[0], sub_type=cls[1],
        start_date=rec.get("start"), end_date=rec.get("end"),
        start_time=rec.get("start_time") or rec.get("start"),
        country_code=rec.get("country") or entry.get("default_country"),
        city=rec.get("city"), venue=rec.get("venue"), address=rec.get("address"),
        lat=rec.get("lat"), lng=rec.get("lng"), poster_url=rec.get("poster"),
        summary=rec.get("summary"), organizer=rec.get("organizer") or entry.get("organizer"),
        entry_fee=rec.get("fee"), ticket_url=rec.get("ticket"),
        official_url=rec.get("url") or None, verified=True,
    )


def crawl_entry(ctx: Context, entry: dict, source: str) -> list[dict]:
    """Bir yapılandırma girdisindeki sayfaları (ve izin verilen alt bağlantıları) tarar."""
    out: dict[str, dict] = {}
    follow = entry.get("follow") or {}
    max_pages = int(follow.get("max_pages", 0))
    queue: list[str] = list(entry.get("pages") or [])
    visited: set[str] = set()
    reached = 0
    start_pages = len(queue)
    while queue and not ctx.expired():
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        body = fetch_text(url, retries=2, timeout=25, pause=0.5)
        if body is None:
            continue
        reached += 1
        recs: list[dict] = []
        if url.lower().split("?")[0].endswith(".ics") or body.lstrip().startswith("BEGIN:VCALENDAR"):
            recs = feeds.ics_events(body)
            for r in recs:  # .ics içinde URL yoksa kaynak sayfa URL'si gerçek bir kaynak bağlantısıdır
                r.setdefault("url", None)
                if not r.get("url"):
                    r["url"] = url
        else:
            recs = feeds.jsonld_events(body, url)
            for r in recs:
                if not r.get("url"):
                    r["url"] = url  # etkinliği barındıran sayfanın kendisi
            if max_pages and len(visited) <= max_pages:
                for link in feeds.page_links(body, url, follow.get("path_contains") or [], max_pages):
                    if link not in visited and len(visited) + len(queue) < max_pages:
                        queue.append(link)
        for r in recs:
            try:
                e = _to_event(r, entry, source, url)
            except Exception as exc:
                log(f"{source} kayıt hatası: {type(exc).__name__}")
                continue
            if e:
                out[e["id"]] = e
    if start_pages and reached == 0:
        raise RuntimeError("sayfalara ulaşılamadı")
    return list(out.values())
