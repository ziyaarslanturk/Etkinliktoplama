"""Genel sayfa ayrıştırıcıları: JSON-LD (schema.org/Event) ve iCalendar (.ics).

Yalnızca sayfada AÇIKÇA yapılandırılmış veri varsa kayıt üretir. Serbest metinden tarih tahmini yapılmaz.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from .normalize import clean_text
from .taxonomy import ISO_COUNTRIES

_LD_RX = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
_HREF_RX = re.compile(r"""<a\s[^>]*href=["']([^"'#]+)["']""", re.I)


def _is_event_type(t) -> bool:
    ts = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and (x.endswith("Event") or x in ("Festival", "Event")) for x in ts)


def _walk(node, out: list):
    if isinstance(node, list):
        for x in node:
            _walk(x, out)
    elif isinstance(node, dict):
        if _is_event_type(node.get("@type")):
            out.append(node)
        for k in ("@graph", "itemListElement", "item", "event", "subEvent"):
            if k in node:
                _walk(node[k], out)


def _first(v):
    return v[0] if isinstance(v, list) and v else v


def _country2(v) -> str | None:
    v = _first(v)
    if isinstance(v, dict):
        v = v.get("name") or v.get("identifier")
    if isinstance(v, str) and len(v.strip()) == 2 and v.strip().upper() in ISO_COUNTRIES:
        return v.strip().upper()
    return None


def jsonld_events(html: str, page_url: str) -> list[dict]:
    """Sayfadaki JSON-LD Event kayıtlarını düz sözlüklere çevirir."""
    found: list[dict] = []
    for block in _LD_RX.findall(html or ""):
        try:
            _walk(json.loads(block.strip()), found)
        except (ValueError, RecursionError):
            continue
    out = []
    for n in found:
        loc = _first(n.get("location")) or {}
        if not isinstance(loc, dict):
            loc = {}
        addr = loc.get("address") or {}
        if isinstance(addr, str):
            addr = {"streetAddress": addr}
        geo = loc.get("geo") or {}
        offers = _first(n.get("offers")) or {}
        org = _first(n.get("organizer")) or {}
        img = _first(n.get("image"))
        if isinstance(img, dict):
            img = img.get("url")
        url = n.get("url")
        if isinstance(url, str):
            url = urljoin(page_url, url)
        fee = None
        if isinstance(offers, dict) and offers.get("price") not in (None, ""):
            fee = f"{offers.get('price')} {offers.get('priceCurrency') or ''}".strip()
        out.append({
            "title": n.get("name"),
            "start": n.get("startDate"),
            "end": n.get("endDate"),
            "url": url,
            "summary": n.get("description"),
            "poster": urljoin(page_url, img) if isinstance(img, str) else None,
            "venue": loc.get("name"),
            "city": addr.get("addressLocality"),
            "address": addr.get("streetAddress"),
            "country": _country2(addr.get("addressCountry")),
            "lat": geo.get("latitude"),
            "lng": geo.get("longitude"),
            "organizer": org.get("name") if isinstance(org, dict) else None,
            "fee": fee,
            "ticket": offers.get("url") if isinstance(offers, dict) else None,
        })
    return out


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _ics_unescape(s: str) -> str:
    return s.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _ics_dt(value: str) -> tuple[str | None, str | None]:
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?", value.strip())
    if not m:
        return None, None
    d = f"{m[1]}-{m[2]}-{m[3]}"
    t = f"{m[4]}:{m[5]}" if m[4] else None
    return d, t


def ics_events(text: str) -> list[dict]:
    out, cur = [], None
    for line in _unfold(text or ""):
        if line.strip() == "BEGIN:VEVENT":
            cur = {}
        elif line.strip() == "END:VEVENT":
            if cur is not None:
                out.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, _, val = line.partition(":")
            name = head.split(";")[0].upper()
            if name in ("SUMMARY", "DESCRIPTION", "LOCATION", "URL"):
                cur[name.lower()] = _ics_unescape(val)
            elif name in ("DTSTART", "DTEND"):
                d, t = _ics_dt(val)
                date_only = "VALUE=DATE" in head.upper() and "DATE-TIME" not in head.upper()
                cur[name.lower()] = d
                cur[name.lower() + "_time"] = None if date_only else t
                if name == "DTEND" and date_only and d:
                    cur["dtend_exclusive"] = True  # tüm gün etkinliklerinde DTEND ertesi gündür
    res = []
    for e in out:
        end = e.get("dtend")
        if end and e.get("dtend_exclusive"):
            from datetime import date, timedelta
            try:
                y, m, d = map(int, end.split("-"))
                end = (date(y, m, d) - timedelta(days=1)).isoformat()
            except ValueError:
                end = None
        res.append({"title": e.get("summary"), "start": e.get("dtstart"), "end": end,
                    "start_time": e.get("dtstart_time"), "url": e.get("url"),
                    "summary": e.get("description"), "venue": e.get("location")})
    return res


def page_links(html: str, base_url: str, path_contains: list[str], max_links: int) -> list[str]:
    host = urlparse(base_url).netloc
    seen, out = set(), []
    for href in _HREF_RX.findall(html or ""):
        full = urljoin(base_url, href.strip())
        p = urlparse(full)
        if p.scheme not in ("http", "https") or p.netloc != host:
            continue
        if path_contains and not any(s in p.path for s in path_contains):
            continue
        key = full.split("?")[0]
        if key in seen or key.rstrip("/") == base_url.rstrip("/"):
            continue
        seen.add(key)
        out.append(full)
        if len(out) >= max_links:
            break
    return out


def clean(v, n=None):
    return clean_text(v, n)
