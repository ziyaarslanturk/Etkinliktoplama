"""Boru hattı giriş noktası:  python -m pipeline.main

Akış: kaynakları izole çalıştır -> doğrula -> (hatalı kaynaklar için önceki yayından taşı) -> süresi
geçenleri sil -> tekilleştir -> site/ klasörüne yaz. Tekil kaynak hataları asla süreci çökertmez.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from . import config
from .context import Context, SkipSource
from .httpclient import fetch_json, log, redact
from .normalize import is_expired, richness, validate_event_dict
from .scrapers import SCRAPERS


def run_sources(ctx: Context) -> tuple[list[dict], list[dict]]:
    events: list[dict] = []
    status: list[dict] = []
    for mod in SCRAPERS:
        name = getattr(mod, "NAME", None) or getattr(mod, "__name__", "bilinmeyen")
        t0 = time.monotonic()
        st = {"source": name, "status": "ok", "accepted": 0, "error": None, "seconds": 0.0}
        if ctx.expired():
            st.update(status="skipped", error="zaman bütçesi doldu")
            status.append(st)
            continue
        try:
            res = mod.fetch(ctx) or []
            st["accepted"] = len(res)
            st["status"] = "ok" if res else "empty"
            events.extend(res)
        except SkipSource as s:
            st.update(status="skipped", error=redact(str(s)))
        except BaseException as exc:  # KeyboardInterrupt dışında hepsi izole
            if isinstance(exc, KeyboardInterrupt):
                raise
            st.update(status="error", error=redact(f"{type(exc).__name__}: {exc}")[:300])
            log(f"[{name}] HATA (diğer kaynaklar devam ediyor): {st['error']}")
        st["seconds"] = round(time.monotonic() - t0, 1)
        log(f"[{name}] {st['status']} kabul={st['accepted']} {st['seconds']}s")
        status.append(st)
    return events, status


def carry_over(ctx: Context, status: list[dict]) -> list[dict]:
    """Hata veren kaynakların önceki yayındaki (hâlâ geçerli) kayıtlarını korur; yeni veri uydurmaz."""
    failed = {s["source"] for s in status if s["status"] == "error"}
    url = (ctx.env.get("PREVIOUS_EVENTS_URL") or "").strip()
    if not failed or not url:
        return []
    prev = fetch_json(url, retries=2, timeout=30)
    items = prev.get("events") if isinstance(prev, dict) else None
    if not isinstance(items, list):
        return []
    kept = [e for e in items if isinstance(e, dict) and (e.get("meta") or {}).get("source") in failed
            and validate_event_dict(e)]
    log(f"Önceki yayından taşınan kayıt: {len(kept)} (hatalı kaynaklar: {sorted(failed)})")
    return kept


def finalize(events: list[dict], ctx: Context) -> tuple[list[dict], dict]:
    fresh = [e for e in events if not is_expired(e, ctx.today)]
    expired = len(events) - len(fresh)
    best: dict[str, dict] = {}
    for e in fresh:
        cur = best.get(e["id"])
        if cur is None or richness(e) > richness(cur):
            best[e["id"]] = e
    final = sorted(best.values(), key=lambda e: (e["schedule"]["start_date"], e["location"]["country_code"], e["title"]))
    return final, {"expired_removed": expired, "duplicates_removed": len(fresh) - len(final)}


def write_site(events: list[dict], status: list[dict], extra: dict, ctx: Context, out_dir: Path) -> None:
    from .normalize import now_iso
    from .taxonomy import TAXONOMY

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "events").mkdir(exist_ok=True)
    for old in (out_dir / "events").glob("*.json"):
        old.unlink()
    generated = now_iso()

    def dump(path: Path, obj) -> None:
        path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    dump(out_dir / "events.json", {"generated_at": generated, "count": len(events), "events": events})
    by_cc: dict[str, list[dict]] = {}
    for e in events:
        by_cc.setdefault(e["location"]["country_code"], []).append(e)
    countries = []
    for cc, items in sorted(by_cc.items()):
        dump(out_dir / "events" / f"{cc}.json", {"generated_at": generated, "country_code": cc,
                                                 "count": len(items), "events": items})
        countries.append({"country_code": cc, "count": len(items),
                          "interests": dict(Counter(i["classification"]["interest"] for i in items))})
    dump(out_dir / "countries.json", {"generated_at": generated, "countries": countries})
    dump(out_dir / "taxonomy.json", TAXONOMY)
    dump(out_dir / "status.json", {"generated_at": generated, "today_utc": ctx.today.isoformat(),
                                   "total_events": len(events), "sources": status, **extra})
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    rows = "".join(f"<tr><td>{s['source']}</td><td>{s['status']}</td><td>{s['accepted']}</td></tr>" for s in status)
    (out_dir / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Kamp &amp; Doğa Etkinlikleri Verisi</title>"
        "<body style='font-family:system-ui;max-width:42rem;margin:2rem auto;padding:0 1rem'>"
        f"<h1>Kamp &amp; Doğa Etkinlikleri Verisi</h1><p>Güncelleme: {generated} &middot; Etkinlik: {len(events)}</p>"
        "<ul><li><a href='events.json'>events.json</a></li><li><a href='countries.json'>countries.json</a></li>"
        "<li><a href='taxonomy.json'>taxonomy.json</a></li><li><a href='status.json'>status.json</a></li></ul>"
        f"<table border=1 cellpadding=6 style='border-collapse:collapse'><tr><th>Kaynak</th><th>Durum</th><th>Kayıt</th></tr>{rows}</table>"
        "</body>", encoding="utf-8")


def main() -> int:
    ctx = Context()
    try:
        raw, status = run_sources(ctx)
        raw += carry_over(ctx, status)
        events, extra = finalize(raw, ctx)
        write_site(events, status, extra, ctx, config.SITE_DIR)
    except Exception as exc:  # yayını bozmamak için: başarısız çıkış -> deploy işi çalışmaz, eski yayın kalır
        log(f"KRİTİK HATA: {type(exc).__name__}: {exc}")
        return 1
    log(f"Bitti: {len(events)} etkinlik, {extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
