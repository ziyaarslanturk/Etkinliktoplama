"""Uluslararası federasyonlar (F.I.C.C., UIAA). Sayfalar config/sources.json içinde tanımlıdır.

Yalnızca sayfada JSON-LD (schema.org/Event) veya .ics varsa kayıt üretir.
"""
from __future__ import annotations

from ..context import Context, SkipSource
from ..httpclient import log
from .pages import crawl_entry

NAME = "federations"


def fetch(ctx: Context) -> list[dict]:
    entries = ctx.sources_config().get("federations") or []
    if not entries:
        raise SkipSource("config/sources.json içinde 'federations' yok")
    out: dict[str, dict] = {}
    failed = tried = 0
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("enabled", True) is False:
            continue
        name = str(entry.get("name") or "federation")
        tried += 1
        try:  # her federasyon kendi bloğunda izole
            for e in crawl_entry(ctx, entry, f"federation_{name}"):
                out[e["id"]] = e
        except Exception as exc:
            failed += 1
            log(f"federations/{name} hatası: {type(exc).__name__}: {exc}")
    if tried and failed == tried and not out:
        raise RuntimeError("tüm federasyon sayfalarına ulaşılamadı")
    return list(out.values())
