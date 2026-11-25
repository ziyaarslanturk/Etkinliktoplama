"""Yerel resmî kaynaklar: TOBB Fuar Takvimi (Türkiye) + config/sources.json 'local_official' sayfaları.

TOBB tablosu başlıkları (Fuar Adı / Tarih / Şehir ...) tanınırsa ayrıştırılır; tanınmazsa kayıt üretilmez.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from ..context import Context, SkipSource
from ..httpclient import fetch_text, log
from ..normalize import make_event
from ..taxonomy import classify
from .pages import crawl_entry

NAME = "local_official"
_DATE_RX = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")


def _fold(s: str) -> str:
    return (s or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower().replace("ş", "s") \
        .replace("ğ", "g").replace("ç", "c").replace("ö", "o").replace("ü", "u").strip()


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, str | None]]] = []
        self._row = None
        self._cell = None
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell, self._href = [], None
        elif tag == "a" and self._cell is not None and self._href is None:
            self._href = dict(attrs).get("href")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append((" ".join("".join(self._cell).split()), self._href))
            self._cell = self._href = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _iso(d: tuple[str, str, str]) -> str:
    return f"{d[2]}-{int(d[1]):02d}-{int(d[0]):02d}"


def parse_tobb(html: str, page_url: str) -> list[dict]:
    p = _TableParser()
    try:
        p.feed(html)
    except Exception:
        return []
    cols: dict[str, int] = {}
    out = []
    for row in p.rows:
        texts = [_fold(c[0]) for c in row]
        if not cols and any("fuar" in t and ("ad" in t or "isim" in t) for t in texts):
            for i, t in enumerate(texts):
                if ("fuar" in t and ("ad" in t or "isim" in t)) or t in ("adi", "etkinlik adi"):
                    cols.setdefault("title", i)
                elif "baslangic" in t:
                    cols["start"] = i
                elif "bitis" in t:
                    cols["end"] = i
                elif "tarih" in t:
                    cols.setdefault("date", i)
                elif t in ("il", "sehir") or "sehir" in t:
                    cols["city"] = i
                elif "alan" in t or "merkez" in t or "mekan" in t or t == "yer":
                    cols["venue"] = i
                elif "organizator" in t or "duzenleyen" in t:
                    cols["org"] = i
            continue
        if "title" not in cols or ("start" not in cols and "date" not in cols):
            continue
        try:
            def cell(k):
                i = cols.get(k)
                return row[i][0] if i is not None and i < len(row) else None
            title = cell("title")
            if cols.get("start") is not None:
                s, e = _DATE_RX.search(cell("start") or ""), _DATE_RX.search(cell("end") or "")
                start, end = (_iso(s.groups()) if s else None), (_iso(e.groups()) if e else None)
            else:
                ds = _DATE_RX.findall(cell("date") or "")
                start = _iso(ds[0]) if ds else None
                end = _iso(ds[-1]) if len(ds) > 1 else None
            href = row[cols["title"]][1] if cols["title"] < len(row) else None
            out.append({"title": title, "start": start, "end": end, "city": cell("city"),
                        "venue": cell("venue"), "organizer": cell("org"), "href": href})
        except Exception:
            continue
    return out


def _tobb(ctx: Context, cfg: dict) -> list[dict]:
    tpl = cfg.get("url_template") or "https://fuarlar.tobb.org.tr/FuarTakvimi/{year}"
    years = range(ctx.today.year, ctx.today.year + 1 + int(cfg.get("years_ahead", 1)))
    out: dict[str, dict] = {}
    from urllib.parse import urljoin
    reached = 0
    for y in years:
        if ctx.expired():
            break
        url = tpl.format(year=y)
        body = fetch_text(url, retries=2, timeout=30, pause=0.5)
        if not body:
            continue
        reached += 1
        for r in parse_tobb(body, url):
            cls = classify(r["title"])
            if not cls:
                continue
            e = make_event(
                source="tobb_fuar_takvimi", title=r["title"], interest=cls[0], sub_type=cls[1],
                start_date=r["start"], end_date=r["end"], country_code="TR", timezone="Europe/Istanbul",
                city=r["city"], venue=r["venue"], organizer=r["organizer"],
                official_url=urljoin(url, r["href"]) if r.get("href") else url, verified=True)
            if e:
                out[e["id"]] = e
    if reached == 0 and not ctx.expired():
        raise RuntimeError("TOBB sayfasına ulaşılamadı")
    return list(out.values())


def fetch(ctx: Context) -> list[dict]:
    cfg = ctx.sources_config()
    out: dict[str, dict] = {}
    ran = False
    failed = tried = 0
    tobb = cfg.get("tobb") or {}
    if tobb.get("enabled", False):
        ran = True
        tried += 1
        try:
            for e in _tobb(ctx, tobb):
                out[e["id"]] = e
        except Exception as exc:
            failed += 1
            log(f"local_official/tobb hatası: {type(exc).__name__}: {exc}")
    for entry in cfg.get("local_official") or []:
        if not isinstance(entry, dict) or entry.get("enabled", True) is False:
            continue
        ran = True
        tried += 1
        name = str(entry.get("name") or "local")
        try:
            for e in crawl_entry(ctx, entry, f"local_{name}"):
                out[e["id"]] = e
        except Exception as exc:
            failed += 1
            log(f"local_official/{name} hatası: {type(exc).__name__}: {exc}")
    if not ran:
        raise SkipSource("etkin yerel kaynak yok")
    if failed == tried and not out:
        raise RuntimeError("yerel resmî kaynaklara ulaşılamadı")
    return list(out.values())
